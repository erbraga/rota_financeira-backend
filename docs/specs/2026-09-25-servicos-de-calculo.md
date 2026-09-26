# Serviços de cálculo e testes unitários (Etapa 6) — Spec

**Criado em:** 2026-09-25
**Status:** Implementada em 2026-09-25
**Origem:** Etapa 6 de `plano.md`; seções 2 e 4 de `proposta-backend-api-rest.md`

## Problema
A API guarda simulações e opções de financiamento (Etapas 4 e 5), mas **nenhum
cálculo existe ainda**: não há preço corrigido pelo IPCA, tabela de amortização
Price/SAC nem simulação do fundo. Sem isso a Etapa 7 (`/parcelas` e `/resultado`)
não tem o que expor. Estado verificado:

- **Código:** `app/services/` tem `auth.py`, `simulacoes.py` e `financiamentos.py`
  (regras de CRUD, com banco e Flask). Não existe código financeiro e **não existe
  `tests/`**, `pytest.ini` nem `pytest` instalado (versão atual no PyPI: 9.1.1;
  Python 3.12.3).
- **Nome que conflita:** o plano lista `app/services/financiamento.py`, mas já
  existe `app/services/financiamentos.py` (CRUD). Dois arquivos que só diferem por
  um "s" e fazem coisas opostas (um puro, outro com banco) são um convite a erros
  (decisão 6).
- **Entradas que a API já garante** (Etapas 4 e 5), que os cálculos podem assumir:
  `valor_veiculo` de 0,01 a 9.999.999,00; `taxa_ipca_projetada` de −20 a 100 (% a.a.);
  `taxa_fundo_rendimento` de 0 a 100 (% a.a.); `prazo_meses_fundo` de 1 a 60;
  `taxa_juros_mensal` de 0 a 20 (% a.m.); `prazo_meses` de 1 a 72; entrada da opção
  **estritamente menor** que o veículo (valor financiado sempre > 0); no máximo 3
  opções por simulação. Percentuais chegam como no banco (`12.5` = 12,5%).
- **Pendência herdada (decisão 12 da Etapa 2):** o modo "dado o aporte" do fundo
  ficou para as Etapas 6 e 7; a tabela `simulacoes` **não** tem coluna de aporte.
- **Pendência herdada (Etapa 5):** "taxa 0 é válida": as fórmulas não podem dividir
  por zero.
- **Verificações exploratórias** (scripts descartáveis, Python 3.12, `decimal`):
  - o contexto padrão do `Decimal` tem **28 dígitos** e arredondamento
    **`ROUND_HALF_EVEN`** (arredondamento "do banqueiro"): o arredondamento comercial
    (`ROUND_HALF_UP`) precisa ser pedido em cada `quantize`;
  - `Decimal ** Decimal` aceita expoente fracionário (`(1+a)^(1/12)`), com precisão
    de 50 dígitos fecha a conta (`(1+im)^12` volta a `1,105` até o 47º dígito) e leva
    ~54 µs por potência: 2.000 potências em ~108 ms;
  - com taxa 0 a potência devolve `0E-49` (zero com expoente): é preciso um ramo
    explícito para taxa zero;
  - os extremos da API não estouram: `(1,20)^72 ≈ 502.400` e
    `9.999.999 × 2^(60/12) ≈ 320 milhões`;
  - **arredondar a parcela do Price** (`75.000`, 1,99% a.m., 48 meses: parcela
    exata 2.440,164810 → 2.440,16) faz a **última parcela ser 2.440,55**
    (39 centavos maior) para o saldo fechar em zero: é como os contratos reais
    funcionam, e a soma das amortizações fecha em 75.000,00;
  - o fundo de `95.000` a 4,5% de IPCA em 36 meses tem meta `108.410,78`; sem capital
    inicial o aporte exato é `2.593,6550` (2.593,66 arredondando para cima); com
    `20.000` de capital inicial cai para `1.948,07`.

## Objetivo
Criar a camada de cálculo financeiro — funções puras em `Decimal`, sem Flask nem
banco — que produza o preço corrigido pelo IPCA, as tabelas de amortização Price e
SAC, o custo total do financiamento e a simulação do fundo (aporte necessário e
tempo para atingir a meta), coberta por testes unitários com valores conhecidos e
propriedades matemáticas.

