from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, TemplateView
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from .forms import RegisterForm
from .models import Transacao, Venda, Saque

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
