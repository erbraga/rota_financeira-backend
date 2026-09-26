from flask import request
from marshmallow import ValidationError
from werkzeug.exceptions import BadRequest, UnsupportedMediaType


def carregar(schema):
    """Lê o corpo JSON da requisição e o valida com o schema (levanta ValidationError)."""
    if not request.is_json:
        raise UnsupportedMediaType()
    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        raise BadRequest("Corpo da requisição deve ser um objeto JSON")
    return schema.load(dados)


def carregar_consulta(schema):
    """Valida os parâmetros da URL (`?nome=valor`); parâmetro repetido é recusado (422)."""
    parametros = request.args.to_dict(flat=False)
    repetidos = {nome: ["Informe o parâmetro uma única vez."] for nome, v in parametros.items() if len(v) > 1}
    if repetidos:
        raise ValidationError(repetidos)
    return schema.load({nome: valores[0] for nome, valores in parametros.items()})
