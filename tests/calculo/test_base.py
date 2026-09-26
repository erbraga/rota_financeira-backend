from decimal import Decimal, getcontext, localcontext

import pytest

from app.services.calculo.base import (
    arredondar_moeda,
    arredondar_moeda_para_cima,
    para_decimal,
    para_inteiro,
    percentual_para_fracao,
    taxa_mensal_equivalente,
)

D = Decimal


@pytest.mark.parametrize(
    "valor, esperado",
    [
        # 2,005 e 2,025 separam o arredondamento comercial do "do banqueiro" (padrão do Decimal).
        ("2.005", "2.01"),
        ("2.025", "2.03"),
        ("2.004", "2.00"),
        ("-2.005", "-2.01"),
        ("2440.164810", "2440.16"),
        ("10", "10.00"),
    ],
)
def test_arredondar_moeda_comercial(valor, esperado):
    resultado = arredondar_moeda(D(valor))
    assert resultado == D(esperado)
    assert resultado.as_tuple().exponent == -2


@pytest.mark.parametrize(
    "valor, esperado",
    [("2593.6550", "2593.66"), ("2593.66", "2593.66"), ("2593.6601", "2593.67"), ("0", "0.00")],
)
def test_arredondar_para_cima(valor, esperado):
    assert arredondar_moeda_para_cima(D(valor)) == D(esperado)


def test_percentual_para_fracao():
    assert percentual_para_fracao(D("12.5")) == D("0.125")
    assert percentual_para_fracao(0) == 0


def test_taxa_mensal_composta_recompoe_a_anual():
    # Referência independente: elevar a taxa mensal a 12 tem de devolver a anual.
    for anual in ("10.5", "12", "100", "0.5", "-3.2"):
        mensal = taxa_mensal_equivalente(D(anual))
        with localcontext(prec=60):  # a conta de referência precisa de mais dígitos que a testada
            recomposta = (1 + mensal) ** 12 - 1
            assert abs(recomposta - D(anual) / 100) < D("1e-40"), anual


def test_taxa_mensal_de_12_por_cento_ao_ano():
    mensal_percentual = taxa_mensal_equivalente(D(12)) * 100
    assert mensal_percentual.quantize(D("0.0000001")) == D("0.9488793")
    # A composta é menor que a simples (12 / 12 = 1% a.m.).
    assert mensal_percentual < 1


def test_taxa_zero_nao_gera_expoente_estranho():
    mensal = taxa_mensal_equivalente(D(0))
    assert mensal == 0
    assert mensal.as_tuple().exponent == 0  # nada de 0E-49


@pytest.mark.parametrize("invalido", [1.5, "12", None, True])
def test_para_decimal_recusa_tipos_invalidos(invalido):
    with pytest.raises(TypeError):
        para_decimal(invalido, "valor")


def test_para_decimal_aceita_int_e_recusa_infinito():
    assert para_decimal(7, "valor") == D(7)
    with pytest.raises(ValueError):
        para_decimal(D("Infinity"), "valor")
    with pytest.raises(ValueError):
        para_decimal(D("NaN"), "valor")


def test_para_inteiro():
    assert para_inteiro(12, "prazo", 1) == 12
    with pytest.raises(ValueError):
        para_inteiro(0, "prazo", 1)
    for invalido in (12.0, D(12), True):
        with pytest.raises(TypeError):
            para_inteiro(invalido, "prazo", 1)


def test_taxa_de_menos_100_por_cento_recusada():
    with pytest.raises(ValueError):
        taxa_mensal_equivalente(D(-100))


def test_contexto_global_nao_muda():
    antes = (getcontext().prec, getcontext().rounding)
    taxa_mensal_equivalente(D("10.5"))
    arredondar_moeda(D("1.005"))
    arredondar_moeda_para_cima(D("1.001"))
    assert (getcontext().prec, getcontext().rounding) == antes
