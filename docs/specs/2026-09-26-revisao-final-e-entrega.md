# Revisão final e entrega (Etapa 13) — Spec

**Criado em:** 2026-09-26
**Status:** Em implementação (2026-09-26) — Tarefas 1 a 7 concluídas; faltam o commit e o *push* (Tarefa 8, do autor) e a verificação a partir do GitHub (Tarefa 9)
**Origem:** Etapa 13 de `plano.md`; requisito R10 (repositório público por módulo, estrutura clara, nomes seguindo boas práticas) e a conferência do checklist R1 a R10

## Problema
As Etapas 0 a 12 entregaram a aplicação, os testes, o Swagger, o Dockerfile e o README, mas **falta fechar o projeto**: conferir, requisito por requisito, que tudo o que o trabalho exige está atendido **e visível para quem avaliar**, limpar o que sobrou (código morto, documentos desatualizados) e deixar a entrega pública e reproduzível. Sem essa etapa, o projeto pode estar pronto e, ainda assim, ser avaliado com um documento de proposta que contradiz o código, com código morto ou com um repositório sem descrição. O repositório do **frontend** é outro módulo e **está fora do escopo desta etapa** (decisão do autor).

Estado verificado (2026-09-26, lendo o repositório, o histórico do git e o GitHub sem autenticação):

- **Checklist (do `CLAUDE.md`), com a evidência atual:**

  | Req. | Situação | Evidência |
  |---|---|---|
  | R1 / R5 | atendido | 16 rotas (POST, PUT, DELETE e GET), Swagger em `/apidocs/`; 1055 testes |
  | R2 | atendido | `README.md` do Rota Financeira e o fluxograma em `docs/img/` (PNG/SVG/`.dot`) |
  | R3 | atendido | `Dockerfile` (imagem de produção validada nas Etapas 11 e 12) |
  | R4 | atendido | JWT com isolamento por usuário, `/resultado` e `/parcelas`, índices do BACEN com cache |
  | R7 | atendido | BACEN/SGS (API externa própria, consumida pelo backend); a integração com o BACEN atende o requisito) |
  | R8 | atendido | Swagger e README, com licença, cadastro e rotas |
  | R10 | atendido | backend público, estrutura e nomes conferidos nesta etapa;|

- **GitHub (acesso anônimo):** `erbraga/rota_financeira-backend` é **público** (`private: false`), `main` == `origin/main`
  (nenhum commit pendente, árvore limpa), 13 commits; o README e a imagem abrem pelo endereço público; **sem descrição, sem tópicos,
  sem licença e sem tags**. O repositório do frontend (`erbraga/rota_financeira-frontend`), citado no README, responde **HTTP 404** sem autenticação
  (o autor informou que é privado); **não faz parte desta etapa** e não é verificado nem alterado aqui.
- **Segredos:** o histórico está limpo — nenhum `.env`, `.env.docker` ou chave em qualquer commit; a chave JWT do `.env` local aparece em **0**
  commits; nenhuma URL de banco com senha real. Ficam **fora** do git (e continuam ignorados): `.env`, `.env.docker`, `CLAUDE.md`,
  `.claude/`, `requisitos back-end.md` e `tmp/` (arquivos de outro assunto: `carros.txt`, `fiat.txt`, `ideia.md`, `marcas.txt`, `citroen`).
- **Estrutura e nomes:** 98 arquivos versionados; a árvore segue a proposta (seção 8.1: `app/{models,routes,services,schemas,integrations}`,
  `migrations/`, `config.py`, `run.py`) mais `tests/`, `docs/` e os arquivos Docker. **Todo arquivo Python está em `snake_case`**; os únicos
  nomes com hífen são documentos e arquivos convencionais (`Dockerfile`, `README.md`, `docker-entrypoint.sh`, `requirements*.txt`,
  `proposta-backend-api-rest.md` e as specs em `docs/specs/AAAA-MM-DD-nome.md`).
- **Código morto:** uma varredura (AST) achou **2 imports sem uso**: `Decimal` em `app/schemas/resultado.py` e `date` em
  `app/integrations/bacen.py`. Os demais "imports sem uso" dos models são anotações de tipo em `TYPE_CHECKING` (legítimos). Nenhuma função ou
  classe de nível superior sem referência.
