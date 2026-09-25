# CRUD de simulações (Etapa 4) — Spec

**Criado em:** 2026-09-25
**Status:** Implementada em 2026-09-25
**Origem:** Etapa 4 de `plano.md`; seções 3.1, 6 e 7.2 de `proposta-backend-api-rest.md`

## Problema
A API já autentica usuários (Etapa 3) e o banco já tem a tabela `simulacoes`
(Etapa 2), mas **nenhuma rota de negócio existe**: o usuário não consegue criar,
listar, abrir, editar nem excluir uma simulação. Estado verificado:

- **Código:** `app/routes/` tem só `saude.py` e `auth.py`; não existem
  `routes/simulacoes.py`, `schemas/simulacao.py` nem `services/simulacoes.py`.
- **Model `Simulacao`** (`app/models/simulacao.py`): `id`, `usuario_id`
  (FK `RESTRICT`), `nome` `VARCHAR(120)`, `valor_veiculo` `NUMERIC(14,2)`,
  `valor_entrada` `NUMERIC(14,2)` (padrão 0), `taxa_ipca_projetada` e
  `taxa_fundo_rendimento` `NUMERIC(12,6)` (% a.a.), `prazo_meses_fundo`
  `INTEGER`, `criado_em`. CHECKs: `valor_veiculo > 0`, `valor_entrada >= 0` e
  `<= valor_veiculo`, `taxa_fundo_rendimento >= 0`, `prazo_meses_fundo > 0`; **o
  IPCA não tem CHECK** (pode ser negativo). A relação `opcoes_financiamento` tem
  cascata `all, delete-orphan` no ORM (o banco usa `ON DELETE RESTRICT`).
- **Infraestrutura pronta e reutilizável:** `usuario_atual()`
  (`app/services/auth.py`), `carregar(Schema())` (`app/schemas/__init__.py`),
  `EntradaSchema` (rejeita campos desconhecidos; hoje definido em
  `app/schemas/auth.py`), `resposta_erro`, handler global de `ValidationError`
  (422) e callbacks do JWT (401).
- **Frontend** (`proposta-frontend-spa-react.md`): telas de histórico, criação e
  edição; contrato `GET|POST /api/simulacoes`, `GET|PUT|DELETE
  /api/simulacoes/:id`; validação esperada: "campos numéricos obrigatórios,
  valores positivos, **entrada menor que** o valor do veículo e prazos inteiros"
  (o banco e o plano aceitam entrada **menor ou igual**: decisão 8).
- **Verificações exploratórias** (scripts descartáveis) com Marshmallow 4.3.1 e
  Flask 3.1:
  - `fields.Decimal(places=2)` **arredonda em silêncio** (`100.005` → `100.00`),
    não rejeita: para recusar casas em excesso é preciso um validador próprio;
  - `fields.Decimal` aceita número e texto (`"12.5"`), recusa `true`, `NaN` e
    `Infinity`, mas **aceita `"1e999999"`**, então é preciso limitar a faixa;
  - `fields.Integer(strict=True)` recusa `36.0`, `"36"` e `true`;
  - `jsonify` serializa `Decimal` como **texto** (`"100000.00"`), não como número;
  - `float(Decimal("99999999999999.99"))` já perde precisão (`...98`): só é
    seguro devolver números se os valores tiverem teto (decisão 6).

## Objetivo
Permitir que o usuário autenticado crie, liste, abra, edite e exclua as
**próprias** simulações (POST, GET, PUT e DELETE — requisito R1), com validação
completa, isolamento por usuário e documentação OpenAPI.

## Fora de escopo
- Opções de financiamento (Etapa 5) e seus dados dentro da simulação.
- `GET /api/simulacoes/<id>/resultado` e os cálculos (Etapas 6 e 7).
- Paginação, ordenação por parâmetro e filtros na listagem (Etapa 9); aqui a
  listagem só traz tudo do usuário, na ordem padrão.
- Preencher taxas com as sugestões do BACEN (Etapa 8): nesta etapa o cliente
  envia as duas taxas.
- Duplicar, compartilhar, arquivar ou excluir "de forma lógica" simulações.
- Atualização parcial (`PATCH`), salvo se a decisão 2 mudar isso.
- Alteração de schema: a tabela `simulacoes` já atende (sem migration).
- Testes automatizados (`pytest` entra na Etapa 6) e o código do frontend.

