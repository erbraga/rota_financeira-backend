# CRUD de opções de financiamento (Etapa 5) — Spec

**Criado em:** 2026-09-25
**Status:** Implementada em 2026-09-25
**Origem:** Etapa 5 de `plano.md`; seções 3.1, 6 e 7.3 de `proposta-backend-api-rest.md`

## Problema
O usuário já cria simulações (Etapa 4), mas a comparação só faz sentido com as
**2 ou 3 opções de financiamento** de cada simulação, e hoje a API não tem como
cadastrá-las. Estado verificado:

- **Código:** `app/routes/` tem `saude.py`, `auth.py` e `simulacoes.py`; não
  existem `routes/financiamentos.py`, `schemas/financiamento.py` nem
  `services/financiamentos.py`.
- **Model `OpcaoFinanciamento`** (`app/models/opcao_financiamento.py`): `id`,
  `simulacao_id` (FK `RESTRICT`), `nome` `VARCHAR(120)`, `taxa_juros_mensal`
  `NUMERIC(12,6)` (% a.m.), `prazo_meses` `INTEGER`, `sistema_amortizacao`
  (`PRICE` ou `SAC`, `VARCHAR(5)` + CHECK), `valor_entrada` `NUMERIC(14,2)`
  (padrão 0). CHECKs: `taxa_juros_mensal >= 0`, `prazo_meses > 0`,
  `valor_entrada >= 0`. **Nenhuma regra entre tabelas** (entrada da opção x valor do
  veículo) nem limite de quantidade: isso fica para a API.
- **Reutilizável das etapas anteriores:** `usuario_atual()`,
  `carregar(Schema())`, `EntradaSchema`, `campo_decimal`/`campo_inteiro`
  (`schemas/base.py`), `obter_simulacao(usuario, id)` (uma consulta por `id` **e**
  `usuario_id`; 404 uniforme), `ID_MAXIMO`, handler de 422 e a cascata do ORM
  (`db.session.delete(simulacao)` apaga as opções). As convenções de números
  (número JSON, percentual, casas rejeitadas), `PUT` total e `204` no `DELETE`
  já estão decididas e valem aqui.
- **Frontend** (`proposta-frontend-spa-react.md`): o formulário tem "opções de
  financiamento (2 ou 3): nome, taxa de juros mensal, prazo em meses, sistema
  (Price ou SAC) e entrada", com validação de "prazos inteiros"; a proposta lista
  `GET` e `POST /api/simulacoes/:id/financiamentos` e `PUT` e `DELETE
  /api/simulacoes/:id/financiamentos/:fid` (não há `GET` de uma opção só).
- **Consistência entre as etapas 4 e 5:** o `PUT /api/simulacoes/<id>` (Etapa 4)
  pode **diminuir o `valor_veiculo` abaixo da entrada de uma opção já cadastrada**,
  deixando a simulação incoerente (decisão 3).
- **Verificações exploratórias** (scripts descartáveis) com Marshmallow 4.3.1 e
  PostgreSQL:
  - `fields.Enum(SistemaAmortizacao, by_value=True)` aceita só o texto exato
    (`"SAC"`); `"sac"` é recusado, a menos que se normalize antes (decisão 6); os
    valores inválidos usam a mensagem `unknown` (redefinível), mas `null` sai em
    **inglês** ("Field may not be null.") e precisa ser redefinida;
  - `SELECT ... FOR UPDATE` compila para PostgreSQL, o que permite serializar dois
    cadastros simultâneos na mesma simulação (limite de opções, decisão 4).

## Objetivo
Permitir que o usuário autenticado cadastre, liste, edite e remova as opções de
financiamento **das próprias simulações**, com validação completa, limite de
opções por simulação, coerência com o valor do veículo e documentação OpenAPI.

## Fora de escopo
- Tabela de amortização (`.../financiamentos/<fid>/parcelas`) e cálculos de
  Price/SAC/CET (Etapas 6, 7 e 9); `resultado` (Etapa 7).
- `GET /api/simulacoes/<id>/financiamentos/<fid>` (uma opção só), salvo decisão 7.
- Mínimo de opções: a API **não** exige 2 opções (a comparação com menos opções
  continua possível; ver Etapa 7).