## Fora de escopo
- Rotas, schemas e formato JSON: `/parcelas` e `/resultado` são da Etapa 7. Esta
  etapa entrega **blocos de cálculo**; a composição dos três cenários fica para a
  Etapa 7 (decisão 6).
- CET (Custo Efetivo Total), IOF, tarifas, seguros, carência, amortização
  extraordinária, portabilidade (CET é opcional na Etapa 9).
- Impostos e taxas do fundo (Imposto de Renda, taxa de administração): o
  rendimento informado é tratado como líquido.
- Exposição do modo "dado o aporte" na API (parâmetro de consulta): Etapa 7. Aqui só
  a função pura (decisão 5).
- Banco, migrations, dependências de runtime novas; `requirements.txt` não muda.
- Testes de integração da API e CI (Etapa 10); os scripts descartáveis das etapas
  anteriores continuam fora do repositório.

## Proposta

### Arquivos
```
app/services/calculo/            # pacote PURO: não importa Flask, SQLAlchemy nem app.*
  __init__.py
  base.py                        # contexto Decimal, arredondamento, conversão de taxas, validações
  preco.py                       # preço à vista corrigido pelo IPCA (valor e série)
  financiamento.py               # tabelas Price e SAC, custo total
  fundo.py                       # aporte necessário, série do saldo, meses para a meta
tests/
  calculo/
    test_base.py  test_preco.py  test_financiamento.py  test_fundo.py  test_pureza.py
pytest.ini                       # testpaths = tests
requirements-dev.txt             # -r requirements.txt + pytest (decisão 7)
```
`requirements.txt` e o restante do `app/` não mudam.

### Convenções gerais (valem para todas as funções)
- **Só `Decimal`** (aceita `int` e converte; **recusa `float`** com `TypeError`, para
  o erro de ponto flutuante não entrar pela porta dos fundos).
- **Percentual na entrada** (`12.5` = 12,5%), como no banco e na API; a conversão
  para fração acontece em **um único ponto** (`base.py`).
- **Precisão interna de 50 dígitos** num contexto local (`localcontext`), sem mexer
  no contexto global; **arredondamento comercial** (`ROUND_HALF_UP`) para 2 casas
  nos valores em reais devolvidos.
- **Validação defensiva:** valor financiado ≤ 0, prazo < 1, taxa negativa (juros e
  rendimento) ou faixa absurda → `ValueError` com mensagem clara. A API já valida;
  isto protege outros chamadores.
- **Saídas imutáveis** (`dataclass(frozen=True)`), com tuplas de linhas.
- **Nomes em português**, `snake_case`, docstrings curtas dizendo a fórmula.

### Funções (interface pública)

**`base.py`**
- `arredondar_moeda(valor)`: 2 casas, `ROUND_HALF_UP`.
- `taxa_mensal_equivalente(taxa_anual_percentual)`: `(1 + a)^(1/12) − 1` como
  fração (decisão 2); com taxa 0 devolve `0` exato.
- `percentual_para_fracao(p)`: `p / 100`.

**`preco.py`**
- `preco_corrigido(valor_veiculo, ipca_aa, meses)`: `valor × (1 + ipca)^(meses/12)`,
  arredondado. A meta do fundo é `preco_corrigido(valor, ipca, prazo_meses_fundo)`.
- `serie_preco_corrigido(valor_veiculo, ipca_aa, prazo)`: valores de `mês 0` até
  `mês prazo` (o mês 0 é o preço de hoje), para o gráfico da Etapa 7.

**`financiamento.py`**
- `tabela_price(valor_financiado, taxa_mensal_percentual, prazo)` e
  `tabela_sac(...)`: devolvem `TabelaAmortizacao` com `parcelas` (`numero`,
  `valor_parcela`, `juros`, `amortizacao`, `saldo_devedor` após o pagamento),
  `total_pago` e `total_juros`. Primeira parcela **um mês depois** da compra, sem
  carência; taxa 0 tem ramo próprio (parcela = valor ÷ prazo).
