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
| 8 | Integração com o BACEN/SGS, cache e endpoints de índices | R7, R8 |
| 9 | Extras: paginação, ordenação, filtros (e CET, opcional) | R4 |
| 10 | Swagger completo e testes de integração | R1, R5 |
| 11 | Dockerfile (e docker-compose, se decidido) | R3 |
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
**Arquivos:** `run.py`, `config.py`, `app/__init__.py`, `app/extensions.py`, `app/routes/__init__.py`

- [ ] `config.py` lendo as variáveis de ambiente (nunca segredos no código).
- [ ] `app/extensions.py` com `db`, `migrate`, `jwt` (instâncias únicas, evitam import circular).
- [ ] Application factory `create_app()` registrando db, migrate, JWT, CORS (só `CORS_ORIGINS`) e Flasgger com a definição de segurança `Bearer`.
- [ ] Um handler global de erros devolvendo JSON (404, 405, 500 etc.).
- [ ] Uma rota mínima (ex.: `GET /api/saude`) documentada no Swagger, para provar o pipeline.
- [ ] `flask db init` gerando `migrations/`.

**Validar:** `flask run` sobe; `/apidocs/` abre com o botão *Authorize*; a rota de saúde responde 200.

## Etapa 2 — Modelagem de dados e migration inicial
**Arquivos:** `app/models/{usuario,simulacao,opcao_financiamento,parcela_calculada,indice_economico_cache}.py`, `app/models/__init__.py`

- [ ] Models conforme a seção 6 da proposta: `usuarios`, `simulacoes`, `opcoes_financiamento`, `parcelas_calculadas`, `indices_economicos_cache`.
- [ ] Dinheiro e taxas em `Numeric`; `sistema_amortizacao` como enum (`PRICE`, `SAC`); `email` único; FKs com `ondelete` definido (excluir simulação remove suas opções).
- [ ] Decidir: `parcelas_calculadas` como tabela de cache ou cálculo sob demanda (a proposta marca como opcional; a recomendação é **sob demanda** no início).
- [ ] `flask db migrate` + revisão manual do arquivo + `flask db upgrade`.

**Validar:** tabelas criadas no Postgres (`\dt`); `flask db downgrade` e `upgrade` funcionam.

## Etapa 3 — Autenticação (registro e login)
**Arquivos:** `app/routes/auth.py`, `app/schemas/auth.py`, `app/services/auth.py` (se necessário)

- [ ] `POST /api/auth/registrar`: valida nome/e-mail/senha, grava só o **hash** da senha, 409 para e-mail duplicado, nunca devolve `senha_hash`.
- [ ] `POST /api/auth/login`: confere a senha e devolve o token JWT; 401 para credencial inválida (mensagem genérica).
- [ ] Callbacks do JWT devolvendo JSON para token ausente, inválido ou expirado (401).
- [ ] Definir a expiração do token.
- [ ] Docstrings Flasgger nas duas rotas.

**Validar:** registrar → login → colar o token no *Authorize* do Swagger; rota protegida de teste responde 200 com token e 401 sem ele.

## Etapa 4 — CRUD de simulações
**Arquivos:** `app/routes/simulacoes.py`, `app/schemas/simulacao.py`

- [ ] `POST /api/simulacoes`, `GET /api/simulacoes`, `GET /api/simulacoes/<id>`, `PUT /api/simulacoes/<id>`, `DELETE /api/simulacoes/<id>`.
- [ ] `usuario_id` sempre vem do token, nunca do corpo da requisição.
- [ ] Simulação de outro usuário responde **404**.
- [ ] Validação de entrada: valores positivos, entrada menor ou igual ao valor do veículo, prazos inteiros positivos, taxas coerentes.
- [ ] Docstrings Flasgger com `security: Bearer`, exemplo de corpo e códigos de resposta.

**Validar:** pelo Swagger, com dois usuários diferentes, confirmar que um não vê nem altera os dados do outro; cobrir os quatro métodos HTTP (R1).

## Etapa 5 — CRUD de opções de financiamento
**Arquivos:** `app/routes/financiamentos.py`, `app/schemas/financiamento.py`