## Proposta

### Endpoints (todos sob `/api/simulacoes`, protegidos por JWT)

| Método e rota | Corpo | Sucesso |
|---|---|---|
| `POST /api/simulacoes` | dados da simulação | `201` + simulação + cabeçalho `Location` |
| `GET /api/simulacoes` | — | `200` com a listagem (decisão 3) |
| `GET /api/simulacoes/<id>` | — | `200` com a simulação |
| `PUT /api/simulacoes/<id>` | dados da simulação | `200` com a simulação atualizada (decisão 2) |
| `DELETE /api/simulacoes/<id>` | — | `204` sem corpo (decisão 5) |

Corpo de criação/edição (com as recomendações aplicadas); taxas em **percentual**
(`12.5` = 12,5%), como no banco:
```json
{"nome": "Onix 2026", "valor_veiculo": 95000.00, "valor_entrada": 20000.00,
 "taxa_ipca_projetada": 4.5, "taxa_fundo_rendimento": 10.5, "prazo_meses_fundo": 36}
```
Resposta (`GET`/`POST`/`PUT`): os mesmos campos mais `id` e `criado_em`; **sem**
`usuario_id`. Números como números JSON (decisão 1).

Erros (formato `{"erro": ..., "detalhes": ...}`):

| Situação | Status |
|---|---|
| Sem token, token inválido/expirado ou de conta inexistente | 401 |
| Simulação inexistente **ou de outro usuário** (mesma resposta) | 404 `{"erro": "Simulação não encontrada"}` |
| `<id>` que não é número inteiro válido | 404 (rota inexistente) |
| Dados inválidos, campo ausente, fora da faixa, campo desconhecido | 422 com `detalhes` por campo |
| Corpo que não é objeto JSON / não é JSON | 400 / 415 |

### Arquivos
```
app/
  routes/simulacoes.py       # blueprint `simulacoes` (só HTTP)
  routes/__init__.py         # registra o blueprint
  schemas/base.py            # EntradaSchema e utilitários movidos de schemas/auth.py
  schemas/auth.py            # passa a importar de base.py
  schemas/simulacao.py       # SimulacaoSchema (entrada) e saída
  services/simulacoes.py     # listar, obter, criar, atualizar, excluir (sempre por usuário)
app/__init__.py              # SWAGGER_TEMPLATE: schemas Simulacao, SimulacaoRequisicao, SimulacaoLista
```
Sem migration e sem dependência nova. O `EntradaSchema` sai de `schemas/auth.py`
para `schemas/base.py` porque agora é usado por dois módulos (ajuste mínimo,
sem mudar comportamento; o `CLAUDE.md` passa a citar o novo caminho).

### Validação de entrada (campos do corpo)

| Campo | Regra (com as recomendações aplicadas) |
|---|---|
| `nome` | obrigatório, texto sem espaços nas pontas, 1 a 120 caracteres |
| `valor_veiculo` | obrigatório, de 0,01 a 9.999.999,00, até 2 casas decimais |
| `valor_entrada` | opcional (padrão 0), ≥ 0 e ≤ `valor_veiculo`, até 2 casas |
| `taxa_ipca_projetada` | obrigatória, de −20 a 100 (% a.a.), até 6 casas |
| `taxa_fundo_rendimento` | obrigatória, de 0 a 100 (% a.a.), até 6 casas |
| `prazo_meses_fundo` | obrigatório, **inteiro** (recusa `36.0`, `"36"`, `true`), de 1 a 60 |

- Números aceitos como número JSON **ou** texto numérico (`"12.5"`); `true`,
  `NaN`, `Infinity` e notação exponencial fora da faixa são recusados.
- A faixa é verificada **antes** de qualquer conversão pesada (evita `"1e999999"`).
- `valor_entrada ≤ valor_veiculo` é uma regra entre campos: o erro aparece em
  `detalhes.valor_entrada`.
- Campos desconhecidos são recusados, inclusive `id`, `usuario_id` e
  `criado_em` (o dono vem sempre do token).
- Mensagens em português, sem eco do valor enviado quando irrelevante.

### Regras de negócio e isolamento
- Toda consulta e alteração filtra por `usuario_id` **e** `id` na **mesma**
  consulta; recurso de outro usuário é indistinguível de recurso inexistente
  (404), como manda o `CLAUDE.md`.