- `custo_total_financiamento(entrada, tabela)`: `entrada + total_pago`.

**`fundo.py`**
- `aporte_para_meta(meta, capital_inicial, taxa_aa, prazo)`: aporte mensal
  **arredondado para cima** ao centavo que leva `capital_inicial` (decisão 4) à `meta`
  em `prazo` meses, com aportes ao fim de cada mês (decisão 3); `0,00` se o capital
  inicial já bastar; taxa 0 → `(meta − capital) ÷ prazo`.
- `serie_fundo(capital_inicial, aporte, taxa_aa, prazo)`: saldo do mês 0 ao `prazo`,
  calculado **sem arredondar no meio** e arredondado só na saída (decisão 1); devolve
  também `total_aportado` e `rendimento`.
- `meses_para_meta(valor_veiculo, ipca_aa, capital_inicial, aporte, taxa_aa, horizonte)`:
  primeiro mês em que o saldo alcança o preço corrigido **daquele mês** (a meta cresce
  com o IPCA), ou `None` se não alcançar dentro do `horizonte` (decisão 5); devolve
  as séries (saldo e meta) até o mês encontrado, ou até o horizonte quando `None`.

### Regras de cálculo (detalhe que os testes cobrem)
- **Price:** `PMT = PV·i / (1 − (1+i)^−n)`, arredondada ao centavo; a cada mês o
  juro é `saldo × i` arredondado e a amortização é `PMT − juros`; a **última parcela
  absorve o resíduo** (amortização = saldo restante), de modo que o saldo final é
  exatamente 0,00 e `Σ amortizações = valor financiado` (decisão 1).
- **SAC:** amortização constante `PV ÷ n` arredondada (a última absorve o resíduo);
  juros sobre o saldo; parcelas não crescentes até a penúltima. A última pode passar
  da anterior só pelo resíduo da amortização (verificado na implementação: com taxa 0,
  R$ 1.000 em 3 meses dá 333,33, 333,33 e 333,34).
- **Custo total:** `entrada da opção + Σ parcelas`.
- **Fundo:** `saldo(0) = capital_inicial`; `saldo(m) = saldo(m−1)·(1+i) + aporte`;
  taxa mensal composta equivalente (decisão 2).
- **Meta do fundo:** `preco_corrigido(valor_veiculo, ipca, prazo_meses_fundo)`.

### Testes (pytest)
- **Valores conhecidos**, verificáveis à mão ou em planilha: Price de 100.000 a 1%
  a.m. em 12 meses (parcela 8.884,88); SAC de 12.000 a 1% em 12 meses (amortização
  1.000,00; 1ª parcela 1.120,00; última 1.010,00); fundo sem rendimento (meta 12.000
  em 12 meses → aporte 1.000,00); preço corrigido com IPCA 0 (igual ao valor).
- **Propriedades** (parametrizadas em vários prazos, taxas e valores): a soma das
  amortizações é igual ao valor financiado; saldo final 0,00; Price com parcelas
  iguais (menos a última) e SAC decrescente; juros do mês = saldo anterior × taxa
  (arredondado); total pago = Σ parcelas; o saldo do fundo com o aporte calculado é
  **maior ou igual** à meta; o aporte é o menor centavo que atinge a meta;
  `meses_para_meta` coerente com `serie_fundo`.
- **Referência independente:** os valores de referência são obtidos por outro caminho
  (fórmula fechada em alta precisão × simulação mês a mês; aritmética em centavos
  inteiros), não pela própria função testada.
- **Bordas:** prazo 1; taxa 0 (financiamento e fundo); valor financiado mínimo
  (0,01, parcelas 0,00 até a última); extremos da API (9.999.999,00 a 20% em 72 meses;
  fundo de 100% a.a. em 60 meses; IPCA −20%); capital inicial que já cobre a meta;
  meta inalcançável no horizonte; entradas inválidas (`float`, negativos, prazo 0).
- **Pureza:** um teste importa o pacote `calculo` em um processo limpo e confere que
  **Flask, SQLAlchemy e `app.models` não foram carregados**.
- **Desempenho:** o pior caso de uma simulação (3 tabelas de 72 meses + fundo de 60)
  roda em bem menos de 100 ms.

