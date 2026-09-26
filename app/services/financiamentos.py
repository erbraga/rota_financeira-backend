from flask import abort
from marshmallow import ValidationError

from app.extensions import db
from app.models import OpcaoFinanciamento
from app.schemas.base import formatar_numero
from app.services.simulacoes import ID_MAXIMO

LIMITE_OPCOES = 3
MENSAGEM_NAO_ENCONTRADA = "Opção de financiamento não encontrada"

CAMPOS_EDITAVEIS = (
    "nome",
    "taxa_juros_mensal",
    "prazo_meses",
    "sistema_amortizacao",
    "valor_entrada",
)


class LimiteDeOpcoesExcedido(Exception):
    pass


def listar_opcoes(simulacao):
    """Opções da simulação em ordem de criação e o total."""
    consulta = (
        db.select(OpcaoFinanciamento)
        .where(OpcaoFinanciamento.simulacao_id == simulacao.id)
        .order_by(OpcaoFinanciamento.id)
    )
    itens = db.session.scalars(consulta).all()
    return itens, len(itens)


def obter_opcao(simulacao, opcao_id):
    """Uma consulta por `id` **e** `simulacao_id`: a de outra simulação dá o mesmo 404."""
    if opcao_id > ID_MAXIMO:
        abort(404, MENSAGEM_NAO_ENCONTRADA)
    consulta = db.select(OpcaoFinanciamento).where(
        OpcaoFinanciamento.id == opcao_id,
        OpcaoFinanciamento.simulacao_id == simulacao.id,
    )
    return db.first_or_404(consulta, description=MENSAGEM_NAO_ENCONTRADA)


def _conferir_entrada(simulacao, dados):
    # Regra entre tabelas (o banco só confere a entrada da simulação): a opção precisa
    # financiar alguma coisa, então a entrada é estritamente menor que o veículo.
    if dados["valor_entrada"] >= simulacao.valor_veiculo:
        valor = formatar_numero(simulacao.valor_veiculo, 2)
        raise ValidationError(
            {
                "valor_entrada": [
                    f"A entrada deve ser menor que o valor do veículo (R$ {valor}); "
                    "com a entrada igual ao valor não há o que financiar."
                ]
            }
        )


def criar_opcao(simulacao, dados):
    """`simulacao` precisa ter sido obtida com `bloquear=True` (a contagem depende disso)."""
    _conferir_entrada(simulacao, dados)
    total = db.session.scalar(
        db.select(db.func.count())
        .select_from(OpcaoFinanciamento)
        .where(OpcaoFinanciamento.simulacao_id == simulacao.id)
    )
    if total >= LIMITE_OPCOES:
        raise LimiteDeOpcoesExcedido()
    opcao = OpcaoFinanciamento(
        simulacao_id=simulacao.id, **{campo: dados[campo] for campo in CAMPOS_EDITAVEIS}
    )
    db.session.add(opcao)
    db.session.commit()
    return opcao


def atualizar_opcao(simulacao, opcao, dados):
    """Substituição total, conferida contra o `valor_veiculo` atual (simulação bloqueada)."""
    _conferir_entrada(simulacao, dados)
    for campo in CAMPOS_EDITAVEIS:
        setattr(opcao, campo, dados[campo])
    db.session.commit()
    return opcao


def excluir_opcao(opcao):
    db.session.delete(opcao)
    db.session.commit()
