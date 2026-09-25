from flask import Blueprint
from flask_jwt_extended import jwt_required

from app.errors import resposta_erro
from app.schemas import carregar
from app.schemas.auth import LoginSchema, RegistroSchema, UsuarioResumoSchema, UsuarioSchema
from app.services.auth import (
    CredenciaisInvalidas,
    EmailJaCadastrado,
    autenticar,
    criar_token,
    registrar_usuario,
    usuario_atual,
)

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@bp.post("/registrar")
def registrar():
    """Cria uma conta de usuário.
    ---
    tags:
      - Autenticação
    summary: Cadastra um novo usuário
    description: >-
      Rota pública. O e-mail é convertido para minúsculas e não pode repetir.
      A senha é guardada apenas como hash e nunca é devolvida. Para entrar,
      use o login.
    requestBody:
      required: true
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/RegistroRequisicao"
    responses:
      201:
        description: Usuário criado.
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Usuario"
      400:
        description: O corpo não é um JSON válido ou não é um objeto.
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Erro"
            example:
              erro: Corpo da requisição deve ser um objeto JSON
      409:
        description: E-mail já cadastrado.
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Erro"
            example:
              erro: E-mail já cadastrado
      415:
        description: O Content-Type não é application/json.
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Erro"
      422:
        description: Dados inválidos, com as mensagens por campo em detalhes.
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Erro"
            example:
              erro: Dados inválidos
              detalhes:
                senha:
                  - A senha deve ter entre 8 e 128 caracteres.
    """
    dados = carregar(RegistroSchema())
    try:
        usuario = registrar_usuario(dados["nome"], dados["email"], dados["senha"])
    except EmailJaCadastrado:
        return resposta_erro("E-mail já cadastrado", 409)
    return UsuarioSchema().dump(usuario), 201


@bp.post("/login")
def login():
    """Autentica o usuário e devolve o token JWT.
    ---
    tags:
      - Autenticação
    summary: Faz login com e-mail e senha
    description: >-
      Rota pública. Devolve o token, que deve ser enviado nas rotas protegidas
      no cabeçalho Authorization (Bearer). No botão Authorize do Swagger, cole
      apenas o token. E-mail inexistente e senha errada respondem exatamente
      igual (401).
    requestBody:
      required: true
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/LoginRequisicao"
    responses:
      200:
        description: Login realizado.
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/LoginResposta"
      400:
        description: O corpo não é um JSON válido ou não é um objeto.
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Erro"
      401:
        description: Credenciais inválidas (e-mail inexistente ou senha errada).
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Erro"
            example:
              erro: Credenciais inválidas
      415:
        description: O Content-Type não é application/json.
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Erro"
      422:
        description: Dados inválidos, com as mensagens por campo em detalhes.
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Erro"
    """
    dados = carregar(LoginSchema())
    try:
        usuario = autenticar(dados["email"], dados["senha"])
    except CredenciaisInvalidas:
        return resposta_erro("Credenciais inválidas", 401)
    token, expira_em = criar_token(usuario)
    return {
        "access_token": token,
        "token_type": "Bearer",
        "expires_in": expira_em,
        "usuario": UsuarioResumoSchema().dump(usuario),
    }


@bp.get("/perfil")
@jwt_required()
def perfil():
    """Devolve os dados do usuário dono do token.
    ---
    tags:
      - Autenticação
    summary: Consulta o usuário autenticado
    description: >-
      Rota protegida. Serve para o cliente conferir se o token ainda vale e
      obter os dados do usuário logado.
    security:
      - BearerAuth: []
    responses:
      200:
        description: Usuário do token.
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Usuario"
      401:
        description: Token ausente, inválido ou expirado, ou usuário inexistente.
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Erro"
            example:
              erro: Token expirado
    """
    return UsuarioSchema().dump(usuario_atual())
