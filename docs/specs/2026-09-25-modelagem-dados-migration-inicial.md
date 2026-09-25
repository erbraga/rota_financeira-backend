# Modelagem de dados e migration inicial (Etapa 2) — Spec

**Criado em:** 2026-09-25
**Status:** Implementada em 2026-09-25
**Origem:** Etapa 2 de `plano.md`; modelagem da seção 6 de `proposta-backend-api-rest.md`

## Problema
A aplicação sobe e conversa com o PostgreSQL (Etapa 1), mas o banco está
**vazio** e não há nenhum model. Estado verificado hoje:

- `app/` tem só `__init__.py`, `extensions.py`, `errors.py` e `routes/`; não
  existe `app/models/`.
- `app/extensions.py` cria `db = SQLAlchemy()` (base padrão do Flask-SQLAlchemy)
  e `migrate = Migrate()`; `create_app()` ainda **não importa nenhum model**,
  então o Alembic não enxergaria tabelas.
- `migrations/` foi criada por `flask db init`, com `versions/` vazia; o
  `env.py` gerado já lê o metadata de `db` (`get_metadata()`), então só falta
  haver models registrados.
- O banco `emerson` não tem tabelas (`\dt` → "Did not find any tables").
- Versões instaladas: SQLAlchemy 2.1.1, Flask-SQLAlchemy 3.1.1, Alembic 1.20.0,
  Flask-Migrate 4.1.0, psycopg 3.3.6.
- Verificação exploratória (script descartável, SQLite em memória, sem criar
  arquivos): com essas versões, models no estilo SQLAlchemy 2.0
  (`DeclarativeBase`, `Mapped`, `mapped_column`), `Numeric` → `Decimal`,
  `Enum(native_enum=False)`, `CheckConstraint`, naming convention,
  relationships com cascata e `db.get_or_404` funcionam **sem nenhum
  `DeprecationWarning`**.
- A modelagem da proposta (seção 6) deixa lacunas de tipos, tamanhos,
  nulabilidade, unicidade e comportamento de exclusão, e traz uma ambiguidade
  sobre o "aporte mensal" do fundo (ver decisão 12).

## Objetivo
Criar os models SQLAlchemy da proposta e a migration inicial, de forma que
`flask db upgrade` construa o schema completo no PostgreSQL e
`flask db downgrade` o desfaça, deixando a base pronta para as rotas de
autenticação e de simulações.

## Fora de escopo
- Rotas, schemas de validação (Marshmallow) e regras de negócio
  (autenticação, hash de senha, limite de 3 opções por simulação): Etapas 3 e 5.
- Cálculos financeiros, integração com o BACEN e preenchimento do cache de
  índices: Etapas 6 e 8.
- Dados de exemplo (*seed*) e testes automatizados (`pytest` entra na Etapa 6).
- Serialização de `Decimal` para JSON (decidida quando os schemas existirem).
- Colunas ou tabelas que a proposta não prevê, exceto as decisões abaixo.

## Proposta

### Arquivos
```
app/
  models/
    __init__.py                    # importa todos os models (para o Alembic enxergar)
    usuario.py                     # Usuario
    simulacao.py                   # Simulacao
    opcao_financiamento.py         # OpcaoFinanciamento + enum SistemaAmortizacao
    indice_economico_cache.py      # IndiceEconomicoCache + enum Indice
app/extensions.py                  # db com classe base declarativa (decisões 2 e 3)
app/__init__.py                    # create_app importa app.models
migrations/versions/<rev>_....py   # migration inicial (gerada e revisada)
```
`parcela_calculada.py` só existe se a decisão 5 mudar. Também: `CLAUDE.md`
passa a citar `db.get_or_404(Modelo, id)` no lugar de `Modelo.query.get_or_404`
(API legada; ainda funciona, mas o projeto adota a atual).

### Modelo (com as recomendações das decisões abaixo aplicadas)

**`usuarios`**

