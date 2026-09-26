# README e fluxograma da arquitetura (Etapa 12) — Spec

**Criado em:** 2026-09-26
**Status:** Implementada (2026-09-26) — README executado do zero (local e Docker) e revisado pelo autor
**Origem:** Etapa 12 de `plano.md`; requisitos R2 (README com instalação e **imagem de fluxograma da arquitetura**) e R8 (documentar a API externa: licença, cadastro e rotas)

## Problema
O `README.md` do repositório ainda é o do projeto anterior (`manutencao-api`, SQLite, rotas
`/recuperar`, `/alterar-item/{id}`), então **descreve outra aplicação** e não atende o **R2**: não tem o
título e a descrição corretos, as instruções de instalação do Rota Financeira (PostgreSQL, variáveis,
migrations, Docker) nem a **imagem (fluxograma) da arquitetura**, que é obrigatória. A API externa
(BACEN/SGS, **R8**) já está documentada no Swagger, mas não no README. Quem abrir o repositório no
GitHub hoje não consegue entender nem subir o projeto.

Estado verificado (2026-09-26, lendo o repositório e o ambiente):

- **README atual:** 180 linhas, seções "Descrição", "Instalação", "Como executar", "Como executar com Docker",
  "Como utilizar", "Persistência dos dados" e "Tecnologias utilizadas", todas do `manutencao-api`
  (inclusive o link de download do zip e o Docker com SQLite). Escrito em português, com títulos, listas e
  tabelas de rotas; nenhuma linha se aplica ao projeto atual.
- **Repositório:** `origin` = `https://github.com/erbraga/rota_financeira-backend`; o histórico já traz as
  etapas até o `Dockerfile`. `docs/` só tem `specs/` (**não existe** `docs/img/`). O `CLAUDE.md` é ignorado pelo
  git, então o README **não pode depender dele** (nem repetir segredos).
- **O que já existe e o README deve refletir (fontes da verdade: o código e o Swagger):**
  - **16 rotas** sob `/api` (saúde, autenticação, 5 de simulações, `/resultado`, 4 de financiamentos,
    `/parcelas`, índices `cdi` e `ipca`); `/apidocs/` (Swagger UI) e `/apispec.json` (OpenAPI 3.0.2);
  - **API externa:** BACEN/SGS, séries **4389** (CDI) e **13522** (IPCA), sem cadastro, cache de 12 h e
    janela de 60 meses; o texto do **R8 já está no Swagger** (`SWAGGER_TEMPLATE`), com a ressalva de que a licença
    ODbL está confirmada no catálogo do portal para outras séries mas **não** listada individualmente para
    4389 e 13522 — o README deve repetir isso sem afirmar além do verificado;
  - **Comandos verificados:** ambiente virtual e `pip install -r requirements.txt`; `.env` a partir do
    `.env.example` (variáveis obrigatórias e opcionais); PostgreSQL 18 em contêiner avulso
    (`docker run` com `--env` lidas do `.env`, **sem senha no comando**); `flask db upgrade`; `flask run`
    e `gunicorn run:app`; `pytest` (com o banco de teste `bd_test`); Docker da API (`docker build`, rede
    `rota-financeira-net`, `.env.docker`, `docker run`), tudo validado nas Etapas 10 e 11;
  - **Contrato do `/resultado`** (custo total = "o que se paga pelo carro", `menor_custo`, séries com `null`,
    modo `?aporte_mensal=`) descrito no `CLAUDE.md` e no Swagger.
- **Ferramentas para a imagem:** `dot` (Graphviz 2.43) instalado e gerando **PNG e SVG** com acentuação
  (fontes DejaVu presentes); **não há** Mermaid CLI, ImageMagick, Inkscape, PIL nem matplotlib. O `node` está
  instalado, mas não é necessário.
- **Referências:** o R2 exige o fluxograma **"ilustrando um cenário de uso"**; a proposta do backend (seção 8) lista
  a arquitetura em camadas (`routes`, `services`, `schemas`, `integrations`, PostgreSQL) e o frontend é **outro
  repositório** (SPA React) que só fala com a API por HTTP/JSON.