### Fluxo principal
1. `pip install -r requirements-dev.txt` (uma vez).
2. `pytest` na raiz do projeto → toda a suíte verde.
3. A Etapa 7 chamará estas funções a partir dos dados do banco.

### Casos de borda
- **Última parcela diferente:** com o arredondamento por parcela a última absorve
  centavos (39 centavos no exemplo verificado); a API deve documentar isso na Etapa 7.
  Com juros muito altos a diferença cresce (R$ 75.000 a 20% a.m. em 72 meses: última
  15.394,98 contra 15.000,03).
- **Quitação antecipada por arredondamento** (decisão 8): com parcelas de centavos ou
  juros extremos, o saldo zera antes do fim e as parcelas restantes saem 0,00.
- **Valor financiado mínimo** (0,01) em 72 meses: parcela e amortização 0,00 até a
  última, que quita os 0,01; aceito e testado como caso degenerado.
- **Meta com capital inicial acima do necessário:** aporte 0,00 (nunca negativo).
- **IPCA negativo:** a meta cai com o tempo; o fundo pode alcançá-la mais cedo.
- **Meta inalcançável** (aporte 0 ou muito baixo, IPCA alto): `meses_para_meta`
  devolve `None`, sem erro.
- **Taxa 0:** ramo próprio, sem divisão por zero e sem o `0E-49` da potência.
- **`float` na entrada:** `TypeError` (o chamador converte com `Decimal(str(...))`).
- **Contexto global do `Decimal`:** nunca é alterado (contexto local), para não
  afetar o Marshmallow nem o SQLAlchemy.

## Decisões tomadas
1. ~~**Convenção de arredondamento**~~ — **RESOLVIDA (2026-09-25): (a)**
   **Financiamento:** arredonda **por parcela** (parcela e juros ao centavo,
   `ROUND_HALF_UP`) e a **última parcela absorve o resíduo** (saldo final exatamente
   0,00; `Σ amortizações = valor financiado`). **Fundo:** precisão alta **sem**
   arredondar no meio, arredondando só na saída, e o **aporte sobe ao centavo
   seguinte** (`ROUND_CEILING`) para a meta ser sempre atingida. Contexto interno de
   50 dígitos; o contexto global do `Decimal` nunca é alterado.
2. ~~**Taxa anual → mensal**~~ — **RESOLVIDA (2026-09-25): (a)** **composta**,
   `(1 + a)^(1/12) − 1` (o IPCA usa `(1 + ipca)^(m/12)`); taxa 0 tem ramo próprio.
   O financiamento não converte: `taxa_juros_mensal` já é % a.m.
3. ~~**Momento dos aportes**~~ — **RESOLVIDA (2026-09-25): (a)** **fim de cada
   mês** (série postecipada): `saldo(m) = saldo(m−1)·(1+i) + aporte`; o primeiro
   aporte rende a partir do mês seguinte. Mesma convenção das parcelas do
   financiamento (pagas ao fim de cada mês).
4. ~~**Papel do `valor_entrada` da simulação no fundo**~~ — **RESOLVIDA
   (2026-09-25): (a)** é o **capital inicial do fundo**: começa aplicado no mês 0 e
   rende junto com os aportes; o aporte mensal só cobre o restante da meta (no
   exemplo, 1.948,07 em vez de 2.593,66). Se o capital já bastar, aporte 0,00.
5. ~~**Modo "dado o aporte" e horizonte**~~ — **RESOLVIDA (2026-09-25): (a)**
   implementar **agora** a função pura `meses_para_meta`, com busca mês a mês (a meta
   cresce com o IPCA), horizonte padrão de **60 meses** (o teto do `prazo_meses_fundo`)
   e `None` quando a meta não é alcançada. A exposição na API fica para a Etapa 7.
6. ~~**Onde ficam os módulos e o que entra nesta etapa**~~ — **RESOLVIDA
   (2026-09-25): (a)** subpacote puro **`app/services/calculo/`** (`base`, `preco`,
   `financiamento`, `fundo`), sem importar Flask, SQLAlchemy nem `app.*` (garantido
   por teste). A composição dos três cenários (`cenarios`) fica para a **Etapa 7**,
   junto do contrato JSON do `/resultado`.
