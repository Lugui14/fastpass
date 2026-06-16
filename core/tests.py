from django.test import TestCase
from django.contrib.auth import get_user_model
from core.models import Conta, Estudante, Empresa
from core.forms import RegisterForm

Usuario = get_user_model()


class UsuarioSignalsAndModelsTest(TestCase):
    def test_criar_usuario_cria_conta_automaticamente(self):
        """
        Verifica se a criação de um usuário comum dispara o signal
        e cria uma conta associada com saldo zero.
        """
        user = Usuario.objects.create_user(
            email="test_estudante@uffs.edu.br",
            nome="Test Estudante",
            tipo="estudante",
            password="securepassword123"
        )
        # Verifica se o UUID foi gerado
        self.assertIsNotNone(user.uuid)
        
        # Verifica se a conta foi criada
        conta_exists = Conta.objects.filter(usuario=user).exists()
        self.assertTrue(conta_exists)
        
        conta = user.conta
        self.assertEqual(conta.saldo, 0.00)

    def test_criar_superuser_cria_conta_automaticamente(self):
        """
        Verifica se a criação de um superuser dispara o signal
        e cria uma conta com saldo zero.
        """
        admin = Usuario.objects.create_superuser(
            email="admin@uffs.edu.br",
            nome="Admin Master",
            password="adminpassword123"
        )
        self.assertEqual(admin.tipo, "adm")
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        
        # Conta deve existir
        self.assertTrue(Conta.objects.filter(usuario=admin).exists())
        self.assertEqual(admin.conta.saldo, 0.00)


class RegistroFormTest(TestCase):
    def test_registro_estudante_valido(self):
        form_data = {
            "nome": "Luiz Zanella",
            "email": "luiz@estudante.uffs.edu.br",
            "tipo": "estudante",
            "password": "mypassword123",
            "confirm_password": "mypassword123",
            "cpf": "12345678901",
            "matricula": "2211100006",
        }
        form = RegisterForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        
        # Verifica se perfil Estudante foi criado
        self.assertTrue(Estudante.objects.filter(usuario=user).exists())
        estudante = user.estudante_perfil
        self.assertEqual(estudante.cpf, "12345678901")
        self.assertEqual(estudante.matricula, "2211100006")
        
        # Conta do estudante criada automaticamente via signals
        self.assertTrue(Conta.objects.filter(usuario=user).exists())

    def test_registro_empresa_valido(self):
        form_data = {
            "nome": "RU Chapecó Ltda",
            "email": "ru.chapeco@empresa.com",
            "tipo": "empresa",
            "password": "companypassword",
            "confirm_password": "companypassword",
            "cnpj": "12345678000199",
            "dados_saque": "chavepix@empresa.com",
        }
        form = RegisterForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        
        # Verifica se perfil Empresa foi criado
        self.assertTrue(Empresa.objects.filter(usuario=user).exists())
        empresa = user.empresa_perfil
        self.assertEqual(empresa.cnpj, "12345678000199")
        self.assertEqual(empresa.dados_saque, "chavepix@empresa.com")
        self.assertEqual(empresa.ativo, 1)
        
        # Conta da empresa criada
        self.assertTrue(Conta.objects.filter(usuario=user).exists())

    def test_registro_estudante_invalido_sem_cpf_matricula(self):
        form_data = {
            "nome": "Luiz Invalido",
            "email": "invalido@estudante.uffs.edu.br",
            "tipo": "estudante",
            "password": "mypassword123",
            "confirm_password": "mypassword123",
            "cpf": "",
            "matricula": "",
        }
        form = RegisterForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("cpf", form.errors)
        self.assertIn("matricula", form.errors)


class DashboardViewsTest(TestCase):
    def setUp(self):
        # Create student
        self.student_user = Usuario.objects.create_user(
            email="estudante@uffs.edu.br",
            nome="Estudante Teste",
            tipo="estudante",
            password="password123"
        )
        Estudante.objects.create(
            usuario=self.student_user,
            cpf="12345678901",
            matricula="2211100006"
        )

        # Create company
        self.company_user = Usuario.objects.create_user(
            email="empresa@uffs.edu.br",
            nome="Empresa Teste",
            tipo="empresa",
            password="password123"
        )
        Empresa.objects.create(
            usuario=self.company_user,
            cnpj="12345678000199"
        )

    def test_home_view_redirects_to_login_if_not_authenticated(self):
        response = self.client.get("/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/login/?next=/")

    def test_home_view_redirects_to_student_dashboard_for_student(self):
        self.client.login(username="estudante@uffs.edu.br", password="password123")
        response = self.client.get("/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/dashboard/estudante/")

    def test_home_view_redirects_to_company_dashboard_for_company(self):
        self.client.login(username="empresa@uffs.edu.br", password="password123")
        response = self.client.get("/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/dashboard/empresa/")

    def test_student_dashboard_restricted_to_student(self):
        self.client.login(username="empresa@uffs.edu.br", password="password123")
        response = self.client.get("/dashboard/estudante/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/")
