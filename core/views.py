from decimal import Decimal, InvalidOperation
from django.shortcuts import render, redirect
from django.db import transaction
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, TemplateView
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from .forms import RegisterForm, EditarPerfilForm
from .models import Transacao, Venda, Saque, Deposito, Usuario, Estudante, Empresa, Conta, Produto
from .services.payment import AbacatePayGateway, confirmar_deposito

class RegisterView(CreateView):
    template_name = "core/register.html"
    form_class = RegisterForm
    success_url = reverse_lazy("login")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Cadastro realizado com sucesso! Faça login para continuar.")
        return response


class CustomLoginView(LoginView):
    template_name = "core/login.html"
    redirect_authenticated_user = True


class CustomLogoutView(LogoutView):
    next_page = reverse_lazy("login")


class HomeView(LoginRequiredMixin, TemplateView):
    def get(self, request, *args, **kwargs):
        tipo = request.user.tipo
        if tipo == "estudante":
            return redirect("student_dashboard")
        elif tipo == "empresa":
            return redirect("company_dashboard")
        elif tipo == "adm" or request.user.is_superuser:
            return redirect("admin_dashboard")
        else:
            messages.error(request, "Tipo de usuário não identificado.")
            return redirect("login")


class StudentDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "core/student_dashboard.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.tipo != "estudante":
            messages.error(request, "Acesso restrito a estudantes.")
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context["estudante"] = user.estudante_perfil
        context["conta"] = user.conta
        # List of transactions for this student
        context["transacoes"] = Transacao.objects.filter(conta=user.conta).order_by("-data_hora")[:10]
        return context


class CompanyDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "core/company_dashboard.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.tipo != "empresa":
            messages.error(request, "Acesso restrito a empresas.")
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context["empresa"] = user.empresa_perfil
        context["conta"] = user.conta
        context["produtos"] = user.empresa_perfil.produtos.all()
        # List of transactions for this company
        context["transacoes"] = Transacao.objects.filter(conta=user.conta).order_by("-data_hora")[:10]
        return context


class AdminDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "core/admin_dashboard.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.tipo != "adm" and not request.user.is_superuser:
            messages.error(request, "Acesso restrito a administradores.")
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # List pending withdraws
        context["saques_pendentes"] = Saque.objects.filter(situacao="pendente").order_by("-transacao__data_hora")
        return context


class SolicitarDepositoView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        if request.user.tipo != "estudante":
            messages.error(request, "Acesso restrito a estudantes.")
            return redirect("home")
            
        valor_str = request.POST.get("valor")
        try:
            valor = Decimal(valor_str)
            if valor <= 0:
                raise ValueError("O valor deve ser positivo.")
        except (TypeError, ValueError, InvalidOperation):
            messages.error(request, "Valor de recarga inválido.")
            return redirect("student_dashboard")

        # 1. Criar Transação pendente
        transacao = Transacao.objects.create(
            operacao="credito",
            valor=0.00,  # Fica 0.00 até ser verificado
            conta=request.user.conta,
            descricao="Recarga PIX pendente"
        )
        
        # 2. Criar Depósito pendente
        Deposito.objects.create(
            transacao=transacao,
            valor=valor,
            situacao="pendente",
            metodo_pagamento="pix",
            descricao=f"PIX-DEP-{transacao.id}"
        )
        
        # 3. Chamar Gateway Abacate Pay
        gateway = AbacatePayGateway()
        payment_data = gateway.gerar_pix_deposito(valor, transacao.id)
        
        # Salva na sessão para exibição no checkout
        request.session[f"checkout_{transacao.id}"] = payment_data
        
        return redirect("checkout_deposito", transacao_id=transacao.id)


class CheckoutDepositoView(LoginRequiredMixin, TemplateView):
    template_name = "core/checkout_deposito.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        transacao_id = self.kwargs.get("transacao_id")
        try:
            transacao = Transacao.objects.get(id=transacao_id, conta=self.request.user.conta)
            deposito = transacao.deposito
            context["transacao"] = transacao
            context["deposito"] = deposito
            
            # Recupera dados gerados pelo gateway
            payment_data = self.request.session.get(f"checkout_{transacao_id}")
            if not payment_data:
                gateway = AbacatePayGateway()
                payment_data = gateway.gerar_pix_deposito(deposito.valor, transacao.id)
                self.request.session[f"checkout_{transacao_id}"] = payment_data
                
            context["payment"] = payment_data
        except (Transacao.DoesNotExist, Deposito.DoesNotExist):
            messages.error(self.request, "Pagamento não encontrado.")
            
        return context


