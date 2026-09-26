"""Tabelas Price e SAC.

Referência independente: a tabela é refeita aqui com `fractions.Fraction` e centavos
inteiros (outro caminho aritmético, sem `Decimal`), aplicando a mesma convenção da
spec: juros arredondados por mês (meio para cima), última parcela com o resíduo e
amortização limitada ao saldo.
"""
from decimal import Decimal
from fractions import Fraction

import pytest

from app.services.calculo.financiamento import (
    PRICE,
    SAC,
    custo_total_financiamento,
    tabela_price,
    tabela_sac,
)

D = Decimal


def _centavos(fracao):
    """Arredonda uma fração não negativa de reais para centavos inteiros (meio para cima)."""
    return int(fracao * 100 + Fraction(1, 2))


def referencia_price(valor, taxa_percentual, prazo):
    pv = int(Fraction(valor) * 100)  # centavos
    i = Fraction(taxa_percentual) / 100
    if i == 0:
        parcela = _centavos(Fraction(pv, 100) / prazo)
    else:
        parcela = _centavos(Fraction(pv, 100) * i / (1 - (1 + i) ** -prazo))
    saldo, linhas = pv, []
    for numero in range(1, prazo + 1):
        juros = _centavos(Fraction(saldo, 100) * i)
        amortizacao = saldo if numero == prazo else min(parcela - juros, saldo)
        saldo -= amortizacao
        linhas.append((numero, juros + amortizacao, juros, amortizacao, saldo))
    return parcela, linhas


def referencia_sac(valor, taxa_percentual, prazo):
    pv = int(Fraction(valor) * 100)
    i = Fraction(taxa_percentual) / 100
    amortizacao_base = _centavos(Fraction(pv, 100) / prazo)
    saldo, linhas = pv, []
    for numero in range(1, prazo + 1):
        juros = _centavos(Fraction(saldo, 100) * i)
        amortizacao = saldo if numero == prazo else min(amortizacao_base, saldo)
        saldo -= amortizacao
        linhas.append((numero, juros + amortizacao, juros, amortizacao, saldo))
    return amortizacao_base, linhas


def em_centavos(tabela):
    return [
        (p.numero, int(p.valor_parcela * 100), int(p.juros * 100), int(p.amortizacao * 100), int(p.saldo_devedor * 100))
        for p in tabela.parcelas
    ]


def conferir_propriedades(tabela, valor, taxa):
    parcelas = tabela.parcelas
    i = D(taxa) / 100
    assert len(parcelas) == tabela.prazo
    assert [p.numero for p in parcelas] == list(range(1, tabela.prazo + 1))
    assert sum(p.amortizacao for p in parcelas) == D(valor)
    assert parcelas[-1].saldo_devedor == 0
    saldo_anterior = D(valor)
    for p in parcelas:
        assert p.saldo_devedor >= 0 and p.amortizacao >= 0 and p.juros >= 0
        assert p.juros == (saldo_anterior * i).quantize(D("0.01"), "ROUND_HALF_UP")
        assert p.valor_parcela == p.juros + p.amortizacao
        assert p.saldo_devedor == saldo_anterior - p.amortizacao
        for campo in (p.valor_parcela, p.juros, p.amortizacao, p.saldo_devedor):
            assert campo.as_tuple().exponent == -2
        saldo_anterior = p.saldo_devedor
    assert tabela.total_pago == sum(p.valor_parcela for p in parcelas)
    assert tabela.total_juros == tabela.total_pago - D(valor)


VALORES = ["0.01", "1000", "75000", "9999999.00"]
TAXAS = ["0", "0.5", "1.99", "20"]
PRAZOS = [1, 12, 48, 72]


@pytest.mark.parametrize("prazo", PRAZOS)
@pytest.mark.parametrize("taxa", TAXAS)
@pytest.mark.parametrize("valor", VALORES)
def test_price_propriedades_e_referencia(valor, taxa, prazo):
    tabela = tabela_price(D(valor), D(taxa), prazo)
    assert tabela.sistema == PRICE
    conferir_propriedades(tabela, valor, taxa)
    parcela, linhas = referencia_price(D(valor), D(taxa), prazo)
    assert em_centavos(tabela) == linhas
    # Parcelas fixas: iguais até a quitação (exceto a última), 0,00 depois dela.
    quitada = next(p.numero for p in tabela.parcelas if p.saldo_devedor == 0)
    for p in tabela.parcelas:
        if p.numero < quitada and p.numero < prazo:
            assert int(p.valor_parcela * 100) == parcela
        elif p.numero > quitada:
            assert p.valor_parcela == 0


def test_price_valor_conhecido():
    # 100.000 a 1% a.m. em 12 meses: parcela 8.884,88 (tabela financeira de referência).
    tabela = tabela_price(D("100000"), D("1"), 12)
    assert tabela.parcelas[0].valor_parcela == D("8884.88")
    assert tabela.parcelas[0].juros == D("1000.00")
    assert tabela.parcelas[0].amortizacao == D("7884.88")
    assert tabela.parcelas[0].saldo_devedor == D("92115.12")


def test_price_ultima_parcela_absorve_o_residuo():
    # Exemplo da spec: parcela exata 2.440,164810 → 2.440,16; a última fecha o saldo.
    tabela = tabela_price(D("75000"), D("1.99"), 48)
    assert {p.valor_parcela for p in tabela.parcelas[:-1]} == {D("2440.16")}
    assert tabela.parcelas[-1].valor_parcela == D("2440.55")
    assert tabela.total_pago == D("117128.07")


