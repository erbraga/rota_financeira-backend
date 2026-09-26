from decimal import Decimal

import pytest

from app.services.calculo.preco import preco_corrigido, serie_preco_corrigido

D = Decimal


@pytest.mark.parametrize("meses", [0, 1, 12, 36, 60])
def test_ipca_zero_mantem_o_preco(meses):
    assert preco_corrigido(D("95000"), D(0), meses) == D("95000.00")


def test_doze_meses_aplica_a_taxa_anual_inteira():
    # 95.000 × 1,045 = 99.275,00 (conta à mão).
    assert preco_corrigido(D("95000"), D("4.5"), 12) == D("99275.00")


def test_valor_conhecido_36_meses():
    # 95.000 × 1,045³ = 108.410,779375 → 108.410,78 (conta à mão: 1,045³ = 1,141166375).
    assert preco_corrigido(D("95000"), D("4.5"), 36) == D("108410.78")


def test_mes_zero_e_o_preco_de_hoje():
    assert preco_corrigido(D("95000"), D("4.5"), 0) == D("95000.00")


def test_meses_fracionarios_do_ano_usam_capitalizacao_composta():
    # 6 meses a 21% a.a.: (1,21)^(1/2) = 1,1 exato → 1.000 × 1,1 = 1.100,00.
    assert preco_corrigido(D("1000"), D(21), 6) == D("1100.00")


def test_ipca_negativo_reduz_o_preco():
    assert preco_corrigido(D("95000"), D("-3.2"), 36) < D("95000")
    # 12 meses a -20% → 80% do valor.
    assert preco_corrigido(D("95000"), D(-20), 12) == D("76000.00")


def test_extremo_da_api():
    # 9.999.999 × 2^(60/12) = 9.999.999 × 32.
    assert preco_corrigido(D("9999999.00"), D(100), 60) == D("319999968.00")


def test_serie_confere_com_o_calculo_mes_a_mes():
    serie = serie_preco_corrigido(D("95000"), D("4.5"), 36)
    assert len(serie) == 37
    assert serie[0] == D("95000.00")
    assert serie[12] == D("99275.00")
    assert serie[36] == D("108410.78")
    assert all(serie[m] == preco_corrigido(D("95000"), D("4.5"), m) for m in range(37))
    assert all(a < b for a, b in zip(serie, serie[1:]))  # IPCA positivo: sempre sobe
    assert all(v.as_tuple().exponent == -2 for v in serie)


@pytest.mark.parametrize(
    "args, erro",
    [
        ((D(0), D("4.5"), 12), ValueError),
        ((D(-1), D("4.5"), 12), ValueError),
        ((D("95000"), D("4.5"), -1), ValueError),
        ((D("95000"), D(-100), 12), ValueError),
        ((95000.0, D("4.5"), 12), TypeError),
        ((D("95000"), 4.5, 12), TypeError),
        ((D("95000"), D("4.5"), 12.0), TypeError),
    ],
)
def test_entradas_invalidas(args, erro):
    with pytest.raises(erro):
        preco_corrigido(*args)
