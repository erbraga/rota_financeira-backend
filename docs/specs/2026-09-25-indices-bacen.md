# Integração com o BACEN/SGS, cache e índices (Etapa 8) — Spec

**Criado em:** 2026-09-25
**Status:** Implementada (2026-09-25) — critérios de aceite conferidos (pytest 617, ponta a ponta com servidor falso, API real do BACEN e Swagger UI)
**Origem:** Etapa 8 de `plano.md`; seções 5 e 7.4 de `proposta-backend-api-rest.md`; requisitos R7 e R8

## Problema
As taxas do formulário (rendimento do fundo, IPCA) hoje são digitadas à mão, e a
integração com a API pública exigida pelos requisitos **R7** (uso de API externa) e **R8**
(documentar a API externa: licença, cadastro e rotas, e consumi-la no backend) ainda não
existe. O frontend espera "taxas sugeridas (IPCA, CDI, Selic) vindas da API, que o usuário
pode sobrescrever"; por decisão do autor a **Selic fica de fora** (só CDI e IPCA).
Estado verificado:

- **Código:** não existem `app/integrations/`, `services/indices.py` nem `routes/indices.py`;
  nenhuma variável de ambiente do BACEN. O `requests` já está no `requirements.txt`
  (2.34.2).
- **Tabela pronta (Etapa 2):** `indices_economicos_cache` com `indice` (`SELIC`, `CDI` ou
  `IPCA`), `data_referencia` (`DATE`), `valor` `NUMERIC(12,6)`, `atualizado_em`
  (`TIMESTAMPTZ`, padrão `now()`) e `UNIQUE (indice, data_referencia)` (nome
  `uq_indices_economicos_cache_indice_data_referencia`). O valor é guardado "como
  publicado pelo BACEN, em percentual, sem conversão". A tabela está **vazia**.
- **Campos que a sugestão alimenta** (Etapas 4 e 5), ambos em **% a.a.**:
  `taxa_fundo_rendimento` (0 a 100) e `taxa_ipca_projetada` (−20 a 100).
- **Rotas da proposta:** `GET /api/indices/{selic|ipca|cdi}?periodo=...` (JWT, como as
  demais); esta spec implementa **só `cdi` e `ipca`** (a rota `selic` não existe e dá 404;
  o valor `SELIC` continua permitido no enum e na CHECK do banco, sem uso, para não exigir
  migration). O plano ainda prevê "gravar a taxa sugerida na simulação quando o cliente não
  enviar" (decisão 11 da Etapa 2), que esta spec reavalia (decisão 6).
- **API real verificada** (sondagem descartável em 2026-09-25, sem cadastro nem chave):
  - as séries respondem em `https://api.bcb.gov.br/dados/serie/bcdata.sgs.<n>/dados`
    (`?formato=json`, `/ultimos/<N>` ou `dataInicial`/`dataFinal` em `dd/mm/aaaa`); o
    corpo é uma lista `[{"data": "24/09/2026", "valor": "13.65"}]` com o valor **em texto**
    e ponto decimal; a resposta leva 0,08 a 0,9 s;
  - séries úteis, já em **% a.a.**: **4389** CDI anualizada base 252 (diária; último 13,65 em
    24/09/2026), **432** meta Selic definida pelo Copom (diária; 13,75) e **13522** IPCA
    acumulado em 12 meses (mensal; último 4,22 em `01/08/2026`); as séries "cruas" (11 e 12,
    taxa **diária** `0,050788` % a.d.; 433, variação mensal do IPCA) exigiriam conversão;
  - **janela máxima de 10 anos** em séries diárias: pedir mais devolve **HTTP 406** com
    corpo JSON de erro;
  - **intervalo sem dados devolve HTTP 404** (`"Value(s) not found"`), **não** lista vazia;
    data mal formatada devolve 400;
  - o **`Content-Type` vem `text/html`** mesmo com corpo JSON (não dá para confiar nele) e
    o cabeçalho sugere cache de 15 minutos (`max-age=900`);
  - a série **432 traz linhas com datas futuras** (pediu-se "últimos 8" e voltaram
    `28/10/2026` a `04/11/2026`): é preciso limitar `dataFinal` a hoje e ignorar datas
    futuras; com `dataFinal` = hoje a última linha é a vigente (13,75);
  - as séries mensais usam o **primeiro dia do mês** como data (`01/08/2026`) e têm defasagem
    de publicação (em setembro o último IPCA é o de agosto);
  - a página do conjunto no portal de dados abertos do BCB indica a licença **Open Data
    Commons Open Database License (ODbL)** (verificada para a série 11; confirmar as
    demais na implementação para o R8).

## Objetivo
Consultar as séries do BACEN/SGS no backend, guardar o resultado em
`indices_economicos_cache` e servi-lo por `GET /api/indices/{cdi|ipca}`, com uma
**taxa sugerida pronta** (em % a.a.) para o formulário, mantendo a aplicação funcionando
quando o BACEN estiver fora do ar, e documentar a API externa (R8).

