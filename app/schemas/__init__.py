from flask import request
from werkzeug.exceptions import BadRequest, UnsupportedMediaType


def carregar(schema):
    """Lê o corpo JSON da requisição e o valida com o schema (levanta ValidationError)."""
    if not request.is_json:
        raise UnsupportedMediaType()
    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        raise BadRequest("Corpo da requisição deve ser um objeto JSON")
    return schema.load(dados)