- **Dependências:** as 11 do `requirements.txt` estão em uso (o `psycopg` como driver da `DATABASE_URL`, o `gunicorn` no *entrypoint* do
  contêiner); o `requirements-dev.txt` só acrescenta o `pytest`. **Nada a remover.**
- **Documento de proposta desatualizado:** o `proposta-backend-api-rest.md` (público) ainda descreve a **Selic** (linhas 33, 46, 135 e
  a rota `/api/indices/selic`), a **FIPE** (linha 95), a tabela **`parcelas_calculadas`** (não criada), **"Marshmallow ou Pydantic"** e
  **APScheduler** — pontos em que o projeto final decidiu de outro modo.
- **Pendências abertas no `plano.md`:** apenas as 4 tarefas da própria Etapa 13; o `CLAUDE.md` tem o R10 como "pendente (frontend)". Os dois textos ainda
  trazem a frase "confirmar com o professor que o BACEN atende o R7" (`plano.md`, seção "Riscos"; `CLAUDE.md`, item R7), que **deixa de valer** e é
  removida na Tarefa 6.
- **Fluxo público de desenvolvimento:** as specs em `docs/specs/` (públicas) e o `.gitignore`/`.dockerignore` citam o Claude Code
  como ferramenta de desenvolvimento; o `CLAUDE.md` (ignorado) diz que **não há IA no produto final**.

## Objetivo
Fechar o trabalho: conferir formalmente o checklist R1 a R10 com evidência atual, confirmar o R10 do backend (repositório público, estrutura e
nomes), corrigir o que a revisão apontar (código morto, proposta desatualizada), deixar o repositório público apresentável
e provar que **o que está no GitHub** — e não só a cópia local — instala e roda seguindo o README.

## Fora de escopo
- Qualquer funcionalidade nova, mudança de contrato, de schema ou de dependência (a Etapa 13 só limpa e confere).
- O **repositório do frontend** (código, README, visibilidade e o link para ele): é outro módulo, **fora do escopo desta etapa** por decisão do autor; o link no README fica como está e não é verificado aqui.
- CI/CD, *badges*, implantação em nuvem, HTTPS e domínio.
- Reescrever o histórico do git (o histórico está limpo, nada a remover).
- Reescrever ou remover testes existentes.

## Proposta

### 1. Checklist R1 a R10 com evidência
Uma tabela final (no `plano.md` e refletida no `CLAUDE.md`) com, para cada requisito, **o comando ou arquivo que prova** o atendimento,
executada de novo (rotas × Swagger, `pytest` completo, `docker build`, links do README).

### 2. R10: repositórios, estrutura e nomes
- **Estrutura e nomes:** conferência final da árvore contra a proposta (seção 8.1) e dos nomes (decisão 5); o `tmp/` local, que não é versionado,
  não entra na entrega.
- **Apresentação do repositório público:** descrição curta e tópicos do GitHub (texto sugerido por mim; quem aplica é você, pela interface do
  GitHub) e, conforme a decisão 4, um arquivo `LICENSE`.

### 3. Limpeza
- **Código morto:** remover os 2 imports sem uso (decisão 3), com a suíte inteira como prova de que nada mudou.
- **Proposta desatualizada:** tratar o `proposta-backend-api-rest.md` (decisão 2).
- **Dependências e segredos:** nova confirmação, no estado final, de que nada do `requirements.txt` sobra e de que nenhum segredo está no
  repositório nem no histórico.

### 4. Entrega verificável
- **Prova a partir do GitHub:** depois do *push* (feito por você), um `git clone` **anônimo** do repositório público numa pasta nova e a execução do
  README dali (caminho local até o `pytest -m "not integracao"` e o `docker build`), para garantir que o publicado é o que foi validado.
- **Marcação da entrega:** sem tag (decisão 6): a versão entregue é o **commit final da `main`**, e o plano registra o hash dele.
- **Registro:** `plano.md` e `CLAUDE.md` com o estado final (todas as etapas concluídas, R1 a R10).

