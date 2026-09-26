"""CRUD das opções de financiamento (`/api/simulacoes/<id>/financiamentos`)."""
import pytest
from sqlalchemy import text

from app.extensions import db

RAIZ = "/api/simulacoes"
SIM_NAO_ENCONTRADA = {"erro": "Simulação não encontrada"}
OPCAO_NAO_ENCONTRADA = {"erro": "Opção de financiamento não encontrada"}
LIMITE = {"erro": "Uma simulação aceita no máximo 3 opções de financiamento"}
IDS_GIGANTES = [2147483648, 99999999999999999999]


@pytest.fixture
def simulacao(client, usuario, corpo_simulacao):
    resposta = client.post(RAIZ, json=corpo_simulacao(), headers=usuario.cabecalho)  # veículo 95.000,00
    return resposta.get_json()["id"]


@pytest.fixture
def colecao(simulacao):
    return f"{RAIZ}/{simulacao}/financiamentos"


def adicionar(client, usuario, colecao, corpo):
    resposta = client.post(colecao, json=corpo, headers=usuario.cabecalho)
    assert resposta.status_code == 201, resposta.get_data(as_text=True)
    return resposta.get_json()


def contar_opcoes(app):
    with app.app_context():
        return db.session.execute(text("SELECT count(*) FROM opcoes_financiamento")).scalar()


# ---------------------------------------------------------------------- POST

def test_criar_201_devolve_a_opcao_e_o_location(client, usuario, colecao, corpo_opcao):
    resposta = client.post(colecao, json=corpo_opcao(), headers=usuario.cabecalho)
    corpo = resposta.get_json()
    assert resposta.status_code == 201
    assert set(corpo) == {"id", "nome", "taxa_juros_mensal", "prazo_meses", "sistema_amortizacao", "valor_entrada"}
    assert corpo["nome"] == "Banco X 48x" and corpo["taxa_juros_mensal"] == 1.99
    assert (corpo["prazo_meses"], corpo["sistema_amortizacao"], corpo["valor_entrada"]) == (48, "PRICE", 20000)
    assert isinstance(corpo["taxa_juros_mensal"], float) and isinstance(corpo["valor_entrada"], (int, float))
    assert resposta.headers["Location"].endswith(f"{colecao}/{corpo['id']}")


@pytest.mark.parametrize("enviado, esperado", [("price", "PRICE"), ("Price", "PRICE"), (" sac ", "SAC"), ("SAC", "SAC"), ("sAc", "SAC")])
def test_sistema_de_amortizacao_aceita_qualquer_caixa_e_volta_em_maiusculas(client, usuario, colecao, corpo_opcao, enviado, esperado):
    assert adicionar(client, usuario, colecao, corpo_opcao(sistema_amortizacao=enviado))["sistema_amortizacao"] == esperado


def test_criar_sem_valor_entrada_grava_zero_e_texto_numerico_e_aceito(client, usuario, colecao, corpo_opcao):
    corpo = corpo_opcao(taxa_juros_mensal="1.500000", valor_entrada="1000.50")
    assert adicionar(client, usuario, colecao, corpo)["valor_entrada"] == 1000.5
    sem_entrada = corpo_opcao()
    del sem_entrada["valor_entrada"]
    assert adicionar(client, usuario, colecao, sem_entrada)["valor_entrada"] == 0


@pytest.mark.parametrize(
    "alteracoes",
    [
        {"taxa_juros_mensal": 0}, {"taxa_juros_mensal": 20}, {"taxa_juros_mensal": 0.000001}, {"taxa_juros_mensal": 19.999999},
        {"prazo_meses": 1}, {"prazo_meses": 72},
        {"valor_entrada": 0}, {"valor_entrada": 94999.99},
        {"nome": "A"}, {"nome": "A" * 120},
    ],
)
def test_criar_aceita_os_limites(client, usuario, colecao, corpo_opcao, alteracoes):
    assert client.post(colecao, json=corpo_opcao(**alteracoes), headers=usuario.cabecalho).status_code == 201


