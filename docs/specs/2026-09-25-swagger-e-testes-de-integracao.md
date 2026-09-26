# Swagger completo e testes de integração (Etapa 10) — Spec

**Criado em:** 2026-09-25
**Status:** Implementada (2026-09-26) — 1055 testes (636 sem banco + 419 de integração) e percurso manual no Swagger confirmado
**Origem:** Etapa 10 de `plano.md`; requisitos R1 e R5 (API REST com Swagger cobrindo POST, PUT, DELETE e GET)

## Problema
As 16 rotas da API (Etapas 1 a 8) foram validadas até aqui por **scripts descartáveis** e
pela conferência manual no Swagger UI; o `pytest` cobre apenas os cálculos e o cliente do
BACEN (617 testes, nenhum toca a API nem o banco). Quem clonar o repositório não tem como
provar que a API funciona, e qualquer regressão futura (Dockerfile, README, ajustes)
depende de reexecutar à mão dezenas de verificações que hoje vivem fora do repositório.

A documentação Swagger existe e está bem coberta, mas nunca foi conferida **de forma
sistemática** nem é protegida por teste.

Estado verificado (2026-09-25, lendo o código e consultando `/apispec.json`):

- **Swagger:** OpenAPI 3.0.2; **16 operações** em 5 tags (Autenticação, Financiamentos,
  Índices, Saúde, Simulações), todas com `summary`, `tags` e respostas com `description`;
  as 13 protegidas têm `security: BearerAuth` e resposta 401; as com corpo têm
  `requestBody` e respostas 400/415/422; **20 schemas** em `components`, todos
  referenciados e **nenhum `$ref` quebrado**. Exemplos estão nas **propriedades** dos
  schemas e nas respostas de erro. Lacunas encontradas:
  - não há `tags` no nível raiz: o Swagger UI ordena os grupos alfabeticamente
    (Autenticação, Financiamentos, Índices, Saúde, Simulações) e sem descrição;
  - o **500** (erro interno genérico) não está documentado em nenhuma rota nem no texto
    geral; o **405** também não (irrelevante para o frontend);
  - não há **validação automática** do documento: nada impede que uma edição futura de
    docstring quebre o YAML de uma rota, esqueça o `security` ou deixe um `$ref` órfão;
  - não há garantia de que **o que está documentado é o que a API faz** (códigos de status
    e formato das respostas): isso só foi conferido à mão, rota a rota.
- **CORS** (`flask-cors`, `resources={r"/api/*": {"origins": CORS_ORIGINS}}`, padrão
  `http://localhost:5173,http://localhost:3000`): o preflight de `Origin` permitido responde
  200 com `Allow-Origin` e `Allow-Headers: authorization, content-type`; origem não listada
  (`evil.example`, `localhost:5174`) responde 200 **sem** cabeçalhos CORS (o navegador
  bloqueia — comportamento correto); as respostas de erro (401, 404, 405, 415) também levam
  `Allow-Origin`. Duas lacunas: **`Location` (201) e `WWW-Authenticate` (401) não são
  expostos** (`Access-Control-Expose-Headers` ausente), então o JavaScript do frontend
  **não consegue ler `Location`** (o corpo do 201 já traz o `id`, então não quebra nada hoje);
  e o preflight não tem **`Max-Age`**, de modo que o navegador repete o `OPTIONS` antes de
  cada requisição com `Authorization`.
- **Testes:** `pytest.ini` (`testpaths = tests`, `DeprecationWarning` vira erro), `tests/` com
  `calculo/` (555) e `integrations/` (62, com `servidor_falso.py`); **não existe `conftest.py`**
  nem `tests/api/`; o `Config` lê `DATABASE_URL` e `JWT_SECRET_KEY` do `.env` já na
  importação, e `create_app(config_dict)` permite sobrescrever qualquer chave (inclusive
  `SQLALCHEMY_DATABASE_URI`, `BACEN_URL_BASE` e `INDICES_TTL_HORAS`).
- **Banco:** um único banco de desenvolvimento (`emerson`) no container
  `rota-financeira-db` (PostgreSQL 18); o papel `emerson` é superusuário (pode criar bancos).
  Só existe a migration inicial, e `flask db migrate` não detecta mudanças.
- **Material a aproveitar:** os scripts descartáveis já cobrem, por HTTP, simulações (36
  verificações), financiamentos (56), resultado (55), índices (62), erros de JWT (9), além
  de serviços e schemas — são o **roteiro** dos testes, não código a copiar.
- **Bloqueio de linhas:** as rotas que contam ou comparam linhas usam
  `obter_simulacao(..., bloquear=True)` (`SELECT ... FOR UPDATE`); a spec da Etapa 5 exige
  um teste de corrida real com controle sem bloqueio que falhe — hoje só foi feito em
  script.

