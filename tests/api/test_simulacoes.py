"""CRUD de simulações (`/api/simulacoes`): contrato, validação de campos e 404/401."""
import pytest
from sqlalchemy import text

from app.extensions import db

RAIZ = "/api/simulacoes"
NAO_ENCONTRADA = {"erro": "Simulação não encontrada"}
IDS_GIGANTES = [2147483648, 99999999999999999999]


def criar(client, usuario, corpo):
    resposta = client.post(RAIZ, json=corpo, headers=usuario.cabecalho)
    assert resposta.status_code == 201, resposta.get_data(as_text=True)
    return resposta.get_json()


# ---------------------------------------------------------------------- POST

def test_criar_201_devolve_a_simulacao_e_o_location(client, usuario, corpo_simulacao):
    resposta = client.post(RAIZ, json=corpo_simulacao(), headers=usuario.cabecalho)
    corpo = resposta.get_json()
    assert resposta.status_code == 201
    assert set(corpo) == {
        "id", "nome", "valor_veiculo", "valor_entrada", "taxa_ipca_projetada",
        "taxa_fundo_rendimento", "prazo_meses_fundo", "criado_em",
    }
    assert "usuario_id" not in corpo
    assert resposta.headers["Location"].endswith(f"{RAIZ}/{corpo['id']}")
    assert (corpo["nome"], corpo["valor_veiculo"], corpo["valor_entrada"]) == ("Onix 2026", 95000, 20000)
    assert (corpo["taxa_ipca_projetada"], corpo["taxa_fundo_rendimento"], corpo["prazo_meses_fundo"]) == (4.5, 10.5, 36)
    assert isinstance(corpo["valor_veiculo"], (int, float)) and isinstance(corpo["taxa_ipca_projetada"], (int, float))
    assert isinstance(corpo["criado_em"], str)


def test_criar_grava_para_o_usuario_do_token_e_ignora_usuario_id_do_corpo(client, app, usuario, outro_usuario, corpo_simulacao):
    resposta = client.post(RAIZ, json=corpo_simulacao() | {"usuario_id": outro_usuario.id}, headers=usuario.cabecalho)
    assert resposta.status_code == 422 and "usuario_id" in resposta.get_json()["detalhes"]
    criada = criar(client, usuario, corpo_simulacao())
    with app.app_context():
        dono = db.session.execute(text("SELECT usuario_id FROM simulacoes WHERE id = :i"), {"i": criada["id"]}).scalar()
    assert dono == usuario.id


def test_criar_sem_valor_entrada_grava_zero(client, usuario, corpo_simulacao):
    corpo = corpo_simulacao()
    del corpo["valor_entrada"]
    assert criar(client, usuario, corpo)["valor_entrada"] == 0


def test_criar_aceita_numero_em_texto_zeros_a_direita_e_normaliza_o_nome(client, usuario, corpo_simulacao):
    criada = criar(
        client, usuario,
        corpo_simulacao(nome="  Carro  ", valor_veiculo="95000.50", taxa_ipca_projetada="4.500000", taxa_fundo_rendimento="10.500000"),
    )
    assert (criada["nome"], criada["valor_veiculo"], criada["taxa_ipca_projetada"]) == ("Carro", 95000.5, 4.5)


@pytest.mark.parametrize(
    "alteracoes",
    [
        {"valor_veiculo": 0.01, "valor_entrada": 0},
        {"valor_veiculo": 9999999.00, "valor_entrada": 9999999.00},
        {"taxa_ipca_projetada": -20, "taxa_fundo_rendimento": 0},
        {"taxa_ipca_projetada": 100, "taxa_fundo_rendimento": 100},
        {"taxa_ipca_projetada": 0.000001, "taxa_fundo_rendimento": 99.999999},
        {"prazo_meses_fundo": 1},
        {"prazo_meses_fundo": 60},
        {"nome": "A"},
        {"nome": "A" * 120},
    ],
)
def test_criar_aceita_os_limites(client, usuario, corpo_simulacao, alteracoes):
    assert client.post(RAIZ, json=corpo_simulacao(**alteracoes), headers=usuario.cabecalho).status_code == 201


