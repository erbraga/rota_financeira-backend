from datetime import timedelta
from functools import lru_cache

from flask import current_app
from flask_jwt_extended import create_access_token, get_jwt_identity
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import Unauthorized
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models import Usuario

RESTRICAO_EMAIL_UNICO = "uq_usuarios_email"


class EmailJaCadastrado(Exception):
    pass


class CredenciaisInvalidas(Exception):
    pass


@lru_cache(maxsize=1)
def _hash_ficticio():
    # Calculado uma única vez: o login com e-mail inexistente confere a senha contra
    # este hash para levar o mesmo tempo de um login com senha errada.
    return generate_password_hash("senha-ficticia-para-igualar-o-tempo-de-resposta")


def _nome_da_restricao(erro):
    # psycopg 3: a violação de integridade traz o nome da restrição em orig.diag.
    return getattr(getattr(erro.orig, "diag", None), "constraint_name", None)


def registrar_usuario(nome, email, senha):
    """Grava o usuário com o hash da senha; nome e e-mail já chegam normalizados."""
    usuario = Usuario(nome=nome, email=email, senha_hash=generate_password_hash(senha))
    db.session.add(usuario)
    try:
        db.session.commit()
    except IntegrityError as erro:
        db.session.rollback()
        if _nome_da_restricao(erro) == RESTRICAO_EMAIL_UNICO:
            raise EmailJaCadastrado() from erro
        raise
    return usuario


def autenticar(email, senha):
    usuario = db.session.scalar(db.select(Usuario).where(Usuario.email == email))
    hash_da_senha = usuario.senha_hash if usuario else _hash_ficticio()
    senha_confere = check_password_hash(hash_da_senha, senha)
    if usuario is None or not senha_confere:
        raise CredenciaisInvalidas()
    return usuario


def criar_token(usuario):
    """Devolve o token JWT e a validade em segundos. O `sub` precisa ser texto."""
    validade = current_app.config["JWT_ACCESS_TOKEN_EXPIRES"]
    if isinstance(validade, timedelta):
        validade = validade.total_seconds()
    return create_access_token(identity=str(usuario.id)), int(validade)


def usuario_atual():
    """Usuário dono do token da requisição (use dentro de uma rota com @jwt_required)."""
    try:
        usuario_id = int(get_jwt_identity())
    except (TypeError, ValueError):
        raise Unauthorized("Token inválido")
    usuario = db.session.get(Usuario, usuario_id)
    if usuario is None:
        raise Unauthorized("Token inválido")
    return usuario
