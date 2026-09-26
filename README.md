# Rota Financeira — Backend

API REST do **Rota Financeira**, um comparador de cenários para a compra de um carro. A partir dos dados informados pelo usuário e das taxas reais do Banco Central, a API calcula e compara três formas de comprar:

1. **À vista**, pelo valor do veículo hoje;
2. **Financiada**, com 2 ou 3 opções de financiamento (sistemas **Price** e **SAC**);
3. **À vista no futuro**, acumulando o valor em um fundo de investimento enquanto o preço do carro é corrigido pelo IPCA.

Este projeto é o MVP da pós-graduação em Desenvolvimento Full Stack da PUC-Rio. **Este repositório contém
somente o backend**; o frontend (SPA em React) fica em outro repositório e conversa com a API apenas por HTTP/JSON:

| Módulo | Repositório |
|---|---|
| Backend (API REST) | https://github.com/erbraga/rota_financeira-backend |
| Frontend (SPA React) | https://github.com/erbraga/rota_financeira-frontend |

O contrato entre os dois é a especificação OpenAPI da API, publicada em `/apidocs/` (Swagger UI) quando a
aplicação está no ar.

## Funcionalidades

- **Autenticação** com JWT (registro, login e perfil); cada usuário só enxerga e altera as próprias simulações.
- **Simulações** de compra (CRUD): valor do veículo, entrada, IPCA projetado, rendimento do fundo e prazo do fundo.
- **Opções de financiamento** (até 3 por simulação), em Price ou SAC, com a **tabela de parcelas** de cada uma.
- **Resultado comparativo** dos três cenários: custo total de cada um, o de menor custo e as **séries mês a mês** que
  alimentam o gráfico do frontend (o frontend só exibe, não recalcula). Há também o modo "dado o aporte mensal".