7. ~~**Framework de testes e dependência**~~ — **RESOLVIDA (2026-09-25): (a)**
   **`pytest`** (9.1.1), instalado só por **`requirements-dev.txt`** (`-r
   requirements.txt` + `pytest`), para não ir à imagem de produção; `pytest.ini`
   com `testpaths = tests`. Justificativa: parametrização das propriedades em muitas
   combinações, asserções simples e reuso na Etapa 10.

8. ~~**Saldo negativo por arredondamento (surgiu na implementação)**~~ —
   **RESOLVIDA (2026-09-25): (a)** a **amortização de cada mês é limitada ao saldo
   restante**. Com parcelas de poucos centavos (ex.: R$ 0,36 em 72 meses) ou juros
   muito altos (ex.: R$ 2.000 a 20% a.m. em 60 meses), o meio centavo do
   arredondamento da parcela rende juros compostos e levaria o saldo a negativo antes
   do fim. Com a trava, o saldo nunca fica negativo, `Σ amortizações = valor
   financiado` e a decisão 1 continua valendo; nesses casos o financiamento é quitado
   antes do último mês e as parcelas seguintes saem **0,00** (a tabela mantém uma
   linha por mês do prazo). Vale para Price e SAC. Alternativas descartadas: baixar o
   teto de juros da Etapa 5 e arredondar só na exibição (reverteria a decisão 1 e
   quebrava com valores de centavos).

9. ~~**Como verificar a pureza (surgiu na implementação)**~~ — **RESOLVIDA
   (2026-09-25): (a)** pelo **código-fonte**: um teste lê os módulos de
   `app/services/calculo/` e exige que só importem a biblioteca padrão e o próprio
   pacote. Em tempo de execução, importar `app.services.calculo` executa
   `app/__init__.py` (a factory, que importa Flask, models e rotas), então a
   verificação por `sys.modules` em processo limpo, como estava no plano, não se
   aplica. Descartados: tornar os imports de `app/__init__.py` preguiçosos (fora do
   escopo) e mover o pacote para fora de `app/` (reverteria a decisão 6).

## Critérios de aceite
- [x] `pip install -r requirements-dev.txt` funciona e `pytest` (na raiz) roda toda a
      suíte, verde, sem avisos de depreciação.
- [x] Valores conhecidos: Price 100.000 / 1% / 12 → parcela 8.884,88; SAC 12.000 /
      1% / 12 → amortização 1.000,00, 1ª parcela 1.120,00, última 1.010,00; fundo com
      taxa 0, meta 12.000, 12 meses → aporte 1.000,00; IPCA 0 → preço igual ao valor.
- [x] Propriedades (parametrizadas): `Σ amortizações = valor financiado`, saldo final
      0,00, Price com parcelas iguais exceto a última, SAC não crescente até a penúltima, juros = saldo
      anterior × taxa, total pago = Σ parcelas, custo total = entrada + total pago.
- [x] Fundo: com o aporte calculado o saldo final é **maior ou igual** à meta e o
      aporte é o **menor** centavo que garante isso; capital inicial que já cobre a
      meta → aporte 0,00; `meses_para_meta` concorda com `serie_fundo`.
- [x] Taxa 0 em financiamento (Price e SAC) e em fundo funciona, sem divisão por zero
      e sem `0E-49` nas saídas.
- [x] Bordas: prazo 1; valor financiado 0,01; extremos da API sem erro; meta
      inalcançável → `None`; IPCA negativo; entradas inválidas (`float`, negativos,
      prazo 0) → `TypeError`/`ValueError` claros.
- [x] Os valores de referência dos testes vêm de cálculo independente (documentado no
      próprio teste), não da função testada.
- [x] Pureza (decisão 9): os módulos de `app/services/calculo/` só importam a
      biblioteca padrão e o próprio pacote (verificado no código-fonte); o contexto
      global do `Decimal` não é alterado.
- [x] Desempenho: o pior caso de uma simulação roda em menos de 100 ms.
- [x] `requirements.txt` inalterado; `requirements-dev.txt` novo; `flask db migrate`
      sem mudanças; os scripts descartáveis das Etapas 1 a 5 continuam `TUDO OK`.
