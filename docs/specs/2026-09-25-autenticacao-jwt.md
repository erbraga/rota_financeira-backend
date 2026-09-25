# Autenticação: registro e login com JWT (Etapa 3) — Spec

**Criado em:** 2026-09-25
**Status:** Implementada em 2026-09-25
**Origem:** Etapa 3 de `plano.md`; seções 3.1, 7.1 e 9 de `proposta-backend-api-rest.md`

## Problema
Hoje a API não tem nenhuma forma de identificar quem a usa. Estado verificado:

- **Código:** só existe `GET /api/saude` (pública). `app/routes/` tem apenas
  `saude.py`; **não** existem `app/schemas/` nem `app/services/`.
- **Banco:** a tabela `usuarios` já existe (Etapa 2): `id` (`IDENTITY`), `nome`
  `VARCHAR(120)`, `email` `VARCHAR(254)` com `UNIQUE` (`uq_usuarios_email`),
  `senha_hash` `VARCHAR(255)` e `criado_em`. Ninguém grava nela ainda.
- **JWT:** o `JWTManager` está registrado (`app/extensions.py`) e a chave vem
  de `JWT_SECRET_KEY` (validada em `config.py`), mas nenhuma rota emite ou
  exige token, e não há callbacks de erro.
- **Erros:** `app/errors.py` já padroniza `{"erro": ..., "detalhes": ...}` para
  `HTTPException` e erros inesperados, mas **não** trata erros de validação nem
  os erros do Flask-JWT-Extended.
- **Marshmallow** está decidido, mas ainda **não instalado**
  (`requirements.txt` tem 10 dependências; versão atual no PyPI: 4.3.1).
- **Frontend** (`proposta-frontend-spa-react.md`): telas `/registrar` e
  `/login`; o token JWT fica no estado de autenticação, vai em
  `Authorization: Bearer <token>` e **"resposta 401 encerra a sessão e leva ao
  login"**.
- **Verificações exploratórias** (scripts descartáveis, sem criar arquivos), com
  Flask-JWT-Extended 4.7.4, PyJWT 2.15.0 e Werkzeug 3.1.8:
  - a expiração padrão do token é de **15 minutos**;
  - `create_access_token(identity=1)` (inteiro) gera um token que a própria
    biblioteca **rejeita** com 422 "Subject must be a string": o `sub` precisa
    ser texto (`"1"`);
  - respostas padrão de erro do JWT: sem cabeçalho → 401
    `{"msg": "Missing Authorization Header"}`; token malformado → **422**
    `{"msg": "Not enough segments"}`; token expirado → 401
    `{"msg": "Token has expired"}`; esquema diferente de Bearer → 401 em inglês.
    Formato e idioma fora do padrão do projeto;
  - `werkzeug.security.generate_password_hash` gera `scrypt` (162 caracteres,
    cabe em `VARCHAR(255)`), leva ~72 ms por hash, e não exige dependência nova.

## Objetivo
Permitir criar uma conta e autenticar por e-mail e senha, devolvendo um token
JWT que identifica o usuário nas rotas protegidas das próximas etapas, com erros
de autenticação e validação no formato padrão do projeto.

## Fora de escopo
- CRUD de simulações e de opções de financiamento (Etapas 4 e 5); aqui só se
  prepara o **helper** que devolve o usuário do token.
- Logout no servidor e revogação de tokens (o token é sem estado; o frontend
  descarta o token para sair), *refresh token* e "lembrar de mim".
- Recuperação/troca de senha, confirmação de e-mail, edição ou exclusão de
  conta, papéis e permissões.
- Limitação de tentativas de login (*rate limiting*) — ver decisão 11.
- Testes automatizados (`pytest` entra na Etapa 6); a validação é manual e por
  scripts descartáveis, como nas etapas anteriores.
- Qualquer alteração de schema: a tabela `usuarios` já atende (sem migration).
- O código do frontend.

## Proposta

### Endpoints (todos sob `/api/auth`, documentados em OpenAPI 3)

| Método e rota | Acesso | Corpo | Resposta de sucesso |
|---|---|---|---|
| `POST /api/auth/registrar` | pública | `{"nome", "email", "senha"}` | `201` com o usuário (sem senha) |
| `POST /api/auth/login` | pública | `{"email", "senha"}` | `200` com o token |
| `GET /api/auth/perfil` | JWT | — | `200` com o usuário do token (decisão 8) |

