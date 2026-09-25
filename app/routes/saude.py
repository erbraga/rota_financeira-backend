from flask import Blueprint
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.errors import resposta_erro
from app.extensions import db

bp = Blueprint("saude", __name__, url_prefix="/api")


@bp.get("/saude")
def saude():
    """Verifica se a API e o banco de dados estão respondendo.
    ---
    tags:
      - Saúde
    summary: Verifica a saúde da API
    description: Rota pública, sem autenticação. Executa uma consulta simples no banco de dados.
    responses:
      200:
        description: API e banco de dados funcionando.
        content:
          application/json:
            schema:
              type: object
              properties:
                status:
                  type: string
                  example: ok
                banco:
                  type: string
                  example: ok
      503:
        description: Banco de dados indisponível.
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Erro"
    """
    try:
        db.session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        db.session.rollback()
        return resposta_erro("Banco de dados indisponível", 503)
    return {"status": "ok", "banco": "ok"}
