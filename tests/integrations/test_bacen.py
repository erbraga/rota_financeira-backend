"""Interpretação da resposta do SGS, com payloads REAIS gravados da API (2026-09-25)."""
import ast
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.integrations.bacen import (
    JANELA_MAXIMA_DIAS,
    BacenIndisponivel,
    formatar_data,
    interpretar_resposta,
    montar_consulta,
)

D = Decimal
HOJE = date(2026, 9, 25)

# Série 4389 (CDI anualizada base 252), 18 a 25/09/2026: 25/09 ainda não publicado.
CDI_REAL = (
    '[{"data":"18/09/2026","valor":"13.65"},{"data":"21/09/2026","valor":"13.65"},'
    '{"data":"22/09/2026","valor":"13.65"},{"data":"23/09/2026","valor":"13.65"},'
    '{"data":"24/09/2026","valor":"13.65"}]'
)
# Série 13522 (IPCA acumulado em 12 meses): mensal, sempre no dia 1.
IPCA_REAL = (
    '[{"data":"01/04/2026","valor":"4.39"},{"data":"01/05/2026","valor":"4.72"},'
    '{"data":"01/06/2026","valor":"4.64"},{"data":"01/07/2026","valor":"4.44"},'
    '{"data":"01/08/2026","valor":"4.22"}]'
)
# Série 433 (variação mensal do IPCA): traz um valor negativo real.
IPCA_NEGATIVO_REAL = '[{"data":"01/07/2026","valor":"0.07"},{"data":"01/08/2026","valor":"-0.32"}]'
# Série 432 (meta Selic): o SGS devolve linhas com datas FUTURAS.
SELIC_COM_FUTURO_REAL = (
    '[{"data":"24/09/2026","valor":"13.75"},{"data":"25/09/2026","valor":"13.75"},'
    '{"data":"26/09/2026","valor":"13.75"},{"data":"01/11/2026","valor":"13.75"}]'
)
# Erros reais: intervalo sem dados (404) e janela acima de 10 anos (406).
ERRO_404_REAL = (
    '{"erro":{"statusCode":404,"detail":"br.gov.bcb.pec.sgs.comum.excecoes.'
    'SGSNegocioException: Value(s) not found"}}'
)
ERRO_406_REAL = (
    '{"error":"O sistema aceita uma janela de consulta de, no máximo, 10 anos em séries de '
    'periodicidade diária","message":"Para acessar uma série de periodicidade diária, é '
    'necessário informar a dataInicial"}'
)
ERRO_400_REAL = (
    '{"erro":{"statusCode":400,"detail":"br.gov.bcb.pec.sgs.comum.excecoes.'
    'SGSNegocioException: Invalid initial date"}}'
)


def test_cdi_real_vira_decimal_exato_em_ordem_crescente():
    linhas = interpretar_resposta(200, CDI_REAL, HOJE)
    assert linhas[0] == (date(2026, 9, 18), D("13.65"))
    assert linhas[-1] == (date(2026, 9, 24), D("13.65"))
    assert [d for d, _ in linhas] == sorted(d for d, _ in linhas) and len(linhas) == 5
    assert all(isinstance(v, Decimal) for _, v in linhas)


def test_ipca_real_mensal_no_dia_1():
    linhas = interpretar_resposta(200, IPCA_REAL, HOJE)
    assert [d.day for d, _ in linhas] == [1] * 5
    assert linhas[-1] == (date(2026, 8, 1), D("4.22"))


def test_valor_negativo_e_aceito():
    assert interpretar_resposta(200, IPCA_NEGATIVO_REAL, HOJE)[-1] == (date(2026, 8, 1), D("-0.32"))


def test_datas_futuras_sao_ignoradas():
    linhas = interpretar_resposta(200, SELIC_COM_FUTURO_REAL, HOJE)
    assert [d for d, _ in linhas] == [date(2026, 9, 24), date(2026, 9, 25)]  # hoje ainda vale


def test_dia_de_hoje_nao_e_futuro_e_amanha_e():
    corpo = '[{"data":"25/09/2026","valor":"1.5"},{"data":"26/09/2026","valor":"2.5"}]'
    assert interpretar_resposta(200, corpo, HOJE) == [(date(2026, 9, 25), D("1.5"))]


def test_datas_repetidas_valem_a_ultima():
    corpo = '[{"data":"24/09/2026","valor":"13.60"},{"data":"24/09/2026","valor":"13.65"}]'
    assert interpretar_resposta(200, corpo, HOJE) == [(date(2026, 9, 24), D("13.65"))]


def test_ordem_e_normalizada():
    corpo = '[{"data":"24/09/2026","valor":"2"},{"data":"22/09/2026","valor":"1"}]'
    assert [d for d, _ in interpretar_resposta(200, corpo, HOJE)] == [date(2026, 9, 22), date(2026, 9, 24)]


def test_lista_vazia_e_vazia():
    assert interpretar_resposta(200, "[]", HOJE) == []


def test_404_com_value_not_found_e_sem_dados():
    assert interpretar_resposta(404, ERRO_404_REAL, HOJE) == []


