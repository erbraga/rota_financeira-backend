# Tabela de parcelas e resultado comparativo (Etapa 7) — Spec

**Criado em:** 2026-09-25
**Status:** Implementada em 2026-09-25
**Origem:** Etapa 7 de `plano.md`; seções 4, 7.2, 7.3 e 7.5 de `proposta-backend-api-rest.md`; seções 4.2 e 5 de `proposta-frontend-spa-react.md`

## Problema
O usuário já cadastra simulações (Etapa 4) e opções de financiamento (Etapa 5), e os
blocos de cálculo existem e estão testados (Etapa 6), mas **nada os expõe**: não há
tabela de amortização nem a comparação dos três cenários, que é a razão de ser do
produto. Estado verificado:

- **Rotas:** existem `GET|POST /api/simulacoes[/<id>]`, `PUT|DELETE /api/simulacoes/<id>`
  e as 4 rotas de `/financiamentos`. **Não existem** `GET .../financiamentos/<fid>/parcelas`
  nem `GET .../resultado` (a URL `.../financiamentos/<fid>` só responde a `PUT` e
  `DELETE`, então um `GET` em `.../parcelas` hoje dá 404).
- **Cálculo pronto** (`app/services/calculo/`, puro, `Decimal`): `preco_corrigido`,
  `serie_preco_corrigido`, `tabela_price`, `tabela_sac`, `custo_total_financiamento`,
  `aporte_para_meta`, `serie_fundo` e `meses_para_meta`. **Falta a composição** dos
  cenários (`cenarios`), deixada para esta etapa (decisão 6 da Etapa 6).
- **Dados:** a simulação guarda `valor_veiculo`, `valor_entrada` (**capital inicial do
  fundo**, decisão 4 da Etapa 6), `taxa_ipca_projetada`, `taxa_fundo_rendimento` e
  `prazo_meses_fundo`; cada opção guarda `taxa_juros_mensal`, `prazo_meses`,
  `sistema_amortizacao` e o **próprio** `valor_entrada` (o valor financiado é
  `valor_veiculo − entrada da opção`, sempre > 0). No máximo 3 opções, prazo de até 72
  meses, fundo de até 60 meses.
- **Frontend** (`proposta-frontend-spa-react.md`): a tela de resultado tem
  **cartões-resumo** ("custo total de cada cenário, com destaque para o mais barato"),
  um **gráfico de linhas** ("saldo devedor de cada financiamento, saldo acumulado do
  fundo e valor do carro corrigido pelo IPCA ao longo dos meses", com Recharts ou
  Chart.js) e a **tabela de amortização**; e o contrato diz que o backend devolve os
  totais e as **séries mês a mês** e que **"o frontend apenas as exibe"** (não
  recalcula nada).
- **Números de referência** (cálculo pelos blocos da Etapa 6; simulação de 95.000, IPCA
  4,5% a.a., fundo 10,5% a.a., 36 meses, entrada 20.000; opção A Price 1,99% a.m. em 48
  meses com entrada 20.000; opção B SAC 1,5% a.m. em 60 meses com entrada 30.000):
  - à vista hoje: **95.000,00**; preço em 36 meses (meta): **108.410,78**;
  - fundo: aporte **1.948,07**, saldo final 108.410,97, rendimento 18.280,45,
    dinheiro que sai do bolso (capital + aportes) **90.130,52**;
  - Price 48x: 1ª parcela 2.440,16, última 2.440,55, juros 42.128,07, total pago
    117.128,07, **custo total (entrada + parcelas) 137.128,07**;
  - SAC 60x: 1ª parcela 2.058,33, última 1.099,78, juros 29.737,50, total pago 94.737,50,
    **custo total 124.737,50**;
  - modo "dado o aporte": com 1.500,00/mês a meta é alcançada no **mês 46** (mais que os
    36 do prazo da simulação); com 300,00/mês **não é alcançada** em 60 meses.
- **O que esses números mostram (e que a spec precisa decidir):** o "custo" do fundo
  medido pelo dinheiro que sai do bolso (90.130,52) fica **abaixo** do à vista de hoje
  (95.000,00), embora o carro só seja comprado em 36 meses **por 108.410,78**. Comparar
  totais nominais de cenários com datas diferentes engana (decisão 1).

## Objetivo
Expor `GET .../financiamentos/<fid>/parcelas` e `GET .../resultado`, montando os três
cenários e as séries mês a mês a partir dos dados do usuário, com um contrato JSON
claro — que o frontend só exibe — documentado no Swagger, com isolamento por usuário.

## Fora de escopo
- Índices do BACEN e sugestão de taxas (Etapa 8); o `/resultado` usa as taxas gravadas
  na simulação.