- [x] `plano.md` e `CLAUDE.md` atualizados (estrutura, convenções de cálculo, como
      rodar o `pytest`, decisões e o que a Etapa 7 deve fazer).

---
*Depois de aprovada, esta spec vira a base do PLANO — não escrever
código antes disso.*

## Plano de Implementação

Tarefas na ordem de execução. Nenhuma faz `git add`/`commit`/`push` (só quando
você pedir). Pré-requisitos: `.venv` ativo e raiz do projeto como diretório de
trabalho. O banco **não** é necessário para esta etapa (o pacote é puro), exceto na
regressão da Tarefa 9. A validação principal passa a ser a **suíte `pytest`**, que
fica no repositório; scripts descartáveis continuam só no diretório temporário.

Cada tarefa de código é escrita **junto com os seus testes** e só termina com o
`pytest` verde. Os valores de referência dos testes vêm de cálculo independente
(fórmula fechada em alta precisão, aritmética em centavos inteiros ou conta à mão),
documentado no próprio teste.

Pontos de atenção que o plano incorpora:
- O contexto padrão do `Decimal` arredonda `ROUND_HALF_EVEN`: todo `quantize` informa
  o modo explicitamente (`ROUND_HALF_UP` ou `ROUND_CEILING`).
- As contas rodam dentro de `localcontext()` com 50 dígitos; um teste confere que o
  contexto global continua igual depois de cada função.
- Com taxa 0, `(1 + 0) ** fração − 1` devolve `0E-49`: há ramo explícito e um teste
  confere que nenhuma saída tem expoente estranho (todas com 2 casas).
- `float` na entrada é recusado (`TypeError`); `int` é aceito e convertido.
- O aporte arredondado para cima não pode "passar do ponto": o teste confere que um
  centavo a menos **não** atinge a meta.

### Tarefa 1 — Infraestrutura de testes
- **Arquivos:** `requirements-dev.txt`, `pytest.ini`, `tests/__init__.py`,
  `tests/calculo/__init__.py`
- **Mudança:** `requirements-dev.txt` com `-r requirements.txt` e `pytest==9.1.1`;
  `pytest.ini` com `testpaths = tests` e avisos de depreciação tratados como erro;
  instalar.
- **Validar:** `pip install -r requirements-dev.txt` sem erro; `pip check` limpo;
  `pytest --version` → 9.1.1; `pytest` roda (0 testes, sem erro de coleta);
  `git diff -- requirements.txt` vazio.

### Tarefa 2 — `base.py`: convenções numéricas
- **Arquivos:** `app/services/__init__.py` (inalterado),
  `app/services/calculo/__init__.py`, `app/services/calculo/base.py`,
  `tests/calculo/test_base.py`
- **Mudança:** contexto local de 50 dígitos, `arredondar_moeda` (`ROUND_HALF_UP`,
  2 casas), `arredondar_moeda_para_cima` (`ROUND_CEILING`), `percentual_para_fracao`,
  `taxa_mensal_equivalente` (composta; taxa 0 → `0` exato) e a conversão/validação
  das entradas (`int` → `Decimal`, `float` → `TypeError`, faixas → `ValueError`).
- **Validar (`pytest tests/calculo/test_base.py`):** `2,005 → 2,01` e `2,004 → 2,00`
  (não o arredondamento do banqueiro); `ROUND_CEILING` de `2593,6550 → 2593,66` e de
  `2593,66 → 2593,66`; 10,5% a.a. → mensal que, elevada a 12, volta a 1,105 com 40+
  dígitos; 12% a.a. → 0,9488793% a.m.; taxa 0 → `Decimal("0")` sem `E-49`; `float`
  → `TypeError`; o contexto global do `Decimal` é o mesmo antes e depois.

### Tarefa 3 — `preco.py`: preço corrigido pelo IPCA
- **Arquivos:** `app/services/calculo/preco.py`, `tests/calculo/test_preco.py`
- **Mudança:** `preco_corrigido(valor, ipca_aa, meses)` e
  `serie_preco_corrigido(valor, ipca_aa, prazo)` (mês 0 a mês `prazo`).
