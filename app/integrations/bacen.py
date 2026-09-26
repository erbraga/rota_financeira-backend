"""Cliente do SGS (Séries Temporais do Banco Central do Brasil).

Sem Flask nem banco. Comportamentos da API real, verificados em 2026-09-25:
- a resposta é uma lista `[{"data": "24/09/2026", "valor": "13.65"}]`, valor em texto;
- o `Content-Type` vem `text/html` mesmo com corpo JSON (não é conferido aqui);
- intervalo sem dados devolve HTTP 404 com `Value(s) not found` (não lista vazia);
- séries diárias aceitam no máximo 10 anos por consulta (senão HTTP 406);
- algumas séries (ex.: meta Selic) trazem linhas com datas futuras.
"""
import json
import logging
import re
from datetime import datetime, timedelta
from decimal import Decimal

import requests

logger = logging.getLogger(__name__)

JANELA_MAXIMA_DIAS = 3650  # 10 anos: acima disso o SGS responde HTTP 406

# Cabe em NUMERIC(12,6): até 6 dígitos inteiros e 6 decimais, com sinal opcional.
_VALOR = re.compile(r"-?\d{1,6}(\.\d{1,6})?")


class BacenIndisponivel(Exception):
    """Qualquer falha ao obter dados do BACEN. A mensagem é genérica (pode ir ao cliente);
    o motivo real fica em `motivo`, só para o log."""

    def __init__(self, motivo):
        super().__init__("Dados do Banco Central indisponíveis no momento")
        self.motivo = motivo


def formatar_data(data):
    return data.strftime("%d/%m/%Y")


def montar_consulta(url_base, codigo, inicio, fim):
    """URL e parâmetros de uma consulta por período (`dataInicial` e `dataFinal`)."""
    if inicio > fim:
        raise ValueError("A data inicial não pode ser posterior à final.")
    if (fim - inicio) > timedelta(days=JANELA_MAXIMA_DIAS):
        raise ValueError("O SGS aceita janelas de no máximo 10 anos em séries diárias.")
    url = f"{url_base.rstrip('/')}.{codigo}/dados"
    parametros = {
        "formato": "json",
        "dataInicial": formatar_data(inicio),
        "dataFinal": formatar_data(fim),
    }
    return url, parametros


def _linha(item):
    if not isinstance(item, dict):
        raise BacenIndisponivel("linha que não é objeto")
    texto_data, texto_valor = item.get("data"), item.get("valor")
    if not isinstance(texto_data, str) or not isinstance(texto_valor, str):
        raise BacenIndisponivel("linha sem data ou valor em texto")
    try:
        data = datetime.strptime(texto_data, "%d/%m/%Y").date()
    except ValueError:
        raise BacenIndisponivel("data fora de dd/mm/aaaa") from None
    if not _VALOR.fullmatch(texto_valor):
        raise BacenIndisponivel("valor não numérico ou fora do formato esperado")
    return data, Decimal(texto_valor)


def interpretar_resposta(status, corpo, hoje):
    """Lista de `(data, Decimal)` em ordem crescente, sem datas futuras nem repetidas.

    HTTP 404 com `Value(s) not found` é "sem dados" (lista vazia). Qualquer outra falha
    (HTTP, JSON quebrado, formato, linha inválida) levanta `BacenIndisponivel`.
    """
    if status == 404:
        if "value(s) not found" in corpo.lower():
            return []
        raise BacenIndisponivel("HTTP 404")
    if status != 200:
        raise BacenIndisponivel(f"HTTP {status}")
    try:
        dados = json.loads(corpo)
    except ValueError:
        raise BacenIndisponivel("corpo que não é JSON") from None
    if not isinstance(dados, list):
        raise BacenIndisponivel("corpo JSON que não é lista")
    por_data = {}
    for item in dados:
        data, valor = _linha(item)
        if data <= hoje:
            por_data[data] = valor  # data repetida: vale a última
    return sorted(por_data.items())


def buscar_serie(codigo, inicio, fim, url_base, timeout):
    """Consulta uma série do SGS de `inicio` a `fim` (datas até hoje) e devolve `(data, Decimal)`.

    Qualquer falha (rede, timeout, HTTP, corpo inválido) vira `BacenIndisponivel`; o motivo
    real vai só para o log, sem URL nem corpo. Sem nova tentativa: quem chama decide.
    """
    url, parametros = montar_consulta(url_base, codigo, inicio, fim)
    try:
        resposta = requests.get(url, params=parametros, timeout=(timeout, timeout))
        # Decodifica como UTF-8: o Content-Type do SGS (text/html) faria o requests supor latin-1.
        corpo = resposta.content.decode("utf-8", errors="replace")
        return interpretar_resposta(resposta.status_code, corpo, fim)
    except requests.RequestException as erro:
        falha = BacenIndisponivel(type(erro).__name__)  # o texto do erro traz a URL: não vai ao log
    except BacenIndisponivel as erro:
        falha = erro
    logger.warning("BACEN indisponível (série %s): %s", codigo, falha.motivo)
    raise falha