## Objetivo
Substituir o README por um documento que apresente o Rota Financeira, mostre a arquitetura numa **imagem
(fluxograma) de um cenário de uso real**, permita a qualquer pessoa **instalar e executar** o backend (local e
em Docker), e documente a **API externa** (R8), as rotas e o contrato principal — sem duplicar o Swagger e
sem expor segredos.

## Fora de escopo
- Qualquer alteração de código, contrato, banco ou dependência (só documentação e a imagem).
- O README do **frontend** (outro repositório) e a integração entre os dois.
- Arquivo `LICENSE`, *badges*, CI, publicação e conferência do checklist R1–R10 (**Etapa 13**).
- Capturas de tela do Swagger ou do frontend; tradução para inglês; *wiki*.
- Instruções de implantação em nuvem (deploy), HTTPS e proxy reverso.
- Reescrever `CLAUDE.md`/`plano.md` além do registro da conclusão da etapa.

## Proposta

### Arquivos (raiz do repositório)
```
README.md                 # reescrito do zero (o atual é do manutencao-api)
docs/img/arquitetura.dot  # fonte do fluxograma (Graphviz), versionada
docs/img/arquitetura.png  # imagem usada no README (R2)
docs/img/arquitetura.svg  # versão vetorial (opcional, decisão 1)
```
`requirements*.txt` e o código **não mudam**; o Graphviz é ferramenta de desenho usada uma vez, não
dependência do projeto.

### Estrutura do README (em português, como o restante do projeto)
1. **Título e descrição:** Rota Financeira — Backend; o que faz (compara **à vista**, **financiado** Price/SAC e
   **à vista no futuro com fundo**, com taxas do Banco Central); contexto acadêmico (PUC-Rio); o que há neste
   repositório (só o backend) e onde fica o frontend.
2. **Arquitetura:** a imagem do fluxograma (R2), a legenda do cenário passo a passo e a descrição das camadas
   (`routes` → `services`/`services/calculo` → `models`/PostgreSQL, `schemas`, `integrations/bacen`).
3. **Tecnologias:** tabela curta (Python 3.12, Flask, SQLAlchemy/Alembic, PostgreSQL, JWT, Marshmallow, Flasgger,
   gunicorn, Docker, pytest) com o papel de cada uma.
4. **Pré-requisitos e instalação local:** Python 3, PostgreSQL (via Docker), `git clone`, ambiente virtual,
   `pip install -r requirements.txt`, `.env` a partir do `.env.example`, subir o banco (`docker run` sem senha
   no comando), migrations.
5. **Variáveis de ambiente:** tabela (obrigatórias `DATABASE_URL` e `JWT_SECRET_KEY`; opcionais
   `JWT_ACCESS_TOKEN_EXPIRES_MINUTOS`, `CORS_ORIGINS`, `FLASK_DEBUG`, `BACEN_URL_BASE`, `BACEN_TIMEOUT_SEGUNDOS`,
   `INDICES_TTL_HORAS`, `TEST_DATABASE_URL`) e a regra "nunca versionar o `.env`".
6. **Como executar:** `flask run` (desenvolvimento), `gunicorn run:app`, e onde abrir `/apidocs/`.
7. **Executar com Docker:** `docker build`, rede, `.env.docker`, `docker run`, parar e limpar (os comandos da
   Etapa 11), com o aviso de que a senha só vai no arquivo local.
8. **Testes:** `pytest`, `pytest -m "not integracao"` e `pytest -m integracao`, o banco `bd_test` e a trava do sufixo
   `_test`.
9. **API externa (R8):** BACEN/SGS, séries 4389 e 13522, URLs consumidas, **sem cadastro**, licença (com a
   ressalva verificada), consumo **pelo backend** (o cliente nunca é redirecionado), cache de 12 h e
   comportamento com o BACEN fora do ar.
10. **Rotas e contrato:** tabela das 16 rotas (método, caminho, descrição, autenticação), resumo do
    contrato de `/resultado` e de `/api/indices/<índice>` e o link para o Swagger (`/apidocs/`), que é o contrato completo.
11. **Estrutura de pastas** e **autoria**.