- Paginação, filtros, ordenação por parâmetro (Etapa 9) e o CET (opcional, Etapa 9).
- Descontar os fluxos a valor presente ou qualquer indicador financeiro além dos totais
  nominais (a comparação é explicada, não "corrigida"; ver decisão 1).
- Salvar resultados no banco, cache ou recálculo em segundo plano: tudo é calculado sob
  demanda, a cada requisição (no máximo 3 × 72 linhas de amortização + 60 pontos do fundo).
- Impostos e taxas do fundo, IOF, tarifas e seguros (já fora de escopo na Etapa 6).
- Alteração de schema ou dependência nova: `requirements.txt` não muda.
- O código do frontend.

## Proposta

### Endpoints (protegidos por JWT; só leitura)

| Método e rota | Resposta de sucesso |
|---|---|
| `GET /api/simulacoes/<id>/financiamentos/<fid>/parcelas` | `200` com a tabela de amortização da opção (decisão 5) |
| `GET /api/simulacoes/<id>/resultado` | `200` com os três cenários e as séries (decisões 1 a 4) |
| `GET /api/simulacoes/<id>/resultado?aporte_mensal=1500` | `200` no modo "dado o aporte" (decisão 4) |

Erros (formato `{"erro": ..., "detalhes": ...}`): 401 (token); 404 "Simulação não
encontrada" (inexistente **ou de outro usuário**, mesma resposta); 404 "Opção de
financiamento não encontrada" (`fid` inexistente ou de outra simulação, só depois de a
simulação ser confirmada como sua); 404 para ids não numéricos ou acima do `INTEGER`;
422 com `detalhes.aporte_mensal` se o parâmetro for inválido. Nenhum `POST`/corpo: sem
400/415.

### Arquivos
```
app/
  services/calculo/cenarios.py   # composição PURA (só stdlib e o pacote calculo)
  services/resultados.py         # adaptador: ORM (simulação, opções) → entradas de cenarios
  schemas/resultado.py           # saídas (parcelas e resultado) e o parâmetro de consulta
  routes/financiamentos.py       # + GET .../parcelas
  routes/simulacoes.py           # + GET .../resultado
app/__init__.py                  # SWAGGER_TEMPLATE: schemas do resultado e das parcelas
tests/calculo/test_cenarios.py   # pytest da composição (referência independente)
```
Sem migration e sem dependência nova. `cenarios.py` continua **puro** (o teste de pureza
da Etapa 6 cobre o novo arquivo); a leitura do banco e a conversão de tipos ficam em
`services/resultados.py`, que reaproveita `obter_simulacao` e `obter_opcao` (404
uniforme) e converte os valores do banco (já `Decimal`) sem passar por `float`.

### Contrato de `/resultado` (com as recomendações das decisões aplicadas)
```json
{
  "simulacao": {"id": 3, "nome": "Onix 2026", "valor_veiculo": 95000.0,
                "valor_entrada": 20000.0, "taxa_ipca_projetada": 4.5,
                "taxa_fundo_rendimento": 10.5, "prazo_meses_fundo": 36},
  "cenarios": {
    "a_vista": {"custo_total": 95000.0},
    "financiamentos": [
      {"id": 4, "nome": "Banco X 48x", "sistema_amortizacao": "PRICE",
       "valor_financiado": 75000.0, "valor_entrada": 20000.0, "prazo_meses": 48,
       "primeira_parcela": 2440.16, "ultima_parcela": 2440.55,
       "total_pago": 117128.07, "total_juros": 42128.07, "custo_total": 137128.07}
    ],
    "fundo": {"capital_inicial": 20000.0, "aporte_mensal": 1948.07, "prazo_meses": 36,
              "preco_na_compra": 108410.78, "total_aportado": 70130.52,
              "rendimento": 18280.45, "saldo_final": 108410.97,
              "custo_total": 108410.78, "alcanca_a_meta": true}
  },
  "menor_custo": {"cenario": "a_vista", "id": null},
  "series": [
    {"mes": 0, "preco_corrigido": 95000.0, "saldo_fundo": 20000.0, "saldo_devedor": {"4": 75000.0}},
    {"mes": 1, "preco_corrigido": 95350.0, "saldo_fundo": 22141.0, "saldo_devedor": {"4": 73052.0}}
  ]
}
```
(os valores de `series` são ilustrativos; `menor_custo`, `custo_total` do fundo e o
formato das séries dependem das decisões 1 a 3.)

