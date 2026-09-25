# Preparação do repositório e ambiente (Etapa 0) — Spec

**Criado em:** 2026-09-25
**Status:** Implementada em 2026-09-25
**Origem:** Etapa 0 de `plano.md`

## Problema
Antes de escrever a primeira linha do backend, o repositório e o ambiente de
desenvolvimento precisam estar prontos. O que foi verificado no projeto e na
máquina hoje:

**Repositório**
- Já existe um repositório Git na branch `main`, com `origin` em
  `https://github.com/erbraga/rota_financeira-backend.git`. O endereço responde
  HTTP 200 sem autenticação, ou seja, o repositório é **público** (R10).
- Há um único commit (`primeiro commit`) com só 3 arquivos: `.gitignore`,
  `README.md` (herdado de outro projeto, `manutencao-api`) e `requirements.txt`.
- O `.gitignore` atual ignora `.claude`, `CLAUDE.md`, `requisitos back-end.md`,
  `proposta-backend-api-rest.md`, `plano.md`, `pendencias.md`,
  `docs/specs/TEMPLATE.md` e `/tmp`. Não cobre `.env`, `instance/`,
  `.pytest_cache/` nem arquivos de IDE. A entrada `.docs/specs` parece ser
  erro de digitação de `docs/specs` (com ela, as specs novas **não** são
  ignoradas).
- Ainda não existe código de aplicação (`app/`, `config.py`, `run.py`).

**Ambiente da máquina**
- Python 3.12.3 e `venv` disponíveis; não há `.venv` no projeto.
- Docker 29.8.1 e Docker Compose v5.5.1 instalados, com o daemon ativo e
  nenhuma imagem de Postgres baixada.
- `psql` **não** está instalado e a porta 5432 está livre.
- A CLI `gh` não está instalada (não é necessária: o repositório já existe).
- Não existe `.env` nem `.env.example`.

**Pendências de decisão que travam as etapas seguintes:** Marshmallow vs.
Pydantic (Etapa 1) e Dockerfile isolado vs. docker-compose com Postgres
(Etapa 11).

## Objetivo
Deixar o repositório público organizado e o ambiente local funcionando —
Python com as dependências instaladas e um PostgreSQL acessível via
`DATABASE_URL` — de modo que a Etapa 1 comece direto no código Flask.

## Fora de escopo
- Qualquer código de aplicação (`app/`, `config.py`, `run.py`, models).
- `Dockerfile` e `docker-compose.yml` **da aplicação** (Etapa 11).
- Reescrever o `README.md` (Etapa 12).
- Criar tabelas, migrations ou `flask db init` (Etapas 1 e 2).
- Configurar o banco de **testes** (Etapa 10).
- Fazer `git commit`/`git push` — só quando você pedir.
- Instalar Marshmallow, Pydantic, pytest ou APScheduler.

## Proposta

### 1. Repositório Git / GitHub
- Manter o repositório e o `origin` existentes; não criar outro.
- Corrigir e completar o `.gitignore`:
  - **remover** `.docs/specs`, `proposta-backend-api-rest.md`, `plano.md` e
    `docs/specs/TEMPLATE.md` (passam a ser publicados);
  - **manter ignorados** `CLAUDE.md`, `.claude`, `requisitos back-end.md`
    (duas entradas, com e sem aspas — deixar uma só), `pendencias.md` e `/tmp`;
  - acrescentar `.env`, `instance/`, `.pytest_cache/` e pastas de IDE
    (`.vscode/`, `.idea/`);
  - manter `.venv` e `__pycache__/`.
- Nenhum dos arquivos que passam a ser publicados foi commitado antes, então
  não é preciso `git rm --cached`.

### 2. Ambiente Python
- Criar o ambiente virtual em `.venv` na raiz do projeto
  (`python3 -m venv .venv`) e ativá-lo.
- Instalar `requirements.txt` (9 dependências diretas) com `pip install -r`.
- Única dependência nova: `python-dotenv` (decisão 3), para o Flask carregar
  o `.env` automaticamente.

### 3. PostgreSQL local
- Como o Docker está disponível e o `psql` não, subir o Postgres em um
  container avulso (`docker run`, sem arquivo compose), com volume nomeado
  para persistir os dados e porta 5432 mapeada.
- Imagem `postgres:18` (versão major mais recente na imagem oficial; ver
  decisão 7). Banco `emerson`, usuário `emerson`; a senha de desenvolvimento fica
  **somente no `.env` local** (não versionado) e nunca aparece na spec, no
  plano, no README nem no `.env.example`.