## Fora de escopo
- Atualização agendada (APScheduler, dependência nova): a atualização é sob demanda.
- Projeção de inflação (expectativas do boletim Focus): é outra API do BACEN; o IPCA
  "projetado" sugerido é o realizado em 12 meses (decisão 1).
- Preencher automaticamente a taxa ao criar a simulação (decisão 6).
- Gráficos ou estatísticas sobre as séries; outros índices além dos três; conversão para
  taxa mensal (o cálculo da Etapa 6 já converte).
- Alteração de schema (a tabela e a restrição única já existem), autenticação diferente
  da dos demais recursos e testes de integração da API (Etapa 10).
- O código do frontend.

## Proposta

### Endpoint (protegido por JWT, só leitura)

| Método e rota | Resposta de sucesso |
|---|---|
| `GET /api/indices/cdi?periodo=12m` | `200` com a série e a taxa sugerida |
| `GET /api/indices/ipca?periodo=12m` | idem |

Erros (formato `{"erro": ..., "detalhes": ...}`): 401 (token); 404 "Índice não
encontrado" (qualquer `<indice>` fora de `cdi` e `ipca`, inclusive `selic`); 422 com
`detalhes.periodo` para valor inválido; **503** "Dados do Banco Central indisponíveis no
momento" quando o BACEN falha **e** não há nada em cache (decisão 5).

### Arquivos
```
app/
  integrations/__init__.py
  integrations/bacen.py      # cliente HTTP (requests) do SGS + interpretação da resposta
  services/indices.py        # cache (TTL, upsert), consulta ao BACEN e fallback
  schemas/indices.py         # saída e parâmetro `periodo`
  routes/indices.py          # blueprint `indices`
config.py                    # BACEN_URL_BASE, BACEN_TIMEOUT_SEGUNDOS, INDICES_TTL_HORAS (opcionais)
.env.example                 # documenta as três variáveis
app/__init__.py              # SWAGGER_TEMPLATE: schemas do índice + descrição da API externa (R8)
tests/integrations/test_bacen.py   # pytest: interpretação da resposta (função pura, payloads reais)
```
Sem migration e sem dependência nova (`requests` já existe).

### Séries e unidades (com a decisão 1 aplicada)

| Índice | Série SGS | Descrição | Unidade | Periodicidade |
|---|---|---|---|---|
| `CDI` | 4389 | Taxa de juros — CDI anualizada base 252 | % a.a. | diária (dias úteis) |
| `IPCA` | 13522 | IPCA acumulado em 12 meses | % a.a. | mensal (dia 1 do mês) |

O cache guarda o valor **como publicado** (percentual a.a.), o que também é a unidade dos
campos da simulação: o valor sugerido entra no formulário **sem conversão**.

### Contrato da resposta (com as decisões 2 e 4 aplicadas)
```json
{
  "indice": "CDI",
  "descricao": "Taxa CDI anualizada, base 252",
  "unidade": "% a.a.",
  "serie_sgs": 4389,
  "sugestao": {"valor": 13.65, "data_referencia": "2026-09-24"},
  "periodo": {"inicio": "2025-09-25", "fim": "2026-09-25"},
  "pontos": [{"data": "2025-09-25", "valor": 14.9}, {"data": "2026-09-24", "valor": 13.65}],
  "atualizado_em": "2026-09-25T13:00:00+00:00",
  "desatualizado": false
}
```
- `sugestao`: o **valor mais recente** com data até hoje (fuso de Brasília), o mesmo
  número que o frontend coloca no formulário; para o IPCA é o acumulado em 12 meses do
  último mês publicado.
- `pontos`: os valores do período pedido, em ordem crescente de data (números JSON),
  ao gráfico ou consulta; sem pontos futuros.
- `atualizado_em`: quando o cache deste índice foi renovado pela última vez;
  `desatualizado` é verdadeiro quando o BACEN falhou e a resposta veio de um cache mais
  velho que o TTL.

### Regras
- **Cache primeiro.** Para cada requisição: se o cache do índice é mais novo que o TTL,
  responde só com o banco (nenhuma chamada ao BACEN); senão consulta o BACEN, grava
  (`INSERT ... ON CONFLICT (indice, data_referencia) DO UPDATE`, idempotente e seguro
  com requisições simultâneas) e responde com o resultado atualizado (decisão 3).
- **Janela de atualização fixa** de 60 meses até hoje: uma única consulta por índice
  cobre qualquer `periodo` permitido, e o `periodo` só filtra o que já está no banco.
- **Interpretação da resposta do BACEN** (função pura, testada com payloads reais):
  `data` em `dd/mm/aaaa`, `valor` em texto lido como `Decimal` (nunca `float`); linhas com
  data futura são ignoradas; **resposta com linha inválida, JSON quebrado ou corpo que não
  é lista** é tratada como falha do BACEN (não se grava lixo); o `Content-Type` não é
  conferido (vem `text/html`); HTTP **404** com `"Value(s) not found"` é "sem dados", não
  erro; qualquer outro 4xx/5xx, timeout ou erro de rede é falha.
- **Falha do BACEN** (decisão 5): com cache, responde 200 com `desatualizado: true`; sem
  cache algum, 503. O motivo real (tipo de erro, código HTTP) vai para o log, nunca para o
  cliente.
