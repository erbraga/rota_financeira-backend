from flask import Blueprint, abort
from flask_jwt_extended import jwt_required

from app.errors import resposta_erro
from app.schemas import carregar_consulta
from app.schemas.indices import ConsultaIndiceSchema, IndiceSchema, indice_para_documento
from app.services.auth import usuario_atual
from app.services.indices import INDICES_POR_URL, IndicesIndisponiveis, consultar_indice

bp = Blueprint("indices", __name__, url_prefix="/api/indices")


@bp.get("/<indice>")
@jwt_required()
def obter(indice):
    """Taxa sugerida e série de um índice do Banco Central (CDI ou IPCA).
    ---
    tags:
      - Índices
    summary: Taxa sugerida (CDI ou IPCA) e série do período
    description: >-
      Dados do Banco Central (API SGS, ver "API externa utilizada" no início desta
      documentação), guardados em cache no banco: o cache vale 12 horas e a primeira consulta
      depois disso busca os últimos 60 meses no BACEN. Os valores estão em % ao ano, como
      publicados. `sugestao` é o valor mais recente até hoje (independe do período) e é o
      número para pré-preencher `taxa_fundo_rendimento` (CDI) e `taxa_ipca_projetada` (IPCA)
      no formulário; o usuário pode alterá-lo, e a simulação guarda o valor enviado. O SGS não
      tem projeção de inflação: a sugestão do IPCA é o acumulado em 12 meses do último mês
      publicado (veja `data_referencia`). Se o BACEN estiver fora do ar, a resposta vem do
      cache com `desatualizado` verdadeiro; sem nada em cache, 503 (o usuário digita a taxa).
      A Selic não faz parte desta API.
    security:
      - BearerAuth: []
    parameters:
      - name: indice
        in: path
        required: true
        description: Só minúsculas.
        schema:
          type: string
          enum: [cdi, ipca]
        example: cdi
      - name: periodo
        in: query
        required: false
        description: Meses para trás até hoje, para os `pontos` (padrão 12m).
        schema:
          type: string
          enum: ["1m", "3m", "6m", "12m", "24m", "60m"]
          default: "12m"
        example: 12m
    responses:
      200:
        description: A taxa sugerida e a série do período.
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/IndiceEconomico"
      401:
        description: Token ausente, inválido ou expirado.
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Erro"
      404:
        description: Índice inexistente (só cdi e ipca, em minúsculas).
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Erro"
            example:
              erro: Índice não encontrado
      422:
        description: Período inválido.
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Erro"
            example:
              erro: Dados inválidos
              detalhes:
                periodo:
                  - "O período deve ser um destes: 1m, 3m, 6m, 12m, 24m, 60m."
      503:
        description: O BACEN não respondeu e não há nada em cache (o usuário pode digitar a taxa).
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Erro"
            example:
              erro: Dados do Banco Central indisponíveis no momento
    """
    usuario_atual()
    tipo = INDICES_POR_URL.get(indice)
    if tipo is None:
        abort(404, "Índice não encontrado")
    consulta = carregar_consulta(ConsultaIndiceSchema())
    try:
        resultado = consultar_indice(tipo, consulta["periodo"])
    except IndicesIndisponiveis:
        return resposta_erro("Dados do Banco Central indisponíveis no momento", 503)
    return IndiceSchema().dump(indice_para_documento(resultado))