| Coluna | Tipo | Restrições |
|---|---|---|
| id | inteiro, autoincremento | PK |
| nome | `VARCHAR(120)` | NOT NULL |
| email | `VARCHAR(254)` | NOT NULL, UNIQUE |
| senha_hash | `VARCHAR(255)` | NOT NULL |
| criado_em | `TIMESTAMPTZ` | NOT NULL, padrão `now()` |

**`simulacoes`**

| Coluna | Tipo | Restrições |
|---|---|---|
| id | inteiro, autoincremento | PK |
| usuario_id | inteiro | NOT NULL, FK → `usuarios.id` `ON DELETE RESTRICT`, índice |
| nome | `VARCHAR(120)` | NOT NULL |
| valor_veiculo | `NUMERIC(14,2)` | NOT NULL, CHECK > 0 |
| valor_entrada | `NUMERIC(14,2)` | NOT NULL, padrão 0, CHECK ≥ 0 e ≤ `valor_veiculo` |
| taxa_ipca_projetada | `NUMERIC(12,6)` | NOT NULL (% a.a.) |
| taxa_fundo_rendimento | `NUMERIC(12,6)` | NOT NULL, CHECK ≥ 0 (% a.a.) |
| prazo_meses_fundo | inteiro | NOT NULL, CHECK > 0 |
| criado_em | `TIMESTAMPTZ` | NOT NULL, padrão `now()` |

**`opcoes_financiamento`**

| Coluna | Tipo | Restrições |
|---|---|---|
| id | inteiro, autoincremento | PK |
| simulacao_id | inteiro | NOT NULL, FK → `simulacoes.id` `ON DELETE RESTRICT`, índice |
| nome | `VARCHAR(120)` | NOT NULL |
| taxa_juros_mensal | `NUMERIC(12,6)` | NOT NULL, CHECK ≥ 0 (% a.m.) |
| prazo_meses | inteiro | NOT NULL, CHECK > 0 |
| sistema_amortizacao | `VARCHAR` + CHECK (`PRICE`/`SAC`) | NOT NULL |
| valor_entrada | `NUMERIC(14,2)` | NOT NULL, padrão 0, CHECK ≥ 0 |

**`indices_economicos_cache`**

| Coluna | Tipo | Restrições |
|---|---|---|
| id | inteiro, autoincremento | PK |
| indice | `VARCHAR` + CHECK (`SELIC`/`CDI`/`IPCA`) | NOT NULL |
| data_referencia | `DATE` | NOT NULL |
| valor | `NUMERIC(12,6)` | NOT NULL |
| atualizado_em | `TIMESTAMPTZ` | NOT NULL, padrão `now()` |
| | | UNIQUE (`indice`, `data_referencia`) |

A restrição única do cache é um acréscimo à proposta: sem ela, atualizar os
índices na Etapa 8 poderia duplicar linhas da mesma data.

**Relacionamentos (ORM):** `Usuario.simulacoes` ⇄ `Simulacao.usuario` e
`Simulacao.opcoes_financiamento` ⇄ `OpcaoFinanciamento.simulacao`, com
`back_populates` e cascata **no ORM** `all, delete-orphan` (sem
`passive_deletes`): ao excluir uma simulação ou um usuário pela sessão do
SQLAlchemy (`db.session.delete(...)`), o ORM apaga antes os filhos. O banco,
por sua vez, usa `ON DELETE RESTRICT` (decisão 9): uma exclusão direta do pai
com filhos, fora do ORM, é recusada. Opções ordenadas por `id`.

### Fluxo principal
1. Criar os models e importá-los em `app/models/__init__.py` e em
   `create_app()`.
2. `flask db migrate -m "modelagem inicial"` gera a revisão em
   `migrations/versions/`.
3. Revisar o arquivo gerado (colunas, tipos, CHECKs, FKs, nomes de
   restrições, `downgrade`) antes de aplicar.
4. `flask db upgrade` cria as tabelas; `flask db downgrade base` remove tudo;
   `flask db upgrade` de novo recria (prova de reversibilidade).
5. Script descartável (fora do projeto) exercita os models e as restrições.

### Casos de borda
- **Autogenerate depende dos imports:** se `create_app()` não importar
  `app.models`, o `flask db migrate` gera uma migration vazia (ou tenta apagar
  tabelas). Conferir que a revisão gerada tem as 4 tabelas.
