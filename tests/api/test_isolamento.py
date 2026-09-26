"""Isolamento entre usuários: recurso alheio e inexistente dão o MESMO 404, e nada muda nem vaza."""
import pytest

RAIZ = "/api/simulacoes"
INEXISTENTE = 999999


@pytest.fixture
def dados_da_ana(client, usuario, corpo_simulacao, corpo_opcao):
    h = usuario.cabecalho
    simulacao = client.post(RAIZ, json=corpo_simulacao(nome="Da Ana"), headers=h).get_json()["id"]
    opcoes = [
        client.post(f"{RAIZ}/{simulacao}/financiamentos", json=corpo_opcao(nome=f"Opção {n}"), headers=h).get_json()["id"]
        for n in range(2)
    ]
    return {"simulacao": simulacao, "opcoes": opcoes}


def rotas(sim, opcao, corpo_simulacao, corpo_opcao):
    """(descrição, método, caminho, argumentos) de cada rota que recebe o id de uma simulação."""
    base = f"{RAIZ}/{sim}"
    return [
        ("GET simulação", "get", base, {}),
        ("PUT simulação", "put", base, {"json": corpo_simulacao(nome="Invasor")}),
        ("DELETE simulação", "delete", base, {}),
        ("GET opções", "get", f"{base}/financiamentos", {}),
        ("POST opção", "post", f"{base}/financiamentos", {"json": corpo_opcao(nome="Invasora")}),
        ("PUT opção", "put", f"{base}/financiamentos/{opcao}", {"json": corpo_opcao(nome="Invasora")}),
        ("DELETE opção", "delete", f"{base}/financiamentos/{opcao}", {}),
        ("GET parcelas", "get", f"{base}/financiamentos/{opcao}/parcelas", {}),
        ("GET resultado", "get", f"{base}/resultado", {}),
        ("GET resultado com aporte", "get", f"{base}/resultado?aporte_mensal=1500", {}),
        ("GET resultado com parâmetro inválido", "get", f"{base}/resultado?aporte_mensal=abc", {}),
    ]


def test_toda_rota_devolve_o_mesmo_404_para_alheio_e_inexistente(client, dados_da_ana, outro_usuario, corpo_simulacao, corpo_opcao):
    opcao = dados_da_ana["opcoes"][0]
    alheias = rotas(dados_da_ana["simulacao"], opcao, corpo_simulacao, corpo_opcao)
    inexistentes = rotas(INEXISTENTE, opcao, corpo_simulacao, corpo_opcao)
    for (descricao, metodo, caminho_alheio, args), (_, _, caminho_inexistente, _) in zip(alheias, inexistentes):
        alheia = getattr(client, metodo)(caminho_alheio, headers=outro_usuario.cabecalho, **args)
        inexistente = getattr(client, metodo)(caminho_inexistente, headers=outro_usuario.cabecalho, **args)
        assert alheia.status_code == inexistente.status_code == 404, descricao
        assert alheia.get_json() == inexistente.get_json() == {"erro": "Simulação não encontrada"}, descricao
        assert alheia.headers.get("Content-Type") == inexistente.headers.get("Content-Type"), descricao


def test_as_tentativas_do_outro_usuario_nao_alteram_nada(client, usuario, dados_da_ana, outro_usuario, corpo_simulacao, corpo_opcao):
    h = usuario.cabecalho
    sim = dados_da_ana["simulacao"]

    def foto():
        return (
            client.get(f"{RAIZ}/{sim}", headers=h).get_json(),
            client.get(f"{RAIZ}/{sim}/financiamentos", headers=h).get_json(),
            client.get(f"{RAIZ}/{sim}/resultado", headers=h).get_json(),
        )

    antes = foto()
    for _, metodo, caminho, args in rotas(sim, dados_da_ana["opcoes"][0], corpo_simulacao, corpo_opcao):
        getattr(client, metodo)(caminho, headers=outro_usuario.cabecalho, **args)
    assert foto() == antes


def test_o_outro_usuario_nao_ve_nada_nas_listagens(client, dados_da_ana, outro_usuario):
    assert client.get(RAIZ, headers=outro_usuario.cabecalho).get_json() == {"itens": [], "total": 0}


def test_cada_usuario_ve_so_as_proprias_simulacoes(client, usuario, dados_da_ana, outro_usuario, corpo_simulacao):
    do_beto = client.post(RAIZ, json=corpo_simulacao(nome="Do Beto"), headers=outro_usuario.cabecalho).get_json()["id"]
    da_ana = client.get(RAIZ, headers=usuario.cabecalho).get_json()
    do_beto_lista = client.get(RAIZ, headers=outro_usuario.cabecalho).get_json()
    assert [i["id"] for i in da_ana["itens"]] == [dados_da_ana["simulacao"]]
    assert [i["id"] for i in do_beto_lista["itens"]] == [do_beto]
    assert client.get(f"{RAIZ}/{do_beto}", headers=usuario.cabecalho).status_code == 404  # e vice-versa


def test_opcao_da_ana_nao_e_alcancavel_pela_simulacao_do_beto(client, dados_da_ana, outro_usuario, corpo_simulacao, corpo_opcao):
    sim_do_beto = client.post(RAIZ, json=corpo_simulacao(), headers=outro_usuario.cabecalho).get_json()["id"]
    opcao_da_ana = dados_da_ana["opcoes"][0]
    url = f"{RAIZ}/{sim_do_beto}/financiamentos/{opcao_da_ana}"
    for metodo, args in (("put", {"json": corpo_opcao(nome="Roubo")}), ("delete", {}), ("get", {})):
        resposta = getattr(client, metodo)(url + ("/parcelas" if metodo == "get" else ""), headers=outro_usuario.cabecalho, **args)
        assert resposta.status_code == 404 and resposta.get_json() == {"erro": "Opção de financiamento não encontrada"}


def test_usuario_id_no_corpo_nunca_e_aceito(client, usuario, outro_usuario, corpo_simulacao):
    resposta = client.post(RAIZ, json=corpo_simulacao() | {"usuario_id": usuario.id}, headers=outro_usuario.cabecalho)
    assert resposta.status_code == 422 and "usuario_id" in resposta.get_json()["detalhes"]
    assert client.get(RAIZ, headers=usuario.cabecalho).get_json()["total"] == 0


def test_excluir_a_simulacao_da_ana_nao_afeta_a_do_beto(client, usuario, dados_da_ana, outro_usuario, corpo_simulacao, corpo_opcao):
    sim_beto = client.post(RAIZ, json=corpo_simulacao(nome="Do Beto"), headers=outro_usuario.cabecalho).get_json()["id"]
    client.post(f"{RAIZ}/{sim_beto}/financiamentos", json=corpo_opcao(), headers=outro_usuario.cabecalho)
    assert client.delete(f"{RAIZ}/{dados_da_ana['simulacao']}", headers=usuario.cabecalho).status_code == 204
    assert client.get(f"{RAIZ}/{sim_beto}/financiamentos", headers=outro_usuario.cabecalho).get_json()["total"] == 1
