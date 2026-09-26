# Imagem de produção da API "Rota Financeira" (Flask + gunicorn).
# Só as dependências de execução (requirements.txt); nenhum segredo entra na imagem:
# as variáveis chegam em tempo de execução (docker run --env-file .env.docker ...).
#
#   docker build -t rota-financeira-api .
#   docker run -d --name rota-financeira-api --network rota-financeira-net \
#       --env-file .env.docker -p 5000:5000 rota-financeira-api
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_ROOT_USER_ACTION=ignore \
    FLASK_APP=run.py

WORKDIR /app

# Dependências primeiro: esta camada só é refeita quando o requirements.txt muda.
COPY requirements.txt .
RUN pip install -r requirements.txt && pip check

# Os índices calculam "hoje" em America/Sao_Paulo (zoneinfo): o build falha se a base
# deixar de trazer os dados de fuso, em vez de a API quebrar só na primeira consulta.
RUN python -c "import zoneinfo; zoneinfo.ZoneInfo('America/Sao_Paulo')"

# Usuário sem privilégios (não roda como root).
RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin app

COPY --chown=app:app app ./app
COPY --chown=app:app migrations ./migrations
COPY --chown=app:app config.py run.py docker-entrypoint.sh ./

USER app
EXPOSE 5000

# /api/saude confere API e banco (503 se o banco cair); a imagem não tem curl.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/api/saude', timeout=4)"]

ENTRYPOINT ["./docker-entrypoint.sh"]