CASOS_INVALIDOS = [
    # nome
    ("nome", "", "O nome deve ter entre 1 e 120 caracteres."),
    ("nome", "   ", "O nome deve ter entre 1 e 120 caracteres."),
    ("nome", "A" * 121, "O nome deve ter entre 1 e 120 caracteres."),
    ("nome", 5, "Nome inválido."),
    ("nome", None, "Campo obrigatório."),
    # valor do veículo (0,01 a 9.999.999,00; 2 casas)
    ("valor_veiculo", 0, "O valor do veículo deve estar entre 0,01 e 9.999.999,00."),
    ("valor_veiculo", -1, "O valor do veículo deve estar entre 0,01 e 9.999.999,00."),
    ("valor_veiculo", 10000000, "O valor do veículo deve estar entre 0,01 e 9.999.999,00."),
    ("valor_veiculo", "1e999999", "O valor do veículo deve estar entre 0,01 e 9.999.999,00."),
    ("valor_veiculo", 95000.005, "Use no máximo 2 casas decimais."),
    ("valor_veiculo", "95000.001", "Use no máximo 2 casas decimais."),
    ("valor_veiculo", "abc", "Número inválido."),
    ("valor_veiculo", "", "Número inválido."),
    ("valor_veiculo", True, "Número inválido."),
    ("valor_veiculo", "NaN", "Número inválido."),
    ("valor_veiculo", "Infinity", "Número inválido."),
    ("valor_veiculo", [1], "Número inválido."),
    ("valor_veiculo", None, "Campo obrigatório."),
    # valor da entrada (0 a 9.999.999,00; 2 casas)
    ("valor_entrada", -0.01, "O valor da entrada deve estar entre 0,00 e 9.999.999,00."),
    ("valor_entrada", 10000000, "O valor da entrada deve estar entre 0,00 e 9.999.999,00."),
    ("valor_entrada", 1.001, "Use no máximo 2 casas decimais."),
    ("valor_entrada", 95000.01, "A entrada não pode ser maior que o valor do veículo."),
    # IPCA projetado (-20 a 100; 6 casas)
    ("taxa_ipca_projetada", -20.000001, "A taxa de IPCA projetada deve estar entre -20 e 100."),
    ("taxa_ipca_projetada", 100.000001, "A taxa de IPCA projetada deve estar entre -20 e 100."),
    ("taxa_ipca_projetada", "4.1234567", "Use no máximo 6 casas decimais."),
    ("taxa_ipca_projetada", None, "Campo obrigatório."),
    # rendimento do fundo (0 a 100; 6 casas)
    ("taxa_fundo_rendimento", -0.000001, "A taxa de rendimento do fundo deve estar entre 0 e 100."),
    ("taxa_fundo_rendimento", 100.000001, "A taxa de rendimento do fundo deve estar entre 0 e 100."),
    ("taxa_fundo_rendimento", "10.1234567", "Use no máximo 6 casas decimais."),
    # prazo do fundo (inteiro estrito, 1 a 60)
    ("prazo_meses_fundo", 0, "O prazo do fundo (em meses) deve estar entre 1 e 60."),
    ("prazo_meses_fundo", 61, "O prazo do fundo (em meses) deve estar entre 1 e 60."),
    ("prazo_meses_fundo", 36.5, "Número inteiro inválido."),
    ("prazo_meses_fundo", 36.0, "Número inteiro inválido."),
    ("prazo_meses_fundo", "36", "Número inteiro inválido."),
    ("prazo_meses_fundo", True, "Número inteiro inválido."),
    ("prazo_meses_fundo", None, "Campo obrigatório."),
    # campos que não existem
    ("usuario_id", 1, "Campo desconhecido."),
    ("id", 1, "Campo desconhecido."),
    ("criado_em", "2026-01-01", "Campo desconhecido."),
]


