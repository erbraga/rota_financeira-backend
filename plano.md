# Plano de Implementação — Rota Financeira (Backend)

**Criado em:** 2026-09-25
**Base:** `proposta-backend-api-rest.md`, `requisitos back-end.md` e `CLAUDE.md`

Este é o plano geral, em ordem de execução. Cada etapa deve virar uma spec em
`docs/specs/AAAA-MM-DD-nome.md` (fluxo `/spec` → `/plan` → `/implementar`)
antes de ser codada. Aqui ficam só o roteiro, os arquivos envolvidos e como
validar cada etapa.

Convenção de status: `[ ]` pendente · `[x]` concluída.

## Visão geral

| # | Etapa | Requisitos |
|---|---|---|
| 0 | Preparação do repositório e ambiente | R10 |
| 1 | Esqueleto da aplicação Flask + PostgreSQL | R1, R5 |
| 2 | Modelagem de dados e migration inicial | — |
| 3 | Autenticação (registro e login com JWT) | R4 |
| 4 | CRUD de simulações | R1, R5 |
| 5 | CRUD de opções de financiamento | R1, R5 |
| 6 | Serviços de cálculo (Price, SAC, fundo) + testes unitários | — |
| 7 | Tabela de parcelas e endpoint de resultado dos 3 cenários | — |
| 8 | Integração com o BACEN/SGS, cache e endpoints de índices (CDI e IPCA) | R7, R8 |
| 9 | ~~Extras: paginação, ordenação, filtros (e CET)~~ — **eliminada** (R4 atendido por JWT, `/resultado` e índices) | R4 |
| 10 | Swagger completo e testes de integração | R1, R5 |
| 11 | Dockerfile (sem docker-compose, por decisão do autor) | R3 |
| 12 | README com fluxograma da arquitetura | R2, R8 |
| 13 | Revisão final e entrega | R10 |

---

## Etapa 0 — Preparação do repositório e ambiente
**Status: concluída em 2026-09-25** (spec: `docs/specs/2026-09-25-preparacao-repositorio-ambiente.md`).

- [x] Repositório Git e repositório **público** no GitHub, só para o backend (R10) — já existia (`origin` = `github.com/erbraga/rota_financeira-backend`).
- [x] `.gitignore` revisado: proposta, plano e specs passam a ser publicados; `CLAUDE.md`, `.claude` e `requisitos back-end.md` seguem ignorados; acrescentados `.env`, `instance/`, `.pytest_cache/` e pastas de IDE.
- [x] Ambiente virtual `.venv` criado e `requirements.txt` instalado (com `python-dotenv` acrescentado).
- [x] PostgreSQL 18 local via `docker run` avulso (container `rota-financeira-db`, volume `rota_financeira_pgdata`, banco/usuário `emerson`).
- [x] `.env.example` com `DATABASE_URL`, `JWT_SECRET_KEY`, `CORS_ORIGINS` e `FLASK_DEBUG`; `.env` local (não versionado).
- [x] Decisões: **Marshmallow** para validação/serialização (dependência entra na etapa 1); Dockerfile isolado vs. docker-compose **adiado para a etapa 11**.

**Validado:** `pip check` sem conflitos; `psql` no container e conexão via `psycopg` com a `DATABASE_URL` do `.env` funcionando.

**Subir o banco novamente** (se o container for removido):

```
set -a; source .env; set +a
docker run -d --name rota-financeira-db -e POSTGRES_USER -e POSTGRES_PASSWORD -e POSTGRES_DB -p 127.0.0.1:5432:5432 -v rota_financeira_pgdata:/var/lib/postgresql --restart unless-stopped postgres:18
```
(a senha vem do `.env` local, que não é versionado)

## Etapa 1 — Esqueleto da aplicação Flask + PostgreSQL
**Status: concluída em 2026-09-25** (spec: `docs/specs/2026-09-25-esqueleto-aplicacao-flask.md`).
**Arquivos:** `run.py`, `config.py`, `app/__init__.py`, `app/extensions.py`, `app/errors.py`, `app/routes/__init__.py`, `app/routes/saude.py`, `migrations/`

- [x] `config.py` lendo as variáveis de ambiente (obrigatórias falham com mensagem clara; chave JWT de exemplo ou curta é recusada; sem segredos no código).
- [x] `app/extensions.py` com `db`, `migrate`, `jwt` (instâncias únicas, evitam import circular).
- [x] Application factory `create_app(config=None)` registrando db, migrate, JWT, CORS (só `CORS_ORIGINS`) e Flasgger em **OpenAPI 3.0.2** com `BearerAuth`.
- [x] Handlers globais de erro em JSON `{"erro": ..., "detalhes": ...}` (404, 405, 500 etc.), sem stack trace.
- [x] `GET /api/saude` (pública, consulta o banco com `SELECT 1`; 503 se o banco cair) documentada no Swagger.
- [x] `flask db init` gerando `migrations/` (versionada; a pasta `versions/` só passa a ser rastreada com a primeira migration, na Etapa 2).