CASOS_INVALIDOS = [
    ("nome", "", "O nome deve ter entre 1 e 120 caracteres."),
    ("nome", "A" * 121, "O nome deve ter entre 1 e 120 caracteres."),
    ("nome", 5, "Nome inválido."),
    ("nome", None, "Campo obrigatório."),
    ("taxa_juros_mensal", -0.000001, "A taxa de juros mensal deve estar entre 0 e 20."),
    ("taxa_juros_mensal", 20.000001, "A taxa de juros mensal deve estar entre 0 e 20."),
    ("taxa_juros_mensal", "1.1234567", "Use no máximo 6 casas decimais."),
    ("taxa_juros_mensal", "abc", "Número inválido."),
    ("taxa_juros_mensal", True, "Número inválido."),
    ("taxa_juros_mensal", None, "Campo obrigatório."),
    ("prazo_meses", 0, "O prazo (em meses) deve estar entre 1 e 72."),
    ("prazo_meses", 73, "O prazo (em meses) deve estar entre 1 e 72."),
    ("prazo_meses", 48.5, "Número inteiro inválido."),
    ("prazo_meses", 48.0, "Número inteiro inválido."),
    ("prazo_meses", "48", "Número inteiro inválido."),
    ("prazo_meses", None, "Campo obrigatório."),
    ("sistema_amortizacao", "", "Sistema de amortização inválido. Use PRICE ou SAC."),
    ("sistema_amortizacao", "SACRE", "Sistema de amortização inválido. Use PRICE ou SAC."),
    ("sistema_amortizacao", 1, "Sistema de amortização inválido. Use PRICE ou SAC."),
    ("sistema_amortizacao", None, "Sistema de amortização inválido. Use PRICE ou SAC."),
    ("valor_entrada", -0.01, "O valor da entrada deve estar entre 0,00 e 9.999.999,00."),
    ("valor_entrada", 10000000, "O valor da entrada deve estar entre 0,00 e 9.999.999,00."),
    ("valor_entrada", 1.001, "Use no máximo 2 casas decimais."),
    ("valor_entrada", 95000, "A entrada deve ser menor que o valor do veículo (R$ 95.000,00); com a entrada igual ao valor não há o que financiar."),
    ("valor_entrada", 95000.01, "A entrada deve ser menor que o valor do veículo (R$ 95.000,00); com a entrada igual ao valor não há o que financiar."),
    ("simulacao_id", 1, "Campo desconhecido."),
    ("id", 1, "Campo desconhecido."),
]


@pytest.mark.parametrize("campo, valor, mensagem", CASOS_INVALIDOS)
def test_criar_422_por_campo_em_portugues(client, app, usuario, colecao, corpo_opcao, campo, valor, mensagem):
    resposta = client.post(colecao, json=corpo_opcao() | {campo: valor}, headers=usuario.cabecalho)
    assert resposta.status_code == 422
    assert resposta.get_json()["erro"] == "Dados inválidos"
    assert mensagem in resposta.get_json()["detalhes"][campo]
    assert contar_opcoes(app) == 0


def test_criar_422_sem_campos_lista_os_obrigatorios(client, usuario, colecao):
    detalhes = client.post(colecao, json={}, headers=usuario.cabecalho).get_json()["detalhes"]
    assert set(detalhes) == {"nome", "taxa_juros_mensal", "prazo_meses", "sistema_amortizacao"}


# ---------------------------------------------------------------------- limite de 3 opções

def test_quarta_opcao_da_409_e_nada_e_criado(client, app, usuario, colecao, corpo_opcao):
    for n in range(3):
        adicionar(client, usuario, colecao, corpo_opcao(nome=f"Opção {n}"))
    resposta = client.post(colecao, json=corpo_opcao(nome="Quarta"), headers=usuario.cabecalho)
    assert resposta.status_code == 409 and resposta.get_json() == LIMITE
    assert contar_opcoes(app) == 3


