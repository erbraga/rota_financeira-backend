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
            "Parcela": {
                "type": "object",
                "description": "Uma linha da tabela de amortização (valores em reais, número JSON).",
                "properties": {
                    "numero": {"type": "integer", "example": 1},
                    "valor_parcela": {"type": "number", "example": 2440.16},
                    "juros": {"type": "number", "example": 1492.5},
                    "amortizacao": {"type": "number", "example": 947.66},
                    "saldo_devedor": {
                        "type": "number",
                        "description": "Saldo devedor DEPOIS de pagar esta parcela (0,00 na última).",
                        "example": 74052.34,
                    },
                },
            },
            "ParcelasFinanciamento": {
                "type": "object",
                "description": (
                    "Tabela de amortização de uma opção, calculada na hora (nada é gravado). A "
                    "última parcela absorve o resíduo do arredondamento e pode diferir das demais "
                    "por centavos (com juros muito altos, bem mais). Com parcelas de centavos ou "
                    "juros extremos o financiamento pode ser quitado antes do prazo por "
                    "arredondamento: as parcelas seguintes saem 0,00 (a tabela mantém uma linha "
                    "por mês do prazo)."
                ),
                "properties": {
                    "financiamento": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer", "example": 4},
                            "nome": {"type": "string", "example": "Banco X 48x"},
                            "sistema_amortizacao": {"type": "string", "enum": ["PRICE", "SAC"], "example": "PRICE"},
                            "valor_financiado": {
                                "type": "number",
                                "description": "Valor do veículo menos a entrada da opção.",
                                "example": 75000.0,
                            },
                            "valor_entrada": {"type": "number", "example": 20000.0},
                            "taxa_juros_mensal": {"type": "number", "description": "% ao mês.", "example": 1.99},
                            "prazo_meses": {"type": "integer", "example": 48},
                        },
                    },
                    "parcelas": {"type": "array", "items": {"$ref": "#/components/schemas/Parcela"}},
                    "totais": {
                        "type": "object",
                        "properties": {
                            "total_pago": {"type": "number", "description": "Soma das parcelas.", "example": 117128.07},
                            "total_juros": {"type": "number", "example": 42128.07},
                            "custo_total": {
                                "type": "number",
                                "description": "Entrada da opção + total pago.",
                                "example": 137128.07,
                            },
                        },
                    },
                },
            },
            "ResultadoFinanciamento": {
                "type": "object",
                "description": "Uma opção de financiamento no resultado (a tabela completa está em /parcelas).",
                "properties": {
                    "id": {"type": "integer", "example": 4},
                    "nome": {"type": "string", "example": "Banco X 48x"},
                    "sistema_amortizacao": {"type": "string", "enum": ["PRICE", "SAC"], "example": "PRICE"},
                    "valor_financiado": {"type": "number", "example": 75000.0},
                    "valor_entrada": {"type": "number", "example": 20000.0},
                    "prazo_meses": {"type": "integer", "example": 48},
                    "primeira_parcela": {"type": "number", "example": 2440.16},
                    "ultima_parcela": {
                        "type": "number",
                        "description": "Pode diferir das demais por centavos: absorve o resíduo do arredondamento.",
                        "example": 2440.55,
                    },
                    "total_pago": {"type": "number", "example": 117128.07},
                    "total_juros": {"type": "number", "example": 42128.07},
                    "custo_total": {
                        "type": "number",
                        "description": "O que se paga pelo carro nesta opção: entrada + soma das parcelas.",
                        "example": 137128.07,
                    },
                },
            },
            "ResultadoFundo": {
                "type": "object",
                "description": (
                    "Cenário de comprar no futuro acumulando em um fundo: aportes ao fim de cada "
                    "mês, o valor_entrada da simulação é o capital inicial e a meta é o preço do "
                    "carro corrigido pelo IPCA. Sem aporte_mensal na URL, o aporte é calculado "
                    "para o prazo_meses_fundo da simulação; com aporte_mensal, esse aporte "
                    "substitui o calculado e o prazo da simulação deixa de ser usado."
                ),
                "properties": {
                    "capital_inicial": {"type": "number", "example": 20000.0},
                    "aporte_mensal": {"type": "number", "example": 1948.07},
                    "prazo_meses": {
                        "type": "integer",
                        "description": "Meses simulados: o prazo da simulação, ou o mês da meta (ou 60, se não alcançada) no modo aporte_mensal.",
                        "example": 36,
                    },
                    "mes_da_meta": {
                        "type": "integer",
                        "nullable": True,
                        "description": "Mês da compra. null se o fundo não alcança o preço em 60 meses (modo aporte_mensal).",
                        "example": 36,
                    },
                    "alcanca_a_meta": {"type": "boolean", "example": True},
                    "preco_na_compra": {
                        "type": "number",
                        "nullable": True,
                        "description": "Preço do carro corrigido pelo IPCA no mês da compra.",
                        "example": 108410.78,
                    },
                    "total_aportado": {"type": "number", "example": 70130.52},
                    "rendimento": {"type": "number", "example": 18280.45},
                    "saldo_final": {"type": "number", "example": 108410.97},
                    "custo_total": {
                        "type": "number",
                        "nullable": True,
                        "description": "O que se paga pelo carro: o preço corrigido na compra. null quando a meta não é alcançada (o fundo fica fora do menor_custo).",
                        "example": 108410.78,
                    },
                },
            },
            "MenorCusto": {
                "type": "object",
                "description": "Cenário de menor custo_total (empate: à vista, financiamentos na ordem de criação, fundo).",
                "properties": {
                    "cenario": {"type": "string", "enum": ["a_vista", "financiamento", "fundo"], "example": "a_vista"},
                    "id": {
                        "type": "integer",
                        "nullable": True,
                        "description": "Id da opção, quando o cenário é um financiamento.",
                    },
                },
            },
            "PontoSerie": {
                "type": "object",
                "description": (
                    "Um mês do gráfico. O eixo é comum, do mês 0 ao maior prazo envolvido; "
                    "preco_corrigido existe em todo o eixo e as demais séries são null depois que "
                    "terminam (o fundo na compra, o saldo devedor na quitação)."
                ),
                "properties": {
                    "mes": {"type": "integer", "example": 0},
                    "preco_corrigido": {"type": "number", "example": 95000.0},
                    "saldo_fundo": {"type": "number", "nullable": True, "example": 20000.0},
                    "saldo_devedor": {
                        "type": "object",
                        "description": "Saldo devedor de cada opção; a chave é o id da opção (texto). No mês 0 vale o valor financiado.",
                        "additionalProperties": {"type": "number", "nullable": True},
                        "example": {"4": 75000.0, "5": 65000.0},
                    },
                },
            },
            "ResultadoSimulacao": {
                "type": "object",
                "description": (
                    "Comparação dos três cenários. custo_total é o que se PAGA PELO CARRO em cada um: "
                    "à vista = valor do veículo; financiamento = entrada + soma das parcelas; fundo = "
                    "preço corrigido na compra. A comparação é nominal (sem valor presente) e "
                    "menor_custo já vem calculado. Tudo é calculado na hora."
                ),
                "properties": {
                    "simulacao": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer", "example": 3},
                            "nome": {"type": "string", "example": "Onix 2026"},
                            "valor_veiculo": {"type": "number", "example": 95000.0},
                            "valor_entrada": {"type": "number", "example": 20000.0},
                            "taxa_ipca_projetada": {"type": "number", "example": 4.5},
                            "taxa_fundo_rendimento": {"type": "number", "example": 10.5},
                            "prazo_meses_fundo": {"type": "integer", "example": 36},
                        },
                    },
                    "cenarios": {
                        "type": "object",
                        "properties": {
                            "a_vista": {
                                "type": "object",
                                "properties": {"custo_total": {"type": "number", "example": 95000.0}},
                            },
                            "financiamentos": {
                                "type": "array",
                                "description": "0 a 3 opções, em ordem de criação.",
                                "items": {"$ref": "#/components/schemas/ResultadoFinanciamento"},
                            },
                            "fundo": {"$ref": "#/components/schemas/ResultadoFundo"},
                        },
                    },
                    "menor_custo": {"$ref": "#/components/schemas/MenorCusto"},
                    "series": {"type": "array", "items": {"$ref": "#/components/schemas/PontoSerie"}},
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