### Casos de borda relevantes
- **Commits e *push*:** eu não faço `git add`/`commit`/`push` nem crio tags sem você pedir; o plano diz **quando** commitar e o que publicar.
- **Mudanças de última hora:** qualquer alteração depois da validação (mesmo de um import) exige rodar de novo a suíte e a conferência do README.
- **Documentos públicos:** o que sai no repositório não pode conter a senha do banco nem a chave JWT (confirmado no histórico e a reconfirmar).
- **Nomes de doc × Python:** o R10 pede `snake_case` para arquivos Python; o `Dockerfile` e o `README.md` seguem convenções estabelecidas.

## Decisões em aberto
1. ~~**Repositório do frontend (link do README)**~~ — **RESOLVIDA (2026-09-26): (a), com o escopo ajustado pelo
   autor**: o repositório `erbraga/rota_financeira-frontend` existe com esse nome e é privado; o **README continua como está**
   (com o link). Tornar o frontend público é assunto do **outro módulo** e **está fora do escopo desta etapa**: não é uma
   tarefa, um critério de aceite nem uma pendência do R10 do backend.
2. ~~**O `proposta-backend-api-rest.md` desatualizado**~~ — **RESOLVIDA (2026-09-26): (b)**: **reescrever as
   seções divergentes** para a proposta refletir o **projeto final** (documento "vivo"): Selic fora (só CDI e IPCA, séries 4389
   e 13522), FIPE fora (`valor_veiculo` sempre informado), sem a tabela `parcelas_calculadas` (amortização calculada sob demanda),
   Marshmallow (sem Pydantic), sem APScheduler (cache sob demanda), rotas e contrato reais (16 rotas, `/parcelas`, `/resultado`,
   `/api/indices/{cdi|ipca}`), estrutura de pastas e tecnologias atuais. O que **não** diverge fica como está. Como a mudança
   apaga o registro do que foi proposto originalmente, o histórico continua disponível no git (`git log` do arquivo).
3. ~~**Código morto (2 imports sem uso)**~~ — **RESOLVIDA (2026-09-26): (a)**: remover os dois
   (`Decimal` em `app/schemas/resultado.py` e `date` em `app/integrations/bacen.py`); mudança sem efeito em
   comportamento, provada pela suíte completa (1055 testes) e pela varredura AST sem achados.
4. ~~**Licença do repositório**~~ — **RESOLVIDA (2026-09-26): (a)**: **não adicionar** arquivo `LICENSE`
   (trabalho acadêmico; o R10 não exige); o README passa a dizer, na seção "Autoria", que **não há licença de reuso
   definida** (a ODbL citada é a dos dados do Banco Central, não a do código).
5. ~~**Nomes com hífen em documentos**~~ — **RESOLVIDA (2026-09-26): (a)**: **manter** (são documentos, não
   código; todo arquivo Python já está em `snake_case`; renomear quebraria os vínculos entre `plano.md`, `CLAUDE.md`,
   o README e as specs).
6. ~~**Como marcar a versão entregue**~~ — **RESOLVIDA (2026-09-26): (b)**: **só o estado da `main`**, sem
   tag e sem branch de entrega; o commit final da `main` é a versão entregue, e o critério de aceite passa a ser
   `main` local == `origin/main`, árvore limpa e o clone anônimo daquele commit funcionando.
7. ~~**Como ficou o uso do Claude Code (transparência)**~~ — **RESOLVIDA (2026-09-26): (b)**: **não mencionar**
   no README; o uso da ferramenta continua visível apenas nas specs públicas em `docs/specs/`.

## Critérios de aceite
- [x] O **checklist R1 a R10** está conferido **de novo**, com evidência executada nesta etapa (16 rotas × Swagger, `pytest` completo, `docker build`,
      README seguido do zero), e registrado no `plano.md` e no `CLAUDE.md`; **nenhum requisito fica com pendência** (o R7 e o R10
      estão atendidos).
- [ ] **R10 — backend:** o repositório do backend está **público** (verificado por acesso anônimo, no fim); o repositório do frontend fica fora do
      escopo (decisão do autor).
- [x] **Estrutura e nomes:** a árvore confere com a proposta (seção 8.1) e todo arquivo Python está em `snake_case`; nada de arquivo estranho na
      árvore versionada (`tmp/` e afins seguem fora).
- [x] **Limpeza:** sem imports sem uso (varredura AST sem achados, exceto os de `TYPE_CHECKING`), nenhuma dependência sobrando no `requirements.txt`, e
      o `proposta-backend-api-rest.md` tratado conforme a decisão 2.