## Objetivo
Levar a validação da API para dentro do repositório, no mesmo `pytest`: uma suíte de
integração contra um PostgreSQL de teste **separado** do de desenvolvimento, que cubra as
16 rotas, os erros documentados, o isolamento entre usuários e os índices do BACEN (com o
servidor falso); e fechar o Swagger com uma revisão completa e um teste que o proteja de
regressões, além de conferir o CORS com a origem do frontend.

## Fora de escopo
- Paginação, ordenação, filtros e CET (Etapa 9 **eliminada** pelo autor).
- Dockerfile, `docker-compose`, README e fluxograma (Etapas 11 e 12); CI (GitHub Actions)
  — não existe hoje e não é pedido.
- Mudar o contrato de qualquer rota, regra de negócio ou schema de banco (nenhuma migration
  nesta etapa); se um teste revelar um defeito, ele é **relatado e corrigido só com aviso**,
  como qualquer bug.
- Limitação de tentativas (*rate limiting*) em login/registro e tratamento global de banco
  fora do ar (`OperationalError` → 503): permanecem como débitos conhecidos do
  `CLAUDE.md`, salvo decisão em contrário abaixo.
- Testes de carga/desempenho e testes de navegador (Selenium/Playwright); o teste do
  frontend é do outro repositório.
- Reescrever ou apagar os 617 testes existentes (permanecem como estão).
- A conferência manual dos dados reais do BACEN (já feita na Etapa 8); os testes usam só o
  servidor falso, **sem rede**.

## Proposta

### 1. Infraestrutura de testes de integração
- **`tests/conftest.py`** (novo) com as fixtures compartilhadas: aplicação de teste,
  `client`, criação de usuários/tokens, limpeza entre testes, servidor falso do BACEN.
- **Banco de teste separado** no mesmo container: `bd_test`, criado pela própria
  fixture se não existir; schema criado por **`flask db upgrade`** (Alembic — o teste
  exercita a migration de verdade e as CHECKs/UNIQUE reais); **`TRUNCATE ... RESTART
  IDENTITY CASCADE`** entre os testes (o `commit` real da aplicação e os testes de corrida
  exigem dados efetivados, então não cabe "transação com rollback").
- **Trava de segurança:** as fixtures **recusam** rodar se o nome do banco não terminar em
  `_test`, para nunca truncar o banco de desenvolvimento.
- Testes marcados (`@pytest.mark.integracao`, registrado em `pytest.ini`) ficam em
  **`tests/api/`**; `pytest` roda tudo; `pytest -m "not integracao"` roda só os testes sem
  banco (os 617 atuais, ~2,5 s).
- **Sem dependência nova** (decisões 7 e 9): `requirements.txt` e `requirements-dev.txt`
  não mudam. `TEST_DATABASE_URL` é opcional e entra comentada no `.env.example`; sem ela,
  usa-se `bd_test` na instância de `DATABASE_URL` (decisões 1 e 2).

### 2. Testes de integração da API (`tests/api/`)
Um arquivo por área, usando o `test_client` do Flask (sem servidor HTTP), seguindo o roteiro
dos scripts descartáveis, **com valores conferidos por referência independente** quando
houver número (os do exemplo da spec da Etapa 7):

| Arquivo | Cobre |
|---|---|
| `test_saude.py` | `GET /api/saude` 200 (e 503 com banco inacessível, simulado com URI inválida) |
| `test_auth.py` | registrar (201, 409, 422 em português, e-mail normalizado), login (200, 401 igual para e-mail inexistente e senha errada), perfil; **401 de token** ausente/inválido/expirado com `WWW-Authenticate` |
| `test_simulacoes.py` | CRUD completo (201 + `Location`, envelope `itens`/`total`, `PUT` substitui tudo, 204 sem corpo, tetos e casas decimais 422, ids gigantes, `PUT` recusado se ≤ entrada de opção) |
| `test_financiamentos.py` | CRUD das opções, limite de **3** (4º → **409**), `valor_entrada` estritamente menor que o veículo, `sistema_amortizacao` em qualquer caixa, ordem de verificação (404 → corpo → 409) |
| `test_resultado.py` | `/parcelas` e `/resultado` com os números do exemplo da Etapa 7, séries com `null`, `menor_custo` e desempate, modo `aporte_mensal` (1500 → mês 46; 300 → `null`), 9 parâmetros inválidos em 422, simulação sem opções |
| `test_indices.py` | `GET /api/indices/{cdi\|ipca}` com o **servidor falso** (`BACEN_URL_BASE`): cache, TTL (envelhecendo `atualizado_em` no banco, sem `sleep`), `desatualizado`, 503 sem cache, 401, 404 (`selic`, `CDI`), 422 do `periodo`, datas futuras ignoradas |
| `test_isolamento.py` | dois usuários: cada rota aninhada devolve o **mesmo 404** para recurso alheio e inexistente |
| `test_fluxo_completo.py` | registrar → login → criar simulação → adicionar 2–3 financiamentos → `/resultado` → excluir (o fluxo do frontend) |
| `test_concorrencia.py` | **corrida real** (duas threads): dois `POST` simultâneos quando falta 1 vaga para as 3 opções, e `PUT` da simulação × `PUT` de opção; cada um com **controle sem bloqueio que falha**, provando que o teste é sensível |
| `test_cors.py` | preflight de origem permitida (com `Authorization`) e de origem não permitida; `CORS_ORIGINS` vazio; cabeçalhos nas respostas de erro |
| `test_openapi.py` | ver seção 3 |

