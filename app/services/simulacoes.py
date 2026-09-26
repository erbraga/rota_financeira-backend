from flask import abort
from marshmallow import ValidationError

from app.extensions import db
from app.models import OpcaoFinanciamento, Simulacao
from app.schemas.base import formatar_numero

# Maior valor do INTEGER do banco: ids acima disso nunca existem (404, não erro do banco).
# Fica aqui, e não no conversor da rota, porque `int(max=...)` faz PUT/DELETE
# responderem 405 em vez de 404.
ID_MAXIMO = 2147483647

CAMPOS_EDITAVEIS = (
    "nome",
    "valor_veiculo",
    "valor_entrada",
    "taxa_ipca_projetada",
    "taxa_fundo_rendimento",
    "prazo_meses_fundo",
)


def listar_simulacoes(usuario):
    """Simulações do usuário, da mais recente para a mais antiga, e o total."""
    consulta = (
        db.select(Simulacao)
        .where(Simulacao.usuario_id == usuario.id)
        .order_by(Simulacao.criado_em.desc(), Simulacao.id.desc())
    )
    itens = db.session.scalars(consulta).all()
    return itens, len(itens)


def obter_simulacao(usuario, simulacao_id, bloquear=False):
    """Uma consulta por `id` **e** `usuario_id`: alheia e inexistente dão o mesmo 404.

    Com `bloquear=True` a linha fica travada (`FOR UPDATE`) até o commit/rollback: use
    quando a regra conta ou compara linhas relacionadas (limite de opções, entrada x
    valor do veículo), para duas requisições simultâneas não furarem a regra.
    """
    if simulacao_id > ID_MAXIMO:
        abort(404, "Simulação não encontrada")
    consulta = db.select(Simulacao).where(
        Simulacao.id == simulacao_id, Simulacao.usuario_id == usuario.id
    )
    if bloquear:
        consulta = consulta.with_for_update()
    return db.first_or_404(consulta, description="Simulação não encontrada")


def criar_simulacao(usuario, dados):
    simulacao = Simulacao(usuario_id=usuario.id, **{campo: dados[campo] for campo in CAMPOS_EDITAVEIS})
    db.session.add(simulacao)
    db.session.commit()
    return simulacao


def _conferir_opcoes(simulacao, dados):
    # Regra entre tabelas: o novo valor do veículo precisa continuar maior que a entrada
    # de cada opção de financiamento (uma opção sem o que financiar não faz sentido).
    conflito = db.session.scalars(
        db.select(OpcaoFinanciamento)
        .where(
            OpcaoFinanciamento.simulacao_id == simulacao.id,
            OpcaoFinanciamento.valor_entrada >= dados["valor_veiculo"],
        )
        .order_by(OpcaoFinanciamento.valor_entrada.desc(), OpcaoFinanciamento.id)
        .limit(1)
    ).first()
    if conflito is not None:
        entrada = formatar_numero(conflito.valor_entrada, 2)
        raise ValidationError(
            {
                "valor_veiculo": [
                    "O valor do veículo deve ser maior que a entrada da opção de "
                    f'financiamento "{conflito.nome}" (R$ {entrada}). Ajuste a opção antes.'
                ]
            }
        )


def atualizar_simulacao(simulacao, dados):
    """Substituição total: nunca toca em `id`, `usuario_id` nem `criado_em`.

    `simulacao` precisa ter sido obtida com `bloquear=True`: a conferência das opções
    não pode correr com o cadastro de uma opção nova.
    """
    _conferir_opcoes(simulacao, dados)
    for campo in CAMPOS_EDITAVEIS:
        setattr(simulacao, campo, dados[campo])
    db.session.commit()
    return simulacao


def excluir_simulacao(simulacao):
    # Pela sessão do ORM: a cascata apaga as opções antes (o banco usa RESTRICT).
    db.session.delete(simulacao)
    db.session.commit()
