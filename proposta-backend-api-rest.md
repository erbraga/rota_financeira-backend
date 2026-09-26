# Proposta – Parte 1: Backend (API REST)

**Projeto:** Comparador de Cenários para Compra de Carros
**Parte:** Backend, API REST em Flask + PostgreSQL
**Parte complementar:** Frontend (SPA React), em outro repositório: https://github.com/erbraga/rota_financeira-frontend

> Este documento foi **atualizado em 2026-09-26 para refletir o projeto entregue**. A proposta original (com a Selic, a tabela FIPE, a tabela
> `parcelas_calculadas`, o APScheduler e a escolha entre Marshmallow e Pydantic) continua disponível no histórico do git. O passo a passo de
> instalação e execução está no [README](README.md) e a decisão de cada etapa, em [`docs/specs/`](docs/specs/) e no [`plano.md`](plano.md).

## 1. Contexto do projeto

O projeto é uma aplicação web que ajuda o usuário a decidir **como comprar um carro**. Ela compara três cenários financeiros com dados econômicos reais do Banco Central:

1. Compra à vista.
2. Compra financiada, com até 3 opções de financiamento.
3. Compra à vista no futuro, acumulando o valor em um fundo de investimento.

Quem vai comprar um carro costuma comparar só o valor da parcela. Ele deixa de considerar o custo total dos juros, a alta do preço do carro (inflação) enquanto junta dinheiro e o rendimento do dinheiro guardado. A aplicação reúne esses cálculos em um só lugar e usa taxas reais (CDI e IPCA) de uma fonte oficial.

### 1.1 Decisão de arquitetura

O sistema é implementado em **duas partes independentes**, que se comunicam apenas por HTTP/JSON:

| Parte | Responsabilidade | Repositório |
|---|---|---|
| **Backend (este documento)** | Regras de negócio, cálculos financeiros, persistência, autenticação, integração com o BACEN | https://github.com/erbraga/rota_financeira-backend |
| **Frontend** | Interface do usuário (SPA), formulários, gráficos e consumo da API | https://github.com/erbraga/rota_financeira-frontend |

O backend não conhece o frontend e pode ser testado, documentado e evoluído sozinho, pelo Swagger. O **contrato entre as duas partes é a especificação OpenAPI** gerada pelo Flasgger (`/apidocs/` e `/apispec.json`), com os endpoints da seção 7.

## 2. Objetivos do backend

- Expor uma API REST completa para autenticação, simulações, opções de financiamento e índices econômicos.
- Implementar o cálculo de financiamento pelos sistemas **Price** e **SAC**, com tabela de amortização mês a mês.
- Projetar o preço futuro do veículo com correção pelo **IPCA**.
- Simular o fundo de acumulação com aportes mensais e rendimento (taxa informada pelo usuário, com o CDI como valor sugerido).
- Integrar a API SGS do Banco Central e manter um cache local dos índices.
- Persistir simulações por usuário e permitir revisitá-las.
- Documentar e permitir testar a API com Swagger (Flasgger).

## 3. Escopo

### 3.1 Incluído

- Cadastro e login de usuários (JWT), com o isolamento dos dados por usuário.
- CRUD de simulações e das opções de financiamento de cada uma (até 3 por simulação).
- Parâmetros personalizáveis: valor do veículo (sempre informado pelo usuário), entrada, taxa de juros, prazo, sistema de amortização, taxa do fundo e prazo para acumulação.
- Cálculo dos três cenários e endpoint de resultado comparativo, com as séries mês a mês, e a tabela de parcelas de cada opção.
- Endpoints de índices econômicos (CDI e IPCA) com cache.
- Documentação interativa da API, testes automatizados e execução em contêiner Docker.

### 3.2 Fora do escopo entregue

- Cálculo do CET (Custo Efetivo Total).
- Paginação, ordenação e filtros nas listagens.
- A Selic e a consulta ao preço do veículo em tabela externa (FIPE ou similar).
- Limitação de tentativas (*rate limiting*) no login e no registro, e atualização agendada do cache (o cache é atualizado sob demanda).

## 4. Lógica de cálculo

A lógica de negócio fica na camada de **serviços**, separada das rotas HTTP, em um pacote de **cálculo puro** (`app/services/calculo/`: só biblioteca padrão e `Decimal`, sem Flask nem banco).