Regras dos testes: cada teste independente (banco limpo pela fixture), nomes em português e
mensagens de falha legíveis; sem dependência de ordem, de relógio real nem de rede
(BACEN só pelo servidor falso); tempo total esperado da suíte inteira **< 30 s**.

### 3. Revisão e proteção do Swagger
- **Revisão de todas as docstrings** das 16 operações (parâmetros, corpos de exemplo,
  respostas de erro, `security`), corrigindo o que a comparação com o comportamento real
  (item 2) apontar. Como cada código de status documentado passa a ter um teste que o
  provoca, a documentação deixa de ser "de memória".
- **Ajustes já identificados:** `tags` no nível raiz com descrição e ordem fixa (Saúde →
  Autenticação → Simulações → Financiamentos → Índices); documentar o **500** (mensagem
  genérica, sem detalhes) no texto geral do Swagger.
- **`tests/api/test_openapi.py`** (sem rede): `/apispec.json` é OpenAPI 3.0.x; todo `$ref`
  resolve e todo schema é usado; **toda** operação `/api/*` tem `summary`, `tags`,
  `description` nas respostas, `security: BearerAuth` + resposta 401 se não for pública
  (`saude`, `registrar`, `login`), `requestBody` + 415/422 quando aceita corpo, respostas de
  erro apontando para o schema `Erro`; os caminhos do documento coincidem com
  `app.url_map` (nenhuma rota sem documentação nem documentação de rota que não existe);
  o botão *Authorize* (`BearerAuth`, `http`/`bearer`) continua declarado.
- **Percurso manual final:** ao término, você percorre o `/apidocs/` executando cada rota
  (com *Authorize*), guiado por um roteiro que eu entregarei — item de validação do
  `plano.md`.

### 4. CORS
- Conferido pelo `test_cors.py` (origens `http://localhost:5173` e `:3000` liberadas;
  outras sem cabeçalhos; nada de `*`).
- Correções das duas lacunas encontradas (decisão 6): `expose_headers=["Location"]` (o
  frontend poderá ler `Location`) e `max_age=600` no preflight.

### Casos de borda relevantes
- **Segurança do banco de dev:** trava do sufixo `_test` (acima); a fixture nunca lê nem
  escreve em `emerson`.
- **Corrida e `TRUNCATE`:** as threads dos testes de concorrência usam conexões próprias e
  a limpeza só ocorre depois de todas terminarem (`join`).
- **Hash de senha:** cada `registrar`/`login` custa ~72 ms de scrypt; a fixture cria
  usuários e tokens **diretamente pelo serviço** (`registrar_usuario`, `criar_token`) e só os
  testes de `auth` passam pelo HTTP, para manter a suíte rápida.
- **Servidor falso:** uma instância por teste (sobe em porta livre, ~ms), `BACEN_URL_BASE`
  apontando para ela; o TTL é vencido reescrevendo `atualizado_em`, nunca dormindo.
- **Banco de teste ausente/inacessível:** os testes `integracao` são pulados com aviso (e
  `pytest -m integracao` falha) — decisão 3.
- **Avisos de depreciação viram erro** (`pytest.ini`): a suíte nova precisa passar com isso.

## Decisões em aberto
1. ~~**Como isolar o banco de teste**~~ — **RESOLVIDA (2026-09-25): (a)**, com o
   banco de teste chamado **`bd_test`**: no mesmo container do PostgreSQL, criado pela
   fixture se não existir, schema via `flask db upgrade` (Alembic), `TRUNCATE ... RESTART
   IDENTITY CASCADE` entre os testes e trava que recusa rodar em banco cujo nome não termine
   em `_test` (`bd_test` atende). `create_all`, container efêmero e SQLite ficam descartados.
2. ~~**Como configurar o banco de teste**~~ — **RESOLVIDA (2026-09-25): (a)**: variável
   opcional `TEST_DATABASE_URL`; se ausente, usa o banco **`bd_test`** na mesma instância de
   `DATABASE_URL` (mesmo host, porta, usuário e senha; a senha só existe no `.env`, nunca em
   arquivo versionado); documentada, comentada, no `.env.example`. A trava do sufixo `_test`
   vale também para um `TEST_DATABASE_URL` informado.
3. ~~**O que fazer quando o PostgreSQL de teste não está acessível**~~ — **RESOLVIDA
   (2026-09-25): (a)**: sem banco, os testes `integracao` são **pulados com aviso claro**
   ("suba o container: `docker start rota-financeira-db`") e o resto da suíte roda; o resumo
   (`-ra`) lista os pulados. `pytest -m integracao` **falha** se não houver banco (é o comando
   para conferir antes de entregar ou commitar).