class ConfirmarDepositoSimulacaoView(LoginRequiredMixin, View):
    """
    View de simulação de pagamento que o usuário aciona clicando em um botão
    na página de checkout para simular que pagou o PIX.
    """
    def post(self, request, *args, **kwargs):
        transacao_id = self.kwargs.get("transacao_id")
        try:
            transacao = Transacao.objects.get(id=transacao_id, conta=request.user.conta)
            deposito = transacao.deposito
            
            sucesso, msg = confirmar_deposito(deposito.id, deposito.valor)
            if sucesso:
                messages.success(request, "Recarga efetuada com sucesso!")
            else:
                messages.warning(request, msg)
        except (Transacao.DoesNotExist, Deposito.DoesNotExist):
            messages.error(request, "Transação inválida.")
            
        return redirect("student_dashboard")


import hmac
import hashlib
from django.conf import settings

def verificar_assinatura_abacatepay(raw_body, signature):
    ABACATEPAY_PUBLIC_KEY = "t9dXRhHHo3yDEj5pVDYz0frf7q6bMKyMRmxxCPIPp3RCplBfXRxqlC6ZpiWmOqj4L63qEaeUOtrCI8P0VMUgo6iIga2ri9ogaHFs0WIIywSMg0q7RmBfybe1E5XJcfC4IW3alNqym0tXoAKkzvfEjZxV6bE0oG2zJrNNYmUCKZyV0KZ3JS8Votf9EAWWYdiDkMkpbMdPggfh1EqHlVkMiTady6jOR3hyzGEHrIz2Ret0xHKMbiqkr9HS1JhNHDX9"

    if not ABACATEPAY_PUBLIC_KEY or not signature:
        return False

    import base64
    computed_digest = hmac.new(
        ABACATEPAY_PUBLIC_KEY.encode("utf-8"),
        raw_body,
        hashlib.sha256
    ).digest()

    computed_signature = base64.b64encode(computed_digest).decode("utf-8")
    
    return hmac.compare_digest(computed_signature, signature.strip())


@method_decorator(csrf_exempt, name="dispatch")
class ConfirmarDepositoWebhookView(View):
    """
    Webhook público para processar callbacks do Abacate Pay.
    """
    def post(self, request, *args, **kwargs):
        import json
        try:
            # 1. Verificar assinatura e query parameter se a chave secreta do webhook estiver configurada
            webhook_secret = getattr(settings, "ABACATE_PAY_WEBHOOK_SECRET", "")
            if webhook_secret:
                # Verificar o segredo na URL params
                req_secret = request.GET.get("webhookSecret", "")
                if not req_secret or not hmac.compare_digest(req_secret, webhook_secret):
                    return JsonResponse({"status": "error", "message": "Secret inválido nos parâmetros."}, status=400)

                # Verificar a assinatura HMAC nos headers
                signature = request.headers.get("X-Webhook-Signature")
                if not signature or not verificar_assinatura_abacatepay(request.body, signature):
                    return JsonResponse({"status": "error", "message": "Assinatura inválida."}, status=400)

            data = json.loads(request.body)

            # 2. Suporte ao formato mockado legado (para testes e simulação direta)
            deposito_id = data.get("deposito_id")
            if deposito_id:
                valor = Decimal(str(data.get("valor")))
                sucesso, msg = confirmar_deposito(deposito_id, valor)
                if sucesso:
                    return JsonResponse({"status": "success", "message": msg})
                return JsonResponse({"status": "error", "message": msg}, status=400)

            # 3. Formato do Abacate Pay Webhook
            event = data.get("event")
            if event != "billing.paid":
                return JsonResponse({"status": "success", "message": f"Evento {event} ignorado."})

            billing_data = data.get("data", {}).get("billing", {})
            billing_id = billing_data.get("id")
            status = billing_data.get("status")

            if status != "PAID":
                return JsonResponse({"status": "success", "message": f"Status {status} ignorado."})

            try:
                deposito = Deposito.objects.get(abacatepay_billing_id=billing_id)
            except Deposito.DoesNotExist:
                return JsonResponse({"status": "error", "message": f"Depósito não encontrado para o billing_id {billing_id}."}, status=404)

            # Valor pago (Abacate Pay envia o valor em centavos)
            amount_cents = billing_data.get("amount")
            if amount_cents:
                valor_pago = Decimal(str(amount_cents)) / Decimal("100")
            else:
                valor_pago = deposito.valor

            sucesso, msg = confirmar_deposito(deposito.id, valor_pago)
            if sucesso:
                return JsonResponse({"status": "success", "message": msg})
            return JsonResponse({"status": "error", "message": msg}, status=400)

        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=400)


