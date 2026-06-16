from abc import ABC, abstractmethod
import uuid
import logging
import urllib.request
import urllib.parse
import json
from django.conf import settings

logger = logging.getLogger(__name__)

class PaymentGatewayInterface(ABC):
    @abstractmethod
    def gerar_pix_deposito(self, valor, transacao_id):
        """
        Retorna um dicionário contendo:
        - qr_code_copy_paste: A chave/código PIX copia e cola ou URL de checkout
        - qr_code_image_url: Link da imagem do QR Code
        - payment_url: Link de checkout real/simulado
        """
        pass


class MockPaymentGateway(PaymentGatewayInterface):
    def gerar_pix_deposito(self, valor, transacao_id):
        # Gera dados de pagamento simulados para homologação local
        mock_uuid = uuid.uuid4()
        return {
            "qr_code_copy_paste": f"00020126580014BR.GOV.BCB.PIX0136{mock_uuid}5204000053039865405{valor:.2f}5802BR5913FastPass UFFS6009Chapeco62070503***6304",
            "qr_code_image_url": "https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=MockFastPassPixPayment",
            "payment_url": f"/deposito/checkout/{transacao_id}/"
        }


class AbacatePayGateway(PaymentGatewayInterface):
    def gerar_pix_deposito(self, valor, transacao_id):
        from core.models import Transacao
        try:
            transacao = Transacao.objects.get(id=transacao_id)
            usuario = transacao.conta.usuario
            email = usuario.email
            nome = usuario.nome
        except Transacao.DoesNotExist:
            email = "estudante@uffs.edu.br"
            nome = "Estudante UFFS"

        # O valor na API do Abacate Pay é passado em centavos (inteiro)
        valor_centavos = int(valor * 100)
        api_key = getattr(settings, "ABACATE_PAY_API_KEY", "")
        
        import sys
        # Se não houver chave de API ou se for ambiente de testes, usa dados mockados do Abacate Pay
        is_test_env = False
        try:
            is_test_env = 'test' in sys.argv or 'test_coverage' in sys.argv or "test" in settings.DATABASES["default"]["NAME"] or not api_key or api_key == "mock"
        except Exception:
            is_test_env = True

        if is_test_env:
            logger.info("Usando checkout do Abacate Pay mockado para ambiente local/testes.")
            billing_id = f"bill_{uuid.uuid4()}"
            checkout_url = f"https://pay.abacatepay.com/bill-{billing_id}"
            
            # Atualiza informações de faturamento no depósito correspondente
            try:
                deposito = transacao.deposito
                deposito.abacatepay_billing_id = billing_id
                deposito.abacatepay_checkout_url = checkout_url
                deposito.save()
            except Exception as e:
                logger.exception(f"Erro ao salvar dados de faturamento mockados no Depósito: {e}")
                
            return {
                "qr_code_copy_paste": checkout_url,
                "qr_code_image_url": f"https://api.qrserver.com/v1/create-qr-code/?size=250x250&data={urllib.parse.quote(checkout_url)}",
                "payment_url": checkout_url
            }

        app_url = getattr(settings, "APP_URL", "http://localhost:8000").rstrip("/")

        payload = {
            "frequency": "ONE_TIME",
            "methods": ["PIX"],
            "products": [
                {
                    "externalId": f"prod-dep-{transacao_id}",
                    "name": "Recarga de Saldo - FastPass UFFS",
                    "description": f"Destinado para carteira digital de: {nome} ({email})",
                    "quantity": 1,
                    "price": valor_centavos
                }
            ],
            "customer": {
                "name": nome,
                "email": email,
                "cellphone": "99999999999"
            },
            # URLs de retorno ao concluir ou voltar do Abacate Pay
            "returnUrl": f"{app_url}/deposito/checkout/{transacao_id}/",
            "completionUrl": f"{app_url}/dashboard/estudante/",
            "externalId": str(transacao_id),
            "metadata": {
                "transacao_id": str(transacao_id)
            }
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        req = urllib.request.Request(
            "https://api.abacatepay.com/v1/billing/create",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                res_body = json.loads(response.read().decode("utf-8"))
                billing_data = res_body.get("data", {})
                billing_id = billing_data.get("id")
                checkout_url = billing_data.get("url")

                # Atualiza dados de faturamento do Abacate Pay no depósito correspondente
                try:
                    deposito = transacao.deposito
                    deposito.abacatepay_billing_id = billing_id
                    deposito.abacatepay_checkout_url = checkout_url
                    deposito.save()
                except Exception as e:
                    logger.error(f"Erro ao salvar dados de faturamento no Depósito: {e}")

                return {
                    "qr_code_copy_paste": checkout_url,
                    "qr_code_image_url": f"https://api.qrserver.com/v1/create-qr-code/?size=250x250&data={urllib.parse.quote(checkout_url)}",
                    "payment_url": checkout_url
                }
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            logger.error(f"Erro na API do Abacate Pay: Status {e.code}, Corpo: {error_body}")
            raise Exception(f"Erro na API do Abacate Pay: {error_body}")
        except Exception as e:
            logger.error(f"Erro de conexão com Abacate Pay: {e}")
            raise e


from django.db import transaction
from core.models import Deposito, Conta

@transaction.atomic
def confirmar_deposito(deposito_id, valor_pago):
    try:
        deposito = Deposito.objects.select_for_update().get(id=deposito_id)
        if deposito.situacao == "pendente":
            deposito.situacao = "confirmado"
            deposito.save()

            # Atualizar saldo da conta do usuário
            conta = Conta.objects.select_for_update().get(usuario=deposito.transacao.conta.usuario)
            conta.saldo += valor_pago
            conta.save()

            # Atualizar a transação correspondente
            transacao = deposito.transacao
            transacao.valor = valor_pago
            transacao.save()
            return True, "Depósito confirmado com sucesso!"
        return False, "Depósito já foi processado anteriormente."
    except Deposito.DoesNotExist:
        return False, "Depósito não encontrado."