4. ~~**Escopo dos testes: só pela API ou também unidades de serviços/schemas**~~ —
   **RESOLVIDA (2026-09-26): (a)**: só a API (`tests/api/`), que já exercita schemas e
   serviços por dentro, com testes **parametrizados** para as regras de campo (tetos, casas
   decimais, caixa, tipos); os scripts descartáveis servem de roteiro e não são portados um a
   um; não haverá `tests/schemas/`.
5. ~~**Teste de corrida real e seu controle sem bloqueio**~~ — **RESOLVIDA
   (2026-09-26): (a)**: os dois cenários entram na suíte (`POST` simultâneo de opções com
   1 vaga restante, e `PUT` da simulação × `PUT` de opção), cada um com o **controle sem
   bloqueio que falha**, provando que o teste detecta a ausência do `FOR UPDATE`.
6. ~~**CORS: corrigir as lacunas achadas**~~ — **RESOLVIDA (2026-09-26): (a)**:
   `expose_headers=["Location"]` e `max_age=600` no `CORS(...)` de `app/__init__.py`, cobertos
   por `test_cors.py`; nenhum contrato de rota muda; `WWW-Authenticate` fica de fora (o
   frontend decide pelo status 401).
7. ~~**Validação do documento OpenAPI**~~ — **RESOLVIDA (2026-09-26): (a)**:
   verificação **estrutural própria** em `test_openapi.py` (regras da seção 3), sem
   dependência nova; nada de `openapi-spec-validator` nem `jsonschema`.
8. ~~**Tratar banco fora do ar globalmente**~~ — **RESOLVIDA (2026-09-26): (a)**: fora
   do escopo; continua como débito conhecido no `CLAUDE.md` (500 genérico nas rotas que usam o
   banco; só `/api/saude` responde 503). Esta etapa apenas testa e documenta o comportamento
   atual.
9. ~~**Cobertura de código (`pytest-cov`)**~~ — **RESOLVIDA (2026-09-26): (a)**: não
   adicionar; a cobertura fica garantida pelos critérios de aceite (cada uma das 16 rotas e
   cada código de status documentado com teste). Nenhuma dependência nova nesta etapa.

## Critérios de aceite
- [x] `pytest` na raiz roda **todos** os testes (os 617 atuais + `tests/api/`) e passa, em
      menos de 30 s; sem banco no ar, os testes `integracao` são **pulados com aviso** e os
      demais passam (`pytest -m "not integracao"` também); `pytest -m integracao` **falha**
      sem banco.
- [x] Os testes de integração usam **somente** o banco de teste (`bd_test` ou o
      configurado por `TEST_DATABASE_URL`), recusam-se a rodar em banco cujo nome não termine em `_test`, criam o
      schema por `flask db upgrade` e deixam o banco de desenvolvimento **intacto** (tabelas
      do `emerson` inalteradas antes/depois de uma execução completa).
- [x] As **16 operações** têm teste de caminho feliz e **cada código de status documentado**
      no Swagger é provocado por pelo menos um teste (200/201/204, 400, 401, 404, 409, 415,
      422, 503 — o 503 de índices com o servidor falso e o de saúde com banco inacessível).
- [x] O fluxo registrar → login → simulação → financiamentos → resultado passa com os
      números do exemplo da Etapa 7 (custos, séries com `null`, `menor_custo`, modo
      `aporte_mensal`); o 4º financiamento dá 409; o isolamento entre dois usuários devolve o
      mesmo 404 para recurso alheio e inexistente em todas as rotas aninhadas.
- [x] Índices: cache, TTL (sem `sleep`), `desatualizado`, 503 sem cache, 401, 404 de `selic`
      e `CDI`, 422 do `periodo`, datas futuras ignoradas — tudo com o servidor falso e **sem
      rede**.
- [x] A corrida real é reproduzida (duas threads) e um **controle sem bloqueio falha**,
      comprovando que o teste detecta a ausência do `FOR UPDATE` (decisão 5).
- [x] O `/apispec.json` é validado pelo `test_openapi.py` (estrutura, `$ref`, `security`,
      401/415/422, caminhos iguais a `app.url_map`); as `tags` de topo, na ordem definida, e a
      nota do **500** aparecem no Swagger UI; nenhuma docstring foi deixada sem revisão.
- [x] CORS: origens do frontend passam no preflight com `Authorization`; origem estranha
      não recebe cabeçalhos CORS; `CORS_ORIGINS` vazio libera nenhuma origem; `Location` exposto e
      `Max-Age` presente (decisão 6).
- [x] `flask db migrate` sem mudanças; `requirements.txt` e
      `requirements-dev.txt` inalterados; `.env.example` com `TEST_DATABASE_URL` comentada;
      nenhum segredo em arquivo versionável; `plano.md` e `CLAUDE.md` atualizados (estrutura
      `tests/api/`, como rodar a suíte, variável de teste, regras de isolamento).