- [x] **Segredos:** nenhum segredo no repositório nem em nenhum commit (busca no histórico repetida no estado final), `.env.example` e
      `.env.docker.example` só com marcadores.
- [ ] **Entrega verificável:** depois do *push*, um `git clone` **anônimo** do repositório público, numa pasta nova, segue o README (instalação local e
      `docker build`) e passa `pytest -m "not integracao"`; a `main` local e a remota estão iguais e a árvore está limpa; o hash do commit
      final da `main` (a versão entregue) está registrado no `plano.md`.
- [x] `pytest` completo continua verde (1055 testes); `flask db migrate` sem mudanças; `requirements*.txt` inalterados (nenhuma dependência nova).
- [x] `plano.md` e `CLAUDE.md` com o estado final: **todas as etapas concluídas** (a 9 eliminada), R1 a R10 (todos atendidos) e
      como reproduzir a entrega.

---

## Plano de Implementação

Tarefas na ordem de execução. **Eu não faço `git add`, `git commit`, `git push` nem crio tags**: o commit e o *push* são a
**Tarefa 8, sua**, e as verificações a partir do GitHub (Tarefa 9) vêm depois. Pré-requisitos: `.venv` ativo, raiz do projeto como
diretório de trabalho, Docker em execução, banco de desenvolvimento no ar (`docker start rota-financeira-db`) e acesso à rede.
A validação combina o `pytest` completo, scripts descartáveis no diretório temporário da sessão (varredura AST, comparações entre
documentos e código, busca no histórico do git), `docker build` e acessos **anônimos** ao GitHub (`curl` sem autenticação).

Detalhes de projeto que o plano fixa (não estavam explícitos na spec):
- **Reescrita da proposta (decisão 2):** mantém o título, a numeração das seções (1 a 11) e o tom; troca apenas o que diverge. O link
  para o "frontend (SPA React)" passa a apontar para o repositório do frontend (a `proposta-frontend-spa-react.md` **não** está neste
  repositório). Uma linha no topo informa que o documento foi **atualizado em 2026-09-26 para refletir o projeto entregue** (o texto original
  fica no histórico do git). A seção 11 vira **"Etapas realizadas"**, apontando para o `plano.md`.
- **Fonte de cada fato da proposta reescrita:** o código e o Swagger (rotas × `/apispec.json`; colunas e tipos × `app/models/`;
  tecnologias e versões × `requirements.txt`; regras de cálculo × `services/calculo/`); nada é escrito "de memória".
- **O hash da versão entregue não vai para o `plano.md`:** um arquivo não pode conter o hash do commit que o inclui. O relatório final
  (Tarefa 10) informa o hash de `origin/main` **verificado** (igual à `main` local, com a árvore limpa). É um ajuste do critério de aceite da spec.
- **Recursos descartáveis** da verificação a partir do clone: `rf-final-*` (contêiner e rede do PostgreSQL) e uma pasta temporária; tudo
  removido ao fim (`docker rm -fv`, sem `volume prune`).
- Se uma verificação apontar defeito real, a tarefa **para** e o problema é relatado antes de qualquer correção.

### Tarefa 1 — Reescrever a proposta do backend (decisão 2)
- **Arquivos:** `proposta-backend-api-rest.md`
- **Mudança:** atualizar as seções divergentes: **cabeçalho** (link do frontend e linha "atualizado em 2026-09-26"); **1** e **2**
  (CDI e IPCA, sem Selic; fundo com "taxa informada, com sugestão de CDI"); **3** (índices CDI e IPCA; o "opcional" vira "fora do escopo entregue":
  CET, paginação, ordenação e filtros); **4** (regras de cálculo reais: Decimal, arredondamento ao centavo com a última parcela absorvendo o resíduo,
  aportes ao fim do mês, capital inicial = entrada da simulação, aporte arredondado para cima, modo "dado o aporte" até 60 meses, `custo_total` = "o que se
  paga pelo carro"); **5** (SGS: séries **4389** e **13522**, sem cadastro, cache de 12 h, janela de 60 meses, fallback e 503); **6** (tipos e colunas reais,
  `valor_veiculo` informado pelo usuário, **sem** `parcelas_calculadas`, `indice` CDI/IPCA com `SELIC` reservado, restrições e `ON DELETE RESTRICT`);
  **7** (as **16 rotas** reais, com `saude`, `perfil`, `/parcelas`, `/resultado`, `/api/indices/{cdi|ipca}`, regras e erros); **8** (Marshmallow, sem
  APScheduler, gunicorn, Docker, pytest, `python-dotenv`, `psycopg`; estrutura de pastas real); **9** (requisitos não funcionais com o que existe hoje e os
  débitos conhecidos: sem *rate limiting*, banco fora do ar com 500 genérico); **10** (ajuste de texto) e **11** ("Etapas realizadas", com a Etapa 9
  eliminada).
