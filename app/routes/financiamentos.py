from flask import Blueprint, url_for
from flask_jwt_extended import jwt_required

from app.errors import resposta_erro
from app.schemas import carregar
from app.schemas.financiamento import FinanciamentoSaidaSchema, FinanciamentoSchema
from app.schemas.resultado import ParcelasSchema, parcelas_para_documento
from app.services.auth import usuario_atual
from app.services.financiamentos import (
    LIMITE_OPCOES,
    LimiteDeOpcoesExcedido,
    atualizar_opcao,
    criar_opcao,
    excluir_opcao,
    listar_opcoes,
    obter_opcao,
)
from app.services.resultados import parcelas_da_opcao
from app.services.simulacoes import obter_simulacao

bp = Blueprint("financiamentos", __name__, url_prefix="/api/simulacoes")

COLECAO = "/<int:simulacao_id>/financiamentos"
ITEM = COLECAO + "/<int:financiamento_id>"


@bp.post(COLECAO)
@jwt_required()
def criar(simulacao_id):
    """Cadastra uma opção de financiamento na simulação.
    ---
    tags:
      - Financiamentos
    summary: Adiciona uma opção de financiamento
    description: >-
      Cada simulação aceita no máximo 3 opções (o quarto cadastro responde 409; excluir
      uma libera a vaga). A entrada da opção precisa ser menor que o valor do veículo da
      simulação. Taxa em percentual ao mês.
    security:
      - BearerAuth: []
    parameters:
      - name: simulacao_id
        in: path
        required: true
        description: Identificador da simulação (inteiro positivo). Se for de outro usuário ou não existir, a resposta é 404.
        schema:
          type: integer
        example: 1
    requestBody:
      required: true
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/FinanciamentoRequisicao"
    responses:
      201:
        description: Opção criada (cabeçalho Location com o endereço dela).
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Financiamento"
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
      409:
        description: A simulação já tem 3 opções de financiamento.
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Erro"
            example:
              erro: Uma simulação aceita no máximo 3 opções de financiamento
      415:
        description: O Content-Type não é application/json.
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Erro"
      422:
        description: Dados inválidos (inclui entrada maior ou igual ao valor do veículo), com as mensagens por campo em detalhes.
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Erro"
            example:
              erro: Dados inválidos
              detalhes:
                valor_entrada:
                  - A entrada deve ser menor que o valor do veículo (R$ 95.000,00); com a entrada igual ao valor não há o que financiar.
    """
    usuario = usuario_atual()
    # Bloqueia a linha da simulação: a contagem do limite não pode correr com outro cadastro.
    simulacao = obter_simulacao(usuario, simulacao_id, bloquear=True)
    dados = carregar(FinanciamentoSchema())
    try:
        opcao = criar_opcao(simulacao, dados)
    except LimiteDeOpcoesExcedido:
        return resposta_erro(
            f"Uma simulação aceita no máximo {LIMITE_OPCOES} opções de financiamento", 409
        )
    cabecalhos = {
        "Location": url_for(
            "financiamentos.atualizar", simulacao_id=simulacao.id, financiamento_id=opcao.id
        )
    }
    return FinanciamentoSaidaSchema().dump(opcao), 201, cabecalhos


@bp.get(COLECAO)
@jwt_required()
def listar(simulacao_id):
    """Lista as opções de financiamento da simulação.
    ---
    tags:
      - Financiamentos
    summary: Lista as opções de financiamento
    description: >-
      As opções da simulação (no máximo 3), em ordem de criação, dentro de um objeto
      (itens e total).
    security:
      - BearerAuth: []
    parameters:
      - name: simulacao_id
        in: path
        required: true
        description: Identificador da simulação (inteiro positivo). Se for de outro usuário ou não existir, a resposta é 404.
        schema:
          type: integer
        example: 1
    responses:
      200:
        description: Opções da simulação (itens vazio quando não há nenhuma).
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/FinanciamentoLista"
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
    simulacao = obter_simulacao(usuario_atual(), simulacao_id)
    itens, total = listar_opcoes(simulacao)
    return {"itens": FinanciamentoSaidaSchema(many=True).dump(itens), "total": total}


@bp.put(ITEM)
@jwt_required()
def atualizar(simulacao_id, financiamento_id):
    """Substitui os dados de uma opção de financiamento.
    ---
    tags:
      - Financiamentos
    summary: Edita uma opção (substituição total)
    description: >-
      Mesmo corpo do POST: todos os campos obrigatórios devem ser enviados e
      valor_entrada, se omitido, volta a 0. A entrada é conferida contra o valor do
      veículo atual da simulação. A opção nunca muda de simulação.
    security:
      - BearerAuth: []
    parameters:
      - name: simulacao_id
        in: path
        required: true
        description: Identificador da simulação (inteiro positivo). Se for de outro usuário ou não existir, a resposta é 404.
        schema:
          type: integer
        example: 1
      - name: financiamento_id
        in: path
        required: true
        description: Identificador da opção de financiamento (inteiro positivo). Se for de outra simulação ou não existir, a resposta é 404.
        schema:
          type: integer
        example: 1
    requestBody:
      required: true
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/FinanciamentoRequisicao"
    responses:
      200:
        description: Opção atualizada.
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Financiamento"
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
        description: Simulação inexistente ou de outro usuário, ou opção inexistente ou de outra simulação.
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Erro"
            example:
              erro: Opção de financiamento não encontrada
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
    simulacao = obter_simulacao(usuario, simulacao_id, bloquear=True)
    opcao = obter_opcao(simulacao, financiamento_id)
    dados = carregar(FinanciamentoSchema())
    return FinanciamentoSaidaSchema().dump(atualizar_opcao(simulacao, opcao, dados))