### O fluxograma (R2)
- **Cenário ilustrado:** o usuário compara como comprar um carro (detalhes na decisão 2), com setas numeradas:
  (1) login e token JWT; (2) taxas sugeridas: a API consulta o **cache no PostgreSQL** e, se estiver vencido (12 h), busca a
  série no **BACEN/SGS** e grava; (3) criação da simulação e das opções de financiamento; (4) `GET .../resultado`: a API lê o
  banco, calcula Price, SAC e fundo e devolve os totais, o `menor_custo` e as séries; (5) o frontend só exibe.
- **Elementos:** usuário/navegador, **frontend SPA** (outro repositório), **API Flask** (com JWT, rotas, serviços de cálculo,
  cliente do BACEN), **PostgreSQL** (4 tabelas), **BACEN/SGS** (externo), Swagger UI; destaque para o que fica dentro do
  contêiner Docker.
- Gerado por Graphviz a partir de um `.dot` versionado (reprodutível: `dot -Tpng` / `dot -Tsvg`), com fontes que
  suportam acentos e contraste legível no fundo claro e escuro do GitHub.

### Casos de borda relevantes
- **Segredos:** nenhum exemplo com senha ou chave real; `troque-esta-senha` e comandos que **leem** o `.env`
  (`set -a; source .env; set +a`) em vez de repetir valores.
- **Consistência:** todo comando do README é **executado do zero** numa cópia limpa (não copiado de memória); rota,
  variável e porta batem com o código, o `.env.example`, o `.env.docker.example` e o Swagger.
- **Links relativos:** a imagem e os links internos funcionam no GitHub (`docs/img/arquitetura.png`).
- **Licença do BACEN:** sem afirmar que as séries 4389/13522 têm licença listada; dizer o que foi verificado.
- **Numeração das rotas:** o README lista as **16** rotas reais (sem `selic`, sem `GET` de uma opção só).
- **Plataformas:** os comandos são de `bash` (Linux/macOS); no Windows, WSL ou Docker (decisão 5).

## Decisões em aberto
1. ~~**Ferramenta e formato do fluxograma**~~ — **RESOLVIDA (2026-09-26): (a)**: **Graphviz** (`dot`, já
   instalado): o `docs/img/arquitetura.dot` fica versionado e o **PNG** (usado no README) e o **SVG** (vetorial) são gerados
   dele (`dot -Tpng` / `dot -Tsvg`), sem dependência nova no projeto.
2. ~~**Uma ou duas imagens**~~ — **RESOLVIDA (2026-09-26): (a)**: **uma** imagem que junta a arquitetura
   (componentes) com o **cenário numerado** (setas 1 a 5), com a legenda passo a passo no README; sem imagem de
   sequência separada.
3. ~~**Profundidade da documentação das rotas no README**~~ — **RESOLVIDA (2026-09-26): (a)**: tabela das
   16 rotas (método, caminho, descrição, autenticação) + resumo do contrato de `/resultado` e de
   `/api/indices/<índice>` + link para o Swagger (`/apidocs/`), que é o contrato completo; sem exemplos `curl`.
4. ~~**Link do repositório do frontend**~~ — **RESOLVIDA (2026-09-26): (a)**: o README cita o frontend com link
   para **https://github.com/erbraga/rota_financeira-frontend** (informado pelo autor), na descrição e na legenda
   do fluxograma. **Verificação (2026-09-26):** um acesso anônimo à URL devolve **HTTP 404** — o GitHub responde 404 tanto para
   repositório inexistente quanto para **privado**; se for privado (ou ainda não publicado), o R10 (repositório
   **público**) exige torná-lo público até a entrega. O link entra no README como informado e a conferência final de que
   ele abre para qualquer pessoa fica para a Etapa 13.
5. ~~**Sistemas operacionais dos comandos de instalação**~~ — **RESOLVIDA (2026-09-26): (a)**: comandos de
   **Linux/macOS (bash)**, com a nota de que no Windows se usa **WSL** ou o caminho **Docker** (independe do
   shell); só entra no README o que foi executado aqui; sem passos de PowerShell.

## Critérios de aceite
- [x] O `README.md` é **do Rota Financeira** (nenhuma menção a `manutencao-api`, SQLite ou às rotas antigas) e traz **título,
      descrição, instalação, execução (local e Docker), variáveis, testes, API externa, rotas e estrutura**, bem formatado
      (cabeçalhos, listas, tabelas, blocos de código).
