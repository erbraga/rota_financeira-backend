"""Composição dos cenários (Etapa 7).

Os números de referência do exemplo vêm da spec da Etapa 7 e foram conferidos com os blocos
da Etapa 6 (testados com referência independente) e com a conta à mão.
"""
import time
from decimal import Decimal, getcontext

import pytest

from app.services.calculo.cenarios import (
    A_VISTA,
    FINANCIAMENTO,
    FUNDO,
    EntradaOpcao,
    EntradaSimulacao,
    financiamento_da_opcao,
    fundo_da_simulacao,
    montar_resultado,
)
from app.services.calculo.fundo import serie_fundo
from app.services.calculo.preco import serie_preco_corrigido

D = Decimal

OPCAO_A = EntradaOpcao(4, "Banco X 48x", "PRICE", D("1.99"), 48, D("20000"))
OPCAO_B = EntradaOpcao(5, "Banco Y 60x", "SAC", D("1.5"), 60, D("30000"))
SIMULACAO = EntradaSimulacao(D("95000"), D("20000"), D("4.5"), D("10.5"), 36)


def test_opcao_price_do_exemplo():
    f = financiamento_da_opcao(D("95000"), OPCAO_A)
    assert f.valor_financiado == D("75000")
    assert (f.primeira_parcela, f.ultima_parcela) == (D("2440.16"), D("2440.55"))
    assert f.total_pago == D("117128.07")
    assert f.total_juros == D("42128.07")
    assert f.custo_total == D("137128.07")  # entrada 20.000 + parcelas
    assert len(f.tabela.parcelas) == 48
    assert f.tabela.parcelas[0].juros == D("1492.50")
    assert f.tabela.parcelas[0].amortizacao == D("947.66")
    assert f.tabela.parcelas[0].saldo_devedor == D("74052.34")


def test_opcao_sac_do_exemplo():
    f = financiamento_da_opcao(D("95000"), OPCAO_B)
    assert f.valor_financiado == D("65000")
    assert (f.primeira_parcela, f.ultima_parcela) == (D("2058.33"), D("1099.78"))
    assert f.total_pago == D("94737.50")
    assert f.total_juros == D("29737.50")
    assert f.custo_total == D("124737.50")
    assert len(f.tabela.parcelas) == 60


def test_custo_total_e_entrada_mais_parcelas():
    for opcao in (OPCAO_A, OPCAO_B):
        f = financiamento_da_opcao(D("95000"), opcao)
        assert f.custo_total == opcao.valor_entrada + sum(p.valor_parcela for p in f.tabela.parcelas)
        assert f.total_juros == f.total_pago - f.valor_financiado


def test_entrada_zero_financia_o_valor_todo():
    f = financiamento_da_opcao(D("95000"), EntradaOpcao(1, "x", "PRICE", D(1), 12, D(0)))
    assert f.valor_financiado == D("95000")
    assert f.custo_total == f.total_pago


@pytest.mark.parametrize(
    "veiculo, opcao, erro",
    [
        (D("95000"), EntradaOpcao(1, "x", "PRICE", D(1), 12, D("95000")), ValueError),  # entrada = veículo
        (D("95000"), EntradaOpcao(1, "x", "PRICE", D(1), 12, D("95000.01")), ValueError),
        (D("95000"), EntradaOpcao(1, "x", "PRICE", D(1), 12, D(-1)), ValueError),
        (D("95000"), EntradaOpcao(1, "x", "SACRE", D(1), 12, D(0)), ValueError),
        (D("95000"), EntradaOpcao(1, "x", "PRICE", D(1), 0, D(0)), ValueError),
        (D(0), EntradaOpcao(1, "x", "PRICE", D(1), 12, D(0)), ValueError),
        (95000.0, EntradaOpcao(1, "x", "PRICE", D(1), 12, D(0)), TypeError),
        (D("95000"), EntradaOpcao(1, "x", "PRICE", 1.0, 12, D(0)), TypeError),
        (D("95000"), EntradaOpcao(1, "x", "PRICE", D(1), 12, 0.0), TypeError),
        (D("95000"), EntradaOpcao(1, "x", "PRICE", D(1), 12.0, D(0)), TypeError),
    ],
)
def test_opcao_entradas_invalidas(veiculo, opcao, erro):
    with pytest.raises(erro):
        financiamento_da_opcao(veiculo, opcao)


