from decimal import Decimal
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from core.models import Conta, Estudante, Empresa, Transacao, Deposito, Venda, Saque
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


@override_settings(ABACATE_PAY_WEBHOOK_SECRET="", ABACATE_PAY_API_KEY="mock")
class DepositFlowTest(TestCase):
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
        # Account is created automatically via signals. Let's make sure it has 0.00
        self.conta = self.student_user.conta
        self.conta.saldo = 0.00
        self.conta.save()

    def test_solicitar_deposito_cria_transacao_e_deposito_pendentes(self):
        self.client.login(username="estudante@uffs.edu.br", password="password123")
        
        # Post a deposit request of 50.00
        response = self.client.post("/deposito/solicitar/", {"valor": "50.00"}, follow=False)
        
        # Should redirect to checkout
        self.assertEqual(response.status_code, 302)
        
        # Verify transaction and deposit creation
        transacao = Transacao.objects.filter(conta=self.conta, operacao="credito").first()
        self.assertIsNotNone(transacao)
        self.assertEqual(transacao.valor, 0.00) # Pending
        
        deposito = Deposito.objects.filter(transacao=transacao).first()
        self.assertIsNotNone(deposito)
        self.assertEqual(deposito.valor, Decimal("50.00"))
        self.assertEqual(deposito.situacao, "pendente")
        self.assertEqual(deposito.metodo_pagamento, "pix")
        
        self.assertEqual(response["Location"], f"/deposito/checkout/{transacao.id}/")

    def test_confirmar_deposito_simulacao_atualiza_saldo_e_transacao(self):
        self.client.login(username="estudante@uffs.edu.br", password="password123")
        
        # Create pending deposit manually
        transacao = Transacao.objects.create(
            operacao="credito",
            valor=0.00,
            conta=self.conta,
            descricao="Recarga PIX pendente"
        )
        deposito = Deposito.objects.create(
            transacao=transacao,
            valor=Decimal("75.50"),
            situacao="pendente",
            metodo_pagamento="pix",
            descricao="PIX-DEP-MOCK"
        )
        
        # Call simulation confirm POST
        response = self.client.post(f"/deposito/confirmar-simulacao/{transacao.id}/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/dashboard/estudante/")
        
        # Check database updates
        self.conta.refresh_from_db()
        self.assertEqual(self.conta.saldo, Decimal("75.50"))
        
        deposito.refresh_from_db()
        self.assertEqual(deposito.situacao, "confirmado")
        
        transacao.refresh_from_db()
        self.assertEqual(transacao.valor, Decimal("75.50"))

    def test_webhook_confirmacao_deposito_e_idempotencia(self):
        # Create pending deposit manually
        transacao = Transacao.objects.create(
            operacao="credito",
            valor=0.00,
            conta=self.conta,
            descricao="Recarga PIX pendente"
        )
        deposito = Deposito.objects.create(
            transacao=transacao,
            valor=Decimal("120.00"),
            situacao="pendente",
            metodo_pagamento="pix",
            descricao="PIX-DEP-MOCK"
        )
        
        # Call webhook POST
        import json
        payload = {"deposito_id": deposito.id, "valor": "120.00"}
        response = self.client.post(
            "/api/pagamentos/confirmar/",
            data=json.dumps(payload),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        
        self.conta.refresh_from_db()
        self.assertEqual(self.conta.saldo, Decimal("120.00"))
        
        # Test Idempotency: call webhook again with same payload
        response2 = self.client.post(
            "/api/pagamentos/confirmar/",
            data=json.dumps(payload),
            content_type="application/json"
        )
        # Should return 400 or handle gracefully
        self.assertEqual(response2.status_code, 400)
        
        # Balance should still be 120.00 (not duplicated to 240.00!)
        self.conta.refresh_from_db()
        self.assertEqual(self.conta.saldo, Decimal("120.00"))

    def test_abacatepay_gateway_gera_checkout_no_ambiente_de_testes(self):
        from core.services.payment import AbacatePayGateway
        # Create pending deposit manually
        transacao = Transacao.objects.create(
            operacao="credito",
            valor=0.00,
            conta=self.conta,
            descricao="Recarga PIX pendente"
        )
        deposito = Deposito.objects.create(
            transacao=transacao,
            valor=Decimal("50.00"),
            situacao="pendente",
            metodo_pagamento="pix",
            descricao="PIX-DEP-MOCK"
        )
        
        gateway = AbacatePayGateway()
        payment_data = gateway.gerar_pix_deposito(Decimal("50.00"), transacao.id)
        
        self.assertIn("payment_url", payment_data)
        self.assertTrue(payment_data["payment_url"].startswith("https://pay.abacatepay.com/bill-"))
        
        deposito.refresh_from_db()
        self.assertIsNotNone(deposito.abacatepay_billing_id)
        self.assertEqual(deposito.abacatepay_checkout_url, payment_data["payment_url"])

    def test_webhook_abacatepay_confirmacao_com_sucesso(self):
        # Create pending deposit manually
        transacao = Transacao.objects.create(
            operacao="credito",
            valor=0.00,
            conta=self.conta,
            descricao="Recarga PIX pendente"
        )
        deposito = Deposito.objects.create(
            transacao=transacao,
            valor=Decimal("60.00"),
            situacao="pendente",
            metodo_pagamento="pix",
            descricao="PIX-DEP-MOCK",
            abacatepay_billing_id="bill_abc123",
            abacatepay_checkout_url="https://pay.abacatepay.com/bill-bill_abc123"
        )
        
        # Simulated Abacate Pay payload
        import json
        payload = {
            "id": "log_webhook_123",
            "event": "billing.paid",
            "apiVersion": 2,
            "devMode": True,
            "data": {
                "id": "bill_abc123",
                "status": "PAID",
                "amount": 6000 # em centavos
            }
        }
        
        response = self.client.post(
            "/api/pagamentos/confirmar/",
            data=json.dumps(payload),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        
        self.conta.refresh_from_db()
        self.assertEqual(self.conta.saldo, Decimal("60.00"))
        
        deposito.refresh_from_db()
        self.assertEqual(deposito.situacao, "confirmado")

    def test_webhook_abacatepay_assinatura_invalida(self):
        # Create pending deposit manually
        transacao = Transacao.objects.create(
            operacao="credito",
            valor=0.00,
            conta=self.conta,
            descricao="Recarga PIX pendente"
        )
        deposito = Deposito.objects.create(
            transacao=transacao,
            valor=Decimal("70.00"),
            situacao="pendente",
            metodo_pagamento="pix",
            descricao="PIX-DEP-MOCK",
            abacatepay_billing_id="bill_xyz789",
            abacatepay_checkout_url="https://pay.abacatepay.com/bill-bill_xyz789"
        )
        
        # Configura segredo do webhook
        from django.test import override_settings
        import json
        payload = {
            "id": "log_webhook_789",
            "event": "billing.paid",
            "apiVersion": 2,
            "data": {
                "id": "bill_xyz789",
                "status": "PAID",
                "amount": 7000
            }
        }
        
        with override_settings(ABACATE_PAY_WEBHOOK_SECRET="super-secret-key"):
            # Sem cabeçalho de assinatura - deve falhar
            response = self.client.post(
                "/api/pagamentos/confirmar/",
                data=json.dumps(payload),
                content_type="application/json"
            )
            self.assertEqual(response.status_code, 400)
            
            # Com assinatura inválida - deve falhar
            response_invalid = self.client.post(
                "/api/pagamentos/confirmar/",
                data=json.dumps(payload),
                content_type="application/json",
                HTTP_X_WEBHOOK_SIGNATURE="invalid_signature"
            )
            self.assertEqual(response_invalid.status_code, 400)
            
            # Com assinatura válida - deve ter sucesso
            import hmac
            import hashlib
            raw_body = json.dumps(payload).encode("utf-8")
            valid_sig = hmac.new(b"super-secret-key", raw_body, hashlib.sha256).hexdigest()
            
            response_valid = self.client.post(
                "/api/pagamentos/confirmar/",
                data=raw_body,
                content_type="application/json",
                HTTP_X_WEBHOOK_SIGNATURE=valid_sig
            )
            self.assertEqual(response_valid.status_code, 200)
            
            self.conta.refresh_from_db()
            self.assertEqual(self.conta.saldo, Decimal("70.00"))


class VendaFlowTest(TestCase):
    def setUp(self):
        # Create student
        self.student_user = Usuario.objects.create_user(
            email="estudante@uffs.edu.br",
            nome="Estudante Teste",
            tipo="estudante",
            password="password123"
        )
        self.estudante = Estudante.objects.create(
            usuario=self.student_user,
            cpf="12345678901",
            matricula="2211100006"
        )
        self.conta_estudante = self.student_user.conta
        self.conta_estudante.saldo = Decimal("50.00")
        self.conta_estudante.save()

        # Create company
        self.company_user = Usuario.objects.create_user(
            email="empresa@uffs.edu.br",
            nome="RU UFFS",
            tipo="empresa",
            password="password123"
        )
        self.empresa = Empresa.objects.create(
            usuario=self.company_user,
            cnpj="12345678000199"
        )
        self.conta_empresa = self.company_user.conta
        self.conta_empresa.saldo = Decimal("10.00")
        self.conta_empresa.save()

        # Create product belonging to company
        from core.models import Produto
        self.produto = Produto.objects.create(
            empresa=self.empresa,
            nome="Almoço RU",
            valor=Decimal("2.50")
        )

        # Create another product belonging to another company
        self.another_company = Usuario.objects.create_user(
            email="outra@empresa.com",
            nome="Outra Cantina",
            tipo="empresa",
            password="password123"
        )
        self.other_empresa = Empresa.objects.create(
            usuario=self.another_company,
            cnpj="98765432100019"
        )
        self.other_produto = Produto.objects.create(
            empresa=self.other_empresa,
            nome="Suco",
            valor=Decimal("5.00")
        )

    def test_registrar_venda_sucesso(self):
        self.client.login(username="empresa@uffs.edu.br", password="password123")
        
        payload = {
            "estudante_uuid": str(self.student_user.uuid),
            "produto_id": self.produto.id
        }
        response = self.client.post("/api/vender/", payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "sucesso")
        
        # Verify balances
        self.conta_estudante.refresh_from_db()
        self.conta_empresa.refresh_from_db()
        self.assertEqual(self.conta_estudante.saldo, Decimal("47.50"))
        self.assertEqual(self.conta_empresa.saldo, Decimal("12.50"))
        
        # Verify Venda and Transacoes
        venda_exists = Venda.objects.filter(produto=self.produto, estudante=self.estudante).exists()
        self.assertTrue(venda_exists)
        
        # Check transaction logs
        self.assertEqual(Transacao.objects.filter(conta=self.conta_estudante, operacao="debito").count(), 1)
        self.assertEqual(Transacao.objects.filter(conta=self.conta_empresa, operacao="credito").count(), 1)

    def test_registrar_venda_saldo_insuficiente(self):
        # Set student balance to 0.00
        self.conta_estudante.saldo = Decimal("0.00")
        self.conta_estudante.save()
        
        self.client.login(username="empresa@uffs.edu.br", password="password123")
        
        payload = {
            "estudante_uuid": str(self.student_user.uuid),
            "produto_id": self.produto.id
        }
        response = self.client.post("/api/vender/", payload)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["status"], "erro")
        
        # Verify balances unchanged
        self.conta_estudante.refresh_from_db()
        self.conta_empresa.refresh_from_db()
        self.assertEqual(self.conta_estudante.saldo, Decimal("0.00"))
        self.assertEqual(self.conta_empresa.saldo, Decimal("10.00"))

    def test_registrar_venda_produto_de_outro_estabelecimento_recusada(self):
        self.client.login(username="empresa@uffs.edu.br", password="password123")
        
        # Try to sell a product belonging to other_empresa
        payload = {
            "estudante_uuid": str(self.student_user.uuid),
            "produto_id": self.other_produto.id
        }
        response = self.client.post("/api/vender/", payload)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["status"], "erro")
        
        # Balances should be unchanged
        self.conta_estudante.refresh_from_db()
        self.conta_empresa.refresh_from_db()
        self.assertEqual(self.conta_estudante.saldo, Decimal("50.00"))
        self.assertEqual(self.conta_empresa.saldo, Decimal("10.00"))