- **`versions/` deixa de estar vazia:** a partir daqui o Git passa a rastrear a
  pasta com a primeira migration.
- **Enum como `VARCHAR` + CHECK** (decisão 4): não cria tipos no PostgreSQL,
  então o `downgrade` não deixa restos e acrescentar um valor depois é só
  trocar a CHECK.
- **`DateTime(timezone=True)`** devolve objetos com fuso; comparar sempre com
  datas com fuso.
- **`Decimal` no JSON:** o Flask serializa `Decimal` como texto; a forma final
  (número ou texto) é definida com os schemas, na Etapa 4.
- **Violações de restrição** (e-mail repetido, CHECK, FK) chegam como
  `IntegrityError`; o tratamento (ex.: 409) é da etapa que expõe a rota.
- **E-mail e maiúsculas:** o banco só garante unicidade exata; normalizar para
  minúsculas é responsabilidade da Etapa 3 (decisão 10).
- **Constraints sem nome** no PostgreSQL recebem nomes automáticos e ficam
  difíceis de alterar depois — daí a decisão 3.
- **Banco fora do ar** ao rodar `flask db ...`: o comando falha com erro de
  conexão; subir o container antes (`docker start rota-financeira-db`).
- **Versão do SQLAlchemy:** a verificação exploratória foi feita em SQLite; o
  comportamento com PostgreSQL só é confirmado na implementação. Se aparecer
  incompatibilidade real com SQLAlchemy 2.1.1, parar e perguntar antes de
  fixar versão.

## Decisões tomadas
1. ~~**Tipo da chave primária**~~ — **RESOLVIDA (2026-09-25): (a)** inteiro
   autoincremento (`IDENTITY`) em todas as tabelas; rotas com `<int:id>`. O
   isolamento por usuário (404 para recurso alheio) evita enumeração.
2. ~~**Estilo dos models**~~ — **RESOLVIDA (2026-09-25): (a)** SQLAlchemy
   2.0 tipado (`DeclarativeBase` + `Mapped[...]` + `mapped_column`), com
   `db = SQLAlchemy(model_class=Base)` em `extensions.py`. Nulabilidade
   expressa no tipo (`Mapped[str]` = `NOT NULL`, `Mapped[str | None]` = `NULL`).
3. ~~**Convenção de nomes das restrições**~~ — **RESOLVIDA (2026-09-25):
   (a)** definida no metadata da `Base`: `pk_<tabela>`,
   `fk_<tabela>_<coluna>_<tabela_referida>`, `uq_<tabela>_<coluna>`,
   `ck_<tabela>_<nome>` e `ix_<tabela>_<coluna>`.
4. ~~**`sistema_amortizacao` e `indice`**~~ — **RESOLVIDA (2026-09-25):
   (a)** `VARCHAR` + CHECK (`Enum(native_enum=False)`), com uma classe
   `enum.Enum` no Python por campo. Sem tipos `ENUM` nativos no PostgreSQL.
5. ~~**`parcelas_calculadas`**~~ — **RESOLVIDA (2026-09-25): (a)** não
   criar a tabela; a amortização é calculada sob demanda pelos serviços
   (Etapa 7). Se um dia for necessário, entra numa nova migration. O
   `plano.md` registra a mudança em relação à proposta.
6. ~~**Precisão e unidade dos números**~~ — **RESOLVIDA (2026-09-25):**
   dinheiro em `NUMERIC(14,2)`; taxas e valores de índices em
   `NUMERIC(12,6)`; unidade **(a) percentual** (`12.5` = 12,5%), como na
   proposta e no BACEN. Os serviços de cálculo dividem por 100 num único
   ponto, documentado.
7. ~~**Carimbos de data**~~ — **RESOLVIDA (2026-09-25):** `criado_em` como
   `TIMESTAMPTZ` com padrão `now()` no banco (não `datetime.utcnow()`). **Sem**
   `atualizado_em` em `simulacoes`, fiel à proposta e ao contrato com o
   frontend.