- O `usuario_id` da simulação criada é sempre o do token (`usuario_atual()`).
- Editar (`PUT`) **não** altera `id`, `usuario_id` nem `criado_em`.
- Excluir apaga a simulação; suas opções de financiamento (Etapa 5) saem junto
  pela cascata do ORM, na mesma transação. Excluir de novo → 404.
- O nome **não** é único: o usuário pode ter duas simulações com o mesmo nome.
- A listagem devolve só as simulações do usuário, da mais recente para a mais
  antiga (`criado_em` decrescente, desempate por `id`).
- Números com o mesmo valor (`10`, `10.0`, `"10.000000"`) gravam igual.

### Documentação (OpenAPI 3)
Docstrings Flasgger nas 5 rotas (modelo: `app/routes/auth.py`), com
`security: BearerAuth`, `requestBody`, exemplos e todas as respostas de erro
(`$ref` para `Erro`). Schemas novos em `SWAGGER_TEMPLATE` (decisão 9 da Etapa 3):
`SimulacaoRequisicao`, `Simulacao` e `SimulacaoLista`, com as faixas, as unidades
(percentual) e o teto de casas decimais escritos junto do Marshmallow.

### Fluxo principal
1. Login (Etapa 3) → **Authorize** no Swagger com o token.
2. `POST /api/simulacoes` → 201.
3. `GET /api/simulacoes` → lista com a simulação; `GET /api/simulacoes/<id>` → 200.
4. `PUT` com novos valores → 200; `DELETE` → 204; `GET` do mesmo id → 404.

### Casos de borda
- **Outro usuário:** `GET`, `PUT` e `DELETE` de uma simulação alheia → 404, sem
  alterar nada; a listagem do outro usuário não a inclui.
- **`<id>` fora do intervalo do `INTEGER`** (ex.: `99999999999`): sem restrição
  na rota, o PostgreSQL falharia com erro de faixa e a API responderia 500;
  o **serviço** trata ids acima do `INTEGER` como 404 (`ID_MAXIMO`). Não se usa
  `int(max=...)` no conversor da rota: verificado na implementação, ele faz `PUT` e
  `DELETE` responderem **405** em vez de 404.
- **Corpo vazio, array, tipo errado por campo, campo ausente:** 400/422 como na
  tabela de erros; `valor_entrada` omitido no `POST` grava 0.
- **`valor_entrada = valor_veiculo`:** aceito (decisão 8).
- **Excesso de casas decimais** (`100.005` em dinheiro): rejeitado (decisão 7).
- **Concorrência** (dois `PUT` simultâneos): vale o último; não há controle de
  versão.
- **Token de conta excluída:** 401 (já tratado por `usuario_atual()`).
- **Decimal no JSON:** os números de saída saem como número JSON (decisão 1);
  o teto de valores garante que a conversão é exata na prática.
- **Rota `/resultado`:** continua inexistente até a Etapa 7 (404).

## Decisões tomadas
1. ~~**Formato dos números na resposta**~~ — **RESOLVIDA (2026-09-25): (a)**
   **número JSON** (`95000.0`, `10.5`) em **toda** a API, inclusive no
   `/resultado`; a exatidão vem dos tetos da decisão 6. Na entrada, aceitar número
   **e** texto numérico.
2. ~~**Semântica do `PUT`**~~ — **RESOLVIDA (2026-09-25): (a)** substituição
   **total**: mesmo corpo e mesmo schema do `POST` (todos os campos obrigatórios,
   exceto `valor_entrada`, que volta a 0 se omitido — documentado no Swagger).
   Sem `PATCH`.
3. ~~**Formato da listagem**~~ — **RESOLVIDA (2026-09-25): (a)** envelope
   `{"itens": [...], "total": N}` desde já; a paginação da Etapa 9 só
   acrescenta metadados, sem quebrar o contrato.
4. ~~**O detalhe traz as opções de financiamento?**~~ — **RESOLVIDA
   (2026-09-25): (a)** não: a simulação só tem seus próprios campos; as opções
   vêm de `GET /api/simulacoes/<id>/financiamentos` (Etapa 5). Incluí-las depois
   é uma mudança aditiva.