@pytest.mark.parametrize("campo, valor, mensagem", CASOS_INVALIDOS)
def test_criar_422_por_campo_em_portugues(client, usuario, corpo_simulacao, campo, valor, mensagem):
    corpo = corpo_simulacao() | {campo: valor}
    resposta = client.post(RAIZ, json=corpo, headers=usuario.cabecalho)
    assert resposta.status_code == 422
    assert resposta.get_json()["erro"] == "Dados inválidos"
    assert mensagem in resposta.get_json()["detalhes"][campo]


def test_criar_422_sem_nenhum_campo_lista_os_obrigatorios(client, usuario):
    detalhes = client.post(RAIZ, json={}, headers=usuario.cabecalho).get_json()["detalhes"]
    assert set(detalhes) == {"nome", "valor_veiculo", "taxa_ipca_projetada", "taxa_fundo_rendimento", "prazo_meses_fundo"}


@pytest.mark.parametrize("corpo", ["{", "[]", "1", "null"])
def test_criar_400_json_invalido_ou_nao_objeto(client, usuario, corpo):
    resposta = client.post(RAIZ, data=corpo, content_type="application/json", headers=usuario.cabecalho)
    assert resposta.status_code == 400
    assert resposta.get_json() == {"erro": "Corpo da requisição deve ser um objeto JSON"}


def test_criar_415_quando_nao_e_json(client, usuario):
    resposta = client.post(RAIZ, data="x", headers=usuario.cabecalho | {"Content-Type": "text/plain"})
    assert resposta.status_code == 415 and resposta.get_json() == {"erro": "Tipo de conteúdo não suportado"}


def test_erros_de_validacao_nao_gravam_nada(client, app, usuario, corpo_simulacao):
    client.post(RAIZ, json=corpo_simulacao(valor_veiculo=0), headers=usuario.cabecalho)
    with app.app_context():
        assert db.session.execute(text("SELECT count(*) FROM simulacoes")).scalar() == 0


# ---------------------------------------------------------------------- GET (coleção e item)

def test_listar_vazio_devolve_o_envelope(client, usuario):
    resposta = client.get(RAIZ, headers=usuario.cabecalho)
    assert resposta.status_code == 200 and resposta.get_json() == {"itens": [], "total": 0}


def test_listar_do_mais_recente_para_o_mais_antigo_e_so_as_proprias(client, usuario, outro_usuario, corpo_simulacao):
    ids = [criar(client, usuario, corpo_simulacao(nome=f"Sim {n}"))["id"] for n in range(3)]
    criar(client, outro_usuario, corpo_simulacao(nome="Do Beto"))
    corpo = client.get(RAIZ, headers=usuario.cabecalho).get_json()
    assert corpo["total"] == 3
    assert [item["id"] for item in corpo["itens"]] == ids[::-1]
    assert all("usuario_id" not in item for item in corpo["itens"])
    assert [i["nome"] for i in client.get(RAIZ, headers=outro_usuario.cabecalho).get_json()["itens"]] == ["Do Beto"]


def test_obter_200_igual_ao_criado(client, usuario, corpo_simulacao):
    criada = criar(client, usuario, corpo_simulacao())
    resposta = client.get(f"{RAIZ}/{criada['id']}", headers=usuario.cabecalho)
    assert resposta.status_code == 200 and resposta.get_json() == criada


def test_obter_nao_traz_as_opcoes_de_financiamento(client, usuario, corpo_simulacao, corpo_opcao):
    criada = criar(client, usuario, corpo_simulacao())
    client.post(f"{RAIZ}/{criada['id']}/financiamentos", json=corpo_opcao(), headers=usuario.cabecalho)
    assert "financiamentos" not in client.get(f"{RAIZ}/{criada['id']}", headers=usuario.cabecalho).get_json()


