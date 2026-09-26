"""`/parcelas` e `/resultado`: números da spec da Etapa 7 e conferência por referência independente.

As tabelas de Price e SAC são refeitas aqui em `Fraction` (centavos exatos) e o preço corrigido e o
fundo em `Decimal` de 60 dígitos, sem usar o código da aplicação.
"""
import math
from decimal import ROUND_HALF_UP, Decimal, localcontext
from fractions import Fraction

import pytest
from sqlalchemy import text

from app.extensions import db

RAIZ = "/api/simulacoes"
SIM_NAO_ENCONTRADA = {"erro": "Simulação não encontrada"}
OPCAO_NAO_ENCONTRADA = {"erro": "Opção de financiamento não encontrada"}
D = Decimal


# --------------------------------------------------------------------------- referência independente

def centavos(x):
    """Arredonda ao centavo, metade para cima (Fraction exata)."""
    return Fraction(math.floor(x * 100 + Fraction(1, 2)), 100)


def frac(x):
    return Fraction(str(x))


def referencia_price(valor, taxa_pct, n):
    saldo, i = frac(valor), frac(taxa_pct) / 100
    pmt = saldo / n if i == 0 else saldo * i / (1 - (1 + i) ** -n)
    parcela, linhas = centavos(pmt), []
    for k in range(1, n + 1):
        juros = centavos(saldo * i)
        amortizacao = saldo if k == n else min(parcela - juros, saldo)
        linhas.append((k, amortizacao + juros, juros, amortizacao, saldo - amortizacao))
        saldo -= amortizacao
    return linhas


def referencia_sac(valor, taxa_pct, n):
    saldo, i = frac(valor), frac(taxa_pct) / 100
    fixa, linhas = centavos(saldo / n), []
    for k in range(1, n + 1):
        juros = centavos(saldo * i)
        amortizacao = saldo if k == n else min(fixa, saldo)
        linhas.append((k, amortizacao + juros, juros, amortizacao, saldo - amortizacao))
        saldo -= amortizacao
    return linhas


def q2(x):
    return x.quantize(D("0.01"), rounding=ROUND_HALF_UP)


def preco_no_mes(valor, ipca_pct, mes):
    with localcontext() as c:
        c.prec = 60
        return q2(D(str(valor)) * (1 + D(str(ipca_pct)) / 100) ** (D(mes) / 12))


def saldo_do_fundo(capital, aporte, rendimento_pct, mes):
    with localcontext() as c:
        c.prec = 60
        i = (1 + D(str(rendimento_pct)) / 100) ** (D(1) / 12) - 1
        saldo = D(str(capital))
        for _ in range(mes):
            saldo = saldo * (1 + i) + D(str(aporte))
        return saldo


# --------------------------------------------------------------------------- fixtures e ajudantes

@pytest.fixture
def exemplo(client, usuario, corpo_simulacao, corpo_opcao):
    """Exemplo da spec da Etapa 7: veículo 95.000, IPCA 4,5 %, fundo 10,5 %, 36 meses, entrada 20.000."""
    h = usuario.cabecalho
    simulacao = client.post(RAIZ, json=corpo_simulacao(), headers=h).get_json()["id"]
    a = client.post(f"{RAIZ}/{simulacao}/financiamentos", json=corpo_opcao(), headers=h).get_json()["id"]
    b = client.post(
        f"{RAIZ}/{simulacao}/financiamentos",
        json=corpo_opcao(nome="Banco Y 60x", taxa_juros_mensal=1.5, prazo_meses=60, sistema_amortizacao="SAC", valor_entrada=30000),
        headers=h,
    ).get_json()["id"]
    return {"simulacao": simulacao, "a": a, "b": b, "url": f"{RAIZ}/{simulacao}/resultado", "cabecalho": h}


def resultado(client, exemplo, consulta=""):
    resposta = client.get(exemplo["url"] + consulta, headers=exemplo["cabecalho"])
    assert resposta.status_code == 200, resposta.get_data(as_text=True)
    return resposta.get_json()


