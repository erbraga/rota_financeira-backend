# Dockerfile do backend e execução em contêiner (Etapa 11) — Spec

**Criado em:** 2026-09-26
**Status:** Implementada (2026-09-26) — imagem validada (banco descartável, BACEN real e banco de desenvolvimento) e percurso manual confirmado
**Origem:** Etapa 11 de `plano.md`; requisito R3 ("deve haver um Dockerfile para cada componente desenvolvido com todo o processo de implementação da solução em um contêiner Docker")

## Problema
A API só roda hoje na máquina do autor: ambiente virtual local (`.venv`, Python 3.12.3), `flask run`
e um PostgreSQL 18 num `docker run` avulso. Não há `Dockerfile`, `.dockerignore` nem `docker-compose.yml`,
então o **R3** não é atendido e quem clonar o repositório precisa montar o ambiente à mão (Python,
dependências, banco, migrations, variáveis). O `README.md` que existe é de outro projeto
(`manutencao-api`) e só será reescrito na Etapa 12.

Estado verificado (2026-09-26, lendo o código e experimentando no ambiente):

- **Aplicação:** `run.py` cria `app = create_app()`; `gunicorn run:app` já sobe a API (testado com
  2 workers: `/api/saude` responde `{"banco": "ok", "status": "ok"}` e `/apidocs/` 200). O `gunicorn`
  26.2.0 já está no `requirements.txt`, que traz só a stack de produção (`pytest` fica em
  `requirements-dev.txt`). O `psycopg[binary]` embute a `libpq`: não exige pacote de sistema.
- **Configuração** (`config.py`): tudo por variável de ambiente; `DATABASE_URL` e `JWT_SECRET_KEY` são
  **obrigatórias** e a aplicação **não sobe** sem elas, com mensagem clara (falha rápida, desejável num
  contêiner). O `python-dotenv` carrega um `.env` **se existir** e nunca sobrescreve o ambiente real.
  Opcionais: `JWT_ACCESS_TOKEN_EXPIRES_MINUTOS` (60), `CORS_ORIGINS`, `BACEN_URL_BASE`,
  `BACEN_TIMEOUT_SEGUNDOS` (8), `INDICES_TTL_HORAS` (12), `FLASK_DEBUG` (0). O `.env` local tem
  `DATABASE_URL` apontando para `localhost:5432` e `FLASK_DEBUG=1`: **não serve como está dentro do
  contêiner** (lá o banco é outro host).
- **Migrations:** `migrations/` (Flask-Migrate) com a revisão inicial; `flask db upgrade` é
  idempotente (sem mudanças quando já está na última). Exige `FLASK_APP=run.py` e o diretório
  `migrations/` relativo ao diretório de trabalho.
- **Banco de desenvolvimento em uso:** contêiner `rota-financeira-db` (`postgres:18`), porta
  `127.0.0.1:5432`, volume `rota_financeira_pgdata`, banco/usuário `emerson`; também abriga o `bd_test`
  dos testes de integração (Etapa 10). Qualquer coisa que a Etapa 11 crie **não pode** colidir com
  isso (nome, porta ou volume; dois PostgreSQL no mesmo volume corrompem os dados).
- **Fuso horário (herdado da Etapa 8):** "hoje" dos índices é calculado em `America/Sao_Paulo` com
  `zoneinfo`, que precisa dos dados de fuso do sistema. Verificado: a imagem `python:3.12-slim`
  (3.12.14, Debian, glibc 2.41) **tem** `/usr/share/zoneinfo` e resolve `America/Sao_Paulo`. Ela **não
  tem** `curl`/`wget` (o *healthcheck* precisa usar o próprio Python) e roda como `root` por padrão.
  O relógio do contêiner é UTC; o cálculo converte a partir de `datetime.now(timezone.utc)`, então
  não depende da variável `TZ`.
- **Ferramentas:** Docker 29.8.1 e Compose v5.5.1 instalados; o *pull* de imagens funciona (a rede está
  disponível). Existe uma imagem local `manutencao-api:latest` de outro projeto, sem relação.