@pytest.mark.parametrize("simulacao_id", [0, 999999, *IDS_GIGANTES])
@pytest.mark.parametrize("metodo", ["get", "put", "delete"])
def test_404_de_id_inexistente_ou_gigante_nunca_405_nem_500(client, usuario, corpo_simulacao, metodo, simulacao_id):
    argumentos = {"json": corpo_simulacao()} if metodo == "put" else {}
    resposta = getattr(client, metodo)(f"{RAIZ}/{simulacao_id}", headers=usuario.cabecalho, **argumentos)
    assert resposta.status_code == 404
    assert resposta.get_json() == NAO_ENCONTRADA


@pytest.mark.parametrize("caminho", ["/-1", "/abc", "/1.5"])
def test_id_que_nao_e_inteiro_positivo_da_404(client, usuario, caminho):
    assert client.get(RAIZ + caminho, headers=usuario.cabecalho).status_code == 404


def test_metodo_sem_rota_da_405_em_json(client, usuario, corpo_simulacao):
    criada = criar(client, usuario, corpo_simulacao())
    resposta = client.patch(f"{RAIZ}/{criada['id']}", json={"nome": "X"}, headers=usuario.cabecalho)
    assert resposta.status_code == 405 and resposta.get_json() == {"erro": "Método não permitido"}


# ---------------------------------------------------------------------- PUT

def test_atualizar_substitui_tudo_e_preserva_id_e_criado_em(client, usuario, corpo_simulacao):
    criada = criar(client, usuario, corpo_simulacao())
    novo = {
        "nome": "Outro nome", "valor_veiculo": 120000, "taxa_ipca_projetada": 3.25,
        "taxa_fundo_rendimento": 9, "prazo_meses_fundo": 24,
    }  # sem valor_entrada: volta a 0
    resposta = client.put(f"{RAIZ}/{criada['id']}", json=novo, headers=usuario.cabecalho)
    corpo = resposta.get_json()
    assert resposta.status_code == 200
    assert (corpo["id"], corpo["criado_em"]) == (criada["id"], criada["criado_em"])
    assert (corpo["nome"], corpo["valor_veiculo"], corpo["valor_entrada"]) == ("Outro nome", 120000, 0)
    assert (corpo["taxa_ipca_projetada"], corpo["taxa_fundo_rendimento"], corpo["prazo_meses_fundo"]) == (3.25, 9, 24)
    assert client.get(f"{RAIZ}/{criada['id']}", headers=usuario.cabecalho).get_json() == corpo


def test_atualizar_nao_troca_o_dono(client, app, usuario, outro_usuario, corpo_simulacao):
    criada = criar(client, usuario, corpo_simulacao())
    client.put(f"{RAIZ}/{criada['id']}", json=corpo_simulacao(nome="Mudou"), headers=usuario.cabecalho)
    with app.app_context():
        assert db.session.execute(text("SELECT usuario_id FROM simulacoes WHERE id = :i"), {"i": criada["id"]}).scalar() == usuario.id


@pytest.mark.parametrize("campo, valor, mensagem", CASOS_INVALIDOS[:6] + CASOS_INVALIDOS[-8:])
def test_atualizar_422_usa_as_mesmas_regras_e_nao_altera_nada(client, usuario, corpo_simulacao, campo, valor, mensagem):
    criada = criar(client, usuario, corpo_simulacao())
    resposta = client.put(f"{RAIZ}/{criada['id']}", json=corpo_simulacao() | {campo: valor}, headers=usuario.cabecalho)
    assert resposta.status_code == 422 and mensagem in resposta.get_json()["detalhes"][campo]
    assert client.get(f"{RAIZ}/{criada['id']}", headers=usuario.cabecalho).get_json() == criada


def test_atualizar_400_e_415(client, usuario, corpo_simulacao):
    criada = criar(client, usuario, corpo_simulacao())
    url = f"{RAIZ}/{criada['id']}"
    assert client.put(url, data="{", content_type="application/json", headers=usuario.cabecalho).status_code == 400
    assert client.put(url, data="x", headers=usuario.cabecalho | {"Content-Type": "text/plain"}).status_code == 415