- [x] A **imagem do fluxograma** existe em `docs/img/`, abre no README (link relativo, também no GitHub), ilustra **um cenário
      de uso** com os componentes reais (frontend, API, PostgreSQL, BACEN/SGS) e é legível (texto com acentos, contraste); o
      arquivo-fonte permite regerá-la e o resultado regerado é idêntico ao versionado.
- [x] A seção da **API externa** cita BACEN/SGS, as **duas rotas** (séries 4389 e 13522), a ausência de cadastro, a licença
      (com a ressalva verificada) e o consumo pelo backend (R8), e **bate** com o texto do Swagger.
- [x] A **tabela de rotas** lista as **16** rotas reais (conferida contra `/apispec.json`) e o link `/apidocs/` funciona; o resumo do
      contrato de `/resultado` (custo total, `menor_custo`, séries com `null`, `aporte_mensal`) confere com o Swagger.
- [x] **Seguindo o README do zero** numa cópia limpa do repositório (pasta nova, sem `.venv` nem `.env`) — venv,
      `pip install`, `.env`, banco em contêiner, `flask db upgrade`, `flask run` — a API **sobe** e `/api/saude`, `/apidocs/` e
      um fluxo curto (registrar, login, simulação, resultado, índice) funcionam; o caminho **Docker** do README também
      funciona do zero (com banco descartável).
- [x] Nenhum segredo nem senha no README nem na imagem; comandos que dependem de senha **leem** o `.env`/`.env.docker`;
      `git status` só com `README.md`, `docs/img/*`, a spec e o `plano.md`.
- [x] `pytest` completo continua verde (1055 testes); `flask db migrate` sem mudanças; `requirements*.txt` inalterados; `plano.md` e
      `CLAUDE.md` atualizados (Etapa 12 concluída, onde estão o README e a imagem, como regerá-la).

---

## Plano de Implementação

Tarefas na ordem de execução. Nenhuma faz `git add`/`commit`/`push` (só quando você pedir).
Pré-requisitos: `.venv` ativo, raiz do projeto como diretório de trabalho, Docker em execução, `dot` (Graphviz) instalado e
acesso à rede (BACEN real e `pip install` nas Tarefas 5 e 6). A validação combina: a **imagem inspecionada visualmente**
(abro o PNG), **scripts descartáveis** no diretório temporário da sessão que comparam o README com o código (rotas × `/apispec.json`,
variáveis × `config.py` e `.env.example`), e a **execução literal do README do zero** numa cópia limpa do repositório, com
recursos descartáveis `rf-readme-*` (nada toca o banco de desenvolvimento). Os testes (`pytest`) seguem como regressão.

Detalhes de projeto que o plano fixa (não estavam explícitos na spec):
- **Fluxograma** (`docs/img/arquitetura.dot`, `rankdir=LR`, fundo **branco opaco** para legibilidade no tema escuro do GitHub,
  fonte DejaVu Sans, `dpi=150`): usuário → **frontend SPA** (aglomerado "outro repositório") → **contêiner Docker "API Flask
  (gunicorn)"** com os blocos `routes + JWT`, `schemas`, `services/calculo` e `integrations/bacen` → **PostgreSQL** (as 4 tabelas)
  e **BACEN/SGS** (séries 4389 e 13522, externo); Swagger UI ligada à API. Setas **numeradas de 1 a 5** do cenário da spec, cores
  distintas para os componentes e para o que é externo. O cabeçalho do `.dot` traz o comando para regenerar
  (`dot -Tpng -Gdpi=150 arquitetura.dot -o arquitetura.png` e `dot -Tsvg ... -o arquitetura.svg`).
- **README** em português, títulos `#`/`##`/`###`, tabelas e blocos de código com a linguagem indicada; links **relativos**
  (`docs/img/arquitetura.png`, `.env.example`, `.env.docker.example`, `Dockerfile`); sem `<br>` decorativo. Fatos vêm do código:
  versões do `requirements.txt`, rotas de `/apispec.json`, variáveis de `config.py`.
