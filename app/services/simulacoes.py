from flask import abort

from app.extensions import db
from app.models import Simulacao

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


def obter_simulacao(usuario, simulacao_id):
    """Uma consulta por `id` **e** `usuario_id`: alheia e inexistente dão o mesmo 404."""
    if simulacao_id > ID_MAXIMO:
        abort(404, "Simulação não encontrada")
    consulta = db.select(Simulacao).where(
        Simulacao.id == simulacao_id, Simulacao.usuario_id == usuario.id
    )
    return db.first_or_404(consulta, description="Simulação não encontrada")


def criar_simulacao(usuario, dados):
    simulacao = Simulacao(usuario_id=usuario.id, **{campo: dados[campo] for campo in CAMPOS_EDITAVEIS})
    db.session.add(simulacao)
    db.session.commit()
    return simulacao


def atualizar_simulacao(simulacao, dados):
    """Substituição total: nunca toca em `id`, `usuario_id` nem `criado_em`."""
    for campo in CAMPOS_EDITAVEIS:
        setattr(simulacao, campo, dados[campo])
    db.session.commit()
    return simulacao


def excluir_simulacao(simulacao):
    # Pela sessão do ORM: a cascata apaga as opções antes (o banco usa RESTRICT).
    db.session.delete(simulacao)
    db.session.commit()
