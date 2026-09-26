"""CORS: só as origens do frontend, com Authorization, `Location` exposto e preflight em cache."""
import pytest

from app import create_app

ORIGENS_DO_FRONTEND = ["http://localhost:5173", "http://localhost:3000"]
ORIGENS_ESTRANHAS = ["http://evil.example", "http://localhost:5174", "https://localhost:5173", "http://localhost:5173.evil.example", "null"]
CABECALHOS_CORS = ("Access-Control-Allow-Origin", "Access-Control-Allow-Methods", "Access-Control-Allow-Headers", "Access-Control-Max-Age")


def preflight(client, origem, caminho="/api/simulacoes", metodo="POST", cabecalhos="authorization,content-type"):
    return client.options(
        caminho,
        headers={"Origin": origem, "Access-Control-Request-Method": metodo, "Access-Control-Request-Headers": cabecalhos},
    )


@pytest.mark.parametrize("origem", ORIGENS_DO_FRONTEND)
@pytest.mark.parametrize("metodo", ["GET", "POST", "PUT", "DELETE"])
def test_preflight_das_origens_do_frontend_com_authorization(client, origem, metodo):
    resposta = preflight(client, origem, metodo=metodo)
    permitidos = {m.strip() for m in resposta.headers["Access-Control-Allow-Methods"].split(",")}
    assert resposta.status_code == 200
    assert resposta.headers["Access-Control-Allow-Origin"] == origem  # a própria origem, nunca "*"
    assert {"authorization", "content-type"} <= {h.strip().lower() for h in resposta.headers["Access-Control-Allow-Headers"].split(",")}
    assert metodo in permitidos
    assert resposta.headers["Access-Control-Max-Age"] == "600"


@pytest.mark.parametrize("origem", ORIGENS_ESTRANHAS)
def test_origem_fora_da_lista_nao_recebe_cabecalhos_cors(client, origem):
    resposta = preflight(client, origem)
    assert not any(c in resposta.headers for c in CABECALHOS_CORS)
    real = client.get("/api/saude", headers={"Origin": origem})
    assert "Access-Control-Allow-Origin" not in real.headers


@pytest.mark.parametrize("origem", ORIGENS_DO_FRONTEND)
def test_resposta_real_leva_allow_origin_e_vary(client, origem):
    resposta = client.get("/api/saude", headers={"Origin": origem})
    assert resposta.headers["Access-Control-Allow-Origin"] == origem
    assert "Origin" in resposta.headers["Vary"]


def test_location_e_exposto_ao_javascript_do_frontend(client, usuario, corpo_simulacao, corpo_opcao):
    origem = {"Origin": "http://localhost:5173"}
    criada = client.post("/api/simulacoes", json=corpo_simulacao(), headers=usuario.cabecalho | origem)
    assert criada.status_code == 201 and "Location" in criada.headers
    assert "Location" in criada.headers["Access-Control-Expose-Headers"]
    opcao = client.post(f"/api/simulacoes/{criada.get_json()['id']}/financiamentos", json=corpo_opcao(), headers=usuario.cabecalho | origem)
    assert opcao.status_code == 201 and "Location" in opcao.headers["Access-Control-Expose-Headers"]


def test_as_respostas_de_erro_tambem_levam_os_cabecalhos_cors(client, usuario):
    origem = {"Origin": "http://localhost:3000"}
    casos = {
        401: client.get("/api/simulacoes", headers=origem),
        404: client.get("/api/simulacoes/999999", headers=usuario.cabecalho | origem),
        415: client.post("/api/auth/login", data="x", headers=origem | {"Content-Type": "text/plain"}),
        422: client.post("/api/auth/login", json={}, headers=origem),
        405: client.delete("/api/saude", headers=origem),
    }
    for status, resposta in casos.items():
        assert resposta.status_code == status
        assert resposta.headers["Access-Control-Allow-Origin"] == "http://localhost:3000", status


def test_o_cors_vale_so_para_a_api(client):
    origem = {"Origin": "http://localhost:5173"}
    assert "Access-Control-Allow-Origin" not in client.get("/apidocs/", headers=origem).headers
    assert "Access-Control-Allow-Origin" not in client.get("/apispec.json", headers=origem).headers


def test_nunca_libera_qualquer_origem(app):
    assert "*" not in app.config["CORS_ORIGINS"]


def test_com_cors_origins_vazio_nenhuma_origem_e_liberada():
    aplicacao = create_app({"CORS_ORIGINS": [], "SQLALCHEMY_DATABASE_URI": "postgresql+psycopg://x:y@127.0.0.1:1/x_test", "TESTING": True})
    cliente = aplicacao.test_client()
    for origem in ORIGENS_DO_FRONTEND:
        assert not any(c in preflight(cliente, origem).headers for c in CABECALHOS_CORS)
        assert "Access-Control-Allow-Origin" not in cliente.get("/api/saude", headers={"Origin": origem}).headers