def nova_simulacao(client, usuario, corpo_simulacao, **alteracoes):
    return client.post(RAIZ, json=corpo_simulacao(**alteracoes), headers=usuario.cabecalho).get_json()["id"]


def nova_opcao(client, usuario, simulacao, corpo_opcao, **alteracoes):
    resposta = client.post(f"{RAIZ}/{simulacao}/financiamentos", json=corpo_opcao(**alteracoes), headers=usuario.cabecalho)
    assert resposta.status_code == 201, resposta.get_data(as_text=True)
    return resposta.get_json()["id"]


# --------------------------------------------------------------------------- /resultado: exemplo da spec

def test_resultado_bate_com_os_numeros_da_spec(client, exemplo):
    corpo = resultado(client, exemplo)
    assert set(corpo) == {"simulacao", "cenarios", "menor_custo", "series"}
    assert corpo["simulacao"] == {
        "id": exemplo["simulacao"], "nome": "Onix 2026", "valor_veiculo": 95000.0, "valor_entrada": 20000.0,
        "taxa_ipca_projetada": 4.5, "taxa_fundo_rendimento": 10.5, "prazo_meses_fundo": 36,
    }
    assert corpo["cenarios"]["a_vista"] == {"custo_total": 95000.0}
    assert corpo["cenarios"]["financiamentos"] == [
        {
            "id": exemplo["a"], "nome": "Banco X 48x", "sistema_amortizacao": "PRICE", "valor_financiado": 75000.0,
            "valor_entrada": 20000.0, "prazo_meses": 48, "primeira_parcela": 2440.16, "ultima_parcela": 2440.55,
            "total_pago": 117128.07, "total_juros": 42128.07, "custo_total": 137128.07,
        },
        {
            "id": exemplo["b"], "nome": "Banco Y 60x", "sistema_amortizacao": "SAC", "valor_financiado": 65000.0,
            "valor_entrada": 30000.0, "prazo_meses": 60, "primeira_parcela": 2058.33, "ultima_parcela": 1099.78,
            "total_pago": 94737.5, "total_juros": 29737.5, "custo_total": 124737.5,
        },
    ]
    assert corpo["cenarios"]["fundo"] == {
        "capital_inicial": 20000.0, "aporte_mensal": 1948.07, "prazo_meses": 36, "mes_da_meta": 36,
        "alcanca_a_meta": True, "preco_na_compra": 108410.78, "total_aportado": 70130.52,
        "rendimento": 18280.45, "saldo_final": 108410.97, "custo_total": 108410.78,
    }
    assert corpo["menor_custo"] == {"cenario": "a_vista", "id": None}


def test_o_fundo_do_exemplo_usa_o_menor_aporte_em_centavos_que_atinge_a_meta(client, exemplo):
    fundo = resultado(client, exemplo)["cenarios"]["fundo"]
    meta = preco_no_mes(95000, 4.5, 36)
    assert meta == D("108410.78")
    assert saldo_do_fundo(20000, "1948.07", 10.5, 36) >= meta
    assert saldo_do_fundo(20000, "1948.06", 10.5, 36) < meta  # um centavo a menos não bastaria
    assert D(str(fundo["saldo_final"])) == q2(saldo_do_fundo(20000, "1948.07", 10.5, 36))
    assert D(str(fundo["total_aportado"])) == D("1948.07") * 36
    assert D(str(fundo["rendimento"])) == D(str(fundo["saldo_final"])) - 20000 - D(str(fundo["total_aportado"]))


# --------------------------------------------------------------------------- /resultado: séries

def test_series_no_eixo_comum_do_mes_0_ao_maior_prazo(client, exemplo):
    series = resultado(client, exemplo)["series"]
    assert [p["mes"] for p in series] == list(range(61))
    assert all(set(p) == {"mes", "preco_corrigido", "saldo_fundo", "saldo_devedor"} for p in series)
    assert all(set(p["saldo_devedor"]) == {str(exemplo["a"]), str(exemplo["b"])} for p in series)


