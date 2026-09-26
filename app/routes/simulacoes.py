from flask import Blueprint, url_for
from flask_jwt_extended import jwt_required

from app.schemas import carregar, carregar_consulta
from app.schemas.resultado import (
    ConsultaResultadoSchema,
    ResultadoSchema,
    resultado_para_documento,
)
from app.schemas.simulacao import SimulacaoSaidaSchema, SimulacaoSchema
from app.services.auth import usuario_atual
from app.services.resultados import resultado_da_simulacao
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
      valor_entrada, se omitido, volta a 0. Não altera id, dono nem criado_em. O valor
      do veículo não pode ficar menor ou igual à entrada de uma opção de financiamento
      já cadastrada (422 em valor_veiculo).
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
    simulacao = obter_simulacao(usuario, simulacao_id, bloquear=True)
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


@bp.get(ID + "/resultado")
@jwt_required()
def resultado(simulacao_id):
    """Compara os três cenários da simulação.
    ---
    tags:
      - Simulações
    summary: Resultado comparativo (à vista, financiamentos e fundo)
    description: >-
      Calculado na hora, sem gravar nada, com os dados atuais da simulação e das opções
      (0 a 3). Traz os totais de cada cenário, o de menor custo e as séries mês a mês do
      gráfico; o frontend só exibe. `custo_total` é o que se PAGA PELO CARRO em cada cenário:
      à vista = valor do veículo; financiamento = entrada da opção + soma das parcelas;
      fundo = preço corrigido pelo IPCA na compra (no fundo, capital inicial, aportes e
      rendimento vêm só como informação). A comparação é nominal (sem valor presente). O
      valor_entrada da simulação é o capital inicial do fundo. As séries são uma lista de
      pontos, um por mês, num eixo comum do mês 0 ao maior prazo; onde uma série terminou o
      valor é null (o fundo na compra, o saldo devedor na quitação) e preco_corrigido
      cobre todo o eixo. Modo aporte_mensal: informe quanto pode guardar por mês e o
      aporte informado substitui o calculado; o fundo passa a dizer em que mês alcança o
      preço do carro (mes_da_meta), até 60 meses, e o prazo_meses_fundo da simulação deixa
      de ser usado. Se não alcançar, mes_da_meta e custo_total do fundo são null e o
      fundo sai do menor_custo.
    security:
      - BearerAuth: []
    parameters:
      - name: simulacao_id
        in: path
        required: true
        schema:
          type: integer
        example: 1
      - name: aporte_mensal
        in: query
        required: false
        description: >-
          Aporte mensal em reais (de 0 a 9.999.999,00, até 2 casas decimais). Omitido, o
          aporte é calculado para o prazo da simulação.
        schema:
          type: number
          minimum: 0
          maximum: 9999999
        example: 1500
    responses:
      200:
        description: Os três cenários, o menor custo e as séries.
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/ResultadoSimulacao"
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
      422:
        description: Parâmetro inválido (aporte_mensal fora da faixa, com casas em excesso, repetido ou desconhecido).
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Erro"
            example:
              erro: Dados inválidos
              detalhes:
                aporte_mensal:
                  - O aporte mensal deve estar entre 0,00 e 9.999.999,00.
    """
    usuario = usuario_atual()
    obter_simulacao(usuario, simulacao_id)  # dono primeiro: o 404 vem antes de qualquer 422
    consulta = carregar_consulta(ConsultaResultadoSchema())
    simulacao, resultado_calculado = resultado_da_simulacao(
        usuario, simulacao_id, consulta["aporte_mensal"]
    )
    return ResultadoSchema().dump(resultado_para_documento(simulacao, resultado_calculado))