| Cenário | Cálculo |
|---|---|
| **À vista (corrigido)** | `valor_veiculo × (1 + taxa_ipca)^(prazo_meses/12)`: preço do carro no momento em que o fundo completaria o valor. |
| **Financiamento** | **Price:** parcelas fixas. **SAC:** amortização constante e parcelas decrescentes. Gera a tabela mês a mês com parcela, juros, amortização e saldo devedor (o saldo **após** o pagamento). Juros e parcela são arredondados ao centavo a cada mês e a **última parcela absorve o resíduo**. O custo total é a entrada da opção mais a soma das parcelas. |
| **Fundo de acumulação** | Aportes mensais fixos, **ao fim de cada mês**, rendendo à taxa do fundo (convertida de anual para mensal de forma composta). O `valor_entrada` da simulação é o **capital inicial** do fundo. Dado o prazo, calcula o **menor aporte** (arredondado para cima, ao centavo) que atinge o preço corrigido. Dado o aporte (`?aporte_mensal=`), calcula em que mês o saldo alcança o preço daquele mês (busca até 60 meses). |

Convenções: todo cálculo usa `Decimal` (nunca `float` para dinheiro), taxas entram em **percentual** e são convertidas em um único ponto, e o custo de cada cenário é comparado em **valores nominais** (sem valor presente). O `custo_total` de cada cenário é **o que se paga pelo carro**: à vista, o valor do veículo; financiamento, a entrada mais as parcelas; fundo, o preço corrigido pelo IPCA na data da compra. Em caso de empate no menor custo, vale a ordem à vista, financiamentos e fundo.

## 5. Integração com API pública

- **Banco Central (SGS):** API REST gratuita, sem cadastro nem autenticação, com séries temporais. São usadas duas séries:

  ```
  CDI  (série 4389, CDI anualizada base 252, % a.a.):
  https://api.bcb.gov.br/dados/serie/bcdata.sgs.4389/dados?formato=json
  IPCA (série 13522, IPCA acumulado em 12 meses, % a.a.):
  https://api.bcb.gov.br/dados/serie/bcdata.sgs.13522/dados?formato=json
  ```

- O backend consulta a API, grava o resultado na tabela `indices_economicos_cache` e serve o cliente por endpoints internos. O cache é atualizado **sob demanda**: a API só consulta o BACEN quando o cache está vazio ou tem mais de **12 horas**, e busca uma janela de **60 meses**. Assim a aplicação não depende da disponibilidade do BACEN a cada acesso.
- Se o BACEN estiver fora do ar (ou demorar mais de 8 segundos), a API responde com o cache existente, marcado com `desatualizado: true`; sem nada em cache, responde **503** com uma mensagem clara. A criação de simulações **não depende** do BACEN.
- Os valores retornados são taxas **sugeridas** (o SGS não tem projeção de inflação: a sugestão do IPCA é o acumulado em 12 meses do último mês publicado). O cliente pode enviar valores diferentes ao criar a simulação, e as taxas são sempre obrigatórias no corpo.
- **Licença:** os dados abertos do Banco Central adotam a *Open Data Commons Open Database License (ODbL)*, conforme o catálogo do portal de dados abertos; as séries 4389 e 13522 não são listadas individualmente nesse catálogo, e o uso segue a política de dados abertos do BCB.

## 6. Modelagem de dados (PostgreSQL)

Todas as colunas são `NOT NULL`. Chaves primárias inteiras autoincrementais (`Identity`). Valores monetários em `NUMERIC(14,2)` e taxas e índices em `NUMERIC(12,6)`, **em percentual** (`12.5` = 12,5 %). O schema é versionado com migrations (Alembic).

### usuarios

| Campo | Tipo | Observação |
|---|---|---|
| id | integer | PK |
| nome | varchar(120) | |
| email | varchar(254) | único; a aplicação normaliza para minúsculas |
| senha_hash | varchar(255) | hash scrypt; nunca devolvido |
| criado_em | timestamp com fuso | padrão `now()` |

### simulacoes

| Campo | Tipo | Observação |
|---|---|---|
| id | integer | PK |
| usuario_id | FK → usuarios | `ON DELETE RESTRICT`; o dono vem sempre do token |
| nome | varchar(120) | ex.: "Onix 2026" |
| valor_veiculo | numeric(14,2) | preço à vista **informado pelo usuário** (maior que zero) |
| valor_entrada | numeric(14,2) | de 0 até o valor do veículo; é o capital inicial do fundo |
| taxa_ipca_projetada | numeric(12,6) | % a.a. para corrigir o preço do carro (a sugestão vem do BACEN) |
| taxa_fundo_rendimento | numeric(12,6) | % a.a. usada no cenário de acumulação (não negativa) |
| prazo_meses_fundo | integer | prazo desejado para juntar o valor à vista (maior que zero) |
| criado_em | timestamp com fuso | |