5. ~~**Resposta do `DELETE`**~~ — **RESOLVIDA (2026-09-25): (a)** `204` sem
   corpo; um segundo `DELETE` do mesmo id responde 404. O contrato avisa que o
   cliente não deve chamar `.json()` na resposta de sucesso.
6. ~~**Faixas de valores aceitas**~~ — **RESOLVIDA (2026-09-25): (a)** com
   valores definidos por você (rejeitados com 422 e mensagem que informa a faixa):

   | Campo | Faixa |
   |---|---|
   | `valor_veiculo` | de R$ 0,01 a R$ 9.999.999,00 |
   | `valor_entrada` | de 0 até `valor_veiculo` |
   | `taxa_ipca_projetada` | de −20 a 100 (% a.a.) |
   | `taxa_fundo_rendimento` | de 0 a 100 (% a.a.) |
   | `prazo_meses_fundo` | de 1 a 60 meses (5 anos) |

   Os tetos também protegem a série mês a mês da Etapa 7 (memória) e mantêm
   exata a saída como número JSON (decisão 1: no máximo 9 dígitos).
7. ~~**Casas decimais em excesso**~~ — **RESOLVIDA (2026-09-25): (a)**
   **rejeitar** com 422 ("Use no máximo 2 casas decimais." em dinheiro, 6 nas
   taxas), sem alterar o dado em silêncio; zeros à direita não contam
   (`10`, `10.0` e `"10.000000"` são aceitos). Validador próprio, reutilizável
   nas Etapas 5 e 6 (o `places` do Marshmallow arredonda).
8. ~~**Entrada igual ao valor do veículo**~~ — **RESOLVIDA (2026-09-25):
   (a)** aceitar `valor_entrada ≤ valor_veiculo` (coerente com a CHECK do banco).
   O frontend relaxa a mensagem de "menor que" para "menor ou igual"; isso fica
   registrado no contrato.

## Critérios de aceite
- [x] `POST /api/simulacoes` válido → 201, corpo com `id` e `criado_em`, **sem**
      `usuario_id`, cabeçalho `Location: /api/simulacoes/<id>`; a linha no banco
      pertence ao usuário do token.
- [x] `GET /api/simulacoes` → só as simulações do usuário, da mais recente para a
      mais antiga, no formato da decisão 3; lista vazia quando não há nenhuma.
- [x] `GET /api/simulacoes/<id>` → 200; `PUT` → 200 com os novos valores (e
      `id`, `usuario_id`, `criado_em` intactos); `DELETE` → 204 e o `GET`
      seguinte → 404.
- [x] **Isolamento:** com dois usuários, `GET`, `PUT` e `DELETE` da simulação de
      um feitos pelo outro → 404 idêntico ao de id inexistente, sem alterar o
      dado; a listagem de cada um só tem as próprias.
- [x] Sem token / token inválido / expirado → 401 `{"erro": ...}` em todas as 5
      rotas.
- [x] Validação: campo ausente, tipo errado (`true`, texto não numérico, lista),
      nome vazio ou de 121 caracteres, valor ≤ 0 ou acima do teto, entrada acima
      do valor do veículo, IPCA e fundo fora da faixa, prazo 0, 61, `36.0` ou
      `"36"`, `NaN`, `"1e999999"`, casas decimais em excesso e campo desconhecido
      (`id`, `usuario_id`, `criado_em`) → 422 com `detalhes` por campo, sem
      erro 500; corpo quebrado/array → 400; sem `Content-Type` JSON → 415.
- [x] `valor_entrada` omitido no `POST` grava 0; entrada igual ao valor do
      veículo é aceita (decisão 8); IPCA negativo dentro da faixa é aceito.
- [x] `<id>` inexistente, `abc` e `99999999999` → 404 (nunca 500).
- [x] Números com casas (`10.5`, `4.5`) voltam iguais ao enviado (sem ruído de
      ponto flutuante), como números JSON.
- [x] Excluir uma simulação que já tenha opções (inseridas por script) apaga as
      opções também; o banco termina sem linhas de teste.
- [x] Swagger UI: as 5 rotas aparecem com exemplos e respostas; **Authorize** com
      só o token e o CRUD completo funcionando (verificação manual, no navegador).
- [x] `flask db migrate` sem mudanças; `requirements.txt` inalterado; sem segredo
      em arquivo versionável; `plano.md` e `CLAUDE.md` atualizados (rotas,
      formato de números, envelope da lista, faixas, `schemas/base.py`).