- [ ] `POST|GET /api/simulacoes/<id>/financiamentos` e `PUT|DELETE /api/simulacoes/<id>/financiamentos/<fid>`.
- [ ] Conferir o dono da simulação em toda operação; a opção precisa pertencer à simulação da URL.
- [ ] Regra de negócio: no máximo 3 opções por simulação (a proposta prevê 2 ou 3) — confirmar na spec.
- [ ] `valor_entrada` da opção pode diferir do da simulação.

**Validar:** pelo Swagger, incluindo o caso de `fid` que pertence a outra simulação (deve dar 404).

## Etapa 6 — Serviços de cálculo + testes unitários
**Arquivos:** `app/services/{financiamento,fundo,cenarios}.py`, `tests/services/`

Sem importar Flask; funções puras com `Decimal`.

- [ ] **Preço futuro (IPCA):** `valor_veiculo × (1 + ipca_aa)^(prazo_meses/12)`.
- [ ] **Price:** parcela fixa `PMT = PV·i / (1 − (1+i)^−n)`, com `PV = valor_veiculo − entrada`; tabela mês a mês (parcela, juros, amortização, saldo).
- [ ] **SAC:** amortização constante `PV/n`, juros sobre o saldo, parcelas decrescentes.
- [ ] Custo total do financiamento = entrada + soma das parcelas.
- [ ] **Fundo de acumulação:** taxa mensal `(1+a.a.)^(1/12) − 1`; (a) dado o prazo, calcula o aporte mensal; (b) dado o aporte, calcula em quantos meses atinge o valor à vista corrigido. Série mês a mês do saldo.
- [ ] Definir a convenção de arredondamento (2 casas, `ROUND_HALF_UP`) e onde aplicá-la.
- [ ] Decidir e documentar a tratativa de taxa 0 (evita divisão por zero).
- [ ] Adicionar `pytest` (ou `unittest`) com justificativa, conforme o CLAUDE.md.

**Validar (`pytest`):** soma das amortizações = valor financiado; saldo final = 0; SAC tem parcelas decrescentes e Price tem parcelas iguais; fundo com aporte calculado chega ao valor-alvo; caso com taxa zero.

## Etapa 7 — Tabela de parcelas e endpoint de resultado
**Arquivos:** `app/routes/financiamentos.py`, `app/routes/simulacoes.py`, `app/schemas/resultado.py`

- [ ] `GET /api/simulacoes/<id>/financiamentos/<fid>/parcelas`: devolve a tabela de amortização calculada sob demanda pelo serviço.
- [ ] `GET /api/simulacoes/<id>/resultado`: monta os três cenários (à vista corrigido, financiamentos, fundo) com totais e as **séries mês a mês** para o gráfico (saldo devedor de cada opção, saldo do fundo, custo à vista corrigido).
- [ ] Definir o formato exato do JSON e registrá-lo no Swagger — é o contrato com o frontend.
- [ ] Tratar simulação sem opções de financiamento (devolver os cenários possíveis, sem erro).

**Validar:** simulação de exemplo no Swagger, com os números conferidos à mão ou em planilha.

## Etapa 8 — Integração com o BACEN/SGS, cache e índices
**Arquivos:** `app/integrations/bacen.py`, `app/services/indices.py`, `app/routes/indices.py`

- [ ] Cliente `requests` para `https://api.bcb.gov.br/dados/serie/bcdata.sgs.<n>/dados?formato=json`, com timeout e tratamento de erro. Confirmar os códigos das séries de Selic, CDI e IPCA na documentação do SGS.
- [ ] Gravar em `indices_economicos_cache` e servir por `GET /api/indices/{selic|ipca|cdi}?periodo=...`.
- [ ] Definir a política de expiração do cache (ex.: consulta o BACEN só se o dado estiver defasado).
- [ ] BACEN fora do ar: servir o cache; sem cache, devolver 502/503 com mensagem clara.
- [ ] Os índices são taxas **sugeridas**: o cliente pode enviar outros valores ao criar a simulação.
- [ ] Opcional: atualização agendada com APScheduler.

**Validar:** chamar o endpoint com rede ativa (grava no cache); repetir (serve do cache); simular falha do BACEN (URL inválida) e conferir a resposta.

## Etapa 9 — Extras de criatividade (R4)
**Arquivos:** `app/routes/simulacoes.py`, `app/schemas/`, possivelmente `app/services/cet.py`