- **Data de "hoje"** no fuso `America/Sao_Paulo` (as datas do SGS são de Brasília).
- **Somente leitura para o cliente:** as requisições `GET` só gravam no cache; nada do
  usuário é gravado.

### Configuração (decisão 7)
Variáveis **opcionais** (com padrão): `BACEN_URL_BASE` (padrão
`https://api.bcb.gov.br/dados/serie/bcdata.sgs`), `BACEN_TIMEOUT_SEGUNDOS` (padrão 8) e
`INDICES_TTL_HORAS` (padrão 12). Valor inválido falha na subida com mensagem clara, como
`JWT_ACCESS_TOKEN_EXPIRES_MINUTOS`. A URL base configurável permite testar falhas com um
servidor falso local, sem depender da rede.

### Documentação da API externa (R8)
No Swagger da rota (e depois no README, Etapa 12): **API** Séries Temporais (SGS) do
Banco Central do Brasil, `api.bcb.gov.br`; **licença** Open Data Commons Open Database
License (ODbL), conforme o portal de dados abertos do BCB; **cadastro** não é necessário
(sem chave nem login); **rotas usadas**:
`GET .../bcdata.sgs.4389/dados` e `.../bcdata.sgs.13522/dados`
com `formato=json`, `dataInicial` e `dataFinal`; o consumo acontece **no backend** (o
cliente nunca é redirecionado ao BACEN).

### Fluxo principal
1. Frontend abre o formulário e chama `GET /api/indices/cdi` e `GET /api/indices/ipca`.
2. Primeira chamada do dia: cache vencido → consulta o BACEN, grava, responde; as seguintes
   respondem só do banco.
3. O frontend preenche `taxa_fundo_rendimento` com a `sugestao` do CDI e
   `taxa_ipca_projetada` com a do IPCA; o usuário pode alterar; a simulação é criada com os
   valores enviados (decisão 6).

### Casos de borda
- **Cache vazio e BACEN fora do ar:** 503, sem quebrar a aplicação nem o restante da API.
- **Cache vencido e BACEN fora do ar:** 200 com os dados antigos e `desatualizado: true`.
- **Intervalo sem dados** (404 do BACEN): tratado como "sem novidades" (mantém o que há no
  cache); se o cache está vazio, 503.
- **Janela acima de 10 anos** (406): não ocorre (a janela é de 60 meses); um teste garante
  que a janela pedida nunca passa de 10 anos.
- **Linhas com data futura** (a série 432 da Selic, fora desta spec, mostrou que o SGS
  pode trazê-las): ignoradas por defesa; a `sugestao` nunca é do futuro.
- **Defasagem mensal do IPCA:** a `sugestao` é do último mês publicado (ex.: em setembro,
  o de agosto); `data_referencia` mostra a qual mês se refere.
- **Valores negativos** (IPCA em 12 meses pode ser negativo): aceitos.
- **Duas requisições simultâneas com cache vencido:** as duas consultam o BACEN e gravam
  o mesmo conteúdo; o `ON CONFLICT` evita duplicata e erro (a consulta duplicada é
  aceitável no volume do MVP).
- **Resposta do BACEN muito grande ou lenta:** timeout de 8 s (conexão e leitura) e nenhuma
  nova tentativa automática; a requisição do cliente nunca espera mais que isso.
- **Fuso e imagem Docker:** a data de hoje usa `zoneinfo` (biblioteca padrão), que exige os
  dados de fuso do sistema; a Etapa 11 confere que a imagem os inclui.
- **Banco fora do ar:** 500 genérico (débito já registrado).
- **JWT:** como as demais rotas; sem token → 401.

## Decisões tomadas
1. ~~**Quais séries do SGS e o que significa a "sugestão"**~~ — **RESOLVIDA
   (2026-09-25): (a)**, **só CDI e IPCA (sem Selic)**: **CDI = 4389** (CDI anualizada
   base 252, % a.a.) e **IPCA = 13522** (IPCA acumulado em 12 meses, % a.a.), sem
   conversão de unidade; a sugestão de IPCA é o **acumulado em 12 meses realizado** (o
   SGS não tem projeção; a projeção do boletim Focus é outra API). A rota `selic` não é
   criada (404); o valor `SELIC` do enum/CHECK do banco fica reservado, sem uso.
2. ~~**Formato da resposta**~~ — **RESOLVIDA (2026-09-25): (a)** objeto completo:
   `indice`, `descricao`, `unidade`, `serie_sgs`, `sugestao` (`valor` e
   `data_referencia`, o valor mais recente até hoje), `periodo` (`inicio` e `fim`),
   `pontos` (em ordem crescente, sem datas futuras), `atualizado_em` e `desatualizado`.
   O frontend só copia `sugestao.valor` para o formulário.
3. ~~**Política de atualização do cache**~~ — **RESOLVIDA (2026-09-25): (a)** **sob
   demanda, TTL de 12 horas e janela fixa de 60 meses** por índice: cache vencido →
   uma consulta ao BACEN dos últimos 60 meses e gravação com `INSERT ... ON CONFLICT DO
   UPDATE`; o `periodo` da requisição só filtra o que já está no banco. Sem agendador
   (nada de APScheduler).