**Contrato de `/parcelas`** (decisão 5):
```json
{"financiamento": {"id": 4, "nome": "Banco X 48x", "sistema_amortizacao": "PRICE",
                   "valor_financiado": 75000.0, "valor_entrada": 20000.0,
                   "taxa_juros_mensal": 1.99, "prazo_meses": 48},
 "parcelas": [{"numero": 1, "valor_parcela": 2440.16, "juros": 1492.5,
               "amortizacao": 947.66, "saldo_devedor": 74052.34}],
 "totais": {"total_pago": 117128.07, "total_juros": 42128.07, "custo_total": 137128.07}}
```

### Regras
- **Meta do fundo:** `preco_corrigido(valor_veiculo, ipca, prazo_meses_fundo)`; capital
  inicial = `valor_entrada` da simulação; aporte pelo `aporte_para_meta` (arredondado
  para cima; 0,00 se o capital já bastar).
- **Financiamento de cada opção:** valor financiado = `valor_veiculo − valor_entrada da
  opção`; Price ou SAC conforme o `sistema_amortizacao`; custo total = entrada da opção +
  soma das parcelas. A entrada da **simulação** não entra no financiamento (cada opção
  tem a sua).
- **Séries:** eixo comum de mês 0 ao maior prazo envolvido (decisão 3); `preco_corrigido`
  em todo o eixo; `saldo_fundo` até a compra; `saldo_devedor` por opção até a quitação;
  fora do alcance de cada série o valor é `null` (decisão 3).
- **0 a 3 opções:** sem opções, `financiamentos` é lista vazia e nada de `saldo_devedor`;
  o resultado continua válido com os cenários possíveis (à vista e fundo).
- **Números:** valores em reais e taxas como **número JSON** (decisão 1 da Etapa 4);
  conversão só na saída, a partir de `Decimal`; datas/ids como nos demais recursos.
- **Isolamento e ordem de verificação:** dono da simulação (404 uniforme) → opção (só no
  `/parcelas`) → parâmetros (422). Sem bloqueio de linha (só leitura).
- **Cálculo sob demanda:** nada é gravado; a resposta é sempre coerente com o estado
  atual da simulação e das opções.

### Documentação (OpenAPI 3)
Docstrings Flasgger nas 2 rotas (modelo: `app/routes/financiamentos.py`), com
`security: BearerAuth`, todos os campos descritos, exemplos com os números da seção
Problema e as respostas de erro (`$ref` para `Erro`). O Swagger **explica**: (1) a
última parcela pode diferir por centavos (e, com juros muito altos, bem mais) porque
absorve o resíduo; (2) parcelas depois de uma quitação antecipada por arredondamento
saem 0,00; (3) o significado de "custo total" de cada cenário e do destaque (decisão 1);
(4) a série do fundo termina na compra e o preço corrigido segue no eixo; (5) o modo
"dado o aporte". Schemas novos em `SWAGGER_TEMPLATE`.

### Fluxo principal
1. Login → **Authorize** → criar simulação e 2 opções (Etapas 4 e 5).
2. `GET .../financiamentos/<fid>/parcelas` → tabela da opção.
3. `GET .../resultado` → cenários, menor custo e séries; o frontend desenha cartões,
   gráfico e tabela sem recalcular nada.
4. `GET .../resultado?aporte_mensal=1500` → em que mês o fundo alcança a meta.

### Casos de borda
- **Simulação sem opções:** `financiamentos: []`, séries só com preço corrigido e fundo;
  `menor_custo` entre os cenários que existem.
- **Capital inicial que já cobre a meta:** aporte 0,00 e custo do fundo = capital.
- **Opção com prazo maior que o do fundo (ou o contrário):** o eixo vai até o maior
  prazo; as séries mais curtas terminam em `null`.
- **`aporte_mensal` no modo aporte:** 0,00 com capital menor que a meta → não alcança
  (`alcanca_a_meta: false`, sem erro); acima de 9.999.999,00, com mais de 2 casas ou
  não numérico → 422 em `detalhes.aporte_mensal`.
- **Taxa de juros 0 e valores de centavos:** já cobertos pelos blocos da Etapa 6
  (quitação antecipada por arredondamento gera parcelas 0,00).
- **Opção alheia / simulação alheia / ids gigantes:** 404 uniforme, como nas outras rotas.
- **Simulação alterada entre duas chamadas:** cada chamada reflete o estado atual (não há
  cache).
- **Desempenho:** pior caso (3 tabelas de 72 meses + fundo de 60) ≈ dezenas de
  milissegundos; a resposta tem no máximo ~200 pontos por série.
- **Banco fora do ar:** 500 genérico (débito já registrado).

