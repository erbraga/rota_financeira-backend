"""Banco de dados dos testes de integração: nome, trava de segurança e criação.

Nunca toca no banco de desenvolvimento: só se aceita um banco cujo nome termine em
`_test`. Sem `TEST_DATABASE_URL`, usa `bd_test` na mesma instância do `DATABASE_URL`
(mesmo host, porta, usuário e senha; a senha existe só no `.env`).
"""
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg import sql
from sqlalchemy.engine import make_url

SUFIXO_OBRIGATORIO = "_test"
NOME_PADRAO = "bd_test"
BANCO_DE_MANUTENCAO = "postgres"
TIMEOUT_CONEXAO_SEGUNDOS = 3

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


class BancoDeTesteInvalido(Exception):
    pass


def validar_nome_banco_de_teste(url):
    """Devolve a URL (como `URL` do SQLAlchemy) ou recusa nome que não termine em `_test`."""
    url = make_url(url)
    nome = url.database or ""
    if not nome.endswith(SUFIXO_OBRIGATORIO) or nome == SUFIXO_OBRIGATORIO:
        raise BancoDeTesteInvalido(
            f"Recusado: o banco de teste precisa ter nome terminado em "
            f"'{SUFIXO_OBRIGATORIO}' (recebido: {nome!r}). Os testes apagam todos os dados."
        )
    return url


def url_do_banco_de_teste(ambiente=None):
    """`TEST_DATABASE_URL` se existir; senão `bd_test` na instância de `DATABASE_URL`."""
    ambiente = os.environ if ambiente is None else ambiente
    explicita = ambiente.get("TEST_DATABASE_URL", "").strip()
    if explicita:
        return validar_nome_banco_de_teste(explicita)
    base = ambiente.get("DATABASE_URL", "").strip()
    if not base:
        raise BancoDeTesteInvalido(
            "Defina DATABASE_URL (ou TEST_DATABASE_URL) no .env para rodar os testes de integração."
        )
    return validar_nome_banco_de_teste(make_url(base).set(database=NOME_PADRAO))


def _conectar(url, banco):
    return psycopg.connect(
        host=url.host,
        port=url.port,
        user=url.username,
        password=url.password,
        dbname=banco,
        connect_timeout=TIMEOUT_CONEXAO_SEGUNDOS,
        autocommit=True,
    )


def garantir_banco(url):
    """Cria o banco de teste se ele não existir (conexão ao banco de manutenção)."""
    url = validar_nome_banco_de_teste(url)
    with _conectar(url, BANCO_DE_MANUTENCAO) as conexao:
        existe = conexao.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (url.database,)
        ).fetchone()
        if not existe:
            try:
                conexao.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(url.database)))
            except psycopg.errors.InsufficientPrivilege as erro:
                raise BancoDeTesteInvalido(
                    f"O usuário '{url.username}' não pode criar o banco '{url.database}'. "
                    "Crie-o manualmente (CREATE DATABASE) ou use um usuário com esse privilégio."
                ) from erro


def conectar_ao_banco_de_teste(url):
    """Conexão psycopg direta ao banco de teste (verificações de esquema nos testes)."""
    url = validar_nome_banco_de_teste(url)
    return _conectar(url, url.database)