- [ ] Paginação em `GET /api/simulacoes` (`pagina`, `por_pagina`) com metadados na resposta.
- [ ] Ordenação (`ordenar_por`, `ordem`) e filtros (ex.: por nome, faixa de valor).
- [ ] Opcional: cálculo do CET (Custo Efetivo Total) por opção de financiamento.
- [ ] Documentar todos os parâmetros no Swagger.

**Validar:** requisições com várias combinações de parâmetros; limites e valores inválidos devolvem 400/422.

## Etapa 10 — Swagger completo e testes de integração
**Arquivos:** todas as rotas, `tests/api/`

- [ ] Revisar as docstrings Flasgger de **todas** as rotas: parâmetros, corpos de exemplo, respostas de erro, `security`.
- [ ] Testes de integração com o `test_client` do Flask e banco de teste separado: fluxo registrar → login → criar simulação → adicionar financiamentos → resultado; isolamento entre usuários; erros 401/404/409.
- [ ] Conferir a política de CORS com a origem do frontend.

**Validar:** `pytest` completo verde; percorrer `/apidocs/` executando cada rota.

## Etapa 11 — Dockerfile (R3)
**Arquivos:** `Dockerfile`, `.dockerignore`, `docker-compose.yml` (se decidido)

- [ ] `Dockerfile` do backend: imagem Python slim, instala `requirements.txt`, roda com `gunicorn`, expõe a porta e lê a configuração por variáveis de ambiente.
- [ ] Se for usar compose: serviços `api` + `db` (Postgres) com volume e `depends_on`.
- [ ] Definir como as migrations rodam no container (`flask db upgrade` no start).

**Validar:** `docker build` e `docker run` (ou `docker compose up`) sobem a API; `/apidocs/` abre; um fluxo completo funciona no container.

## Etapa 12 — README com fluxograma (R2 e R8)
**Arquivos:** `README.md`, `docs/img/arquitetura.png` (ou `.svg`)

- [ ] Reescrever o README (o atual é do projeto `manutencao-api`): título, descrição, instalação local, variáveis de ambiente, migrations, execução, execução com Docker.
- [ ] **Fluxograma da arquitetura** em imagem, ilustrando um cenário (ex.: Frontend → API Flask → PostgreSQL / BACEN).
- [ ] Seção da **API externa** (R8): BACEN/SGS, licença, ausência de cadastro e rotas usadas.
- [ ] Tabela das rotas da API e link para `/apidocs/`.

**Validar:** seguir o README do zero em uma pasta limpa e conseguir subir a aplicação.

## Etapa 13 — Revisão final e entrega (R10)
- [ ] Conferir o checklist R1 a R10 do `CLAUDE.md` e atualizar a lista.
- [ ] Nomes de arquivos em `snake_case`, estrutura de pastas conforme a proposta, sem código morto.
- [ ] Nenhum segredo commitado; `.env.example` atualizado.
- [ ] Remover do `requirements.txt` o que não for usado; atualizar o `CLAUDE.md` com o estado final.
- [ ] Publicar no repositório público do GitHub e conferir o link.

---

## Riscos e pontos de atenção
- **Precisão financeira:** usar `Decimal` de ponta a ponta; conferir os resultados contra uma planilha.
- **Contrato com o frontend:** definir o JSON de `/resultado` na etapa 7 e evitar mudanças depois; qualquer mudança precisa ser avisada ao outro módulo.
- **Dependência do BACEN:** os cálculos não podem depender dele em tempo de requisição; só as sugestões de taxa dependem.
- **R7:** o enunciado cita BrasilAPI/FIPE, mas o projeto decidiu atender com o BACEN/SGS — confirmar isso com o professor antes da entrega.

## Decisões em aberto (resolver nas specs)
- `parcelas_calculadas` como cache ou sob demanda (etapa 2).
- Limite de opções por simulação e expiração do JWT (etapas 3 e 5).
- Convenção de arredondamento e caso de taxa zero (etapa 6).
- Política de expiração do cache do BACEN (etapa 8).
- Escopo de paginação, ordenação e filtros; se o CET entra (etapa 9).
- Dockerfile isolado ou docker-compose com Postgres (etapa 11).
