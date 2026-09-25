# Esqueleto da aplicação Flask + PostgreSQL (Etapa 1) — Spec

**Criado em:** 2026-09-25
**Status:** Implementada em 2026-09-25
**Origem:** Etapa 1 de `plano.md`

## Problema
A Etapa 0 deixou o ambiente pronto (`.venv`, PostgreSQL 18 em container,
`.env`), mas o projeto ainda **não tem nenhum código de aplicação**. Estado
verificado hoje:

- Não existem `app/`, `config.py`, `run.py` nem `migrations/`; a raiz tem só
  documentação, `requirements.txt`, `.env`/`.env.example`, `.venv/` e `tmp/`.
- O `.env.example` tem `DATABASE_URL`, `POSTGRES_*`, `JWT_SECRET_KEY`,
  `CORS_ORIGINS` e `FLASK_DEBUG`, mas **não** tem `FLASK_APP`, então o
  `flask run` ainda não sabe onde está a aplicação.
- Não há como abrir o Swagger, validar CORS nem provar que a aplicação
  conversa com o banco.
- Verificação exploratória feita nesta spec (teste descartável, sem criar
  arquivos): com as versões instaladas (Flask 3.1.2, Flasgger 0.9.7.1,
  Flask-CORS 6.0.2, Flask-JWT-Extended 4.7.4, SQLAlchemy 2.1.1) o Flasgger
  serve `/apidocs/` e `/apispec_1.json` (200), o Flask-CORS libera a origem
  `http://localhost:5173` e não devolve cabeçalho para uma origem
  desconhecida, e o `JWTManager` inicializa sem erro.

## Objetivo
Criar a estrutura mínima da aplicação — application factory, configuração por
variáveis de ambiente, extensões (`db`, `migrate`, `jwt`), CORS restrito,
Swagger com segurança `Bearer`, tratamento de erros em JSON e uma rota de
saúde — e provar que ela sobe, conversa com o PostgreSQL e está pronta para as
etapas seguintes.

## Fora de escopo
- Models, migrations de tabelas e qualquer `flask db migrate` (Etapa 2).
  Aqui só se roda `flask db init`.
- Rotas de autenticação, callbacks de erro do JWT e expiração do token
  (Etapa 3). O `JWTManager` é apenas registrado.
- Schemas de validação; instalar o Marshmallow (ver decisão 7).
- Serviços de cálculo, integração com o BACEN e qualquer rota de negócio.
- Testes automatizados e `pytest` (a suíte começa na Etapa 6); a validação
  aqui é manual e por `curl`/Swagger, como manda o `CLAUDE.md`.
- `Dockerfile`, `docker-compose.yml`, README (Etapas 11 e 12).
- Ambientes separados de dev/produção além do que vier do `.env`.

## Proposta

### Arquivos criados
```
run.py                     # expõe `app = create_app()`; `python run.py` sobe em modo dev
config.py                  # classe Config lendo o ambiente
app/
  __init__.py              # create_app(): config, extensões, CORS, Swagger, erros, blueprints
  extensions.py            # db, migrate, jwt (instâncias únicas, sem app)
  errors.py                # handlers globais de erro em JSON
  routes/
    __init__.py            # registrar_blueprints(app)
    saude.py               # blueprint da rota de saúde
migrations/                # gerado por `flask db init` (versionado)
```
Também: `.env.example` ganha `FLASK_APP=run.py` (e o `.env` local, o mesmo
valor). Nenhuma dependência nova.

### Configuração (`config.py`)
- Lê do ambiente: `DATABASE_URL` → `SQLALCHEMY_DATABASE_URI`,
  `JWT_SECRET_KEY`, `CORS_ORIGINS` (lista separada por vírgula) e
  `FLASK_DEBUG`.
- Carrega o `.env` com `python-dotenv` também quando a aplicação não é
  iniciada pelo comando `flask` (`python run.py`, gunicorn com `.env`
  local), sem sobrescrever variáveis já definidas no ambiente real.
- `DATABASE_URL` e `JWT_SECRET_KEY` são obrigatórias: um helper em
  `config.py` levanta erro claro (com a dica de copiar `.env.example` para
  `.env`) se estiverem ausentes ou vazias. A `JWT_SECRET_KEY` também é
  recusada se for o valor de exemplo `troque-esta-chave` ou tiver menos de 32
  caracteres. A checagem roda quando o `config.py` é importado.
