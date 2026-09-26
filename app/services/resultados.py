"""Adaptador entre o banco e a composição pura dos cenários (`calculo.cenarios`).

Só leitura: nada é gravado nem bloqueado, e o resultado reflete sempre o estado atual da
simulação e das opções. Os `Decimal` do banco entram no cálculo direto, sem passar por `float`.
"""
from app.services.calculo.cenarios import (
    EntradaOpcao,
    EntradaSimulacao,
    financiamento_da_opcao,
    montar_resultado,
)
from app.services.financiamentos import listar_opcoes, obter_opcao
from app.services.simulacoes import obter_simulacao


def _entrada_simulacao(simulacao):
    return EntradaSimulacao(
        valor_veiculo=simulacao.valor_veiculo,
        valor_entrada=simulacao.valor_entrada,
        ipca_aa=simulacao.taxa_ipca_projetada,
        taxa_fundo_aa=simulacao.taxa_fundo_rendimento,
        prazo_fundo=simulacao.prazo_meses_fundo,
    )


def _entrada_opcao(opcao):
    return EntradaOpcao(
        id=opcao.id,
        nome=opcao.nome,
        sistema=opcao.sistema_amortizacao.value,
        taxa_juros_mensal=opcao.taxa_juros_mensal,
        prazo_meses=opcao.prazo_meses,
        valor_entrada=opcao.valor_entrada,
    )


def parcelas_da_opcao(usuario, simulacao_id, opcao_id):
    """Tabela de amortização de uma opção. 404 uniforme: dono da simulação, depois a opção."""
    simulacao = obter_simulacao(usuario, simulacao_id)
    opcao = obter_opcao(simulacao, opcao_id)
    return financiamento_da_opcao(simulacao.valor_veiculo, _entrada_opcao(opcao))


def resultado_da_simulacao(usuario, simulacao_id, aporte_mensal=None):
    """Os três cenários da simulação (devolve o model e o resultado, para o documento)."""
    simulacao = obter_simulacao(usuario, simulacao_id)
    opcoes, _ = listar_opcoes(simulacao)
    resultado = montar_resultado(
        _entrada_simulacao(simulacao), [_entrada_opcao(o) for o in opcoes], aporte_mensal
    )
    return simulacao, resultado
