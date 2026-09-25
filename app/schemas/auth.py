from marshmallow import Schema, fields, pre_load, validate

from app.schemas.base import EntradaSchema, mensagens, normalizar_texto

TAMANHO_MINIMO_SENHA = 8
TAMANHO_MAXIMO_SENHA = 128


def campo_email():
    return fields.Email(
        required=True,
        validate=validate.Length(max=254, error="O e-mail deve ter até 254 caracteres."),
        error_messages=mensagens("E-mail inválido."),
    )


class RegistroSchema(EntradaSchema):
    nome = fields.String(
        required=True,
        validate=validate.Length(min=2, max=120, error="O nome deve ter entre 2 e 120 caracteres."),
        error_messages=mensagens("Nome inválido."),
    )
    email = campo_email()
    senha = fields.String(
        required=True,
        load_only=True,
        validate=validate.Length(
            min=TAMANHO_MINIMO_SENHA,
            max=TAMANHO_MAXIMO_SENHA,
            error=f"A senha deve ter entre {TAMANHO_MINIMO_SENHA} e {TAMANHO_MAXIMO_SENHA} caracteres.",
        ),
        error_messages=mensagens("Senha inválida."),
    )

    @pre_load
    def normalizar(self, dados, **kwargs):
        # A senha nunca é alterada (nem strip): guarda-se exatamente o que foi digitado.
        return normalizar_texto(dados, ("nome", "email"), minusculas=("email",))


class LoginSchema(EntradaSchema):
    email = campo_email()
    # No login a senha só é conferida; o limite de tamanho apenas recusa requisições enormes.
    senha = fields.String(
        required=True,
        load_only=True,
        validate=validate.Length(
            min=1,
            max=TAMANHO_MAXIMO_SENHA,
            error=f"A senha deve ter de 1 a {TAMANHO_MAXIMO_SENHA} caracteres.",
        ),
        error_messages=mensagens("Senha inválida."),
    )

    @pre_load
    def normalizar(self, dados, **kwargs):
        return normalizar_texto(dados, ("email",), minusculas=("email",))


class UsuarioSchema(Schema):
    id = fields.Integer(dump_only=True)
    nome = fields.String(dump_only=True)
    email = fields.String(dump_only=True)
    criado_em = fields.DateTime(dump_only=True)


class UsuarioResumoSchema(UsuarioSchema):
    class Meta:
        fields = ("id", "nome", "email")
