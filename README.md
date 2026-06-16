# FastPass

Projeto FastPass para venda de tickets ou lanches dentro do campus da universidade

## Tecnologias Utilizadas

- Django
- Python

## Como rodar

```bash
# Virtualenv
uv venv
uv sync

# Banco de dados
uv run manage.py migrate

# Criar superusuário (opcional)
uv run manage.py createsuperuser

# Rodar servidor
uv run manage.py runserver
```