- **Endpoint de saúde:** `GET /api/saude` faz `SELECT 1` e responde 503 se o banco cair — serve de
  *healthcheck* do contêiner.
- **Porta:** `flask run` usa 5000, e o README antigo também (`-p 5000:5000`); o frontend (outro
  repositório) aponta para a API por HTTP, e o CORS libera `localhost:5173` e `:3000`.

## Objetivo
Empacotar o backend numa imagem Docker reproduzível e de produção (só as dependências de execução,
sem segredos, sem usuário `root`, com verificação de saúde) que, apontada para um PostgreSQL por
variável de ambiente, migra o banco e sobe a API, sem mexer no ambiente de desenvolvimento existente.

## Fora de escopo
- **`docker-compose.yml`** (decisão 1: só o `Dockerfile`): o PostgreSQL **não** faz parte da pilha
  desta etapa; a API o encontra por `DATABASE_URL`, e o README (Etapa 12) ensina a subir o banco.
- Publicar a imagem em registro (Docker Hub, GHCR) e automatizar build/deploy (CI/CD).
- HTTPS, proxy reverso (nginx/Traefik), domínio, balanceamento, mais de uma réplica da API.
- Dockerfile do **frontend** (outro repositório) e orquestração dos dois juntos.
- Backup do banco, ajuste fino do PostgreSQL, Kubernetes.
- Alterar código da aplicação, contrato das rotas, schema do banco ou `requirements.txt`
  (sem migration nem dependência nova, salvo decisão 5 abaixo).
- O `README.md` (Etapa 12): esta etapa deixa os comandos prontos e comentados nos arquivos; o
  README os documenta depois.
- Rodar a suíte de testes dentro do contêiner (ver decisão 4).
- Reescrever ou remover os 1055 testes existentes.

## Proposta

### Arquivos novos (raiz do repositório)
```
Dockerfile               # imagem de produção da API
.dockerignore            # mantém fora da imagem: .venv, .env*, .git, tests, docs, tmp, caches, CLAUDE.md...
docker-entrypoint.sh     # migra o banco e sobe o gunicorn (decisão 2)
.env.docker.example      # modelo das variáveis do contêiner (decisão 6)
```
`.gitignore` passa a ignorar o `.env.docker` real. Nenhum arquivo de código muda.

### Imagem (`Dockerfile`)
- Base **`python:3.12-slim`** (mesma versão do ambiente de desenvolvimento); variáveis
  `PYTHONDONTWRITEBYTECODE=1`, `PYTHONUNBUFFERED=1`, `PIP_NO_CACHE_DIR=1`, `FLASK_APP=run.py`.
- Camadas pensadas para cache: copia só o `requirements.txt` e instala (**apenas produção**), depois
  copia `app/`, `migrations/`, `config.py`, `run.py` e o *entrypoint*. **Não** entram `tests/`, `docs/`,
  `tmp/`, `.env`, `CLAUDE.md`, `.claude/`, `requirements-dev.txt` (`.dockerignore`).
- **Trava de fuso:** um `RUN` que importa `zoneinfo` e resolve `America/Sao_Paulo` — o *build* falha
  se a base deixar de trazer os dados de fuso (decisão 5).
- Usuário **não-root** (uid fixo) dono de `/app`; `EXPOSE 5000`.
- `HEALTHCHECK` em Python puro (`urllib`) sobre `GET /api/saude` (sem `curl` na imagem), com período de
  carência para a migração.
- `ENTRYPOINT` no script: aplica as migrations (decisão 2) e faz `exec gunicorn run:app` (para receber
  os sinais do Docker), escutando `0.0.0.0:5000`, `--workers` = `WEB_CONCURRENCY` (padrão 2),
  `--timeout 30` (acima dos 8 s de timeout do BACEN), *access log* e *error log* na saída padrão.
- **Nenhum segredo na imagem** (nem `JWT_SECRET_KEY` nem senha de banco): tudo entra em tempo de execução
  por `--env-file`; sem `JWT_SECRET_KEY`/`DATABASE_URL` o contêiner sai com a mensagem clara da `config.py`.