- Na imagem do Postgres 18 o volume deve ser montado em
  `/var/lib/postgresql` (nas versões anteriores era `/var/lib/postgresql/data`).
- A validação da conexão usa o cliente dentro do container
  (`docker exec ... psql`) e, depois, uma conexão via `psycopg` a partir do
  `.venv` — que exercita também o driver que a aplicação vai usar.

### 4. Variáveis de ambiente
- Criar `.env.example` (versionado, sem segredos reais) com:
  - `DATABASE_URL=postgresql+psycopg://emerson:<senha>@localhost:5432/emerson`
    com senha-placeholder (o prefixo `+psycopg` é obrigatório por causa do driver escolhido);
  - `JWT_SECRET_KEY` (valor de exemplo óbvio, com nota de que deve ser trocado);
  - `CORS_ORIGINS` (ex.: `http://localhost:5173,http://localhost:3000`);
  - `FLASK_APP` / `FLASK_DEBUG`, se necessário.
- Criar o `.env` local a partir dele (não versionado).
- O `flask run` lê o `.env` automaticamente porque o `python-dotenv` será
  instalado.

### 5. Casos de borda
- Porta 5432 já ocupada por outro Postgres em outra máquina/sessão: usar outra
  porta no mapeamento e refletir na `DATABASE_URL`.
- Container reiniciado ou removido: dados só sobrevivem se o volume nomeado
  estiver montado; documentar isso no `README` na Etapa 12.
- `psycopg[binary]` sem wheel para a versão de Python usada: hoje há wheels
  para o Python 3.12, sem problema esperado.

## Decisões tomadas
Todas as decisões em aberto da versão de rascunho foram resolvidas em
2026-09-25:

1. **Repositório público:** publicar proposta, plano e specs
   (`proposta-backend-api-rest.md`, `plano.md`, `docs/specs/`, incluindo o
   `TEMPLATE.md`). Continuam ignorados `CLAUDE.md`, `.claude/` e
   `requisitos back-end.md`. A entrada `.docs/specs` é removida.
2. **Postgres local:** `docker run` avulso, sem arquivo compose.
3. **`.env`:** adicionar `python-dotenv` ao `requirements.txt`.
4. **Validação/serialização:** **Marshmallow**. A dependência só é instalada
   na Etapa 1, quando for usada.
5. **Dockerfile isolado vs. docker-compose:** adiado para a Etapa 11.
6. **Credenciais de desenvolvimento do banco:** banco `emerson`, usuário
   `emerson`. **Revisada em 2026-09-25:** a senha não pode ficar exposta no
   repositório público; ela existe apenas no `.env` local, e o
   `.env.example` traz só um placeholder.
7. **Versão do PostgreSQL:** o Postgres não tem versões "LTS"; foi adotada a
   major estável mais recente da imagem oficial, a **18** (`postgres:18`).
8. **README antigo:** permanece como está até a Etapa 12.

## Critérios de aceite
- [x] `.env` local não aparece no `git status`; `.env.example` aparece como
      arquivo novo versionável.
- [x] `.gitignore` sem `.docs/specs`, sem as entradas da proposta, do plano e
      do `TEMPLATE.md`; com `.env`, `instance/`, `.pytest_cache/`, IDEs,
      `.venv` e `__pycache__/`; `CLAUDE.md`, `.claude/` e
      `requisitos back-end.md` seguem ignorados (`git check-ignore -v`).
- [x] `requirements.txt` com `python-dotenv` e nenhuma outra dependência nova.
- [x] `.venv` criado; `pip install -r requirements.txt` termina sem erro e
      `pip check` não reporta conflitos.
- [x] `python -c "import flask, flask_sqlalchemy, flask_migrate, flask_jwt_extended, flask_cors, flasgger, psycopg, requests, dotenv"`
      executa sem erro dentro do `.venv`.
- [x] O container do Postgres 18 está de pé (`docker ps`) e responde a
      `SELECT version();` via `psql` dentro dele.
- [x] Uma conexão via `psycopg`, usando a `DATABASE_URL` do `.env`, executa
      `SELECT 1` a partir do `.venv`.
- [x] `.env.example` contém `DATABASE_URL`, `JWT_SECRET_KEY` e `CORS_ORIGINS`,
      sem nenhum segredo real (só placeholders, inclusive para a senha do banco).
- [x] Nenhum arquivo de código de aplicação foi criado.

---
*Esta spec vira a base do PLANO abaixo — não escrever código antes da
aprovação do plano.*