8. ~~**CHECKs no banco**~~ — **RESOLVIDA (2026-09-25): (a)** incluir as
   CHECKs da tabela do modelo: positividade de valores e prazos, entrada ≤
   valor do veículo (em `simulacoes`), taxas ≥ 0 exceto o IPCA (que pode ser
   negativo) e os valores permitidos dos enums. A regra "entrada da opção ≤
   valor do veículo" (entre tabelas) fica para a API (Etapa 5).
9. ~~**Exclusão de registros pai**~~ — **RESOLVIDA (2026-09-25): (b)**
   `ON DELETE RESTRICT` nas duas chaves estrangeiras (`simulacoes.usuario_id`
   e `opcoes_financiamento.simulacao_id`): o banco recusa apagar um pai que
   ainda tenha filhos. Para o CRUD continuar funcionando, o ORM mantém a
   cascata `all, delete-orphan`: `DELETE /api/simulacoes/:id` (Etapa 4)
   remove a simulação **e** suas opções pela sessão do SQLAlchemy, na mesma
   transação. Suposição a confirmar: excluir uma simulação com opções apaga
   tudo (não responde 409).
10. ~~**E-mail sem distinção de maiúsculas**~~ — **RESOLVIDA (2026-09-25):
    (a)** normalizar (minúsculas e sem espaços nas pontas) na aplicação, no
    registro e no login (Etapa 3), com `UNIQUE` simples em `email` no banco.
    A Etapa 3 deve registrar essa obrigação.
11. ~~**Nulabilidade**~~ — **RESOLVIDA (2026-09-25): (a)** todas as colunas
    `NOT NULL` (`valor_entrada` com padrão 0). A simulação guarda as taxas
    usadas, então o resultado não muda com o tempo; se o cliente quiser a taxa
    sugerida do BACEN, a API a busca no cache (Etapa 8) e a grava ao criar a
    simulação.
12. ~~**Aporte mensal do fundo**~~ — **RESOLVIDA (2026-09-25): (a)** manter
    a modelagem da proposta (sem coluna de aporte). O modo "dado o aporte"
    será tratado como parâmetro da consulta de resultado, decidido nas
    Etapas 6 e 7; se virar coluna, é uma migration pequena.

## Critérios de aceite
- [x] `flask db migrate` gerou **uma** revisão com as 4 tabelas
      (`usuarios`, `simulacoes`, `opcoes_financiamento`,
      `indices_economicos_cache`), revisada e coerente com a tabela da
      proposta (tipos, tamanhos, `NOT NULL`, padrões, CHECKs, FKs com
      `ON DELETE RESTRICT`, restrição única do cache, nomes das restrições).
- [x] `flask db upgrade` cria as tabelas; `\d+ <tabela>` no `psql` confere as
      colunas e restrições; `flask db current` mostra a revisão aplicada.
- [x] `flask db downgrade base` remove todas as tabelas (fica só
      `alembic_version`) e um novo `flask db upgrade` as recria, sem erro.
- [x] `flask db migrate` logo após o upgrade não detecta mudanças
      ("No changes in schema detected") — os models e o banco estão em
      sincronia.
- [x] Script descartável confirma: inserir usuário → simulação → duas opções
      funciona; e-mail repetido, `sistema_amortizacao` inválido, `valor_entrada
      > valor_veiculo`, prazo ≤ 0 e `indice` inválido são **rejeitados pelo
      banco**; um `DELETE` direto (SQL) de simulação com opções, ou de usuário
      com simulações, é **recusado** pelo banco (`RESTRICT`), enquanto
      `db.session.delete(simulacao)` e `db.session.delete(usuario)` removem os
      filhos antes e funcionam; `Numeric` volta como `Decimal`; `criado_em`
      volta com fuso.
- [x] `flask run` continua subindo e `GET /api/saude` responde 200.
- [x] Nenhum `DeprecationWarning` do SQLAlchemy ao importar os models e
      rodar as migrations.
- [x] Nenhuma rota, schema, serviço ou dependência nova; `requirements.txt`
      inalterado.