## Decisões tomadas
1. ~~**O que é "custo total" de cada cenário e como destacar o mais barato**~~ —
   **RESOLVIDA (2026-09-25): (a)** `custo_total` é **o que se paga pelo carro**: à vista =
   `valor_veiculo`; financiamento = entrada da opção + soma das parcelas; fundo = **preço
   corrigido na compra** (ex.: 108.410,78). No fundo, `capital_inicial`, `total_aportado`
   e `rendimento` vêm só como informação. O backend indica `menor_custo`
   (`{"cenario", "id"}`) pelo menor `custo_total`, para o frontend apenas destacar o
   cartão. A comparação é **nominal** (sem valor presente), dito no Swagger.
2. ~~**Formato das séries**~~ — **RESOLVIDA (2026-09-25): (a)** **lista de pontos por
   mês** (`{"mes", "preco_corrigido", "saldo_fundo", "saldo_devedor": {"<id da opção>":
   valor}}`), o formato que Recharts e Chart.js consomem direto; o frontend não junta
   nada. A chave de `saldo_devedor` é o `id` da opção (ligado ao nome por
   `cenarios.financiamentos`).
3. ~~**Eixo do tempo e fim de cada série**~~ — **RESOLVIDA (2026-09-25): (a)** **eixo
   comum** do mês 0 ao maior prazo envolvido; `preco_corrigido` em todo o eixo; onde uma
   série terminou o valor é **`null`** (o fundo termina na compra; o saldo devedor
   termina na quitação, com 0,00 no último mês da opção e `null` depois). Sem
   preenchimento com o último valor.
4. ~~**Modo "dado o aporte" (`?aporte_mensal=`)**~~ — **RESOLVIDA (2026-09-25): (a)** o
   aporte informado **substitui** o calculado: o fundo usa esse aporte, o bloco do fundo
   traz `mes_da_meta` (mês em que o saldo alcança o preço corrigido **daquele mês**, ou
   `null`) e `alcanca_a_meta`, o horizonte é **60 meses**, o `prazo_meses_fundo` da
   simulação **deixa de ser usado**, o `custo_total` do fundo é o preço corrigido no
   `mes_da_meta` (ou `null`, e então o fundo fica fora do `menor_custo`) e a série do
   fundo vai até esse mês (ou até 60). Sem o parâmetro, `mes_da_meta` é o próprio
   prazo da simulação. Parâmetro validado (0 a 9.999.999,00, até 2 casas), 422 em
   português.
5. ~~**Corpo do `/parcelas`**~~ — **RESOLVIDA (2026-09-25): (a)** **documento
   completo**: `financiamento` (resumo da opção, incluindo `valor_financiado`), `parcelas`
   (`numero`, `valor_parcela`, `juros`, `amortizacao`, `saldo_devedor` após o pagamento,
   sem linha do mês 0) e `totais` (`total_pago`, `total_juros`, `custo_total`), para a
   tela de amortização não precisar de outra chamada nem de somas no frontend.

## Critérios de aceite
- [x] `GET .../parcelas` devolve o documento da decisão 5; para o exemplo do Problema a
      opção A tem 48 linhas, 1ª parcela 2.440,16 / juros 1.492,50 / amortização 947,66 /
      saldo 74.052,34, última parcela 2.440,55, `total_pago` 117.128,07, `custo_total`
      137.128,07; a opção B (SAC) tem 60 linhas, 1ª parcela 2.058,33 e última 1.099,78.
- [x] `GET .../resultado` devolve à vista 95.000,00; fundo com meta 108.410,78, aporte
      1.948,07 e `alcanca_a_meta` verdadeiro; os totais dos dois financiamentos; e
      `menor_custo` conforme a decisão 1 — todos conferidos com o cálculo independente
      (testes) e à mão/planilha.
- [x] Séries: eixo de 0 ao maior prazo (60 no exemplo); `preco_corrigido` em todos os
      pontos (95.000,00 no mês 0; 108.410,78 no mês 36); fundo do mês 0 (20.000,00) ao 36
      e `null` depois; `saldo_devedor` de cada opção começando no valor financiado e
      terminando em 0,00 no último mês da opção, `null` depois; nenhuma série mais
      longa que o eixo.
- [x] `?aporte_mensal=1500` → `mes_da_meta` 46; `?aporte_mensal=300` → `mes_da_meta`
      `null` e `alcanca_a_meta` falso; `?aporte_mensal=` inválido (texto, negativo, acima
      do teto, 3 casas) → 422 em `detalhes.aporte_mensal` em português, sem 500.
- [x] Simulação sem opções → 200 com `financiamentos: []` e sem `saldo_devedor`; com
      capital que já cobre a meta → aporte 0,00 sem erro; com opção de prazo maior que o
      do fundo → eixo até o maior prazo.
- [x] Isolamento: outro usuário recebe 404 "Simulação não encontrada" (idêntico ao de
      inexistente) nas 2 rotas; `fid` de outra simulação do próprio usuário → 404
      "Opção de financiamento não encontrada"; ids `abc`, `-1`, `99999999999` → 404
      (nunca 500).
