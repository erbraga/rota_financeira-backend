"""GET /api/saude: pública, confere API e banco."""
from app import create_app
from tests.conftest import registrar_mapa_de_codigos


def test_saude_200_sem_autenticacao(client):
    resposta = client.get("/api/saude")
    assert resposta.status_code == 200
    assert resposta.get_json() == {"status": "ok", "banco": "ok"}


def test_saude_503_com_o_banco_inacessivel():
    # Aplicação auxiliar apontando para uma porta fechada (nunca toca em banco real).
    aplicacao = create_app(
        {"SQLALCHEMY_DATABASE_URI": "postgresql+psycopg://x:y@127.0.0.1:1/inexistente_test", "TESTING": True}
    )
    registrar_mapa_de_codigos(aplicacao, principal=False)  # entra no mapa de códigos provocados
    resposta = aplicacao.test_client().get("/api/saude")
    assert resposta.status_code == 503
    assert resposta.get_json() == {"erro": "Banco de dados indisponível"}