- [x] **Você** percorre o `/apidocs/` executando cada rota com *Authorize* (roteiro
      entregue no fim da etapa) e confirma.

---

## Plano de Implementação

Tarefas na ordem de execução. Nenhuma faz `git add`/`commit`/`push` (só quando você pedir).
Pré-requisitos: `.venv` ativo, raiz do projeto como diretório de trabalho e o banco no ar
(`docker start rota-financeira-db`). A validação de cada tarefa é o próprio `pytest`
(`pytest tests/api/<arquivo>` na tarefa e a suíte inteira ao final), mais **testes de
sensibilidade**: sempre que um teste protege uma regra, ele é conferido quebrando a regra de
propósito (num script descartável no diretório temporário da sessão, sem alterar o código
versionado) para provar que o teste falha quando deveria. Os scripts descartáveis das etapas
anteriores servem de roteiro de casos; **os valores esperados vêm das specs** (números
conferidos à mão) ou de uma conta independente, nunca da função testada.

Detalhes de projeto que o plano fixa (não estavam explícitos na spec):
- **Marcador automático:** todo teste sob `tests/api/` recebe `@pytest.mark.integracao` por um
  gancho de coleta em `tests/conftest.py` (sem repetir o decorador em cada teste); o marcador é
  registrado em `pytest.ini` (o `-ra` já lista os pulados).
- **Aplicação de teste única por sessão** (`create_app` com `SQLALCHEMY_DATABASE_URI` do banco de
  teste e `TESTING`); o que muda de teste para teste (`BACEN_URL_BASE`, `INDICES_TTL_HORAS`,
  `BACEN_TIMEOUT_SEGUNDOS`) é alterado em `app.config` por `monkeypatch`, já que `indices.py` lê
  `current_app.config` a cada chamada. Isso evita criar e descartar um pool de conexões por teste.
- **Criação do banco:** conexão de manutenção ao banco `postgres` da mesma instância (mesmas
  credenciais) para `CREATE DATABASE bd_test` se ele não existir; sem esse privilégio, a mensagem
  de erro diz o que fazer. O schema vem de `flask_migrate.upgrade()` uma vez por sessão (no-op se
  já estiver na última revisão); entre os testes, `TRUNCATE` de todas as tabelas, exceto
  `alembic_version`, com `RESTART IDENTITY CASCADE`.
- **Trava:** função pura `validar_nome_banco_de_teste(url)` recusa nome que não termine em `_test`
  (vale para `TEST_DATABASE_URL` também); testada sem banco.
- **Sem banco / com `-m integracao`:** uma verificação de conexão na primeira fixture de banco:
  inacessível → `pytest.skip` com a mensagem `suba o container: docker start
  rota-financeira-db`; se a expressão `-m` da execução contém `integracao`, vira **falha**.
- **Usuários e tokens** pelas funções de serviço (`registrar_usuario`, `criar_token`), nunca pelo
  HTTP (scrypt ~72 ms); só `test_auth.py` passa pelo HTTP. Corpos de exemplo são fábricas de
  dicionário nas fixtures (uma simulação e uma opção válidas, sobrescritas por parâmetro).
- **Servidor falso do BACEN:** fixture por teste sobre `tests/integrations/servidor_falso.py`
  (sem alterá-lo); o TTL é vencido reescrevendo `atualizado_em` no banco, nunca dormindo.
- **Corrida real:** as duas threads usam clientes próprios (uma conexão do banco cada); a
  sobreposição é forçada por uma **pausa curta** (`sleep`) num ouvinte SQLAlchemy `before_insert`
  / `before_update` registrado só dentro do teste e removido no fim; o **controle sem bloqueio**
  troca, por `monkeypatch`, o `obter_simulacao` das rotas por uma versão com `bloquear=False` e o
  teste afirma que a regra **foi furada** (4 opções / entrada ≥ veículo), provando que ele
  enxerga a corrida.
- **Mapa de códigos documentados × provocados** (informativo, não reprova): um `after_request`
  registrado na aplicação de teste anota `(método, regra, status)` de cada resposta e o
  `pytest_terminal_summary` imprime, ao fim de uma execução completa, os códigos do
  `/apispec.json` que nenhum teste provocou. Serve para conferir o critério "cada código
  documentado tem teste" sem depender de memória.
- **Documentação não vira código de produção além do pedido:** as únicas mudanças fora de
  `tests/` são a linha do CORS (`app/__init__.py`), as `tags` de topo e a nota do 500 no
  `SWAGGER_TEMPLATE`, e correções de docstring que os testes apontarem (avisadas).
- Se um teste revelar defeito real na API, a tarefa **para** e o defeito é relatado antes de
  qualquer correção.

### Tarefa 1 — Infraestrutura dos testes de integração
- **Arquivos:** `pytest.ini`, `tests/conftest.py` (novo), `tests/api/__init__.py` (novo),
  `tests/api/test_infraestrutura.py` (novo), `.env.example`