4. ~~**Parâmetro `periodo`**~~ — **RESOLVIDA (2026-09-25): (a)** meses para trás
   até hoje, valores **`1m`, `3m`, `6m`, `12m`, `24m` e `60m`**, padrão **`12m`**; qualquer
   outro (`13m`, `abc`, `0`, `-1`, vazio, repetido) → 422 em `detalhes.periodo`, com a
   mensagem listando os valores permitidos. O parâmetro só filtra o cache (nunca dispara
   consulta extra ao BACEN); a `sugestao` não depende dele.
5. ~~**Quando o BACEN falha**~~ — **RESOLVIDA (2026-09-25): (a)** com cache
   disponível → **200** com os dados antigos e `desatualizado: true` (e o
   `atualizado_em` real); **sem cache algum → 503** "Dados do Banco Central
   indisponíveis no momento". Falha = conexão recusada, timeout (8 s), HTTP 5xx ou outro
   4xx, corpo que não é JSON ou linha inválida (nada é gravado); o HTTP 404 "Value(s)
   not found" é "sem dados novos", não falha. Motivo real só no log; sem nova tentativa
   automática.
6. ~~**Sugestão automática ao criar a simulação**~~ — **RESOLVIDA (2026-09-25):
   (a)** **manter as taxas obrigatórias** no `POST`/`PUT` da simulação: o frontend
   pré-preenche o formulário pelo `GET /api/indices` e envia valores explícitos, e a
   criação/edição de simulação **não depende** do BACEN. A decisão 11 da Etapa 2 ("a API
   grava a taxa sugerida quando omitida") é reavaliada e **descartada**; o `plano.md` e o
   `CLAUDE.md` registram isso.
7. ~~**Configuração e testes**~~ — **RESOLVIDA (2026-09-25): (a)**
   `BACEN_URL_BASE`, `BACEN_TIMEOUT_SEGUNDOS` (padrão 8) e `INDICES_TTL_HORAS` (padrão 12)
   **opcionais por ambiente** (valor inválido derruba a subida com mensagem clara;
   documentadas no `.env.example`); falhas exercitadas com um **servidor HTTP falso local**
   (biblioteca padrão) e a interpretação da resposta testada no `pytest` com **payloads
   reais gravados**. Sem dependência nova.

## Critérios de aceite
- [x] Com rede e cache vazio, `GET /api/indices/cdi` → 200, `sugestao` igual ao último
      valor da série 4389 até hoje (conferido com uma consulta direta ao BACEN),
      `desatualizado` falso, e `indices_economicos_cache` passa a ter linhas de `CDI`
      (`valor` como publicado, `data_referencia` em datas reais, nenhuma futura).
- [x] Repetida logo depois, a resposta sai **do cache** (comprovado: nenhuma chamada ao
      BACEN, medida no servidor falso) e `atualizado_em` não muda; após o TTL (com um
      TTL curto por ambiente), a consulta ao BACEN acontece de novo.
- [x] Nenhuma data futura no cache nem em `pontos` (inclusive com um servidor falso que as
      devolve); IPCA (13522): `sugestao` é o último mês publicado, com `data_referencia`
      no primeiro dia do mês; CDI (4389): `sugestao` é o último dia útil publicado.
- [x] `GET /api/indices/selic` → 404 "Índice não encontrado" (a Selic não faz parte desta
      entrega) e nada da Selic é consultado nem gravado.
- [x] `periodo`: `1m`, `3m`, `6m`, `12m`, `24m`, `60m` aceitos (os pontos respeitam o
      período e a ordem crescente); ausente = `12m`; `abc`, `13m`, `0`, `-1`, vazio e
      repetido → 422 em português em `detalhes.periodo`; índice desconhecido → 404.
- [x] **BACEN fora do ar** (servidor falso: conexão recusada, timeout, HTTP 500, HTTP 406,
      HTTP 404 "Value(s) not found", corpo HTML, JSON quebrado, linha com valor ou data
      inválidos): com cache → 200 com `desatualizado: true` e nada novo gravado; sem cache →
      503 com mensagem clara, **sem** vazar detalhes internos; a aplicação e as demais rotas
      seguem funcionando; o motivo aparece no log.
- [x] Requisições simultâneas com cache vencido não duplicam linhas nem geram erro (a
      restrição única segura a corrida).
- [x] Nenhum `float` no caminho: valores lidos como `Decimal`; a janela consultada nunca
      passa de 10 anos; o `Content-Type` da resposta do BACEN não é usado para decidir.
- [x] `tests/integrations/test_bacen.py` (pytest) cobre a interpretação da resposta com
      payloads reais gravados (lista normal, data futura, valor negativo, linha inválida,
      JSON quebrado, 404 "sem dados", corpo HTML) e a suíte inteira continua verde; o
      arquivo `bacen.py` **não** importa Flask nem o banco.
- [x] Sem token → 401 `{"erro": ...}`; `<indice>` maiúsculo (`CDI`) → 404 (só minúsculas).
- [x] Swagger UI: a rota aparece com o contrato, o `periodo`, os erros (inclusive 503) e a
      **documentação da API externa** (nome, licença ODbL, sem cadastro, rotas usadas,
      consumo no backend); **Authorize** com só o token e o `GET` funcionando (verificação
      manual, no navegador, com rede).
- [x] `flask db migrate` sem mudanças; `requirements.txt` inalterado; sem segredo em
      arquivo versionável; `plano.md` e `CLAUDE.md` atualizados (séries, política de cache,
      falhas, contrato, decisão 6 e a nota de Docker/fuso).

---
*Depois de aprovada, esta spec vira a base do PLANO — não escrever
código antes disso.*

## Plano de Implementação

Tarefas na ordem de execução. Nenhuma faz `git add`/`commit`/`push` (só quando você pedir).
Pré-requisitos: `.venv` ativo, raiz do projeto como diretório de trabalho e, da tarefa 4 em
diante, o banco no ar (`docker start rota-financeira-db`). A validação combina o `pytest`
(interpretação da resposta e cliente HTTP, sem banco), scripts descartáveis no diretório
temporário da sessão, um **servidor HTTP falso local** (biblioteca padrão) que imita o SGS e
falha sob comando, requisições reais contra o servidor da aplicação (`requests`), uma
conferência **com a rede real** do BACEN e o Swagger UI (verificação manual sua). Os testes e
scripts das etapas anteriores são reexecutados como **regressão**.

Detalhes de projeto que o plano fixa (não estavam explícitos na spec):
- **Resposta duplicada do BACEN:** o `ON CONFLICT DO UPDATE` do PostgreSQL falha se a mesma
  chave aparece duas vezes no mesmo `INSERT`. O interpretador remove datas repetidas (vale a
  última) e o serviço grava as linhas **em ordem crescente de data**, a mesma ordem em
  qualquer requisição (evita deadlock entre duas atualizações simultâneas).
- **Configuração:** `INDICES_TTL_HORAS` e `BACEN_TIMEOUT_SEGUNDOS` aceitam número **decimal
  positivo** (não só inteiro), para os testes usarem TTL de poucos segundos e timeout de 1 s;
  `BACEN_URL_BASE` precisa começar com `http://` ou `https://`.
- **"Hoje"** vem de uma função que recebe o instante (`America/Sao_Paulo`, `zoneinfo`), para
  os testes fixarem a data; "N meses para trás" usa aritmética de calendário da biblioteca
  padrão (dia 31 e 29/02 ajustados ao último dia do mês).
- **`atualizado_em` do índice** é o maior `atualizado_em` das suas linhas; o upsert regrava
  todas as linhas da janela, então uma atualização bem-sucedida renova o cache mesmo sem
  novidades. Um HTTP 404 "sem dados" (ou lista vazia) **não** renova o cache (a próxima
  requisição tenta de novo).
- **404 do SGS:** só é "sem dados" quando o corpo traz `Value(s) not found`; qualquer outro
  404 é falha.
- **Ordem de verificação na rota:** token (401) → índice (404) → `periodo` (422) → cache/BACEN.
  A rota usa `usuario_atual()` como as demais (conta excluída → 401).
- Todos os usuários e linhas de teste são removidos; o cache real de `CDI`/`IPCA` gravado pelas
  conferências com a rede é apagado ao final (a tabela termina vazia).

### Tarefa 1 — Configuração por ambiente
- **Arquivos:** `config.py`, `.env.example`
- **Mudança:** três variáveis **opcionais** em `Config` — `BACEN_URL_BASE` (padrão
  `https://api.bcb.gov.br/dados/serie/bcdata.sgs`), `BACEN_TIMEOUT_SEGUNDOS` (padrão 8) e
  `INDICES_TTL_HORAS` (padrão 12) —, com erro claro na subida para valor inválido (URL sem
  `http(s)://`, número não positivo ou não numérico), no estilo de
  `JWT_ACCESS_TOKEN_EXPIRES_MINUTOS`; documentadas (comentadas) no `.env.example`.
- **Validar:** `python -c "import config; print(config.Config.BACEN_URL_BASE, config.Config.BACEN_TIMEOUT_SEGUNDOS, config.Config.INDICES_TTL_HORAS)"`
  mostra os padrões; com `INDICES_TTL_HORAS=0.001`, `BACEN_TIMEOUT_SEGUNDOS=1` e uma URL
  `http://127.0.0.1:9999` os valores mudam; `abc`, `0`, `-1` e `ftp://x` em cada variável
  falham com a mensagem esperada; `git status` não lista o `.env`.

### Tarefa 2 — Interpretação da resposta do BACEN (`bacen.py`, parte 1)
- **Arquivos:** `app/integrations/__init__.py`, `app/integrations/bacen.py`,
  `tests/integrations/__init__.py`, `tests/integrations/test_bacen.py`
- **Mudança:** funções **puras** (só biblioteca padrão): montar a URL e os parâmetros
  (`formato=json`, `dataInicial`/`dataFinal` em `dd/mm/aaaa`) com a **guarda de 10 anos**, e
  `interpretar_resposta(status, corpo, hoje)` — lista de `(data, Decimal)` em ordem crescente,
  sem datas futuras e sem datas repetidas; 404 com `Value(s) not found` → lista vazia
  ("sem dados"); JSON quebrado, corpo que não é lista, linha com data/valor inválidos ou
  qualquer outro status → exceção do módulo. Não confere `Content-Type`.
- **Validar (`pytest tests/integrations/test_bacen.py`):** **payloads reais gravados** da
  API (trechos das séries 4389 e 13522 e os corpos de erro 404 e 406 capturados na sondagem):
  lista normal → `Decimal` exatos (`13.65`) e datas certas; data futura ignorada; valor
  negativo aceito; datas repetidas → uma linha (a última); lista vazia → vazia; 404 "Value(s)
  not found" → vazia, outro 404 → exceção; 406, 500, corpo HTML, JSON quebrado, objeto em vez
  de lista, `data` fora de `dd/mm/aaaa`, `valor` não numérico, `NaN`/`Infinity`/`1e999999` →
  exceção; a URL e as datas de uma janela de 60 meses saem certas e uma janela > 10 anos é
  recusada; um teste lê os `import` de `bacen.py` e confirma que **não** há Flask, SQLAlchemy
  nem `app.models`.

### Tarefa 3 — Cliente HTTP do SGS (`bacen.py`, parte 2)
- **Arquivos:** `app/integrations/bacen.py`, `tests/integrations/test_bacen_http.py`
- **Mudança:** `buscar_serie(codigo, inicio, fim, url_base, timeout)` com `requests` (timeout
  de conexão e de leitura, sem nova tentativa), que traduz qualquer falha de rede, HTTP ou
  interpretação numa **única exceção** (`BacenIndisponivel`), registra o motivo real no log e
  nunca o repassa ao cliente.
- **Validar:** teste `pytest` com um servidor HTTP falso da biblioteca padrão, em thread,
  respondendo `200` com o `Content-Type: text/html` (como o SGS) e corpo JSON → lista certa;
  e falhando sob comando: conexão recusada (porta fechada), resposta mais lenta que o
  timeout, `500`, `406`, `404` "Value(s) not found" (→ vazia), `404` de outro tipo, HTML,
  JSON quebrado e linha inválida → `BacenIndisponivel` (e vazia no caso do 404 "sem dados");
  confere os parâmetros recebidos pelo servidor falso (`dataInicial`, `dataFinal`,
  `formato=json`); o log traz o motivo e a mensagem da exceção **não** traz URL, corpo nem
  detalhes internos.

### Tarefa 4 — Cache: gravação e leitura (`services/indices.py`, parte 1)
- **Arquivos:** `app/services/indices.py`
- **Mudança:** o mapa dos dois índices (`CDI` → série 4389, `IPCA` → 13522, com descrição e
  unidade), a função de "hoje" em `America/Sao_Paulo`, a aritmética de "N meses para trás",
  o **upsert** em `indices_economicos_cache` (`INSERT ... ON CONFLICT` na restrição única,
  linhas em ordem crescente, `valor` e `atualizado_em` atualizados) e a **leitura**: pontos
  do período (data até hoje, em ordem crescente), a `sugestao` (o valor mais recente até
  hoje, independente do período) e o `atualizado_em` do índice.
- **Validar:** script descartável com o banco: upsert de uma lista → linhas certas
  (`valor` como `Decimal`); repetir o mesmo upsert → **nenhuma linha nova**, `atualizado_em`
  renovado; mudar um valor → atualizado; upsert simultâneo de duas threads com as mesmas
  datas → sem erro e sem duplicata; leitura: `periodo` de 1 e 3 meses filtra certo, `sugestao`
  é o último valor até hoje mesmo com datas futuras gravadas à mão, ordem crescente; casos de
  calendário de "N meses para trás" (31/03 − 1 mês = 28 ou 29/02, 29/02 − 12 meses);
  `hoje` no fuso de Brasília (às 01:00 UTC ainda é o dia anterior). Limpar o cache de teste.

### Tarefa 5 — Cache: TTL, atualização e fallback (`services/indices.py`, parte 2)
- **Arquivos:** `app/services/indices.py`
- **Mudança:** `consultar_indice(indice, periodo_meses)`: cache mais novo que o TTL → só
  banco; vencido ou vazio → consulta ao BACEN da janela de 60 meses até hoje, grava e responde;
  falha do BACEN → responde com o cache existente marcando `desatualizado`, ou, sem nenhuma
  linha, levanta `IndicesIndisponiveis` (a rota vira 503). "Sem dados" não renova o cache.
- **Validar:** script descartável com o servidor falso e o banco: primeira consulta → 1
  chamada ao BACEN e linhas gravadas; segunda → **0 chamadas** e o mesmo `atualizado_em`;
  com TTL curto, depois de esperar → nova chamada e `atualizado_em` maior; falha (500, 406,
  timeout, HTML, JSON quebrado, linha inválida, conexão recusada) **com cache** →
  `desatualizado` verdadeiro, dados antigos, nada novo gravado; **sem cache** → exceção;
  "sem dados" com cache → dados antigos sem renovar; a janela pedida ao servidor falso é de
  60 meses até hoje (< 10 anos); duas consultas simultâneas com o cache vencido → sem erro e
  sem duplicata; datas futuras devolvidas pelo servidor falso não chegam ao banco. Limpar o
  cache de teste.

### Tarefa 6 — Schemas de saída e do parâmetro `periodo`
- **Arquivos:** `app/schemas/indices.py`
- **Mudança:** schema do parâmetro (`periodo` opcional, padrão `12m`, valores `1m`, `3m`,
  `6m`, `12m`, `24m`, `60m`, mensagem em português listando os permitidos; parâmetros
  desconhecidos recusados) e o schema de saída do contrato (`indice`, `descricao`, `unidade`,
  `serie_sgs`, `sugestao`, `periodo`, `pontos`, `atualizado_em`, `desatualizado`), com números
  como número JSON e datas em ISO.
- **Validar:** script descartável: o `dump` de um resultado de exemplo (CDI 13,65 em
  24/09/2026) gera exatamente o JSON do contrato da spec; `1m`, `3m`, `6m`, `12m`, `24m`,
  `60m` e ausente (→ `12m`) aceitos; `13m`, `abc`, `0`, `-1`, `12M`, vazio, `periodo` repetido
  e `x=1` recusados em português, sem erro 500.

### Tarefa 7 — Schemas do Swagger e documentação da API externa (R8)
- **Arquivos:** `app/__init__.py`
- **Mudança:** acrescentar a `SWAGGER_TEMPLATE` os schemas da resposta do índice (com
  `sugestao`, `pontos` e `desatualizado`) e o texto de referência da **API externa**: Séries
  Temporais (SGS) do Banco Central do Brasil, `api.bcb.gov.br`, licença Open Data Commons Open
  Database License (ODbL), sem cadastro nem chave, as duas rotas usadas (séries 4389 e 13522) e
  o consumo feito no backend.
- **Validar:** `/apispec.json` (pelo `test_client`) contém os schemas novos ao lado dos
  anteriores e a aplicação continua criando; antes de fechar o texto, **confirmar a licença ODbL
  também nas páginas das séries 4389 e 13522** no portal de dados abertos do BCB (ou registrar
  o que aparecer).

### Tarefa 8 — Rota `GET /api/indices/<indice>`
- **Arquivos:** `app/routes/indices.py`, `app/routes/__init__.py`
- **Mudança:** blueprint `indices` (`/api/indices`) com `GET /<indice>` protegido por JWT
  (`usuario_atual()`), aceitando só `cdi` e `ipca` em minúsculas (404 "Índice não encontrado"
  para o resto, inclusive `selic` e `CDI`), lendo o `periodo`, chamando `consultar_indice`
  e traduzindo `IndicesIndisponiveis` em **503** "Dados do Banco Central indisponíveis no
  momento"; docstring OpenAPI 3 completa (contrato, `periodo`, erros, sugestão de IPCA =
  acumulado em 12 meses realizado, desatualizado, e a documentação da API externa do R8).