# ------------------------------------------------------------------------ fundo


def test_fundo_modo_normal_do_exemplo():
    f = fundo_da_simulacao(SIMULACAO)
    assert f.capital_inicial == D("20000.00")
    assert f.aporte_mensal == D("1948.07")
    assert f.prazo_meses == 36 and f.mes_da_meta == 36 and f.alcanca_a_meta
    assert f.preco_na_compra == D("108410.78") and f.custo_total == D("108410.78")
    assert f.total_aportado == D("70130.52")  # 36 × 1.948,07
    assert f.saldo_final == D("108410.97")
    assert f.rendimento == D("18280.45")  # 108.410,97 − 20.000 − 70.130,52
    assert len(f.saldos) == 37 and f.saldos[0] == D("20000.00") and f.saldos[-1] == f.saldo_final


def test_fundo_modo_normal_usa_a_entrada_como_capital_inicial():
    sem_capital = fundo_da_simulacao(EntradaSimulacao(D("95000"), D(0), D("4.5"), D("10.5"), 36))
    assert sem_capital.aporte_mensal == D("2593.66")  # sem capital inicial (exemplo da Etapa 6)
    assert sem_capital.saldos[0] == D("0.00")


def test_fundo_dado_o_aporte_alcanca_a_meta_no_mes_46():
    f = fundo_da_simulacao(SIMULACAO, D("1500"))
    assert f.mes_da_meta == 46 and f.alcanca_a_meta
    assert f.prazo_meses == 46  # o prazo da simulação (36) deixa de ser usado
    assert f.preco_na_compra == D("112461.20") and f.custo_total == D("112461.20")
    assert f.saldo_final == D("113040.26")
    assert f.total_aportado == D("69000.00")  # 1.500 × 46
    assert f.rendimento == D("24040.26")  # 113.040,26 − 20.000 − 69.000
    assert len(f.saldos) == 47


def test_fundo_dado_o_aporte_nao_alcanca_no_horizonte():
    f = fundo_da_simulacao(SIMULACAO, D("300"))
    assert f.mes_da_meta is None and not f.alcanca_a_meta
    assert f.preco_na_compra is None and f.custo_total is None
    esperado = serie_fundo(D("20000"), D("300"), D("10.5"), 60)  # valores do fim do horizonte
    assert f.prazo_meses == 60 and len(f.saldos) == 61
    assert (f.saldo_final, f.total_aportado, f.rendimento) == (esperado.saldo_final, esperado.total_aportado, esperado.rendimento)


def test_fundo_aporte_zero_sem_capital_suficiente_nao_alcanca_e_nao_da_erro():
    f = fundo_da_simulacao(SIMULACAO, D("0"))
    assert f.mes_da_meta is None and f.total_aportado == 0
    assert f.saldos[0] == D("20000.00")


def test_fundo_capital_que_ja_cobre_a_meta_da_aporte_zero():
    # IPCA −20% a.a.: em 12 meses o carro vale 76.000; 90.000 de capital sobram.
    simulacao = EntradaSimulacao(D("95000"), D("90000"), D(-20), D("10.5"), 12)
    f = fundo_da_simulacao(simulacao)
    assert f.preco_na_compra == D("76000.00")
    assert f.aporte_mensal == D("0.00") and f.total_aportado == D("0.00")
    assert f.alcanca_a_meta and f.saldo_final >= f.preco_na_compra


def test_fundo_capital_que_ja_cobre_o_preco_de_hoje_no_modo_aporte():
    simulacao = EntradaSimulacao(D("95000"), D("95000"), D("4.5"), D("10.5"), 36)
    f = fundo_da_simulacao(simulacao, D("100"))
    assert f.mes_da_meta == 0 and f.prazo_meses == 0
    assert f.saldos == (D("95000.00"),) and f.total_aportado == 0 and f.rendimento == 0
    assert f.custo_total == D("95000.00")


@pytest.mark.parametrize(
    "aporte, erro",
    [(D(-1), ValueError), (D("10.005"), ValueError), (10.0, TypeError), (D("NaN"), ValueError)],
)
def test_fundo_aporte_invalido(aporte, erro):
    with pytest.raises(erro):
        fundo_da_simulacao(SIMULACAO, aporte)