- **Mudança:** registrar o marcador `integracao`; fixtures de banco (resolução de
  `TEST_DATABASE_URL`/`bd_test`, trava do sufixo, criação do banco, `upgrade`, `TRUNCATE`,
  skip/falha sem banco), `app`, `client`, fábricas de usuário/token/corpos, servidor falso e o mapa
  de códigos; `TEST_DATABASE_URL` comentada no `.env.example`.
- **Validar:** `pytest -m "not integracao"` → os 617 testes de antes, sem banco; `pytest
  tests/api/test_infraestrutura.py` prova: nome do banco é `bd_test`, tabelas vazias no início
  de cada teste, esquema vem da migration (todas as CHECKs/UNIQUE presentes), a trava recusa
  nomes como `emerson` e `bd_test_old`, e o banco `emerson` não foi tocado (contagens iguais
  antes/depois). Com o container parado (`docker stop rota-financeira-db`, depois
  `docker start`): `pytest` pula os de integração com a mensagem e os 617 passam;
  `pytest -m integracao` falha.

### Tarefa 2 — Saúde e autenticação
- **Arquivos:** `tests/api/test_saude.py`, `tests/api/test_auth.py`
- **Mudança:** `GET /api/saude` 200 e 503 (banco inacessível, com URI inválida numa aplicação
  auxiliar); registrar 201/400/409/415/422 (e-mail normalizado, mensagens em português, senha
  nunca ecoada), login 200/400/401/415/422 (401 igual para e-mail inexistente e senha errada),
  perfil 200/401 e o 401 de token ausente, inválido e expirado com `WWW-Authenticate: Bearer` e
  corpo `{"erro": ...}`; conta excluída com token válido → 401.
- **Validar:** `pytest tests/api/test_saude.py tests/api/test_auth.py` verde; teste de
  sensibilidade: fazer o login devolver 404 para e-mail inexistente e conferir que o teste falha.

### Tarefa 3 — Simulações
- **Arquivos:** `tests/api/test_simulacoes.py`
- **Mudança:** CRUD completo (POST 201 + `Location`; GET da coleção em envelope
  `itens`/`total`, mais recentes primeiro; GET por id; PUT que substitui tudo e volta
  `valor_entrada` a 0; DELETE 204 sem corpo que apaga as opções); 404 de id inexistente,
  gigante (acima de `INTEGER`) e de outro usuário; 401 em todas; 400/415/422; regras de campo
  **parametrizadas** (tetos: veículo até 9.999.999,00, IPCA −20 a 100, fundo 0 a 100, prazo 1 a
  60; excesso de casas → 422; número em texto aceito; campo desconhecido, tipo errado, `NaN`,
  `1e999999`, entrada > veículo → 422); PUT recusado com 422 em `valor_veiculo` se o novo valor ≤
  entrada de alguma opção.
- **Validar:** `pytest tests/api/test_simulacoes.py` verde; sensibilidade: relaxar um teto no
  schema (temporariamente, em cópia) e ver a linha da tabela de casos falhar.

### Tarefa 4 — Opções de financiamento
- **Arquivos:** `tests/api/test_financiamentos.py`
- **Mudança:** CRUD das opções (POST 201 + `Location`, lista em envelope na ordem de criação,
  PUT que substitui tudo, DELETE 204, sem `GET` de uma opção só → 405); limite de **3** (4º →
  409 e DELETE da última permitido); `sistema_amortizacao` em qualquer caixa e devolvido em
  maiúsculas; taxa 0 a 20 % (6 casas), prazo 1–72; `valor_entrada` estritamente menor que o
  veículo; **ordem de verificação** (dono 404 → corpo 400/415/422 → estado 409); 404 de
  simulação alheia/inexistente e de opção inexistente/de outra simulação; 401.
- **Validar:** `pytest tests/api/test_financiamentos.py` verde; sensibilidade: trocar o limite
  para 4 e ver o teste do 409 falhar.

### Tarefa 5 — `/parcelas` e `/resultado`
- **Arquivos:** `tests/api/test_resultado.py`
- **Mudança:** números do **exemplo da spec da Etapa 7** (custos, `menor_custo`, preço corrigido
  108.410,78 na compra etc.), conferidos contra os valores da spec e, onde houver conta, contra
  uma referência independente (`Fraction`); `/parcelas` (uma linha por mês, `saldo_devedor` após o
  pagamento, totais, última parcela ajustada, sem opção/opção alheia → 404); séries no eixo comum
  com `null` (fundo na compra, quitação) e chave de `saldo_devedor` = id da opção em texto;
  desempate do `menor_custo`; simulação com 0, 1 e 3 opções; modo `aporte_mensal` (1500 → mês 46;
  300 → `null`, com `alcanca_a_meta` falso e `custo_total` do fundo `null`); 9 parâmetros
  inválidos (vazio, repetido, desconhecido, negativo, 3 casas, texto, teto…) → 422 **só depois** do
  404; números como número JSON, nunca `float` de texto; 401.