- `CORS_ORIGINS` é opcional: ausente ou vazia significa nenhuma origem
  liberada, e a aplicação registra um aviso no log ao subir.
- Nenhum segredo ou senha no código.
- `create_app()` aceita um objeto/dicionário de configuração opcional, para
  os testes das Etapas 6 e 10 trocarem o banco sem tocar em `config.py`.

### Extensões (`app/extensions.py`)
- `db = SQLAlchemy()`, `migrate = Migrate()`, `jwt = JWTManager()`, criadas
  sem app e ligadas em `create_app()` — evita import circular.

### Application factory (`app/__init__.py`)
Ordem: carregar configuração → `db`/`migrate`/`jwt` → CORS → Swagger →
handlers de erro → blueprints.
- **CORS:** `flask-cors` só para `/api/*`, com as origens de `CORS_ORIGINS`
  (nunca `*`). Origem fora da lista não recebe cabeçalho CORS.
- **Swagger (Flasgger):** UI em `/apidocs/`, `openapi: 3.0.2`, título "Rota
  Financeira API", versão `0.1.0`, descrição em português e esquema de
  segurança `BearerAuth` (`type: http`, `scheme: bearer`, `bearerFormat: JWT`)
  em `components/securitySchemes`, que gera o botão *Authorize*. A
  especificação sai em `/apispec.json` (rota configurada no Flasgger).
- **JWT:** apenas `jwt.init_app(app)` usando `JWT_SECRET_KEY`.

### Tratamento de erros (`app/errors.py`)
- Toda resposta de erro é JSON, nunca HTML: `HTTPException` (404, 405, 400,
  etc.) e exceções não tratadas (500) passam por handlers globais.
- O 500 registra a exceção no log, mas **não** devolve stack trace nem
  detalhes internos ao cliente.
- Corpo padrão: `{"erro": "mensagem legível"}`, com `"detalhes"` opcional (só
  quando houver informação por campo). O 500 devolve apenas
  `{"erro": "Erro interno do servidor"}`. Esse formato vira o padrão de
  todas as etapas seguintes e é documentado no Swagger como o schema
  reutilizável `Erro` (`components/schemas/Erro`).

### Rota de saúde (`app/routes/saude.py`)
- `GET /api/saude`, pública (sem JWT), com docstring Flasgger completa.
- Executa uma consulta trivial no banco (`SELECT 1`), com timeout curto, para
  provar a conexão. Sucesso: 200 `{"status": "ok", "banco": "ok"}`; banco
  inacessível: 503 `{"erro": "Banco de dados indisponível"}` (formato de erro
  da decisão 5), sem derrubar a aplicação nem expor detalhes internos.

### Migrations
- Rodar `flask db init` para gerar `migrations/` (com `alembic.ini` dentro
  da pasta, `env.py` e `versions/` vazia). Não há models, então não há
  revisão a gerar; a pasta é versionada.

### Fluxo principal
1. `FLASK_APP=run.py` (do `.env`) → `flask run` cria a app, lê o `.env`,
   registra extensões, CORS, Swagger, handlers e blueprints.
2. `GET /api/saude` → 200 e o banco responde.
3. `/apidocs/` mostra a rota de saúde e o botão *Authorize*.
4. Rota inexistente ou método inválido → JSON de erro.

### Casos de borda
- **Banco fora do ar na subida:** a aplicação sobe normalmente (o SQLAlchemy
  só conecta na primeira consulta); apenas `/api/saude` responde 503, e volta
  a 200 quando o banco retorna.
- **`DATABASE_URL` sem `+psycopg`:** o SQLAlchemy procuraria o driver
  `psycopg2`, que não está instalado; deve ficar claro na documentação do
  `.env.example` (já está).
- **Variável obrigatória ausente ou vazia** (`DATABASE_URL`,
  `JWT_SECRET_KEY`): erro claro na subida em vez de um erro obscuro depois.
- **`JWT_SECRET_KEY` de exemplo ou curta** (`troque-esta-chave` ou menos de
  32 caracteres): a subida é recusada com mensagem indicando como gerar uma
  chave (`python -c "import secrets; print(secrets.token_hex(32))"`).
- **Testes:** como a checagem roda no import do `config.py`, os testes
  precisam das variáveis no ambiente (o `.env` local já atende; num CI
  futuro, defini-las lá).