### Fluxo de uso (o que os arquivos devem permitir)
1. `docker build -t rota-financeira-api .`
2. Um PostgreSQL acessível pelo contêiner (o `docker run` do `CLAUDE.md`, ou outro) e um
   `.env.docker` local com `DATABASE_URL` apontando para ele (decisão 3), `JWT_SECRET_KEY`, `CORS_ORIGINS`
   e `FLASK_DEBUG=0`.
3. Rede (uma vez): `docker network create rota-financeira-net` e `docker network connect
   rota-financeira-net rota-financeira-db`. Depois: `docker run -d --name rota-financeira-api --network
   rota-financeira-net --env-file .env.docker -p 5000:5000 rota-financeira-api`; `docker logs
   rota-financeira-api` mostra a migração e o gunicorn.
4. `http://localhost:5000/apidocs/` abre; `docker stop`/`docker start` preservam os dados (que vivem no
   banco, não no contêiner da API).

### Casos de borda relevantes
- **Banco fora do ar ao subir:** o `flask db upgrade` falha e o contêiner **sai com erro visível** (sem
  ficar de pé sem banco); com `--restart unless-stopped` o Docker tenta de novo.
- **Banco cai com a API no ar:** `/api/saude` responde 503, o `HEALTHCHECK` marca `unhealthy`, o processo
  não cai (as demais rotas dão o 500 genérico já registrado como débito).
- **Reinício com o banco já migrado:** o `upgrade` é idempotente (não altera nada).
- **`.env` do desenvolvimento:** fora da imagem (`.dockerignore`); o `DATABASE_URL` dele (host
  `localhost`) **não vale** dentro do contêiner, por isso o arquivo de variáveis próprio (decisão 6).
- **Fuso:** UTC no contêiner não afeta os índices (o cálculo usa `America/Sao_Paulo` explicitamente).
- **Porta 5000 ocupada no host** (por um `flask run` esquecido): trocar o lado esquerdo de `-p`.
- **CORS:** o frontend precisa estar em `CORS_ORIGINS` do arquivo de variáveis.

## Decisões em aberto
1. ~~**Só `Dockerfile` ou também `docker-compose.yml`**~~ — **RESOLVIDA (2026-09-26): (b)**: só o
   `Dockerfile` (mais `.dockerignore` e o *entrypoint*); **sem `docker-compose.yml`**. O PostgreSQL não
   entra na pilha desta etapa: a API o alcança por `DATABASE_URL`, e o README (Etapa 12) documenta o
   `docker run` do banco e da API. O R3 fica atendido (um Dockerfile por componente desenvolvido).
2. ~~**Como as migrations rodam no contêiner**~~ — **RESOLVIDA (2026-09-26): (a)**: o
   *entrypoint* roda `flask db upgrade` a cada partida e depois `exec gunicorn`; a API só fica de pé com o
   banco migrado; banco fora do ar → o contêiner sai com erro visível (e `--restart unless-stopped`
   tenta de novo); o `upgrade` é idempotente. Sem `SKIP_MIGRATIONS` e sem várias réplicas (fora de escopo).
3. ~~**Como o contêiner da API alcança o PostgreSQL**~~ — **RESOLVIDA (2026-09-26): (a)**: uma
   **rede Docker própria** (`docker network create rota-financeira-net`), à qual se liga o contêiner do banco
   (`docker network connect rota-financeira-net rota-financeira-db`, sem recriá-lo nem mexer nos dados) e a
   API (`--network rota-financeira-net`); o `DATABASE_URL` do `.env.docker` usa o **nome do contêiner do
   banco** como host (`...@rota-financeira-db:5432/...`). Sem `--network host`.
4. ~~**Testes dentro do Docker**~~ — **RESOLVIDA (2026-09-26): (a)**: fora de escopo; a imagem é
   só de produção (sem `pytest`) e os testes continuam no host, contra o `bd_test`; a validação do
   contêiner é o fluxo completo por HTTP dos critérios de aceite. Sem estágio `teste`.
5. ~~**Garantia dos dados de fuso (`zoneinfo`)**~~ — **RESOLVIDA (2026-09-26): (a)**: confiar no
   `tzdata` do Debian da imagem base (verificado) e **falhar o *build*** se `America/Sao_Paulo` não resolver
   (`RUN` de trava no `Dockerfile`); sem o pacote Python `tzdata` e sem dependência nova.
