from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from .models import Estudante, Empresa

Usuario = get_user_model()

class RegisterForm(forms.ModelForm):
    # Common fields
    password = forms.CharField(label="Senha", widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Digite sua senha"}), min_length=6)
    confirm_password = forms.CharField(label="Confirme a Senha", widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Confirme sua senha"}))
    
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
            "tipo": forms.Select(attrs={"class": "form-control"}),
        }

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if Usuario.objects.filter(email=email).exists():
            raise ValidationError("Este e-mail já está cadastrado.")
        return email

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
