"""Registro, login e perfil (`/api/auth/*`) e os 401 de token."""
import pytest
from sqlalchemy import text

from app.extensions import db
from app.models import Usuario

REGISTRO = {"nome": "Carla Souza", "email": "carla@exemplo.com", "senha": "senha-da-carla-1"}
INGLES = ("Not a valid", "Missing", "Unknown field", "Field may not", "Length must", "Invalid")


def registrar(client, **alteracoes):
    return client.post("/api/auth/registrar", json=REGISTRO | alteracoes)


def sem_ingles(resposta):
    texto = resposta.get_data(as_text=True)
    return not any(trecho in texto for trecho in INGLES)


# ---------------------------------------------------------------------- registrar

def test_registrar_201_devolve_o_usuario_sem_senha_nem_token(client):
    resposta = registrar(client)
    corpo = resposta.get_json()
    assert resposta.status_code == 201
    assert set(corpo) == {"id", "nome", "email", "criado_em"}
    assert (corpo["nome"], corpo["email"]) == ("Carla Souza", "carla@exemplo.com")
    assert "senha" not in resposta.get_data(as_text=True).lower()


def test_registrar_guarda_so_o_hash_da_senha(app, client):
    registrar(client)
    with app.app_context():
        hash_guardado = db.session.scalar(db.select(Usuario.senha_hash).where(Usuario.email == "carla@exemplo.com"))
    assert hash_guardado.startswith("scrypt:") and REGISTRO["senha"] not in hash_guardado


def test_registrar_normaliza_nome_e_email(client):
    corpo = registrar(client, nome="  Carla Souza  ", email="  CARLA@Exemplo.COM ").get_json()
    assert (corpo["nome"], corpo["email"]) == ("Carla Souza", "carla@exemplo.com")


def test_registrar_409_email_repetido_mesmo_com_outra_caixa(client):
    assert registrar(client).status_code == 201
    for email in ("carla@exemplo.com", "CARLA@EXEMPLO.COM", " carla@exemplo.com "):
        resposta = registrar(client, email=email)
        assert resposta.status_code == 409
        assert resposta.get_json() == {"erro": "E-mail já cadastrado"}


@pytest.mark.parametrize("corpo", ["{", "[]", "1", '"texto"', "null"])
def test_registrar_400_quando_o_json_e_invalido_ou_nao_e_objeto(client, corpo):
    resposta = client.post("/api/auth/registrar", data=corpo, content_type="application/json")
    assert resposta.status_code == 400
    assert resposta.get_json() == {"erro": "Corpo da requisição deve ser um objeto JSON"}


@pytest.mark.parametrize("cabecalhos", [{}, {"Content-Type": "text/plain"}, {"Content-Type": "application/x-www-form-urlencoded"}])
def test_registrar_415_quando_nao_e_json(client, cabecalhos):
    resposta = client.post("/api/auth/registrar", data="x=1", headers=cabecalhos)
    assert resposta.status_code == 415
    assert resposta.get_json() == {"erro": "Tipo de conteúdo não suportado"}


@pytest.mark.parametrize(
    "alteracoes, campo, mensagem",
    [
        ({"nome": None}, "nome", "Campo obrigatório."),
        ({"nome": "A"}, "nome", "O nome deve ter entre 2 e 120 caracteres."),
        ({"nome": "A" * 121}, "nome", "O nome deve ter entre 2 e 120 caracteres."),
        ({"nome": 10}, "nome", "Nome inválido."),
        ({"email": "sem-arroba"}, "email", "E-mail inválido."),
        ({"email": "a@b"}, "email", "E-mail inválido."),
        ({"email": "a" * 250 + "@b.co"}, "email", "O e-mail deve ter até 254 caracteres."),
        ({"email": None}, "email", "Campo obrigatório."),
        ({"senha": "1234567"}, "senha", "A senha deve ter entre 8 e 128 caracteres."),
        ({"senha": "x" * 129}, "senha", "A senha deve ter entre 8 e 128 caracteres."),
        ({"senha": 12345678}, "senha", "Senha inválida."),
        ({"extra": 1}, "extra", "Campo desconhecido."),
        ({"usuario_id": 1}, "usuario_id", "Campo desconhecido."),
    ],
)
def test_registrar_422_em_portugues_por_campo(client, alteracoes, campo, mensagem):
    resposta = registrar(client, **alteracoes)
    assert resposta.status_code == 422
    corpo = resposta.get_json()
    assert corpo["erro"] == "Dados inválidos"
    assert mensagem in corpo["detalhes"][campo]
    assert sem_ingles(resposta)
    assert REGISTRO["senha"] not in resposta.get_data(as_text=True)


def test_registrar_422_sem_nenhum_campo_lista_os_tres(client):
    corpo = client.post("/api/auth/registrar", json={}).get_json()
    assert set(corpo["detalhes"]) == {"nome", "email", "senha"}


