"""Fundo de acumulação.

Referência independente: valor futuro pela fórmula fechada, com a taxa mensal e as
potências recalculadas aqui em 80 dígitos (o módulo usa 50 dígitos e soma mês a mês).
"""
from decimal import Decimal, localcontext

import pytest

from app.services.calculo.fundo import aporte_para_meta, meses_para_meta, serie_fundo
from app.services.calculo.preco import preco_corrigido

D = Decimal


def valor_futuro_referencia(capital, aporte, taxa_aa, meses):
    with localcontext(prec=80):
        a = D(taxa_aa) / 100
        if a == 0:
            return D(capital) + D(aporte) * meses
        i = (1 + a) ** (D(1) / 12) - 1
        crescimento = (1 + i) ** meses
        return D(capital) * crescimento + D(aporte) * (crescimento - 1) / i


def centavos(valor):
    with localcontext(prec=80):
        return valor.quantize(D("0.01"), "ROUND_HALF_UP")


# --------------------------------------------------------------------- aporte


def test_aporte_sem_rendimento():
    # 12.000 em 12 meses a 0% → 1.000,00 por mês (conta à mão).
    assert aporte_para_meta(D("12000"), D(0), D(0), 12) == D("1000.00")


def test_aporte_sem_rendimento_arredonda_para_cima():
    # 1.000 / 3 = 333,333... → 333,34 (com 333,33 faltaria 0,01).
    assert aporte_para_meta(D("1000"), D(0), D(0), 3) == D("333.34")


@pytest.mark.parametrize(
    "capital, esperado",
    [
        # Exemplo da spec: meta 108.410,78 (95.000 a 4,5% em 36 meses), fundo a 10,5% a.a.
        (D(0), D("2593.66")),
        (D("20000"), D("1948.07")),
    ],
)
def test_aporte_exemplo_da_spec(capital, esperado):
    assert aporte_para_meta(D("108410.78"), capital, D("10.5"), 36) == esperado


@pytest.mark.parametrize("prazo", [1, 12, 36, 60])
@pytest.mark.parametrize("taxa", ["0", "0.5", "10.5", "100"])
@pytest.mark.parametrize("capital", ["0", "20000", "90000"])
@pytest.mark.parametrize("meta", ["0.01", "12000", "108410.78", "9999999.00"])
def test_aporte_e_o_menor_centavo_que_atinge_a_meta(meta, capital, taxa, prazo):
    aporte = aporte_para_meta(D(meta), D(capital), D(taxa), prazo)
    assert aporte >= 0 and aporte.as_tuple().exponent == -2
    assert valor_futuro_referencia(capital, aporte, taxa, prazo) >= D(meta)
    if aporte > 0:
        # Um centavo a menos não atinge a meta: o aporte é o menor possível.
        assert valor_futuro_referencia(capital, aporte - D("0.01"), taxa, prazo) < D(meta)


@pytest.mark.parametrize("capital", ["12000", "50000"])
def test_capital_que_ja_cobre_a_meta_da_aporte_zero(capital):
    assert aporte_para_meta(D("12000"), D(capital), D("10.5"), 12) == D("0.00")


def test_capital_que_rende_ate_a_meta_da_aporte_zero():
    # 10.000 a 21% a.a. por 12 meses = 12.100 ≥ 12.000.
    assert aporte_para_meta(D("12000"), D("10000"), D(21), 12) == D("0.00")


# ---------------------------------------------------------------------- série


@pytest.mark.parametrize("prazo", [1, 12, 60])
@pytest.mark.parametrize("taxa", ["0", "10.5", "100"])
@pytest.mark.parametrize("capital, aporte", [("0", "2593.66"), ("20000", "1948.07"), ("9999999.00", "9999999.00")])
def test_serie_confere_com_a_formula_fechada(capital, aporte, taxa, prazo):
    serie = serie_fundo(D(capital), D(aporte), D(taxa), prazo)
    assert len(serie.saldos) == prazo + 1
    assert serie.saldos[0] == D(capital)
    for mes, saldo in enumerate(serie.saldos):
        assert saldo == centavos(valor_futuro_referencia(capital, aporte, taxa, mes))
        assert saldo.as_tuple().exponent == -2
    assert serie.saldo_final == serie.saldos[-1]
    assert serie.total_aportado == D(aporte) * prazo
    assert serie.rendimento == serie.saldo_final - D(capital) - serie.total_aportado


def test_serie_do_exemplo_atinge_a_meta():
    serie = serie_fundo(D(0), D("2593.66"), D("10.5"), 36)
    assert serie.saldo_final >= D("108410.78")
    # Aporte no fim do mês: no mês 1 ainda não houve rendimento.
    assert serie.saldos[1] == D("2593.66")


def test_serie_sem_rendimento():
    serie = serie_fundo(D(0), D("1000"), D(0), 12)
    assert serie.saldos == tuple(D(1000 * m).quantize(D("0.01")) for m in range(13))
    assert serie.rendimento == 0


# ------------------------------------------------------------------ inválidos