- **Validar:** `flask routes` lista a rota; `/apispec.json` traz o caminho com o parâmetro
  `periodo`, `security` e as respostas 200/401/404/422/503; `flask run` sobe; sem token → 401;
  `GET /api/indices/selic` sem token → 401 e com token (na tarefa 9) → 404.

### Tarefa 9 — Validação ponta a ponta com o servidor falso
- **Arquivos:** nenhum no projeto.
- **Mudança:** nenhuma; um script descartável sobe o servidor falso do SGS (com contador de
  chamadas e modos de falha), inicia a aplicação **com `BACEN_URL_BASE` apontando para ele**
  e `INDICES_TTL_HORAS` curto, e exercita a API por HTTP real com um usuário de teste.
- **Validar:**
  - cache vazio → `GET /api/indices/cdi` → 200; `sugestao` igual ao último valor até hoje
    servido pelo servidor falso; `pontos` em ordem crescente e sem datas futuras; linhas de
    `CDI` no banco (`valor` como publicado, nenhuma data futura); `desatualizado` falso;
  - repetir → **nenhuma chamada nova** ao servidor falso e `atualizado_em` igual; após o TTL
    → nova chamada e `atualizado_em` maior;
  - IPCA: `sugestao` é o último mês publicado com `data_referencia` no dia 1; `selic` e
    `CDI` → 404; sem token/token inválido/expirado → 401;
  - `periodo`: `1m`, `3m`, `6m`, `12m`, `24m` e `60m` respeitam o período; ausente = `12m`;
    `abc`, `13m`, `0`, `-1`, vazio, repetido e `x=1` → 422 em português; índice inválido com
    `periodo` inválido → 404 (não 422);
  - **falhas** (500, 406, 404 "sem dados", HTML, JSON quebrado, linha inválida, lento acima do
    timeout, conexão recusada): **com cache** → 200 com `desatualizado: true` e nada novo
    gravado; **sem cache** → 503 com a mensagem clara e sem vazar detalhes; o restante da API
    (`/api/saude`, simulações) segue funcionando; o motivo aparece no log da aplicação;
  - várias requisições simultâneas com o cache vencido → todas 200, sem duplicatas no banco;
  - números como número JSON; nenhum `Traceback` no log.
  Ao final, remover o usuário de teste e limpar o cache.