**Validado:** `flask run`, `python run.py` e `gunicorn run:app` sobem; `/api/saude` responde 200 e 503 (banco parado) e volta a 200 sem reiniciar; erros em JSON; CORS por origem; `/apidocs/` e o *Authorize* (só o token) conferidos no navegador.
**Pendência levada adiante:** os erros 401 do Flask-JWT-Extended saíam como `{"msg": ...}` — **resolvido na Etapa 3** (tudo em 401 `{"erro": ...}`).

## Etapa 2 — Modelagem de dados e migration inicial
**Status: concluída em 2026-09-25** (spec: `docs/specs/2026-09-25-modelagem-dados-migration-inicial.md`).
**Arquivos:** `app/models/{usuario,simulacao,opcao_financiamento,indice_economico_cache}.py`, `app/models/__init__.py`, `app/extensions.py`, `migrations/versions/df960bba0ba5_modelagem_inicial.py`

- [x] Models da seção 6 da proposta: `usuarios`, `simulacoes`, `opcoes_financiamento`, `indices_economicos_cache` (SQLAlchemy 2.0 tipado, `Identity()`, convenção de nomes de restrições na `Base`).
- [x] Dinheiro `Numeric(14,2)`; taxas e índices `Numeric(12,6)` em **percentual**; `sistema_amortizacao` e `indice` como `VARCHAR` + CHECK; `email` único; `criado_em` `TIMESTAMPTZ` com `now()`; tudo `NOT NULL`; CHECKs de positividade/limites; unicidade `(indice, data_referencia)` no cache (acréscimo à proposta).
- [x] **`parcelas_calculadas` NÃO foi criada** (mudança em relação à proposta): a amortização é calculada sob demanda pelos serviços (Etapas 6 e 7).
- [x] FKs com `ON DELETE RESTRICT`; a cascata `all, delete-orphan` fica no ORM (`db.session.delete(simulacao)` apaga as opções).
- [x] `flask db migrate` + revisão manual (removida a CHECK de enum duplicada) + `flask db upgrade`.

**Validado:** `\d+` das 4 tabelas conforme a spec; `downgrade base` → `upgrade` sem resíduos; `flask db migrate` sem mudanças; script descartável com 25 verificações (Decimal, fuso, rejeições do banco, `RESTRICT` x cascata do ORM, `db.get_or_404`).

**Nota (Etapa 8):** a ideia de "a API grava a taxa sugerida do BACEN quando a simulação a omite" (decisão 11) foi **descartada**: as taxas continuam obrigatórias e o frontend as pré-preenche a partir de `/api/indices`.
**Obrigações levadas às próximas etapas:** Etapa 3 — normalizar e-mail e mapear `IntegrityError` em 409; Etapa 5 — validar `valor_entrada` da opção ≤ `valor_veiculo` (o banco só confere a entrada da simulação); Etapa 6/7 — amortização sob demanda e decidir o modo "dado o aporte"; Etapa 8 — preencher as taxas do BACEN antes de gravar a simulação.

## Etapa 3 — Autenticação (registro e login)
**Status: concluída em 2026-09-25** (spec: `docs/specs/2026-09-25-autenticacao-jwt.md`).
**Arquivos:** `app/routes/auth.py`, `app/schemas/{__init__,auth}.py`, `app/services/auth.py`, `app/errors.py`, `app/__init__.py`, `config.py`

- [x] `POST /api/auth/registrar`: 201 com o usuário (sem token); valida nome/e-mail/senha (8 a 128, sem regras de composição), normaliza o e-mail, grava só o **hash** (scrypt), 409 só para a violação de `uq_usuarios_email` (sem consulta prévia), nunca devolve `senha_hash`.
- [x] `POST /api/auth/login`: 200 com `access_token`, `token_type`, `expires_in` e `usuario`; 401 "Credenciais inválidas" igual para e-mail inexistente e senha errada (hash fictício iguala o tempo).
- [x] `GET /api/auth/perfil` (**acréscimo à proposta**): usuário do token; rota protegida real e base do helper `usuario_atual()`.
- [x] Erros: 422 com `detalhes` por campo (handler global de `ValidationError`), 400/415 para corpo quebrado/não JSON, e **todos os erros do JWT em 401** `{"erro": ...}` com `WWW-Authenticate: Bearer`.
- [x] Expiração: 60 min por padrão, `JWT_ACCESS_TOKEN_EXPIRES_MINUTOS` configurável; `marshmallow==4.3.1` é a única dependência nova.
- [x] Docstrings Flasgger (OpenAPI 3) nas 3 rotas; schemas `RegistroRequisicao`, `LoginRequisicao`, `LoginResposta`, `Usuario`, `UsuarioResumo` em `SWAGGER_TEMPLATE`.