- **Validar:** `pytest tests/api/test_resultado.py` verde; sensibilidade: alterar um centavo do
  valor esperado do exemplo e ver o teste falhar (garante que a comparação é exata).

### Tarefa 6 — Índices do BACEN
- **Arquivos:** `tests/api/test_indices.py`
- **Mudança:** com o servidor falso apontado por `BACEN_URL_BASE`: cache vazio → 200 com 1
  chamada e linhas gravadas; repetir → nenhuma chamada nova e `atualizado_em` igual; TTL vencido
  (reescrevendo `atualizado_em`) → nova chamada; `desatualizado` com falha (500, 406, HTML, JSON
  quebrado, linha inválida, timeout, conexão recusada) e nada gravado; **503** sem cache com a
  mensagem genérica; datas futuras ignoradas; IPCA no dia 1; os 6 períodos e o padrão `12m`;
  422 do `periodo` (`13m`, `abc`, `0`, `-1`, vazio, repetido); 404 de `selic`, `CDI`, `IPCA`;
  401 (ausente/inválido/expirado); ordem 404 → 422; a `sugestao` não muda com o `periodo`.
- **Validar:** `pytest tests/api/test_indices.py` verde e **sem rede** (rodar com a rede
  desligada ou com `BACEN_URL_BASE` real bloqueado por `monkeypatch` que falha se usado);
  sensibilidade: colocar `TTL` gigante e ver o teste de vencimento falhar.

### Tarefa 7 — Isolamento e fluxo completo
- **Arquivos:** `tests/api/test_isolamento.py`, `tests/api/test_fluxo_completo.py`
- **Mudança:** com dois usuários, **cada rota aninhada** (simulação, financiamentos, `/parcelas`,
  `/resultado`, PUT/DELETE) devolve o **mesmo 404** e o mesmo corpo para recurso alheio e
  inexistente, e nunca altera nem vaza o dado do outro; `GET` da coleção só lista os próprios; o
  fluxo do frontend: registrar → login → criar simulação → 2–3 financiamentos → `/resultado` →
  excluir opção → excluir simulação (com o token vindo do login HTTP).
- **Validar:** `pytest tests/api/test_isolamento.py tests/api/test_fluxo_completo.py` verde;
  sensibilidade: fazer `obter_simulacao` ignorar o `usuario_id` (em cópia) e ver o isolamento falhar.

### Tarefa 8 — Concorrência (corrida real)
- **Arquivos:** `tests/api/test_concorrencia.py`
- **Mudança:** dois cenários com duas threads — (1) dois `POST` de opção quando falta 1 vaga:
  exatamente um 201 e um 409, sempre 3 opções no fim; (2) `PUT` da simulação (baixando o valor
  do veículo) × `PUT` de opção (subindo a entrada): nunca fica uma entrada ≥ valor do veículo.
  Para cada um, o **controle sem bloqueio** (`bloquear=False`) tem de **furar a regra** (4 opções /
  entrada ≥ veículo), provando que o teste é sensível; a pausa vem do ouvinte SQLAlchemy.
- **Validar:** `pytest tests/api/test_concorrencia.py` verde **20 vezes seguidas** (sem
  intermitência; o controle falha sempre da mesma forma); tempo dos dois cenários ≤ ~3 s.

### Tarefa 9 — CORS
- **Arquivos:** `app/__init__.py`, `tests/api/test_cors.py`
- **Mudança:** `CORS(..., expose_headers=["Location"], max_age=600)`; testes: preflight de
  `http://localhost:5173` e `:3000` com `Authorization` e `Content-Type` (200, `Allow-Origin`
  igual à origem, `Allow-Headers`, `Max-Age: 600`); origem estranha (`evil.example`,
  `localhost:5174`) sem cabeçalhos CORS; `Access-Control-Expose-Headers` traz `Location` no 201;
  cabeçalhos também nas respostas de erro (401, 404, 415); nunca `*`; com `CORS_ORIGINS` vazio
  nenhuma origem é liberada (aplicação auxiliar).
- **Validar:** `pytest tests/api/test_cors.py` verde; `pytest` inteiro sem regressão; mudança
  restrita à linha do `CORS(...)` (conferir por diff do arquivo).

### Tarefa 10 — Revisão das docstrings e ajustes do Swagger
- **Arquivos:** `app/__init__.py` (`SWAGGER_TEMPLATE`), docstrings de `app/routes/*.py` **somente
  se** os testes das tarefas 2 a 9 apontarem divergência
- **Mudança:** `tags` de topo com descrição na ordem Saúde → Autenticação → Simulações →
  Financiamentos → Índices; nota do **500** (erro interno genérico, sem detalhes, com o schema
  `Erro`) no texto geral; revisão rota a rota de parâmetros, exemplos, respostas e `security`
  contra o que os testes provaram; qualquer divergência encontrada é listada e corrigida **na
  documentação** (o código só muda com aviso).