- [x] Sem token / token inválido / expirado → 401 `{"erro": ...}` nas 2 rotas.
- [x] Números como número JSON; nenhuma conversão por `float` no cálculo (valores vêm
      de `Decimal`); resposta em menos de 100 ms no pior caso.
- [x] `tests/calculo/test_cenarios.py` (pytest) cobre a composição com referência
      independente; a suíte inteira continua verde; `cenarios.py` só importa a
      biblioteca padrão e o pacote `calculo`.
- [x] Swagger UI: as 2 rotas aparecem com exemplos e explicações (última parcela,
      quitação antecipada, "custo total", séries, modo aporte); **Authorize** com só o
      token e as chamadas funcionando (verificação manual, no navegador).
- [x] `flask db migrate` sem mudanças; `requirements.txt` inalterado; sem segredo em
      arquivo versionável; `plano.md` e `CLAUDE.md` atualizados (contrato, definição de
      custo, eixo, modo aporte, contrato com o frontend).

---
*Depois de aprovada, esta spec vira a base do PLANO — não escrever
código antes disso.*

## Plano de Implementação

Tarefas na ordem de execução. Nenhuma faz `git add`/`commit`/`push` (só quando você
pedir). Pré-requisitos: `.venv` ativo, raiz do projeto como diretório de trabalho e, para
as tarefas 3 em diante, o banco no ar (`docker start rota-financeira-db`). A composição
(`cenarios`) é código **puro** e é validada só com `pytest` (sem banco); o adaptador, as
rotas e o contrato são validados por scripts descartáveis (no diretório temporário da
sessão), requisições HTTP reais contra o servidor (`requests`) e o Swagger UI (verificação
manual sua). Os scripts descartáveis e o `pytest` das etapas anteriores são reexecutados
como **regressão**.

Detalhes de projeto que o plano fixa (não estavam explícitos na spec):
- **Bloco do fundo:** `prazo_meses` é o número de meses **simulados** (o prazo da
  simulação no modo normal; o mês da meta, ou 60, no modo aporte). Se a meta **não** é
  alcançada em 60 meses: `mes_da_meta`, `preco_na_compra` e `custo_total` são `null`,
  `alcanca_a_meta` é falso e `saldo_final`, `total_aportado` e `rendimento` são os do
  fim do horizonte (mês 60).
- **Desempate do `menor_custo`:** menor `custo_total`; em empate vale a ordem à vista,
  financiamentos (na ordem de criação) e fundo, o que torna a resposta determinística.
- **Chave de `saldo_devedor`:** o `id` da opção **como texto** (chaves JSON são sempre
  texto). No mês 0 vale o `valor_financiado`; do mês 1 ao prazo, o saldo após a parcela;
  depois do prazo, `null`.
- **Parâmetro desconhecido na URL** (`?x=1`) é recusado como campo desconhecido (422),
  como no corpo das requisições; `?aporte_mensal=` vazio ou repetido também dá 422.
- **`valor_financiado` e as taxas** vêm sempre do estado **atual** do banco (nada é
  guardado); as rotas são só de leitura e **não** bloqueiam linhas.
- **Nenhum `float` no caminho do cálculo:** os `Decimal` do banco entram direto; a
  conversão para número JSON acontece só na saída (schemas), como nas etapas 4 e 5.
- Todos os usuários, simulações e opções de teste são removidos; o banco termina com as
  4 tabelas vazias.

### Tarefa 1 — Composição: opção de financiamento (`cenarios`, parte 1)
- **Arquivos:** `app/services/calculo/cenarios.py`, `tests/calculo/test_cenarios.py`
- **Mudança:** dataclasses de entrada (`EntradaSimulacao`, `EntradaOpcao`) e de saída, e
  `financiamento_da_opcao(valor_veiculo, opcao)`: valor financiado (veículo − entrada da
  opção), tabela Price ou SAC pelo `sistema_amortizacao`, primeira e última parcela,
  totais e `custo_total` (entrada + parcelas). Só importa a biblioteca padrão e o pacote
  `calculo`.
- **Validar (`pytest tests/calculo/test_cenarios.py`):** opção Price 75.000 a 1,99% em 48
  (valor financiado 75.000,00; 1ª 2.440,16; última 2.440,55; total pago 117.128,07;
  custo total 137.128,07) e SAC 65.000 a 1,5% em 60 (1ª 2.058,33; última 1.099,78; total
  pago 94.737,50; custo total 124.737,50), conferidos com os blocos da Etapa 6 e com a
  conta à mão; sistema inválido → `ValueError`; entrada ≥ veículo → `ValueError`;
  `float` → `TypeError`; `pytest tests/calculo/test_pureza.py` continua verde (cobre o
  arquivo novo).

