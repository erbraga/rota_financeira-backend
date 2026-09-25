# Proposta – Parte 1: Backend (API REST)

**Projeto:** Comparador de Cenários para Compra de Carros
**Parte:** Backend, API REST em Flask + PostgreSQL
**Parte complementar:** [Frontend (SPA React)](proposta-frontend-spa-react.md)

## 1. Contexto do projeto

O projeto é uma aplicação web que ajuda o usuário a decidir **como comprar um carro**. Ela compara três cenários financeiros com dados econômicos reais do Banco Central:

1. Compra à vista.
2. Compra financiada, com 2 ou 3 opções de financiamento.
3. Compra à vista no futuro, acumulando o valor em um fundo de investimento.

Quem vai comprar um carro costuma comparar só o valor da parcela. Ele deixa de considerar o custo total dos juros, a alta do preço do carro (inflação) enquanto junta dinheiro e o rendimento do dinheiro guardado. A aplicação reúne esses cálculos em um só lugar e usa taxas reais (Selic, CDI e IPCA) de uma fonte oficial.

### 1.1 Decisão de arquitetura

O sistema é implementado em **duas partes independentes**, que se comunicam apenas por HTTP/JSON:

| Parte | Responsabilidade | Documento |
|---|---|---|
| **Backend (este documento)** | Regras de negócio, cálculos financeiros, persistência, autenticação, integração com o BACEN | `proposta-backend-api-rest.md` |
| **Frontend** | Interface do usuário (SPA), formulários, gráficos e consumo da API | `proposta-frontend-spa-react.md` |

O backend não conhece o frontend e pode ser testado, documentado e evoluído sozinho, pelo Swagger. O **contrato entre as duas partes é a especificação OpenAPI** gerada pelo Flasgger, com os endpoints da seção 7.

## 2. Objetivos do backend

- Expor uma API REST completa para autenticação, simulações, opções de financiamento e índices econômicos.
- Implementar o cálculo de financiamento pelos sistemas **Price** e **SAC**, com tabela de amortização mês a mês.
- Projetar o preço futuro do veículo com correção pelo **IPCA**.
- Simular o fundo de acumulação com aportes mensais e rendimento (CDI, Selic ou taxa informada).
- Integrar a API SGS do Banco Central e manter um cache local dos índices.
- Persistir simulações por usuário e permitir revisitá-las.
- Documentar e permitir testar a API com Swagger (Flasgger).

## 3. Escopo

### 3.1 Incluído

- Cadastro e login de usuários (JWT).
- CRUD de simulações e das opções de financiamento de cada uma.
- Parâmetros personalizáveis: valor do veículo, entrada, taxa de juros, prazo, sistema de amortização, taxa do fundo e prazo para acumulação.
- Cálculo dos três cenários e endpoint de resultado comparativo.
- Endpoints de índices econômicos (Selic, CDI, IPCA) com cache.
- Documentação interativa da API.

### 3.2 Opcional, se houver tempo

- 
- Cálculo do CET (Custo Efetivo Total).
- 

## 4. Lógica de cálculo

A lógica de negócio fica na camada de **serviços**, separada das rotas HTTP.

| Cenário | Cálculo |
|---|---|
| **À vista (corrigido)** | `valor_veiculo × (1 + taxa_ipca)^(prazo_meses/12)`: preço do carro no momento em que o fundo completaria o valor. |
| **Financiamento** | **Price:** parcelas fixas. **SAC:** amortização constante e parcelas decrescentes. Gera a tabela mês a mês com parcela, juros, amortização e saldo devedor, e o custo total (entrada + soma das parcelas). |
| **Fundo de acumulação** | Aportes mensais fixos rendendo à taxa do fundo. Dado o prazo, calcula quanto aportar por mês. Dado o aporte, calcula quanto tempo leva para atingir o valor à vista corrigido. |

## 5. Integração com API pública

- **Banco Central (SGS):** API REST gratuita, sem autenticação, com séries temporais. O exemplo é o CDI (série 12):

  ```
  https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados?formato=json
  ```

- O backend consulta a API, grava o resultado na tabela `indices_economicos_cache` e serve o cliente por endpoints internos. Assim a aplicação não depende da disponibilidade do BACEN a cada acesso.
- Os valores retornados são taxas **sugeridas**. O cliente pode enviar valores diferentes ao criar a simulação.

## 6. Modelagem de dados (PostgreSQL)

### usuarios

| Campo | Tipo | Observação |
|---|---|---|
| id | UUID/serial | PK |
| nome | varchar | |
| email | varchar | único |
| senha_hash | varchar | |
| criado_em | timestamp | |

### simulacoes

| Campo | Tipo | Observação |
|---|---|---|
| id | UUID/serial | PK |
| usuario_id | FK → usuarios | |
| nome | varchar | ex.: "Onix 2026" |
| valor_veiculo | decimal | preço à vista informado ou obtido da FIPE |
| valor_entrada | decimal | |
| taxa_ipca_projetada | decimal | % a.a. para corrigir o preço do carro (pode vir do BACEN) |
| taxa_fundo_rendimento | decimal | % a.a. usada no cenário de acumulação (CDI, poupança) |
| prazo_meses_fundo | int | prazo desejado para juntar o valor à vista |
| criado_em | timestamp | |

### opcoes_financiamento

Cada simulação tem 2 ou 3 opções.

