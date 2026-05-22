from django.contrib import admin

from .models import Usuario, Estudante, Empresa, Conta, Produto, Transacao


@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ("nome", "email", "tipo", "is_superuser", "is_staff")
    list_filter = ("nome", "email", "tipo", "is_superuser", "is_staff")
    search_fields = ("nome", "email", "tipo", "is_superuser", "is_staff")
    ordering = ("nome", "email", "tipo", "is_superuser", "is_staff")
    fieldsets = (("Informações do Usuário", {"fields": ("nome", "email", "tipo", "is_superuser", "is_staff")}),)


@admin.register(Estudante)
class EstudanteAdmin(admin.ModelAdmin):
    list_display = ("usuario", "cpf", "matricula")
    list_filter = ("usuario", "cpf", "matricula")
    search_fields = ("usuario", "cpf", "matricula")
    ordering = ("usuario", "cpf", "matricula")
    fieldsets = (("Informações do Estudante", {"fields": ("usuario", "cpf", "matricula")}),)


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ("usuario", "cnpj", "ativo", "dados_saque")
    list_filter = ("usuario", "cnpj", "ativo", "dados_saque")
    search_fields = ("usuario", "cnpj", "ativo", "dados_saque")
    ordering = ("usuario", "cnpj", "ativo", "dados_saque")
    fieldsets = (("Informações da Empresa", {"fields": ("usuario", "cnpj", "ativo", "dados_saque")}),)


@admin.register(Conta)
class ContaAdmin(admin.ModelAdmin):
    list_display = ("usuario", "saldo")
    list_filter = ("usuario", "saldo")
    search_fields = ("usuario", "saldo")
    ordering = ("usuario", "saldo")
    fieldsets = (("Informações da Conta", {"fields": ("usuario", "saldo")}),)


@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ("empresa", "nome", "valor")
    list_filter = ("empresa", "nome", "valor")
    search_fields = ("empresa", "nome", "valor")
    ordering = ("empresa", "nome", "valor")
    fieldsets = (("Informações do Produto", {"fields": ("empresa", "nome", "valor")}),)