def test_preco_corrigido_em_todo_o_eixo_confere_com_a_formula(client, exemplo):
    for ponto in resultado(client, exemplo)["series"]:
        assert D(str(ponto["preco_corrigido"])) == preco_no_mes(95000, 4.5, ponto["mes"]), ponto["mes"]


def test_saldo_do_fundo_mes_a_mes_confere_com_a_recorrencia_e_termina_em_null(client, exemplo):
    series = resultado(client, exemplo)["series"]
    aporte = "1948.07"
    for ponto in series[:37]:
        assert D(str(ponto["saldo_fundo"])) == q2(saldo_do_fundo(20000, aporte, 10.5, ponto["mes"])), ponto["mes"]
    assert series[0]["saldo_fundo"] == 20000.0 and series[36]["saldo_fundo"] == 108410.97
    assert all(p["saldo_fundo"] is None for p in series[37:])  # fundo termina na compra: null, não zero


def test_saldo_devedor_de_cada_opcao_confere_com_a_tabela_de_referencia_e_termina_em_null(client, exemplo):
    series = resultado(client, exemplo)["series"]
    for chave, referencia, valor in (
        (str(exemplo["a"]), referencia_price(75000, 1.99, 48), 75000),
        (str(exemplo["b"]), referencia_sac(65000, 1.5, 60), 65000),
    ):
        assert series[0]["saldo_devedor"][chave] == valor  # mês 0: o valor financiado
        for linha in referencia:
            assert frac(series[linha[0]]["saldo_devedor"][chave]) == linha[4], (chave, linha[0])
        ultimo = referencia[-1][0]
        assert series[ultimo]["saldo_devedor"][chave] == 0.0  # último mês da opção: 0,00
        assert all(p["saldo_devedor"][chave] is None for p in series[ultimo + 1:])  # depois: null


# --------------------------------------------------------------------------- /parcelas

@pytest.mark.parametrize(
    "chave, referencia, valor, taxa, prazo",
    [("a", referencia_price, 75000, 1.99, 48), ("b", referencia_sac, 65000, 1.5, 60)],
)
def test_parcelas_batem_linha_a_linha_com_a_referencia(client, exemplo, chave, referencia, valor, taxa, prazo):
    resposta = client.get(f"{RAIZ}/{exemplo['simulacao']}/financiamentos/{exemplo[chave]}/parcelas", headers=exemplo["cabecalho"])
    corpo = resposta.get_json()
    assert resposta.status_code == 200 and set(corpo) == {"financiamento", "parcelas", "totais"}
    esperado = referencia(valor, taxa, prazo)
    assert len(corpo["parcelas"]) == prazo
    for linha, (numero, parcela, juros, amortizacao, saldo) in zip(corpo["parcelas"], esperado):
        assert set(linha) == {"numero", "valor_parcela", "juros", "amortizacao", "saldo_devedor"}
        assert linha["numero"] == numero
        assert (frac(linha["valor_parcela"]), frac(linha["juros"]), frac(linha["amortizacao"]), frac(linha["saldo_devedor"])) == (
            parcela, juros, amortizacao, saldo,
        ), numero
    total_pago = sum(p for _, p, *_ in esperado)
    total_juros = sum(j for _, _, j, *_ in esperado)
    assert frac(corpo["totais"]["total_pago"]) == total_pago
    assert frac(corpo["totais"]["total_juros"]) == total_juros
    assert frac(corpo["totais"]["custo_total"]) == total_pago + frac(corpo["financiamento"]["valor_entrada"])


