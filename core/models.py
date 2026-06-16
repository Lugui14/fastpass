import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.conf import settings


class UsuarioManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, nome, tipo, password=None, **extra_fields):
        if not email:
            raise ValueError("O email é obrigatório")

        email = self.normalize_email(email)
        user = self.model(email=email, nome=nome, tipo=tipo, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, nome, tipo, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)

        return self._create_user(email, nome, tipo, password, **extra_fields)

    def create_superuser(self, email, nome, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        return self._create_user(email, nome, "adm", password, **extra_fields)


class Usuario(AbstractUser):
    TIPOS = [
        ("estudante", "Estudante"),
        ("empresa", "Empresa"),
        ("adm", "Administrador"),
    ]

    username = None
    first_name = None
    last_name = None

    nome = models.CharField(max_length=100)
    email = models.CharField(max_length=150, unique=True)
    tipo = models.CharField(max_length=10, choices=TIPOS)
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["nome", "tipo"]

    objects = UsuarioManager()

    class Meta:
        db_table = "usuario"


class Estudante(models.Model):
    cpf = models.CharField(max_length=12)
    matricula = models.CharField(max_length=15)
    data_nascimento = models.DateTimeField(null=True, blank=True)
    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="estudante_perfil")

    def nome(self):
        return self.usuario.nome

    class Meta:
        db_table = "estudante"


class Empresa(models.Model):
    cnpj = models.CharField(max_length=14)
    ativo = models.IntegerField(default=1)
    dados_saque = models.CharField(max_length=255, null=True, blank=True)
    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="empresa_perfil")

    def nome(self):
        return self.usuario.nome

    class Meta:
        db_table = "empresa"


class Conta(models.Model):
    saldo = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conta")

    class Meta:
        db_table = "conta"


class Produto(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="produtos")
    nome = models.CharField(max_length=50)
    valor = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "produto"


class Transacao(models.Model):
    OPERACOES = [
        ("debito", "Débito"),
        ("credito", "Crédito"),
    ]

    operacao = models.CharField(max_length=10, choices=OPERACOES)
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    conta = models.ForeignKey(Conta, on_delete=models.PROTECT, related_name="transacoes")
    data_hora = models.DateTimeField(auto_now_add=True)
    descricao = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "transacao"


class Venda(models.Model):
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT, related_name="vendas")
    estudante = models.ForeignKey(Estudante, on_delete=models.PROTECT, related_name="vendas")
    valor_unidade = models.DecimalField(max_digits=12, decimal_places=2)
    quantidade = models.IntegerField(default=1)
    valor_total = models.DecimalField(max_digits=12, decimal_places=2)
    transacao = models.ForeignKey(Transacao, on_delete=models.PROTECT, related_name="vendas")

    class Meta:
        db_table = "venda"


class Saque(models.Model):
    SITUACOES = [
        ("pendente", "Pendente"),
        ("aprovado", "Aprovado"),
        ("recusado", "Recusado"),
    ]

    transacao = models.OneToOneField(Transacao, on_delete=models.PROTECT, related_name="saque")
    situacao = models.CharField(max_length=10, default="pendente", choices=SITUACOES)
    metodo_pagamento = models.CharField(max_length=255)
    descricao = models.TextField()
    adm_responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="saques_gerenciados"
    )

    class Meta:
        db_table = "saque"


class Deposito(models.Model):
    transacao = models.OneToOneField(Transacao, on_delete=models.PROTECT, related_name="deposito")
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    situacao = models.CharField(max_length=255)
    metodo_pagamento = models.CharField(max_length=255)
    descricao = models.CharField(max_length=255)

    class Meta:
        db_table = "deposito"