- Mover, duplicar ou reordenar opções; nomes únicos por simulação.
- Sugestões de taxas do BACEN para o financiamento (Etapa 8).
- Paginação/filtros (a lista tem no máximo 3 itens).
- Alteração de schema: a tabela `opcoes_financiamento` já atende (sem migration).
- Testes automatizados (`pytest` entra na Etapa 6) e o código do frontend.

## Proposta

### Endpoints (todos protegidos por JWT)

| Método e rota | Corpo | Sucesso |
|---|---|---|
| `POST /api/simulacoes/<id>/financiamentos` | dados da opção | `201` + opção + `Location` |
| `GET /api/simulacoes/<id>/financiamentos` | — | `200` com a listagem (decisão 5) |
| `PUT /api/simulacoes/<id>/financiamentos/<fid>` | dados da opção | `200` com a opção atualizada |
| `DELETE /api/simulacoes/<id>/financiamentos/<fid>` | — | `204` sem corpo |

Corpo de criação/edição (com as recomendações aplicadas); taxa em **percentual ao
mês** (`1.99` = 1,99% a.m.):
```json
{"nome": "Banco X 48x", "taxa_juros_mensal": 1.99, "prazo_meses": 48,
 "sistema_amortizacao": "PRICE", "valor_entrada": 20000.00}
```
Resposta: os mesmos campos mais `id` (sem `simulacao_id`, que já está na URL).
Números como número JSON; `sistema_amortizacao` sempre em maiúsculas.

Erros (formato `{"erro": ..., "detalhes": ...}`):

| Situação | Status |
|---|---|
| Sem token, token inválido/expirado ou de conta inexistente | 401 |
| Simulação inexistente **ou de outro usuário** | 404 `{"erro": "Simulação não encontrada"}` |
| Simulação **minha**, mas opção inexistente ou de **outra** simulação | 404 `{"erro": "Opção de financiamento não encontrada"}` |
| `<id>`/`<fid>` não numérico ou acima do `INTEGER` | 404 |
| Simulação já com 3 opções (só no `POST`) | 409 (decisão 4) |
| Dados inválidos, fora da faixa, entrada incoerente, campo desconhecido | 422 com `detalhes` por campo |
| Corpo que não é objeto JSON / não é JSON | 400 / 415 |

A verificação do dono da simulação vem **antes** de qualquer outra: o usuário nunca
descobre se um id de simulação alheia existe, nem por meio de uma opção.

### Arquivos
```
app/
  routes/financiamentos.py      # blueprint `financiamentos` (só HTTP)
  routes/__init__.py            # registra o blueprint
  schemas/financiamento.py      # FinanciamentoSchema (entrada) e saída
  services/financiamentos.py    # listar, obter, criar, atualizar, excluir (sempre pelo dono)
  services/simulacoes.py        # atualizar_simulacao passa a conferir as opções (decisão 3)
app/__init__.py                 # SWAGGER_TEMPLATE: FinanciamentoRequisicao, Financiamento, FinanciamentoLista
```
Sem migration e sem dependência nova.

### Validação de entrada

| Campo | Regra (com as recomendações aplicadas) |
|---|---|
| `nome` | obrigatório, sem espaços nas pontas, 1 a 120 caracteres |
| `taxa_juros_mensal` | obrigatória, de 0 a 20 (% a.m.), até 6 casas decimais (decisão 1) |
| `prazo_meses` | obrigatório, **inteiro** (recusa `48.0`, `"48"`, `true`), de 1 a 72 (decisão 1) |
| `sistema_amortizacao` | obrigatório, `PRICE` ou `SAC`, em qualquer caixa (decisão 6) |
| `valor_entrada` | opcional (padrão 0, decisão 8), ≥ 0, até 2 casas e **menor que o `valor_veiculo` da simulação** (decisão 2) |

- Faixas, casas decimais e recusa de `true`, `NaN`, `"1e999999"` seguem o mesmo
  mecanismo da Etapa 4 (`campo_decimal`/`campo_inteiro`).
- A regra "entrada < valor do veículo" depende da simulação, então é conferida no
  **serviço** (depois do schema), com o erro em `detalhes.valor_entrada` e a
  mensagem citando o valor do veículo.
- Campos desconhecidos (`id`, `simulacao_id`, `usuario_id`) são recusados; a opção
  **nunca** muda de simulação.
- Todas as mensagens em português, inclusive as de `null` e de sistema inválido.