def test_atualizar_recusa_valor_do_veiculo_menor_ou_igual_a_entrada_de_uma_opcao(client, usuario, corpo_simulacao, corpo_opcao):
    criada = criar(client, usuario, corpo_simulacao())
    url = f"{RAIZ}/{criada['id']}"
    client.post(f"{url}/financiamentos", json=corpo_opcao(nome="Banco Z", valor_entrada=30000), headers=usuario.cabecalho)
    for valor in (30000, 29999.99, 1000):
        resposta = client.put(url, json=corpo_simulacao(valor_veiculo=valor, valor_entrada=0), headers=usuario.cabecalho)
        assert resposta.status_code == 422, valor
        mensagem = resposta.get_json()["detalhes"]["valor_veiculo"][0]
        assert 'Banco Z' in mensagem and "R$ 30.000,00" in mensagem
    assert client.get(url, headers=usuario.cabecalho).get_json() == criada
    assert client.put(url, json=corpo_simulacao(valor_veiculo=30000.01, valor_entrada=0), headers=usuario.cabecalho).status_code == 200


# ---------------------------------------------------------------------- DELETE

def test_excluir_204_sem_corpo_e_some_junto_com_as_opcoes(client, app, usuario, corpo_simulacao, corpo_opcao):
    criada = criar(client, usuario, corpo_simulacao())
    url = f"{RAIZ}/{criada['id']}"
    client.post(f"{url}/financiamentos", json=corpo_opcao(), headers=usuario.cabecalho)
    resposta = client.delete(url, headers=usuario.cabecalho)
    assert resposta.status_code == 204 and resposta.get_data() == b""
    assert client.get(url, headers=usuario.cabecalho).status_code == 404
    with app.app_context():
        assert db.session.execute(text("SELECT count(*) FROM opcoes_financiamento")).scalar() == 0
    assert client.delete(url, headers=usuario.cabecalho).get_json() == NAO_ENCONTRADA


def test_excluir_so_apaga_a_simulacao_indicada(client, usuario, corpo_simulacao):
    a, b = (criar(client, usuario, corpo_simulacao(nome=n))["id"] for n in "AB")
    client.delete(f"{RAIZ}/{a}", headers=usuario.cabecalho)
    assert [i["id"] for i in client.get(RAIZ, headers=usuario.cabecalho).get_json()["itens"]] == [b]


# ---------------------------------------------------------------------- dono e 401

@pytest.mark.parametrize("metodo, sufixo", [("get", ""), ("put", ""), ("delete", "")])
def test_simulacao_de_outro_usuario_da_o_mesmo_404_e_nao_muda(client, usuario, outro_usuario, corpo_simulacao, metodo, sufixo):
    criada = criar(client, usuario, corpo_simulacao())
    argumentos = {"json": corpo_simulacao(nome="Invasor")} if metodo == "put" else {}
    resposta = getattr(client, metodo)(f"{RAIZ}/{criada['id']}{sufixo}", headers=outro_usuario.cabecalho, **argumentos)
    assert resposta.status_code == 404 and resposta.get_json() == NAO_ENCONTRADA
    assert client.get(f"{RAIZ}/{criada['id']}", headers=usuario.cabecalho).get_json() == criada


@pytest.mark.parametrize(
    "metodo, caminho",
    [("get", RAIZ), ("post", RAIZ), ("get", f"{RAIZ}/1"), ("put", f"{RAIZ}/1"), ("delete", f"{RAIZ}/1")],
)
def test_401_sem_credencial_valida(client, credenciais_recusadas, corpo_simulacao, metodo, caminho):
    for descricao, cabecalhos, mensagem in credenciais_recusadas:
        argumentos = {"json": corpo_simulacao()} if metodo in ("post", "put") else {}
        resposta = getattr(client, metodo)(caminho, headers=cabecalhos, **argumentos)
        assert resposta.status_code == 401, descricao
        assert resposta.get_json() == {"erro": mensagem}, descricao
        assert resposta.headers.get("WWW-Authenticate") == "Bearer", descricao
