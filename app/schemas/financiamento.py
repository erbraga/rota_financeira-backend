from decimal import Decimal

from marshmallow import Schema, fields, pre_load, validate

from app.models import SistemaAmortizacao
from app.schemas.base import (
    EntradaSchema,
    campo_decimal,
    campo_inteiro,
    mensagens,
    normalizar_texto,
)
from app.schemas.simulacao import VALOR_MAXIMO

MENSAGEM_SISTEMA = "Sistema de amortização inválido. Use PRICE ou SAC."


class FinanciamentoSchema(EntradaSchema):
    """Corpo do POST e do PUT (substituição total). Taxa em percentual ao mês (1.99 = 1,99%)."""

    nome = fields.String(
        required=True,
        validate=validate.Length(min=1, max=120, error="O nome deve ter entre 1 e 120 caracteres."),
        error_messages=mensagens("Nome inválido."),
    )
    taxa_juros_mensal = campo_decimal(
        "A taxa de juros mensal", "0", "20", 6, required=True
    )
    prazo_meses = campo_inteiro("O prazo (em meses)", 1, 72, required=True)
    sistema_amortizacao = fields.Enum(
        SistemaAmortizacao,
        by_value=True,
        required=True,
        error_messages={
            "required": "Campo obrigatório.",
            "null": MENSAGEM_SISTEMA,
            "unknown": MENSAGEM_SISTEMA,
            "invalid": MENSAGEM_SISTEMA,
        },
    )
    valor_entrada = campo_decimal(
        "O valor da entrada", "0", VALOR_MAXIMO, 2, exibir_casas=2, load_default=Decimal("0")
    )

    @pre_load
    def normalizar(self, dados, **kwargs):
        dados = normalizar_texto(dados, ("nome", "sistema_amortizacao"), maiusculas=("sistema_amortizacao",))
        return dados


class FinanciamentoSaidaSchema(Schema):
    """Saída: números como número JSON, sistema em maiúsculas e sem `simulacao_id`."""

    id = fields.Integer()
    nome = fields.String()
    taxa_juros_mensal = fields.Float()
    prazo_meses = fields.Integer()
    sistema_amortizacao = fields.Enum(SistemaAmortizacao, by_value=True)
    valor_entrada = fields.Float()
