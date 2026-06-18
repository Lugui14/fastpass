from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from .models import Estudante, Empresa

Usuario = get_user_model()

class RegisterForm(forms.ModelForm):
    TIPO_CHOICES = [
        ("estudante", "Estudante"),
        ("empresa", "Empresa"),
    ]

    # Common fields
    password = forms.CharField(label="Senha", widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Digite sua senha"}), min_length=6)
    confirm_password = forms.CharField(label="Confirme a Senha", widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Confirme sua senha"}))
    tipo = forms.ChoiceField(label="Tipo de Conta", choices=TIPO_CHOICES, widget=forms.Select(attrs={"class": "form-control"}))
    
    # Estudante fields
    cpf = forms.CharField(label="CPF", required=False, widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "CPF (apenas números)"}), max_length=12)
    matricula = forms.CharField(label="Matrícula", required=False, widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Matrícula"}), max_length=15)
    data_nascimento = forms.DateField(label="Data de Nascimento", required=False, widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}))
    
    # Empresa fields
    cnpj = forms.CharField(label="CNPJ", required=False, widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "CNPJ (apenas números)"}), max_length=14)
    dados_saque = forms.CharField(label="Dados para Saque (Pix, etc.)", required=False, widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Sua chave Pix"}))

    class Meta:
        model = Usuario
        fields = ["nome", "email", "tipo"]
        widgets = {
            "nome": forms.TextInput(attrs={"class": "form-control", "placeholder": "Nome completo ou Razão Social"}),
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "E-mail de acesso"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if Usuario.objects.filter(email=email).exists():
            raise ValidationError("Este e-mail já está cadastrado.")
        return email

    def clean_tipo(self):
        tipo = self.cleaned_data.get("tipo")
        if tipo not in ["estudante", "empresa"]:
            raise ValidationError("Tipo de conta inválido. Você não pode registrar um usuário administrador.")
        return tipo

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")
        tipo = cleaned_data.get("tipo")

        if password and confirm_password and password != confirm_password:
            self.add_error("confirm_password", "As senhas não coincidem.")

        # Conditional validation based on tipo
        if tipo == "estudante":
            cpf = cleaned_data.get("cpf")
            matricula = cleaned_data.get("matricula")
            if not cpf:
                self.add_error("cpf", "O CPF é obrigatório para estudantes.")
            if not matricula:
                self.add_error("matricula", "A matrícula é obrigatória para estudantes.")
        elif tipo == "empresa":
            cnpj = cleaned_data.get("cnpj")
            if not cnpj:
                self.add_error("cnpj", "O CNPJ é obrigatório para empresas.")
        
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        
        if commit:
            user.save()
            tipo = self.cleaned_data.get("tipo")
            if tipo == "estudante":
                Estudante.objects.create(
                    usuario=user,
                    cpf=self.cleaned_data.get("cpf"),
                    matricula=self.cleaned_data.get("matricula"),
                    data_nascimento=self.cleaned_data.get("data_nascimento"),
                )
            elif tipo == "empresa":
                Empresa.objects.create(
                    usuario=user,
                    cnpj=self.cleaned_data.get("cnpj"),
                    dados_saque=self.cleaned_data.get("dados_saque"),
                    ativo=1,
                )
        return user


class EditarPerfilForm(forms.ModelForm):
    # Estudante fields
    cpf = forms.CharField(label="CPF", required=False, widget=forms.TextInput(attrs={"class": "form-control form-control-uffs", "readonly": "readonly"}))
    matricula = forms.CharField(label="Matrícula", required=False, widget=forms.TextInput(attrs={"class": "form-control form-control-uffs", "readonly": "readonly"}))
    data_nascimento = forms.DateField(label="Data de Nascimento", required=False, widget=forms.DateInput(attrs={"class": "form-control form-control-uffs", "type": "date"}))
    
    # Empresa fields
    cnpj = forms.CharField(label="CNPJ", required=False, widget=forms.TextInput(attrs={"class": "form-control form-control-uffs", "readonly": "readonly"}))
    dados_saque = forms.CharField(label="Dados para Saque (Pix, etc.)", required=False, widget=forms.TextInput(attrs={"class": "form-control form-control-uffs", "placeholder": "Sua chave Pix"}))

    class Meta:
        model = Usuario
        fields = ["nome", "email"]
        widgets = {
            "nome": forms.TextInput(attrs={"class": "form-control form-control-uffs", "placeholder": "Nome completo ou Razão Social"}),
            "email": forms.EmailInput(attrs={"class": "form-control form-control-uffs", "placeholder": "E-mail de acesso"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            tipo = self.instance.tipo
            if tipo == "estudante" and hasattr(self.instance, "estudante_perfil"):
                perfil = self.instance.estudante_perfil
                self.fields["cpf"].initial = perfil.cpf
                self.fields["matricula"].initial = perfil.matricula
                self.fields["data_nascimento"].initial = perfil.data_nascimento
                # Remove fields not applicable to estudantes
                self.fields.pop("cnpj", None)
                self.fields.pop("dados_saque", None)
            elif tipo == "empresa" and hasattr(self.instance, "empresa_perfil"):
                perfil = self.instance.empresa_perfil
                self.fields["cnpj"].initial = perfil.cnpj
                self.fields["dados_saque"].initial = perfil.dados_saque
                # Remove fields not applicable to empresas
                self.fields.pop("cpf", None)
                self.fields.pop("matricula", None)
                self.fields.pop("data_nascimento", None)
            else:
                # Admins / others
                self.fields.pop("cpf", None)
                self.fields.pop("matricula", None)
                self.fields.pop("data_nascimento", None)
                self.fields.pop("cnpj", None)
                self.fields.pop("dados_saque", None)

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if Usuario.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise ValidationError("Este e-mail já está sendo utilizado por outro usuário.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            tipo = user.tipo
            if tipo == "estudante" and hasattr(user, "estudante_perfil"):
                perfil = user.estudante_perfil
                perfil.data_nascimento = self.cleaned_data.get("data_nascimento")
                perfil.save()
            elif tipo == "empresa" and hasattr(user, "empresa_perfil"):
                perfil = user.empresa_perfil
                perfil.dados_saque = self.cleaned_data.get("dados_saque")
                perfil.save()
        return user