**Validado:** scripts descartáveis (schemas 40 verificações, erros do JWT, serviço), `curl` ponta a ponta (registro, 409, 422/400/415, login, tempos iguais, `perfil` com 8 tipos de token ruim, validade de 300 s com a variável em 5) e Swagger UI conferido por você (registrar, login, *Authorize* só com o token, `perfil` 200/401).
**Levado adiante:** Etapas 4 e 5 usam `usuario_atual()` e `carregar(Schema())`; débito de *rate limiting* e 401 do login x frontend registrados no `CLAUDE.md`.

## Etapa 4 — CRUD de simulações
**Status: concluída em 2026-09-25** (spec: `docs/specs/2026-09-25-crud-simulacoes.md`).
**Arquivos:** `app/routes/simulacoes.py`, `app/schemas/{base,simulacao}.py`, `app/services/simulacoes.py`, `app/__init__.py`

- [x] `POST` (201 + `Location`), `GET` lista (`{"itens", "total"}`, mais recentes primeiro), `GET` por id, `PUT` (**substituição total**, sem `PATCH`) e `DELETE` (**204 sem corpo**) em `/api/simulacoes` — cobre POST/GET/PUT/DELETE do **R1**.
- [x] `usuario_id` sempre do token; corpo lido com `carregar(Schema())`; campos desconhecidos (`id`, `usuario_id`, `criado_em`) recusados (422).
- [x] Simulação de outro usuário responde **404** igual à inexistente (uma consulta por `id` e `usuario_id`); ids fora do `INTEGER` também dão 404 (tratado no serviço).
- [x] Validação: veículo 0,01 a 9.999.999,00; entrada 0 a `valor_veiculo` (igual aceito); IPCA −20 a 100; fundo 0 a 100; prazo inteiro de 1 a 60; casas em excesso **rejeitadas** (2 no dinheiro, 6 nas taxas); números como **número JSON** na saída.
- [x] Docstrings OpenAPI 3 nas 5 rotas; schemas `SimulacaoRequisicao`, `Simulacao` e `SimulacaoLista` no Swagger.

**Validado:** scripts descartáveis (campos numéricos 66 verificações, schemas 38, serviço 19), ponta a ponta contra o servidor com dois usuários (36 verificações: isolamento, 401 nas 5 rotas, 24 entradas inválidas em POST e PUT, ids inválidos, exclusão com opções) e Swagger UI conferido por você (criar, listar, abrir, editar, erro 422, excluir 204 e 404).
**Ajuste em relação ao plano:** o teto do id ficou no serviço (`ID_MAXIMO`), não no conversor `int(max=...)`, que fazia `PUT`/`DELETE` responderem 405.
**Levado adiante:** Etapa 5 reutiliza `obter_simulacao`, `campo_decimal`/`campo_inteiro` e o padrão de isolamento; Etapa 7 devolve números como número JSON; o envelope `itens`/`total` fica como está (a antiga Etapa 9 foi eliminada).

## Etapa 5 — CRUD de opções de financiamento
**Status: concluída em 2026-09-25** (spec: `docs/specs/2026-09-25-opcoes-financiamento.md`).
**Arquivos:** `app/routes/financiamentos.py`, `app/schemas/financiamento.py`, `app/services/financiamentos.py`, `app/services/simulacoes.py`, `app/routes/simulacoes.py`, `app/__init__.py`

- [x] `POST` (201 + `Location`) e `GET` (envelope `{"itens","total"}`, ordem de criação) em `/api/simulacoes/<id>/financiamentos`; `PUT` (substituição total) e `DELETE` (204) em `.../<fid>`. **Sem** `GET` por `fid`.
- [x] Dono da simulação verificado primeiro (`obter_simulacao`, 404 "Simulação não encontrada"); a opção é buscada por `id` **e** `simulacao_id` (404 "Opção de financiamento não encontrada"); ids acima do `INTEGER` → 404 no serviço.
- [x] Campos: `taxa_juros_mensal` de 0 a 20 (% a.m., 6 casas), `prazo_meses` inteiro de 1 a 72, `sistema_amortizacao` `PRICE`/`SAC` em qualquer caixa, `valor_entrada` padrão 0; casas em excesso rejeitadas; números como número JSON.
- [x] **Máximo de 3 opções** por simulação (4º `POST` → **409**; sem mínimo; excluir libera vaga), com **bloqueio da linha da simulação** (`FOR UPDATE`) contra corrida.
- [x] `valor_entrada` da opção **estritamente menor** que o `valor_veiculo` da simulação (a da simulação segue aceitando `≤`).
- [x] **Alteração na Etapa 4:** `PUT /api/simulacoes/<id>` é recusado (422 em `valor_veiculo`, citando a opção) se o novo valor do veículo for menor ou igual à entrada de alguma opção; a rota obtém a simulação com bloqueio.
- [x] Docstrings OpenAPI 3 nas 4 rotas (com o 409); schemas `FinanciamentoRequisicao`, `Financiamento` e `FinanciamentoLista`.