def test_registrar_422_nunca_ecoa_a_senha_digitada(client):
    resposta = registrar(client, email="invalido", senha="segredo-que-nao-pode-voltar")
    assert resposta.status_code == 422
    assert "segredo-que-nao-pode-voltar" not in resposta.get_data(as_text=True)


def test_registrar_aceita_senha_de_8_e_de_128_caracteres(client):
    assert registrar(client, email="a@exemplo.com", senha="12345678").status_code == 201
    assert registrar(client, email="b@exemplo.com", senha="x" * 128).status_code == 201


# ---------------------------------------------------------------------- login

def login(client, **alteracoes):
    return client.post("/api/auth/login", json={"email": "carla@exemplo.com", "senha": REGISTRO["senha"]} | alteracoes)


def test_login_200_devolve_token_e_usuario(client):
    registrar(client)
    resposta = login(client)
    corpo = resposta.get_json()
    assert resposta.status_code == 200
    assert set(corpo) == {"access_token", "token_type", "expires_in", "usuario"}
    assert corpo["token_type"] == "Bearer" and corpo["expires_in"] == 3600
    assert set(corpo["usuario"]) == {"id", "nome", "email"} and corpo["usuario"]["email"] == "carla@exemplo.com"
    perfil = client.get("/api/auth/perfil", headers={"Authorization": f"Bearer {corpo['access_token']}"})
    assert perfil.status_code == 200 and perfil.get_json()["id"] == corpo["usuario"]["id"]


def test_login_ignora_caixa_e_espacos_do_email(client):
    registrar(client)
    assert login(client, email="  CARLA@Exemplo.com ").status_code == 200


def test_login_401_igual_para_email_inexistente_e_senha_errada(client):
    registrar(client)
    inexistente = login(client, email="ninguem@exemplo.com")
    errada = login(client, senha="senha-errada-123")
    assert inexistente.status_code == errada.status_code == 401
    assert inexistente.get_json() == errada.get_json() == {"erro": "Credenciais inválidas"}


def test_login_senha_e_sensivel_a_caixa_e_a_espacos(client):
    registrar(client)
    assert login(client, senha=REGISTRO["senha"].upper()).status_code == 401
    assert login(client, senha=f" {REGISTRO['senha']}").status_code == 401


@pytest.mark.parametrize("corpo", ["{", "[]", "null"])
def test_login_400(client, corpo):
    assert client.post("/api/auth/login", data=corpo, content_type="application/json").status_code == 400


def test_login_415(client):
    assert client.post("/api/auth/login", data="x", headers={"Content-Type": "text/plain"}).status_code == 415


@pytest.mark.parametrize(
    "corpo, campo",
    [
        ({}, "email"),
        ({"email": "carla@exemplo.com"}, "senha"),
        ({"email": "invalido", "senha": "x"}, "email"),
        ({"email": "carla@exemplo.com", "senha": ""}, "senha"),
        ({"email": "carla@exemplo.com", "senha": "x" * 129}, "senha"),
        ({"email": "carla@exemplo.com", "senha": "x", "extra": 1}, "extra"),
    ],
)
def test_login_422_em_portugues(client, corpo, campo):
    resposta = client.post("/api/auth/login", json=corpo)
    assert resposta.status_code == 422
    assert campo in resposta.get_json()["detalhes"] and sem_ingles(resposta)


# ---------------------------------------------------------------------- perfil e token

def test_perfil_200_devolve_o_usuario_do_token(client, usuario, outro_usuario):
    corpo = client.get("/api/auth/perfil", headers=usuario.cabecalho).get_json()
    assert set(corpo) == {"id", "nome", "email", "criado_em"}
    assert (corpo["id"], corpo["email"]) == (usuario.id, usuario.email)


def test_perfil_e_rotas_protegidas_devolvem_401_para_credenciais_recusadas(client, credenciais_recusadas):
    for descricao, cabecalhos, mensagem in credenciais_recusadas:
        resposta = client.get("/api/auth/perfil", headers=cabecalhos)
        assert resposta.status_code == 401, descricao
        assert resposta.get_json() == {"erro": mensagem}, descricao
        assert resposta.headers.get("WWW-Authenticate") == "Bearer", descricao


def test_token_de_conta_excluida_devolve_401(app, client, usuario):
    with app.app_context():
        db.session.delete(db.session.get(Usuario, usuario.id))
        db.session.commit()
    resposta = client.get("/api/auth/perfil", headers=usuario.cabecalho)
    assert resposta.status_code == 401 and resposta.get_json() == {"erro": "Token inválido"}


def test_registro_nao_cria_sessao_nem_token(client):
    assert "access_token" not in registrar(client).get_data(as_text=True)


def test_email_e_unico_no_banco_mesmo_fora_da_aplicacao(app, client):
    registrar(client)
    with app.app_context():
        with pytest.raises(Exception, match="uq_usuarios_email"):
            db.session.execute(
                text("INSERT INTO usuarios (nome, email, senha_hash) VALUES ('X', 'carla@exemplo.com', 'h')")
            )
        db.session.rollback()