- **`CORS_ORIGINS` vazio:** nenhuma origem liberada, com aviso no log.
- **Requisição `OPTIONS` (preflight)** de origem permitida: respondida pelo
  Flask-CORS sem exigir JWT.
- **SQLAlchemy 2.1.1** (o arquivo antigo fixava 2.0.44): o teste exploratório
  com Flask-SQLAlchemy 3.1.1 funcionou; se aparecer incompatibilidade real
  nesta etapa, parar e perguntar antes de fixar versão.
- **`flask db init` em pasta já existente** falha; só rodar uma vez.
- **Rota com/sem barra final** (`/apidocs` × `/apidocs/`): o Flasgger cuida
  do redirecionamento.

## Decisões tomadas
1. ~~**Como o Flask CLI encontra a aplicação?**~~ — **RESOLVIDA
   (2026-09-25): (a)** `run.py` com `app = create_app()`, e `FLASK_APP=run.py`
   no `.env.example` (e no `.env` local). Serve a `flask run`, `python run.py`
   e `gunicorn run:app`.
2. ~~**Configuração**~~ — **RESOLVIDA (2026-09-25): (a)** uma única classe
   `Config` + `create_app(config=None)` para sobrescrita nos testes.
   Classes por ambiente só se uma futura spec de produção exigir.
3. ~~**Variáveis ausentes**~~ — **RESOLVIDA (2026-09-25): (a) com
   refinamento.** `DATABASE_URL` e `JWT_SECRET_KEY` são obrigatórias (vazia
   conta como ausente); sem elas a aplicação falha na subida com mensagem
   clara. Nunca haver valor padrão para chave JWT nem credenciais no código.
   `CORS_ORIGINS` ausente/vazia = nenhuma origem liberada, com aviso no log.
   Refinamento: a subida também recusa `JWT_SECRET_KEY` igual ao valor de
   exemplo do `.env.example` (`troque-esta-chave`) ou com menos de 32
   caracteres.
4. ~~**Esquema do Swagger**~~ — **RESOLVIDA (2026-09-25): OpenAPI 3.0.2**
   com `components/securitySchemes` do tipo `http`/`bearer` (o usuário cola
   só o token no *Authorize*). Todas as docstrings futuras usam
   `requestBody`, `components/schemas` e `security: - BearerAuth: []`.
   A geração do JSON foi testada com as versões instaladas; a renderização
   da UI e o *Authorize* serão verificados nesta etapa (critério de aceite).
   Se a UI falhar, voltar para Swagger 2.0 **antes** de criar novas rotas,
   avisando antes de trocar.
5. ~~**Formato do corpo de erro**~~ — **RESOLVIDA (2026-09-25): (b)**
   `{"erro": "mensagem legível", "detalhes": {...}}`, com `detalhes` opcional
   (usado nos erros de validação a partir da Etapa 3, no formato por campo do
   Marshmallow). O código HTTP não se repete no corpo; chaves em português.
6. ~~**`/api/saude` consulta o banco?**~~ — **RESOLVIDA (2026-09-25): (a)**
   sim, com `SELECT 1`. Sucesso: 200 `{"status": "ok", "banco": "ok"}`; banco
   inacessível: 503 `{"erro": "Banco de dados indisponível"}`, sem expor
   detalhes internos (host, usuário, versão) e com timeout curto na consulta.
7. ~~**Marshmallow**~~ — **RESOLVIDA (2026-09-25): (a)** instalar só na
   Etapa 3, junto com o primeiro schema (versão atual no PyPI: 4.3.1). Nada
   desta etapa o usa; o `requirements.txt` não muda. O `CLAUDE.md` foi
   ajustado de "Etapa 1" para "Etapa 3".
8. ~~**Pacotes vazios**~~ — **RESOLVIDA (2026-09-25): (a)** criar só o que
   é usado agora (`routes/`, `extensions.py`, `errors.py`, `config.py`).
   `models/` nasce na Etapa 2, `schemas/` na 3, `services/` na 6 e
   `integrations/` na 8. A estrutura-alvo completa segue documentada no
   `CLAUDE.md`.
9. ~~**Blueprint da saúde**~~ — **RESOLVIDA (2026-09-25): (a)** aceito o
   blueprint `saude` (`app/routes/saude.py`) como acréscimo aos quatro da
   proposta; já registrado no `CLAUDE.md`.