- **Validar:** IPCA 0 → igual ao valor em qualquer mês; 12 meses a 4,5% → valor ×
  1,045 exato; 95.000 a 4,5% em 36 meses → 108.410,78; IPCA negativo → preço menor;
  a série tem `prazo + 1` pontos, começa no valor de hoje e cada ponto confere com
  `preco_corrigido`; extremo (9.999.999,00 a 100% em 60 meses) sem erro; meses < 0
  → `ValueError`.

### Tarefa 4 — `financiamento.py`: tabela Price
- **Arquivos:** `app/services/calculo/financiamento.py`,
  `tests/calculo/test_financiamento.py`
- **Mudança:** dataclasses imutáveis (`Parcela`, `TabelaAmortizacao`) e
  `tabela_price(valor_financiado, taxa_mensal_percentual, prazo)`: parcela e juros
  arredondados por parcela, última parcela absorve o resíduo, taxa 0 com ramo próprio.
- **Validar:** 100.000 a 1% em 12 meses → parcela 8.884,88 (conta de referência);
  75.000 a 1,99% em 48 → parcela 2.440,16 e última 2.440,55; **propriedades
  parametrizadas** (prazos 1, 12, 48, 72; taxas 0, 0,5, 1,99, 20; valores 0,01,
  1.000, 75.000, 9.999.999,00): `Σ amortizações = valor financiado`, saldo final
  0,00, parcelas iguais exceto a última, juros = saldo anterior × taxa arredondado,
  saldo sempre ≥ 0, `total_pago = Σ parcelas`, `total_juros = total_pago − valor`,
  todas as saídas com 2 casas; conferência independente em centavos inteiros;
  valor ≤ 0, prazo 0 e taxa negativa → `ValueError`.

### Tarefa 5 — `financiamento.py`: tabela SAC e custo total
- **Arquivos:** `app/services/calculo/financiamento.py`,
  `tests/calculo/test_financiamento.py`
- **Mudança:** `tabela_sac(...)` (amortização constante arredondada, última absorve
  o resíduo, juros sobre o saldo) e `custo_total_financiamento(entrada, tabela)`.
- **Validar:** 12.000 a 1% em 12 → amortização 1.000,00, 1ª parcela 1.120,00,
  última 1.010,00; mesmas propriedades parametrizadas do Price, trocando "parcelas
  iguais" por "parcelas não crescentes"; com a mesma taxa e prazo, o SAC paga menos
  juros no total que o Price (propriedade conhecida); custo total = entrada + total
  pago; taxa 0 → parcelas iguais a `valor ÷ prazo` (última com o resíduo).

### Tarefa 6 — `fundo.py`: série e aporte para a meta
- **Arquivos:** `app/services/calculo/fundo.py`, `tests/calculo/test_fundo.py`
- **Mudança:** `serie_fundo(capital_inicial, aporte, taxa_aa, prazo)` (saldo do mês
  0 ao `prazo`, sem arredondar no meio, com `total_aportado` e `rendimento`) e
  `aporte_para_meta(meta, capital_inicial, taxa_aa, prazo)` (aporte ao fim de cada
  mês, arredondado para cima; 0,00 se o capital já bastar; taxa 0 →
  `(meta − capital) ÷ prazo`).
- **Validar:** taxa 0, meta 12.000, 12 meses, sem capital → 1.000,00; exemplo da
  spec (meta 108.410,78, 10,5% a.a., 36 meses) → 2.593,66 sem capital e 1.948,07 com
  20.000; **propriedade parametrizada**: com o aporte calculado o saldo final é
  ≥ meta, e com **um centavo a menos** fica < meta (o aporte é o menor possível);
  capital que já cobre a meta → 0,00 (nunca negativo); a série começa no capital, tem
  `prazo + 1` pontos e confere com a fórmula fechada do valor futuro em alta precisão;
  `rendimento = saldo final − capital − total aportado`; extremos (100% a.a., 60
  meses, 9.999.999,00) sem erro.