---
*Depois de aprovada, esta spec vira a base do PLANO — não escrever
código antes disso.*

## Plano de Implementação

Tarefas na ordem de execução. Nenhuma faz `git add`/`commit`/`push` (só quando
você pedir). Scripts de teste e servidores auxiliares ficam no diretório
temporário da sessão, nunca no projeto. Pré-requisitos de todas: `.venv` ativo,
raiz do projeto como diretório de trabalho e o banco no ar
(`docker start rota-financeira-db`). Como ainda não há suíte automatizada, a
validação é por `python -c`, scripts descartáveis, `curl`, `psql` no container e
o Swagger UI no navegador (verificação manual sua). Os scripts descartáveis das
Etapas 1 a 3 (schemas, erros do JWT, serviço de autenticação) são reexecutados
como **regressão** depois da refatoração da Tarefa 1.

Pontos de atenção que o plano incorpora (surgiram ao planejar):
- Os validadores do Marshmallow rodam **todos** (não param no primeiro erro).
  Um validador de casas decimais que fizesse `quantize` num valor fora da faixa
  (`"1e999999"`) levantaria `InvalidOperation` (erro 500). Por isso há **um único
  validador por campo numérico**: confere a faixa primeiro e só então as casas.
- A regra "entrada ≤ valor do veículo" só roda quando os dois campos são
  válidos (`@validates_schema` com `skip_on_field_errors`), e o erro aparece em
  `detalhes.valor_entrada`.
- A rota da coleção precisa responder em `/api/simulacoes` **sem** barra final e
  sem redirecionar; o teto do id (`2147483647`) é verificado no serviço, não no conversor `int` (ver Casos de borda).
- `criado_em` vem do banco (`now()`): depois do `commit` o atributo é relido,
  então a resposta do `POST` traz o valor gravado.
- Todos os usuários e simulações de teste são removidos; o banco termina com as
  4 tabelas vazias.

### Tarefa 1 — Mover a base dos schemas e reexecutar a regressão
- **Arquivos:** `app/schemas/base.py` (novo), `app/schemas/auth.py`
- **Mudança:** mover `EntradaSchema`, a normalização de texto e as mensagens
  padrão para `schemas/base.py` (nomes públicos) e fazer `schemas/auth.py`
  importar de lá, sem mudar nenhum comportamento.
- **Validar:** `python -c "import app.schemas.auth, app.schemas.base"`; reexecutar
  os 3 scripts descartáveis das Etapas 1 a 3 (schemas, erros do JWT e serviço de
  autenticação) → todos `TUDO OK`; `flask routes` inalterado.

### Tarefa 2 — Campos numéricos limitados (faixa + casas decimais)
- **Arquivos:** `app/schemas/base.py`
- **Mudança:** fábrica de campo `Decimal` com faixa e número máximo de casas: um
  único validador (faixa primeiro, casas depois, sem erro para zeros à direita),
  mensagens em português com a faixa formatada à brasileira, aceita número JSON e
  texto numérico e recusa `true`, `NaN`, `Infinity`; e uma fábrica análoga para
  inteiro estrito com faixa.
- **Validar:** script descartável com uma matriz de entradas: `10`, `10.0`,
  `"10.000000"`, `"12.5"` aceitos; `100.005`, `"100.005"` (2 casas) e `0.0000001`
  (6 casas) recusados; `true`, `"abc"`, `[]`, `null`, `NaN`, `Infinity` recusados;
  `"1e999999"` recusado **sem erro 500**; limites exatos (mínimo, máximo) aceitos
  e um passo além recusado; inteiro: `36` aceito, `36.0`, `"36"`, `true`, `0` e
  `61` recusados; mensagens sem texto em inglês.

### Tarefa 3 — Schemas da simulação (entrada e saída)
- **Arquivos:** `app/schemas/simulacao.py`
- **Mudança:** `SimulacaoSchema` (entrada) com `nome` 1 a 120 sem espaços nas
  pontas, `valor_veiculo` (0,01 a 9.999.999,00; 2 casas), `valor_entrada` (opcional,
  padrão 0; 0 a `valor_veiculo`; 2 casas), `taxa_ipca_projetada` (−20 a 100; 6
  casas), `taxa_fundo_rendimento` (0 a 100; 6 casas) e `prazo_meses_fundo`
  (inteiro, 1 a 60), rejeitando campos desconhecidos (`id`, `usuario_id`,
  `criado_em`); e o schema de saída (`id`, todos os campos, `criado_em`; **sem**
  `usuario_id`) com números como número JSON.
