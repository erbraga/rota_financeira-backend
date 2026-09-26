"""Fixtures compartilhadas dos testes de integração (`tests/api/`).

Só os testes de `tests/api/` recebem o marcador `integracao` e usam o PostgreSQL de teste
(`bd_test`, ver `banco_de_teste.py`). Os demais testes continuam sem banco. As importações
da aplicação são feitas dentro das fixtures para que os testes puros não dependam do `.env`.
"""
import functools
import itertools
import logging
import re
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import psycopg
import pytest

from tests.banco_de_teste import (
    BancoDeTesteInvalido,
    garantir_banco,
    url_do_banco_de_teste,
)

RAIZ = Path(__file__).resolve().parent.parent
PASTA_API = Path(__file__).resolve().parent / "api"
DICA_BANCO = "Suba o container: docker start rota-financeira-db"

# (método, regra no formato do OpenAPI, status) de cada resposta vista pelos testes.
_provocados = set()
_apps = []


def pytest_collection_modifyitems(items):
    for item in items:
        if PASTA_API in item.path.parents:
            item.add_marker(pytest.mark.integracao)


def _modo_estrito(config):
    """Com `-m integracao` a falta do banco é falha; senão os testes são pulados."""
    expressao = config.getoption("markexpr") or ""
    return "integracao" in expressao and "not integracao" not in expressao


def _regra_openapi(regra):
    return re.sub(r"<(?:\w+:)?(\w+)>", r"{\1}", regra)


def registrar_mapa_de_codigos(app, principal=True):
    from flask import request

    @app.after_request
    def anotar(resposta):
        if request.url_rule is not None:
            _provocados.add((request.method, _regra_openapi(request.url_rule.rule), resposta.status_code))
        return resposta

    if principal:
        _apps.append(app)


def pytest_terminal_summary(terminalreporter):
    """Informativo: códigos do Swagger que nenhum teste de integração provocou."""
    if not _apps or not _provocados:
        return
    especificacao = _apps[0].test_client().get("/apispec.json").get_json()
    documentados = {
        (metodo.upper(), caminho, int(codigo))
        for caminho, operacoes in especificacao["paths"].items()
        for metodo, operacao in operacoes.items()
        for codigo in operacao["responses"]
        if codigo.isdigit()
    }
    faltam = sorted(documentados - _provocados)
    terminalreporter.section("códigos documentados no Swagger sem teste de integração")
    if not faltam:
        terminalreporter.write_line("nenhum: todos os códigos documentados foram provocados")
        return
    terminalreporter.write_line(
        f"{len(faltam)} de {len(documentados)} (só conclusivo com a suíte completa):"
    )
    for metodo, caminho, codigo in faltam:
        terminalreporter.write_line(f"  {metodo} {caminho} → {codigo}")


def limpar_banco(app):
    """Esvazia todas as tabelas da aplicação (menos `alembic_version`) e zera as identidades."""
    from sqlalchemy import text

    from app.extensions import db

    with app.app_context():
        tabelas = ", ".join(f'"{tabela.name}"' for tabela in db.metadata.sorted_tables)
        with db.engine.begin() as conexao:
            conexao.execute(text(f"TRUNCATE {tabelas} RESTART IDENTITY CASCADE"))


def _aplicar_migrations(app):
    import flask_migrate

    # O env.py do Alembic chama `fileConfig`, que desativa loggers já criados e troca os
    # handlers da raiz; restaura o estado para não silenciar os testes de log (caplog).
    raiz = logging.getLogger()
    handlers, nivel = list(raiz.handlers), raiz.level
    desativados = {
        nome: logger.disabled
        for nome, logger in logging.root.manager.loggerDict.items()
        if isinstance(logger, logging.Logger)
    }
    try:
        with app.app_context():
            flask_migrate.upgrade(directory=str(RAIZ / "migrations"))
    finally:
        raiz.handlers[:] = handlers
        raiz.setLevel(nivel)
        for nome, desativado in desativados.items():
            logging.getLogger(nome).disabled = desativado


@pytest.fixture(scope="session")
def app(request):
    from app import create_app
    from app.extensions import db

    try:
        url = url_do_banco_de_teste()
    except BancoDeTesteInvalido as erro:
        pytest.fail(str(erro), pytrace=False)
    try:
        garantir_banco(url)
    except psycopg.OperationalError as erro:
        motivo = f"PostgreSQL de teste inacessível ({str(erro).strip().splitlines()[0]}). {DICA_BANCO}"
        if _modo_estrito(request.config):
            pytest.fail(motivo, pytrace=False)
        pytest.skip(motivo)
    except BancoDeTesteInvalido as erro:
        pytest.fail(str(erro), pytrace=False)

    aplicacao = create_app(
        {"SQLALCHEMY_DATABASE_URI": url.render_as_string(hide_password=False), "TESTING": True}
    )
    registrar_mapa_de_codigos(aplicacao)
    _aplicar_migrations(aplicacao)
    yield aplicacao
    with aplicacao.app_context():
        db.engine.dispose()