Exemplo de sucesso do registro (`201`), com as recomendações aplicadas:
```json
{"id": 1, "nome": "Ana Souza", "email": "ana@exemplo.com", "criado_em": "2026-09-25T21:00:00-03:00"}
```
Exemplo de sucesso do login (`200`):
```json
{"access_token": "eyJ...", "token_type": "Bearer", "expires_in": 3600,
 "usuario": {"id": 1, "nome": "Ana Souza", "email": "ana@exemplo.com"}}
```
Erros (formato `{"erro": ..., "detalhes": ...}` da Etapa 1):

| Situação | Status | Corpo |
|---|---|---|
| Campo ausente, vazio, longo/curto demais, e-mail inválido, campo desconhecido | 422 | `{"erro": "Dados inválidos", "detalhes": {"email": ["..."]}}` |
| Corpo que não é JSON válido ou não é um objeto | 400 | `{"erro": "Corpo da requisição deve ser um objeto JSON"}` |
| `Content-Type` diferente de JSON | 415 | mensagem padrão do projeto |
| E-mail já cadastrado | 409 | `{"erro": "E-mail já cadastrado"}` |
| Credenciais inválidas (e-mail inexistente **ou** senha errada) | 401 | `{"erro": "Credenciais inválidas"}` (mesma mensagem nos dois casos) |
| Token ausente, malformado, expirado ou de usuário inexistente | 401 | `{"erro": "..."}` + `WWW-Authenticate: Bearer` |

### Arquivos
```
app/
  routes/auth.py          # blueprint `auth`: registrar, login, perfil (só HTTP)
  schemas/__init__.py
  schemas/auth.py         # Marshmallow: RegistroSchema, LoginSchema, UsuarioSchema
  services/__init__.py
  services/auth.py        # registrar_usuario, autenticar, usuario_atual
app/errors.py             # + handler de ValidationError (422) e callbacks do JWT (401)
app/routes/__init__.py    # registra o blueprint auth
app/__init__.py           # SWAGGER_TEMPLATE ganha os schemas; registra os callbacks do JWT
config.py                 # JWT_ACCESS_TOKEN_EXPIRES a partir do ambiente
.env.example              # nova variável opcional de expiração
requirements.txt          # + marshmallow (única dependência nova)
```
Sem migration. `schemas/` e `services/` nascem aqui (antes do previsto no
plano) porque esta etapa é a primeira a usá-los.

### Regras de negócio
- **Registro:**
  1. O schema valida e normaliza: `nome` (sem espaços nas pontas, 2 a 120
     caracteres), `email` (formato válido, até 254 caracteres, **minúsculas e sem
     espaços nas pontas** — obrigação da Etapa 2) e `senha` (política da
     decisão 4; **não** se remove espaço da senha).
  2. O serviço gera o hash (decisão 5) e grava o usuário. Não há consulta
     prévia: a unicidade é garantida pelo banco, e a violação de
     `uq_usuarios_email` vira `409`. Qualquer outra violação de integridade não é
     mascarada (segue como erro 500 registrado no log).
  3. A resposta nunca contém `senha_hash` nem a senha.
- **Login:** o e-mail é normalizado do mesmo jeito. Se o usuário não existir,
  o serviço ainda confere a senha contra um hash fictício, para que o tempo de
  resposta não revele se o e-mail existe. Falha → `401 Credenciais inválidas`
  (mesma mensagem sempre). Sucesso → `create_access_token(identity=str(usuario.id))`
  com o prazo da decisão 1; o token leva só o `sub` (mais os campos padrão).
- **Usuário do token (`usuario_atual`):** helper para as rotas protegidas
  seguintes: lê o `sub`, converte para inteiro, busca o `Usuario` no banco e, se
  não existir mais, responde `401` (token de conta excluída). Nunca se confia em
  `usuario_id` vindo do corpo (regra do `CLAUDE.md`).
- **Campos desconhecidos** no corpo são **rejeitados** (422), para acusar erros
  de contrato e tentativas de enviar campos como `id` ou `criado_em`.

### Erros de validação e de JWT (`app/errors.py`)
- Um handler global de `marshmallow.ValidationError` devolve
  `422 {"erro": "Dados inválidos", "detalhes": <mensagens por campo>}`. Vale para
  todas as etapas seguintes; as mensagens **não** repetem o valor enviado
  (a senha não aparece em resposta nem em log).