- **Comandos do README = comandos executados:** o `docker run` do PostgreSQL usa `set -a; source .env; set +a` e `-e
  POSTGRES_USER -e POSTGRES_PASSWORD -e POSTGRES_DB` (nunca a senha escrita). Na validação, para não colidir com o banco de
  desenvolvimento em uso, **só** são trocados o nome do contêiner (`rf-readme-db`), a porta do host (5433) e o volume; as
  trocas são listadas no relatório da tarefa.
- **Autoria:** GitHub `erbraga` (link do backend e do frontend informado pelo autor); nenhum outro dado pessoal.
- Se um comando do README **falhar** no teste do zero, a tarefa **para**: o texto (ou, se for defeito real, o projeto) é
  corrigido e o teste **recomeça do início**.

### Tarefa 1 — Fluxograma da arquitetura
- **Arquivos:** `docs/img/arquitetura.dot`, `docs/img/arquitetura.png`, `docs/img/arquitetura.svg`
- **Mudança:** escrever o `.dot` como acima e gerar o PNG e o SVG com o Graphviz.
- **Validar:** `dot` sem avisos; **abrir o PNG e conferir** cada elemento (componentes, setas 1 a 5, legendas, acentos, contraste) e
  ajustar o `.dot` até ficar legível; o PNG tem largura utilizável no README (≈ 1600–2200 px) e menos de 500 KB; **regerar duas
  vezes** e comparar os hashes (idêntico ao versionado); o SVG abre e mantém o texto selecionável.

### Tarefa 2 — README, parte 1: apresentação e arquitetura
- **Arquivos:** `README.md` (reescrito do zero)
- **Mudança:** título e descrição (com o link do frontend), seção **Arquitetura** com a imagem e a legenda dos 5 passos, descrição das
  camadas, tabela de **tecnologias** (versões do `requirements.txt`) e **estrutura de pastas**.
- **Validar:** nenhuma menção a `manutencao-api`, SQLite ou às rotas antigas (`grep`); a imagem aparece (caminho relativo existe);
  as versões da tabela batem com o `requirements.txt`; a estrutura de pastas bate com `ls`/`git ls-files`.

### Tarefa 3 — README, parte 2: instalação, variáveis, execução e testes
- **Arquivos:** `README.md`
- **Mudança:** pré-requisitos (Python 3.12, Docker), `git clone`, ambiente virtual, `pip install -r requirements.txt`, `.env` a partir
  do `.env.example`, subir o PostgreSQL 18 em contêiner (sem senha no comando), `flask db upgrade`, `flask run`/`gunicorn run:app`,
  **tabela de variáveis** (obrigatórias e opcionais) e a seção **Testes** (`pytest`, `-m "not integracao"`, `-m integracao`, `bd_test`,
  `TEST_DATABASE_URL`); nota de Linux/macOS (bash) e Windows (WSL ou Docker).
- **Validar:** script que extrai as variáveis de `config.py` e do `.env.example` e confirma que **todas** estão na tabela (e só
  elas), com o padrão e a obrigatoriedade corretos; nenhum valor de senha ou chave real no texto (`grep` da senha e da chave do
  `.env` local e da validação).

### Tarefa 4 — README, parte 3: Docker, API externa e rotas
- **Arquivos:** `README.md`
- **Mudança:** seção **Executar com Docker** (`docker build`, rede, `.env.docker`, `docker run`, parar e limpar, o aviso da senha),
  seção **API externa (R8)** (BACEN/SGS, séries 4389 e 13522, as duas URLs, sem cadastro, licença com a ressalva verificada, consumo pelo
  backend, cache de 12 h e comportamento com o BACEN fora do ar) e **Rotas e contrato** (tabela das 16 rotas, resumo de `/resultado` e de
  `/api/indices/<índice>`, link para `/apidocs/`).
- **Validar:** script que lê a tabela do README e compara com o `/apispec.json`: **exatamente** as 16 rotas (método, caminho,
  autenticação); a seção da API externa **bate** com o texto do Swagger (nomes, séries, URLs, "sem cadastro", 12 h, 60 meses); os
  comandos Docker são idênticos aos do `CLAUDE.md` (fonte validada na Etapa 11).

