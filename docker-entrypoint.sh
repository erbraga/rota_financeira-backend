#!/bin/sh
# Partida do contêiner da API.
#   sem argumentos: aplica as migrations e sobe o gunicorn (comportamento padrão);
#   com argumentos: executa o comando pedido, sem migrar (ex.: docker run ... flask routes, sh).
set -e

if [ "$#" -gt 0 ]; then
    exec "$@"
fi

echo "Aplicando as migrations do banco..."
flask db upgrade

echo "Iniciando o gunicorn na porta 5000 (${WEB_CONCURRENCY:-2} processos)..."
exec gunicorn run:app \
    --bind 0.0.0.0:5000 \
    --workers "${WEB_CONCURRENCY:-2}" \
    --timeout 30 \
    --no-control-socket \
    --access-logfile - \
    --error-logfile -