### Tarefa 2 — Composição: fundo nos dois modos (`cenarios`, parte 2)
- **Arquivos:** `app/services/calculo/cenarios.py`, `tests/calculo/test_cenarios.py`
- **Mudança:** `fundo_da_simulacao(simulacao, aporte_mensal=None)`: no modo normal, meta =
  preço corrigido no prazo, aporte para a meta, série do fundo, `mes_da_meta` = prazo,
  `alcanca_a_meta` verdadeiro; no modo aporte, `meses_para_meta` com horizonte 60 (regras
  acima para meta alcançada e não alcançada); sempre com `capital_inicial` = entrada da
  simulação.
- **Validar:** exemplo da spec no modo normal (meta e `preco_na_compra` 108.410,78; aporte
  1.948,07; total aportado 70.130,52; saldo final 108.410,97; rendimento 18.280,45; custo
  total 108.410,78); modo aporte com 1.500,00 → `mes_da_meta` 46, preço na compra
  112.461,20, saldo no mês 113.040,26; com 300,00 → `mes_da_meta` `None`,
  `alcanca_a_meta` falso, custo `None` e valores do mês 60; capital que já cobre a meta
  (IPCA −20%, capital 90.000) → aporte 0,00; aporte 0,00 sem capital suficiente → não
  alcança, sem erro; a série do fundo tem `prazo + 1` pontos (ou `mes_da_meta + 1` / 61).

### Tarefa 3 — Composição: séries, eixo e menor custo (`cenarios`, parte 3)
- **Arquivos:** `app/services/calculo/cenarios.py`, `tests/calculo/test_cenarios.py`
- **Mudança:** `montar_resultado(simulacao, opcoes, aporte_mensal=None)`: à vista
  (`custo_total` = valor do veículo), financiamentos (0 a 3), fundo, `menor_custo` (com o
  desempate acima; o fundo sai da disputa quando o custo é `None`) e a lista de pontos por
  mês num **eixo comum** até o maior prazo, com `preco_corrigido` em todo o eixo e `None`
  onde cada série terminou; mais `tabela_da_opcao` para o `/parcelas`.
- **Validar:** exemplo completo (eixo 0 a 60; `preco_corrigido` 95.000,00 no mês 0 e
  108.410,78 no mês 36; `saldo_fundo` 20.000,00 no mês 0, valor final no mês 36 e `None`
  depois; `saldo_devedor` de cada opção começando no valor financiado, terminando em 0,00
  no último mês e `None` depois); `menor_custo` = à vista; sem opções → lista vazia, sem
  `saldo_devedor` e resultado válido; prazo de opção maior que o do fundo (72 x 36) e o
  inverso (12 x 60) → eixo no maior; `menor_custo` no fundo quando a opção custa mais e o
  à vista não existe no teste (caso construído) e desempate por ordem; propriedades: cada
  ponto coincide com as séries dos blocos, `len(series) = eixo + 1`; pior caso (3 tabelas
  de 72 meses + fundo de 60) em menos de 100 ms; contexto global do `Decimal` intacto.

### Tarefa 4 — Schemas de saída e do parâmetro de consulta
- **Arquivos:** `app/schemas/resultado.py`, `app/schemas/__init__.py`
- **Mudança:** schemas de saída de `/parcelas` (documento: `financiamento`, `parcelas`,
  `totais`) e de `/resultado` (`simulacao`, `cenarios`, `menor_custo`, `series`), com
  números como número JSON e `null` preservado; schema do parâmetro `aporte_mensal`
  (0 a 9.999.999,00, 2 casas, opcional; recusa desconhecidos) e o helper
  `carregar_consulta(schema)` que lê `request.args`.
- **Validar:** script descartável: `dump` de um resultado montado na Tarefa 3 vira JSON
  com `95000.0`, `1948.07` etc. e `null` onde a série terminou; chaves de `saldo_devedor`
  em texto; parâmetro: `1500`, `"1500.5"`, `0`, `9999999.00` aceitos e `None` se ausente;
  `""`, `abc`, `-1`, `9999999.01`, `10.005`, `NaN`, `1e999999`, `x=1` recusados em
  português, sem erro 500.

### Tarefa 5 — Adaptador com o banco
- **Arquivos:** `app/services/resultados.py`
- **Mudança:** `parcelas_da_opcao(usuario, simulacao_id, opcao_id)` (dono da simulação →
  opção → tabela) e `resultado_da_simulacao(usuario, simulacao_id, aporte_mensal)`
  (dono → opções em ordem de criação → `montar_resultado`), convertendo os models para as
  entradas puras (`Decimal` do banco direto; `sistema_amortizacao` pelo `.value`) e sem
  bloquear linhas.