- **Taxas sugeridas do Banco Central** (CDI e IPCA), com cache no banco e uso pelo backend (a API externa é
  descrita na seção [API externa](#api-externa-banco-central-sgs)).

## Arquitetura

![Fluxograma da arquitetura do Rota Financeira e do cenário de uso](docs/img/arquitetura.png)

A imagem acima ilustra um cenário de uso: **o usuário compara como comprar um carro**. Há uma
[versão vetorial (SVG)](docs/img/arquitetura.svg) e o arquivo-fonte do [Graphviz](docs/img/arquitetura.dot), que permite
regenerá-la (`dot -Tpng -Gdpi=100 arquitetura.dot -o arquitetura.png`, dentro de `docs/img`).

**O cenário, passo a passo**

| Passo | O que acontece |
|---|---|
| **1** | O usuário entra no frontend, que chama `POST /api/auth/login` e recebe um **token JWT**, enviado nas demais requisições. |
| **2** | O frontend pede a taxa sugerida (`GET /api/indices/cdi`). A API primeiro **lê o cache** no PostgreSQL (**2a**, vale 12 horas). |
| **2b** | Se o cache estiver vencido, o cliente HTTP da API busca a série no **Banco Central (SGS)** e grava no banco; se o BACEN estiver fora do ar, a API serve o cache marcado como desatualizado (ou responde 503 se não houver nada guardado). |
| **3** | O usuário informa os dados: o frontend envia `POST /api/simulacoes` e, para cada opção, `POST /api/simulacoes/{id}/financiamentos`; a API valida e **grava** no PostgreSQL. |
| **4** | O frontend pede `GET /api/simulacoes/{id}/resultado`. A API **lê** os dados e **calcula** Price, SAC e o fundo. |
| **5** | A API devolve um JSON com os totais de cada cenário, o `menor_custo` e as séries mês a mês; o frontend exibe os cartões-resumo e os gráficos. |

**Camadas da API** (todas em `app/`)

| Camada | Responsabilidade |
|---|---|
| `routes/` | Só HTTP: blueprints sob `/api`, autenticação JWT, códigos de status e a documentação Swagger de cada rota. |
| `schemas/` | Validação dos dados de entrada e serialização da saída (Marshmallow), com mensagens em português. |
| `services/` | Regras de aplicação e acesso ao banco: simulações, financiamentos, resultado e cache dos índices. |
| `services/calculo/` | **Cálculo financeiro puro** (Price, SAC, fundo e composição dos cenários), só com a biblioteca padrão e `Decimal`, sem Flask nem banco. |
| `integrations/` | Único ponto de contato com a API externa (cliente do Banco Central, com timeout e tratamento de falhas). |
| `models/` e `migrations/` | Tabelas (SQLAlchemy) e o histórico do schema (Alembic): `usuarios`, `simulacoes`, `opcoes_financiamento` e `indices_economicos_cache`. |

## Tecnologias

| Tecnologia | Versão | Para que serve |
|---|---|---|
| Python | 3.12 | Linguagem do projeto |
| Flask | 3.1.2 | Framework web |
| Flask-SQLAlchemy | 3.1.1 | ORM (SQLAlchemy 2) |
| Flask-Migrate | 4.1.0 | Migrations do banco (Alembic) |
| PostgreSQL | 18 | Banco de dados |
| psycopg | 3.3.6 | Driver do PostgreSQL |
| Flask-JWT-Extended | 4.7.4 | Autenticação por token JWT |
| Marshmallow | 4.3.1 | Validação e serialização |
| Flasgger | 0.9.7.1 | Documentação Swagger/OpenAPI 3 (`/apidocs/`) |
| flask-cors | 6.0.2 | CORS restrito às origens do frontend |
| requests | 2.34.2 | Cliente HTTP da API do Banco Central |
| python-dotenv | 1.2.3 | Leitura do arquivo `.env` |
| gunicorn | 26.2.0 | Servidor de produção (no contêiner) |
| Docker | — | Empacotamento da API |
| pytest | 9.1.1 | Testes (só em `requirements-dev.txt`) |

## Instalação e execução local

**Pré-requisitos:** Python 3.12 (com o módulo `venv`), Git e Docker (para o PostgreSQL). Os comandos abaixo são de
**Linux/macOS (bash)**; no Windows, use o **WSL** ou siga apenas o caminho [Executar com Docker](#executar-com-docker),
que não depende do shell.

**1. Clonar o repositório**

```bash
git clone https://github.com/erbraga/rota_financeira-backend.git
cd rota_financeira-backend
```

**2. Criar o ambiente virtual e instalar as dependências**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**3. Configurar as variáveis de ambiente**

```bash
cp .env.example .env
```

Abra o `.env` e preencha, no mínimo:

- a **senha do banco**, a mesma em `POSTGRES_PASSWORD` e dentro de `DATABASE_URL` (substitua `troque-esta-senha`; a linha
  comentada `TEST_DATABASE_URL` só precisa dela se você a ativar);
- a **chave dos tokens** em `JWT_SECRET_KEY`, com pelo menos 32 caracteres. Para gerar uma:
  `python -c "import secrets; print(secrets.token_hex(32))"`.

O `.env` guarda segredos e **nunca deve ser versionado** (já está no `.gitignore`); as demais variáveis estão na
tabela [Variáveis de ambiente](#variáveis-de-ambiente).

**4. Subir o PostgreSQL** (contêiner Docker; as credenciais são lidas do `.env`, nada é escrito no comando)

```bash
set -a; source .env; set +a
docker run -d --name rota-financeira-db \
  -e POSTGRES_USER -e POSTGRES_PASSWORD -e POSTGRES_DB \
  -p 127.0.0.1:5432:5432 \
  -v rota_financeira_pgdata:/var/lib/postgresql \
  --restart unless-stopped postgres:18
```

Se o contêiner já existir e estiver parado, basta `docker start rota-financeira-db`. Os dados ficam no volume
`rota_financeira_pgdata`.

**5. Criar as tabelas** (migrations)

```bash
flask db upgrade
```

**6. Executar a API**

```bash
flask run
```

A API responde em `http://127.0.0.1:5000`: `GET /api/saude` confere a API e o banco, e a documentação interativa
(Swagger UI) fica em `http://127.0.0.1:5000/apidocs/`. Para simular a execução de produção, use
`gunicorn run:app` (o gunicorn escuta, por padrão, em `http://127.0.0.1:8000`). Para usar as rotas protegidas no Swagger: registre um usuário, faça o login e clique em
**Authorize**, colando apenas o token.

## Variáveis de ambiente

Todas as configurações vêm de variáveis de ambiente (o arquivo `.env` é lido automaticamente; uma variável já definida
no ambiente prevalece sobre o arquivo). A aplicação **não sobe** sem as obrigatórias e diz qual está faltando.

| Variável | Obrigatória | Padrão | Descrição |
|---|---|---|---|
| `DATABASE_URL` | sim | — | URL do PostgreSQL: `postgresql+psycopg://usuario:senha@host:5432/banco` |
| `JWT_SECRET_KEY` | sim | — | Chave que assina os tokens JWT (mínimo de 32 caracteres, diferente do valor de exemplo) |
| `JWT_ACCESS_TOKEN_EXPIRES_MINUTOS` | não | `60` | Validade do token de login, em minutos |
| `CORS_ORIGINS` | não | vazio (nenhuma origem liberada) | Origens do frontend permitidas, separadas por vírgula (ex.: `http://localhost:5173,http://localhost:3000`) |
| `FLASK_DEBUG` | não | `0` | Modo de depuração do Flask (use `0` fora do desenvolvimento) |
| `FLASK_APP` | não | — | `run.py`; usada só pelos comandos `flask` no ambiente local (já vem no `.env.example`) |
| `BACEN_URL_BASE` | não | `https://api.bcb.gov.br/dados/serie/bcdata.sgs` | Endereço base da API do Banco Central |
| `BACEN_TIMEOUT_SEGUNDOS` | não | `8` | Tempo máximo de espera pela resposta do Banco Central |
| `INDICES_TTL_HORAS` | não | `12` | Validade do cache dos índices, em horas (aceita fração) |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | só para criar o banco | — | Credenciais usadas no `docker run` do PostgreSQL (passo 4) |
| `TEST_DATABASE_URL` | não | banco `bd_test` na mesma instância do `DATABASE_URL` | Banco dos testes de integração (o nome **deve terminar em `_test`**) |
| `WEB_CONCURRENCY` | não | `2` | Número de processos do gunicorn (só no contêiner) |

Os modelos dos arquivos são o [`.env.example`](.env.example) (ambiente local) e o
[`.env.docker.example`](.env.docker.example) (contêiner).

## Executar com Docker

O `Dockerfile` da raiz gera a imagem de **produção** da API: instala só o `requirements.txt`, roda como usuário sem
privilégios, aplica as migrations ao iniciar (`flask db upgrade`) e sobe o gunicorn na porta 5000, com verificação de
saúde em `/api/saude`. **Nenhum segredo entra na imagem**: as variáveis chegam na hora de executar, por um arquivo local.
O PostgreSQL não faz parte da imagem; a API o encontra pela variável `DATABASE_URL`.

**1. Ter um PostgreSQL no ar.** Use o contêiner do [passo 4 da instalação local](#instalação-e-execução-local)
(`rota-financeira-db`); se estiver parado, `docker start rota-financeira-db`.

**2. Criar o arquivo de variáveis do contêiner**

```bash
cp .env.docker.example .env.docker
```

No `.env.docker`, troque `troque-esta-senha` pela senha do banco (o host `rota-financeira-db` já é o nome do contêiner do
banco na rede Docker) e preencha `JWT_SECRET_KEY`. O `.env.docker` real é **ignorado pelo git e pela imagem**: escreva a senha
**somente nele**, nunca no `.env.docker.example`, que é versionado.

**3. Construir a imagem**

```bash
docker build -t rota-financeira-api .
```

**4. Ligar a API ao banco por uma rede Docker** (uma vez; o contêiner do banco não é recriado nem perde dados)

```bash
docker network create rota-financeira-net
docker network connect rota-financeira-net rota-financeira-db
```

**5. Executar a API**

```bash
docker run -d --name rota-financeira-api \
  --network rota-financeira-net \
  --env-file .env.docker \
  -p 5000:5000 rota-financeira-api
```

**6. Conferir.** `docker logs rota-financeira-api` mostra a migração e o gunicorn; `docker ps` marca o contêiner como
`healthy` em até cerca de 30 segundos; `curl http://localhost:5000/api/saude` responde `{"banco":"ok","status":"ok"}` e o
Swagger abre em `http://localhost:5000/apidocs/`. Para usar outra porta do computador, troque o lado esquerdo de `-p`
(por exemplo, `-p 5100:5000`).

**7. Encerrar e limpar**

```bash
docker rm -f rota-financeira-api
docker network disconnect rota-financeira-net rota-financeira-db
docker network rm rota-financeira-net
```

O contêiner da API usa o banco do contêiner `rota-financeira-db`: o que for criado pela API fica nele. Se o contêiner
sair logo depois de iniciar, veja `docker logs rota-financeira-api`: as causas comuns são variável obrigatória faltando
no `.env.docker` (a mensagem diz qual) ou o banco inacessível pela rede.

## Testes

A suíte usa o `pytest`, com testes de cálculo e do cliente do Banco Central (sem banco) e testes de **integração** da API
inteira, que rodam contra um PostgreSQL de teste separado, o **`bd_test`**: a suíte o cria sozinha na mesma instância do
`DATABASE_URL` (ou usa o `TEST_DATABASE_URL`) e aplica as migrations. Os testes recusam-se a rodar em qualquer banco cujo
nome não termine em `_test`, porque apagam todos os dados dele.

```bash
pip install -r requirements-dev.txt   # uma vez: acrescenta o pytest
pytest                                # tudo (com o PostgreSQL no ar)
pytest -m "not integracao"            # só os testes que não usam banco
pytest -m integracao                  # só os de integração (falham se o PostgreSQL estiver fora do ar)
```

Com o PostgreSQL parado, o `pytest` puro **pula** os testes de integração e avisa como subir o contêiner
(`docker start rota-financeira-db`).

## API externa (Banco Central, SGS)

O projeto usa **uma** API externa, a do **Banco Central do Brasil**: o **Sistema Gerenciador de Séries Temporais (SGS)**,
em `api.bcb.gov.br`, que fornece as **taxas sugeridas** de CDI e IPCA (a Selic não é usada). Ela é consumida **pelo
backend**: o cliente nunca é redirecionado ao Banco Central. A API busca, valida e normaliza os dados e os devolve no seu
próprio formato JSON (rota `GET /api/indices/{cdi|ipca}`).

| Item | Descrição |
|---|---|
| **Cadastro** | Não é necessário: sem chave, token ou login. |
| **Licença** | Os dados abertos do Banco Central adotam a *Open Data Commons Open Database License (ODbL)*, conforme o catálogo do portal de dados abertos (`dadosabertos.bcb.gov.br`). As séries 4389 e 13522 não são listadas individualmente nesse catálogo; o uso segue a política de dados abertos do Banco Central. |
| **Rotas utilizadas** | Ambas por `GET`, com `formato=json`, `dataInicial` e `dataFinal` (formato `dd/mm/aaaa`): |
| CDI (série **4389**) | `https://api.bcb.gov.br/dados/serie/bcdata.sgs.4389/dados` — CDI anualizada, base 252, em % ao ano |
| IPCA (série **13522**) | `https://api.bcb.gov.br/dados/serie/bcdata.sgs.13522/dados` — IPCA acumulado em 12 meses, em % ao ano |

**Como a API a utiliza**

- As respostas ficam em **cache no PostgreSQL** (tabela `indices_economicos_cache`): a API só consulta o Banco Central quando o
  cache está vazio ou tem mais de **12 horas** (`INDICES_TTL_HORAS`), e busca uma janela de **60 meses**.
- A **taxa sugerida** é o valor mais recente publicado até hoje. O SGS não tem projeção de inflação: a sugestão do IPCA é o
  acumulado em 12 meses do último mês publicado. O usuário pode informar outros valores ao criar a simulação; a criação da
  simulação **não depende** do Banco Central.
- Se o Banco Central estiver fora do ar (ou demorar mais de 8 segundos), a API responde com o cache existente, marcado com
  `"desatualizado": true`; sem nada em cache, responde **503** com uma mensagem clara. As demais rotas continuam funcionando.

## Rotas e contrato

Todas as rotas ficam sob `/api`. Com exceção de `saude`, `registrar` e `login`, exigem o cabeçalho
`Authorization: Bearer <token>` (o token vem de `POST /api/auth/login`). Cada usuário só acessa os próprios dados: um
recurso de outro usuário responde **404**, igual a um que não existe. A documentação **completa e interativa** (campos,
exemplos e códigos de resposta de cada rota) é o Swagger, em **`/apidocs/`**; a especificação OpenAPI está em `/apispec.json`.

| Método | Rota | Descrição | Autenticação |
|---|---|---|---|
| `GET` | `/api/saude` | Verifica se a API e o banco de dados estão respondendo | não |
| `POST` | `/api/auth/registrar` | Cria uma conta de usuário | não |
| `POST` | `/api/auth/login` | Autentica o usuário e devolve o token JWT | não |
| `GET` | `/api/auth/perfil` | Devolve os dados do usuário dono do token | sim |
| `POST` | `/api/simulacoes` | Cria uma simulação do usuário logado | sim |
| `GET` | `/api/simulacoes` | Lista as simulações do usuário logado | sim |
| `GET` | `/api/simulacoes/{simulacao_id}` | Detalha uma simulação do usuário logado | sim |
| `PUT` | `/api/simulacoes/{simulacao_id}` | Substitui os dados de uma simulação | sim |
| `DELETE` | `/api/simulacoes/{simulacao_id}` | Exclui uma simulação (e as opções dela) | sim |
| `GET` | `/api/simulacoes/{simulacao_id}/resultado` | Compara os três cenários da simulação | sim |
| `POST` | `/api/simulacoes/{simulacao_id}/financiamentos` | Cadastra uma opção de financiamento (no máximo 3) | sim |
| `GET` | `/api/simulacoes/{simulacao_id}/financiamentos` | Lista as opções de financiamento da simulação | sim |
| `PUT` | `/api/simulacoes/{simulacao_id}/financiamentos/{financiamento_id}` | Substitui os dados de uma opção de financiamento | sim |
| `DELETE` | `/api/simulacoes/{simulacao_id}/financiamentos/{financiamento_id}` | Exclui uma opção de financiamento | sim |
| `GET` | `/api/simulacoes/{simulacao_id}/financiamentos/{financiamento_id}/parcelas` | Tabela de amortização (Price ou SAC) de uma opção | sim |
| `GET` | `/api/indices/{indice}` | Taxa sugerida e série do Banco Central (`indice` = `cdi` ou `ipca`, em minúsculas) | sim |

**Convenções:** erros sempre em JSON, `{"erro": "mensagem"}`, com `detalhes` por campo nos erros de validação (422); valores
monetários e taxas saem como **número JSON**, e as taxas são **percentuais** (`12.5` = 12,5 %); `POST` responde 201 com o
cabeçalho `Location`, e `DELETE` responde 204 sem corpo.

### Resultado da simulação

`GET /api/simulacoes/{id}/resultado` devolve tudo pronto para o frontend exibir:

- **`cenarios`**: `a_vista`, `financiamentos` (0 a 3, na ordem de criação, cada um com `primeira_parcela`,
  `ultima_parcela`, `total_pago`, `total_juros` e `custo_total`) e `fundo` (aporte mensal calculado, prazo, saldo final etc.);
- **`custo_total`** é **o que se paga pelo carro** em cada cenário: à vista = valor do veículo; financiamento = entrada da
  opção + soma das parcelas; fundo = preço do carro corrigido pelo IPCA na data da compra. A comparação é nominal;
- **`menor_custo`**: `{"cenario": "a_vista" | "financiamento" | "fundo", "id": ...}` (em caso de empate, vale a ordem à vista,
  financiamentos e fundo);
- **`series`**: um ponto por mês, num eixo comum do mês 0 ao maior prazo, com `preco_corrigido`, `saldo_fundo` e `saldo_devedor`
  (indexado pelo `id` de cada opção); onde uma série já terminou o valor é **`null`**, e o gráfico não deve ligar essas lacunas;
- **modo `?aporte_mensal=1500`**: o aporte informado substitui o calculado e o fundo passa a indicar em que mês alcança o preço
  do carro (`mes_da_meta`, até 60 meses, ou `null` se não alcançar).

```jsonc
{
  "simulacao": { "id": 1, "nome": "Onix 2026", "valor_veiculo": 95000.0, "valor_entrada": 20000.0, "...": "..." },
  "cenarios": {
    "a_vista": { "custo_total": 95000.0 },
    "financiamentos": [
      { "id": 1, "nome": "Banco X 48x", "sistema_amortizacao": "PRICE", "valor_financiado": 75000.0,
        "primeira_parcela": 2440.16, "ultima_parcela": 2440.55, "total_pago": 117128.07, "custo_total": 137128.07, "...": "..." }
    ],
    "fundo": { "aporte_mensal": 1948.07, "mes_da_meta": 36, "preco_na_compra": 108410.78, "custo_total": 108410.78, "...": "..." }
  },
  "menor_custo": { "cenario": "a_vista", "id": null },
  "series": [ { "mes": 0, "preco_corrigido": 95000.0, "saldo_fundo": 20000.0, "saldo_devedor": { "1": 75000.0 } }, "..." ]
}
```

### Taxas sugeridas

`GET /api/indices/{cdi|ipca}?periodo=12m` devolve `indice`, `descricao`, `unidade` (`% a.a.`), `serie_sgs`, a **`sugestao`**
(`valor` e `data_referencia`, o valor mais recente até hoje, que o frontend usa para preencher o formulário), o `periodo`,
os `pontos` da série (`periodo` aceita `1m`, `3m`, `6m`, `12m`, `24m` e `60m`; padrão `12m`), `atualizado_em` e
`desatualizado`.

## Estrutura do projeto

```text
.
├── app/                      # a aplicação (ver "Camadas da API")
│   ├── __init__.py           # create_app(): configuração, extensões, Swagger, CORS, erros e blueprints
│   ├── errors.py             # respostas de erro em JSON
│   ├── extensions.py         # instâncias únicas (db, migrate, jwt)
│   ├── models/               # tabelas
│   ├── routes/               # blueprints: saude, auth, simulacoes, financiamentos, indices
│   ├── schemas/              # validação e serialização
│   ├── services/             # regras de aplicação; services/calculo/ = cálculo puro
│   └── integrations/         # cliente do Banco Central
├── migrations/               # Alembic (Flask-Migrate)
├── tests/                    # calculo/, integrations/ e api/ (integração com o PostgreSQL)
├── docs/
│   ├── img/                  # fluxograma da arquitetura (.dot, .png e .svg)
│   └── specs/                # especificações e planos de cada etapa do desenvolvimento
├── config.py                 # configuração por variáveis de ambiente
├── run.py                    # ponto de entrada (app = create_app())
├── Dockerfile                # imagem de produção da API
├── docker-entrypoint.sh      # migra o banco e sobe o gunicorn no contêiner
├── requirements.txt          # dependências de execução
├── requirements-dev.txt      # + pytest
├── .env.example              # modelo das variáveis do ambiente local
├── .env.docker.example       # modelo das variáveis do contêiner
├── plano.md                  # plano de implementação por etapas
└── proposta-backend-api-rest.md   # proposta do backend
```

## Autoria

Projeto acadêmico desenvolvido por [Emerson Range Braga](https://github.com/erbraga) na pós-graduação em Desenvolvimento
Full Stack da PUC-Rio.

**Licença:** este projeto não define uma licença de reuso do código. A licença ODbL citada na seção
[API externa](#api-externa-banco-central-sgs) é a dos **dados** do Banco Central, e não a do código deste repositório.
