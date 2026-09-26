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
            "SimulacaoRequisicao": {
                "type": "object",
                "required": [
                    "nome",
                    "valor_veiculo",
                    "taxa_ipca_projetada",
                    "taxa_fundo_rendimento",
                    "prazo_meses_fundo",
                ],
                "description": (
                    "Corpo do POST e do PUT (o PUT substitui todos os campos: se "
                    "valor_entrada for omitido, volta a 0). Taxas em percentual "
                    "(12.5 = 12,5%). Aceita número ou texto numérico."
                ),
                "properties": {
                    "nome": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 120,
                        "example": "Onix 2026",
                    },
                    "valor_veiculo": {
                        "type": "number",
                        "minimum": 0.01,
                        "maximum": 9999999,
                        "description": "Em reais, até 2 casas decimais (de 0,01 a 9.999.999,00).",
                        "example": 95000,
                    },
                    "valor_entrada": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 9999999,
                        "default": 0,
                        "description": (
                            "Em reais, até 2 casas decimais; não pode passar do valor "
                            "do veículo (igual é aceito). Opcional, padrão 0."
                        ),
                        "example": 20000,
                    },
                    "taxa_ipca_projetada": {
                        "type": "number",
                        "minimum": -20,
                        "maximum": 100,
                        "description": "IPCA projetado, % ao ano, até 6 casas decimais (pode ser negativo).",
                        "example": 4.5,
                    },
                    "taxa_fundo_rendimento": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 100,
                        "description": "Rendimento do fundo, % ao ano, até 6 casas decimais.",
                        "example": 10.5,
                    },
                    "prazo_meses_fundo": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 60,
                        "description": "Prazo para acumular, em meses (número inteiro).",
                        "example": 36,
                    },
                },
            },
            "Simulacao": {
                "type": "object",
                "description": "Os campos da requisição mais `id` e `criado_em` (números como número JSON).",
                "properties": {
                    "id": {"type": "integer", "example": 1},
                    "nome": {"type": "string", "example": "Onix 2026"},
                    "valor_veiculo": {"type": "number", "example": 95000.0},
                    "valor_entrada": {"type": "number", "example": 20000.0},
                    "taxa_ipca_projetada": {"type": "number", "example": 4.5},
                    "taxa_fundo_rendimento": {"type": "number", "example": 10.5},
                    "prazo_meses_fundo": {"type": "integer", "example": 36},
                    "criado_em": {
                        "type": "string",
                        "format": "date-time",
                        "example": "2026-09-25T21:00:00+00:00",
                    },
                },
            },
            "SimulacaoLista": {
                "type": "object",
                "description": "Simulações do usuário, da mais recente para a mais antiga.",
                "properties": {
                    "itens": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/Simulacao"},
                    },
                    "total": {"type": "integer", "example": 1},
                },
            },
            "FinanciamentoRequisicao": {
                "type": "object",
                "required": ["nome", "taxa_juros_mensal", "prazo_meses", "sistema_amortizacao"],
                "description": (
                    "Corpo do POST e do PUT de uma opção de financiamento (o PUT substitui "
                    "todos os campos: se valor_entrada for omitido, volta a 0). Taxa em "
                    "percentual ao mês (1.99 = 1,99% a.m.). Aceita número ou texto numérico."
                ),
                "properties": {
                    "nome": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 120,
                        "example": "Banco X 48x",
                    },
                    "taxa_juros_mensal": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 20,
                        "description": "Juros, % ao mês, até 6 casas decimais (0 é aceito).",
                        "example": 1.99,
                    },
                    "prazo_meses": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 72,
                        "description": "Prazo em meses (número inteiro).",
                        "example": 48,
                    },
                    "sistema_amortizacao": {
                        "type": "string",
                        "enum": ["PRICE", "SAC"],
                        "description": "Aceita qualquer caixa (sac, Price); a resposta vem em maiúsculas.",
                        "example": "PRICE",
                    },
                    "valor_entrada": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 9999999,
                        "default": 0,
                        "description": (
                            "Em reais, até 2 casas decimais. Precisa ser MENOR que o valor do "
                            "veículo da simulação (igual não é aceito: não haveria o que "
                            "financiar). Opcional, padrão 0."
                        ),
                        "example": 20000,
                    },
                },
            },
            "Financiamento": {
                "type": "object",
                "description": "Os campos da requisição mais `id` (números como número JSON).",
                "properties": {
                    "id": {"type": "integer", "example": 1},
                    "nome": {"type": "string", "example": "Banco X 48x"},
                    "taxa_juros_mensal": {"type": "number", "example": 1.99},
                    "prazo_meses": {"type": "integer", "example": 48},
                    "sistema_amortizacao": {"type": "string", "enum": ["PRICE", "SAC"], "example": "PRICE"},
                    "valor_entrada": {"type": "number", "example": 20000.0},
                },
            },
            "FinanciamentoLista": {
                "type": "object",
                "description": "Opções da simulação (no máximo 3), em ordem de criação.",
                "properties": {
                    "itens": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/Financiamento"},
                    },
                    "total": {"type": "integer", "example": 2},
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