- **Validar:** script que confere a proposta contra o projeto: as rotas listadas na seção 7 são **exatamente** as 16 do `/apispec.json`; as tabelas e colunas
  da seção 6 coincidem com os models (nomes e tipos); as tecnologias da seção 8 estão no `requirements*.txt` (e nada a mais); **nenhuma** ocorrência de
  `parcelas_calculadas`, `Pydantic`, `APScheduler`, `/selic` ou FIPE como recurso do projeto (só como "fora do escopo", se citados); links relativos existentes;
  o `git diff` mostra que o que não divergia continua igual.

### Tarefa 2 — Remover os imports sem uso (decisão 3)
- **Arquivos:** `app/schemas/resultado.py`, `app/integrations/bacen.py`
- **Mudança:** remover `from decimal import Decimal` (o comentário do topo de `resultado.py` sobre `Decimal` fica) e `date` da linha `from datetime import ...`
  de `bacen.py` (mantendo `datetime` e `timedelta`).
- **Validar:** a varredura AST sem achados (exceto os de `TYPE_CHECKING`); `pytest` completo (1055) verde; `flask db migrate` sem mudanças; `git diff` só com
  essas duas linhas.

### Tarefa 3 — README: nota de licença (decisão 4)
- **Arquivos:** `README.md`
- **Mudança:** na seção "Autoria", uma frase: o projeto não define licença de reuso (a ODbL citada na seção da API externa é a dos **dados** do Banco Central, não a do
  código).
- **Validar:** o mesmo *script* de consistência da Etapa 12 (links relativos existentes, âncoras, títulos sem salto, blocos com linguagem, tabelas sem coluna a
  mais) e a tabela de rotas ainda idêntica ao `/apispec.json`; os blocos de código do README **inalterados** (então a execução do zero da Etapa 12 continua
  valendo).

### Tarefa 4 — Checklist R1 a R10 com evidência executada
- **Arquivos:** nenhum (a tabela vai para o `plano.md` na Tarefa 7)
- **Mudança:** nenhuma; conferir cada requisito **agora**: R1/R5 (16 rotas por método POST, PUT, DELETE e GET, a partir do `/apispec.json`, e o Swagger abrindo);
  R2 (README e imagem: existem, abrem, links); R3 (`docker build -t rota-financeira-api .` sem aviso, usuário não-root, sem `.env*`, `tests` ou `pytest` na imagem);
  R4 (JWT com isolamento, `/resultado`, `/parcelas` e índices: testes correspondentes passando); R7/R8 (BACEN real respondendo e o texto do README igual ao do Swagger);
  R10 (estrutura, nomes e visibilidade, conforme as Tarefas 5 e 9).
- **Validar:** cada linha com o comando executado e o resultado; nenhuma linha sem evidência atual (o R7 consta como atendido, sem pendência de confirmação).

### Tarefa 5 — Estrutura, nomes, segredos e dependências
- **Arquivos:** nenhum
- **Mudança:** nenhuma; repetir as varreduras no estado final.
- **Validar:** árvore versionada × proposta (seção 8.1) atualizada; todo `.py` em `snake_case` (e diretórios sem maiúscula ou hífen); nenhum arquivo estranho versionado
  (`git ls-files`), `tmp/` e demais ignorados **fora** do git; **histórico do git** sem `.env`, `.env.docker` ou chave (nome de arquivo e conteúdo: chave JWT do
  `.env` local em 0 commits, nenhuma URL de banco com senha real, nenhum `POSTGRES_PASSWORD=` com valor); `.env.example` e `.env.docker.example` só com
  marcadores; nenhuma dependência sobrando (cada pacote do `requirements.txt` importado ou usado pelo Docker); nenhuma dependência nova.