def test_excluir_libera_uma_vaga_e_a_ultima_opcao_pode_ser_excluida(client, usuario, colecao, corpo_opcao):
    ids = [adicionar(client, usuario, colecao, corpo_opcao(nome=f"O{n}"))["id"] for n in range(3)]
    assert client.delete(f"{colecao}/{ids[1]}", headers=usuario.cabecalho).status_code == 204
    assert client.post(colecao, json=corpo_opcao(nome="Nova"), headers=usuario.cabecalho).status_code == 201
    for opcao_id in [i for i in ids if i != ids[1]]:
        assert client.delete(f"{colecao}/{opcao_id}", headers=usuario.cabecalho).status_code == 204
    restantes = client.get(colecao, headers=usuario.cabecalho).get_json()
    assert restantes["total"] == 1  # só a "Nova"; sem mínimo: dá para esvaziar
    client.delete(f"{colecao}/{restantes['itens'][0]['id']}", headers=usuario.cabecalho)
    assert client.get(colecao, headers=usuario.cabecalho).get_json() == {"itens": [], "total": 0}


def test_o_limite_vale_por_simulacao(client, usuario, colecao, corpo_opcao, corpo_simulacao):
    outra = client.post(RAIZ, json=corpo_simulacao(nome="Outra"), headers=usuario.cabecalho).get_json()["id"]
    for n in range(3):
        adicionar(client, usuario, colecao, corpo_opcao(nome=f"A{n}"))
        adicionar(client, usuario, f"{RAIZ}/{outra}/financiamentos", corpo_opcao(nome=f"B{n}"))
    assert client.post(colecao, json=corpo_opcao(), headers=usuario.cabecalho).status_code == 409


# ---------------------------------------------------------------------- ordem de verificação

def test_ordem_dono_depois_corpo_depois_estado(client, usuario, outro_usuario, colecao, corpo_opcao):
    for n in range(3):
        adicionar(client, usuario, colecao, corpo_opcao(nome=f"O{n}"))
    invalido = corpo_opcao(prazo_meses=0)
    # dono primeiro: simulação alheia/inexistente → 404 mesmo com corpo inválido ou não-JSON
    alheio = outro_usuario.cabecalho
    assert client.post(colecao, json=invalido, headers=alheio).get_json() == SIM_NAO_ENCONTRADA
    assert client.post(colecao, data="x", headers=alheio | {"Content-Type": "text/plain"}).status_code == 404
    assert client.post(f"{RAIZ}/999999/financiamentos", json=invalido, headers=usuario.cabecalho).status_code == 404
    # corpo antes do estado: com o limite atingido, corpo ruim é 400/415/422, não 409
    assert client.post(colecao, json=invalido, headers=usuario.cabecalho).status_code == 422
    assert client.post(colecao, data="{", content_type="application/json", headers=usuario.cabecalho).status_code == 400
    assert client.post(colecao, data="x", headers=usuario.cabecalho | {"Content-Type": "text/plain"}).status_code == 415
    # corpo válido: só então o 409
    assert client.post(colecao, json=corpo_opcao(), headers=usuario.cabecalho).status_code == 409


def test_put_ordem_dono_opcao_corpo(client, usuario, outro_usuario, simulacao, colecao, corpo_opcao):
    opcao = adicionar(client, usuario, colecao, corpo_opcao())
    invalido = corpo_opcao(prazo_meses=0)
    assert client.put(f"{colecao}/{opcao['id']}", json=invalido, headers=outro_usuario.cabecalho).get_json() == SIM_NAO_ENCONTRADA
    assert client.put(f"{colecao}/999999", json=invalido, headers=usuario.cabecalho).get_json() == OPCAO_NAO_ENCONTRADA
    assert client.put(f"{colecao}/999999", data="x", headers=usuario.cabecalho | {"Content-Type": "text/plain"}).status_code == 404
    assert client.put(f"{colecao}/{opcao['id']}", json=invalido, headers=usuario.cabecalho).status_code == 422