### Regras de negócio e isolamento
- **Dono:** toda operação começa por `obter_simulacao(usuario, id)`; a opção é
  buscada por `id` **e** `simulacao_id` (uma consulta), de modo que a de outra
  simulação é indistinguível de uma inexistente.
- **Limite de 3 opções por simulação**, verificado no `POST`. Para dois cadastros
  simultâneos não passarem do limite, o `POST` trava a linha da simulação
  (`SELECT ... FOR UPDATE`) antes de contar. Excluir uma opção libera vaga.
- **Sem mínimo:** dá para ter 0, 1, 2 ou 3 opções; o `DELETE` da última é permitido.
- **Nome não é único** dentro da simulação.
- Editar (`PUT`) **substitui todos os campos** (`valor_entrada` omitido volta a 0)
  e reavalia a entrada contra o `valor_veiculo` **atual**.
- A listagem devolve as opções da simulação em ordem de criação (`id` crescente).
- Excluir a simulação (Etapa 4) continua apagando as opções (cascata do ORM).
- Alterar o `valor_veiculo` da simulação com opções já cadastradas segue a
  decisão 3.

### Documentação (OpenAPI 3)
Docstrings Flasgger nas 4 rotas (modelo: `app/routes/simulacoes.py`), com
`security: BearerAuth`, `requestBody`, exemplos e todas as respostas de erro
(`$ref` para `Erro`), incluindo o 409. Schemas novos em `SWAGGER_TEMPLATE`:
`FinanciamentoRequisicao`, `Financiamento` e `FinanciamentoLista`, com faixas,
unidades (percentual ao mês) e a explicação da regra da entrada.

### Fluxo principal
1. Login → **Authorize** → `POST /api/simulacoes` (Etapa 4).
2. `POST /api/simulacoes/<id>/financiamentos` duas ou três vezes → 201.
3. `GET .../financiamentos` → `{"itens": [...], "total": N}`.
4. `PUT .../financiamentos/<fid>` → 200; `DELETE` → 204; o quarto `POST` → 409.

### Casos de borda
- **Simulação de outro usuário:** `POST`, `GET`, `PUT` e `DELETE` das suas
  opções → 404 "Simulação não encontrada", sem alterar nada.
- **`fid` de outra simulação** (mesmo do próprio usuário) → 404 "Opção de
  financiamento não encontrada"; `PUT`/`DELETE` não alteram a opção alheia.
- **Quarto cadastro** → 409 e nada é gravado; depois de excluir uma opção, o
  cadastro volta a funcionar.
- **Dois `POST` simultâneos** com 2 opções já cadastradas: só um dos dois é aceito
  (o outro recebe 409), graças ao bloqueio da linha da simulação.
- **`taxa_juros_mensal = 0`:** aceita (financiamento sem juros); as fórmulas da
  Etapa 6 precisam tratar taxa zero (já previsto no plano).
- **`valor_entrada = 0` ou omitido:** financia o valor inteiro do veículo.
- **`PUT` de opção depois de a simulação mudar o `valor_veiculo`:** a entrada é
  conferida contra o valor **atual**.
- **Sistema em minúsculas ou com espaços** (`" sac "`): normalizado (decisão 6);
  valores fora de `PRICE`/`SAC`, `null`, número ou lista → 422 em português.
- **Ids muito grandes ou inválidos** (`abc`, `-1`, `99999999999`) em `<id>` ou
  `<fid>` → 404 (o teto do `INTEGER` é tratado no serviço, como na Etapa 4).
- **Banco fora do ar:** 500 genérico (débito já registrado no `CLAUDE.md`).
- **Concorrência de edição** (dois `PUT`): vale o último; sem controle de versão.

## Decisões tomadas
1. ~~**Faixas de `taxa_juros_mensal` e `prazo_meses`**~~ — **RESOLVIDA
   (2026-09-25): (a)** com valores definidos por você (rejeitados com 422 e
   mensagem que informa a faixa):

   | Campo | Faixa |
   |---|---|
   | `taxa_juros_mensal` | de 0 a 20 (% a.m.), até 6 casas decimais |
   | `prazo_meses` | inteiro de 1 a 72 (6 anos) |

   Taxa 0 é aceita (as fórmulas da Etapa 6 tratam taxa zero). Os tetos protegem a
   tabela mês a mês da Etapa 7 (no máximo 216 linhas por simulação, 3 opções × 72
   meses) e os cálculos `(1+i)^n`.