- Callbacks do Flask-JWT-Extended, todos em `{"erro": ...}` com `401` e o
  cabeçalho `WWW-Authenticate: Bearer` (decisão 7): token ausente / esquema
  errado → "Token de autenticação ausente"; token inválido (assinatura, formato,
  `sub` inválido) → "Token inválido"; expirado → "Token expirado".

### Configuração
- `JWT_ACCESS_TOKEN_EXPIRES`: `timedelta` a partir da variável opcional
  `JWT_ACCESS_TOKEN_EXPIRES_MINUTOS` (padrão da decisão 1). Valor não numérico ou
  menor que 1 falha na subida com mensagem clara, no mesmo estilo do
  `config.py`. O `.env.example` documenta a variável.

### Documentação (OpenAPI 3)
Docstrings Flasgger nas 3 rotas (modelo: `app/routes/saude.py`), com
`requestBody`, exemplos, todas as respostas de erro da tabela (`$ref` para o
schema `Erro`) e `security: - BearerAuth: []` em `perfil`. Os schemas
reutilizáveis (`RegistroRequisicao`, `LoginRequisicao`, `LoginResposta`,
`Usuario`) entram em `SWAGGER_TEMPLATE` (decisão 9).

### Fluxo principal
1. `POST /api/auth/registrar` → 201.
2. `POST /api/auth/login` → 200 com o token.
3. No Swagger UI, **Authorize** → colar só o token → `GET /api/auth/perfil` → 200
   com o usuário; sem token → 401.

### Casos de borda
- **E-mail com maiúsculas ou espaços** (`" Ana@Exemplo.COM "`): normalizado; o
  segundo cadastro do "mesmo" e-mail dá 409.
- **Cadastros simultâneos com o mesmo e-mail:** o segundo bate no `UNIQUE` e
  responde 409 (sem condição de corrida, por não haver consulta prévia).
- **Nome só com espaços**, senha curta/longa, campos nulos ou de tipo errado
  (número, lista): 422 por campo.
- **Corpo vazio, texto solto ou array:** 400; **sem `Content-Type: application/json`:** 415.
- **Senha:** aceita espaços e caracteres Unicode; limite máximo para evitar
  requisições enormes. Como o scrypt custa ~72 ms de CPU e memória por hash,
  registro e login são pontos naturais de abuso (ver decisão 11).
- **Token de usuário excluído** ou assinado com outra chave: 401.
- **Cabeçalho `Authorization` com esquema errado** (`Basic ...`): 401.
- **Banco fora do ar** em registro/login/perfil: erro 500 genérico (a rota de
  saúde é que informa 503); tratar `OperationalError` globalmente fica como
  débito, fora desta etapa.
- **`sub` numérico:** o token sempre é gerado com o id **como texto**; um token
  assim gerado por outro código seria rejeitado (401 "Token inválido").
- **CORS:** o cabeçalho `Authorization` já é aceito no preflight (verificado na
  Etapa 1).
- **401 no login x frontend:** credenciais erradas também respondem 401, e o
  frontend trata 401 como "sessão encerrada". O cliente precisa **não**
  redirecionar em loop quando o 401 vier da própria tela de login; ajuste do
  frontend, registrado no contrato.
- **Compatibilidade:** Marshmallow 4.x com Flask 3.1 e as demais versões
  instaladas; se surgir incompatibilidade real, parar e perguntar antes de fixar
  versões.

## Decisões tomadas
1. ~~**Expiração do token**~~ — **RESOLVIDA (2026-09-25): (a)** padrão de
   **60 minutos**, configurável pela variável opcional
   `JWT_ACCESS_TOKEN_EXPIRES_MINUTOS`. Sem *refresh token*.
2. ~~**Resposta do registro**~~ — **RESOLVIDA (2026-09-25): (a)** `201` com
   os dados do usuário (`id`, `nome`, `email`, `criado_em`) e **sem** token; só o
   login emite token. Se o frontend quiser "já entrar logado", chama o login
   logo após o registro.
3. ~~**Resposta do login**~~ — **RESOLVIDA (2026-09-25): (a)**
   `{"access_token", "token_type": "Bearer", "expires_in": <segundos>,
   "usuario": {"id", "nome", "email"}}`. Nunca inclui `senha_hash`.
4. ~~**Política de senha**~~ — **RESOLVIDA (2026-09-25): (a)** 8 a 128
   caracteres, sem regras de composição; aceita espaços e Unicode e não altera
   a senha (sem `strip`). A mensagem de erro não repete o valor enviado.