# ---------------------------------------------------------------------- GET (lista)

def test_listar_em_ordem_de_criacao_com_envelope(client, usuario, colecao, corpo_opcao):
    assert client.get(colecao, headers=usuario.cabecalho).get_json() == {"itens": [], "total": 0}
    criadas = [adicionar(client, usuario, colecao, corpo_opcao(nome=f"O{n}")) for n in range(3)]
    corpo = client.get(colecao, headers=usuario.cabecalho).get_json()
    assert corpo == {"itens": criadas, "total": 3}


def test_nao_existe_get_de_uma_opcao_so(client, usuario, colecao, corpo_opcao):
    opcao = adicionar(client, usuario, colecao, corpo_opcao())
    resposta = client.get(f"{colecao}/{opcao['id']}", headers=usuario.cabecalho)
    assert resposta.status_code == 405 and resposta.get_json() == {"erro": "Método não permitido"}


# ---------------------------------------------------------------------- PUT

def test_atualizar_substitui_tudo_e_preserva_o_id(client, usuario, colecao, corpo_opcao):
    opcao = adicionar(client, usuario, colecao, corpo_opcao())
    novo = {"nome": "Banco Y 60x", "taxa_juros_mensal": 1.5, "prazo_meses": 60, "sistema_amortizacao": "sac"}  # sem entrada → 0
    resposta = client.put(f"{colecao}/{opcao['id']}", json=novo, headers=usuario.cabecalho)
    assert resposta.status_code == 200
    assert resposta.get_json() == {
        "id": opcao["id"], "nome": "Banco Y 60x", "taxa_juros_mensal": 1.5, "prazo_meses": 60,
        "sistema_amortizacao": "SAC", "valor_entrada": 0,
    }
    assert client.get(colecao, headers=usuario.cabecalho).get_json()["itens"] == [resposta.get_json()]


@pytest.mark.parametrize("campo, valor, mensagem", CASOS_INVALIDOS[::3])
def test_atualizar_422_mesmas_regras_e_nao_altera_nada(client, usuario, colecao, corpo_opcao, campo, valor, mensagem):
    opcao = adicionar(client, usuario, colecao, corpo_opcao())
    resposta = client.put(f"{colecao}/{opcao['id']}", json=corpo_opcao() | {campo: valor}, headers=usuario.cabecalho)
    assert resposta.status_code == 422 and mensagem in resposta.get_json()["detalhes"][campo]
    assert client.get(colecao, headers=usuario.cabecalho).get_json()["itens"] == [opcao]


def test_atualizar_confere_a_entrada_contra_o_valor_atual_do_veiculo(client, usuario, colecao, corpo_opcao):
    opcao = adicionar(client, usuario, colecao, corpo_opcao())
    assert client.put(f"{colecao}/{opcao['id']}", json=corpo_opcao(valor_entrada=94999.99), headers=usuario.cabecalho).status_code == 200
    assert client.put(f"{colecao}/{opcao['id']}", json=corpo_opcao(valor_entrada=95000), headers=usuario.cabecalho).status_code == 422


def test_atualizar_400_e_415(client, usuario, colecao, corpo_opcao):
    url = f"{colecao}/{adicionar(client, usuario, colecao, corpo_opcao())['id']}"
    assert client.put(url, data="[]", content_type="application/json", headers=usuario.cabecalho).status_code == 400
    assert client.put(url, data="x", headers=usuario.cabecalho | {"Content-Type": "text/plain"}).status_code == 415


# ---------------------------------------------------------------------- DELETE

def test_excluir_204_sem_corpo(client, usuario, colecao, corpo_opcao):
    opcao = adicionar(client, usuario, colecao, corpo_opcao())
    resposta = client.delete(f"{colecao}/{opcao['id']}", headers=usuario.cabecalho)
    assert resposta.status_code == 204 and resposta.get_data() == b""
    assert client.get(colecao, headers=usuario.cabecalho).get_json()["total"] == 0
    assert client.delete(f"{colecao}/{opcao['id']}", headers=usuario.cabecalho).get_json() == OPCAO_NAO_ENCONTRADA


