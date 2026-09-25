import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

# Não sobrescreve variáveis que já estejam definidas no ambiente real.
load_dotenv(Path(__file__).resolve().parent / ".env")

CHAVE_JWT_EXEMPLO = "troque-esta-chave"
TAMANHO_MINIMO_CHAVE_JWT = 32
EXPIRACAO_PADRAO_MINUTOS = 60


def _obrigatoria(nome):
    valor = os.environ.get(nome, "").strip()
    if not valor:
        raise RuntimeError(
            f"Variável de ambiente obrigatória não definida: {nome}. "
            "Copie .env.example para .env e preencha os valores."
        )
    return valor


def _chave_jwt():
    chave = _obrigatoria("JWT_SECRET_KEY")
    if chave == CHAVE_JWT_EXEMPLO or len(chave) < TAMANHO_MINIMO_CHAVE_JWT:
        raise RuntimeError(
            "JWT_SECRET_KEY inválida: use uma chave secreta com pelo menos "
            f"{TAMANHO_MINIMO_CHAVE_JWT} caracteres, diferente do valor de exemplo. "
            'Para gerar uma: python -c "import secrets; print(secrets.token_hex(32))"'
        )
    return chave


def _expiracao_token():
    valor = os.environ.get("JWT_ACCESS_TOKEN_EXPIRES_MINUTOS", "").strip()
    if not valor:
        return timedelta(minutes=EXPIRACAO_PADRAO_MINUTOS)
    try:
        minutos = int(valor)
    except ValueError:
        minutos = 0
    if minutos < 1:
        raise RuntimeError(
            "JWT_ACCESS_TOKEN_EXPIRES_MINUTOS inválida: informe um número inteiro "
            f"de minutos maior ou igual a 1 (valor recebido: {valor!r})."
        )
    return timedelta(minutes=minutos)


def _origens_cors():
    valor = os.environ.get("CORS_ORIGINS", "")
    return [origem.strip() for origem in valor.split(",") if origem.strip()]


class Config:
    SQLALCHEMY_DATABASE_URI = _obrigatoria("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "connect_args": {"connect_timeout": 3},
    }
    JWT_SECRET_KEY = _chave_jwt()
    JWT_ACCESS_TOKEN_EXPIRES = _expiracao_token()
    CORS_ORIGINS = _origens_cors()
    DEBUG = os.environ.get("FLASK_DEBUG", "0").strip().lower() in ("1", "true", "yes", "on")
