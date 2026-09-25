import logging

from flask import jsonify
from werkzeug.exceptions import HTTPException

logger = logging.getLogger(__name__)

MENSAGENS_PADRAO = {
    400: "Requisição inválida",
    401: "Não autenticado",
    403: "Acesso negado",
    404: "Recurso não encontrado",
    405: "Método não permitido",
    409: "Conflito com o estado atual do recurso",
    415: "Tipo de conteúdo não suportado",
    422: "Dados inválidos",
    429: "Muitas requisições",
}


def mensagem_http(erro):
    # Descrição personalizada (abort(404, "...")) prevalece sobre a padrão do Werkzeug.
    if erro.description and erro.description != type(erro).description:
        return erro.description
    return MENSAGENS_PADRAO.get(erro.code, erro.name)


def resposta_erro(mensagem, status, detalhes=None):
    corpo = {"erro": mensagem}
    if detalhes:
        corpo["detalhes"] = detalhes
    return jsonify(corpo), status


def registrar_handlers(app):
    @app.errorhandler(HTTPException)
    def tratar_http(erro):
        resposta, status = resposta_erro(mensagem_http(erro), erro.code)
        resposta.headers.extend(
            (chave, valor)
            for chave, valor in erro.get_headers()
            if chave.lower() != "content-type"
        )
        return resposta, status

    @app.errorhandler(Exception)
    def tratar_erro_inesperado(erro):
        logger.exception("Erro não tratado: %s", erro)
        return resposta_erro("Erro interno do servidor", 500)