**Validado:** scripts descartáveis (schemas 42, serviço 23 com **corrida real** e controle sem bloqueio que falha, coerência 11), ponta a ponta contra o servidor com dois usuários (56 verificações: limite e 2 `POST` simultâneos, isolamento, 401, 28 entradas inválidas em POST e PUT, ids extremos, coerência com a simulação, cascata) e Swagger UI conferido por você. Regressão das Etapas 1 a 4 verde.
**Levado adiante:** Etapa 6 — taxa 0 tratada e valor financiado sempre > 0; Etapa 7 — no máximo 216 linhas por simulação (3 opções × 72 meses) e 0 a 3 opções (com 0 opções, só os cenários possíveis); Etapa 12 — README com as rotas de financiamentos.

## Etapa 6 — Serviços de cálculo + testes unitários
**Status: concluída em 2026-09-25** (spec: `docs/specs/2026-09-25-servicos-de-calculo.md`).
**Arquivos:** `app/services/calculo/{__init__,base,preco,financiamento,fundo}.py`, `tests/calculo/`, `pytest.ini`, `requirements-dev.txt`

Pacote **puro** (só biblioteca padrão; verificado no código-fonte por teste), em `Decimal`, com percentual na entrada.

- [x] **Preço corrigido (IPCA):** `valor × (1 + ipca)^(meses/12)` e série mês a mês.
- [x] **Price** e **SAC:** parcela e juros arredondados ao centavo a cada mês (`ROUND_HALF_UP`), última parcela com o resíduo e **amortização limitada ao saldo** (decisão 8: com parcelas de centavos ou juros extremos o financiamento é quitado antes e as parcelas restantes saem 0,00); custo total = entrada + Σ parcelas; taxa 0 com ramo próprio.
- [x] **Fundo:** taxa mensal composta, aportes ao fim do mês, `valor_entrada` da simulação como **capital inicial**, saldo sem arredondar no meio e aporte arredondado **para cima**; `aporte_para_meta`, `serie_fundo` e `meses_para_meta` (modo "dado o aporte", horizonte 60).
- [x] `pytest` 9.1.1 em `requirements-dev.txt` (fora do `requirements.txt`).
- [x] **Não entrou aqui:** a composição dos três cenários (`cenarios`), que vai para a Etapa 7 junto do contrato JSON.

**Validado:** 511 testes em ~1,4 s — valores conhecidos (8.884,88; 1.120,00/1.010,00; 2.593,66 e 1.948,07; 108.410,78), propriedades parametrizadas com referência independente (`Fraction`/centavos inteiros e fórmula fechada em 80 dígitos), aporte mínimo (um centavo a menos não atinge a meta), bordas (taxa 0, prazo 1, valor 0,01, extremos da API, meta inalcançável), pureza, contexto do `Decimal` e desempenho (pior caso < 100 ms). Regressão das Etapas 1 a 5 verde.
**Decisões novas na implementação:** 8 (trava da amortização no saldo) e 9 (pureza verificada no código-fonte, porque importar `app.services.calculo` executa `app/__init__.py`).

## Etapa 7 — Tabela de parcelas e endpoint de resultado
**Status: concluída em 2026-09-25** (spec: `docs/specs/2026-09-25-parcelas-e-resultado.md`).
**Arquivos:** `app/services/calculo/cenarios.py`, `app/services/resultados.py`, `app/schemas/resultado.py`, `app/schemas/__init__.py` (`carregar_consulta`), `app/routes/financiamentos.py`, `app/routes/simulacoes.py`, `app/__init__.py`, `tests/calculo/test_cenarios.py`

- [x] **Composição** (`cenarios`, pura): opção de financiamento, fundo nos dois modos, eixo comum, séries e `menor_custo`; `services/resultados.py` lê o banco (só leitura, sem bloqueio) e entrega `Decimal` ao cálculo, sem `float`.
- [x] `GET .../financiamentos/<fid>/parcelas`: documento `{"financiamento", "parcelas", "totais"}` (uma linha por mês, `saldo_devedor` após o pagamento).
- [x] `GET .../resultado[?aporte_mensal=]`: `cenarios` (à vista, 0 a 3 financiamentos, fundo), `menor_custo` e `series`. **`custo_total` = o que se paga pelo carro** (à vista = valor; financiamento = entrada + parcelas; fundo = preço corrigido na compra), comparação nominal; `menor_custo` calculado no backend (empate: à vista, financiamentos, fundo).
- [x] **Séries** em lista de pontos por mês, eixo comum até o maior prazo, `null` onde a série terminou; chave de `saldo_devedor` = id da opção (texto).
- [x] **Modo `aporte_mensal`:** o aporte informado substitui o calculado, `prazo_meses_fundo` deixa de ser usado, `mes_da_meta` (ou `null`, e então o fundo sai do `menor_custo`), horizonte 60.
- [x] Swagger: schemas novos e explicações (última parcela ajustada, quitação antecipada, custo total, eixo e `null`, modo aporte). Simulação com 0 a 3 opções tratada.

