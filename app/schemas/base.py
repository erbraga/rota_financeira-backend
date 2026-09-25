from decimal import Decimal

from marshmallow import RAISE, Schema, ValidationError, fields, validate


class EntradaSchema(Schema):
    """Base dos schemas de entrada: rejeita campos desconhecidos, mensagens em português."""

    class Meta:
        unknown = RAISE

    error_messages = {
        "unknown": "Campo desconhecido.",
        "type": "Corpo da requisição inválido.",
    }


def normalizar_texto(dados, campos, minusculas=()):
    if not isinstance(dados, dict):
        return dados
    dados = dict(dados)
    for campo in campos:
        if isinstance(dados.get(campo), str):
            dados[campo] = dados[campo].strip()
            if campo in minusculas:
                dados[campo] = dados[campo].lower()
    return dados


def mensagens(invalido):
    return {
        "required": "Campo obrigatório.",
        "null": "Campo obrigatório.",
        "invalid": invalido,
    }


def formatar_numero(valor, casas):
    """Formata à brasileira (9.999.999,00) para as mensagens de erro."""
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "\0").replace(".", ",").replace("\0", ".")


def campo_decimal(rotulo, minimo, maximo, casas, exibir_casas=0, **opcoes):
    """Decimal com faixa e limite de casas decimais.

    Aceita número JSON ou texto numérico; recusa true, NaN e Infinity. Há um único
    validador: a faixa é conferida antes das casas, porque os validadores do
    Marshmallow rodam todos e um quantize em "1e999999" levantaria InvalidOperation.
    Zeros à direita não contam como casas em excesso ("10.000000" é aceito).
    """
    minimo, maximo = Decimal(str(minimo)), Decimal(str(maximo))
    passo = Decimal(1).scaleb(-casas)

    def validar(valor):
        if not minimo <= valor <= maximo:
            raise ValidationError(
                f"{rotulo} deve estar entre {formatar_numero(minimo, exibir_casas)} "
                f"e {formatar_numero(maximo, exibir_casas)}."
            )
        if valor != valor.quantize(passo):
            raise ValidationError(f"Use no máximo {casas} casas decimais.")

    return fields.Decimal(
        validate=validar,
        error_messages={**mensagens("Número inválido."), "special": "Número inválido."},
        **opcoes,
    )


def campo_inteiro(rotulo, minimo, maximo, **opcoes):
    """Inteiro estrito (recusa 36.0, "36" e true) dentro de uma faixa."""
    return fields.Integer(
        strict=True,
        validate=validate.Range(
            min=minimo,
            max=maximo,
            error=f"{rotulo} deve estar entre {minimo} e {maximo}.",
        ),
        error_messages=mensagens("Número inteiro inválido."),
        **opcoes,
    )