@pytest.mark.parametrize(
    "simulacao, erro",
    [
        (EntradaSimulacao(D("95000"), D("-1"), D("4.5"), D("10.5"), 36), ValueError),
        (EntradaSimulacao(D("95000"), D("20000"), D("4.5"), D("-1"), 36), ValueError),
        (EntradaSimulacao(D("95000"), D("20000"), D("4.5"), D("10.5"), 0), ValueError),
        (EntradaSimulacao(D("95000"), 20000.0, D("4.5"), D("10.5"), 36), TypeError),
        (EntradaSimulacao(D("95000"), D("20000"), D("4.5"), D("10.5"), 36.0), TypeError),
    ],
)
def test_fundo_simulacao_invalida(simulacao, erro):
    with pytest.raises(erro):
        fundo_da_simulacao(simulacao)


# ------------------------------------------------- resultado: séries, eixo e menor custo


def test_resultado_do_exemplo_series_e_eixo():
    r = montar_resultado(SIMULACAO, [OPCAO_A, OPCAO_B])
    assert r.a_vista_custo_total == D("95000.00")
    assert [f.opcao.id for f in r.financiamentos] == [4, 5]
    assert len(r.series) == 61  # eixo comum: do mês 0 ao maior prazo (60)
    assert [p.mes for p in r.series] == list(range(61))
    assert r.series[0].preco_corrigido == D("95000.00")
    assert r.series[36].preco_corrigido == D("108410.78")
    # Fundo: do mês 0 ao 36 e None depois (a compra é no mês 36).
    assert r.series[0].saldo_fundo == D("20000.00") and r.series[36].saldo_fundo == D("108410.97")
    assert r.series[37].saldo_fundo is None and r.series[60].saldo_fundo is None
    # Saldo devedor: valor financiado no mês 0, 0,00 no último mês da opção e None depois.
    assert r.series[0].saldo_devedor == {"4": D("75000"), "5": D("65000")}
    assert r.series[1].saldo_devedor["4"] == D("74052.34")
    assert r.series[48].saldo_devedor["4"] == D("0.00") and r.series[49].saldo_devedor["4"] is None
    assert r.series[60].saldo_devedor == {"4": None, "5": D("0.00")}
    assert r.menor_custo.cenario == A_VISTA and r.menor_custo.id is None


def test_pontos_coincidem_com_os_blocos():
    r = montar_resultado(SIMULACAO, [OPCAO_A, OPCAO_B])
    precos = serie_preco_corrigido(D("95000"), D("4.5"), 60)
    for f in r.financiamentos:
        for p in f.tabela.parcelas:
            assert r.series[p.numero].saldo_devedor[str(f.opcao.id)] == p.saldo_devedor
    assert all(p.preco_corrigido == precos[p.mes] for p in r.series)
    assert all(r.series[m].saldo_fundo == r.fundo.saldos[m] for m in range(37))
    assert all(list(p.saldo_devedor) == ["4", "5"] for p in r.series)  # chaves em texto, na ordem


def test_sem_opcoes_o_resultado_continua_valido():
    r = montar_resultado(SIMULACAO, [])
    assert r.financiamentos == ()
    assert len(r.series) == 37 and all(p.saldo_devedor == {} for p in r.series)
    assert r.menor_custo.cenario == A_VISTA


@pytest.mark.parametrize("prazo_opcao, prazo_fundo, eixo", [(72, 36, 72), (12, 60, 60), (36, 36, 36)])
def test_eixo_vai_ate_o_maior_prazo(prazo_opcao, prazo_fundo, eixo):
    simulacao = EntradaSimulacao(D("95000"), D("20000"), D("4.5"), D("10.5"), prazo_fundo)
    opcao = EntradaOpcao(1, "x", "PRICE", D("1.5"), prazo_opcao, D("20000"))
    r = montar_resultado(simulacao, [opcao])
    assert len(r.series) == eixo + 1
    assert r.series[-1].preco_corrigido == serie_preco_corrigido(D("95000"), D("4.5"), eixo)[-1]
    fundo_termina = prazo_fundo + 1
    assert all((p.saldo_fundo is None) == (p.mes >= fundo_termina) for p in r.series)
    assert all((p.saldo_devedor["1"] is None) == (p.mes > prazo_opcao) for p in r.series)


