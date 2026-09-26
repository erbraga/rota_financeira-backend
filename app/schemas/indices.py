"""Saída de `GET /api/indices/<indice>` (contrato com o frontend) e o parâmetro `periodo`."""
from marshmallow import Schema, fields, validate

from app.schemas.base import EntradaSchema, mensagens
from app.services.indices import PERIODO_PADRAO, PERIODOS

MENSAGEM_PERIODO = "O período deve ser um destes: " + ", ".join(PERIODOS) + "."


class ConsultaIndiceSchema(EntradaSchema):
    """`?periodo=` (opcional, padrão 12m). Recusa parâmetros desconhecidos."""

    periodo = fields.String(
        load_default=PERIODO_PADRAO,
        validate=validate.OneOf(list(PERIODOS), error=MENSAGEM_PERIODO),
        error_messages=mensagens(MENSAGEM_PERIODO),
    )


class SugestaoSchema(Schema):
    valor = fields.Float()
    data_referencia = fields.Date()


class PeriodoSchema(Schema):
    inicio = fields.Date()
    fim = fields.Date()


class PontoIndiceSchema(Schema):
    data = fields.Date()
    valor = fields.Float()


class IndiceSchema(Schema):
    indice = fields.String()
    descricao = fields.String()
    unidade = fields.String()
    serie_sgs = fields.Integer()
    sugestao = fields.Nested(SugestaoSchema, allow_none=True)
    periodo = fields.Nested(PeriodoSchema)
    pontos = fields.List(fields.Nested(PontoIndiceSchema))
    atualizado_em = fields.DateTime(allow_none=True)
    desatualizado = fields.Boolean()


def indice_para_documento(resultado):
    """`resultado`: `ResultadoIndice` (services.indices) → documento para o `IndiceSchema`."""
    sugestao = None
    if resultado.sugestao is not None:
        data, valor = resultado.sugestao
        sugestao = {"valor": valor, "data_referencia": data}
    return {
        "indice": resultado.indice.value,
        "descricao": resultado.serie.descricao,
        "unidade": resultado.serie.unidade,
        "serie_sgs": resultado.serie.codigo,
        "sugestao": sugestao,
        "periodo": {"inicio": resultado.inicio, "fim": resultado.fim},
        "pontos": [{"data": data, "valor": valor} for data, valor in resultado.pontos],
        "atualizado_em": resultado.atualizado_em,
        "desatualizado": resultado.desatualizado,
    }
