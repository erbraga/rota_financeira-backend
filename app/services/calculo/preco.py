"""Preço à vista do veículo corrigido pelo IPCA."""
from app.services.calculo.base import (
    MESES_NO_ANO,
    arredondar_moeda,
    contexto,
    exigir,
    para_decimal,
    para_inteiro,
    percentual_para_fracao,
)


def _fator(ipca_aa, meses):
    """(1 + ipca)^(meses/12); IPCA em percentual ao ano (pode ser negativo)."""
    ipca = percentual_para_fracao(ipca_aa, "IPCA")
    exigir(ipca > -1, "O IPCA deve ser maior que -100%.")
    if ipca == 0 or meses == 0:
        return 1
    with contexto():
        return (1 + ipca) ** (meses / MESES_NO_ANO)


def _valor(valor_veiculo):
    valor = para_decimal(valor_veiculo, "O valor do veículo")
    exigir(valor > 0, "O valor do veículo deve ser positivo.")
    return valor


def preco_corrigido(valor_veiculo, ipca_aa, meses):
    """valor × (1 + ipca)^(meses/12), arredondado ao centavo."""
    valor = _valor(valor_veiculo)
    meses = para_inteiro(meses, "O número de meses", 0)
    with contexto():
        return arredondar_moeda(valor * _fator(ipca_aa, meses))


def serie_preco_corrigido(valor_veiculo, ipca_aa, prazo):
    """Preço corrigido do mês 0 (hoje) ao mês `prazo`: `prazo + 1` valores."""
    valor = _valor(valor_veiculo)
    prazo = para_inteiro(prazo, "O prazo", 0)
    with contexto():
        return tuple(arredondar_moeda(valor * _fator(ipca_aa, m)) for m in range(prazo + 1))