6. ~~**Onde ficam as variáveis do contêiner**~~ — **RESOLVIDA (2026-09-26): (a)**: um arquivo
   **`.env.docker`** local, ignorado pelo git, com o `DATABASE_URL` do contêiner (host `rota-financeira-db`
   na rede Docker), `JWT_SECRET_KEY`, `CORS_ORIGINS`, `FLASK_DEBUG=0` e as opcionais, usado com
   `--env-file`; o `.env.docker.example` é versionado, sem segredos; a senha do banco fica só no arquivo
   local, nunca na linha de comando.

## Critérios de aceite
- [x] `docker build` da raiz gera a imagem **sem erro e sem `.env`**; a imagem não contém `tests/`, `docs/`,
      `tmp/`, `.env*`, `CLAUDE.md` nem `requirements-dev.txt`, e o `pip` instalou **só** o `requirements.txt`
      (`pytest` ausente); nenhum segredo aparece em `docker history` nem nos arquivos da imagem.
- [x] O contêiner roda como **usuário não-root**, expõe a 5000 e tem `HEALTHCHECK` funcionando (sem
      `curl`); dentro dele `zoneinfo` resolve `America/Sao_Paulo` (e o *build* falharia se não resolvesse).
- [x] Com um PostgreSQL vazio e o `.env.docker` preenchido, `docker run` **migra o banco** (a tabela
      `alembic_version` na revisão atual), o contêiner fica `healthy`, `GET /api/saude` → `ok` e
      `/apidocs/` → 200 pela porta publicada.
- [x] **Fluxo completo no contêiner:** registrar → login → criar simulação → 3 financiamentos (4º → 409) →
      `/resultado` (números da spec da Etapa 7) → `/parcelas` → `GET /api/indices/cdi` e `ipca` (200 com
      o BACEN real, `serie_sgs` 4389 e 13522) → exclusões.
- [x] Os dados **persistem** a `docker stop`/`start` e à recriação do contêiner da API (vivem no banco);
      reiniciar com o banco já migrado não altera o schema.
- [x] **Falhas explícitas:** sem `JWT_SECRET_KEY` (ou `DATABASE_URL`) o contêiner **sai** com a mensagem
      clara da `config.py`; com o banco inacessível ao subir, sai com erro visível da migração; com o
      banco parado depois de no ar, a API fica `unhealthy` e `/api/saude` responde 503, sem derrubar
      o processo.
- [x] O ambiente de desenvolvimento **não é afetado**: o contêiner `rota-financeira-db` (dados e volume
      `rota_financeira_pgdata`) só ganha a ligação à rede de teste se a decisão 3 for (a); as 4 tabelas do banco
      `emerson` seguem vazias e o `bd_test` intacto; a validação usa um banco descartável.
- [x] `FLASK_DEBUG` fica 0 no contêiner; o CORS aceita as origens do `.env.docker` e rejeita as demais;
      trocar o lado esquerdo de `-p` muda a porta publicada.
- [x] `pytest` completo continua verde (1055 testes) e `flask db migrate` sem mudanças;
      `requirements.txt` e `requirements-dev.txt` inalterados (salvo a decisão 5-b); nenhum segredo em
      arquivo versionável (`.env.docker` no `.gitignore`); `plano.md` e `CLAUDE.md` atualizados (arquivos
      Docker, comandos, variáveis, coexistência com o banco de desenvolvimento).

---

## Plano de Implementação

Tarefas na ordem de execução. Nenhuma faz `git add`/`commit`/`push` (só quando você pedir).
Pré-requisitos: Docker em execução, `.venv` ativo, raiz do projeto como diretório de trabalho, a imagem
`python:3.12-slim` já baixada (foi na exploração) e acesso à rede (BACEN real nas Tarefas 5 e 9). A
validação é feita com **recursos descartáveis** nomeados `rf-validacao-*` (rede, banco PostgreSQL, API),
um arquivo de variáveis **fora do repositório** (diretório temporário da sessão, com uma senha aleatória
gerada na hora e nunca impressa) e a porta **5100** do host (para não colidir com um `flask run` na
5000); ao fim tudo isso é removido, e o banco de desenvolvimento só é tocado na Tarefa 7 (somente leitura).