def test_parcelas_numeros_da_spec_e_propriedades(client, exemplo):
    corpo = client.get(f"{RAIZ}/{exemplo['simulacao']}/financiamentos/{exemplo['a']}/parcelas", headers=exemplo["cabecalho"]).get_json()
    assert corpo["financiamento"] == {
        "id": exemplo["a"], "nome": "Banco X 48x", "prazo_meses": 48, "sistema_amortizacao": "PRICE",
        "taxa_juros_mensal": 1.99, "valor_entrada": 20000.0, "valor_financiado": 75000.0,
    }
    assert corpo["totais"] == {"custo_total": 137128.07, "total_juros": 42128.07, "total_pago": 117128.07}
    linhas = corpo["parcelas"]
    assert (linhas[0]["valor_parcela"], linhas[-1]["valor_parcela"]) == (2440.16, 2440.55)  # a última absorve o resíduo
    assert sum(frac(p["amortizacao"]) for p in linhas) == 75000
    assert linhas[-1]["saldo_devedor"] == 0.0
    assert all(frac(p["valor_parcela"]) == frac(p["juros"]) + frac(p["amortizacao"]) for p in linhas)
    anterior = Fraction(75000)
    for p in linhas:  # saldo_devedor é o saldo APÓS o pagamento
        assert frac(p["saldo_devedor"]) == anterior - frac(p["amortizacao"])
        anterior = frac(p["saldo_devedor"])


def test_parcelas_taxa_zero_prazo_maximo_e_prazo_um(client, usuario, corpo_simulacao, corpo_opcao):
    sim = nova_simulacao(client, usuario, corpo_simulacao)
    casos = [
        (referencia_price, {"taxa_juros_mensal": 0, "prazo_meses": 48, "valor_entrada": 20000}, 75000, 0, 48),
        (referencia_sac, {"taxa_juros_mensal": 0, "prazo_meses": 72, "sistema_amortizacao": "SAC", "valor_entrada": 0}, 95000, 0, 72),
        (referencia_price, {"taxa_juros_mensal": 20, "prazo_meses": 72, "valor_entrada": 0}, 95000, 20, 72),
        (referencia_sac, {"taxa_juros_mensal": 20, "prazo_meses": 1, "sistema_amortizacao": "SAC", "valor_entrada": 0}, 95000, 20, 1),
        (referencia_price, {"taxa_juros_mensal": 1.99, "prazo_meses": 1, "valor_entrada": 94999.99}, "0.01", 1.99, 1),
    ]
    for referencia, alteracoes, financiado, taxa, prazo in casos:
        opcao = nova_opcao(client, usuario, sim, corpo_opcao, **alteracoes)
        corpo = client.get(f"{RAIZ}/{sim}/financiamentos/{opcao}/parcelas", headers=usuario.cabecalho).get_json()
        esperado = referencia(financiado, taxa, prazo)
        assert len(corpo["parcelas"]) == prazo
        for linha, (_, parcela, juros, amortizacao, saldo) in zip(corpo["parcelas"], esperado):
            assert (frac(linha["valor_parcela"]), frac(linha["juros"]), frac(linha["saldo_devedor"])) == (parcela, juros, saldo)
        client.delete(f"{RAIZ}/{sim}/financiamentos/{opcao}", headers=usuario.cabecalho)


# --------------------------------------------------------------------------- menor_custo, 0/1/3 opções

def test_sem_opcoes_de_financiamento(client, usuario, corpo_simulacao):
    sim = nova_simulacao(client, usuario, corpo_simulacao)
    corpo = client.get(f"{RAIZ}/{sim}/resultado", headers=usuario.cabecalho).get_json()
    assert corpo["cenarios"]["financiamentos"] == []
    assert corpo["cenarios"]["a_vista"] == {"custo_total": 95000.0}
    assert len(corpo["series"]) == 37  # eixo até o prazo do fundo
    assert all(p["saldo_devedor"] == {} for p in corpo["series"])
    assert corpo["menor_custo"] == {"cenario": "a_vista", "id": None}