**Validado:** 44 testes de `cenarios` (exemplo completo, eixo, `null`, modos, desempate, pior caso < 100 ms) e a suíte inteira com 555 testes; scripts descartáveis (schemas 36, adaptador 19); ponta a ponta contra o servidor com dois usuários (55 verificações: números da spec, 61 pontos, `/parcelas`, modo aporte 1500 → mês 46 e 300 → `null`, 9 parâmetros inválidos em 422, sem opções, prazo 72, isolamento, 401, sem cache, pior caso em 18 ms) e Swagger UI conferido por você. Regressão das Etapas 1 a 6 verde.
**Decisões do plano (não estavam explícitas na spec):** no modo aporte sem alcançar, `saldo_final`/`total_aportado`/`rendimento` são os do mês 60; `prazo_meses` do fundo = meses **simulados**; parâmetro desconhecido, vazio ou repetido → 422.
**Levado adiante:** Etapa 8 — as taxas sugeridas do BACEN alimentam o **formulário**/criação da simulação (o `/resultado` sempre usa as taxas gravadas); Etapa 10 — testes de integração das duas rotas no `pytest`; Etapa 12 — rotas e contrato do resultado no README.

## Etapa 8 — Integração com o BACEN/SGS, cache e índices
**Status: concluída em 2026-09-25** (spec: `docs/specs/2026-09-25-indices-bacen.md`).
**Arquivos:** `app/integrations/bacen.py`, `app/services/indices.py`, `app/schemas/indices.py`, `app/routes/indices.py`, `app/__init__.py` (schema `IndiceEconomico` e texto R8 do Swagger), `config.py`, `.env.example`, `tests/integrations/{test_bacen.py,test_bacen_http.py,servidor_falso.py}`

- [x] Cliente `requests` (`integrations/bacen.py`, sem Flask nem banco): timeout, janela de no máximo 10 anos, interpretação estrita da resposta (uma linha inválida invalida tudo; datas futuras ignoradas; HTTP 404 "Value(s) not found" = sem dados), e `BacenIndisponivel` com mensagem genérica (o motivo real só vai para o log, sem URL nem corpo).
- [x] **Só CDI e IPCA — a Selic ficou de fora por decisão do autor:** **CDI = série 4389** (CDI anualizada base 252, % a.a.) e **IPCA = série 13522** (acumulado em 12 meses, % a.a.), sem conversão de unidade. A sugestão de IPCA é o acumulado **realizado** (o SGS não tem projeção). `GET /api/indices/{cdi|ipca}?periodo=` (JWT); `selic`, `CDI` maiúsculo e qualquer outro → 404 "Índice não encontrado". O valor `SELIC` do enum/CHECK do banco fica reservado, sem uso.
- [x] **Contrato:** `indice`, `descricao`, `unidade`, `serie_sgs`, `sugestao` (`valor`, `data_referencia`: o mais recente até hoje), `periodo` (`inicio`, `fim`), `pontos` (crescentes, sem datas futuras), `atualizado_em`, `desatualizado`. `periodo` aceita `1m|3m|6m|12m|24m|60m` (padrão `12m`), outro → 422; só filtra o cache.
- [x] **Cache:** sob demanda, **TTL de 12 h**, **janela fixa de 60 meses**, `INSERT ... ON CONFLICT DO UPDATE` (a restrição única segura a corrida); sem agendador (APScheduler continua fora).
- [x] **BACEN fora do ar:** com cache → 200 com `desatualizado: true`; sem cache → **503** "Dados do Banco Central indisponíveis no momento". Sem nova tentativa automática.
- [x] **Configuração opcional por ambiente:** `BACEN_URL_BASE`, `BACEN_TIMEOUT_SEGUNDOS` (8), `INDICES_TTL_HORAS` (12); valor inválido derruba a subida.
- [x] **Decisão 11 da Etapa 2 descartada:** a API **não** grava taxa sugerida quando omitida; as taxas seguem obrigatórias no `POST`/`PUT` da simulação, que não depende do BACEN. O frontend pré-preenche o formulário com `sugestao.valor`.
- [x] Swagger: rota com contrato, erros (inclusive 503) e texto da API externa (R8: fonte, sem cadastro, rotas usadas, consumo pelo backend; licença ODbL confirmada no catálogo do portal para outras séries do SGS, mas **não** listada individualmente para 4389/13522 — o texto não afirma além disso).