class SaqueFlowTest(TestCase):
    def setUp(self):
        # Create company user
        self.company_user = Usuario.objects.create_user(
            email="empresa@uffs.edu.br",
            nome="RU UFFS",
            tipo="empresa",
            password="password123"
        )
        self.empresa = Empresa.objects.create(
            usuario=self.company_user,
            cnpj="12345678000199",
            dados_saque="chavepix@uffs.br"
        )
        self.conta_empresa = self.company_user.conta
        self.conta_empresa.saldo = Decimal("500.00")
        self.conta_empresa.save()

        # Create admin user
        self.admin_user = Usuario.objects.create_user(
            email="admin@uffs.edu.br",
            nome="Admin Master",
            tipo="adm",
            password="adminpassword"
        )

    def test_solicitar_saque_sucesso(self):
        self.client.login(username="empresa@uffs.edu.br", password="password123")
        
        payload = {
            "valor": "150.00",
            "chave_pix": "chavepix@uffs.br"
        }
        response = self.client.post("/saque/solicitar/", payload, follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/dashboard/empresa/")
        
        # Check database updates: balance deducted immediately
        self.conta_empresa.refresh_from_db()
        self.assertEqual(self.conta_empresa.saldo, Decimal("350.00"))
        
        # Verify pending withdraw record
        transacao = Transacao.objects.filter(conta=self.conta_empresa, operacao="debito").first()
        self.assertIsNotNone(transacao)
        self.assertEqual(transacao.valor, Decimal("150.00"))
        
        saque = Saque.objects.filter(transacao=transacao).first()
        self.assertIsNotNone(saque)
        self.assertEqual(saque.situacao, "pendente")
        self.assertEqual(saque.descricao, "chavepix@uffs.br")

    def test_solicitar_saque_saldo_insuficiente(self):
        self.client.login(username="empresa@uffs.edu.br", password="password123")
        
        payload = {
            "valor": "600.00",
            "chave_pix": "chavepix@uffs.br"
        }
        response = self.client.post("/saque/solicitar/", payload, follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/dashboard/empresa/")
        
        # Check database updates: balance unchanged
        self.conta_empresa.refresh_from_db()
        self.assertEqual(self.conta_empresa.saldo, Decimal("500.00"))
        self.assertEqual(Saque.objects.count(), 0)

    def test_aprovar_saque_sucesso(self):
        # Setup pending saque
        transacao = Transacao.objects.create(
            operacao="debito",
            valor=Decimal("100.00"),
            conta=self.conta_empresa,
            descricao="Saque solicitado para chave Pix: chavepix@uffs.br"
        )
        saque = Saque.objects.create(
            transacao=transacao,
            situacao="pendente",
            metodo_pagamento="pix",
            descricao="chavepix@uffs.br"
        )
        
        # Deduct balance as if requested
        self.conta_empresa.saldo = Decimal("400.00")
        self.conta_empresa.save()
        
        # Admin log in and approve
        self.client.login(username="admin@uffs.edu.br", password="adminpassword")
        
        response = self.client.post(f"/saque/aprovar/{saque.id}/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/dashboard/admin/")
        
        # Check database: status changed to aprovado, admin recorded, balance remains 400.00
        saque.refresh_from_db()
        self.assertEqual(saque.situacao, "aprovado")
        self.assertEqual(saque.adm_responsavel, self.admin_user)
        
        self.conta_empresa.refresh_from_db()
        self.assertEqual(self.conta_empresa.saldo, Decimal("400.00"))

    def test_recusar_saque_sucesso_com_estorno(self):
        # Setup pending saque
        transacao = Transacao.objects.create(
            operacao="debito",
            valor=Decimal("100.00"),
            conta=self.conta_empresa,
            descricao="Saque solicitado para chave Pix: chavepix@uffs.br"
        )
        saque = Saque.objects.create(
            transacao=transacao,
            situacao="pendente",
            metodo_pagamento="pix",
            descricao="chavepix@uffs.br"
        )
        
        # Deduct balance as if requested
        self.conta_empresa.saldo = Decimal("400.00")
        self.conta_empresa.save()
        
        # Admin log in and reject
        self.client.login(username="admin@uffs.edu.br", password="adminpassword")
        
        response = self.client.post(f"/saque/recusar/{saque.id}/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/dashboard/admin/")
        
        # Check database: status changed to recusado, admin recorded
        saque.refresh_from_db()
        self.assertEqual(saque.situacao, "recusado")
        self.assertEqual(saque.adm_responsavel, self.admin_user)
        
        # Balance restored to 500.00
        self.conta_empresa.refresh_from_db()
        self.assertEqual(self.conta_empresa.saldo, Decimal("500.00"))
        
        # Compensating credit transaction created
        estorno_trans = Transacao.objects.filter(conta=self.conta_empresa, operacao="credito").first()
        self.assertIsNotNone(estorno_trans)
        self.assertEqual(estorno_trans.valor, Decimal("100.00"))


class ProdutoFlowTest(TestCase):
    def setUp(self):
        # Create company
        self.company_user = Usuario.objects.create_user(
            email="empresa@uffs.edu.br",
            nome="RU UFFS",
            tipo="empresa",
            password="password123"
        )
        self.empresa = Empresa.objects.create(
            usuario=self.company_user,
            cnpj="12345678000199"
        )
        
        # Create student
        self.student_user = Usuario.objects.create_user(
            email="estudante@uffs.edu.br",
            nome="Estudante Teste",
            tipo="estudante",
            password="password123"
        )

    def test_criar_produto_sucesso(self):
        self.client.login(username="empresa@uffs.edu.br", password="password123")
        
        payload = {
            "nome": "Cafezinho",
            "valor": "1.50"
        }
        from core.models import Produto
        response = self.client.post("/produto/criar/", payload, follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/dashboard/empresa/")
        
        # Verify product created
        produto = Produto.objects.filter(empresa=self.empresa, nome="Cafezinho").first()
        self.assertIsNotNone(produto)
        self.assertEqual(produto.valor, Decimal("1.50"))

    def test_criar_produto_valor_invalido(self):
        self.client.login(username="empresa@uffs.edu.br", password="password123")
        
        from core.models import Produto
        # Test negative value
        payload = {
            "nome": "Suco Estranho",
            "valor": "-1.50"
        }
        response = self.client.post("/produto/criar/", payload, follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Produto.objects.count(), 0)

    def test_criar_produto_restrito_a_empresa(self):
        # Student logs in
        self.client.login(username="estudante@uffs.edu.br", password="password123")
        
        payload = {
            "nome": "Tentativa Invasao",
            "valor": "10.00"
        }
        from core.models import Produto
        response = self.client.post("/produto/criar/", payload, follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/")
        self.assertEqual(Produto.objects.count(), 0)
