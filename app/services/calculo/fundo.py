"""Fundo de acumulação: aportes mensais fixos rendendo a uma taxa anual.

Convenção (decisões 1 a 4 da spec da Etapa 6): taxa mensal composta equivalente,
aportes ao fim de cada mês, o `valor_entrada` da simulação entra como capital
inicial no mês 0; o saldo é calculado sem arredondar no meio (só na saída) e o
aporte necessário sobe ao centavo seguinte, para a meta ser sempre atingida.
"""
from dataclasses import dataclass
from decimal import Decimal

from app.services.calculo.base import (
    arredondar_moeda,
    arredondar_moeda_para_cima,
    contexto,
    exigir,
    para_decimal,
    para_inteiro,
    taxa_mensal_equivalente,
)
from app.services.calculo.preco import serie_preco_corrigido

ZERO = Decimal("0.00")
HORIZONTE_PADRAO = 60  # meses: o mesmo teto do prazo do fundo na API


@dataclass(frozen=True)
class ResultadoMeta:
    mes: int | None  # primeiro mês em que o saldo alcança o preço corrigido; None se não alcançar
    saldos: tuple  # do mês 0 até `mes` (ou até o horizonte), arredondados
    metas: tuple  # preço corrigido nos mesmos meses


@dataclass(frozen=True)
class SerieFundo:
    saldos: tuple  # do mês 0 (capital inicial) ao mês `prazo`, arredondados
    total_aportado: Decimal
    rendimento: Decimal
    saldo_final: Decimal


def _moeda(valor, nome, minimo=0):
    valor = para_decimal(valor, nome)
    exigir(valor >= minimo, f"{nome} não pode ser menor que {minimo}.")
    exigir(valor == arredondar_moeda(valor), f"{nome} deve ter no máximo 2 casas decimais.")
    return arredondar_moeda(valor)


def _taxa_mensal(taxa_aa):
    exigir(para_decimal(taxa_aa, "A taxa do fundo") >= 0, "A taxa do fundo não pode ser negativa.")
    return taxa_mensal_equivalente(taxa_aa, "A taxa do fundo")


def _saldos_exatos(capital, aporte, i, prazo):
    """saldo(0) = capital; saldo(m) = saldo(m−1)·(1+i) + aporte, sem arredondar."""
    with contexto():
        saldo = capital
        saldos = [saldo]
        for _ in range(prazo):
            saldo = saldo * (1 + i) + aporte
            saldos.append(saldo)
    return saldos


def serie_fundo(capital_inicial, aporte, taxa_aa, prazo):
    capital = _moeda(capital_inicial, "O capital inicial")
    aporte = _moeda(aporte, "O aporte")
    prazo = para_inteiro(prazo, "O prazo", 1)
    saldos = tuple(arredondar_moeda(s) for s in _saldos_exatos(capital, aporte, _taxa_mensal(taxa_aa), prazo))
    total_aportado = aporte * prazo
    return SerieFundo(
        saldos=saldos,
        total_aportado=total_aportado,
        rendimento=saldos[-1] - capital - total_aportado,
        saldo_final=saldos[-1],
    )


def aporte_para_meta(meta, capital_inicial, taxa_aa, prazo):
    """Menor aporte mensal (em centavos, para cima) que leva o capital à meta no prazo.

    Valor futuro: capital·(1+i)^n + aporte·((1+i)^n − 1)/i; com taxa 0, capital + aporte·n.
    Devolve 0,00 se o capital inicial já bastar.
    """
    meta = _moeda(meta, "A meta", minimo=Decimal("0.01"))
    capital = _moeda(capital_inicial, "O capital inicial")
    prazo = para_inteiro(prazo, "O prazo", 1)
    i = _taxa_mensal(taxa_aa)
    with contexto():
        crescimento = (1 + i) ** prazo
        falta = meta - capital * crescimento
        if falta <= 0:
            return ZERO
        fator = Decimal(prazo) if i == 0 else (crescimento - 1) / i
        return arredondar_moeda_para_cima(falta / fator)


def meses_para_meta(valor_veiculo, ipca_aa, capital_inicial, aporte, taxa_aa, horizonte=HORIZONTE_PADRAO):
    """Modo "dado o aporte": em que mês o fundo alcança o preço do carro daquele mês.

    A meta cresce com o IPCA enquanto o fundo cresce, então não há fórmula fechada:
    a busca é mês a mês até o horizonte.
    """
    capital = _moeda(capital_inicial, "O capital inicial")
    aporte = _moeda(aporte, "O aporte")
    horizonte = para_inteiro(horizonte, "O horizonte", 1)
    metas = serie_preco_corrigido(valor_veiculo, ipca_aa, horizonte)
    saldos = _saldos_exatos(capital, aporte, _taxa_mensal(taxa_aa), horizonte)
    for mes, (saldo, meta) in enumerate(zip(saldos, metas)):
        if saldo >= meta:
            fim = mes + 1
            return ResultadoMeta(mes, tuple(arredondar_moeda(s) for s in saldos[:fim]), metas[:fim])
    return ResultadoMeta(None, tuple(arredondar_moeda(s) for s in saldos), metas)