# ---------------------------------------------------------------------- 404

@pytest.mark.parametrize("opcao_id", [0, 999999, *IDS_GIGANTES])
@pytest.mark.parametrize("metodo", ["put", "delete"])
def test_opcao_inexistente_ou_gigante_da_404(client, usuario, colecao, corpo_opcao, metodo, opcao_id):
    argumentos = {"json": corpo_opcao()} if metodo == "put" else {}
    resposta = getattr(client, metodo)(f"{colecao}/{opcao_id}", headers=usuario.cabecalho, **argumentos)
    assert resposta.status_code == 404 and resposta.get_json() == OPCAO_NAO_ENCONTRADA


@pytest.mark.parametrize("simulacao_id", [0, 999999, *IDS_GIGANTES])
@pytest.mark.parametrize("metodo", ["get", "post"])
def test_simulacao_inexistente_ou_gigante_da_404(client, usuario, corpo_opcao, metodo, simulacao_id):
    argumentos = {"json": corpo_opcao()} if metodo == "post" else {}
    resposta = getattr(client, metodo)(f"{RAIZ}/{simulacao_id}/financiamentos", headers=usuario.cabecalho, **argumentos)
    assert resposta.status_code == 404 and resposta.get_json() == SIM_NAO_ENCONTRADA


def test_opcao_de_outra_simulacao_do_mesmo_usuario_da_404(client, usuario, colecao, corpo_opcao, corpo_simulacao):
    outra = client.post(RAIZ, json=corpo_simulacao(nome="Outra"), headers=usuario.cabecalho).get_json()["id"]
    opcao_da_outra = adicionar(client, usuario, f"{RAIZ}/{outra}/financiamentos", corpo_opcao())
    url = f"{colecao}/{opcao_da_outra['id']}"
    assert client.put(url, json=corpo_opcao(nome="Troca"), headers=usuario.cabecalho).get_json() == OPCAO_NAO_ENCONTRADA
    assert client.delete(url, headers=usuario.cabecalho).status_code == 404
    assert client.get(f"{RAIZ}/{outra}/financiamentos", headers=usuario.cabecalho).get_json()["itens"] == [opcao_da_outra]


def test_opcoes_de_simulacao_alheia_dao_404_e_nao_mudam(client, usuario, outro_usuario, colecao, corpo_opcao):
    opcao = adicionar(client, usuario, colecao, corpo_opcao())
    alheio = outro_usuario.cabecalho
    assert client.get(colecao, headers=alheio).get_json() == SIM_NAO_ENCONTRADA
    assert client.post(colecao, json=corpo_opcao(), headers=alheio).get_json() == SIM_NAO_ENCONTRADA
    assert client.put(f"{colecao}/{opcao['id']}", json=corpo_opcao(nome="Invasor"), headers=alheio).get_json() == SIM_NAO_ENCONTRADA
    assert client.delete(f"{colecao}/{opcao['id']}", headers=alheio).get_json() == SIM_NAO_ENCONTRADA
    assert client.get(colecao, headers=usuario.cabecalho).get_json()["itens"] == [opcao]


@pytest.mark.parametrize("metodo, sufixo", [("get", ""), ("post", ""), ("put", "/1"), ("delete", "/1")])
def test_401_sem_credencial_valida(client, credenciais_recusadas, corpo_opcao, metodo, sufixo):
    for descricao, cabecalhos, mensagem in credenciais_recusadas:
        argumentos = {"json": corpo_opcao()} if metodo in ("post", "put") else {}
        resposta = getattr(client, metodo)(f"{RAIZ}/1/financiamentos{sufixo}", headers=cabecalhos, **argumentos)
        assert resposta.status_code == 401, descricao
        assert resposta.get_json() == {"erro": mensagem}, descricao
        assert resposta.headers.get("WWW-Authenticate") == "Bearer", descricao