@bp.delete(ITEM)
@jwt_required()
def excluir(simulacao_id, financiamento_id):
    """Exclui uma opção de financiamento.
    ---
    tags:
      - Financiamentos
    summary: Exclui uma opção de financiamento
    description: >-
      Libera uma vaga (o limite é de 3 opções por simulação). A simulação pode ficar sem
      opções. A resposta de sucesso não tem corpo (não chame .json() nela).
    security:
      - BearerAuth: []
    parameters:
      - name: simulacao_id
        in: path
        required: true
        description: Identificador da simulação (inteiro positivo). Se for de outro usuário ou não existir, a resposta é 404.
        schema:
          type: integer
        example: 1
      - name: financiamento_id
        in: path
        required: true
        description: Identificador da opção de financiamento (inteiro positivo). Se for de outra simulação ou não existir, a resposta é 404.
        schema:
          type: integer
        example: 1
    responses:
      204:
        description: Opção excluída (sem corpo).
      401:
        description: Token ausente, inválido ou expirado.
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Erro"
      404:
        description: Simulação inexistente ou de outro usuário, ou opção inexistente ou de outra simulação.
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Erro"
            example:
              erro: Opção de financiamento não encontrada
    """
    simulacao = obter_simulacao(usuario_atual(), simulacao_id)
    excluir_opcao(obter_opcao(simulacao, financiamento_id))
    return "", 204


@bp.get(ITEM + "/parcelas")
@jwt_required()
def parcelas(simulacao_id, financiamento_id):
    """Tabela de amortização de uma opção de financiamento.
    ---
    tags:
      - Financiamentos
    summary: Tabela de parcelas (amortização) da opção
    description: >-
      Calculada na hora, sem gravar nada, a partir do valor do veículo atual da simulação e
      dos dados da opção (Price ou SAC). Traz o resumo da opção, uma linha por mês do prazo e
      os totais (total pago, juros e custo total = entrada + parcelas). O saldo devedor de
      cada linha é o saldo DEPOIS de pagar a parcela. A última parcela absorve o resíduo do
      arredondamento e pode diferir das demais por centavos (com juros muito altos, bem mais).
      Com parcelas de centavos ou juros extremos, o financiamento pode ser quitado antes do
      prazo por arredondamento e as parcelas seguintes saem 0,00.
    security:
      - BearerAuth: []
    parameters:
      - name: simulacao_id
        in: path
        required: true
        description: Identificador da simulação (inteiro positivo). Se for de outro usuário ou não existir, a resposta é 404.
        schema:
          type: integer
        example: 1
      - name: financiamento_id
        in: path
        required: true
        description: Identificador da opção de financiamento (inteiro positivo). Se for de outra simulação ou não existir, a resposta é 404.
        schema:
          type: integer
        example: 1
    responses:
      200:
        description: A tabela de amortização da opção.
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/ParcelasFinanciamento"
      401:
        description: Token ausente, inválido ou expirado.
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Erro"
      404:
        description: Simulação inexistente ou de outro usuário, ou opção inexistente ou de outra simulação.
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Erro"
            example:
              erro: Opção de financiamento não encontrada
    """
    financiamento = parcelas_da_opcao(usuario_atual(), simulacao_id, financiamento_id)
    return ParcelasSchema().dump(parcelas_para_documento(financiamento))