- **Validar:** `/apispec.json` mostra as `tags` na ordem certa e a nota do 500; a lista de
  divergências (ou "nenhuma") é apresentada; `pytest` verde; o mapa de códigos documentados ×
  provocados imprime **nenhum código sem teste** (ou justifica os que ficarem de fora).

### Tarefa 11 — Teste estrutural do Swagger
- **Arquivos:** `tests/api/test_openapi.py`
- **Mudança:** regras da seção 3 da spec: OpenAPI 3.0.x; todo `$ref` resolve e todo schema é
  usado; toda operação `/api/*` tem `summary`, `tags` e `description` nas respostas; rotas
  protegidas com `security: BearerAuth` + 401, e só `saude`, `registrar` e `login` públicas; rota
  com corpo tem `requestBody` + 415/422; respostas de erro apontam para `Erro`; caminhos do
  documento iguais a `app.url_map` (conversores `<int:...>` ↔ `{...}`, sem rota faltando nem
  sobrando); `BearerAuth` `http`/`bearer` declarado; `tags` de topo cobrem as usadas.
- **Validar:** `pytest tests/api/test_openapi.py` verde; **sensibilidade em cópia**: remover o
  `security` de uma rota, quebrar um `$ref`, apagar o `summary` de outra e registrar uma rota sem
  docstring — cada mutação precisa fazer o teste falhar com mensagem que nomeia a operação.

### Tarefa 12 — Regressão e conferência da suíte
- **Arquivos:** nenhum (só verificação)
- **Mudança:** nenhuma.
- **Validar:** `pytest` completo (617 + novos) verde e **< 30 s**; `pytest -m "not integracao"`
  sem banco; `pytest -m integracao` verde; execução repetida 3 vezes (ordem/dados residuais);
  execução com a ordem dos arquivos invertida (independência entre testes); banco `emerson`
  com as mesmas tabelas e **0 linhas** em `usuarios`, `simulacoes`, `opcoes_financiamento`,
  `indices_economicos_cache` antes e depois; `flask db migrate` sem mudanças; `pip check`;
  `requirements.txt` e `requirements-dev.txt` inalterados; `git status` só com o esperado (busca
  por segredo: senha do `.env` ausente dos arquivos versionáveis); scripts ponta a ponta das etapas
  anteriores (`e2e_*`) reexecutados como regressão contra o servidor real.

### Tarefa 13 — Percurso manual no Swagger (sua verificação)
- **Arquivos:** nenhum
- **Mudança:** subir o servidor e entregar o **roteiro** de percurso do `/apidocs/`: grupos na ordem
  das `tags`, *Authorize* só com o token, e cada uma das 16 rotas executada com sucesso e, quando
  houver, com um erro documentado (401 sem token, 404, 409 no 4º financiamento, 422), conferindo
  exemplos e descrições; o 503 de `/api/indices` não é reproduzível na UI e fica coberto pelos testes.
- **Validar:** você confirma ("funcionou"); depois removo os dados criados (usuário de teste e
  cache) e o servidor.

### Tarefa 14 — Documentação
- **Arquivos:** `plano.md`, `CLAUDE.md`, esta spec
- **Mudança:**
  - `plano.md`: marcar a Etapa 10 como concluída, com o que foi validado e o que sobrou para as
    Etapas 11 e 12 (Dockerfile precisa de `tzdata`; README com como rodar a suíte, `bd_test` e
    `TEST_DATABASE_URL`);
  - `CLAUDE.md`: estrutura (`tests/conftest.py`, `tests/api/`), como rodar (`pytest`,
    `pytest -m "not integracao"`, `pytest -m integracao`), banco `bd_test` e a variável
    `TEST_DATABASE_URL`, a trava do sufixo `_test`, regras dos testes de corrida (controle sem
    bloqueio), CORS com `Location` exposto e `Max-Age`, contagem de testes, e o "Estado atual"
    (a API deixa de ser validada só por scripts); manter o débito do banco fora do ar (500);
  - esta spec: marcar os critérios de aceite e o status como implementada.
- **Validar:** reler os três arquivos e conferir que não restam menções a "a API é validada por
  scripts descartáveis e pelo Swagger até a Etapa 10" nem à contagem antiga de testes.

### Tarefa 15 — Conferência final
- **Arquivos:** nenhum
- **Mudança:** nenhuma; verificação de todos os critérios de aceite.
- **Validar:** percorrer a lista de critérios, informar o que passou e o que dependeu da sua
  verificação manual, mostrar o resultado do `pytest` e o `git status --short` final (esperado:
  `tests/conftest.py`, `tests/api/`, `pytest.ini`, `.env.example`, `app/__init__.py`, documentação e a
  spec) e aguardar você pedir o commit.

---
*Depois de aprovada, esta spec vira a base do PLANO — não escrever
código antes disso.*