**Validado:** 617 testes no `pytest` (62 novos: interpretação com payloads reais, servidor HTTP falso local); scripts descartáveis (cache 32, consulta 33, schema 23); ponta a ponta com o servidor falso (62 verificações: cache, TTL real, 8 modos de falha com e sem cache, timeout, datas futuras, 8 requisições simultâneas, 401/404/422, log sem Traceback); conferência com a **API real** (sugestão e todas as linhas iguais a um `curl` direto: CDI 1.255 linhas, IPCA 60; segunda chamada sem rede); Swagger UI conferido por você; regressão das Etapas 1 a 7 verde, `flask db migrate` sem mudanças, `requirements.txt` inalterado.
**Levado adiante:** Etapa 10 — testes de integração da rota `/api/indices/*` com o servidor falso (`tests/integrations/servidor_falso.py`) e o contrato sem `selic`; Etapa 11 — conferir na imagem os dados de fuso (`tzdata`, exigidos pelo `zoneinfo` que calcula "hoje" em `America/Sao_Paulo`) e as variáveis do BACEN; Etapa 12 — seção da API externa (R8) no README.

## Etapa 9 — ~~Extras de criatividade~~ (eliminada)
**Status: eliminada em 2026-09-25, por decisão do autor.** Paginação, ordenação, filtros e CET **não serão implementados**. A numeração das demais etapas foi mantida (as specs e o `CLAUDE.md` se referem a elas). O **R4** ("funcionalidades extras além do CRUD básico, ex.: autenticação, ordenação, filtros, paginação") fica atendido pelos extras já entregues: **autenticação JWT** com isolamento por usuário (Etapa 3), cálculo dos 3 cenários com séries e `/parcelas` (Etapa 7) e índices do BACEN com cache (Etapa 8). `GET /api/simulacoes` permanece como está: envelope `{"itens", "total"}`, mais recentes primeiro, sem parâmetros.

## Etapa 10 — Swagger completo e testes de integração
**Status: concluída em 2026-09-26** (spec: `docs/specs/2026-09-25-swagger-e-testes-de-integracao.md`).
**Arquivos:** `tests/conftest.py`, `tests/banco_de_teste.py`, `tests/api/`, `tests/test_banco_de_teste.py`, `pytest.ini`, `.env.example`, `app/__init__.py` (CORS, `tags` e "Convenções da API"), docstrings de `app/routes/{simulacoes,financiamentos}.py`

- [x] **Infraestrutura:** banco de teste **`bd_test`** no mesmo container (criado pela fixture; `TEST_DATABASE_URL` opcional), schema por `flask db upgrade`, `TRUNCATE ... RESTART IDENTITY` entre os testes, **trava** que recusa nome de banco sem o sufixo `_test`; marcador `integracao` automático em `tests/api/`; sem banco os testes são **pulados com aviso** e `pytest -m integracao` **falha**.
- [x] **419 testes de integração** (`tests/api/`): saúde e autenticação (401 de 6 tipos de token), simulações (107, regras de campo parametrizadas), financiamentos (87: limite de 3 e ordem dono → corpo → estado), `/parcelas` e `/resultado` (números da spec da Etapa 7 e **referência independente** em `Fraction`/`Decimal`), índices com o servidor falso (cache, TTL sem `sleep`, 10 modos de falha com e sem cache, 503, timeout, concorrência), isolamento entre usuários (mesmo 404 para alheio e inexistente), fluxo completo, **corrida real** (2 cenários, com **controle sem bloqueio que fura a regra**), CORS e o teste estrutural do Swagger.
- [x] **Swagger:** revisão das 16 operações (descrição dos parâmetros de caminho, texto do 422 do `/resultado`), `tags` de topo em ordem fixa, seção "Convenções da API" com a nota do **500**; `test_openapi.py` valida estrutura, `$ref`, `security`/401, 400/415/422, caminhos iguais a `app.url_map` (16 rotas); mapa informativo "códigos documentados × provocados" no fim do `pytest`: **nenhum código sem teste**.
- [x] **CORS:** `expose_headers=["Location"]`, `max_age=600` e padrão restrito a `r"/api/.*"` (o antigo `/api/*` também cobria `/apidocs/` e `/apispec.json`); testado com as origens do frontend e origens estranhas.