def test_tres_opcoes_em_ordem_de_criacao_e_eixo_ate_o_maior_prazo(client, usuario, corpo_simulacao, corpo_opcao):
    sim = nova_simulacao(client, usuario, corpo_simulacao)
    ids = [
        nova_opcao(client, usuario, sim, corpo_opcao, nome="Curta", prazo_meses=12),
        nova_opcao(client, usuario, sim, corpo_opcao, nome="Média", prazo_meses=36, sistema_amortizacao="SAC"),
        nova_opcao(client, usuario, sim, corpo_opcao, nome="Longa", prazo_meses=72),
    ]
    corpo = client.get(f"{RAIZ}/{sim}/resultado", headers=usuario.cabecalho).get_json()
    assert [f["id"] for f in corpo["cenarios"]["financiamentos"]] == ids
    assert [f["nome"] for f in corpo["cenarios"]["financiamentos"]] == ["Curta", "Média", "Longa"]
    assert [p["mes"] for p in corpo["series"]] == list(range(73))
    assert corpo["series"][12]["saldo_devedor"][str(ids[0])] == 0.0 and corpo["series"][13]["saldo_devedor"][str(ids[0])] is None
    assert corpo["series"][72]["saldo_devedor"][str(ids[2])] == 0.0


def test_a_vista_vence_o_empate_com_ipca_zero_e_com_financiamento_sem_juros(client, usuario, corpo_simulacao, corpo_opcao):
    sim = nova_simulacao(client, usuario, corpo_simulacao, taxa_ipca_projetada=0)
    nova_opcao(client, usuario, sim, corpo_opcao, taxa_juros_mensal=0, valor_entrada=20000)
    corpo = client.get(f"{RAIZ}/{sim}/resultado", headers=usuario.cabecalho).get_json()
    assert corpo["cenarios"]["fundo"]["custo_total"] == 95000.0  # preço não corrigido: igual ao à vista
    assert corpo["cenarios"]["financiamentos"][0]["custo_total"] == 95000.0  # sem juros: igual ao à vista
    assert corpo["menor_custo"] == {"cenario": "a_vista", "id": None}  # desempate: à vista primeiro


def test_com_ipca_negativo_o_fundo_pode_ser_o_menor_custo(client, usuario, corpo_simulacao):
    sim = nova_simulacao(client, usuario, corpo_simulacao, taxa_ipca_projetada=-5)
    corpo = client.get(f"{RAIZ}/{sim}/resultado", headers=usuario.cabecalho).get_json()
    esperado = preco_no_mes(95000, -5, 36)
    assert corpo["cenarios"]["fundo"]["custo_total"] == float(esperado) < 95000
    assert corpo["menor_custo"] == {"cenario": "fundo", "id": None}


# --------------------------------------------------------------------------- modo ?aporte_mensal=

def test_modo_aporte_1500_alcanca_a_meta_no_mes_46(client, exemplo):
    corpo = resultado(client, exemplo, "?aporte_mensal=1500")
    fundo = corpo["cenarios"]["fundo"]
    assert fundo == {
        "capital_inicial": 20000.0, "aporte_mensal": 1500.0, "prazo_meses": 46, "mes_da_meta": 46, "alcanca_a_meta": True,
        "preco_na_compra": 112461.2, "total_aportado": 69000.0, "rendimento": 24040.26, "saldo_final": 113040.26,
        "custo_total": 112461.2,
    }
    # independente: 46 é o primeiro mês em que o saldo alcança o preço DAQUELE mês
    assert saldo_do_fundo(20000, 1500, 10.5, 46) >= preco_no_mes(95000, 4.5, 46)
    assert saldo_do_fundo(20000, 1500, 10.5, 45) < preco_no_mes(95000, 4.5, 45)
    assert corpo["menor_custo"] == {"cenario": "a_vista", "id": None}