@pytest.fixture(autouse=True)
def _banco_limpo(request):
    if request.node.get_closest_marker("integracao") is None:
        return
    limpar_banco(request.getfixturevalue("app"))


@pytest.fixture
def client(app):
    return app.test_client()


@functools.lru_cache(maxsize=None)
def _hash_da_senha(senha):
    from werkzeug.security import generate_password_hash

    return generate_password_hash(senha)  # scrypt custa ~70 ms: calculado uma vez por senha


@pytest.fixture
def criar_usuario(app):
    """Cria usuário e token direto no banco, com o hash da senha em cache (o login real passa
    pelo HTTP só nos testes de autenticação)."""
    from app.extensions import db
    from app.models import Usuario
    from app.services.auth import criar_token

    contador = itertools.count(1)

    def _criar(nome="Ana", email=None, senha="senha-da-ana-x9"):
        email = email or f"usuario{next(contador)}@exemplo.com"
        with app.app_context():
            usuario = Usuario(nome=nome, email=email, senha_hash=_hash_da_senha(senha))
            db.session.add(usuario)
            db.session.commit()
            token, _ = criar_token(usuario)
            usuario_id = usuario.id
        return SimpleNamespace(
            id=usuario_id,
            nome=nome,
            email=email,
            senha=senha,
            token=token,
            cabecalho={"Authorization": f"Bearer {token}"},
        )

    return _criar


@pytest.fixture
def usuario(criar_usuario):
    return criar_usuario("Ana", "ana@exemplo.com", "senha-da-ana-x9")


@pytest.fixture
def outro_usuario(criar_usuario):
    return criar_usuario("Beto", "beto@exemplo.com", "senha-do-beto-x9")


@pytest.fixture
def credenciais_recusadas(app, usuario):
    """Cabeçalhos que a API deve recusar com 401: `[(descrição, cabeçalhos, mensagem)]`."""
    import time

    import jwt as pyjwt
    from flask_jwt_extended import create_access_token

    with app.app_context():
        valido = create_access_token(identity=str(usuario.id))
        expirado = create_access_token(identity=str(usuario.id), expires_delta=timedelta(seconds=-5))
        sub_inteiro = create_access_token(identity=usuario.id)
    agora = int(time.time())
    de_outra_chave = pyjwt.encode(
        {"sub": str(usuario.id), "iat": agora, "nbf": agora, "exp": agora + 600, "jti": "x", "type": "access", "fresh": False},
        "outra-chave-qualquer-com-mais-de-32-caracteres",
        algorithm="HS256",
    )
    ausente, invalido = "Token de autenticação ausente", "Token inválido"
    return [
        ("sem cabeçalho", {}, ausente),
        ("esquema Basic", {"Authorization": f"Basic {valido}"}, ausente),
        ("token malformado", {"Authorization": "Bearer abc"}, invalido),
        ("assinado com outra chave", {"Authorization": f"Bearer {de_outra_chave}"}, invalido),
        ("sub inteiro", {"Authorization": f"Bearer {sub_inteiro}"}, invalido),
        ("expirado", {"Authorization": f"Bearer {expirado}"}, "Token expirado"),
    ]


@pytest.fixture
def corpo_simulacao():
    """Simulação válida (exemplo da Etapa 7: preço corrigido em 36 meses = 108.410,78)."""

    def _corpo(**alteracoes):
        return {
            "nome": "Onix 2026",
            "valor_veiculo": 95000,
            "valor_entrada": 20000,
            "taxa_ipca_projetada": 4.5,
            "taxa_fundo_rendimento": 10.5,
            "prazo_meses_fundo": 36,
        } | alteracoes

    return _corpo


@pytest.fixture
def corpo_opcao():
    """Opção de financiamento válida (Price, 48 meses)."""

    def _corpo(**alteracoes):
        return {
            "nome": "Banco X 48x",
            "taxa_juros_mensal": 1.99,
            "prazo_meses": 48,
            "sistema_amortizacao": "PRICE",
            "valor_entrada": 20000,
        } | alteracoes

    return _corpo


@pytest.fixture
def servidor_falso(app, monkeypatch):
    """Servidor HTTP falso do SGS; a aplicação passa a consultá-lo em vez do BACEN real."""
    from tests.integrations.servidor_falso import ServidorFalsoSgs

    with ServidorFalsoSgs() as servidor:
        monkeypatch.setitem(app.config, "BACEN_URL_BASE", servidor.url_base)
        yield servidor