| Campo | Tipo | Observação |
|---|---|---|
| id | UUID/serial | PK |
| simulacao_id | FK → simulacoes | |
| nome | varchar | ex.: "Banco X 48x" |
| taxa_juros_mensal | decimal | |
| prazo_meses | int | |
| sistema_amortizacao | enum | `PRICE` ou `SAC` |
| valor_entrada | decimal | pode diferir da entrada do cenário à vista |

### parcelas_calculadas

Opcional: cache do resultado, ou cálculo sob demanda.

| Campo | Tipo | Observação |
|---|---|---|
| id | UUID/serial | PK |
| opcao_financiamento_id | FK | |
| numero_parcela | int | |
| valor_parcela | decimal | |
| valor_juros | decimal | |
| valor_amortizacao | decimal | |
| saldo_devedor | decimal | |

### indices_economicos_cache

| Campo | Tipo | Observação |
|---|---|---|
| id | serial | PK |
| indice | varchar | `SELIC`, `CDI` ou `IPCA` |
| data_referencia | date | |
| valor | decimal | |
| atualizado_em | timestamp | |

## 7. Endpoints da API REST

Todas as rotas ficam sob `/api`. Com exceção de `registrar` e `login`, exigem o cabeçalho `Authorization: Bearer <token>`. Cada usuário só acessa as próprias simulações.

### 7.1 Autenticação

```
POST /api/auth/registrar
POST /api/auth/login
```

### 7.2 Simulações

```
POST   /api/simulacoes                  # cria simulação
GET    /api/simulacoes                  # lista simulações do usuário logado
GET    /api/simulacoes/:id              # detalhe da simulação
PUT    /api/simulacoes/:id              # atualiza parâmetros
DELETE /api/simulacoes/:id              # remove
GET    /api/simulacoes/:id/resultado    # três cenários calculados
```

### 7.3 Opções de financiamento

```
POST   /api/simulacoes/:id/financiamentos                  # adiciona opção
GET    /api/simulacoes/:id/financiamentos                  # lista opções
PUT    /api/simulacoes/:id/financiamentos/:fid             # edita
DELETE /api/simulacoes/:id/financiamentos/:fid             # remove
GET    /api/simulacoes/:id/financiamentos/:fid/parcelas    # tabela de amortização
```

### 7.4 Índices econômicos (proxy com cache do BACEN)

```
GET /api/indices/selic?periodo=...
GET /api/indices/ipca?periodo=...
GET /api/indices/cdi?periodo=...
```

### 7.5 Documentação e contrato

A resposta de `GET /api/simulacoes/:id/resultado` deve trazer, além dos totais de cada cenário, as **séries mês a mês** que alimentam o gráfico comparativo (saldo devedor, saldo do fundo e custo à vista corrigido). Assim o frontend só exibe os dados e não recalcula nada. O formato exato é definido na especificação OpenAPI e é o que o frontend segue.

## 8. Arquitetura e tecnologias

| Item | Tecnologia |
|---|---|
| Framework | Flask |
| ORM e migrations | Flask-SQLAlchemy, Flask-Migrate (Alembic) |
| Banco de dados | PostgreSQL |
| Autenticação | Flask-JWT-Extended |
| Validação e serialização | Marshmallow ou Pydantic |
| Cliente HTTP (BACEN) | requests |
| CORS | Flask-CORS, liberando a origem do frontend (ex.: `localhost:5173` ou `3000` em desenvolvimento) |
| Documentação e testes manuais | **Flasgger** (Swagger UI em `/apidocs/`) |
| Agendamento (opcional) | APScheduler |

### 8.1 Estrutura de pastas

```
backend/
  app/
    models/          # Usuario, Simulacao, OpcaoFinanciamento...
    routes/          # blueprints: auth, simulacoes, financiamentos, indices
    services/        # cálculo Price, SAC e fundo
    schemas/         # validação e serialização
    integrations/    # cliente da API do BACEN
  migrations/
  config.py
  run.py
```

### 8.2 Documentação com Flasgger

O Flasgger gera a documentação interativa a partir das docstrings YAML das rotas. A definição de segurança `Bearer` adiciona o botão *Authorize* na interface. Depois de fazer login em `/api/auth/login`, o desenvolvedor cola o token e testa as rotas protegidas sem Postman.

## 9. Requisitos não funcionais

- **Segurança:** senhas armazenadas com hash, rotas protegidas por JWT e isolamento dos dados por usuário.
- **Disponibilidade:** o cache dos índices mantém o sistema funcionando se o BACEN estiver fora do ar.
- **Manutenibilidade:** cálculo separado das rotas, schema versionado com migrations e API documentada.
- **Testabilidade:** os serviços de cálculo têm testes unitários e a API pode ser exercitada de forma independente pelo Swagger.
- **Configuração:** URL do banco, chave JWT e origens permitidas no CORS vêm de variáveis de ambiente.

## 10. Resultados esperados

Uma API REST documentada e testável, que autentica usuários, persiste simulações e devolve a comparação entre os três cenários. Ela usa taxas reais do BACEN e calcula Price, SAC e o fundo de acumulação. Qualquer cliente HTTP pode consumi-la, e o frontend React é o primeiro deles.

## 11. Etapas de desenvolvimento (sugestão)

Este cronograma é uma sugestão. Ajuste os prazos ao seu calendário.

1. Configuração do projeto (Flask, Postgres, migrations) e modelagem do banco.
2. Autenticação (registro e login com JWT).
3. CRUD de simulações e opções de financiamento.
4. Serviços de cálculo (Price, SAC, fundo) com testes unitários.
5. Integração com o BACEN, cache de índices e endpoint de resultado.
6. Documentação Swagger completa, CORS e testes de integração.