**Validado:** suíte completa **1055 testes em ~24 s** (636 sem banco + 419 de integração), 3 execuções seguidas e uma com a ordem dos arquivos invertida; **testes de sensibilidade** (mutações em cópia: teto do prazo, limite de opções, dono da simulação, `FOR UPDATE` removido, TTL infinito, datas futuras, arredondamento do Price, +1 centavo no aporte, CORS antigo, 9 mutações de docstring); corrida 20 vezes seguidas verde; banco `emerson` intacto; regressão dos scripts ponta a ponta das Etapas 4 a 8; percurso manual no `/apidocs/` confirmado por você.
**Decisões do plano (não estavam explícitas na spec):** usuários de teste inseridos direto no banco com o hash da senha em cache (o scrypt real só nos testes de `auth` e no fluxo completo); um único aviso de depreciação ignorado no `pytest.ini` (`get_engine` do `migrations/env.py` gerado pelo Flask-Migrate, débito para o Flask-SQLAlchemy 3.2); padrão de CORS restrito (decisão sua).
**Levado adiante:** Etapa 11 — (concluída) imagem com os dados de fuso e as variáveis no `.env.docker`; os testes ficam fora do Docker; Etapa 12 — README com como rodar a suíte (`pytest`, `-m "not integracao"`, `-m integracao`, `TEST_DATABASE_URL`) e a seção da API externa (R8).

## Etapa 11 — Dockerfile (R3)
**Status: concluída em 2026-09-26** (spec: `docs/specs/2026-09-26-dockerfile.md`).
**Arquivos:** `Dockerfile`, `.dockerignore`, `docker-entrypoint.sh`, `.env.docker.example`, `.gitignore` (linha `.env.docker`)

- [x] **`Dockerfile`** (`python:3.12-slim`, 295 MB): instala **só** o `requirements.txt` (+ `pip check`), copia `app/`, `migrations/`, `config.py`, `run.py` e o *entrypoint*; usuário **não-root** (`app`, uid/gid 10001), `EXPOSE 5000`, `HEALTHCHECK` em Python puro sobre `GET /api/saude` (a imagem não tem `curl`); **nenhum segredo** na imagem (tudo entra por `--env-file`).
- [x] **Trava de fuso:** um `RUN` que resolve `America/Sao_Paulo` (o `zoneinfo` dos índices); o *build* falha se a base deixar de trazer os dados (provado com um fuso inexistente). Sem o pacote Python `tzdata`.
- [x] **Migrations:** o `docker-entrypoint.sh` roda `flask db upgrade` a cada partida e depois `exec gunicorn run:app` (`0.0.0.0:5000`, `WEB_CONCURRENCY` = 2, `--timeout 30`, `--no-control-socket`, logs na saída padrão); com argumentos executa o comando pedido **sem migrar** (`flask routes`, `sh`).
- [x] **Sem `docker-compose.yml`** (decisão do autor): a API alcança o PostgreSQL por `DATABASE_URL`, numa **rede Docker própria** (`rota-financeira-net`) à qual se liga o contêiner do banco (`docker network connect`); variáveis num **`.env.docker`** local (ignorado pelo git e pela imagem), com o `.env.docker.example` versionado. Testes fora do Docker (a imagem é só de produção).

**Comandos** (raiz do projeto): `docker build -t rota-financeira-api .`; `docker network create rota-financeira-net` e `docker network connect rota-financeira-net rota-financeira-db`; `docker run -d --name rota-financeira-api --network rota-financeira-net --env-file .env.docker -p 5000:5000 rota-financeira-api`; `docker logs rota-financeira-api`; para encerrar: `docker rm -f rota-financeira-api`, `docker network disconnect ...`, `docker network rm ...`.
**Validado:** *build* sem aviso; conteúdo da imagem (sem `tests`, `docs`, `tmp`, `.env*`, `CLAUDE.md`, `pytest`); subida contra um PostgreSQL descartável (migração, `healthy`, `/apidocs/` 200); fluxo completo no contêiner (25 verificações com o **BACEN real**: custos da Etapa 7, índices 4389 e 13522, CORS); falhas (sem `JWT_SECRET_KEY`/`DATABASE_URL` e banco inacessível → saída 1 com mensagem; banco parado → 503 e `unhealthy` sem derrubar o processo; volta a `healthy`); persistência a `stop`/`start` e à recriação; outra porta; roteiro documentado contra o banco de desenvolvimento (somente leitura, depois desfeito) e a suíte de integração verde logo em seguida; sem segredo na imagem (`docker save` e `docker history`); 1055 testes, `flask db migrate` sem mudanças e `requirements*` inalterados; percurso manual seu com o `.env.docker` real.
**Achados:** o gunicorn 26 abre por padrão um socket de controle em `~/.gunicorn/` e registrava um `ERROR` (o usuário não tem home): desligado com `--no-control-socket`; a mensagem de variável faltando da `config.py` fala em "copiar `.env.example` para `.env`" (dentro do Docker vale o `--env-file`).
**Levado adiante:** Etapa 12 — o README documenta os comandos acima, a criação do `.env.docker` (sem colocar a senha no `.example`), o `docker run` do banco (seção "Banco de dados" do `CLAUDE.md`) e a coexistência com o ambiente local.

