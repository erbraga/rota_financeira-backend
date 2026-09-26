"""Cliente HTTP do SGS contra um servidor falso local (rede real, sem depender do BACEN)."""
import logging
import socket
from datetime import timedelta
from decimal import Decimal

import pytest

from app.integrations.bacen import BacenIndisponivel, buscar_serie
from tests.integrations.servidor_falso import CDI, IPCA, ServidorFalsoSgs, hoje_brasilia

D = Decimal
HOJE = hoje_brasilia()
INICIO = HOJE - timedelta(days=60)
TIMEOUT = 0.5


@pytest.fixture
def sgs():
    with ServidorFalsoSgs() as servidor:
        yield servidor


def buscar(sgs, codigo=CDI, inicio=INICIO, fim=HOJE, timeout=TIMEOUT):
    return buscar_serie(codigo, inicio, fim, sgs.url_base, timeout)


def test_resposta_normal_com_content_type_text_html(sgs):
    linhas = buscar(sgs)
    assert linhas and all(isinstance(v, D) for _, v in linhas)
    assert [d for d, _ in linhas] == sorted(d for d, _ in linhas)
    assert linhas[-1][0] < HOJE  # o CDI só sai até o dia útil anterior
    assert all(d.weekday() < 5 for d, _ in linhas)


def test_parametros_enviados_ao_servidor(sgs):
    buscar(sgs, codigo=IPCA, inicio=HOJE - timedelta(days=200))
    codigo, inicial, final = sgs.chamadas[-1]
    assert (codigo, inicial, final) == (IPCA, (HOJE - timedelta(days=200)).strftime("%d/%m/%Y"), HOJE.strftime("%d/%m/%Y"))


def test_ipca_mensal_no_dia_1(sgs):
    linhas = buscar(sgs, codigo=IPCA, inicio=HOJE - timedelta(days=400))
    assert linhas and all(d.day == 1 for d, _ in linhas)


def test_janela_de_60_meses_e_aceita_pelo_servidor(sgs):
    assert len(buscar(sgs, inicio=HOJE - timedelta(days=1826))) > 1200


def test_datas_futuras_do_servidor_sao_descartadas(sgs):
    sgs.modo = "futuro"
    linhas = buscar(sgs)
    assert linhas and all(d <= HOJE for d, _ in linhas)
    assert all(v != D("99.99") for _, v in linhas)


@pytest.mark.parametrize("modo", ["404_sem_dados", "vazio"])
def test_sem_dados_devolve_lista_vazia(sgs, modo):
    sgs.modo = modo
    assert buscar(sgs) == []


@pytest.mark.parametrize("modo", ["500", "503", "406", "404_outro", "html", "quebrado", "linha_invalida", "objeto"])
def test_falhas_do_servidor_viram_bacen_indisponivel(sgs, modo, caplog):
    sgs.modo = modo
    with caplog.at_level(logging.WARNING, logger="app.integrations.bacen"):
        with pytest.raises(BacenIndisponivel) as erro:
            buscar(sgs)
    assert str(erro.value) == "Dados do Banco Central indisponíveis no momento"
    assert any("BACEN indisponível" in r.getMessage() and erro.value.motivo in r.getMessage() for r in caplog.records)


def test_resposta_mais_lenta_que_o_timeout(sgs, caplog):
    sgs.atraso = 1.0
    with caplog.at_level(logging.WARNING, logger="app.integrations.bacen"):
        with pytest.raises(BacenIndisponivel) as erro:
            buscar(sgs, timeout=0.3)
    assert erro.value.motivo in ("ReadTimeout", "ConnectTimeout")
    assert any(erro.value.motivo in r.getMessage() for r in caplog.records)


def test_conexao_recusada(caplog):
    with socket.socket() as s:  # porta livre e depois fechada: ninguém escuta
        s.bind(("127.0.0.1", 0))
        porta = s.getsockname()[1]
    with caplog.at_level(logging.WARNING, logger="app.integrations.bacen"):
        with pytest.raises(BacenIndisponivel) as erro:
            buscar_serie(CDI, INICIO, HOJE, f"http://127.0.0.1:{porta}/bcdata.sgs", TIMEOUT)
    assert erro.value.motivo == "ConnectionError"


def test_log_nao_vaza_url_corpo_nem_detalhes(sgs, caplog):
    sgs.modo = "html"
    with caplog.at_level(logging.DEBUG, logger="app.integrations.bacen"):
        with pytest.raises(BacenIndisponivel) as erro:
            buscar(sgs)
    # Só o log do nosso módulo (o DEBUG interno do urllib3 mostra a URL, mas não sai em produção).
    nosso = " ".join(r.getMessage() for r in caplog.records if r.name == "app.integrations.bacen")
    texto = nosso + str(erro.value)
    assert nosso and "127.0.0.1" not in texto and "Manutenção" not in texto and "/dados" not in texto


def test_janela_acima_de_10_anos_nem_chega_ao_servidor(sgs):
    with pytest.raises(ValueError):
        buscar(sgs, inicio=HOJE - timedelta(days=3651))
    assert sgs.numero_de_chamadas() == 0


def test_servidor_falso_imita_o_406_do_sgs_real():
    # Documenta o comportamento real: o cliente jamais pede isso, mas o servidor falso o reproduz.
    import requests

    with ServidorFalsoSgs() as sgs:
        r = requests.get(f"{sgs.url_base}.4389/dados", params={"formato": "json", "dataInicial": "01/01/2006", "dataFinal": HOJE.strftime("%d/%m/%Y")}, timeout=2)
    assert r.status_code == 406 and r.headers["Content-Type"].startswith("text/html")