### Tarefa 10 — Conferência com a API real do BACEN
- **Arquivos:** nenhum no projeto.
- **Mudança:** nenhuma; verificação com a rede real, com o servidor da aplicação **sem**
  `BACEN_URL_BASE` (padrão).
- **Validar:** `GET /api/indices/cdi` e `.../ipca` → 200, `sugestao.valor` idêntico ao último
  valor até hoje de uma consulta direta `curl` às séries 4389 e 13522 (dentro do mesmo dia),
  linhas gravadas em `indices_economicos_cache` (CDI ~1.250, IPCA 60 na janela de 60 meses),
  nenhuma data futura; segunda chamada sai do cache (`atualizado_em` igual); `periodo=1m` e
  `60m` coerentes; tempo da primeira chamada e da segunda registrados. Limpar o cache ao final.

### Tarefa 11 — Validação manual no Swagger UI (sua)
- **Arquivos:** nenhum.
- **Mudança:** nenhuma; eu subo o servidor (com rede real) e você confere no navegador.
- **Validar:** em `/apidocs/`: a rota aparece (grupo "Índices") com o contrato, o `periodo`, os
  erros (inclusive 503) e a **documentação da API externa** (nome, licença ODbL, sem cadastro,
  rotas usadas, consumo no backend); login, **Authorize** com só o token, `GET .../cdi`,
  `.../ipca` (conferir `sugestao`, `data_referencia` e `pontos`), `?periodo=1m` e um 422
  (`periodo=13m`) e o 404 de `selic`. Se a página falhar, parar e avisar antes de mudar o
  esquema do Swagger.