## Etapa 12 — README com fluxograma (R2 e R8)
**Status: concluída em 2026-09-26** (spec: `docs/specs/2026-09-26-readme-e-fluxograma.md`).
**Arquivos:** `README.md` (reescrito do zero), `docs/img/arquitetura.dot` (fonte), `docs/img/arquitetura.png`, `docs/img/arquitetura.svg`

- [x] **README** do Rota Financeira (o antigo era do `manutencao-api`): título e descrição dos 3 cenários, funcionalidades, arquitetura (imagem + legenda dos 5 passos + camadas), tecnologias com versões, instalação e execução local, variáveis de ambiente, execução com Docker, testes, **API externa (R8)**, tabela das 16 rotas com o contrato de `/resultado` e das taxas sugeridas, estrutura de pastas e autoria; links para os dois repositórios.
- [x] **Fluxograma** (R2) em **Graphviz**: uma imagem só com a arquitetura e o cenário numerado (usuário compara como comprar um carro: login, taxa sugerida via cache/BACEN, simulação, `/resultado`, exibição). Regerar, em `docs/img`: `dot -Tpng -Gdpi=100 arquitetura.dot -o arquitetura.png` e `dot -Tsvg arquitetura.dot -o arquitetura.svg` (saída idêntica à versionada).
- [x] **API externa (R8):** BACEN/SGS, séries 4389 e 13522, sem cadastro, licença ODbL com a ressalva verificada, consumo pelo backend, cache de 12 h; **bate** com o texto do Swagger.
- [x] Rotas sem exemplos `curl` (o Swagger é o contrato completo); comandos de Linux/macOS (bash), com WSL ou Docker para Windows (só entra o que foi executado).

**Validado:** tabela de rotas × `/apispec.json` (as mesmas 16, com a autenticação), variáveis × `config.py`/`.env.example`/`.env.docker.example` (nenhuma falta ou sobra), versões × `requirements.txt`, links e âncoras, títulos, tabelas e blocos de código; **execução literal do README do zero** numa cópia limpa: caminho local (venv, `pip install`, `.env`, PostgreSQL em contêiner, migrations, `flask run`, fluxo curto com o BACEN real, os 1055 testes) e caminho Docker (build, rede, `.env.docker`, `docker run`, fluxo curto, limpeza que o README ensina); sem segredos no README, no PNG e no SVG; 1055 testes e `flask db migrate` sem mudanças; leitura sua do README e da imagem.
**Achados corrigidos no texto:** `gunicorn run:app` escuta na porta **8000** (não na 5000); a linha comentada `TEST_DATABASE_URL` do `.env.example` também tem o marcador `troque-esta-senha`.
**Levado adiante:** Etapa 13 — o repositório do **frontend** (`github.com/erbraga/rota_financeira-frontend`, link do README) respondeu **404 anônimo** em 2026-09-26 (privado ou ainda não publicado): torná-lo **público** e conferir que o link abre (R10).

## Etapa 13 — Revisão final e entrega (R10)
- [ ] Conferir o checklist R1 a R10 do `CLAUDE.md` e atualizar a lista.
- [ ] Nomes de arquivos em `snake_case`, estrutura de pastas conforme a proposta, sem código morto.
- [ ] Nenhum segredo commitado; `.env.example` atualizado.
- [ ] Remover do `requirements.txt` o que não for usado; atualizar o `CLAUDE.md` com o estado final.


---

## Riscos e pontos de atenção
- **Precisão financeira:** usar `Decimal` de ponta a ponta; conferir os resultados contra uma planilha.
- **Contrato com o frontend:** definir o JSON de `/resultado` na etapa 7 e evitar mudanças depois; qualquer mudança precisa ser avisada ao outro módulo.
- **Dependência do BACEN:** os cálculos não podem depender dele em tempo de requisição; só as sugestões de taxa dependem.
- **R7:** o enunciado cita BrasilAPI/FIPE, mas o projeto decidiu atender com o BACEN/SGS — confirmar isso com o professor antes da entrega.

## Decisões em aberto (resolver nas specs)
- Limite de opções por simulação e expiração do JWT (etapas 3 e 5).
- Convenção de arredondamento e caso de taxa zero (etapa 6).
- ~~Política de expiração do cache do BACEN (etapa 8)~~ — resolvida: TTL de 12 h, janela de 60 meses.
- ~~Escopo de paginação, ordenação e filtros; se o CET entra (etapa 9)~~ — resolvida: nada disso será implementado.
- ~~Dockerfile isolado ou docker-compose com Postgres (etapa 11)~~ — resolvida: só o Dockerfile, sem compose.
