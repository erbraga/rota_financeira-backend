"""Composição dos três cenários (à vista, financiamento e fundo) e das séries mês a mês.

Puro, como o resto do pacote: só biblioteca padrão e `app.services.calculo`. A leitura do
banco e a conversão de tipos ficam em `app/services/resultados.py`.

Custo total de cada cenário (decisão 1 da spec da Etapa 7): o que se **paga pelo carro** —
à vista = valor do veículo; financiamento = entrada da opção + soma das parcelas; fundo =
preço corrigido na compra. A comparação é nominal (sem valor presente).
"""
from dataclasses import dataclass
from decimal import Decimal

from app.services.calculo.base import arredondar_moeda, exigir, para_decimal, para_inteiro
from app.services.calculo.financiamento import (
    PRICE,
    SAC,
    TabelaAmortizacao,
    custo_total_financiamento,
    tabela_price,
    tabela_sac,
)
from app.services.calculo.fundo import (
    HORIZONTE_PADRAO,
    aporte_para_meta,
    meses_para_meta,
    serie_fundo,
)
from app.services.calculo.preco import preco_corrigido, serie_preco_corrigido


@dataclass(frozen=True)
class EntradaSimulacao:
    valor_veiculo: Decimal
    valor_entrada: Decimal  # capital inicial do fundo
    ipca_aa: Decimal  # % a.a.
    taxa_fundo_aa: Decimal  # % a.a.
    prazo_fundo: int  # meses


@dataclass(frozen=True)
class EntradaOpcao:
    id: int
    nome: str
    sistema: str  # PRICE ou SAC
    taxa_juros_mensal: Decimal  # % a.m.
    prazo_meses: int
    valor_entrada: Decimal


@dataclass(frozen=True)
class FinanciamentoCalculado:
    opcao: EntradaOpcao
    valor_financiado: Decimal
    tabela: TabelaAmortizacao
    primeira_parcela: Decimal
    ultima_parcela: Decimal
    total_pago: Decimal
    total_juros: Decimal
    custo_total: Decimal


def financiamento_da_opcao(valor_veiculo, opcao):
    """Tabela e totais de uma opção: valor financiado = veículo − entrada da opção (> 0)."""
    veiculo = para_decimal(valor_veiculo, "O valor do veículo")
    exigir(veiculo > 0, "O valor do veículo deve ser positivo.")
    entrada = para_decimal(opcao.valor_entrada, "A entrada da opção")
    exigir(entrada >= 0, "A entrada da opção não pode ser negativa.")
    exigir(entrada < veiculo, "A entrada da opção deve ser menor que o valor do veículo.")
    exigir(opcao.sistema in (PRICE, SAC), f"Sistema de amortização inválido: {opcao.sistema!r}.")
    prazo = para_inteiro(opcao.prazo_meses, "O prazo da opção", 1)
    valor_financiado = veiculo - entrada
    montar = tabela_price if opcao.sistema == PRICE else tabela_sac
    tabela = montar(valor_financiado, opcao.taxa_juros_mensal, prazo)
    return FinanciamentoCalculado(
        opcao=opcao,
        valor_financiado=valor_financiado,
        tabela=tabela,
        primeira_parcela=tabela.parcelas[0].valor_parcela,
        ultima_parcela=tabela.parcelas[-1].valor_parcela,
        total_pago=tabela.total_pago,
        total_juros=tabela.total_juros,
        custo_total=custo_total_financiamento(entrada, tabela),
    )


@dataclass(frozen=True)
class FundoCalculado:
    capital_inicial: Decimal
    aporte_mensal: Decimal
    prazo_meses: int  # meses simulados: o prazo da simulação, ou o mês da meta (ou o horizonte)
    mes_da_meta: int | None
    alcanca_a_meta: bool
    preco_na_compra: Decimal | None
    total_aportado: Decimal
    rendimento: Decimal
    saldo_final: Decimal
    custo_total: Decimal | None  # preço corrigido na compra; None se a meta não for alcançada
    saldos: tuple  # do mês 0 ao último mês simulado


def fundo_da_simulacao(simulacao, aporte_mensal=None):
    """Cenário do fundo, em um de dois modos.

    - Sem `aporte_mensal`: calcula o aporte que leva o capital inicial (`valor_entrada` da
      simulação) ao preço corrigido em `prazo_fundo` meses.
    - Com `aporte_mensal`: o aporte informado substitui o calculado e o `prazo_fundo` deixa de
      ser usado; busca o mês em que o saldo alcança o preço corrigido daquele mês (horizonte
      de 60 meses). Se não alcançar: mês, preço e custo `None`, e saldo/aportes/rendimento
      do fim do horizonte.
    """
    capital = para_decimal(simulacao.valor_entrada, "O capital inicial")
    if aporte_mensal is not None:
        return _fundo_dado_o_aporte(simulacao, capital, aporte_mensal)
    prazo = para_inteiro(simulacao.prazo_fundo, "O prazo do fundo", 1)
    meta = preco_corrigido(simulacao.valor_veiculo, simulacao.ipca_aa, prazo)
    aporte = aporte_para_meta(meta, capital, simulacao.taxa_fundo_aa, prazo)
    serie = serie_fundo(capital, aporte, simulacao.taxa_fundo_aa, prazo)
    return FundoCalculado(
        capital_inicial=arredondar_moeda(capital),
        aporte_mensal=aporte,
        prazo_meses=prazo,
        mes_da_meta=prazo,
        alcanca_a_meta=serie.saldo_final >= meta,
        preco_na_compra=meta,
        total_aportado=serie.total_aportado,
        rendimento=serie.rendimento,
        saldo_final=serie.saldo_final,
        custo_total=meta,
        saldos=serie.saldos,
    )