### Tarefa 12 — Regressão e conferência de dependências
- **Arquivos:** nenhum.
- **Mudança:** nenhuma; verificação.
- **Validar:** `pytest` (suíte inteira) verde, sem avisos; `flask run` sobe sem as variáveis
  novas (padrões); `/api/saude` e `/apidocs/` → 200; login e `perfil` funcionam; todos os
  scripts descartáveis das Etapas 1 a 7 (incluindo os ponta a ponta de simulações,
  financiamentos e resultado) → `TUDO OK`; `flask db migrate` → "No changes in schema
  detected"; `pip check` limpo; `requirements.txt` e `requirements-dev.txt` inalterados; sem
  segredo em arquivo versionável; sem `DeprecationWarning` ao importar a aplicação; as 4 tabelas
  vazias.

### Tarefa 13 — Atualizar a documentação
- **Arquivos:** `plano.md`, `CLAUDE.md`, esta spec
- **Mudança:**
  - `plano.md`: marcar a Etapa 8 como concluída com as decisões (**só CDI e IPCA, sem Selic**;
    séries 4389 e 13522; contrato; TTL de 12 h e janela de 60 meses; falhas; configuração);
    registrar que a **decisão 11 da Etapa 2 foi descartada** (taxas seguem obrigatórias na
    simulação); na Etapa 10, os testes de integração da rota (com servidor falso) e o
    contrato sem `selic`; na Etapa 11, conferir os dados de fuso (`tzdata`) na imagem e as
    variáveis do BACEN; na Etapa 12, a seção da API externa (R8);
  - `CLAUDE.md`: estrutura ✔ (`integrations/bacen.py`, `services/indices.py`,
    `schemas/indices.py`, `routes/indices.py`), a rota e o **contrato** (`sugestao`, `pontos`,
    `periodo`, `atualizado_em`, `desatualizado`, 503), as séries e unidades, a política do cache
    e do fallback, as três variáveis de ambiente, a regra "todo acesso ao BACEN passa por
    `integrations/`, com timeout, sem repassar detalhes ao cliente", o teste com servidor falso
    e payloads reais, o contrato com o frontend (**sem `GET /api/indices/selic`**, pré-preencher
    o formulário com `sugestao.valor` de CDI e IPCA, avisar quando `desatualizado`, tratar 503
    deixando digitar) e o "Estado atual";
  - esta spec: marcar os critérios de aceite e o status como implementada.
- **Validar:** reler os três arquivos e conferir que não restam menções a "índices do BACEN
  ainda não" nem à sugestão automática na criação da simulação como plano.

### Tarefa 14 — Conferência final
- **Arquivos:** nenhum.
- **Mudança:** nenhuma; verificação de todos os critérios de aceite.
- **Validar:** percorrer a lista de critérios, informar o que passou e o que dependeu da sua
  verificação manual e da rede real, mostrar o resultado do `pytest` e o `git status --short`
  final (esperado: `app/integrations/`, `app/services/indices.py`, `app/schemas/indices.py`,
  `app/routes/indices.py`, `tests/integrations/`, alterações em `config.py`, `.env.example`,
  `app/__init__.py`, `app/routes/__init__.py` e documentação) e aguardar você pedir o commit.