def test_price_taxa_zero():
    tabela = tabela_price(D("1000"), D(0), 3)
    assert [p.valor_parcela for p in tabela.parcelas] == [D("333.33"), D("333.33"), D("333.34")]
    assert tabela.total_juros == 0


def test_price_prazo_um():
    tabela = tabela_price(D("1000"), D(2), 1)
    (p,) = tabela.parcelas
    assert (p.valor_parcela, p.juros, p.amortizacao, p.saldo_devedor) == (D("1020.00"), D("20.00"), D("1000.00"), D("0.00"))


@pytest.mark.parametrize(
    "valor, taxa, prazo, mes_quitacao",
    [
        # Decisão 8: sem a trava, o saldo ficaria negativo (verificado na implementação).
        ("0.36", "0", 72, 36),
        ("2000", "20", 60, 59),
    ],
)
def test_price_quitacao_antecipada_por_arredondamento(valor, taxa, prazo, mes_quitacao):
    tabela = tabela_price(D(valor), D(taxa), prazo)
    conferir_propriedades(tabela, valor, taxa)
    quitada = next(p.numero for p in tabela.parcelas if p.saldo_devedor == 0)
    assert quitada == mes_quitacao
    assert all(p.valor_parcela == 0 for p in tabela.parcelas[quitada:])


@pytest.mark.parametrize(
    "args, erro",
    [
        ((D(0), D(1), 12), ValueError),
        ((D(-10), D(1), 12), ValueError),
        ((D("10.005"), D(1), 12), ValueError),
        ((D(1000), D(-1), 12), ValueError),
        ((D(1000), D(1), 0), ValueError),
        ((1000.0, D(1), 12), TypeError),
        ((D(1000), 1.0, 12), TypeError),
        ((D(1000), D(1), 12.0), TypeError),
    ],
)
def test_price_entradas_invalidas(args, erro):
    with pytest.raises(erro):
        tabela_price(*args)


# ----------------------------------------------------------------------------- SAC


@pytest.mark.parametrize("prazo", PRAZOS)
@pytest.mark.parametrize("taxa", TAXAS)
@pytest.mark.parametrize("valor", VALORES)
def test_sac_propriedades_e_referencia(valor, taxa, prazo):
    tabela = tabela_sac(D(valor), D(taxa), prazo)
    assert tabela.sistema == SAC
    conferir_propriedades(tabela, valor, taxa)
    amortizacao_base, linhas = referencia_sac(D(valor), D(taxa), prazo)
    assert em_centavos(tabela) == linhas
    parcelas = [p.valor_parcela for p in tabela.parcelas]
    # Não crescentes até a penúltima; a última só passa da anterior pelo resíduo.
    assert all(a >= b for a, b in zip(parcelas[:-1], parcelas[1:-1]))
    if prazo > 1:
        residuo = abs(D(valor) - D(amortizacao_base * prazo) / 100)
        assert parcelas[-1] - parcelas[-2] <= residuo


def test_sac_valores_conhecidos():
    # 12.000 a 1% a.m. em 12 meses (conta à mão): amortização 1.000,00;
    # 1ª parcela 1.000 + 120 = 1.120,00; última 1.000 + 10 = 1.010,00.
    tabela = tabela_sac(D("12000"), D("1"), 12)
    assert {p.amortizacao for p in tabela.parcelas} == {D("1000.00")}
    assert tabela.parcelas[0].valor_parcela == D("1120.00")
    assert tabela.parcelas[-1].valor_parcela == D("1010.00")
    # Juros totais = 1% × (12.000 + 11.000 + ... + 1.000) = 780,00.
    assert tabela.total_juros == D("780.00")


def test_sac_taxa_zero():
    tabela = tabela_sac(D("1000"), D(0), 3)
    assert [p.valor_parcela for p in tabela.parcelas] == [D("333.33"), D("333.33"), D("333.34")]


def test_sac_quitacao_antecipada_por_arredondamento():
    # 0,36 / 72 = 0,005 → 0,01 por mês: quitado no mês 36 (decisão 8).
    tabela = tabela_sac(D("0.36"), D(0), 72)
    conferir_propriedades(tabela, "0.36", "0")
    quitada = next(p.numero for p in tabela.parcelas if p.saldo_devedor == 0)
    assert quitada == 36
    assert all(p.valor_parcela == 0 for p in tabela.parcelas[quitada:])


@pytest.mark.parametrize("prazo", [12, 48, 72])
@pytest.mark.parametrize("taxa", ["0.5", "1.99", "20"])
@pytest.mark.parametrize("valor", ["1000", "75000", "9999999.00"])
def test_sac_paga_menos_juros_que_price(valor, taxa, prazo):
    # Propriedade conhecida: com a mesma taxa e prazo, o SAC amortiza mais cedo e paga menos juros.
    assert tabela_sac(D(valor), D(taxa), prazo).total_juros < tabela_price(D(valor), D(taxa), prazo).total_juros


# ---------------------------------------------------------------------- custo total


def test_custo_total():
    tabela = tabela_price(D("75000"), D("1.99"), 48)
    assert custo_total_financiamento(D("20000"), tabela) == D("137128.07")
    assert custo_total_financiamento(0, tabela) == tabela.total_pago


@pytest.mark.parametrize("entrada, erro", [(D(-1), ValueError), (D("1.001"), ValueError), (10.0, TypeError)])
def test_custo_total_entrada_invalida(entrada, erro):
    with pytest.raises(erro):
        custo_total_financiamento(entrada, tabela_sac(D("1000"), D(1), 12))