### Tarefa 7 — `fundo.py`: meses para a meta (modo "dado o aporte")
- **Arquivos:** `app/services/calculo/fundo.py`, `tests/calculo/test_fundo.py`
- **Mudança:** `meses_para_meta(valor_veiculo, ipca_aa, capital_inicial, aporte,
  taxa_aa, horizonte=60)`: busca mês a mês o primeiro mês em que o saldo alcança o
  preço corrigido **daquele mês**; devolve o mês e as séries (saldo e meta) até ele,
  ou `None` e as séries até o horizonte.
- **Validar:** coerência com `aporte_para_meta` (usando o aporte calculado para `n`
  meses, a meta é alcançada em **no máximo** `n` meses, e com 1 centavo a menos em
  mais de `n` ou nunca); capital que já cobre o preço de hoje → mês 0; aporte 0 e
  sem capital → `None`; IPCA alto e aporte baixo → `None` dentro do horizonte;
  IPCA negativo alcança antes do que com IPCA 0; as séries têm o tamanho certo;
  horizonte < 1 → `ValueError`.

### Tarefa 8 — Pureza, desempenho e contexto
- **Arquivos:** `tests/calculo/test_pureza.py`
- **Mudança:** testes transversais do pacote.
- **Validar:** em **subprocesso limpo**, `import app.services.calculo` (e os quatro
  módulos) não carrega `flask`, `sqlalchemy`, `flask_sqlalchemy` nem `app.models`
  (`sys.modules`); o pior caso de uma simulação (3 tabelas de 72 meses a 20% com
  9.999.999,00 + fundo e `meses_para_meta` de 60 meses) roda em menos de 100 ms;
  nenhuma função altera o contexto global do `Decimal`.

### Tarefa 9 — Suíte completa e regressão
- **Arquivos:** nenhum.
- **Mudança:** nenhuma; verificação.
- **Validar:** `pytest` (na raiz) → todos os testes verdes, sem avisos; `pytest
  --durations=5` sem teste lento; `flask run` sobe e `/api/saude` → 200; os scripts
  descartáveis das Etapas 1 a 5 → `TUDO OK` (banco no ar); `flask db migrate` → "No
  changes in schema detected"; `requirements.txt` inalterado; `pip check` limpo;
  sem segredo em arquivo versionável; banco vazio ao final.

### Tarefa 10 — Atualizar a documentação
- **Arquivos:** `plano.md`, `CLAUDE.md`, esta spec
- **Mudança:**
  - `plano.md`: marcar a Etapa 6 como concluída com as decisões (arredondamento,
    taxa composta, aportes no fim do mês, entrada como capital inicial,
    `meses_para_meta` com horizonte 60, pacote `calculo`, `pytest` em
    `requirements-dev.txt`); na Etapa 7, registrar que ela cria a composição dos
    cenários (`cenarios`), expõe o modo "dado o aporte" como parâmetro do
    `/resultado`, documenta a última parcela ajustada e usa `valor_entrada` como
    capital inicial do fundo; na Etapa 10, reaproveitar o `pytest`; na Etapa 11, o
    container instala só o `requirements.txt`;
  - `CLAUDE.md`: estrutura (`services/calculo/`, `tests/`), convenções de cálculo
    (percentual na entrada, 50 dígitos em contexto local, `ROUND_HALF_UP` por
    parcela e última com o resíduo, fundo sem arredondar no meio e aporte
    `ROUND_CEILING`, taxa composta, aportes postecipados, `float` recusado), como
    instalar e rodar os testes, a regra de pureza (garantida por teste) e "Estado
    atual" (há suíte `pytest` para os cálculos; a API segue sem testes
    automatizados até a Etapa 10);
  - esta spec: marcar os critérios de aceite e o status como implementada.
- **Validar:** reler os três arquivos e conferir que não restam menções a "sem
  suíte de testes automatizada" como estado atual nem a `app/services/financiamento.py`.

### Tarefa 11 — Conferência final
- **Arquivos:** nenhum.
- **Mudança:** nenhuma; verificação de todos os critérios de aceite.
- **Validar:** percorrer a lista de critérios, informar o que passou, mostrar o
  resultado do `pytest` e o `git status --short` final (esperado:
  `app/services/calculo/`, `tests/`, `pytest.ini`, `requirements-dev.txt` e
  documentação) e aguardar você pedir o commit.