@pytest.mark.parametrize(
    "args, erro",
    [
        ((D(0), D(0), D(0), 12), ValueError),  # meta zero
        ((D(1000), D(-1), D(0), 12), ValueError),  # capital negativo
        ((D(1000), D(0), D(-1), 12), ValueError),  # rendimento negativo
        ((D(1000), D(0), D(0), 0), ValueError),  # prazo zero
        ((D("1000.001"), D(0), D(0), 12), ValueError),
        ((1000.0, D(0), D(0), 12), TypeError),
        ((D(1000), D(0), 10.5, 12), TypeError),
    ],
)
def test_aporte_entradas_invalidas(args, erro):
    with pytest.raises(erro):
        aporte_para_meta(*args)


@pytest.mark.parametrize(
    "args, erro",
    [
        ((D(0), D(-1), D(0), 12), ValueError),
        ((D(0), D("1.001"), D(0), 12), ValueError),
        ((D(0), D(1), D(0), 0), ValueError),
        ((D(0), 1.5, D(0), 12), TypeError),
    ],
)
def test_serie_entradas_invalidas(args, erro):
    with pytest.raises(erro):
        serie_fundo(*args)


# ------------------------------------------------------------ meses para a meta


@pytest.mark.parametrize("prazo", [1, 12, 36, 60])
@pytest.mark.parametrize("ipca, taxa", [("0", "0"), ("4.5", "10.5"), ("4.5", "4.5"), ("-3", "8"), ("10", "4")])
@pytest.mark.parametrize("capital", ["0", "20000"])
def test_meses_para_meta_coerente_com_aporte_para_meta(capital, ipca, taxa, prazo):
    valor = D("95000")
    meta = preco_corrigido(valor, D(ipca), prazo)
    aporte = aporte_para_meta(meta, D(capital), D(taxa), prazo)
    resultado = meses_para_meta(valor, D(ipca), D(capital), aporte, D(taxa))
    # Com o aporte calculado para `prazo` meses, a meta é alcançada em no máximo `prazo` meses.
    assert resultado.mes is not None and resultado.mes <= prazo
    # Com um centavo a menos, não é alcançada até o prazo. Só vale quando o fundo rende pelo
    # menos o IPCA: aí, uma vez acima da meta, o saldo não fica mais para trás.
    if aporte > 0 and D(taxa) >= D(ipca):
        menor = meses_para_meta(valor, D(ipca), D(capital), aporte - D("0.01"), D(taxa))
        assert menor.mes is None or menor.mes > prazo


def test_meses_para_meta_series_e_tamanho():
    resultado = meses_para_meta(D("95000"), D("4.5"), D(0), D("2593.66"), D("10.5"))
    assert resultado.mes == 36
    assert len(resultado.saldos) == len(resultado.metas) == 37
    assert resultado.metas[0] == D("95000.00") and resultado.metas[36] == D("108410.78")
    assert resultado.saldos[36] >= resultado.metas[36]
    assert all(s < m for s, m in zip(resultado.saldos[:36], resultado.metas[:36]))
    assert resultado.saldos == serie_fundo(D(0), D("2593.66"), D("10.5"), 36).saldos


def test_capital_que_ja_cobre_o_preco_de_hoje_da_mes_zero():
    resultado = meses_para_meta(D("95000"), D("4.5"), D("95000"), D(0), D(0))
    assert resultado.mes == 0
    assert resultado.saldos == (D("95000.00"),) and resultado.metas == (D("95000.00"),)


@pytest.mark.parametrize(
    "capital, aporte, ipca, taxa",
    [
        ("0", "0", "4.5", "10.5"),  # nada guardado
        ("0", "100", "4.5", "10.5"),  # aporte baixo demais
        ("90000", "0", "10", "0"),  # capital parado com IPCA alto
    ],
)
def test_meta_inalcancavel_no_horizonte(capital, aporte, ipca, taxa):
    resultado = meses_para_meta(D("95000"), D(ipca), D(capital), D(aporte), D(taxa), horizonte=60)
    assert resultado.mes is None
    assert len(resultado.saldos) == len(resultado.metas) == 61


def test_ipca_negativo_alcanca_antes():
    com_ipca_zero = meses_para_meta(D("95000"), D(0), D(0), D("2000"), D("10.5"))
    com_deflacao = meses_para_meta(D("95000"), D(-5), D(0), D("2000"), D("10.5"))
    assert com_deflacao.mes < com_ipca_zero.mes


def test_horizonte_menor_limita_a_busca():
    assert meses_para_meta(D("95000"), D("4.5"), D(0), D("2593.66"), D("10.5"), horizonte=35).mes is None


@pytest.mark.parametrize(
    "kwargs, erro",
    [
        ({"horizonte": 0}, ValueError),
        ({"horizonte": 12.0}, TypeError),
        ({"aporte": D(-1)}, ValueError),
        ({"valor_veiculo": D(0)}, ValueError),
        ({"taxa_aa": D(-1)}, ValueError),
    ],
)
def test_meses_para_meta_entradas_invalidas(kwargs, erro):
    args = {"valor_veiculo": D("95000"), "ipca_aa": D("4.5"), "capital_inicial": D(0), "aporte": D("100"), "taxa_aa": D("10.5")}
    args.update(kwargs)
    with pytest.raises(erro):
        meses_para_meta(**args)