Detalhes de projeto que o plano fixa (não estavam explícitos na spec):
- **`docker-entrypoint.sh`** (`#!/bin/sh`, `set -e`): **sem argumentos**, imprime uma linha de log, roda
  `flask db upgrade` e faz `exec gunicorn run:app --bind 0.0.0.0:5000 --workers "${WEB_CONCURRENCY:-2}"
  --timeout 30 --access-logfile - --error-logfile -`; **com argumentos** (`docker run ... flask routes`,
  `sh`), faz `exec "$@"` sem migrar — útil para depurar sem subir o servidor.
- **`Dockerfile`:** `python:3.12-slim`; `ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
  PIP_NO_CACHE_DIR=1 FLASK_APP=run.py`; `WORKDIR /app`; `pip install -r requirements.txt` seguido de
  `pip check` (o build falha com dependências quebradas); trava de fuso (`RUN python -c "import zoneinfo;
  zoneinfo.ZoneInfo('America/Sao_Paulo')"`); usuário de sistema `app` (uid 10001, sem *shell* de login) dono
  de `/app` e `USER app`; `EXPOSE 5000`; `HEALTHCHECK` (`--interval=30s --timeout=5s --start-period=30s
  --retries=3`) que chama `GET /api/saude` com `urllib` (status diferente de 200, inclusive o 503, sai com
  código 1); `ENTRYPOINT ["./docker-entrypoint.sh"]`. Etiqueta da imagem: `rota-financeira-api`.
- **`.dockerignore`:** `.venv`, `.git`, `.gitignore`, `.env`, `.env.*` (com exceção **nenhuma**: o
  `.env.docker.example` também fica de fora), `tests`, `docs`, `tmp`, `migrations/__pycache__` e todo
  `__pycache__`, `.pytest_cache`, `.vscode`, `.idea`, `.claude`, `CLAUDE.md`, `*.md`, `pytest.ini`,
  `requirements-dev.txt`, `requisitos back-end.md`, `pendencias.md`, `Dockerfile` e `.dockerignore`.
- **`.env.docker.example`:** `DATABASE_URL` com o host `rota-financeira-db` e a senha como marcador
  (`troque-esta-senha`), `JWT_SECRET_KEY=troque-esta-chave`, `CORS_ORIGINS` do frontend, `FLASK_DEBUG=0` e
  as opcionais comentadas (`JWT_ACCESS_TOKEN_EXPIRES_MINUTOS`, `WEB_CONCURRENCY`, BACEN, TTL), no estilo do
  `.env.example`; o `.gitignore` recebe a linha `.env.docker`.
- **Segredos:** a senha do banco e a chave JWT só existem no arquivo local do usuário e nos arquivos
  temporários da validação; nada disso entra na imagem, no histórico de comandos impresso ou no repositório.
- **Se um passo revelar defeito real** (na aplicação ou nas premissas da spec), a tarefa **para** e o
  problema é relatado antes de qualquer correção.

### Tarefa 1 — Arquivos de configuração do contexto de build
- **Arquivos:** `.dockerignore`, `.env.docker.example`, `.gitignore`
- **Mudança:** criar o `.dockerignore` e o `.env.docker.example` como acima e acrescentar `.env.docker` ao
  `.gitignore`.
- **Validar:** `git check-ignore -v .env.docker` mostra a regra e `git check-ignore .env.docker.example`
  **não** ignora o exemplo; busca no `.env.docker.example` por qualquer valor real (deve ter só marcadores);
  o `.gitignore` mantém as regras antigas (diff só com a linha nova).

### Tarefa 2 — Script de partida
- **Arquivos:** `docker-entrypoint.sh` (executável)
- **Mudança:** o script acima, com `chmod +x`.
- **Validar:** `sh -n docker-entrypoint.sh` (sintaxe); `ls -l` mostra o bit de execução; teste do fluxo com
  argumentos e sem eles fica para a Tarefa 4 (dentro da imagem).