def test_modo_aporte_300_nao_alcanca_e_o_fundo_sai_do_menor_custo(client, exemplo):
    corpo = resultado(client, exemplo, "?aporte_mensal=300")
    assert corpo["cenarios"]["fundo"] == {
        "capital_inicial": 20000.0, "aporte_mensal": 300.0, "prazo_meses": 60, "mes_da_meta": None, "alcanca_a_meta": False,
        "preco_na_compra": None, "total_aportado": 18000.0, "rendimento": 18196.14, "saldo_final": 56196.14, "custo_total": None,
    }
    assert D(str(56196.14)) == q2(saldo_do_fundo(20000, 300, 10.5, 60))
    assert all(saldo_do_fundo(20000, 300, 10.5, m) < preco_no_mes(95000, 4.5, m) for m in range(61))
    assert corpo["menor_custo"]["cenario"] != "fundo"
    assert len(corpo["series"]) == 61 and corpo["series"][60]["saldo_fundo"] == 56196.14  # o fundo vai até o mês 60


def test_modo_aporte_ignora_o_prazo_do_fundo_da_simulacao(client, usuario, corpo_simulacao):
    curto = nova_simulacao(client, usuario, corpo_simulacao, prazo_meses_fundo=1)
    longo = nova_simulacao(client, usuario, corpo_simulacao, prazo_meses_fundo=60)
    a = client.get(f"{RAIZ}/{curto}/resultado?aporte_mensal=1500", headers=usuario.cabecalho).get_json()["cenarios"]["fundo"]
    b = client.get(f"{RAIZ}/{longo}/resultado?aporte_mensal=1500", headers=usuario.cabecalho).get_json()["cenarios"]["fundo"]
    assert a == b and a["mes_da_meta"] == 46


@pytest.mark.parametrize("valor", ["0", "0.00", "1500.5", "9999999.00", "1500.000", " 1500"])
def test_modo_aporte_aceita_valores_validos(client, exemplo, valor):
    assert client.get(exemplo["url"], query_string={"aporte_mensal": valor}, headers=exemplo["cabecalho"]).status_code == 200


def test_modo_aporte_teto_alcanca_a_meta_no_mes_1(client, exemplo):
    fundo = resultado(client, exemplo, "?aporte_mensal=9999999")["cenarios"]["fundo"]
    assert (fundo["mes_da_meta"], fundo["alcanca_a_meta"]) == (1, True)


@pytest.mark.parametrize(
    "consulta",
    ["?aporte_mensal=", "?aporte_mensal=abc", "?aporte_mensal=-1", "?aporte_mensal=10000000", "?aporte_mensal=1500.001",
     "?aporte_mensal=NaN", "?aporte_mensal=Infinity", "?aporte_mensal=1e999999", "?aporte_mensal=1&aporte_mensal=2",
     "?aporte=1500", "?x=1", "?aporte_mensal=1500&x=1"],
)
def test_parametros_invalidos_dao_422_em_portugues(client, exemplo, consulta):
    resposta = client.get(exemplo["url"] + consulta, headers=exemplo["cabecalho"])
    corpo = resposta.get_json()
    assert resposta.status_code == 422 and corpo["erro"] == "Dados inválidos" and corpo["detalhes"]
    texto = resposta.get_data(as_text=True)
    assert not any(e in texto for e in ("Not a valid", "Unknown field", "Missing", "Must be"))


# --------------------------------------------------------------------------- números, leitura e determinismo

def test_todos_os_valores_sao_numeros_json(client, exemplo):
    corpo = resultado(client, exemplo)

    def numeros(x):
        if isinstance(x, dict):
            for v in x.values():
                yield from numeros(v)
        elif isinstance(x, list):
            for v in x:
                yield from numeros(v)
        elif x is not None and not isinstance(x, (str, bool)):
            yield x

    assert all(isinstance(n, (int, float)) for n in numeros(corpo))
    assert not any(isinstance(v, str) for f in corpo["cenarios"]["financiamentos"] for k, v in f.items() if k not in ("nome", "sistema_amortizacao"))
    assert isinstance(corpo["cenarios"]["fundo"]["aporte_mensal"], float)


