from flasgger import Swagger
from flask import Flask
from flask_cors import CORS

from app.errors import registrar_handlers
from app.extensions import db, jwt, migrate
from app.routes import registrar_blueprints
from config import Config

SWAGGER_CONFIG = {
    "openapi": "3.0.2",
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec",
            "route": "/apispec.json",
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/apidocs/",
}

SWAGGER_TEMPLATE = {
    "info": {
        "title": "Rota Financeira API",
        "version": "0.1.0",
        "description": (
            "API REST do comparador de cenários para compra de carros: "
            "à vista, financiado e à vista no futuro com fundo de investimento."
        ),
    },
    "components": {
        "securitySchemes": {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "Token JWT obtido em /api/auth/login (cole apenas o token).",
            }
        },
        "schemas": {
            "Erro": {
                "type": "object",
                "required": ["erro"],
                "properties": {
                    "erro": {"type": "string", "example": "Recurso não encontrado"},
                    "detalhes": {
                        "type": "object",
                        "description": "Informações adicionais por campo, quando houver.",
                        "additionalProperties": True,
                    },
                },
            }
        },
    },
}


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    app.json.ensure_ascii = False
    if config:
        app.config.update(config)

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)

    origens = app.config["CORS_ORIGINS"]
    if not origens:
        app.logger.warning("CORS_ORIGINS vazio: nenhuma origem externa está liberada.")
    CORS(app, resources={r"/api/*": {"origins": origens}})

    Swagger(app, config=SWAGGER_CONFIG, template=SWAGGER_TEMPLATE)

    registrar_handlers(app)
    registrar_blueprints(app)
    return app