### Tarefa 5 — README do zero: caminho local
- **Arquivos:** nenhum (cópia limpa no diretório temporário)
- **Mudança:** copiar o repositório **sem `.venv`, `.env`, `.git` nem caches** (`git ls-files -co --exclude-standard`) para uma pasta nova e
  **seguir o README à risca**: venv, `pip install`, `.env` (senha e chave geradas na hora, sem imprimir), PostgreSQL em contêiner
  (com as três trocas da validação), `flask db upgrade`, `flask run`; depois o fluxo curto por HTTP (registrar, login, simulação, opção,
  resultado, `GET /api/indices/cdi` **com o BACEN real**), `pytest -m "not integracao"` e `pytest` completo (que cria o `bd_test` no
  banco descartável).
- **Validar:** cada passo funciona **sem ajuste fora do README**; `/api/saude` → `ok`, `/apidocs/` → 200, o fluxo curto passa, os
  1055 testes passam na cópia; anotar qualquer divergência e corrigir o texto (recomeçando do início se algo mudar).

### Tarefa 6 — README do zero: caminho Docker
- **Arquivos:** nenhum
- **Mudança:** na mesma cópia limpa, seguir a seção Docker: `docker build`, rede `rota-financeira-net` (nome do README, sem colisão
  porque o banco descartável usa outro nome de contêiner e o de desenvolvimento não é ligado à rede), `.env.docker` a partir do
  `.example` (host do banco descartável, senha e chave geradas na hora), `docker run`, fluxo curto e encerramento com a limpeza que o README
  ensina.
- **Validar:** a API sobe `healthy` e responde ao fluxo curto; ao final, os comandos de limpeza do README **removem tudo** (contêiner,
  rede, volume); nada de `rf-readme-*` ou `rota-financeira-net` sobra em `docker ps -a`, `network ls` e `volume ls`.

### Tarefa 7 — Consistência e regressão
- **Arquivos:** nenhum
- **Mudança:** nenhuma; verificação final e limpeza.
- **Validar:** `README.md`: links relativos existem, hierarquia de títulos sem saltos, blocos de código com linguagem, tabelas com o mesmo
  número de colunas em todas as linhas; nenhum segredo (senha/chave do `.env`, da validação e `POSTGRES_PASSWORD=` com valor) no README
  nem na imagem (`strings` do PNG/SVG); `pytest` completo (1055) verde; `flask db migrate` sem mudanças; `requirements*.txt` inalterados;
  `git status` só com `README.md`, `docs/img/*`, a spec e o `plano.md`; recursos e pasta temporários removidos.

### Tarefa 8 — Revisão do autor (sua)
- **Arquivos:** nenhum
- **Mudança:** você lê o README e abre a imagem (na prévia do editor, ou no GitHub depois do *push*), conferindo texto, tom, fluxo do cenário
  e o que faltar.
- **Validar:** você confirma ("funcionou") ou pede ajustes (que são aplicados e revalidados nas partes afetadas).

### Tarefa 9 — Documentação
- **Arquivos:** `plano.md`, `CLAUDE.md`, esta spec
- **Mudança:**
  - `plano.md`: marcar a Etapa 12 como concluída, com as decisões (Graphviz, uma imagem, tabela de rotas sem `curl`, link do frontend, bash) e o
    que passa para a Etapa 13 (o repositório do **frontend** devolveu 404 anônimo: torná-lo público e conferir o link);
  - `CLAUDE.md`: remover "README é resquício de outro projeto"; registrar onde estão o README e a imagem, **como regenerar** o fluxograma
    (`dot`), a regra "todo comando do README foi executado" e o "Estado atual" (Etapas 0 a 8 e 10 a 12; **R2 e R8 atendidos**);
  - esta spec: marcar os critérios de aceite e o status como implementada.
- **Validar:** reler os três arquivos e conferir que não restam menções a "README a reescrever" nem a "Etapa 12 pendente".

### Tarefa 10 — Conferência final
- **Arquivos:** nenhum
- **Mudança:** nenhuma; verificação de todos os critérios de aceite.
- **Validar:** percorrer a lista de critérios, informar o que passou e o que dependeu da sua verificação, mostrar o resultado do `pytest` e o
  `git status --short` final e aguardar você pedir o commit.

---
*Depois de aprovada, esta spec vira a base do PLANO — não escrever
código antes disso.*