### opcoes_financiamento

Cada simulação tem de 0 a 3 opções.

| Campo | Tipo | Observação |
|---|---|---|
| id | integer | PK |
| simulacao_id | FK → simulacoes | `ON DELETE RESTRICT` (o ORM apaga as opções junto com a simulação) |
| nome | varchar(120) | ex.: "Banco X 48x" |
| taxa_juros_mensal | numeric(12,6) | % a.m. (não negativa) |
| prazo_meses | integer | maior que zero |
| sistema_amortizacao | varchar(5) | `PRICE` ou `SAC` (restrição `CHECK`) |
| valor_entrada | numeric(14,2) | pode diferir da entrada do cenário à vista; menor que o valor do veículo |

Não há tabela de parcelas: a **tabela de amortização é calculada sob demanda** (`/parcelas`), a partir dos dados da opção.

### indices_economicos_cache

| Campo | Tipo | Observação |
|---|---|---|
| id | integer | PK |
| indice | varchar(5) | `CDI` ou `IPCA` em uso (`SELIC` existe na restrição `CHECK`, reservado e sem uso) |
| data_referencia | date | `UNIQUE (indice, data_referencia)` |
| valor | numeric(12,6) | como publicado pelo BACEN, em percentual |
| atualizado_em | timestamp com fuso | |

## 7. Endpoints da API REST

Todas as rotas ficam sob `/api` (16 rotas). Com exceção de `saude`, `registrar` e `login`, exigem o cabeçalho `Authorization: Bearer <token>`. Cada usuário só acessa as próprias simulações: um recurso de outro usuário responde **404**, igual a um que não existe. Erros são sempre JSON (`{"erro": "mensagem"}`, com `detalhes` por campo nos erros de validação).

### 7.1 Saúde e autenticação

```
GET  /api/saude                 # API e banco (público)
POST /api/auth/registrar        # cria a conta (público)
POST /api/auth/login            # devolve o token JWT (público)
GET  /api/auth/perfil           # usuário do token
```

### 7.2 Simulações

```
POST   /api/simulacoes                  # cria simulação
GET    /api/simulacoes                  # lista simulações do usuário logado (envelope itens/total)
GET    /api/simulacoes/:id              # detalhe da simulação
PUT    /api/simulacoes/:id              # substitui os parâmetros (corpo completo)
DELETE /api/simulacoes/:id              # remove (204, junto com as opções)
GET    /api/simulacoes/:id/resultado    # três cenários calculados (?aporte_mensal= opcional)
```

### 7.3 Opções de financiamento

```
POST   /api/simulacoes/:id/financiamentos                  # adiciona opção (no máximo 3; a 4ª responde 409)
GET    /api/simulacoes/:id/financiamentos                  # lista opções
PUT    /api/simulacoes/:id/financiamentos/:fid             # substitui a opção
DELETE /api/simulacoes/:id/financiamentos/:fid             # remove (204)
GET    /api/simulacoes/:id/financiamentos/:fid/parcelas    # tabela de amortização
```

Regras: a entrada da opção é **estritamente menor** que o valor do veículo; editar o valor do veículo para menor ou igual à entrada de uma opção é recusado (422); `sistema_amortizacao` aceita qualquer caixa e devolve maiúsculas.

### 7.4 Índices econômicos (proxy com cache do BACEN)

```
GET /api/indices/cdi?periodo=12m
GET /api/indices/ipca?periodo=12m
```

`periodo` aceita `1m`, `3m`, `6m`, `12m`, `24m` e `60m` (padrão `12m`) e só filtra o cache. A resposta traz a **`sugestao`** (o valor mais recente até hoje), os pontos do período, `atualizado_em` e `desatualizado`. Qualquer outro índice (inclusive `selic`) responde 404.

### 7.5 Documentação e contrato

A resposta de `GET /api/simulacoes/:id/resultado` traz, além dos totais de cada cenário, o `menor_custo` e as **séries mês a mês** que alimentam o gráfico comparativo (preço corrigido do carro, saldo do fundo e saldo devedor de cada opção, num eixo comum, com `null` onde uma série já terminou). Assim o frontend só exibe os dados e não recalcula nada. O formato exato é definido na especificação OpenAPI (`/apidocs/`) e é o que o frontend segue.