- [x] `CLAUDE.md` e `plano.md` atualizados (estrutura, estilo de model e
      `db.get_or_404`).

---
*Depois de aprovada, esta spec vira a base do PLANO — não escrever
código antes disso.*

## Plano de Implementação

Tarefas na ordem de execução. Nenhuma faz `git add`/`commit`/`push` (só quando
você pedir). Scripts de teste ficam no diretório temporário da sessão, nunca no
projeto. Pré-requisito de todas: `.venv` ativo, raiz do projeto como diretório
de trabalho e o banco no ar (`docker start rota-financeira-db`). Como ainda
não há suíte automatizada, a validação é por `python -c`, `flask db ...`,
`psql` dentro do container e o script descartável da Tarefa 11.

Pontos de atenção que o plano incorpora (surgiram ao planejar):
- No SQLAlchemy 2.x, `Enum(native_enum=False)` **não cria a CHECK por padrão**;
  é preciso `create_constraint=True` (e um `name`) para a decisão 4 valer. A
  revisão da migration (Tarefa 8) confere que as duas CHECKs de enum existem.
- Com a convenção de nomes (decisão 3), cada CHECK recebe o nome
  `ck_<tabela>_<nome>`; as CHECKs declaradas nos models usam só o sufixo.
- A suposição da decisão 9 (excluir simulação com opções apaga tudo, sem 409)
  está incorporada ao plano; se você não concordar, avise antes da Tarefa 3.

### Tarefa 1 — Base declarativa com convenção de nomes
- **Arquivos:** `app/extensions.py`
- **Mudança:** criar a classe `Base(DeclarativeBase)` com o `naming_convention`
  (`ix`, `uq`, `ck`, `fk`, `pk`) e trocar `db = SQLAlchemy()` por
  `SQLAlchemy(model_class=Base)`; `migrate` e `jwt` ficam iguais.
- **Validar:** `python -c "from app.extensions import db, Base; print(Base.metadata.naming_convention)"`
  mostra as 5 chaves; `python -c "from app import create_app; create_app()"`
  sem erro (a aplicação continua criando).

### Tarefa 2 — Model `Usuario`
- **Arquivos:** `app/models/usuario.py`, `app/models/__init__.py` (vazio por ora)
- **Mudança:** model `Usuario` (`usuarios`) com `id` inteiro autoincremento,
  `nome`, `email` único, `senha_hash` e `criado_em` (`TIMESTAMPTZ`, padrão
  `now()`), todos `NOT NULL`, e o relacionamento `simulacoes` (cascata do ORM
  `all, delete-orphan`, sem `passive_deletes`).
- **Validar:** compilar o `CREATE TABLE` para o dialeto PostgreSQL sem
  conexão (`CreateTable(Usuario.__table__).compile(dialect=postgresql.dialect())`)
  e conferir tipos, `NOT NULL`, `now()`, `pk_usuarios` e `uq_usuarios_email`.

### Tarefa 3 — Model `Simulacao`
- **Arquivos:** `app/models/simulacao.py`
- **Mudança:** model `Simulacao` (`simulacoes`) com as colunas e `NUMERIC`
  da spec, FK `usuario_id` → `usuarios.id` `ON DELETE RESTRICT` com índice,
  as CHECKs (`valor_veiculo > 0`, `valor_entrada >= 0`,
  `valor_entrada <= valor_veiculo`, `taxa_fundo_rendimento >= 0`,
  `prazo_meses_fundo > 0`; **sem** CHECK no IPCA), `valor_entrada` com padrão 0,
  e os relacionamentos `usuario` e `opcoes_financiamento` (ordenadas por `id`,
  cascata `all, delete-orphan`).
- **Validar:** compilar o `CREATE TABLE` (importando antes o `Usuario`) e
  conferir `fk_simulacoes_usuario_id_usuarios ... ON DELETE RESTRICT`, o índice
  `ix_simulacoes_usuario_id` e as 4 CHECKs com nomes `ck_simulacoes_*`.

