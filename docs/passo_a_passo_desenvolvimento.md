# FastPass - Passo a Passo do Desenvolvimento

Este guia descreve o plano de desenvolvimento detalhado, etapa por etapa, para implementar os casos de uso, requisitos e regras de negócio do sistema **FastPass**, tendo como base os modelos já existentes em [core/models.py](../core/models.py).

---

## Estrutura Atual do Banco de Dados

O sistema já possui a modelagem inicial em Django no app `core`:

- **`Usuario`**: Modelo de usuário customizado (Estudante, Empresa ou Administrador).
- **`Estudante`**: Perfil detalhado com CPF, Matrícula e Data de Nascimento.
- **`Empresa`** (Estabelecimento): Perfil com CNPJ, status ativo/inativo e dados bancários de saque.
- **`Conta`**: Armazena o saldo atual associado ao usuário.
- **`Produto`**: Representa os itens vendidos pelo Estabelecimento (ex: Entrada RU, Café, Almoço).
- **`Transacao`**: Registro de entrada (crédito) e saída (débito) de saldo.
- **`Venda`**: Relaciona a compra de um produto por um estudante à transação financeira correspondente.
- **`Saque`**: Controle das solicitações de saque realizadas pelas empresas e aprovadas pelos administradores.
- **`Deposito`**: Registro de recarga de créditos pelo estudante.

---

## Cronograma de Desenvolvimento (Passo a Passo)

### Passo 1: Ajustes no Modelo e Sistema de Autenticação (RF01, RF02, RN01, RN02)

Para cumprir a regra de identificação por UUID (**RN04**), notamos que o modelo `Usuario` atual não possui um campo `uuid`. Devemos adicioná-lo.

#### Ação 1.1: Adicionar UUID ao Usuário

Modificar [core/models.py](../core/models.py) para incluir o campo UUID:

```python
import uuid
from django.db import models

class Usuario(AbstractUser):
    # ... campos existentes ...
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
```

_Executar as migrações:_

```bash
python manage.py makemigrations core
python manage.py migrate
```

#### Ação 1.2: Criação Automática de Conta (Signals)

Garantir que sempre que um novo `Usuario` for criado, uma `Conta` com saldo `0.00` seja criada automaticamente para ele.
Criar ou editar o arquivo `core/signals.py`:

```python
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Usuario, Conta

@receiver(post_save, sender=Usuario)
def criar_conta_usuario(sender, instance, created, **kwargs):
    if created:
        Conta.objects.create(usuario=instance)
```

_Importar os signals em `core/apps.py`:_

```python
from django.apps import AppConfig

class CoreConfig(AppConfig):
    name = 'core'

    def ready(self):
        import core.signals
```

#### Ação 1.3: Fluxo de Registro e Login (RN01)

- Desenvolver o formulário de cadastro (`RegisterForm`), permitindo escolher entre **Estudante** (exigindo CPF e Matrícula) e **Empresa** (exigindo CNPJ e dados de saque).
- Utilizar views baseadas em classe (`CreateView`, `LoginView`, `LogoutView`) do Django.
- **Segurança:** Utilizar `pbkdf2_sha256` padrão do Django para a criptografia segura das senhas (**RNF01**).

---

### Passo 2: Dashboards e Geração de QR Code (RF03, RF04, RN08, RN09)

As telas devem seguir o modelo **Mobile First** (**RNF04**). Utilizar CSS responsivo e frameworks leves se necessário (ou Vanilla CSS com Flexbox/Grid).

#### Ação 2.1: Implementação do Design Global

- Criar padrão de design (cores, fontes, etc.) (use bootstrap, mas estilizado de acordo com as cores da UFFS) que será usada em todas as telas(templates). Essa base pode estar em uma pasta separada, na qual poderá ser utilizada em todos os módulos.
- Criar páginas de erro padrões (404, 500, etc.)
- Dentro desse termo, criar diretorio para arquivos JS, CSS e arquivos fixos (imagens, documentos, etc.) e configura-los para fácil acesso nos módulos.

#### Ação 2.2: Implementação da Dashboard Comum