- **Validar:** script descartável carregando casos válidos (limites incluídos,
  `valor_entrada` igual ao veículo, IPCA negativo) e inválidos (campo ausente,
  nome de 121 caracteres, entrada acima do veículo com o erro em
  `detalhes.valor_entrada`, cada campo um passo fora da faixa, campos
  desconhecidos); o `dump` de um objeto parecido com o model devolve `float` sem
  ruído (`10.5`, `95000.0`) e sem `usuario_id`.

### Tarefa 4 — Serviço de simulações
- **Arquivos:** `app/services/simulacoes.py`
- **Mudança:** `listar_simulacoes` (só do usuário, `criado_em` e `id`
  decrescentes, com o total), `obter_simulacao` (uma única consulta por `id` **e**
  `usuario_id`; 404 "Simulação não encontrada" para inexistente ou alheia),
  `criar_simulacao`, `atualizar_simulacao` (substituição total; `valor_entrada`
  ausente volta a 0; nunca toca em `id`, `usuario_id`, `criado_em`) e
  `excluir_simulacao` (pela sessão do ORM, com a cascata das opções).
- **Validar:** script descartável em contexto da aplicação, com dois usuários:
  criar, listar (ordem e total, lista vazia), obter, atualizar, excluir; o outro
  usuário recebe 404 ao obter/atualizar/excluir a simulação alheia e nada muda no
  banco; excluir uma simulação com 2 opções inseridas por script apaga as opções
  (banco sem linhas órfãs). Limpar os dados de teste.

### Tarefa 5 — Schemas do Swagger
- **Arquivos:** `app/__init__.py`
- **Mudança:** acrescentar a `SWAGGER_TEMPLATE` os schemas `SimulacaoRequisicao`,
  `Simulacao` e `SimulacaoLista`, com faixas, unidades (percentual), tetos de casas
  decimais e exemplos escritos junto das regras do Marshmallow.
- **Validar:** `/apispec.json` (pelo `test_client`) contém os 3 schemas ao lado dos
  anteriores e a aplicação continua criando.

### Tarefa 6 — Rotas de simulações
- **Arquivos:** `app/routes/simulacoes.py`, `app/routes/__init__.py`
- **Mudança:** blueprint `simulacoes` (`/api/simulacoes`) com as 5 rotas finas —
  todas com `@jwt_required()` e `usuario_atual()`; `POST` devolve 201 com o corpo e
  `Location`; `GET` da coleção devolve `{"itens": [...], "total": N}`; `PUT`
  substitui tudo; `DELETE` devolve 204 sem corpo — e docstrings OpenAPI 3
  completas (`security: BearerAuth`, `requestBody`, exemplos, respostas de erro
  com `$ref` para `Erro`; teto do id no serviço); registrar o
  blueprint.
- **Validar:** `flask routes` lista as 5 rotas com os métodos certos;
  `/apispec.json` traz os caminhos com `requestBody`, `security` e as respostas;
  `flask run` sobe; `curl -i /api/simulacoes` (sem barra) responde direto
  (401 sem token, sem redirecionar).

### Tarefa 7 — Validação ponta a ponta com `curl`
- **Arquivos:** nenhum no projeto.
- **Mudança:** nenhuma; verificação com o servidor rodando, dois usuários e tokens
  gerados por script descartável.