### Tarefa 4 — Model `OpcaoFinanciamento` e enum `SistemaAmortizacao`
- **Arquivos:** `app/models/opcao_financiamento.py`
- **Mudança:** `enum.Enum` `SistemaAmortizacao` (`PRICE`, `SAC`) e model
  `OpcaoFinanciamento` (`opcoes_financiamento`) com FK `simulacao_id` →
  `simulacoes.id` `ON DELETE RESTRICT` com índice, `taxa_juros_mensal`,
  `prazo_meses`, `valor_entrada` (padrão 0), CHECKs (`taxa_juros_mensal >= 0`,
  `prazo_meses > 0`, `valor_entrada >= 0`) e a coluna do sistema como
  `Enum(native_enum=False, create_constraint=True, name=...)`.
- **Validar:** compilar o `CREATE TABLE` e conferir `VARCHAR`, a CHECK do enum
  (`ck_opcoes_financiamento_sistema_amortizacao` com `'PRICE'`, `'SAC'`), a FK
  com `RESTRICT` e o índice `ix_opcoes_financiamento_simulacao_id`.

### Tarefa 5 — Model `IndiceEconomicoCache` e enum `Indice`
- **Arquivos:** `app/models/indice_economico_cache.py`
- **Mudança:** `enum.Enum` `Indice` (`SELIC`, `CDI`, `IPCA`) e model
  `IndiceEconomicoCache` (`indices_economicos_cache`) com `indice` (mesmo
  padrão de enum com CHECK), `data_referencia` (`DATE`), `valor`
  (`NUMERIC(12,6)`), `atualizado_em` (`TIMESTAMPTZ`, padrão `now()`) e
  `UNIQUE (indice, data_referencia)`.
- **Validar:** compilar o `CREATE TABLE` e conferir a CHECK do enum, o
  `uq_indices_economicos_cache_indice_data_referencia` (ou o nome que a
  convenção gerar, com no máximo 63 caracteres) e `now()`.

### Tarefa 6 — Registrar os models na aplicação
- **Arquivos:** `app/models/__init__.py`, `app/__init__.py`
- **Mudança:** `app/models/__init__.py` importa e exporta as 4 classes e os 2
  enums; `create_app()` importa `app.models` para o metadata ficar populado
  antes de o Alembic rodar.
- **Validar:** `python -c "from app import create_app; from app.extensions import db; create_app(); print(sorted(db.metadata.tables))"`
  lista as 4 tabelas; `sqlalchemy.orm.configure_mappers()` roda sem erro
  (relacionamentos resolvidos); `flask routes` continua funcionando.

### Tarefa 7 — Gerar a migration
- **Arquivos:** `migrations/versions/<rev>_modelagem_inicial.py` (gerado)
- **Mudança:** `flask db migrate -m "modelagem inicial"` com o banco vazio.
- **Validar:** existe **um** único arquivo em `migrations/versions/`; o
  comando não reporta erro nem `DeprecationWarning`.

### Tarefa 8 — Revisar a migration gerada
- **Arquivos:** `migrations/versions/<rev>_modelagem_inicial.py`
- **Mudança:** ler o arquivo e corrigir o que divergir da spec (o autogenerate
  não é confiável em tudo), sem reescrever o que estiver certo.
- **Validar (checklist):** 4 `create_table` (`usuarios`, `simulacoes`,
  `opcoes_financiamento`, `indices_economicos_cache`), sem
  `parcelas_calculadas`; tipos e tamanhos da spec; `server_default` (`now()` e
  `0`); as 2 CHECKs de enum presentes; demais CHECKs com nomes `ck_*`; FKs com
  `ondelete='RESTRICT'`; índices `ix_*`; unique do cache; nomes dentro do
  padrão; `downgrade` derruba as tabelas na ordem inversa (opções → simulações
  → usuários, e o cache) e os índices, sem deixar tipos.

### Tarefa 9 — Aplicar a migration
- **Arquivos:** nenhum (altera o banco de desenvolvimento).
- **Mudança:** `flask db upgrade`.
- **Validar:** `flask db current` mostra a revisão (`head`); no `psql` do
  container, `\dt` lista as 4 tabelas + `alembic_version`, e `\d+ usuarios`,
  `\d+ simulacoes`, `\d+ opcoes_financiamento`, `\d+ indices_economicos_cache`
  batem com a tabela da spec (colunas, tipos, `NOT NULL`, defaults, CHECKs,
  FKs com `ON DELETE RESTRICT`, índices, unique).