- **Validar:** script descartável em contexto da aplicação, com dois usuários: resultado do
  exemplo da spec bate número a número com o da Tarefa 3; simulação sem opções; ids
  alheio/inexistente/enorme → 404 "Simulação não encontrada" e opção alheia → 404 "Opção
  de financiamento não encontrada"; **nenhum `float`** nas entradas entregues ao cálculo
  (asserção nos tipos); as tabelas do banco continuam intactas; limpar os dados de teste.

### Tarefa 6 — Schemas do Swagger
- **Arquivos:** `app/__init__.py`
- **Mudança:** acrescentar a `SWAGGER_TEMPLATE` os schemas do documento de `/parcelas`
  (`Parcela`, `ParcelasFinanciamento`) e de `/resultado` (`ResultadoSimulacao`, os blocos
  `ResultadoFinanciamento`, `ResultadoFundo`, `MenorCusto` e `PontoSerie`, com
  `nullable`, exemplos e a descrição de cada campo, incluindo o significado de
  `custo_total`).
- **Validar:** `/apispec.json` (pelo `test_client`) contém os schemas novos, com os campos
  e `nullable` certos, ao lado dos anteriores; a aplicação continua criando.

### Tarefa 7 — Rota `GET .../parcelas`
- **Arquivos:** `app/routes/financiamentos.py`
- **Mudança:** `GET /api/simulacoes/<id>/financiamentos/<fid>/parcelas`, protegida por JWT,
  só chama `parcelas_da_opcao` e serializa; docstring OpenAPI 3 completa (última parcela
  ajustada, parcelas 0,00 após quitação antecipada, `saldo_devedor` após o pagamento,
  respostas 200/401/404).
- **Validar:** `flask routes` lista a rota; `/apispec.json` traz o caminho com `security`
  e as respostas; com o servidor no ar, sem token → 401; `curl` com token de uma opção do
  exemplo → 200 com 48 linhas e os números da spec; `GET .../financiamentos/<fid>` (sem
  `/parcelas`) continua 405.

### Tarefa 8 — Rota `GET .../resultado`
- **Arquivos:** `app/routes/simulacoes.py`
- **Mudança:** `GET /api/simulacoes/<id>/resultado[?aporte_mensal=]`, protegida por JWT,
  lê o parâmetro com `carregar_consulta`, chama `resultado_da_simulacao` e serializa;
  docstring OpenAPI 3 completa (o significado de "custo total" e do destaque, a comparação
  nominal, o eixo e os `null`, o modo "dado o aporte", respostas 200/401/404/422).
- **Validar:** `flask routes` lista a rota; `/apispec.json` traz o caminho com o parâmetro
  `aporte_mensal`, `security` e as respostas; sem token → 401; `?x=1` → 422;
  `flask run` sobe sem erro.

### Tarefa 9 — Validação ponta a ponta contra o servidor
- **Arquivos:** nenhum no projeto.
- **Mudança:** nenhuma; verificação com o servidor rodando, dois usuários e tokens gerados
  por script descartável.
- **Validar:**
  - **exemplo da spec** (95.000, IPCA 4,5%, fundo 10,5%, 36 meses, entrada 20.000; opção
    A Price 1,99% 48x entrada 20.000; opção B SAC 1,5% 60x entrada 30.000): à vista
    95.000,00; fundo com meta 108.410,78, aporte 1.948,07, `alcanca_a_meta` verdadeiro;
    totais dos dois financiamentos; `menor_custo` = à vista;
  - **séries:** 61 pontos (mês 0 a 60); `preco_corrigido` 95.000,00 no mês 0 e 108.410,78
    no mês 36; fundo 20.000,00 no mês 0 e `null` a partir do mês 37; `saldo_devedor` de
    cada opção começando no valor financiado, 0,00 no último mês da opção e `null` depois;
    nenhum ponto sem `mes`;
  - **`/parcelas`:** opção A com 48 linhas, 1ª parcela 2.440,16 / juros 1.492,50 /
    amortização 947,66 / saldo 74.052,34, última 2.440,55, totais; opção B com 60 linhas, 1ª
    2.058,33 e última 1.099,78; soma das amortizações = valor financiado e saldo final 0,00;
  - **modo aporte:** `?aporte_mensal=1500` → `mes_da_meta` 46, `preco_na_compra` 112.461,20;
    `?aporte_mensal=300` → `null`, `alcanca_a_meta` falso, fundo fora do `menor_custo`;
    `?aporte_mensal=` vazio/`abc`/`-1`/`9999999.01`/`10.005`/repetido e `?x=1` → 422 em
    português, sem 500;
  - simulação **sem opções** → 200, `financiamentos: []`, sem `saldo_devedor` nos pontos;
    opção de prazo 72 com fundo de 36 → eixo de 73 pontos; capital que cobre a meta
    (IPCA negativo) → aporte 0,00;
  - **isolamento:** o usuário B recebe 404 "Simulação não encontrada" (idêntico ao de
    inexistente) nas 2 rotas; `fid` de outra simulação do próprio usuário → 404 "Opção de
    financiamento não encontrada"; ids `abc`, `-1`, `99999999999` → 404 (nunca 500);
  - 401 `{"erro": ...}` nas 2 rotas sem token, com token inválido e expirado;
  - alterar a simulação (`PUT`) muda o resultado seguinte (sem cache); números como número
    JSON; resposta do pior caso em menos de 100 ms; nenhum `Traceback` no log.
  Ao final, remover usuários, simulações e opções de teste.