class RegistrarVendaView(LoginRequiredMixin, View):
    """
    Registra a venda debitando do estudante e creditando na empresa de forma atômica e segura.
    """
    def post(self, request, *args, **kwargs):
        if request.user.tipo != "empresa":
            return JsonResponse({"status": "erro", "mensagem": "Acesso restrito a estabelecimentos."}, status=403)
            
        estudante_uuid = request.POST.get("estudante_uuid")
        produto_id = request.POST.get("produto_id")
        
        if not estudante_uuid or not produto_id:
            return JsonResponse({"status": "erro", "mensagem": "UUID do estudante e ID do produto são obrigatórios."}, status=400)
            
        try:
            # Encontra o estudante e o produto
            estudante_usuario = Usuario.objects.get(uuid=estudante_uuid, tipo="estudante")
            estudante = estudante_usuario.estudante_perfil
            produto = Produto.objects.get(id=produto_id, empresa=request.user.empresa_perfil)
            
            conta_estudante = estudante_usuario.conta
            conta_empresa = request.user.conta
            
            # 1. Validação rápida de saldo (pre-lock)
            if conta_estudante.saldo < produto.valor:
                return JsonResponse({"status": "erro", "mensagem": "Saldo do estudante insuficiente."}, status=400)
                
            # 2. Executa a transferência de saldo de forma atômica
            with transaction.atomic():
                # select_for_update para garantir concorrência segura e evitar double spending
                conta_est_locked = Conta.objects.select_for_update().get(id=conta_estudante.id)
                conta_emp_locked = Conta.objects.select_for_update().get(id=conta_empresa.id)
                
                # Re-validação de saldo após o lock
                if conta_est_locked.saldo < produto.valor:
                    return JsonResponse({"status": "erro", "mensagem": "Saldo do estudante insuficiente."}, status=400)
                
                # Deduz do estudante
                conta_est_locked.saldo -= produto.valor
                conta_est_locked.save()
                
                # Credita na empresa
                conta_emp_locked.saldo += produto.valor
                conta_emp_locked.save()
                
                # Registra as Transações
                trans_debito = Transacao.objects.create(
                    operacao="debito",
                    valor=produto.valor,
                    conta=conta_est_locked,
                    descricao=f"Compra: {produto.nome}"
                )
                
                trans_credito = Transacao.objects.create(
                    operacao="credito",
                    valor=produto.valor,
                    conta=conta_emp_locked,
                    descricao=f"Venda: {produto.nome} para {estudante.nome()}"
                )
                
                # Registra a Venda
                Venda.objects.create(
                    produto=produto,
                    estudante=estudante,
                    valor_unidade=produto.valor,
                    quantidade=1,
                    valor_total=produto.valor,
                    transacao=trans_debito
                )
                
            return JsonResponse({"status": "sucesso", "mensagem": "Acesso Autorizado! Débito efetuado."})
            
        except Usuario.DoesNotExist:
            return JsonResponse({"status": "erro", "mensagem": "Estudante não cadastrado ou UUID inválido."}, status=404)
        except Produto.DoesNotExist:
            return JsonResponse({"status": "erro", "mensagem": "Produto inválido ou não pertence a esta empresa."}, status=404)
        except Exception as e:
            return JsonResponse({"status": "erro", "mensagem": str(e)}, status=500)


class SolicitarSaqueView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        if request.user.tipo != "empresa":
            messages.error(request, "Acesso restrito a estabelecimentos.")
            return redirect("home")
            
        valor_str = request.POST.get("valor")
        chave_pix = request.POST.get("chave_pix")
        
        try:
            valor = Decimal(valor_str)
            if valor <= 0:
                raise ValueError("O valor deve ser positivo.")
        except (TypeError, ValueError, InvalidOperation):
            messages.error(request, "Valor de saque inválido.")
            return redirect("company_dashboard")
            
        if not chave_pix:
            messages.error(request, "Chave Pix de recebimento é obrigatória.")
            return redirect("company_dashboard")
            
        conta = request.user.conta
        
        if conta.saldo < valor:
            messages.error(request, "Saldo insuficiente para o saque solicitado.")
            return redirect("company_dashboard")
            
        try:
            with transaction.atomic():
                conta_locked = Conta.objects.select_for_update().get(id=conta.id)
                
                if conta_locked.saldo < valor:
                    messages.error(request, "Saldo insuficiente para o saque solicitado.")
                    return redirect("company_dashboard")
                    
                # 1. Deduct balance from vendor immediately
                conta_locked.saldo -= valor
                conta_locked.save()
                
                # 2. Create debit transaction
                transacao = Transacao.objects.create(
                    operacao="debito",
                    valor=valor,
                    conta=conta_locked,
                    descricao=f"Saque solicitado para chave Pix: {chave_pix}"
                )
                
                # 3. Create withdraw record
                Saque.objects.create(
                    transacao=transacao,
                    situacao="pendente",
                    metodo_pagamento="pix",
                    descricao=chave_pix
                )
                
                messages.success(request, f"Solicitação de saque de R$ {valor} enviada com sucesso!")
        except Exception as e:
            messages.error(request, f"Erro ao solicitar saque: {str(e)}")
            
        return redirect("company_dashboard")