2. ~~**Entrada da opção contra o valor do veículo**~~ — **RESOLVIDA
   (2026-09-25): (a)** **estritamente menor** (`valor_entrada < valor_veiculo` da
   simulação): a opção precisa financiar algo, e a Etapa 6 não precisa tratar
   valor financiado zero. A entrada da **simulação** continua aceitando `≤`. O
   frontend reflete as duas regras nas mensagens (registrado no contrato).
3. ~~**Editar o `valor_veiculo` da simulação com opções cadastradas**~~ —
   **RESOLVIDA (2026-09-25): (a)** **recusar** o `PUT` da simulação com 422 em
   `detalhes.valor_veiculo`, citando a opção e a entrada que conflitam, quando o novo
   valor do veículo for **menor ou igual** à maior entrada das opções da simulação;
   aumentar o valor nunca dá erro. Nada é alterado no banco.
4. ~~**Limite de opções e resposta ao exceder**~~ — **RESOLVIDA
   (2026-09-25): (a)** máximo de **3** opções por simulação; o quarto cadastro
   responde **409** "Uma simulação aceita no máximo 3 opções de financiamento".
   Sem mínimo (0 a 3 opções; o `DELETE` da última é permitido). O `POST` trava a
   linha da simulação (`SELECT ... FOR UPDATE`) antes de contar, para dois
   cadastros simultâneos não passarem do limite.
5. ~~**Formato da listagem**~~ — **RESOLVIDA (2026-09-25): (a)** envelope
   `{"itens": [...], "total": N}`, igual ao de `/api/simulacoes`, em ordem de
   criação (`id` crescente).