### Tarefa 10 — Validação manual no Swagger UI (sua)
- **Arquivos:** nenhum.
- **Mudança:** nenhuma; eu subo o servidor e você confere no navegador.
- **Validar:** em `/apidocs/`: as 2 rotas aparecem com os exemplos e as explicações
  (última parcela, quitação antecipada, "custo total", eixo e `null`, modo aporte);
  login, **Authorize** com só o token, criar a simulação do exemplo com as 2 opções,
  `GET .../parcelas` de cada uma, `GET .../resultado`, `GET .../resultado?aporte_mensal=1500`
  (mês 46) e `?aporte_mensal=300` (não alcança), e um 422 (`aporte_mensal=-1`). Se a página
  falhar, parar e avisar antes de mudar o esquema do Swagger.

### Tarefa 11 — Regressão e conferência de dependências
- **Arquivos:** nenhum.
- **Mudança:** nenhuma; verificação.
- **Validar:** `pytest` (suíte inteira) verde, sem avisos; `flask run` sobe; `/api/saude` e
  `/apidocs/` → 200; login e `perfil` funcionam; todos os scripts descartáveis das
  Etapas 1 a 5 (incluindo os ponta a ponta de simulações e financiamentos) → `TUDO OK`;
  `flask db migrate` → "No changes in schema detected"; `pip check` limpo; `requirements.txt`
  e `requirements-dev.txt` inalterados; sem segredo em arquivo versionável; sem
  `DeprecationWarning` ao importar a aplicação; as 4 tabelas vazias.

### Tarefa 12 — Atualizar a documentação
- **Arquivos:** `plano.md`, `CLAUDE.md`, esta spec
- **Mudança:**
  - `plano.md`: marcar a Etapa 7 como concluída com as decisões (custo = o que se paga pelo
    carro e `menor_custo` no backend, séries em lista de pontos, eixo comum com `null`,
    modo aporte substituindo o cálculo, `/parcelas` como documento); registrar na Etapa 8
    que as taxas sugeridas do BACEN alimentam o formulário (o `/resultado` usa as gravadas),
    na Etapa 10 os testes de integração das 2 rotas e na Etapa 12 as rotas novas e o
    contrato do resultado no README;
  - `CLAUDE.md`: rotas implementadas (`/parcelas` e `/resultado`), o **contrato do
    resultado** (definição de `custo_total` por cenário, `menor_custo`, comparação nominal,
    lista de pontos, eixo comum e `null`, chave de `saldo_devedor`, modo `aporte_mensal` e o
    bloco do fundo), a estrutura ✔ (`calculo/cenarios.py`, `services/resultados.py`,
    `schemas/resultado.py`), a regra "rotas de leitura calculam sob demanda e não gravam",
    o contrato com o frontend (o que ele **não** recalcula, `null` no fim das séries,
    `mes_da_meta`) e o "Estado atual";
  - esta spec: marcar os critérios de aceite e o status como implementada.
- **Validar:** reler os três arquivos e conferir que não restam menções a "`/parcelas`,
  `/resultado` ainda não" nem a `cenarios` como pendência.

### Tarefa 13 — Conferência final
- **Arquivos:** nenhum.
- **Mudança:** nenhuma; verificação de todos os critérios de aceite.
- **Validar:** percorrer a lista de critérios, informar o que passou e o que dependeu da
  sua verificação manual, mostrar o resultado do `pytest` e o `git status --short` final
  (esperado: `app/services/calculo/cenarios.py`, `app/services/resultados.py`,
  `app/schemas/resultado.py`, `tests/calculo/test_cenarios.py`, alterações em
  `app/schemas/__init__.py`, `app/__init__.py`, `app/routes/financiamentos.py`,
  `app/routes/simulacoes.py` e documentação) e aguardar você pedir o commit.