def _fundo_dado_o_aporte(simulacao, capital, aporte_mensal):
    aporte = para_decimal(aporte_mensal, "O aporte mensal")
    exigir(aporte >= 0, "O aporte mensal não pode ser negativo.")
    exigir(aporte == arredondar_moeda(aporte), "O aporte mensal deve ter no máximo 2 casas decimais.")
    resultado = meses_para_meta(
        simulacao.valor_veiculo,
        simulacao.ipca_aa,
        capital,
        aporte,
        simulacao.taxa_fundo_aa,
        HORIZONTE_PADRAO,
    )
    meses = len(resultado.saldos) - 1  # até a meta, ou até o horizonte
    capital = arredondar_moeda(capital)
    saldo_final = resultado.saldos[-1]
    total_aportado = arredondar_moeda(aporte) * meses
    alcanca = resultado.mes is not None
    preco = resultado.metas[resultado.mes] if alcanca else None
    return FundoCalculado(
        capital_inicial=capital,
        aporte_mensal=arredondar_moeda(aporte),
        prazo_meses=meses,
        mes_da_meta=resultado.mes,
        alcanca_a_meta=alcanca,
        preco_na_compra=preco,
        total_aportado=total_aportado,
        rendimento=saldo_final - capital - total_aportado,
        saldo_final=saldo_final,
        custo_total=preco,
        saldos=resultado.saldos,
    )


A_VISTA = "a_vista"
FINANCIAMENTO = "financiamento"
FUNDO = "fundo"


@dataclass(frozen=True)
class MenorCusto:
    cenario: str  # A_VISTA, FINANCIAMENTO ou FUNDO
    id: int | None  # id da opção, quando o cenário é um financiamento


@dataclass(frozen=True)
class PontoSerie:
    mes: int
    preco_corrigido: Decimal
    saldo_fundo: Decimal | None  # None depois da compra
    saldo_devedor: dict  # {"<id da opção>": saldo ou None depois da quitação}


@dataclass(frozen=True)
class Resultado:
    simulacao: EntradaSimulacao
    a_vista_custo_total: Decimal
    financiamentos: tuple
    fundo: FundoCalculado
    menor_custo: MenorCusto
    series: tuple


def _saldo_devedor(financiamento, mes):
    """Valor financiado no mês 0; saldo após a parcela do mês até a quitação; None depois."""
    if mes == 0:
        return financiamento.valor_financiado
    if mes <= financiamento.tabela.prazo:
        return financiamento.tabela.parcelas[mes - 1].saldo_devedor
    return None


def _menor_custo(custo_a_vista, financiamentos, fundo):
    """Menor `custo_total`; em empate vale a ordem à vista, financiamentos e fundo."""
    candidatos = [(custo_a_vista, MenorCusto(A_VISTA, None))]
    candidatos += [(f.custo_total, MenorCusto(FINANCIAMENTO, f.opcao.id)) for f in financiamentos]
    if fundo.custo_total is not None:
        candidatos.append((fundo.custo_total, MenorCusto(FUNDO, None)))
    melhor = min(range(len(candidatos)), key=lambda i: (candidatos[i][0], i))
    return candidatos[melhor][1]


def montar_resultado(simulacao, opcoes, aporte_mensal=None):
    """Os três cenários, o de menor custo e a lista de pontos mês a mês (eixo comum).

    O eixo vai do mês 0 ao maior prazo envolvido (fundo ou opções); o preço corrigido cobre
    todo o eixo e as demais séries são `None` depois que terminam.
    """
    veiculo = para_decimal(simulacao.valor_veiculo, "O valor do veículo")
    exigir(veiculo > 0, "O valor do veículo deve ser positivo.")
    opcoes = tuple(opcoes)
    exigir(len({o.id for o in opcoes}) == len(opcoes), "As opções devem ter ids diferentes.")
    financiamentos = tuple(financiamento_da_opcao(veiculo, o) for o in opcoes)
    fundo = fundo_da_simulacao(simulacao, aporte_mensal)

    eixo = max([len(fundo.saldos) - 1] + [f.tabela.prazo for f in financiamentos])
    precos = serie_preco_corrigido(veiculo, simulacao.ipca_aa, eixo)
    series = tuple(
        PontoSerie(
            mes=mes,
            preco_corrigido=precos[mes],
            saldo_fundo=fundo.saldos[mes] if mes < len(fundo.saldos) else None,
            saldo_devedor={str(f.opcao.id): _saldo_devedor(f, mes) for f in financiamentos},
        )
        for mes in range(eixo + 1)
    )
    custo_a_vista = arredondar_moeda(veiculo)
    return Resultado(
        simulacao=simulacao,
        a_vista_custo_total=custo_a_vista,
        financiamentos=financiamentos,
        fundo=fundo,
        menor_custo=_menor_custo(custo_a_vista, financiamentos, fundo),
        series=series,
    )