### Tarefa 3 — Imagem
- **Arquivos:** `Dockerfile`
- **Mudança:** o `Dockerfile` acima.
- **Validar:** `docker build -t rota-financeira-api .` sem erro; o contexto enviado é pequeno (mostrar o
  tamanho do "transferring context"); conferir na imagem, com `docker run --rm --entrypoint sh`: `id` (uid
  10001, não-root), `ls -A /app` (só `app`, `migrations`, `config.py`, `run.py`, `docker-entrypoint.sh`; **sem**
  `tests`, `docs`, `tmp`, `.env*`, `CLAUDE.md`, `requirements-dev.txt`), `pip list` (sem `pytest`), o
  `zoneinfo` resolvendo `America/Sao_Paulo`, e o tamanho da imagem; **sensibilidade da trava**: numa cópia
  do `Dockerfile` no diretório temporário trocar o fuso por um nome inexistente e ver o `docker build`
  **falhar** com a mensagem de fuso.

### Tarefa 4 — Subida contra um banco descartável
- **Arquivos:** nenhum (recursos `rf-validacao-*` e um arquivo de variáveis temporário)
- **Mudança:** criar a rede `rf-validacao-net`, um PostgreSQL `rf-validacao-db` (`postgres:18`, sem porta
  publicada, sem volume nomeado) e o arquivo de variáveis temporário (host `rf-validacao-db`, senha
  aleatória, `FLASK_DEBUG=0`); subir `rf-validacao-api` com `--network`, `--env-file` e `-p 5100:5000`.
- **Validar:** `docker logs` mostra a migração e o gunicorn, sem Traceback; `docker ps` chega a `healthy`;
  `GET /api/saude` → `ok` e `/apidocs/` → 200 pela 5100; no banco, `alembic_version` na revisão atual e as 4
  tabelas vazias; `docker exec rf-validacao-api id` (não-root) e `docker exec ... printenv FLASK_DEBUG` → 0;
  `docker run --rm --entrypoint ... rota-financeira-api flask routes` (o modo com argumentos, **sem** migrar)
  lista as 16 rotas.

### Tarefa 5 — Fluxo completo dentro do contêiner
- **Arquivos:** nenhum (script descartável no diretório temporário)
- **Mudança:** um script com `requests` contra `http://localhost:5100`: registrar → login → simulação → 3
  financiamentos (4º → 409) → `/resultado` (custos 137.128,07 e 124.737,50, fundo 108.410,78 da spec) →
  `/parcelas` → `GET /api/indices/cdi` e `ipca` **com o BACEN real** (200, séries 4389 e 13522) → `?periodo=13m`
  (422) → `selic` (404) → exclusões; conferência de CORS (preflight de `localhost:5173` com `Authorization`,
  origem estranha sem cabeçalhos).
- **Validar:** todas as verificações passam; o log do contêiner sem Traceback; usuário, simulações e cache
  removidos no fim (`TRUNCATE` pelo `psql` do banco descartável).

### Tarefa 6 — Falhas e persistência
- **Arquivos:** nenhum
- **Mudança:** exercitar, com contêineres descartáveis `rf-validacao-*`: (1) sem `JWT_SECRET_KEY`; (2) sem
  `DATABASE_URL`; (3) `DATABASE_URL` com host inexistente (banco inacessível ao subir); (4) `docker stop` do
  banco com a API no ar; (5) `docker stop`/`start` e **recriação** (`rm` + `run`) do contêiner da API; (6)
  outra porta publicada (`-p 5200:5000`).
- **Validar:** (1) e (2) saem com código ≠ 0 e a mensagem da `config.py`; (3) sai com erro visível da
  migração (sem servidor de pé); (4) `/api/saude` → 503, o contêiner vira `unhealthy` e o processo não cai;
  religado o banco, volta a `healthy`; (5) os dados criados antes continuam lá e o `flask db upgrade`
  reexecutado não altera o schema (`alembic_version` igual); (6) responde na nova porta.

