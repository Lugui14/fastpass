# Detalhes Técnicos de Implementação - FastPass

Este documento descreve detalhadamente as escolhas de arquitetura e padrões de codificação adotados no projeto **FastPass**, com foco especial em **Class-Based Views (CBVs)**, **Django Signals** e a estrutura de **Testes Unitários**.

---

## 1. Class-Based Views (CBVs)

As Class-Based Views (CBVs) do Django foram utilizadas para estruturar as rotas de autenticação e os dashboards em [core/views.py](file:///home/luiz/src/fastpass/core/views.py). Elas promovem a reutilização de código e reduzem o esforço de codificação (boilerplate).

### Classes Utilizadas

1. **`CreateView`** (usada em `RegisterView`):
   - _Objetivo:_ Tratar a exibição e a submissão de formulários para criação de novos registros no banco de dados.
   - _Configuração:_ Associa-se a um template (`template_name`), um formulário (`form_class`) e uma URL de sucesso (`success_url`).
2. **`LoginView`** e **`LogoutView`** (usadas em `CustomLoginView` e `CustomLogoutView`):
   - _Objetivo:_ Abstrair toda a lógica padrão de autenticação do Django, gerenciamento de sessões de cookies e sanitização de entradas.
3. **`TemplateView`** (usada em `HomeView` e dashboards):
   - _Objetivo:_ Renderizar um template HTML estático ou enriquecido com um contexto dinâmico do banco de dados.

### Principais Funções Sobrescritas

#### A) `dispatch(self, request, *args, **kwargs)`

O método `dispatch` atua como o ponto de entrada da view. Ele recebe a requisição HTTP (GET, POST, etc.) e decide qual método correspondente da classe chamar.

- _Uso no FastPass:_ Sobrescrito para implementar **verificações de permissão e controle de acesso** antes que qualquer lógica de renderização seja processada.

```python
# Exemplo de controle de acesso na dashboard do estudante
def dispatch(self, request, *args, **kwargs):
    if request.user.tipo != "estudante":
        messages.error(request, "Acesso restrito a estudantes.")
        return redirect("home")
    return super().dispatch(request, *args, **kwargs)
```

#### B) `get_context_data(self, **kwargs)`

Esse método constrói e retorna o dicionário de contexto utilizado para renderizar o template HTML.

- _Uso no FastPass:_ Sobrescrito para **injetar dados dinâmicos do banco de dados** baseados no perfil do usuário logado.

```python
def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    user = self.request.user
    context["estudante"] = user.estudante_perfil
    context["conta"] = user.conta
    # Retorna o histórico recente do extrato
    context["transacoes"] = Transacao.objects.filter(conta=user.conta).order_by("-data_hora")[:10]
    return context
```

#### C) `form_valid(self, form)`

Chamado automaticamente quando um formulário submetido via POST é considerado válido de acordo com as validações declaradas.

- _Uso no FastPass:_ Sobrescrito em `RegisterView` para injetar uma mensagem temporária de feedback de sucesso no navegador do usuário.

```python
def form_valid(self, form):
    response = super().form_valid(form)
    messages.success(self.request, "Cadastro realizado com sucesso! Faça login para continuar.")
    return response
```

---

## 2. Django Signals

Os Signals permitem que partes desacopladas da aplicação sejam notificadas quando determinados eventos ocorrem no ciclo de vida de um modelo.

- _Arquivo de Definição:_ [core/signals.py](file:///home/luiz/src/fastpass/core/signals.py)
- _Evento Capturado:_ `post_save` do modelo `Usuario`.

### O Fluxo de Execução

Sempre que uma instância do modelo `Usuario` é salva (`save()`), o Django emite o sinal `post_save`. Nossa função receptora (`criar_conta_usuario`) intercepta esse sinal e cria automaticamente um registro correspondente na tabela `Conta` para o usuário recém-criado.

```python
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Usuario, Conta

@receiver(post_save, sender=Usuario)
def criar_conta_usuario(sender, instance, created, **kwargs):
    # O parâmetro 'created' é um booleano que indica se o registro foi inserido (True) ou atualizado (False)
    if created:
        Conta.objects.create(usuario=instance)
```

### Configuração do Ciclo de Vida do App

Para garantir que o Django carregue os signals na inicialização, o import do arquivo de signals deve ser feito explicitamente no método `ready()` da classe `AppConfig` em [core/apps.py](file:///home/luiz/src/fastpass/core/apps.py):

```python
from django.apps import AppConfig

class CoreConfig(AppConfig):
    name = 'core'

    def ready(self):
        import core.signals  # Garante o carregamento dos receptores
```

> [!IMPORTANT]
> Em versões antigas do Django (como a **2.2.5** utilizada neste projeto), colocar apenas `"core"` em `INSTALLED_APPS` no arquivo `settings.py` ignora a execução da classe `CoreConfig`. Por essa razão, configurou-se explicitamente o caminho `"core.apps.CoreConfig"` na lista de aplicativos.

---

## 3. Testes Unitários

O Django disponibiliza o módulo `django.test.TestCase` para testes de integração e testes unitários com isolamento automático de banco de dados. Os testes foram estruturados em [core/tests.py](../core/tests.py).

### Padrões e Práticas Adotadas

1. **Isolamento de Banco de Dados:** Cada execução de teste cria um banco de dados temporário e limpa todas as tabelas a cada método de teste para evitar poluição de dados.
2. **Método `setUp(self)`:** Usado para criar fixtures básicas (como usuários estudantes e empresas) que serão compartilhados pelos métodos de teste da mesma classe.
3. **Uso de `self.client`:** O Django providencia um cliente HTTP simulado para enviar requisições GET/POST.
4. **Parâmetro `follow=False`:** Usado nas asserções de redirecionamento. Ao desabilitar o redirecionamento automático, conseguimos testar diretamente o comportamento individual de cada rota (verificando o status `302` e o cabeçalho `Location`), em vez de testar a cadeia completa.

### Exemplos de Cenários de Testes

#### Teste de Signals (Modelos)

Garante que a lógica do banco de dados integrada com signals está funcionando:

```python
def test_criar_usuario_cria_conta_automaticamente(self):
    user = Usuario.objects.create_user(
        email="estudante@uffs.edu.br",
        nome="Estudante Teste",
        tipo="estudante",
        password="securepassword"
    )
    # Testa se o trigger do signal instanciou a Conta associada
    self.assertTrue(Conta.objects.filter(usuario=user).exists())
    self.assertEqual(user.conta.saldo, 0.00)
```

#### Teste de Validação Condicional (Forms)

Garante que as regras de negócio declaradas no formulário bloqueiem cadastros inválidos:

```python
def test_registro_estudante_invalido_sem_cpf_matricula(self):
    form_data = {
        "nome": "Estudante Sem Dados",
        "email": "semdados@estudante.uffs.edu.br",
        "tipo": "estudante",  # Tipo estudante exige cpf/matrícula
        "password": "mypassword123",
        "confirm_password": "mypassword123",
        "cpf": "",
        "matricula": "",
    }
    form = RegisterForm(data=form_data)
    self.assertFalse(form.is_valid())
    self.assertIn("cpf", form.errors)
```

#### Teste de Redirecionamento e Controle de Acesso (Views)

Garante que a lógica de sessões e o middleware de autenticação estejam barrando ou autorizando os usuários corretamente:

```python
def test_student_dashboard_restricted_to_student(self):
    # Simula autenticação de uma Empresa
    self.client.login(username="empresa@uffs.edu.br", password="password123")
    # Tenta acessar dashboard exclusiva de Estudantes
    response = self.client.get("/dashboard/estudante/", follow=False)
    # Valida que o acesso foi negado (redirecionamento de volta para home)
    self.assertEqual(response.status_code, 302)
    self.assertEqual(response["Location"], "/")
```

---

## 4. Integração com Abacate Pay (Gateway de Pagamentos)

Para processar depósitos via PIX em ambiente de homologação (devmode), integramos a API da **Abacate Pay** (versão **v1** para criação de cobranças e **v2** para recepção de webhooks).

### A) Mapeamento no Banco de Dados
A tabela de `Deposito` ([core/models.py](file:///home/luiz/src/fastpass/core/models.py)) foi estendida para associar cobranças do sistema com faturas do Abacate Pay:
*   `abacatepay_billing_id`: Identificador único da fatura retornado pela API da Abacate Pay (usado para localizar o depósito ao receber webhooks).
*   `abacatepay_checkout_url`: Link gerado pela Abacate Pay para o qual o estudante é redirecionado para pagar.

### B) Criação de Cobranças (`AbacatePayGateway`)
A classe `AbacatePayGateway` em [core/services/payment.py](file:///home/luiz/src/fastpass/core/services/payment.py) implementa a interface `PaymentGatewayInterface` e realiza chamadas para `POST https://api.abacatepay.com/v1/billing/create`.

*   **Identificação do Estudante:** Cada cobrança inclui os dados do estudante correspondente (`nome` e `email`) no objeto `customer`.
*   **Descrição de Destino:** O produto criado na fatura possui uma descrição explícita indicando a carteira destinatária do valor para auditoria e documentação no dashboard do Abacate Pay: `Destinado para carteira digital de: {nome} ({email})`.
*   **URLs Dinâmicas:** Os links de redirecionamento (`returnUrl` e `completionUrl`) são construídos de forma dinâmica utilizando a variável de ambiente `APP_URL` (com fallback padrão para `http://localhost:8000`), permitindo fácil portabilidade entre ambientes locais, de staging e produção.
*   **Isolamento de Testes e Dev Mode:** Caso a chave `ABACATE_PAY_API_KEY` não esteja configurada ou o sistema esteja rodando testes unitários, o gateway automaticamente desvia a chamada de rede e gera links e IDs mockados locais seguros, assegurando o funcionamento offline completo e hermético.

### C) Webhook de Confirmação e Segurança (`ConfirmarDepositoWebhookView`)
O endpoint `/api/pagamentos/confirmar/` escuta as notificações enviadas pela Abacate Pay.

1.  **Validação de Assinatura (HMAC-SHA256):**
    Caso a chave `ABACATE_PAY_WEBHOOK_SECRET` esteja configurada no `.env` da aplicação, o webhook obrigatoriamente valida a autenticidade da requisição calculando o HMAC-SHA256 do corpo da requisição bruta (*raw body*) com a chave secreta e comparando com o valor presente no cabeçalho `X-Webhook-Signature`.
2.  **Processamento de Eventos:**
    Somente eventos do tipo `billing.paid` que tenham `status` igual a `PAID` são processados. O saldo correspondente é incrementado de forma atômica no banco de dados e a transação é confirmada.
3.  **Retrocompatibilidade:**
    O webhook preserva retrocompatibilidade com o formato de simulação de desenvolvimento simplificado (enviando `deposito_id` e `valor` diretamente), garantindo a estabilidade de testes unitários legados.

