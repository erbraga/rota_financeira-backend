from flask import Blueprint, url_for
from flask_jwt_extended import jwt_required

from app.schemas import carregar
from app.schemas.simulacao import SimulacaoSaidaSchema, SimulacaoSchema
from app.services.auth import usuario_atual
from app.services.simulacoes import (
    atualizar_simulacao,
    criar_simulacao,
    excluir_simulacao,
    listar_simulacoes,
    obter_simulacao,
)

bp = Blueprint("simulacoes", __name__, url_prefix="/api/simulacoes")

ID = "<int:simulacao_id>"


@bp.post("")
@jwt_required()
def criar():
    """Cria uma simulação do usuário logado.
    ---
    tags:
      - Simulações
    summary: Cria uma simulação
    description: >-
      O dono é sempre o usuário do token. Taxas em percentual (12.5 = 12,5%).
      Campos desconhecidos (id, usuario_id, criado_em) são recusados.
    security:
      - BearerAuth: []
    requestBody:
      required: true
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/SimulacaoRequisicao"
    responses:
      201:
        description: Simulação criada (cabeçalho Location com o endereço dela).
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Simulacao"
      400:
        description: O corpo não é um JSON válido ou não é um objeto.
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Erro"
      401:
        description: Token ausente, inválido ou expirado.
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Erro"
            example:
              erro: Token de autenticação ausente
      415:
        description: O Content-Type não é application/json.
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Erro"
      422:
        description: Dados inválidos, com as mensagens por campo em detalhes.
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Erro"
            example:
              erro: Dados inválidos
              detalhes:
                prazo_meses_fundo:
                  - O prazo do fundo (em meses) deve estar entre 1 e 60.
    """
    usuario = usuario_atual()
    dados = carregar(SimulacaoSchema())
    simulacao = criar_simulacao(usuario, dados)
    cabecalhos = {"Location": url_for("simulacoes.obter", simulacao_id=simulacao.id)}
    return SimulacaoSaidaSchema().dump(simulacao), 201, cabecalhos


@bp.get("")
@jwt_required()
def listar():
    """Lista as simulações do usuário logado.
    ---
    tags:
      - Simulações
    summary: Lista as simulações do usuário
    description: >-
      Só as simulações do usuário do token, da mais recente para a mais antiga.
      A lista vem dentro de um objeto (itens e total).
    security:
      - BearerAuth: []
    responses:
      200:
        description: Simulações do usuário (itens vazio quando não há nenhuma).
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/SimulacaoLista"
      401:
        description: Token ausente, inválido ou expirado.
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Erro"
            example:
              erro: Token expirado
    """
    itens, total = listar_simulacoes(usuario_atual())
    return {"itens": SimulacaoSaidaSchema(many=True).dump(itens), "total": total}


@bp.get(ID)
@jwt_required()
def obter(simulacao_id):
    """Detalha uma simulação do usuário logado.
    ---
    tags:
      - Simulações
    summary: Consulta uma simulação
    description: >-
      Simulação de outro usuário responde 404, igual a uma que não existe. As
      opções de financiamento não vêm aqui (têm rota própria).
    security:
      - BearerAuth: []
    parameters:
      - name: simulacao_id
        in: path
        required: true
        schema:
          type: integer
        example: 1
    responses:
      200:
        description: A simulação.
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Simulacao"
      401:
        description: Token ausente, inválido ou expirado.
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Erro"
      404:
        description: Simulação inexistente ou de outro usuário.
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Erro"
            example:
              erro: Simulação não encontrada
    """
    return SimulacaoSaidaSchema().dump(obter_simulacao(usuario_atual(), simulacao_id))


@bp.put(ID)
@jwt_required()
def atualizar(simulacao_id):
    """Substitui os dados de uma simulação do usuário logado.
    ---
    tags:
      - Simulações
    summary: Edita uma simulação (substituição total)
    description: >-
      Mesmo corpo do POST: todos os campos obrigatórios devem ser enviados e
      valor_entrada, se omitido, volta a 0. Não altera id, dono nem criado_em.
    security:
      - BearerAuth: []
    parameters:
      - name: simulacao_id
        in: path
        required: true
        schema:
          type: integer
        example: 1
    requestBody:
      required: true
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/SimulacaoRequisicao"
    responses:
      200:
        description: Simulação atualizada.
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Simulacao"
      400:
        description: O corpo não é um JSON válido ou não é um objeto.
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Erro"
      401:
        description: Token ausente, inválido ou expirado.
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Erro"
      404:
        description: Simulação inexistente ou de outro usuário.
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Erro"
            example:
              erro: Simulação não encontrada
      415:
        description: O Content-Type não é application/json.
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Erro"
      422:
        description: Dados inválidos, com as mensagens por campo em detalhes.
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Erro"
    """
    usuario = usuario_atual()
    simulacao = obter_simulacao(usuario, simulacao_id)
    dados = carregar(SimulacaoSchema())
    return SimulacaoSaidaSchema().dump(atualizar_simulacao(simulacao, dados))


@bp.delete(ID)
@jwt_required()
def excluir(simulacao_id):
    """Exclui uma simulação do usuário logado.
    ---
    tags:
      - Simulações
    summary: Exclui uma simulação
    description: >-
      Apaga também as opções de financiamento dela. Excluir de novo responde 404.
      A resposta de sucesso não tem corpo (não chame .json() nela).
    security:
      - BearerAuth: []
    parameters:
      - name: simulacao_id
        in: path
        required: true
        schema:
          type: integer
        example: 1
    responses:
      204:
        description: Simulação excluída (sem corpo).
      401:
        description: Token ausente, inválido ou expirado.
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Erro"
      404:
        description: Simulação inexistente ou de outro usuário.
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Erro"
            example:
              erro: Simulação não encontrada
    """
    excluir_simulacao(obter_simulacao(usuario_atual(), simulacao_id))
    return "", 204