## Critérios de aceite
- [x] `flask run` (com `FLASK_APP=run.py` do `.env`) sobe sem erro; `python
      run.py` e `gunicorn run:app` também respondem.
- [x] `GET /api/saude` responde 200 com o corpo definido, sem token.
- [x] Com o container do banco parado (`docker stop rota-financeira-db`),
      `GET /api/saude` responde 503 sem derrubar a aplicação; após
      `docker start`, volta a 200.
- [x] `/apidocs/` abre e renderiza sem erro (verificação visual no
      navegador), lista `GET /api/saude` e mostra o botão *Authorize* com
      `BearerAuth`; a especificação tem `openapi: 3.0.2` e
      `components.securitySchemes.BearerAuth` do tipo `http`/`bearer`.
- [x] No *Authorize*, colar apenas o token (sem a palavra `Bearer`) basta para
      o Swagger UI enviar `Authorization: Bearer <token>` (conferido com uma
      rota protegida temporária ou com a inspeção do cabeçalho enviado; a
      rota de teste não fica no código final).
- [x] Rota inexistente → 404 e método não permitido → 405, ambos em JSON;
      um erro forçado em desenvolvimento não devolve stack trace ao cliente.
- [x] CORS: requisição com `Origin: http://localhost:5173` recebe
      `Access-Control-Allow-Origin`; com `Origin: http://exemplo.com` não
      recebe; o preflight `OPTIONS` de origem permitida funciona.
- [x] Sem `DATABASE_URL` ou `JWT_SECRET_KEY` (ausente ou vazia), a subida
      falha com mensagem clara.
- [x] Com `JWT_SECRET_KEY=troque-esta-chave` ou com menos de 32 caracteres, a
      subida é recusada com mensagem clara; com a chave do `.env` local
      (64 caracteres), sobe normalmente.
- [x] Com `CORS_ORIGINS` vazio, a aplicação sobe, não libera nenhuma origem e
      registra um aviso no log.
- [x] `flask db init` criou `migrations/`; `flask db current` roda sem erro
      contra o banco.
- [x] Nenhum segredo no código; nenhum model, schema ou rota de negócio
      criado; nenhuma dependência nova no `requirements.txt` (conforme
      decisão 7).
- [x] `.env.example` com `FLASK_APP=run.py`.

---
*Depois de aprovada, esta spec vira a base do PLANO — não escrever
código antes disso.*

## Plano de Implementação

Tarefas na ordem de execução. Nenhuma faz `git add`/`commit`/`push` (só quando
você pedir). Os testes descartáveis (variáveis alteradas, servidor com rota
temporária, cópia do `config.py`) ficam no diretório temporário da sessão,
**nunca** no projeto. Não há suíte automatizada nesta etapa: a validação é por
`python -c`, `curl`, `flask routes` e Swagger. Comandos abaixo assumem o
`.venv` ativo e a raiz do projeto como diretório de trabalho.

### Tarefa 1 — Variável `FLASK_APP`
- **Arquivos:** `.env.example`, `.env` (local, ignorado)
- **Mudança:** acrescentar `FLASK_APP=run.py` nos dois, junto de `FLASK_DEBUG`.
- **Validar:** `grep FLASK_APP .env.example .env` mostra a linha nos dois;
  `git status --short` não lista o `.env`.

### Tarefa 2 — Configuração (`config.py`)
- **Arquivos:** `config.py`
- **Mudança:** carregar o `.env` com `python-dotenv` (sem sobrescrever o que já
  está no ambiente); helper que exige `DATABASE_URL` e `JWT_SECRET_KEY`
  (ausentes ou vazias → erro claro com a dica de copiar `.env.example`) e
  recusa `JWT_SECRET_KEY` igual a `troque-esta-chave` ou com menos de 32
  caracteres (mensagem com o comando para gerar uma chave); classe `Config`
  com `SQLALCHEMY_DATABASE_URI`, `SQLALCHEMY_TRACK_MODIFICATIONS` desligado,
  `JWT_SECRET_KEY`, `CORS_ORIGINS` (lista, vazia se ausente) e `DEBUG` a
  partir de `FLASK_DEBUG`. Sem nenhum valor padrão para segredos.