6. ~~**Caixa do `sistema_amortizacao`**~~ — **RESOLVIDA (2026-09-25): (a)**
   aceitar em **qualquer caixa e com espaços** nas pontas (`"sac"`, `" Price "`),
   sempre devolvendo `PRICE`/`SAC` em maiúsculas; valores inválidos (`"SACRE"`, `""`,
   número, lista, `null`) → 422 em português ("Sistema de amortização inválido. Use
   PRICE ou SAC.").
7. ~~**Rota `GET /api/simulacoes/<id>/financiamentos/<fid>`**~~ — **RESOLVIDA
   (2026-09-25): (a)** **não incluir**: a tela de edição usa a lista (no máximo 3
   itens); dá para acrescentar depois sem quebrar nada.
8. ~~**`valor_entrada` omitido no cadastro da opção**~~ — **RESOLVIDA
   (2026-09-25): (a)** grava **0** (financia o valor inteiro do veículo), igual ao
   padrão do banco e da simulação; no `PUT`, omitir também volta a 0.

## Critérios de aceite
- [x] `POST .../financiamentos` válido → 201, corpo com `id`, sem `simulacao_id`,
      cabeçalho `Location: /api/simulacoes/<id>/financiamentos/<fid>`; a linha no
      banco fica na simulação da URL.
- [x] `GET .../financiamentos` → `{"itens": [...], "total": N}` em ordem de criação;
      lista vazia para simulação sem opções.
- [x] `PUT` → 200 com os novos valores (`valor_entrada` omitido volta a 0; `id` e
      `simulacao_id` intactos); `DELETE` → 204 sem corpo e o `PUT`/`DELETE`
      seguintes → 404 "Opção de financiamento não encontrada"; excluir a última
      opção é permitido.
- [x] **Isolamento:** outro usuário recebe 404 "Simulação não encontrada" nas 4 rotas
      (idêntico ao de simulação inexistente) sem alterar dados; `fid` de outra
      simulação do próprio usuário → 404 "Opção de financiamento não encontrada", e
      `PUT`/`DELETE` não alteram a opção alheia.
- [x] **Limite:** com 3 opções, o quarto `POST` → 409 sem gravar; excluindo uma, o
      `POST` volta a funcionar; **dois `POST` simultâneos** com 2 opções resultam em
      exatamente 3 (um 201 e um 409).
- [x] **Entrada:** `valor_entrada` igual ou maior que o `valor_veiculo` da simulação
      → 422 em `detalhes.valor_entrada`; menor é aceito; o `PUT` da opção usa o
      valor atual do veículo.
- [x] **Consistência (decisão 3):** `PUT /api/simulacoes/<id>` que deixe o
      `valor_veiculo` menor ou igual à entrada de alguma opção → 422 em
      `detalhes.valor_veiculo` sem alterar nada; com valor maior → 200.
- [x] Sem token / token inválido / expirado → 401 `{"erro": ...}` nas 4 rotas.
- [x] Validação: nome vazio/de 121 caracteres, taxa negativa/acima do teto/com 7
      casas, prazo 0/73/`48.0`/`"48"`/`true`, sistema `"XYZ"`/`null`/número/lista,
      campos ausentes, `NaN`, `"1e999999"`, casas em excesso e campos desconhecidos
      (`id`, `simulacao_id`, `usuario_id`) → 422 com `detalhes` por campo em
      português, sem erro 500 e sem gravar nada; JSON quebrado/array → 400; sem
      `Content-Type` JSON → 415.
- [x] `"sac"`, `" Price "` → aceitos e devolvidos como `SAC`/`PRICE`; taxa `0` e
      entrada `0` aceitas; números como número JSON (`1.99`, `20000.0`).
- [x] Ids `abc`, `-1`, `99999999999` em `<id>` e em `<fid>` → 404 (nunca 500 nem
      405).
- [x] Excluir a simulação apaga as opções (cascata); o banco termina sem linhas de
      teste.
- [x] Swagger UI: as 4 rotas aparecem (grupo "Financiamentos") com exemplos e
      respostas, inclusive 409; **Authorize** com só o token e o CRUD completo
      funcionando (verificação manual, no navegador).
- [x] `flask db migrate` sem mudanças; `requirements.txt` inalterado; sem segredo em
      arquivo versionável; `plano.md` e `CLAUDE.md` atualizados (rotas, limite e
      409, regra da entrada, consistência com o `PUT` da simulação).

---
*Depois de aprovada, esta spec vira a base do PLANO — não escrever
código antes disso.*

## Plano de Implementação

Tarefas na ordem de execução. Nenhuma faz `git add`/`commit`/`push` (só quando
você pedir). Scripts de teste e servidores auxiliares ficam no diretório
temporário da sessão, nunca no projeto. Pré-requisitos de todas: `.venv` ativo,
raiz do projeto como diretório de trabalho e o banco no ar
(`docker start rota-financeira-db`). Como ainda não há suíte automatizada, a
validação é por `python -c`, scripts descartáveis, requisições HTTP reais contra o
servidor (script com `requests`, no lugar de dezenas de `curl`), `psql` no
container e o Swagger UI no navegador (verificação manual sua). Os scripts
descartáveis das Etapas 1 a 4 são reexecutados como **regressão** sempre que o
código da Etapa 4 for tocado.

Pontos de atenção que o plano incorpora (surgiram ao planejar):
- **Ordem de verificação nas rotas:** primeiro o **dono da simulação** (404
  uniforme), depois o corpo (400/415/422) e só então as regras de estado (409 do
  limite). Assim, com a simulação cheia e o corpo inválido, o cliente vê o 422; e
  ninguém descobre se uma simulação alheia existe.
- **Bloqueio da linha da simulação** (`SELECT ... FOR UPDATE`) em três lugares: no
  `POST` da opção (para contar sem corrida), no `PUT` da opção (para ler o
  `valor_veiculo` estável) e no `PUT` da **simulação** (para conferir as entradas
  das opções sem que uma opção nova entre no meio). O bloqueio termina no
  `commit`/`rollback` (a sessão é encerrada ao fim da requisição).
- Não existe `GET` de uma opção (decisão 7); o `Location` do `POST` aponta para o
  endereço da opção, que responde a `PUT` e `DELETE`, e é montado com o endpoint do
  `PUT`.
- `null` e valor inválido do sistema precisam de mensagem em português (a padrão do
  Marshmallow para `null` sai em inglês).
- O teto de id (`ID_MAXIMO`) vale para `<id>` **e** para `<fid>` e é tratado no
  serviço, nunca no conversor da rota (fazia `PUT`/`DELETE` responderem 405).
- Todos os usuários, simulações e opções de teste são removidos; o banco termina
  com as 4 tabelas vazias.

### Tarefa 1 — `obter_simulacao` com bloqueio opcional
- **Arquivos:** `app/services/simulacoes.py`
- **Mudança:** `obter_simulacao` ganha o parâmetro opcional `bloquear` (padrão
  falso, comportamento atual intacto) que acrescenta `FOR UPDATE` à consulta única
  por `id` e `usuario_id`.
- **Validar:** `python -c "import app.services.simulacoes"`; reexecutar os
  scripts descartáveis do serviço de simulações e o ponta a ponta da Etapa 4 →
  `TUDO OK`; um teste rápido confirma que, com `bloquear=True`, o SQL emitido
  contém `FOR UPDATE` e que simulação alheia continua dando o mesmo 404.

### Tarefa 2 — Schemas da opção de financiamento
- **Arquivos:** `app/schemas/financiamento.py`
- **Mudança:** `FinanciamentoSchema` (entrada: `nome` 1 a 120; `taxa_juros_mensal`
  de 0 a 20 com até 6 casas; `prazo_meses` inteiro de 1 a 72; `sistema_amortizacao`
  normalizado (sem espaços, maiúsculas) e validado como `PRICE`/`SAC`, com mensagens
  em português inclusive para `null`; `valor_entrada` opcional, padrão 0, de 0 até o
  teto de valor com 2 casas; campos desconhecidos recusados) e o schema de saída
  (`id`, `nome`, taxa e entrada como número JSON, `prazo_meses`,
  `sistema_amortizacao` como texto em maiúsculas; **sem** `simulacao_id`).
- **Validar:** script descartável carregando casos válidos (limites incluídos,
  `"sac"`, `" Price "`, taxa 0, entrada omitida → 0) e inválidos (cada campo um passo
  fora da faixa, `48.0`, `"48"`, `true`, sistema `"SACRE"`/`""`/`null`/número/lista,
  `NaN`, `"1e999999"`, casas em excesso, campos `id`/`simulacao_id`/`usuario_id`) →
  erro só no campo certo, em português, sem erro 500; o `dump` devolve `PRICE`/`SAC`
  e números sem ruído.

### Tarefa 3 — Serviço de financiamentos
- **Arquivos:** `app/services/financiamentos.py`
- **Mudança:** `listar_opcoes` (da simulação, `id` crescente, com o total),
  `obter_opcao` (uma consulta por `id` **e** `simulacao_id`; 404 "Opção de
  financiamento não encontrada", inclusive para ids acima de `ID_MAXIMO`),
  `criar_opcao` (conta as opções da simulação já bloqueada: com 3, levanta a exceção
  do limite → 409 "Uma simulação aceita no máximo 3 opções de financiamento"),
  `atualizar_opcao` (substituição total) e `excluir_opcao`; a regra
  "`valor_entrada` < `valor_veiculo` da simulação" é conferida em `criar_opcao` e
  `atualizar_opcao` e falha com erro de validação em `detalhes.valor_entrada`
  citando o valor do veículo.
- **Validar:** script descartável em contexto da aplicação, com dois usuários:
  criar/listar/atualizar/excluir; 4º cadastro → limite; excluir libera vaga;
  entrada igual e maior que o veículo → erro, menor → aceita; `PUT` reavalia com o
  valor atual do veículo; `fid` de outra simulação do mesmo usuário e de outro
  usuário → 404 da opção sem alterar nada; **corrida real**: duas threads, cada uma
  com sessão própria, cadastrando ao mesmo tempo numa simulação com 2 opções →
  exatamente 3 no banco (uma recebe o erro do limite). Limpar os dados de teste.

### Tarefa 4 — Coerência ao editar o valor do veículo da simulação
- **Arquivos:** `app/services/simulacoes.py`, `app/routes/simulacoes.py`
- **Mudança:** `atualizar_simulacao` passa a recusar (erro de validação em
  `detalhes.valor_veiculo`, citando o nome e a entrada da opção) um `valor_veiculo`
  **menor ou igual** à maior entrada das opções da simulação, sem alterar nada; a
  rota `PUT` da simulação obtém a simulação com `bloquear=True`.
- **Validar:** script descartável: simulação com uma opção de entrada 40.000 →
  `PUT` com veículo 30.000 e com 40.000 → 422 e banco intacto; com 40.000,01 → 200;
  sem opções → sempre 200; aumentar o valor → 200; mensagem correta; **corrida**: um
  `PUT` da simulação e um `POST` de opção simultâneos não deixam o banco incoerente;
  reexecutar a regressão da Etapa 4 (serviço e ponta a ponta) → `TUDO OK`.

### Tarefa 5 — Schemas do Swagger
- **Arquivos:** `app/__init__.py`
- **Mudança:** acrescentar a `SWAGGER_TEMPLATE` os schemas `FinanciamentoRequisicao`
  (com `sistema_amortizacao` como `enum` `PRICE`/`SAC`, faixas, unidade % a.m. e a
  regra da entrada), `Financiamento` e `FinanciamentoLista`.
- **Validar:** `/apispec.json` (pelo `test_client`) contém os 3 schemas ao lado dos
  anteriores, com o `enum` e os limites corretos, e a aplicação continua criando.

### Tarefa 6 — Rotas de financiamentos
- **Arquivos:** `app/routes/financiamentos.py`, `app/routes/__init__.py`
- **Mudança:** blueprint `financiamentos` com as 4 rotas finas — `POST` e `GET` em
  `/api/simulacoes/<id>/financiamentos`, `PUT` e `DELETE` em `.../<fid>` —, todas com
  `@jwt_required()` e `usuario_atual()`, dono da simulação verificado primeiro, `POST`
  e `PUT` com `bloquear=True`, `POST` devolvendo 201 + `Location`, lista em envelope,
  409 do limite, `DELETE` 204 sem corpo, e docstrings OpenAPI 3 completas
  (`security: BearerAuth`, `requestBody`, exemplos, todas as respostas de erro com
  `$ref` para `Erro`, incluindo o 409); registrar o blueprint.
- **Validar:** `flask routes` lista as 4 rotas com os métodos certos;
  `/apispec.json` traz os caminhos com `requestBody`, `security` e as respostas;
  `flask run` sobe; sem token as 4 rotas respondem 401 e ids como `99999999999`
  respondem 404 em **todos** os métodos.

### Tarefa 7 — Validação ponta a ponta contra o servidor
- **Arquivos:** nenhum no projeto.
- **Mudança:** nenhuma; verificação com o servidor rodando, dois usuários e tokens
  gerados por script descartável.
- **Validar:**
  - `POST` válido → 201, corpo com `id`, sem `simulacao_id`, `Location:
    /api/simulacoes/<id>/financiamentos/<fid>`; no `psql`, a linha fica na simulação
    da URL; `"sac"` e `" Price "` → `SAC`/`PRICE`; taxa 0 e entrada 0/omitida
    aceitas; números como número JSON;
  - `GET` lista (envelope, ordem de criação, `total`, vazia para simulação sem
    opções); `PUT` (novos valores, entrada omitida volta a 0, `id` intacto);
    `DELETE` → 204 sem corpo e `PUT`/`DELETE` seguintes → 404 "Opção de
    financiamento não encontrada"; excluir a última opção é permitido;
  - **isolamento:** o usuário B recebe 404 "Simulação não encontrada" idêntico ao de
    simulação inexistente nas 4 rotas, sem alterar dados; `fid` de outra simulação do
    próprio usuário → 404 "Opção de financiamento não encontrada" e `PUT`/`DELETE`
    não alteram a opção alheia;
  - **limite:** 4º `POST` → 409 sem gravar; excluir uma libera vaga; **dois `POST`
    HTTP simultâneos** com 2 opções → um 201 e um 409, exatamente 3 no banco;
  - **entrada:** igual ou maior que o veículo → 422 em `detalhes.valor_entrada`;
    menor → 201; `PUT` da opção usa o valor atual do veículo;
  - **coerência (Etapa 4 alterada):** `PUT /api/simulacoes/<id>` com veículo menor ou
    igual à entrada de uma opção → 422 em `detalhes.valor_veiculo` sem alterar nada;
    maior → 200;
  - 401 `{"erro": ...}` nas 4 rotas sem token, com token inválido e expirado;
  - 422 com `detalhes` em português, sem erro 500 e sem gravar, para: nome vazio e de
    121, taxa negativa/acima do teto/7 casas, prazo 0/73/`48.0`/`"48"`/`true`, sistema
    `"XYZ"`/`null`/número/lista, campos ausentes, `NaN`, `"1e999999"`, casas em
    excesso e campos `id`/`simulacao_id`/`usuario_id`; 400 (JSON quebrado/array) e 415;
    com a simulação cheia e o corpo inválido → 422 (não 409);
  - ids `abc`, `-1`, `99999999999` em `<id>` e em `<fid>` → 404 em todos os métodos
    (nunca 500 nem 405);
  - excluir a simulação (Etapa 4) apaga as opções; nenhum `Traceback` no log.
  Ao final, remover usuários, simulações e opções de teste.

### Tarefa 8 — Validação manual no Swagger UI (sua)
- **Arquivos:** nenhum.
- **Mudança:** nenhuma; eu subo o servidor e você confere no navegador.
- **Validar:** em `/apidocs/`: as 4 rotas aparecem (grupo "Financiamentos") com
  exemplos e respostas, inclusive 409; login, **Authorize** com só o token, criar
  uma simulação e percorrer criar 3 opções → 4ª dá 409 → listar → editar → excluir
  (204) → 404; um 422 de entrada (entrada maior que o veículo); tentar reduzir o
  `valor_veiculo` da simulação abaixo da entrada de uma opção (422 em
  `valor_veiculo`). Se a página falhar, parar e avisar antes de mudar o esquema do
  Swagger.

### Tarefa 9 — Regressão e conferência de dependências
- **Arquivos:** nenhum.
- **Mudança:** nenhuma; verificação.
- **Validar:** `flask run` sobe; `/api/saude` e `/apidocs/` → 200; login e `perfil`
  funcionam; todos os scripts descartáveis das Etapas 1 a 5 → `TUDO OK`;
  `flask db migrate` → "No changes in schema detected"; `pip check` limpo;
  `git diff -- requirements.txt` vazio; busca por senha/chave do `.env` em arquivos
  versionáveis sem resultados; sem `DeprecationWarning` ao importar a aplicação; as 4
  tabelas vazias.

### Tarefa 10 — Atualizar a documentação
- **Arquivos:** `plano.md`, `CLAUDE.md`, esta spec
- **Mudança:**
  - `plano.md`: marcar a Etapa 5 como concluída, com as decisões (faixas 0 a 20 e 1 a
    72, entrada `<`, coerência no `PUT` da simulação, limite de 3 com 409 e bloqueio,
    envelope, sistema em qualquer caixa, sem `GET` por `fid`, entrada padrão 0);
    Etapa 6: taxa 0 tratada e valor financiado sempre > 0 (entrada `<` veículo);
    Etapa 7: no máximo 216 linhas por simulação e 0 a 3 opções (com 0 opções, devolver
    só os cenários possíveis); Etapa 12 (README): incluir as rotas de financiamentos;
  - `CLAUDE.md`: rotas de financiamentos implementadas (limite, 409, `Location`,
    lista em envelope, sem `GET` por `fid`); regras entre tabelas (entrada da opção
    `<` `valor_veiculo`; `PUT` da simulação recusa valor do veículo que conflita com
    opções); padrão de bloqueio (`obter_simulacao(..., bloquear=True)`) para regras
    que contam ou comparam linhas; ordem de verificação (dono → corpo → regras de
    estado); estrutura ✔ (`routes/financiamentos.py`, `schemas/financiamento.py`,
    `services/financiamentos.py`); estado atual; contrato com o frontend (entrada da
    opção "menor que" x da simulação "menor ou igual"; 409 do limite; lista em
    envelope);
  - esta spec: marcar os critérios de aceite e o status como implementada.
- **Validar:** reler os três arquivos e conferir que não restam menções a "opções de
  financiamento ainda não" nem a "Etapa 5 pendente" como estado atual.

### Tarefa 11 — Conferência final
- **Arquivos:** nenhum.
- **Mudança:** nenhuma; verificação de todos os critérios de aceite.
- **Validar:** percorrer a lista de critérios, informar o que passou e o que
  dependeu da sua verificação manual, mostrar o `git status --short` final (esperado:
  `app/routes/financiamentos.py`, `app/schemas/financiamento.py`,
  `app/services/financiamentos.py`, alterações em `app/services/simulacoes.py`,
  `app/routes/simulacoes.py`, `app/routes/__init__.py`, `app/__init__.py`,
  documentação) e aguardar você pedir o commit.
