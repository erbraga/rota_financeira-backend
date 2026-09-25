from flasgger import Swagger
from flask import Flask
from flask_cors import CORS

from app import models  # noqa: F401  (registra os models no metadata para as migrations)
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
            },
            "RegistroRequisicao": {
                "type": "object",
                "required": ["nome", "email", "senha"],
                "properties": {
                    "nome": {
                        "type": "string",
                        "minLength": 2,
                        "maxLength": 120,
                        "example": "Ana Souza",
                    },
                    "email": {
                        "type": "string",
                        "format": "email",
                        "maxLength": 254,
                        "description": "Convertido para minúsculas e sem espaços nas pontas.",
                        "example": "ana@exemplo.com",
                    },
                    "senha": {
                        "type": "string",
                        "format": "password",
                        "minLength": 8,
                        "maxLength": 128,
                        "description": "Guardada apenas como hash; espaços e acentos são aceitos.",
                        "example": "minha senha 2027",
                    },
                },
            },
            "LoginRequisicao": {
                "type": "object",
                "required": ["email", "senha"],
                "properties": {
                    "email": {"type": "string", "format": "email", "example": "ana@exemplo.com"},
                    "senha": {
                        "type": "string",
                        "format": "password",
                        "maxLength": 128,
                        "example": "minha senha 2027",
                    },
                },
            },
            "Usuario": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "example": 1},
                    "nome": {"type": "string", "example": "Ana Souza"},
                    "email": {"type": "string", "format": "email", "example": "ana@exemplo.com"},
                    "criado_em": {
                        "type": "string",
                        "format": "date-time",
                        "example": "2026-09-25T21:00:00+00:00",
                    },
                },
            },
            "UsuarioResumo": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "example": 1},
                    "nome": {"type": "string", "example": "Ana Souza"},
                    "email": {"type": "string", "format": "email", "example": "ana@exemplo.com"},
                },
            },
            "LoginResposta": {
                "type": "object",
                "properties": {
                    "access_token": {"type": "string", "description": "Token JWT."},
                    "token_type": {"type": "string", "example": "Bearer"},
                    "expires_in": {
                        "type": "integer",
                        "description": "Validade do token, em segundos.",
                        "example": 3600,
                    },
                    "usuario": {"$ref": "#/components/schemas/UsuarioResumo"},
                },
            },
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