## Plano de Implementação

Tarefas na ordem de execução. Nenhuma cria código de aplicação, e nenhuma
faz `git add`/`commit`/`push` (só quando você pedir).

### Tarefa 1 — Ajustar o `.gitignore`
- **Arquivo:** `.gitignore`
- **Mudança:** remover `.docs/specs`, `proposta-backend-api-rest.md`,
  `plano.md`, `docs/specs/TEMPLATE.md` e a entrada duplicada
  `"requisitos back-end.md"` (com aspas); acrescentar `.env`, `instance/`,
  `.pytest_cache/`, `.vscode/` e `.idea/`.
- **Validar:** `git check-ignore -v CLAUDE.md .claude "requisitos back-end.md" .env`
  lista os quatro como ignorados; `git status --short` mostra
  `proposta-backend-api-rest.md`, `plano.md` e `docs/` como novos, e
  **não** mostra `CLAUDE.md` nem `.claude/`.

### Tarefa 2 — Adicionar `python-dotenv` ao `requirements.txt`
- **Arquivo:** `requirements.txt`
- **Mudança:** acrescentar `python-dotenv==1.2.3` (última versão no PyPI hoje).
  Justificativa: o Flask só carrega o `.env` automaticamente com ele.
- **Validar:** o arquivo tem 10 linhas e nenhuma outra dependência nova.

### Tarefa 3 — Criar o `.venv` e instalar as dependências
- **Arquivos:** `.venv/` (ignorado pelo Git)
- **Mudança:** `python3 -m venv .venv`, ativar e
  `pip install -r requirements.txt`.
- **Validar:** `pip check` sem conflitos e o `python -c "import ..."` dos
  critérios de aceite sem erro.

### Tarefa 4 — Subir o PostgreSQL 18 em container
- **Arquivos:** nenhum no projeto.
- **Mudança:** `set -a; source .env; set +a` e `docker run ... -e POSTGRES_USER -e POSTGRES_PASSWORD -e POSTGRES_DB ... postgres:18`.
  Se a porta 5432 estiver ocupada, usar outra e ajustar a `DATABASE_URL`.
- **Validar:** `docker ps` mostra o container `Up`;
  `docker exec rota-financeira-db psql -U emerson -d emerson -c "SELECT version();"`
  retorna PostgreSQL 18.

### Tarefa 5 — Criar `.env.example` e `.env`
- **Arquivos:** `.env.example` (versionado), `.env` (ignorado)
- **Mudança:** `.env.example` com `DATABASE_URL` e `POSTGRES_*` usando senha-placeholder,
  `JWT_SECRET_KEY` de exemplo (com aviso para trocar),
  `CORS_ORIGINS=http://localhost:5173,http://localhost:3000` e `FLASK_DEBUG=1`.
  Copiar para `.env` e gerar um `JWT_SECRET_KEY` aleatório local.
- **Validar:** `git status --short` mostra `.env.example` e não mostra `.env`.

### Tarefa 6 — Validar a conexão do Python com o banco
- **Arquivos:** nenhum (comando `python -c` pontual, sem criar arquivo).
- **Mudança:** carregar o `.env` com `dotenv` e abrir uma conexão `psycopg`
  com a `DATABASE_URL` (removendo o prefixo `+psycopg`, que é específico do
  SQLAlchemy), executando `SELECT 1`.
- **Validar:** o comando imprime `1` sem erro.

### Tarefa 7 — Atualizar a documentação do projeto
- **Arquivos:** `plano.md`, `CLAUDE.md`
- **Mudança:**
  - `plano.md`: marcar as tarefas da Etapa 0 como concluídas e registrar as
    decisões (Marshmallow, `docker run` avulso, Dockerfile/compose adiado
    para a Etapa 11).
  - `CLAUDE.md`: trocar "Marshmallow ou Pydantic (decisão em aberto)" por
    Marshmallow; incluir `python-dotenv` na stack e atualizar a lista de
    dependências que ainda não estão no `requirements.txt`; anotar o Postgres local
    (`docker run`, imagem `postgres:18`) e o que passa a ser público.
- **Validar:** reler os dois arquivos e conferir que não há mais menção a
  decisão em aberto já resolvida.

### Tarefa 8 — Conferência final
- **Mudança:** nenhuma; só verificação de todos os critérios de aceite.
- **Validar:** percorrer a lista de critérios, informar o que passou e o que
  não passou, e mostrar o `git status --short` final. Depois, aguardar você
  pedir o commit, se quiser.