### Tarefa 7 — Roteiro documentado com o banco de desenvolvimento (somente leitura)
- **Arquivos:** nenhum
- **Mudança:** seguir o fluxo da decisão 3 com o banco real: `docker network create rota-financeira-net`,
  `docker network connect rota-financeira-net rota-financeira-db`, um arquivo de variáveis temporário com
  `DATABASE_URL` apontando para `rota-financeira-db` (senha lida do `.env` local, sem imprimir), `docker run`
  da API na 5100 — e **apenas** `GET /api/saude`, `/apidocs/` e `GET /api/indices/selic` (404); depois
  parar a API, `docker network disconnect` e remover a rede.
- **Validar:** a API sobe com o banco de desenvolvimento (migração sem mudanças), o `rota-financeira-db`
  continua `Up`, com o volume `rota_financeira_pgdata` e a porta `127.0.0.1:5432` como antes; o banco
  `emerson` segue com as 4 tabelas vazias (nenhuma escrita) e o `bd_test` intacto; a suíte `pytest -m
  integracao` continua passando logo depois (a conexão pelo host não foi afetada pela rede extra).

### Tarefa 8 — Regressão e limpeza
- **Arquivos:** nenhum
- **Mudança:** nenhuma; verificação e remoção dos recursos descartáveis.
- **Validar:** `pytest` completo (1055) verde; `flask db migrate` sem mudanças; `pip check`;
  `requirements.txt` e `requirements-dev.txt` inalterados; **sem segredo na imagem** (`docker history
  --no-trunc` e busca da senha e da chave da validação no sistema de arquivos da imagem: nada); `git status`
  só com o esperado (`Dockerfile`, `.dockerignore`, `docker-entrypoint.sh`, `.env.docker.example`,
  `.gitignore`, `plano.md` e a spec); removidos os contêineres, a rede, o banco e os arquivos
  temporários `rf-validacao-*` (`docker ps -a`, `docker network ls` e `docker volume ls` sem sobras); a
  imagem `rota-financeira-api` permanece (é a entrega).

### Tarefa 9 — Verificação manual (sua)
- **Arquivos:** nenhum
- **Mudança:** entregar o roteiro para você repetir o processo **do zero**: copiar
  `.env.docker.example` para `.env.docker` e preenchê-lo (senha do banco de desenvolvimento e uma chave
  JWT), `docker build`, criar/ligar a rede, `docker run`, abrir `/apidocs/` e fazer o percurso curto
  (registrar, login, criar simulação, resultado, índices), e como parar e limpar.
- **Validar:** você confirma ("funcionou"); depois desligo o contêiner e desfaço a rede, se você pedir.

### Tarefa 10 — Documentação
- **Arquivos:** `plano.md`, `CLAUDE.md`, esta spec
- **Mudança:**
  - `plano.md`: marcar a Etapa 11 como concluída, com as decisões (sem compose, migração no *entrypoint*,
    rede própria, `.env.docker`, trava do fuso) e o que passa para a Etapa 12 (o README documenta os
    comandos: `docker build`, rede, `.env.docker`, `docker run`, portas, parada e limpeza);
  - `CLAUDE.md`: estrutura (arquivos Docker), Stack (Docker) e a seção "Banco de dados"/"Testes e
    validação" com o roteiro `docker build`/`network`/`run`, o `.env.docker` (e que ele **não** entra no
    git nem na imagem), a regra "imagem só de produção, sem segredos, usuário não-root", a porta 5000 do
    contêiner, o healthcheck e o "Estado atual" (Etapa 11 concluída; sem compose; R3 atendido);
  - esta spec: marcar os critérios de aceite e o status como implementada.
- **Validar:** reler os três arquivos e conferir que não restam menções a "Dockerfile pendente" nem a
  `docker-compose` como plano.

### Tarefa 11 — Conferência final
- **Arquivos:** nenhum
- **Mudança:** nenhuma; verificação de todos os critérios de aceite.
- **Validar:** percorrer a lista de critérios, informar o que passou e o que dependeu da sua verificação
  manual e da rede real, mostrar o resultado do `pytest` e o `git status --short` final e aguardar você
  pedir o commit.

---
*Depois de aprovada, esta spec vira a base do PLANO — não escrever
código antes disso.*
