from decimal import Decimal

from marshmallow import Schema, ValidationError, fields, pre_load, validate, validates_schema

from app.schemas.base import (
    EntradaSchema,
    campo_decimal,
    campo_inteiro,
    mensagens,
    normalizar_texto,
)

VALOR_MAXIMO = "9999999.00"


class SimulacaoSchema(EntradaSchema):
    """Corpo do POST e do PUT (substituição total). Taxas em percentual (12.5 = 12,5%)."""

    nome = fields.String(
        required=True,
        validate=validate.Length(min=1, max=120, error="O nome deve ter entre 1 e 120 caracteres."),
        error_messages=mensagens("Nome inválido."),
    )
    valor_veiculo = campo_decimal(
        "O valor do veículo", "0.01", VALOR_MAXIMO, 2, exibir_casas=2, required=True
    )
    valor_entrada = campo_decimal(
        "O valor da entrada", "0", VALOR_MAXIMO, 2, exibir_casas=2, load_default=Decimal("0")
    )
    taxa_ipca_projetada = campo_decimal(
        "A taxa de IPCA projetada", "-20", "100", 6, required=True
    )
    taxa_fundo_rendimento = campo_decimal(
        "A taxa de rendimento do fundo", "0", "100", 6, required=True
    )
    prazo_meses_fundo = campo_inteiro("O prazo do fundo (em meses)", 1, 60, required=True)

    @pre_load
    def normalizar(self, dados, **kwargs):
        return normalizar_texto(dados, ("nome",))

    @validates_schema
    def entrada_nao_excede_o_veiculo(self, dados, **kwargs):
        # Só roda quando os campos são válidos; o banco tem a mesma regra (<=).
        if dados["valor_entrada"] > dados["valor_veiculo"]:
            raise ValidationError(
                "A entrada não pode ser maior que o valor do veículo.", "valor_entrada"
            )


class SimulacaoSaidaSchema(Schema):
    """Saída: números como número JSON e sem `usuario_id`."""

    id = fields.Integer()
    nome = fields.String()
    valor_veiculo = fields.Float()
    valor_entrada = fields.Float()
    taxa_ipca_projetada = fields.Float()
    taxa_fundo_rendimento = fields.Float()
    prazo_meses_fundo = fields.Integer()
    criado_em = fields.DateTime()