- Criar a view da Dashboard (`views.py`) que redireciona de acordo com o `tipo` do usuário logado:
  - Se `estudante` -> Renderiza `dashboard_estudante.html`
  - Se `empresa` -> Renderiza `dashboard_empresa.html`
  - Se `adm` -> Renderiza `dashboard_admin.html`

#### Ação 2.3: Renderização do QR Code do Estudante (RN04)

Para evitar processamento excessivo no servidor, o QR Code deve ser gerado diretamente no navegador do estudante via JavaScript (usando a biblioteca `qrcode.js` ou similar).
No arquivo HTML `dashboard_estudante.html`:

```html
<div id="qrcode-container"></div>
<script src="https://cdn.jsdelivr.net/npm/qrcodejs@1.0.0/qrcode.min.js"></script>
<script>
  // O QR code conterá o UUID seguro do usuário logado
  var userUuid = "{{ request.user.uuid }}";
  new QRCode(document.getElementById("qrcode-container"), {
    text: userUuid,
    width: 256,
    height: 256,
    colorDark: "#000000",
    colorLight: "#ffffff",
  });
</script>
```

#### Ação 2.4: Cadastro de Produtos pelas Empresas (RF11)

- Na dashboard da Empresa, haverá um botão para abrir o modal de cadastro de produtos.
- O formulário enviará os dados para a view de criação de produto (`CriarProdutoView`).
- O backend valida se o usuário autenticado é do tipo `empresa`, extrai os campos `nome` e `valor` e cria a instância no banco vinculando ao perfil da `Empresa`.

---

### Passo 3: Fluxo de Depósito e Recarga via PIX (RF05, RN05, RN07, RNF01)

#### Ação 3.1: Solicitação de Depósito

- Na dashboard do estudante, haverá um formulário para inserir o valor do depósito.
- Ao submeter, o backend cria um registro de `Transacao` do tipo `credito`, associada a um `Deposito` com status `pendente`.
- Integração com a API do gateway (Stripe ou Abacate Pay): o backend envia a requisição e retorna o código PIX Copia e Cola / QR Code dinâmico do banco central.

#### Ação 3.2: Confirmação e Idempotência (Webhook)

- Configurar um endpoint de Webhook (ex: `/api/pagamentos/confirmar/`) para receber a notificação de pagamento do gateway.
- **Evitar Condições de Corrida (Race Conditions):** Usar transações atômicas e travar a conta para atualização.

```python
from django.db import transaction

@transaction.atomic
def confirmar_deposito(deposito_id, valor_pago):
    deposito = Deposito.objects.select_for_update().get(id=deposito_id)
    if deposito.situacao == "pendente":
        deposito.situacao = "confirmado"
        deposito.save()

        # Atualizar saldo da conta
        conta = Conta.objects.select_for_update().get(usuario=deposito.transacao.conta.usuario)
        conta.saldo += valor_pago
        conta.save()

        # Atualizar a transação correspondente
        transacao = deposito.transacao
        transacao.valor = valor_pago
        transacao.save()
```

---

### Passo 4: Validação de Entrada e Débito no RU (RF04, RF05, RF07, RN05, RN07)

Este fluxo representa a compra da entrada do RU pelo estudante ao passar pela catraca / guichê da Empresa.

#### Ação 4.1: Interface da Empresa (Scanner de Câmera)

- A pessoa logada como empresa deve poder cadastrar novos produtos vinculados àquela empresa.

- O funcionário do RU acessa a dashboard da Empresa e clica em **"Escanear Entrada"**.
- A tela ativa a câmera traseira do dispositivo usando a biblioteca `html5-qrcode` para ler o QR Code do estudante.
- Ao ler o QR Code, extrai o UUID do estudante e realiza uma chamada POST assíncrona (via `fetch` JS) para `/api/vender/`.

#### Ação 4.2: Lógica de Débito no Backend

No arquivo `core/views.py`, implementar a view de venda:

```python
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db import transaction
from .models import Usuario, Produto, Transacao, Venda

@require_POST
@transaction.atomic
def registrar_venda(request):
    estudante_uuid = request.POST.get("estudante_uuid")
    produto_id = request.POST.get("produto_id") # ex: Produto "Entrada RU"

    try:
        estudante_usuario = Usuario.objects.get(uuid=estudante_uuid, tipo="estudante")
        estudante = estudante_usuario.estudante_perfil
        produto = Produto.objects.get(id=produto_id)

        conta_estudante = estudante_usuario.conta

        if conta_estudante.saldo < produto.valor:
            return JsonResponse({"status": "erro", "mensagem": "Saldo insuficiente"}, status=400)

        # 1. Deduzir saldo do estudante
        conta_estudante.saldo -= produto.valor
        conta_estudante.save()

        # 2. Creditar saldo da empresa (RU)
        conta_empresa = produto.empresa.usuario.conta
        conta_empresa.saldo += produto.valor
        conta_empresa.save()

        # 3. Registrar Transações no Extrato (Débito para o Estudante)
        transacao_debito = Transacao.objects.create(
            operacao="debito",
            valor=produto.valor,
            conta=conta_estudante,
            descricao=f"Compra de {produto.nome}"
        )

        # (Crédito para o RU)
        transacao_credito = Transacao.objects.create(
            operacao="credito",
            valor=produto.valor,
            conta=conta_empresa,
            descricao=f"Venda de {produto.nome} para {estudante.nome()}"
        )

        # 4. Registrar a Venda
        Venda.objects.create(
            produto=produto,
            estudante=estudante,
            valor_unidade=produto.valor,
            quantidade=1,
            valor_total=produto.valor,
            transacao=transacao_debito
        )

        return JsonResponse({"status": "sucesso", "mensagem": "Acesso Autorizado!"})

    except Usuario.DoesNotExist:
        return JsonResponse({"status": "erro", "mensagem": "Estudante não encontrado"}, status=404)
    except Produto.DoesNotExist:
        return JsonResponse({"status": "erro", "mensagem": "Produto inválido"}, status=404)
```

---

### Passo 5: Fluxo de Saques e Moderação Administrativa (RF06, RF10, RN06, RN10)

#### Ação 5.1: Solicitação de Saque

- Na dashboard da Empresa, exibir o saldo acumulado e um botão **"Solicitar Saque"**.
- Ao clicar, abre-se um modal solicitando o valor do saque e a chave Pix de recebimento.
- O backend valida se a empresa possui saldo livre igual ou superior ao solicitado:
  - Se sim, deduz o saldo da conta da Empresa imediatamente (para reter o valor) e cria um registro na tabela `Transacao` (débito) associado a um `Saque` com status `pendente`.

#### Ação 5.2: Tela de Moderação Administrativa (Admin)

- Criar uma view restrita a administradores (`tipo='adm'`) ou estender o Django Admin para exibir uma tabela contendo todos os `Saques` com `situacao='pendente'`.
- Exibir os dados PIX da Empresa e o valor.
- Fornecer ações rápidas: **"Marcar como Pago (Aprovar)"** ou **"Rejeitar"**.
  - **Aprovar:** Altera `situacao` do saque para `aprovado` e registra o administrador responsável. O pagamento Pix é feito de forma manual pelo administrador (ou por webhook automatizado se houver gateway de payout).
  - **Rejeitar:** Altera `situacao` para `recusado`. O backend deve devolver o valor retido estornando o saldo para a `Conta` da Empresa e registrando uma transação de compensação.

---

### Passo 6: Qualidade, Otimização e Deploy (RNF02, RNF03, RNF05)

#### Ação 6.1: Testes Unitários de Concorrência

Em [core/tests.py](../core/tests.py), criar testes simulando acessos paralelos e transações concorrentes para garantir a integridade dos saldos utilizando a biblioteca `threading` ou ferramentas de teste de carga.

#### Ação 6.2: Otimização de Queries

Garantir que as listagens de extrato e dashboards não realizem dezenas de consultas ao banco de dados (problema do N+1). Utilizar `select_related` ou `prefetch_related`:

```python
# Correto
transacoes = Transacao.objects.select_related('conta').filter(conta__usuario=request.user)
```

#### Ação 6.3: Deploy em Produção

- Configurar variáveis de ambiente de produção no arquivo `.env` (ocultando credenciais do banco e chaves de APIs).
- Configurar o arquivo `wsgi.py` e bibliotecas de staticfiles (ex: `whitenoise`) para rodar em servidores como Render ou Heroku usando contêineres Docker ou buildpacks Python.
