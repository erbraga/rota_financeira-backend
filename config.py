import math
import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

# Não sobrescreve variáveis que já estejam definidas no ambiente real.
load_dotenv(Path(__file__).resolve().parent / ".env")

CHAVE_JWT_EXEMPLO = "troque-esta-chave"
TAMANHO_MINIMO_CHAVE_JWT = 32
EXPIRACAO_PADRAO_MINUTOS = 60
BACEN_URL_BASE_PADRAO = "https://api.bcb.gov.br/dados/serie/bcdata.sgs"
BACEN_TIMEOUT_PADRAO_SEGUNDOS = 8
INDICES_TTL_PADRAO_HORAS = 12


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


def _url_bacen():
    valor = os.environ.get("BACEN_URL_BASE", "").strip()
    if not valor:
        return BACEN_URL_BASE_PADRAO
    if not valor.startswith(("http://", "https://")):
        raise RuntimeError(
            "BACEN_URL_BASE inválida: informe uma URL começando com http:// ou https:// "
            f"(valor recebido: {valor!r})."
        )
    return valor.rstrip("/")


def _numero_positivo(nome, padrao):
    """Número decimal positivo e finito (aceita fração: TTL de 0.001 h serve aos testes)."""
    valor = os.environ.get(nome, "").strip()
    if not valor:
        return padrao
    try:
        numero = float(valor)
    except ValueError:
        numero = 0
    if not (math.isfinite(numero) and numero > 0):
        raise RuntimeError(
            f"{nome} inválida: informe um número maior que zero (valor recebido: {valor!r})."
        )
    return numero


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
    BACEN_URL_BASE = _url_bacen()
    BACEN_TIMEOUT_SEGUNDOS = _numero_positivo("BACEN_TIMEOUT_SEGUNDOS", BACEN_TIMEOUT_PADRAO_SEGUNDOS)
    INDICES_TTL_HORAS = _numero_positivo("INDICES_TTL_HORAS", INDICES_TTL_PADRAO_HORAS)
    CORS_ORIGINS = _origens_cors()
    DEBUG = os.environ.get("FLASK_DEBUG", "0").strip().lower() in ("1", "true", "yes", "on")