5. ~~**Hash da senha**~~ — **RESOLVIDA (2026-09-25): (a)**
   `werkzeug.security` (`generate_password_hash`/`check_password_hash`, scrypt),
   sem dependência nova.
6. ~~**Status dos erros de validação**~~ — **RESOLVIDA (2026-09-25): (a)**
   **422** com `detalhes` por campo para dados inválidos; **400** para corpo que
   não é JSON válido ou não é um objeto; **415** para `Content-Type` que não é
   JSON. Vale para todas as etapas.
7. ~~**Erros do JWT**~~ — **RESOLVIDA (2026-09-25): (a)** tudo em **401**
   `{"erro": ...}` com `WWW-Authenticate: Bearer`, inclusive o token
   malformado (que a biblioteca devolve como 422): "Token de autenticação
   ausente", "Token inválido" e "Token expirado".
8. ~~**Rota `GET /api/auth/perfil`**~~ — **RESOLVIDA (2026-09-25): (a)**
   incluir, com o nome **`perfil`**: devolve o usuário do token (acréscimo à
   proposta, a registrar no `CLAUDE.md`). Serve de rota protegida real para a
   validação do *Authorize* e exercita o helper `usuario_atual`.
9. ~~**Schemas no Swagger**~~ — **RESOLVIDA (2026-09-25): (a)** escritos à
   mão em `SWAGGER_TEMPLATE` e referenciados por `$ref`, como o `Erro`
   (`RegistroRequisicao`, `LoginRequisicao`, `LoginResposta`, `Usuario`); sem
   `apispec`. As regras de validação são escritas juntas nos dois lugares e
   conferidas na revisão de cada etapa.
10. ~~**E-mail já cadastrado**~~ — **RESOLVIDA (2026-09-25): (a)** `409
    {"erro": "E-mail já cadastrado"}`, vindo da violação de `uq_usuarios_email`.
    Risco de enumeração de contas aceito para o MVP (o login não vaza essa
    informação).
11. ~~**Força bruta no login**~~ — **RESOLVIDA (2026-09-25): (a)** só
    mitigar a enumeração por tempo (hash fictício quando o e-mail não existe) e
    registrar o *rate limiting* como débito técnico no `CLAUDE.md`. Sem
    `Flask-Limiter` nesta etapa.

## Critérios de aceite
- [x] `POST /api/auth/registrar` com dados válidos → 201, corpo sem `senha_hash`
      nem senha, e a linha em `usuarios` guarda um hash `scrypt` (nunca a senha).
- [x] O e-mail é gravado em minúsculas e sem espaços; repetir o cadastro com
      outra grafia do mesmo e-mail → 409 `{"erro": "E-mail já cadastrado"}`; o
      `uq_usuarios_email` é a única fonte da verificação.
- [x] Corpos inválidos (campos ausentes, e-mail inválido, senha fora do
      tamanho, nome vazio, tipos errados, campo desconhecido) → 422 com
      `detalhes` por campo, sem eco da senha; JSON malformado ou não objeto →
      400; sem `Content-Type` JSON → 415.
- [x] `POST /api/auth/login` correto → 200 com `access_token`, `token_type`,
      `expires_in` e `usuario`; senha errada e e-mail inexistente → 401 com a
      **mesma** mensagem; o tempo de resposta dos dois casos é da mesma ordem.
- [x] O `sub` do token é o id **como texto**, e a expiração respeita a variável
      de ambiente (conferida decodificando o token e com um valor alterado).
- [x] `GET /api/auth/perfil`: 200 com token válido; 401 (formato `{"erro": ...}`
      e cabeçalho `WWW-Authenticate: Bearer`) sem token, com token malformado
      (não 422), com token expirado, assinado com outra chave, com `sub` inválido,
      com esquema `Basic` e com token de usuário excluído.
- [x] No Swagger UI (`/apidocs/`), as 3 rotas aparecem com exemplos e
      respostas; **Authorize** com só o token faz o `perfil` responder 200
      (verificação manual, no navegador).
- [x] Variável de expiração inválida (texto ou < 1) falha na subida com
      mensagem clara; sem a variável, vale o padrão da decisão 1.
- [x] `flask run` e `/api/saude` continuam funcionando; `flask db migrate` não
      detecta mudanças (nenhum schema alterado).