@pytest.mark.parametrize(
    "status, corpo",
    [
        (404, '{"erro":{"statusCode":404,"detail":"outra coisa"}}'),
        (406, ERRO_406_REAL),
        (400, ERRO_400_REAL),
        (500, "Internal Server Error"),
        (503, "<html>Service Unavailable</html>"),
        (200, "<html><body>Erro</body></html>"),
        (200, "[{quebrado"),
        (200, ""),
        (200, '{"data":"24/09/2026","valor":"13.65"}'),  # objeto em vez de lista
        (200, '"texto"'),
        (200, "[1, 2]"),
        (200, '[{"valor":"13.65"}]'),
        (200, '[{"data":"24/09/2026"}]'),
        (200, '[{"data":"2026-09-24","valor":"13.65"}]'),  # data fora de dd/mm/aaaa
        (200, '[{"data":"31/02/2026","valor":"13.65"}]'),  # data inexistente
        (200, '[{"data":"24/09/2026","valor":13.65}]'),  # número em vez de texto
        (200, '[{"data":"24/09/2026","valor":"abc"}]'),
        (200, '[{"data":"24/09/2026","valor":""}]'),
        (200, '[{"data":"24/09/2026","valor":"NaN"}]'),
        (200, '[{"data":"24/09/2026","valor":"Infinity"}]'),
        (200, '[{"data":"24/09/2026","valor":"1e999999"}]'),
        (200, '[{"data":"24/09/2026","valor":"13,65"}]'),  # vírgula decimal
        (200, '[{"data":"24/09/2026","valor":"1234567.5"}]'),  # não cabe em NUMERIC(12,6)
        (200, '[{"data":"24/09/2026","valor":"1.1234567"}]'),  # 7 decimais: não se arredonda em silêncio
        (200, '[{"data":"25/09/2026","valor":"13.65"},{"data":"24/09/2026","valor":"x"}]'),  # uma linha ruim invalida tudo
    ],
)
def test_respostas_com_falha_levantam_bacen_indisponivel(status, corpo):
    with pytest.raises(BacenIndisponivel) as erro:
        interpretar_resposta(status, corpo, HOJE)
    assert erro.value.motivo
    assert str(erro.value) == "Dados do Banco Central indisponíveis no momento"  # nada interno ao cliente


def test_linha_invalida_e_futura_tambem_invalida_a_resposta():
    # A validação vale para todas as linhas, inclusive as futuras que seriam descartadas.
    with pytest.raises(BacenIndisponivel):
        interpretar_resposta(200, '[{"data":"01/11/2026","valor":"abc"}]', HOJE)


def test_content_type_nao_entra_na_interpretacao():
    # O SGS devolve text/html com corpo JSON; a função só recebe status e corpo.
    assert interpretar_resposta(200, CDI_REAL, HOJE)


# ------------------------------------------------------------------ URL e janela


def test_formatar_data():
    assert formatar_data(date(2026, 9, 5)) == "05/09/2026"


def test_consulta_de_60_meses_sai_certa():
    url, parametros = montar_consulta("https://api.bcb.gov.br/dados/serie/bcdata.sgs", 4389, date(2021, 9, 25), HOJE)
    assert url == "https://api.bcb.gov.br/dados/serie/bcdata.sgs.4389/dados"
    assert parametros == {"formato": "json", "dataInicial": "25/09/2021", "dataFinal": "25/09/2026"}


def test_url_base_com_barra_final_e_normalizada():
    url, _ = montar_consulta("http://127.0.0.1:9/x.sgs/", 13522, date(2026, 1, 1), HOJE)
    assert url == "http://127.0.0.1:9/x.sgs.13522/dados"


def test_janela_de_exatamente_10_anos_passa_e_acima_e_recusada():
    inicio_ok = date(2016, 9, 27)  # 3.650 dias antes de 25/09/2026
    assert (HOJE - inicio_ok).days == JANELA_MAXIMA_DIAS
    montar_consulta("http://x", 1, inicio_ok, HOJE)
    with pytest.raises(ValueError):
        montar_consulta("http://x", 1, date(2016, 9, 26), HOJE)
    with pytest.raises(ValueError):
        montar_consulta("http://x", 1, date(2006, 1, 1), HOJE)


def test_data_inicial_posterior_a_final_e_recusada():
    with pytest.raises(ValueError):
        montar_consulta("http://x", 1, date(2026, 9, 26), HOJE)


# ---------------------------------------------------------------------- pureza


def test_bacen_nao_importa_flask_nem_banco():
    fonte = Path(__file__).resolve().parents[2] / "app" / "integrations" / "bacen.py"
    proibidos = ("flask", "sqlalchemy", "flask_sqlalchemy", "marshmallow", "flask_jwt_extended", "app.")
    for no in ast.walk(ast.parse(fonte.read_text(encoding="utf-8"))):
        nomes = [a.name for a in no.names] if isinstance(no, ast.Import) else [no.module] if isinstance(no, ast.ImportFrom) else []
        for nome in nomes:
            assert not nome.startswith(proibidos), f"bacen.py importa {nome}"