class AprovarSaqueView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        if request.user.tipo != "adm" and not request.user.is_superuser:
            messages.error(request, "Acesso restrito a administradores.")
            return redirect("home")
            
        saque_id = self.kwargs.get("saque_id")
        try:
            with transaction.atomic():
                saque = Saque.objects.select_for_update().get(id=saque_id)
                if saque.situacao != "pendente":
                    messages.warning(request, "Este saque já foi processado.")
                    return redirect("admin_dashboard")
                    
                saque.situacao = "aprovado"
                saque.adm_responsavel = request.user
                saque.save()
                
                messages.success(request, f"Saque de R$ {saque.transacao.valor} aprovado com sucesso!")
        except Saque.DoesNotExist:
            messages.error(request, "Solicitação de saque não encontrada.")
        except Exception as e:
            messages.error(request, f"Erro ao aprovar saque: {str(e)}")
            
        return redirect("admin_dashboard")


class RecusarSaqueView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        if request.user.tipo != "adm" and not request.user.is_superuser:
            messages.error(request, "Acesso restrito a administradores.")
            return redirect("home")
            
        saque_id = self.kwargs.get("saque_id")
        try:
            with transaction.atomic():
                saque = Saque.objects.select_for_update().get(id=saque_id)
                if saque.situacao != "pendente":
                    messages.warning(request, "Este saque já foi processado.")
                    return redirect("admin_dashboard")
                    
                saque.situacao = "recusado"
                saque.adm_responsavel = request.user
                saque.save()
                
                # Devuelve el saldo retornado
                conta_empresa = saque.transacao.conta
                conta_locked = Conta.objects.select_for_update().get(id=conta_empresa.id)
                conta_locked.saldo += saque.transacao.valor
                conta_locked.save()
                
                # Registra transação de estorno (crédito)
                Transacao.objects.create(
                    operacao="credito",
                    valor=saque.transacao.valor,
                    conta=conta_locked,
                    descricao=f"Estorno de saque recusado (Saque ID: {saque.id})"
                )
                
                messages.success(request, f"Saque de R$ {saque.transacao.valor} recusado. Saldo estornado para a empresa.")
        except Saque.DoesNotExist:
            messages.error(request, "Solicitação de saque não encontrada.")
        except Exception as e:
            messages.error(request, f"Erro ao recusar saque: {str(e)}")
            
        return redirect("admin_dashboard")


class CriarProdutoView(LoginRequiredMixin, View):
    """
    Cadastra um novo produto/serviço para o estabelecimento logado.
    """
    def post(self, request, *args, **kwargs):
        if request.user.tipo != "empresa":
            messages.error(request, "Acesso restrito a estabelecimentos.")
            return redirect("home")
            
        nome = request.POST.get("nome")
        valor_str = request.POST.get("valor")
        
        if not nome:
            messages.error(request, "O nome do produto é obrigatório.")
            return redirect("company_dashboard")
            
        try:
            valor = Decimal(valor_str)
            if valor <= 0:
                raise ValueError("O valor deve ser positivo.")
        except (TypeError, ValueError, InvalidOperation):
            messages.error(request, "Valor do produto inválido.")
            return redirect("company_dashboard")
            
        try:
            Produto.objects.create(
                empresa=request.user.empresa_perfil,
                nome=nome,
                valor=valor
            )
            messages.success(request, f"Produto '{nome}' cadastrado com sucesso!")
        except Exception as e:
            messages.error(request, f"Erro ao cadastrar produto: {str(e)}")
            
        return redirect("company_dashboard")


class EditarPerfilView(LoginRequiredMixin, View):
    template_name = "core/editar_perfil.html"

    def get(self, request, *args, **kwargs):
        form = EditarPerfilForm(instance=request.user)
        return render(request, self.template_name, {"form": form})

    def post(self, request, *args, **kwargs):
        form = EditarPerfilForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Perfil atualizado com sucesso!")
            return redirect("editar_perfil")
        return render(request, self.template_name, {"form": form})