### Tarefa 10 — Reversibilidade e sincronia
- **Arquivos:** nenhum.
- **Mudança:** nenhuma; verificação.
- **Validar:** `flask db downgrade base` → `\dt` mostra só `alembic_version`
  (sem tipos ou índices órfãos); `flask db upgrade` recria tudo sem erro;
  `flask db migrate` em seguida responde "No changes in schema detected" e não
  cria arquivo novo em `versions/` (se criar, apagar e investigar a diferença
  entre models e migration).

### Tarefa 11 — Exercitar os models e as restrições
- **Arquivos:** nenhum no projeto (script no diretório temporário).
- **Mudança:** script descartável, com `SADeprecationWarning` tratado como erro,
  que cria usuário → simulação → duas opções e confere `Decimal`, `criado_em`
  com fuso e ordenação das opções; provoca e confirma as rejeições do banco
  (e-mail repetido, `sistema_amortizacao` e `indice` inválidos, `valor_entrada >
  valor_veiculo`, prazo ≤ 0, taxa negativa em juros/fundo, IPCA negativo
  **aceito**, par `(indice, data_referencia)` repetido); prova que `DELETE`
  direto de simulação com opções e de usuário com simulações é recusado
  (`RESTRICT`), que `db.session.delete(simulacao)` e
  `db.session.delete(usuario)` removem os filhos antes, e que `db.get_or_404`
  devolve 404 para id inexistente. Ao final, o script apaga todos os dados de
  teste.
- **Validar:** todas as verificações passam e, depois do script, as 4 tabelas
  estão vazias (`SELECT count(*)`).

### Tarefa 12 — Regressão da aplicação
- **Arquivos:** nenhum.
- **Mudança:** nenhuma; verificação.
- **Validar:** `flask run` sobe; `curl /api/saude` → 200 com o banco;
  `/apidocs/` → 200; `git diff -- requirements.txt` vazio (nenhuma dependência
  nova).

### Tarefa 13 — Atualizar a documentação
- **Arquivos:** `plano.md`, `CLAUDE.md`, esta spec
- **Mudança:**
  - `plano.md`: marcar a Etapa 2 como concluída, registrando que
    `parcelas_calculadas` **não** foi criada (cálculo sob demanda) e as
    decisões-chave; acrescentar às etapas seguintes as obrigações que nasceram
    aqui — Etapa 3: normalizar e-mail (minúsculas, sem espaços) e mapear
    `IntegrityError` em 409; Etapa 5: validar `valor_entrada` da opção ≤
    `valor_veiculo`; Etapa 7: cálculo da amortização sob demanda; Etapa 8:
    preencher taxas do BACEN antes de gravar; Etapas 6 e 7: decidir o modo "dado
    o aporte".
  - `CLAUDE.md`: marcar `models/` como existente, descrever o estilo tipado, a
    convenção de nomes, a unidade percentual das taxas, `ON DELETE RESTRICT` +
    cascata do ORM, o padrão de enum com `create_constraint=True`, e trocar
    `Modelo.query.get_or_404` por `db.get_or_404(Modelo, id)` na convenção de
    erros e em "Estado atual".
  - Esta spec: marcar os critérios de aceite e o status como implementada.
- **Validar:** reler os três arquivos e conferir que não restam menções a
  `parcelas_calculadas` como tabela a criar nem a "ainda não há models".

### Tarefa 14 — Conferência final
- **Arquivos:** nenhum.
- **Mudança:** nenhuma; verificação de todos os critérios de aceite.
- **Validar:** percorrer a lista de critérios, informar o que passou, conferir
  que não há segredo nos arquivos versionáveis e mostrar o `git status --short`
  final (esperado: `app/models/`, `app/extensions.py`, `app/__init__.py`,
  `migrations/versions/<rev>_....py`, documentação). Aguardar você pedir o
  commit.
