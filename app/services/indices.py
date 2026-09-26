"""Índices econômicos do BACEN (CDI e IPCA): cache em `indices_economicos_cache`.

Política (spec da Etapa 8): sob demanda, sem agendador. Se o cache do índice é mais novo
que o TTL, responde só com o banco; senão consulta o BACEN (janela fixa de 60 meses até
hoje), grava e responde. Se o BACEN falha, serve o cache existente marcado como
desatualizado, ou levanta `IndicesIndisponiveis` (503) se não há nada em cache.
"""
import calendar
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from flask import current_app

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert

from app.extensions import db
from app.integrations.bacen import BacenIndisponivel, buscar_serie
from app.models import Indice, IndiceEconomicoCache

logger = logging.getLogger(__name__)

FUSO = ZoneInfo("America/Sao_Paulo")
JANELA_MESES = 60  # o maior `periodo` permitido: uma consulta ao BACEN cobre todos
PERIODOS = {"1m": 1, "3m": 3, "6m": 6, "12m": 12, "24m": 24, "60m": 60}
PERIODO_PADRAO = "12m"
RESTRICAO_UNICA = "uq_indices_economicos_cache_indice_data_referencia"


@dataclass(frozen=True)
class SerieSgs:
    codigo: int
    descricao: str
    unidade: str


# Só CDI e IPCA (a Selic ficou de fora por decisão do autor); ambos já em % a.a.
INDICES = {
    Indice.CDI: SerieSgs(4389, "Taxa CDI anualizada, base 252", "% a.a."),
    Indice.IPCA: SerieSgs(13522, "IPCA acumulado em 12 meses", "% a.a."),
}
INDICES_POR_URL = {"cdi": Indice.CDI, "ipca": Indice.IPCA}  # só minúsculas: `CDI` → 404


def hoje(agora=None):
    """Data de hoje em Brasília (as datas do SGS são de Brasília). `agora` é para os testes."""
    agora = agora or datetime.now(FUSO)
    return agora.astimezone(FUSO).date()


def meses_atras(data, meses):
    """`data` menos `meses` meses; dia 31 e 29/02 caem no último dia do mês de destino."""
    indice = data.year * 12 + (data.month - 1) - meses
    ano, mes = divmod(indice, 12)
    mes += 1
    return date(ano, mes, min(data.day, calendar.monthrange(ano, mes)[1]))


def gravar_serie(indice, linhas):
    """Upsert das linhas `(data, Decimal)`: `ON CONFLICT` na restrição única, idempotente.

    As linhas vão em ordem crescente de data, sempre a mesma, para duas atualizações
    simultâneas não travarem uma à outra (deadlock). Renova `atualizado_em`.
    """
    linhas = sorted(linhas)
    if not linhas:
        return 0
    valores = [
        {"indice": indice, "data_referencia": data, "valor": valor} for data, valor in linhas
    ]
    comando = insert(IndiceEconomicoCache).values(valores)
    comando = comando.on_conflict_do_update(
        constraint=RESTRICAO_UNICA,
        set_={"valor": comando.excluded.valor, "atualizado_em": func.now()},
    )
    db.session.execute(comando)
    db.session.commit()
    return len(linhas)


def ultima_atualizacao(indice):
    """Maior `atualizado_em` das linhas do índice (None se o cache está vazio)."""
    return db.session.scalar(
        db.select(func.max(IndiceEconomicoCache.atualizado_em)).where(
            IndiceEconomicoCache.indice == indice
        )
    )


def ler_pontos(indice, inicio, fim):
    """Pontos `(data, Decimal)` de `inicio` a `fim` (inclusive), em ordem crescente."""
    consulta = (
        db.select(IndiceEconomicoCache.data_referencia, IndiceEconomicoCache.valor)
        .where(
            IndiceEconomicoCache.indice == indice,
            IndiceEconomicoCache.data_referencia >= inicio,
            IndiceEconomicoCache.data_referencia <= fim,
        )
        .order_by(IndiceEconomicoCache.data_referencia)
    )
    return [(data, valor) for data, valor in db.session.execute(consulta)]


def ler_sugestao(indice, ate):
    """O valor mais recente com data até `ate`, independente do período pedido."""
    consulta = (
        db.select(IndiceEconomicoCache.data_referencia, IndiceEconomicoCache.valor)
        .where(IndiceEconomicoCache.indice == indice, IndiceEconomicoCache.data_referencia <= ate)
        .order_by(IndiceEconomicoCache.data_referencia.desc())
        .limit(1)
    )
    linha = db.session.execute(consulta).first()
    return (linha[0], linha[1]) if linha else None


class IndicesIndisponiveis(Exception):
    """O BACEN falhou e não há nada em cache (a rota responde 503)."""


@dataclass(frozen=True)
class ResultadoIndice:
    indice: Indice
    serie: SerieSgs
    sugestao: tuple | None  # (data, valor) mais recente até hoje
    inicio: date
    fim: date
    pontos: list  # [(data, valor)] do período, em ordem crescente
    atualizado_em: datetime | None
    desatualizado: bool


def _cache_valido_em(ultima, agora, ttl_horas):
    return (agora - ultima) <= timedelta(hours=ttl_horas)


def _cache_valido(indice, agora, ttl_horas):
    ultima = ultima_atualizacao(indice)
    if ultima is None:
        return False, None
    return _cache_valido_em(ultima, agora, ttl_horas), ultima


def _atualizar(indice, data_de_hoje, config):
    """Consulta o BACEN (janela de 60 meses até hoje) e grava. Levanta BacenIndisponivel;
    lista vazia ("sem dados") não grava nada nem renova o cache."""
    linhas = buscar_serie(
        INDICES[indice].codigo,
        meses_atras(data_de_hoje, JANELA_MESES),
        data_de_hoje,
        config["BACEN_URL_BASE"],
        config["BACEN_TIMEOUT_SEGUNDOS"],
    )
    return gravar_serie(indice, linhas)


def consultar_indice(indice, periodo, agora=None):
    """Série do período e sugestão do índice, com cache, TTL e fallback (ver o módulo).

    `periodo`: uma chave de `PERIODOS` ("12m"); `agora`: instante, para os testes.
    """
    agora = agora or datetime.now(timezone.utc)
    data_de_hoje = hoje(agora)
    config = current_app.config
    valido, ultima = _cache_valido(indice, agora, config["INDICES_TTL_HORAS"])
    desatualizado = False
    if not valido:
        try:
            _atualizar(indice, data_de_hoje, config)
        except BacenIndisponivel:
            db.session.rollback()
            if ultima is None:
                raise IndicesIndisponiveis() from None
            desatualizado = True  # serve o cache existente, marcado como desatualizado
        else:
            ultima = ultima_atualizacao(indice)
            if ultima is None:  # BACEN sem dados e cache vazio
                raise IndicesIndisponiveis()
            # Atualizado agora: novo por definição. Se o BACEN respondeu "sem dados" (nada
            # gravado) e o cache antigo continua vencido, `ultima` segue velha.
            desatualizado = not _cache_valido_em(ultima, agora, config["INDICES_TTL_HORAS"])
    inicio = meses_atras(data_de_hoje, PERIODOS[periodo])
    return ResultadoIndice(
        indice=indice,
        serie=INDICES[indice],
        sugestao=ler_sugestao(indice, data_de_hoje),
        inicio=inicio,
        fim=data_de_hoje,
        pontos=ler_pontos(indice, inicio, data_de_hoje),
        atualizado_em=ultima,
        desatualizado=desatualizado,
    )