## 8. Arquitetura e tecnologias

| Item | Tecnologia |
|---|---|
| Linguagem | Python 3.12 |
| Framework | Flask |
| ORM e migrations | Flask-SQLAlchemy (SQLAlchemy 2), Flask-Migrate (Alembic) |
| Banco de dados | PostgreSQL 18 (driver `psycopg`) |
| Autenticação | Flask-JWT-Extended |
| Validação e serialização | Marshmallow 4 (mensagens em português) |
| Cliente HTTP (BACEN) | requests |
| CORS | Flask-CORS, liberando só as origens do frontend configuradas (ex.: `localhost:5173` ou `3000` em desenvolvimento) |
| Documentação e testes manuais | **Flasgger** (Swagger UI em `/apidocs/`, OpenAPI 3) |
| Configuração | variáveis de ambiente (`python-dotenv` lê o `.env` local) |
| Servidor e empacotamento | gunicorn e Docker (`Dockerfile` da raiz) |
| Testes | pytest (`requirements-dev.txt`) |

### 8.1 Estrutura de pastas

```
app/
  models/          # Usuario, Simulacao, OpcaoFinanciamento, IndiceEconomicoCache
  routes/          # blueprints: saude, auth, simulacoes, financiamentos, indices
  services/        # regras de aplicação e acesso ao banco
    calculo/       # cálculo puro: Price, SAC, fundo e composição dos cenários
  schemas/         # validação e serialização
  integrations/    # cliente da API do BACEN
migrations/
tests/             # calculo/, integrations/ e api/ (integração com o PostgreSQL de teste)
docs/              # img/ (fluxograma) e specs/ (uma spec por etapa)
config.py
run.py
Dockerfile
```

### 8.2 Documentação com Flasgger

O Flasgger gera a documentação interativa a partir das docstrings YAML das rotas. A definição de segurança `Bearer` adiciona o botão *Authorize* na interface. Depois de fazer login em `/api/auth/login`, o desenvolvedor cola o token e testa as rotas protegidas sem Postman.

## 9. Requisitos não funcionais

- **Segurança:** senhas armazenadas com hash, rotas protegidas por JWT e isolamento dos dados por usuário; nenhum segredo no repositório (variáveis de ambiente). Débito conhecido: não há limitação de tentativas no login e no registro.
- **Disponibilidade:** o cache dos índices mantém o sistema funcionando se o BACEN estiver fora do ar. Débito conhecido: com o banco fora do ar, as rotas que o usam respondem 500 genérico (só `/api/saude` responde 503).
- **Manutenibilidade:** cálculo separado das rotas, schema versionado com migrations e API documentada.
- **Testabilidade:** os serviços de cálculo têm testes unitários com referência independente, e a API inteira é coberta por testes de integração contra um PostgreSQL de teste separado.
- **Portabilidade:** a API roda em um contêiner Docker (imagem de produção, usuário sem privilégios, com verificação de saúde).
- **Configuração:** URL do banco, chave JWT, origens permitidas no CORS e parâmetros do BACEN vêm de variáveis de ambiente.

## 10. Resultados esperados

Uma API REST documentada e testável, que autentica usuários, persiste simulações e devolve a comparação entre os três cenários. Ela usa taxas reais do BACEN e calcula Price, SAC e o fundo de acumulação. Qualquer cliente HTTP pode consumi-la, e o frontend React é o primeiro deles.

## 11. Etapas realizadas

O desenvolvimento seguiu etapas, cada uma com spec, plano e validação (ver [`plano.md`](plano.md) e [`docs/specs/`](docs/specs/)):

0. Preparação do repositório e do ambiente.
1. Esqueleto da aplicação Flask com PostgreSQL.
2. Modelagem de dados e migration inicial.
3. Autenticação (registro e login com JWT).
4. CRUD de simulações.
5. CRUD de opções de financiamento.
6. Serviços de cálculo (Price, SAC e fundo) com testes unitários.
7. Tabela de parcelas e endpoint de resultado dos três cenários.
8. Integração com o BACEN, cache e endpoints de índices (CDI e IPCA).
9. *(eliminada por decisão do autor)* Extras de criatividade: paginação, ordenação, filtros e CET.
10. Swagger completo, CORS e testes de integração da API.
11. Dockerfile.
12. README com o fluxograma da arquitetura.
13. Revisão final e entrega.
