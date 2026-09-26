"""Trava de segurança e resolução do banco de teste (sem banco; roda sempre)."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.banco_de_teste import BancoDeTesteInvalido, url_do_banco_de_teste, validar_nome_banco_de_teste

RAIZ = Path(__file__).resolve().parent.parent
BASE = "postgresql+psycopg://usuario:segredo@servidor:5433/{}"


@pytest.mark.parametrize("nome", ["bd_test", "outro_test", "a_test"])
def test_trava_aceita_nome_terminado_em_test(nome):
    assert validar_nome_banco_de_teste(BASE.format(nome)).database == nome


@pytest.mark.parametrize("nome", ["emerson", "bd_test_old", "bd_TEST", "test", "_test", "postgres", "bd_testes"])
def test_trava_recusa_nome_que_nao_termina_em_test(nome):
    with pytest.raises(BancoDeTesteInvalido, match="Recusado"):
        validar_nome_banco_de_teste(BASE.format(nome))


def test_trava_recusa_url_sem_nome_de_banco():
    with pytest.raises(BancoDeTesteInvalido):
        validar_nome_banco_de_teste("postgresql+psycopg://usuario:segredo@servidor:5433")


def test_sem_variavel_de_teste_usa_bd_test_na_instancia_do_banco_de_desenvolvimento():
    url = url_do_banco_de_teste({"DATABASE_URL": BASE.format("emerson")})
    assert (url.database, url.host, url.port, url.username, url.password) == (
        "bd_test", "servidor", 5433, "usuario", "segredo",
    )


def test_test_database_url_tem_prioridade():
    url = url_do_banco_de_teste(
        {"DATABASE_URL": BASE.format("emerson"), "TEST_DATABASE_URL": "postgresql+psycopg://x:y@outro:5/meu_test"}
    )
    assert (url.database, url.host, url.port) == ("meu_test", "outro", 5)


def test_test_database_url_tambem_passa_pela_trava():
    with pytest.raises(BancoDeTesteInvalido, match="Recusado"):
        url_do_banco_de_teste(
            {"DATABASE_URL": BASE.format("emerson"), "TEST_DATABASE_URL": "postgresql+psycopg://x:y@outro:5/emerson"}
        )


@pytest.mark.parametrize("ambiente", [{}, {"DATABASE_URL": "  "}])
def test_sem_nenhuma_url_a_mensagem_orienta(ambiente):
    with pytest.raises(BancoDeTesteInvalido, match="DATABASE_URL"):
        url_do_banco_de_teste(ambiente)


# -- sem PostgreSQL de teste acessível (subprocesso apontando para uma porta fechada) --------

def _pytest_sem_banco(*argumentos):
    ambiente = {**os.environ, "TEST_DATABASE_URL": "postgresql+psycopg://x:y@127.0.0.1:1/inexistente_test"}
    return subprocess.run(
        [sys.executable, "-m", "pytest", "tests/api/test_infraestrutura.py", "-k", "usa_bd_test", "-p", "no:cacheprovider", *argumentos],
        cwd=RAIZ, env=ambiente, capture_output=True, text=True, timeout=60,
    )


def test_sem_banco_os_testes_de_integracao_sao_pulados_com_aviso():
    resultado = _pytest_sem_banco()
    assert resultado.returncode == 0, resultado.stdout
    assert "skipped" in resultado.stdout
    assert "docker start rota-financeira-db" in resultado.stdout


def test_sem_banco_o_marcador_integracao_falha():
    resultado = _pytest_sem_banco("-m", "integracao")
    assert resultado.returncode != 0
    assert "docker start rota-financeira-db" in resultado.stdout
    assert "skipped" not in resultado.stdout.splitlines()[-1]


def test_sem_banco_o_filtro_not_integracao_nao_roda_nem_falha():
    resultado = _pytest_sem_banco("-m", "not integracao")
    assert resultado.returncode == 5  # nenhum teste selecionado: nada foi pulado nem falhou
