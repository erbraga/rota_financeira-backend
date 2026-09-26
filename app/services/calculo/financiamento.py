"""Tabelas de amortização (Price e SAC) e custo total do financiamento.

Convenção (decisões 1 e 8 da spec da Etapa 6): parcela e juros arredondados ao
centavo a cada mês (`ROUND_HALF_UP`), a última parcela absorve o resíduo e a
amortização de um mês nunca passa do saldo restante. Primeira parcela um mês após
a compra, sem carência. Taxa em percentual ao mês (1.99 = 1,99% a.m.).
"""
from dataclasses import dataclass
from decimal import Decimal

from app.services.calculo.base import (
    arredondar_moeda,
    contexto,
    exigir,
    para_decimal,
    para_inteiro,
    percentual_para_fracao,
)

PRICE = "PRICE"
SAC = "SAC"
ZERO = Decimal("0.00")


@dataclass(frozen=True)
class Parcela:
    numero: int
    valor_parcela: Decimal
    juros: Decimal
    amortizacao: Decimal
    saldo_devedor: Decimal  # saldo após o pagamento desta parcela


@dataclass(frozen=True)
class TabelaAmortizacao:
    sistema: str
    valor_financiado: Decimal
    taxa_juros_mensal: Decimal  # percentual ao mês, como recebido
    prazo: int
    parcelas: tuple
    total_pago: Decimal
    total_juros: Decimal


def _validar(valor_financiado, taxa_mensal_percentual, prazo):
    valor = para_decimal(valor_financiado, "O valor financiado")
    exigir(valor > 0, "O valor financiado deve ser positivo.")
    exigir(
        valor == arredondar_moeda(valor),
        "O valor financiado deve ter no máximo 2 casas decimais.",
    )
    taxa = para_decimal(taxa_mensal_percentual, "A taxa de juros mensal")
    exigir(taxa >= 0, "A taxa de juros mensal não pode ser negativa.")
    prazo = para_inteiro(prazo, "O prazo", 1)
    return arredondar_moeda(valor), taxa, prazo


def _montar(sistema, valor, taxa, prazo, amortizacao_do_mes):
    """Percorre os meses: juros sobre o saldo, amortização pela regra do sistema.

    A amortização nunca passa do saldo (o meio centavo do arredondamento, somado
    mês a mês com juros, poderia quitar o financiamento antes do fim); a última
    parcela quita o que restar.
    """
    i = percentual_para_fracao(taxa)
    saldo = valor
    parcelas = []
    with contexto():
        for numero in range(1, prazo + 1):
            juros = arredondar_moeda(saldo * i)
            if numero == prazo:
                amortizacao = saldo
            else:
                amortizacao = min(amortizacao_do_mes(juros), saldo)
            saldo -= amortizacao
            parcelas.append(Parcela(numero, juros + amortizacao, juros, amortizacao, saldo))
        total_pago = sum((p.valor_parcela for p in parcelas), ZERO)
    return TabelaAmortizacao(
        sistema=sistema,
        valor_financiado=valor,
        taxa_juros_mensal=taxa,
        prazo=prazo,
        parcelas=tuple(parcelas),
        total_pago=total_pago,
        total_juros=total_pago - valor,
    )


def tabela_price(valor_financiado, taxa_mensal_percentual, prazo):
    """Parcelas fixas: PMT = PV·i / (1 − (1+i)^−n); com taxa 0, PV / n."""
    valor, taxa, prazo = _validar(valor_financiado, taxa_mensal_percentual, prazo)
    i = percentual_para_fracao(taxa)
    with contexto():
        exata = valor / prazo if i == 0 else valor * i / (1 - (1 + i) ** -prazo)
        parcela = arredondar_moeda(exata)
    return _montar(PRICE, valor, taxa, prazo, lambda juros: parcela - juros)


def tabela_sac(valor_financiado, taxa_mensal_percentual, prazo):
    """Amortização constante PV / n (arredondada); juros sobre o saldo; parcelas decrescentes."""
    valor, taxa, prazo = _validar(valor_financiado, taxa_mensal_percentual, prazo)
    with contexto():
        amortizacao = arredondar_moeda(valor / prazo)
    return _montar(SAC, valor, taxa, prazo, lambda juros: amortizacao)


def custo_total_financiamento(entrada, tabela):
    """Entrada da opção + soma das parcelas."""
    entrada = para_decimal(entrada, "A entrada")
    exigir(entrada >= 0, "A entrada não pode ser negativa.")
    exigir(entrada == arredondar_moeda(entrada), "A entrada deve ter no máximo 2 casas decimais.")
    return arredondar_moeda(entrada) + tabela.total_pago