- [x] A única dependência nova é `marshmallow` no `requirements.txt`, com
      versão fixada e `pip check` limpo; nenhum segredo ou senha em arquivo
      versionável.
- [x] Os usuários de teste são removidos do banco ao final; `plano.md` e
      `CLAUDE.md` atualizados (estrutura, `usuario_atual`, formato dos erros de
      validação e do JWT, débito de *rate limiting*).

---
*Depois de aprovada, esta spec vira a base do PLANO — não escrever
código antes disso.*

## Plano de Implementação

Tarefas na ordem de execução. Nenhuma faz `git add`/`commit`/`push` (só quando
você pedir). Scripts de teste e servidores auxiliares ficam no diretório
temporário da sessão, nunca no projeto. Pré-requisitos de todas: `.venv` ativo,
raiz do projeto como diretório de trabalho e o banco no ar
(`docker start rota-financeira-db`). Como ainda não há suíte automatizada, a
validação é por `python -c`, scripts descartáveis, `curl`, `psql` no container e
o Swagger UI no navegador (verificação manual sua).

Pontos de atenção que o plano incorpora:
- O `sub` do token **precisa ser texto** (verificado: com inteiro, a própria
  biblioteca rejeita o token). O código sempre usa `str(usuario.id)` na criação e
  `int(...)` na leitura.