### Tarefa 6 — Documentação
- **Arquivos:** `plano.md`, `CLAUDE.md`, esta spec
- **Mudança:**
  - `plano.md`: marcar a Etapa 13 como concluída, com a **tabela final do checklist R1 a R10** (evidências da Tarefa 4), as decisões (proposta reescrita, imports
    removidos, sem `LICENSE`, nomes mantidos, sem tag, sem menção ao Claude Code no README) e a nota de que o repositório do frontend é outro módulo, fora do escopo; **remover** o item "tornar público o repositório do
    frontend" da lista da Etapa 13 e o "Levado adiante" da Etapa 12 sobre o 404 do frontend; **remover** da seção
    "Riscos" a frase "confirmar isso com o professor" sobre o R7 (o requisito está atendido); a linha "Verificações pós-publicação (clone anônimo) estão no relatório da entrega";
  - `CLAUDE.md`: estado final ("todas as etapas concluídas; a 9 foi eliminada"), R1 a R10 (todos atendidos) e como reproduzir a entrega; remover
    "falta a 13" e o "Pendente (Etapa 13)" do R10 (passa a "atendido"; o repositório do frontend é outro módulo) e a frase
    "(Confirmar com o professor que o BACEN atende o R7.)" do item R7;
  - esta spec: marcar os critérios de aceite e o status como implementada (menos os que dependem da Tarefa 9, marcados só depois dela).
- **Validar:** reler os três arquivos e conferir que não restam menções a "Etapa 13 pendente" nem a "README a reescrever".

### Tarefa 7 — Regressão antes do commit
- **Arquivos:** nenhum
- **Mudança:** nenhuma.
- **Validar:** `pytest` completo (1055) verde; `flask db migrate` sem mudanças; `pip check`; `requirements*.txt` inalterados; `docker build` sem aviso; `git status --short` só com
  o esperado (`proposta-backend-api-rest.md`, `README.md`, os 2 arquivos de código, `plano.md` e a spec); nenhum segredo nos arquivos alterados.

### Tarefa 8 — Commit e publicação (sua)
- **Arquivos:** nenhum
- **Mudança:** entregar o roteiro: `git status`, `git add` dos arquivos listados, `git commit` (mensagem sugerida) e `git push origin main`; e, no GitHub, (opcional) preencher a **descrição** e os **tópicos** do repositório do backend (texto sugerido por mim).
- **Validar:** você confirma ("feito" ou "funcionou"); só então sigo para a Tarefa 9.

### Tarefa 9 — Verificação a partir do GitHub (sem autenticação)
- **Arquivos:** nenhum
- **Mudança:** nenhuma; acessos anônimos e um clone limpo: (1) `curl` sem autenticação no repositório do **backend** (200) e no README e na imagem; (2) `git rev-parse main` ==
  `git rev-parse origin/main` e árvore limpa; (3) `git clone` **anônimo** (`https://github.com/erbraga/rota_financeira-backend.git`) numa pasta nova; (4) no clone, seguir o README:
  venv, `pip install -r requirements.txt` e `-r requirements-dev.txt`, `.env` (senha e chave geradas na hora, sem imprimir), PostgreSQL descartável `rf-final-*` (as trocas de nome, porta
  e volume, como na Etapa 12), `flask db upgrade`, `flask run` com o fluxo curto (registrar → resultado → `/api/indices/cdi` com o BACEN real), `pytest -m "not integracao"` e o `pytest`
  completo, e `docker build` a partir do clone; (5) busca de segredos no histórico do clone.
- **Validar:** tudo passa a partir do que está **publicado**; remover os recursos `rf-final-*` e a pasta temporária; o repositório do frontend **não é verificado** (fora do escopo).

### Tarefa 10 — Conferência final e relatório
- **Arquivos:** nenhum
- **Mudança:** nenhuma; verificação de todos os critérios de aceite.
- **Validar:** percorrer a lista de critérios, informando o que passou, o que dependeu de você (commit e *push*); relatar o **hash de `origin/main`** (a
  versão entregue), o resultado do `pytest` e o `git status --short` final.

---
*Depois de aprovada, esta spec vira a base do PLANO — não escrever
código antes disso.*