- **Validar:**
  - `POST` válido → 201, corpo com `id` e `criado_em`, sem `usuario_id`,
    `Location: /api/simulacoes/<id>`; no `psql`, a linha pertence ao usuário do
    token; `valor_entrada` omitido grava 0; entrada igual ao veículo e IPCA
    negativo aceitos; `10.5` e `4.5` voltam iguais, como números JSON;
  - `GET` lista (ordem da mais recente para a mais antiga, `total`, vazia para
    quem não tem nada), `GET` por id, `PUT` (novos valores; `id`, `usuario_id` e
    `criado_em` intactos; `valor_entrada` omitido volta a 0), `DELETE` → 204 sem
    corpo e o `GET`/`DELETE` seguintes → 404;
  - **isolamento:** o usuário B recebe 404 idêntico ao de id inexistente em `GET`,
    `PUT` e `DELETE` da simulação de A, sem alterar dados, e sua lista não a inclui;
  - 401 `{"erro": ...}` nas 5 rotas sem token, com token inválido e com token
    expirado;
  - 422 com `detalhes` por campo, sem erro 500, para: campo ausente, tipos errados
    (`true`, texto, lista), nome vazio e de 121 caracteres, valor ≤ 0 e acima do
    teto, entrada acima do veículo, IPCA e fundo fora da faixa, prazo 0, 61, `36.0`
    e `"36"`, `NaN`, `"1e999999"`, casas em excesso e campos desconhecidos (`id`,
    `usuario_id`, `criado_em`); 400 para JSON quebrado e array; 415 sem
    `Content-Type` JSON;
  - ids `abc`, `99999999999` e `-1` → 404 (nunca 500);
  - excluir pela API uma simulação com opções inseridas por script apaga as
    opções também; nenhum `Traceback` no log do servidor.
  Ao final, remover usuários e simulações de teste.

### Tarefa 8 — Validação manual no Swagger UI (sua)
- **Arquivos:** nenhum.
- **Mudança:** nenhuma; eu subo o servidor e você confere no navegador.
- **Validar:** em `/apidocs/`: as 5 rotas aparecem (grupo "Simulações") com
  exemplos e respostas; registrar e fazer login, **Authorize** com só o token, e
  percorrer criar → listar → abrir → editar → excluir (204) → abrir de novo (404);
  um erro de validação (ex.: prazo 61) mostrando o 422 com `detalhes`. Se a página
  falhar, parar e avisar antes de mudar o esquema do Swagger.

### Tarefa 9 — Regressão e conferência de dependências
- **Arquivos:** nenhum.
- **Mudança:** nenhuma; verificação.
- **Validar:** `flask run` sobe; `/api/saude` e `/apidocs/` → 200; login e `perfil`
  continuam funcionando; `flask db migrate` → "No changes in schema detected";
  `pip check` limpo; `git diff -- requirements.txt` vazio; busca por senha/chave do
  `.env` em arquivos versionáveis sem resultados; sem `DeprecationWarning` ao
  importar a aplicação; as 4 tabelas vazias (`SELECT count(*)`).

### Tarefa 10 — Atualizar a documentação
- **Arquivos:** `plano.md`, `CLAUDE.md`, esta spec
- **Mudança:**
  - `plano.md`: marcar a Etapa 4 como concluída, com as decisões (números JSON,
    `PUT` total, envelope da lista, `204`, faixas, rejeição de casas em excesso,
    `≤`); na Etapa 5, reaproveitar os campos limitados e `obter_simulacao` para
    conferir o dono; na Etapa 7, saída numérica como número JSON; na Etapa 9,
    manter o envelope e só acrescentar metadados;
  - `CLAUDE.md`: rotas de simulações implementadas; formato numérico (número JSON,
    percentual, faixas e tetos como protetores da série mês a mês); `schemas/base.py`
    no lugar de `schemas/auth.py` para `EntradaSchema`; padrão de isolamento
    (uma consulta por `id` e `usuario_id`, 404 uniforme); regras de `PUT` total,
    envelope da lista e `204`; estrutura ✔ e "Estado atual"; e, em contrato com o
    frontend, o `204` sem `.json()` e a mensagem "entrada menor ou igual";
  - esta spec: marcar os critérios de aceite e o status como implementada.
- **Validar:** reler os três arquivos e conferir que não restam menções a
  `EntradaSchema` em `schemas/auth.py` nem a "ainda não há rotas de negócio".

### Tarefa 11 — Conferência final
- **Arquivos:** nenhum.
- **Mudança:** nenhuma; verificação de todos os critérios de aceite.
- **Validar:** percorrer a lista de critérios, informar o que passou e o que
  dependeu da sua verificação manual, mostrar o `git status --short` final
  (esperado: `app/routes/simulacoes.py`, `app/schemas/{base,simulacao}.py`,
  `app/services/simulacoes.py`, alterações em `app/__init__.py`,
  `app/routes/__init__.py`, `app/schemas/auth.py`, documentação) e aguardar você
  pedir o commit.