def test_modo_aporte_ajusta_o_eixo_ao_mes_da_meta():
    r = montar_resultado(SIMULACAO, [OPCAO_A], aporte_mensal=D("1500"))
    assert r.fundo.mes_da_meta == 46
    assert len(r.series) == 49  # eixo = max(46 do fundo, 48 da opção) + 1
    assert r.series[46].saldo_fundo == D("113040.26") and r.series[47].saldo_fundo is None
    r = montar_resultado(SIMULACAO, [], aporte_mensal=D("1500"))
    assert len(r.series) == 47


def test_modo_aporte_sem_alcancar_deixa_o_fundo_fora_do_menor_custo():
    # IPCA −20%: com o fundo válido ele seria o mais barato; sem alcançar a meta, sai da disputa.
    simulacao = EntradaSimulacao(D("95000"), D(0), D(-20), D("10.5"), 12)
    assert montar_resultado(simulacao, []).menor_custo.cenario == FUNDO
    r = montar_resultado(simulacao, [], aporte_mensal=D(0))
    assert r.fundo.custo_total is None
    assert r.menor_custo.cenario == A_VISTA
    assert len(r.series) == 61  # horizonte inteiro


def test_menor_custo_fundo_com_deflacao():
    simulacao = EntradaSimulacao(D("95000"), D("20000"), D(-20), D("10.5"), 12)
    r = montar_resultado(simulacao, [OPCAO_A])
    assert r.fundo.custo_total == D("76000.00") < r.a_vista_custo_total
    assert r.menor_custo.cenario == FUNDO


def test_menor_custo_empates_seguem_a_ordem_a_vista_financiamentos_fundo():
    # IPCA 0: preço corrigido = valor de hoje → fundo empata com o à vista.
    simulacao = EntradaSimulacao(D("95000"), D("20000"), D(0), D("10.5"), 12)
    r = montar_resultado(simulacao, [])
    assert r.fundo.custo_total == r.a_vista_custo_total == D("95000.00")
    assert r.menor_custo.cenario == A_VISTA
    # Financiamento sem juros custa exatamente o valor do veículo: empata com o à vista.
    sem_juros = EntradaOpcao(9, "sem juros", "PRICE", D(0), 12, D(0))
    r = montar_resultado(simulacao, [sem_juros])
    assert r.financiamentos[0].custo_total == r.a_vista_custo_total
    assert r.menor_custo.cenario == A_VISTA
    # Sem o à vista na disputa não há como o financiamento vencer com juros > 0 (custo maior).
    r = montar_resultado(SIMULACAO, [OPCAO_A, OPCAO_B])
    assert r.menor_custo.cenario != FINANCIAMENTO


def test_ids_de_opcoes_repetidos_sao_recusados():
    with pytest.raises(ValueError):
        montar_resultado(SIMULACAO, [OPCAO_A, OPCAO_A])


@pytest.mark.parametrize(
    "simulacao, erro",
    [
        (EntradaSimulacao(D(0), D(0), D(4), D(10), 12), ValueError),
        (EntradaSimulacao(95000.0, D(0), D(4), D(10), 12), TypeError),
    ],
)
def test_resultado_simulacao_invalida(simulacao, erro):
    with pytest.raises(erro):
        montar_resultado(simulacao, [])


def _pior_caso():
    simulacao = EntradaSimulacao(D("9999999.00"), D("1000000"), D(100), D(100), 60)
    opcoes = [
        EntradaOpcao(1, "a", "PRICE", D(20), 72, D("1000000")),
        EntradaOpcao(2, "b", "SAC", D(20), 72, D("1000000")),
        EntradaOpcao(3, "c", "PRICE", D(20), 72, D(0)),
    ]
    montar_resultado(simulacao, opcoes)
    montar_resultado(simulacao, opcoes, aporte_mensal=D("100000"))


def test_pior_caso_do_resultado_e_rapido_e_nao_altera_o_contexto():
    contexto = getcontext()
    antes = (contexto.prec, contexto.rounding, contexto.Emax, contexto.Emin, dict(contexto.traps))
    _pior_caso()  # aquece
    inicio = time.perf_counter()
    _pior_caso()
    assert time.perf_counter() - inicio < 0.1
    assert (contexto.prec, contexto.rounding, contexto.Emax, contexto.Emin, dict(contexto.traps)) == antes