- As mensagens padrão do Marshmallow são em **inglês** ("Missing data for
  required field."): todas as mensagens de campo são redefinidas em português e a
  validação confere que nenhuma mensagem em inglês vaza.
- O scrypt custa ~72 ms por hash; o hash fictício do login é calculado **uma
  vez**, na primeira necessidade, e reutilizado.
- O `login` só exige senha presente e com tamanho máximo (128, para recusar
  requisições enormes); a política de 8 a 128 vale apenas no registro.
- Todo usuário criado nos testes é removido; o banco termina com `usuarios`
  vazia.

### Tarefa 1 — Dependência `marshmallow`
- **Arquivos:** `requirements.txt`
- **Mudança:** acrescentar `marshmallow==4.3.1` (única dependência nova da
  etapa) e instalar.
- **Validar:** `pip install -r requirements.txt` sem erro; `pip check` limpo;
  `python -c "import marshmallow; print(marshmallow.__version__)"` → 4.3.1;
  `git diff -- requirements.txt` mostra só essa linha.

### Tarefa 2 — Expiração do token na configuração
- **Arquivos:** `config.py`, `.env.example`
- **Mudança:** `Config.JWT_ACCESS_TOKEN_EXPIRES` (`timedelta`) lida da variável
  opcional `JWT_ACCESS_TOKEN_EXPIRES_MINUTOS` (padrão 60; texto ou valor menor
  que 1 → erro claro no estilo do `config.py`); documentar a variável (comentada)
  no `.env.example`.
- **Validar:** `python -c "import config; print(config.Config.JWT_ACCESS_TOKEN_EXPIRES)"`
  → `1:00:00`; com a variável em `15` → `0:15:00`; com `abc`, `0` e `-5` a
  importação falha com a mensagem esperada; `git status` não lista o `.env`.

### Tarefa 3 — Schemas de autenticação e leitura do corpo
- **Arquivos:** `app/schemas/__init__.py`, `app/schemas/auth.py`
- **Mudança:** `RegistroSchema` (nome sem espaços nas pontas, 2 a 120; e-mail
  válido, até 254, normalizado para minúsculas e sem espaços; senha de 8 a 128,
  sem alterar espaços), `LoginSchema` (e-mail normalizado; senha obrigatória, não
  vazia, até 128), `UsuarioSchema` (`id`, `nome`, `email`, `criado_em`, só saída)
  e uma variante resumida (`id`, `nome`, `email`); todos rejeitam campos
  desconhecidos, com **todas as mensagens em português**. Um helper em
  `app/schemas/__init__.py` lê o corpo da requisição: 415 se não for JSON, 400
  ("Corpo da requisição deve ser um objeto JSON") se o JSON for inválido ou não
  for objeto, e devolve os dados validados pelo schema recebido.
- **Validar:** script descartável que carrega os schemas com casos válidos e
  inválidos e confere: `" Ana@Exemplo.COM "` → `ana@exemplo.com`; nome só com
  espaços, nome de 1 e de 121 caracteres, e-mail inválido/longo, senha de 7 e de
  129 caracteres, campos ausentes, tipos errados (número, lista, `null`) e campo
  desconhecido geram erro **por campo**; senha com espaços nas pontas é
  preservada; **nenhuma mensagem em inglês** nem eco do valor da senha; o helper
  (com uma rota temporária em memória) responde 415, 400 (JSON quebrado e
  array) e 422 conforme a tabela da spec.

### Tarefa 4 — Handler de validação e callbacks do JWT
- **Arquivos:** `app/errors.py`, `app/__init__.py`
- **Mudança:** handler global de `marshmallow.ValidationError` →
  `422 {"erro": "Dados inválidos", "detalhes": {...}}`; callbacks do
  Flask-JWT-Extended (token ausente/esquema errado, inválido, expirado) →
  `401 {"erro": "..."}` com `WWW-Authenticate: Bearer`; ambos registrados por
  `create_app()`.
- **Validar:** script descartável com uma rota protegida temporária **em
  memória**: sem cabeçalho, `Basic ...`, token `abc`, token expirado, token
  assinado com outra chave e token com `sub` inteiro → todos 401 no formato
  `{"erro": ...}` (mensagens "ausente"/"inválido"/"expirado" corretas) e com o
  cabeçalho `WWW-Authenticate: Bearer`; um `ValidationError` levantado numa rota
  temporária → 422 com `detalhes`; token válido → 200.

### Tarefa 5 — Serviço de autenticação
- **Arquivos:** `app/services/__init__.py`, `app/services/auth.py`
- **Mudança:** `registrar_usuario` (hash com `werkzeug.security`, grava, e trata
  **só** a violação de `uq_usuarios_email` como `EmailJaCadastrado`, sem consulta
  prévia), `autenticar` (confere o hash; e-mail inexistente compara contra um
  hash fictício reutilizado e levanta o mesmo `CredenciaisInvalidas` da senha
  errada), criação do token (`sub` = `str(id)`, prazo da configuração, devolve
  também `expires_in` em segundos) e `usuario_atual` (lê o `sub`, converte para
  inteiro, busca o usuário e responde 401 "Token inválido" se o `sub` for
  inválido ou a conta não existir mais).
- **Validar:** script descartável em contexto da aplicação: cadastro grava hash
  com prefixo `scrypt` e e-mail em minúsculas; segundo cadastro com outra grafia
  do e-mail → `EmailJaCadastrado` (e a sessão continua utilizável); outra
  violação de integridade **não** é mascarada; `autenticar` correto devolve o
  usuário, senha errada e e-mail inexistente levantam a mesma exceção e levam
  tempos da mesma ordem (dezenas de milissegundos, sem diferença de ordem de
  grandeza); o token decodificado tem `sub` texto e `exp - iat` = 3600 s;
  `usuario_atual` devolve o usuário e dá 401 para conta excluída. Remover os
  usuários criados.

### Tarefa 6 — Schemas do Swagger
- **Arquivos:** `app/__init__.py`
- **Mudança:** acrescentar a `SWAGGER_TEMPLATE` os schemas `RegistroRequisicao`,
  `LoginRequisicao`, `LoginResposta` e `Usuario`, com exemplos e as regras de
  validação escritas junto das do Marshmallow (decisão 9).
- **Validar:** `python -c` que carrega `/apispec.json` pelo `test_client` e
  confere que os 4 schemas existem em `components.schemas`, ao lado de `Erro`; a
  aplicação continua criando.

### Tarefa 7 — Rotas `registrar`, `login` e `perfil`
- **Arquivos:** `app/routes/auth.py`, `app/routes/__init__.py`
- **Mudança:** blueprint `auth` (prefixo `/api/auth`) com as 3 rotas finas —
  leem o corpo pelo helper, chamam o serviço, traduzem `EmailJaCadastrado` em 409
  e `CredenciaisInvalidas` em 401 — e docstrings OpenAPI 3 completas (exemplos,
  todas as respostas de erro com `$ref` para `Erro`, `security: BearerAuth` em
  `perfil`); registrar o blueprint em `registrar_blueprints`.
- **Validar:** `flask routes` lista as 3 rotas com os métodos corretos;
  `/apispec.json` contém os 3 caminhos com `requestBody`/respostas; `flask run`
  sobe sem erro.

### Tarefa 8 — Validação ponta a ponta com `curl`
- **Arquivos:** nenhum no projeto.
- **Mudança:** nenhuma; verificação com o servidor rodando e um script
  descartável para gerar tokens inválidos.
- **Validar:**
  - registro válido → 201 sem `senha_hash`/senha; no `psql`, `senha_hash` começa
    com `scrypt:` e o e-mail está em minúsculas e sem espaços; repetir com outra
    grafia → 409 `{"erro": "E-mail já cadastrado"}`;
  - 422 com `detalhes` por campo (campo ausente, e-mail inválido, senha de 7 e
    de 129 caracteres, nome vazio, tipo errado, campo desconhecido) sem eco da
    senha; JSON quebrado e array → 400; sem `Content-Type` JSON → 415;
  - login → 200 com `access_token`, `token_type`, `expires_in` (3600) e
    `usuario`; senha errada e e-mail inexistente → 401 com a mesma mensagem
    (`Credenciais inválidas`) e tempos da mesma ordem;
  - token decodificado (sem verificar assinatura): `sub` em texto, prazo de 3600 s;
    reiniciando com `JWT_ACCESS_TOKEN_EXPIRES_MINUTOS=5` → `expires_in` 300;
  - `perfil`: 200 com token válido; 401 no formato `{"erro": ...}` e com
    `WWW-Authenticate: Bearer` sem token, com `abc` (não 422), expirado,
    assinado com outra chave, `sub` inválido, esquema `Basic` e token de usuário
    **excluído**;
  - o log do servidor não contém a senha usada nos testes (`grep`);
  - variável de expiração inválida derruba a subida com mensagem clara.
  Ao final, remover os usuários de teste.

### Tarefa 9 — Validação manual no Swagger UI (sua)
- **Arquivos:** nenhum.
- **Mudança:** nenhuma; eu subo o servidor e você confere no navegador.
- **Validar:** em `/apidocs/`: as 3 rotas aparecem com exemplos e respostas;
  *Try it out* de `registrar` (201) e de `login` (200, copiar o `access_token`);
  **Authorize** colando **só o token** e `GET /api/auth/perfil` → 200; sem
  autorizar → 401. Se a página falhar, parar e avisar antes de mudar o esquema
  do Swagger.

### Tarefa 10 — Regressão e conferência de dependências
- **Arquivos:** nenhum.
- **Mudança:** nenhuma; verificação.
- **Validar:** `flask run` sobe; `/api/saude` → 200; `/apidocs/` → 200;
  `flask db migrate` → "No changes in schema detected" (nenhum schema alterado);
  `pip check` limpo; `git diff -- requirements.txt` só com o `marshmallow`;
  busca por senha/chave do `.env` em arquivos versionáveis sem resultados;
  `usuarios` vazia (`SELECT count(*)`).

### Tarefa 11 — Atualizar a documentação
- **Arquivos:** `plano.md`, `CLAUDE.md`, esta spec
- **Mudança:**
  - `plano.md`: marcar a Etapa 3 como concluída, registrando as decisões, a rota
    `perfil` (acréscimo) e que as Etapas 4 e 5 devem usar `usuario_atual` e o
    helper de leitura do corpo (`schemas`);
  - `CLAUDE.md`: estrutura (`routes/auth.py`, `schemas/`, `services/auth.py`
    existentes), Marshmallow **instalado** (remover "ainda não instalado"),
    rotas públicas/protegidas com `perfil`, formato dos erros 422 e 401 (JWT),
    `sub` do token como texto, `usuario_atual`, variável
    `JWT_ACCESS_TOKEN_EXPIRES_MINUTOS`, política de senha, mensagens do
    Marshmallow em português, débito técnico de *rate limiting*, ajuste pendente
    no frontend (401 no login não deve redirecionar em loop) e "Estado atual";
  - esta spec: marcar os critérios de aceite e o status como implementada.
- **Validar:** reler os três arquivos e conferir que não restam menções a
  "Marshmallow ainda não instalado" nem a "401 padrão da biblioteca" como
  pendência.

### Tarefa 12 — Conferência final
- **Arquivos:** nenhum.
- **Mudança:** nenhuma; verificação de todos os critérios de aceite.
- **Validar:** percorrer a lista de critérios, informar o que passou e o que
  dependeu da sua verificação manual, mostrar o `git status --short` final
  (esperado: `app/routes/auth.py`, `app/schemas/`, `app/services/`, alterações em
  `app/__init__.py`, `app/errors.py`, `config.py`, `.env.example`,
  `requirements.txt`, documentação) e aguardar você pedir o commit.