def test_resultado_e_parcelas_so_leem_e_sao_deterministicos(client, app, exemplo):
    def contagens():
        with app.app_context():
            return [db.session.execute(text(f"SELECT count(*) FROM {t}")).scalar() for t in ("simulacoes", "opcoes_financiamento", "indices_economicos_cache")]

    antes = contagens()
    parcelas = f"{RAIZ}/{exemplo['simulacao']}/financiamentos/{exemplo['a']}/parcelas"
    primeira = (resultado(client, exemplo), client.get(parcelas, headers=exemplo["cabecalho"]).get_json())
    segunda = (resultado(client, exemplo), client.get(parcelas, headers=exemplo["cabecalho"]).get_json())
    assert primeira == segunda and contagens() == antes == [1, 2, 0]


def test_resultado_reflete_a_edicao_da_simulacao(client, exemplo, corpo_simulacao):
    client.put(exemplo["url"].removesuffix("/resultado"), json=corpo_simulacao(valor_veiculo=100000), headers=exemplo["cabecalho"])
    corpo = resultado(client, exemplo)
    assert corpo["cenarios"]["a_vista"] == {"custo_total": 100000.0}
    assert corpo["cenarios"]["fundo"]["preco_na_compra"] == float(preco_no_mes(100000, 4.5, 36))


# --------------------------------------------------------------------------- 404 e 401

@pytest.mark.parametrize("simulacao_id", [0, 999999, 2147483648, 99999999999999999999])
def test_simulacao_inexistente_ou_gigante_da_404_mesmo_com_parametro_invalido(client, usuario, simulacao_id):
    for sufixo in ("/resultado", "/resultado?aporte_mensal=abc", "/financiamentos/1/parcelas"):
        resposta = client.get(f"{RAIZ}/{simulacao_id}{sufixo}", headers=usuario.cabecalho)
        assert resposta.status_code == 404 and resposta.get_json() == SIM_NAO_ENCONTRADA, sufixo


def test_simulacao_de_outro_usuario_da_o_mesmo_404_antes_de_validar_parametros(client, exemplo, outro_usuario):
    alheio = outro_usuario.cabecalho
    for sufixo in ("/resultado", "/resultado?aporte_mensal=abc", f"/financiamentos/{exemplo['a']}/parcelas", "/financiamentos/999999/parcelas"):
        resposta = client.get(f"{RAIZ}/{exemplo['simulacao']}{sufixo}", headers=alheio)
        assert resposta.status_code == 404 and resposta.get_json() == SIM_NAO_ENCONTRADA, sufixo


@pytest.mark.parametrize("opcao_id", [0, 999999, 2147483648, 99999999999999999999])
def test_parcelas_de_opcao_inexistente_ou_gigante_da_404(client, exemplo, opcao_id):
    resposta = client.get(f"{RAIZ}/{exemplo['simulacao']}/financiamentos/{opcao_id}/parcelas", headers=exemplo["cabecalho"])
    assert resposta.status_code == 404 and resposta.get_json() == OPCAO_NAO_ENCONTRADA


def test_parcelas_de_opcao_de_outra_simulacao_da_404(client, usuario, exemplo, corpo_simulacao, corpo_opcao):
    outra = nova_simulacao(client, usuario, corpo_simulacao, nome="Outra")
    da_outra = nova_opcao(client, usuario, outra, corpo_opcao)
    resposta = client.get(f"{RAIZ}/{exemplo['simulacao']}/financiamentos/{da_outra}/parcelas", headers=usuario.cabecalho)
    assert resposta.status_code == 404 and resposta.get_json() == OPCAO_NAO_ENCONTRADA


@pytest.mark.parametrize("sufixo", ["/resultado", "/financiamentos/1/parcelas"])
def test_401_sem_credencial_valida(client, credenciais_recusadas, sufixo):
    for descricao, cabecalhos, mensagem in credenciais_recusadas:
        resposta = client.get(f"{RAIZ}/1{sufixo}", headers=cabecalhos)
        assert resposta.status_code == 401 and resposta.get_json() == {"erro": mensagem}, descricao
        assert resposta.headers.get("WWW-Authenticate") == "Bearer", descricao
