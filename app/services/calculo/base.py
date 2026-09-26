"""Convenções numéricas comuns aos cálculos.

- Só `Decimal` (ou `int`): `float` é recusado para o erro de ponto flutuante não entrar.
- Contas em contexto local de 50 dígitos; o contexto global nunca é alterado.
- Valores em reais saem com 2 casas, arredondamento comercial (`ROUND_HALF_UP`).
"""
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal, localcontext

PRECISAO = 50
CENTAVO = Decimal("0.01")
MESES_NO_ANO = Decimal(12)


def contexto():
    """Contexto local de alta precisão para as contas intermediárias."""
    return localcontext(prec=PRECISAO)


def para_decimal(valor, nome):
    if isinstance(valor, bool) or not isinstance(valor, (Decimal, int)):
        raise TypeError(
            f"{nome} deve ser Decimal ou int, não {type(valor).__name__} "
            "(converta com Decimal(str(valor)))."
        )
    valor = Decimal(valor)
    if not valor.is_finite():
        raise ValueError(f"{nome} deve ser um número finito.")
    return valor


def para_inteiro(valor, nome, minimo):
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise TypeError(f"{nome} deve ser int, não {type(valor).__name__}.")
    if valor < minimo:
        raise ValueError(f"{nome} deve ser maior ou igual a {minimo}.")
    return valor


def exigir(condicao, mensagem):
    if not condicao:
        raise ValueError(mensagem)


def arredondar_moeda(valor):
    """2 casas, arredondamento comercial (2,005 → 2,01; o padrão do Decimal daria 2,00)."""
    with contexto():
        return valor.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def arredondar_moeda_para_cima(valor):
    """2 casas, sempre para cima (usado no aporte, para a meta ser atingida)."""
    with contexto():
        return valor.quantize(CENTAVO, rounding=ROUND_CEILING)


def percentual_para_fracao(percentual, nome="taxa"):
    """12.5 → 0.125. Único ponto de conversão de percentual para fração."""
    percentual = para_decimal(percentual, nome)
    with contexto():
        return percentual / 100


def taxa_mensal_equivalente(taxa_anual_percentual, nome="taxa anual"):
    """Taxa composta: (1 + a)^(1/12) − 1, como fração. Taxa 0 devolve 0 exato."""
    anual = percentual_para_fracao(taxa_anual_percentual, nome)
    exigir(anual > -1, f"{nome} deve ser maior que -100%.")
    if anual == 0:
        return Decimal(0)
    with contexto():
        return (1 + anual) ** (1 / MESES_NO_ANO) - 1