- **Validar:**
  - `python -c "import config; print(config.Config.CORS_ORIGINS)"` imprime as
    duas origens do `.env`, sem mostrar segredos;
  - `JWT_SECRET_KEY= python -c "import config"` (vazia) e
    `JWT_SECRET_KEY=troque-esta-chave python -c "import config"` e uma chave
    curta falham com a mensagem esperada;
  - para "variável ausente", importar uma cópia do `config.py` numa pasta
    temporária **sem `.env`**, com `env -i`, e conferir o erro de
    `DATABASE_URL`/`JWT_SECRET_KEY`.

### Tarefa 3 — Extensões (`app/extensions.py`)
- **Arquivos:** `app/extensions.py` (e `app/__init__.py` provisório vazio, só
  para `app` ser importável até a Tarefa 6)
- **Mudança:** `db = SQLAlchemy()`, `migrate = Migrate()`, `jwt = JWTManager()`.
- **Validar:** `python -c "from app.extensions import db, migrate, jwt"` sem
  erro.

### Tarefa 4 — Tratamento de erros (`app/errors.py`)
- **Arquivos:** `app/errors.py`
- **Mudança:** função `registrar_handlers(app)` com handler de
  `HTTPException` (corpo `{"erro": <descrição em português quando houver>}`,
  mantendo o status e os cabeçalhos da exceção, ex.: `Allow` no 405) e handler
  de `Exception` (registra a exceção no log e devolve 500
  `{"erro": "Erro interno do servidor"}`, sem stack trace). Suporte ao campo
  opcional `detalhes` para as etapas seguintes.
- **Validar:** na Tarefa 6, quando a factory existir (esta tarefa só é
  importada por ela); aqui, `python -c "import app.errors"` sem erro.

### Tarefa 5 — Rota de saúde
- **Arquivos:** `app/routes/saude.py`, `app/routes/__init__.py`
- **Mudança:** blueprint `saude` com `GET /api/saude`, pública, docstring
  Flasgger em OpenAPI 3 (respostas 200 e 503 com o schema `Erro`). Executa
  `SELECT 1` pela sessão do `db` com timeout curto; em falha de banco devolve
  503 `{"erro": "Banco de dados indisponível"}` sem detalhes internos e sem
  deixar a sessão em estado inválido (rollback). `registrar_blueprints(app)`
  em `routes/__init__.py`.
- **Validar:** `python -c "import app.routes"` sem erro (a chamada HTTP fica
  para a Tarefa 7).

### Tarefa 6 — Application factory (`app/__init__.py`)
- **Arquivos:** `app/__init__.py`
- **Mudança:** `create_app(config=None)`: `from_object(Config)` + `update` com
  a sobrescrita opcional; `db.init_app`, `migrate.init_app(app, db)`,
  `jwt.init_app`; CORS só em `/api/*` com `CORS_ORIGINS` (aviso no log se a
  lista estiver vazia; nunca `*`); Flasgger com `openapi: 3.0.2`, título "Rota
  Financeira API", versão `0.1.0`, descrição em português, `specs_route`
  `/apidocs/`, especificação em `/apispec.json`, `components/securitySchemes`
  `BearerAuth` (`http`/`bearer`/`JWT`) e `components/schemas/Erro`; depois
  `registrar_handlers` e `registrar_blueprints`.
- **Validar:** `python -c "from app import create_app; a = create_app(); print(sorted(str(r) for r in a.url_map.iter_rules()))"`
  lista `/api/saude` e as rotas do Swagger; o `create_app` com um dicionário
  de sobrescrita altera a configuração.

### Tarefa 7 — Ponto de entrada (`run.py`) e subida
- **Arquivos:** `run.py`
- **Mudança:** `from app import create_app`, `app = create_app()` e o bloco
  `if __name__ == "__main__": app.run()` (só `127.0.0.1`; debug vem da
  configuração).
- **Validar:**
  - `flask routes` lista `/api/saude`;
  - `flask run` sobe sem erro; `curl -i http://127.0.0.1:5000/api/saude` →
    200 `{"status": "ok", "banco": "ok"}`, sem token;
  - `python run.py` e `gunicorn run:app` (em outra porta) também respondem
    200 em `/api/saude`.

### Tarefa 8 — Validar a rota de saúde sem o banco
- **Arquivos:** nenhum.
- **Mudança:** nenhuma; verificação.
- **Validar:** com a aplicação rodando, `docker stop rota-financeira-db`;
  `curl -i /api/saude` → 503 `{"erro": "Banco de dados indisponível"}` em tempo
  curto e a aplicação continua respondendo (ex.: `/apidocs/`);
  `docker start rota-financeira-db` e a rota volta a 200 sem reiniciar a
  aplicação. Se o banco não voltar a responder sem reiniciar, ajustar a
  Tarefa 5 (rollback/`pool_pre_ping`) antes de seguir e avisar.

