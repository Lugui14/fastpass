from abc import ABC, abstractmethod
import uuid

class PaymentGatewayInterface(ABC):
    @abstractmethod
    def gerar_pix_deposito(self, valor, transacao_id):
        """
        Retorna um dicionário contendo:
        - qr_code_copy_paste: A chave/código PIX copia e cola
        - qr_code_image_url: Link da imagem do QR Code
        - payment_url: Link de checkout simulado
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