### Tarefa 9 — Validar erros em JSON
- **Arquivos:** nenhum (script descartável no diretório temporário).
- **Mudança:** nenhuma no projeto.
- **Validar:** `curl -i` em uma rota inexistente → 404 JSON; `POST /api/saude`
  → 405 JSON com cabeçalho `Allow`; script temporário que importa
  `create_app`, acrescenta **em memória** uma rota que levanta exceção e
  chama-a com `test_client()` (com `debug` ligado e desligado) → 500
  `{"erro": "Erro interno do servidor"}`, sem `Traceback` no corpo e com a
  exceção registrada no log.

### Tarefa 10 — Validar CORS
- **Arquivos:** nenhum.
- **Mudança:** nenhuma; verificação.
- **Validar:** `curl -i -H "Origin: http://localhost:5173" /api/saude` →
  cabeçalho `Access-Control-Allow-Origin: http://localhost:5173`; com
  `Origin: http://exemplo.com` → sem o cabeçalho; preflight
  `curl -i -X OPTIONS -H "Origin: http://localhost:5173" -H "Access-Control-Request-Method: GET"`
  → 200/204 com os cabeçalhos CORS; iniciar com `CORS_ORIGINS=` (vazia) →
  aplicação sobe, nenhuma origem liberada e aviso no log.

### Tarefa 11 — Validar o Swagger e o *Authorize*
- **Arquivos:** nenhum no projeto (servidor de teste no diretório temporário).
- **Mudança:** nenhuma no projeto. Um script temporário importa `create_app`,
  registra **em memória** uma rota protegida (`jwt_required`, com `security:
  - BearerAuth: []` na docstring) e sobe em outra porta (ex.: 5001).
- **Validar:**
  - `curl /apispec.json` tem `openapi: 3.0.2`,
    `components.securitySchemes.BearerAuth` (`http`/`bearer`),
    `components.schemas.Erro` e o caminho `/api/saude`;
  - **verificação manual sua, no navegador** (não tenho navegador aqui):
    abrir `http://127.0.0.1:5000/apidocs/` (a UI renderiza sem erro, lista
    `GET /api/saude` e mostra *Authorize*) e, no servidor temporário
    (`:5001/apidocs/`), colar **só o token** (gerado por um comando que eu
    fornecer) no *Authorize* e executar a rota protegida — deve responder 200,
    e sem token, 401;
  - se a UI do OpenAPI 3.0 falhar, **parar e avisar** antes de voltar ao
    Swagger 2.0 (decisão 4).

### Tarefa 12 — Migrations (`flask db init`)
- **Arquivos:** `migrations/` (gerada)
- **Mudança:** rodar `flask db init` uma única vez.
- **Validar:** existem `migrations/alembic.ini`, `env.py`, `script.py.mako` e
  `versions/` vazia; `flask db current` roda sem erro contra o PostgreSQL. Se
  houver incompatibilidade com o SQLAlchemy 2.1.1, **parar e perguntar** antes
  de fixar qualquer versão (caso de borda da spec).

### Tarefa 13 — Atualizar a documentação
- **Arquivos:** `plano.md`, `CLAUDE.md`, esta spec
- **Mudança:** em `plano.md`, marcar a Etapa 1 como concluída, registrando as
  decisões; no `CLAUDE.md`, atualizar "Estrutura de código" e "Estado atual"
  (agora existe código), incluir os comandos de execução (`flask run`,
  `flask db ...`) e o formato de erro e o estilo OpenAPI 3 das docstrings;
  nesta spec, marcar os critérios de aceite e o status como implementada.
- **Validar:** reler os três arquivos e conferir que nada diz que "ainda não
  há código de aplicação".

### Tarefa 14 — Conferência final
- **Arquivos:** nenhum.
- **Mudança:** nenhuma; verificação de todos os critérios de aceite.
- **Validar:** percorrer a lista de critérios, informar o que passou e o que
  ficou dependente de verificação manual sua, conferir que não há segredo no
  código (`grep` por chaves/senhas nos arquivos versionáveis) e mostrar o
  `git status --short` final. Aguardar você pedir o commit.
