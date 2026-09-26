"""O fluxo do frontend de ponta a ponta, só por HTTP (com o login real)."""

RAIZ = "/api/simulacoes"


def test_fluxo_completo_registrar_ate_excluir(client, corpo_simulacao, corpo_opcao):
    # 1. registrar e entrar (a senha só existe no corpo destas duas requisições)
    registro = client.post("/api/auth/registrar", json={"nome": "Diana Lima", "email": "diana@exemplo.com", "senha": "senha-da-diana-1"})
    assert registro.status_code == 201
    login = client.post("/api/auth/login", json={"email": "diana@exemplo.com", "senha": "senha-da-diana-1"})
    assert login.status_code == 200
    h = {"Authorization": f"Bearer {login.get_json()['access_token']}"}
    assert client.get("/api/auth/perfil", headers=h).get_json()["email"] == "diana@exemplo.com"

    # 2. criar a simulação (a lista começa vazia)
    assert client.get(RAIZ, headers=h).get_json() == {"itens": [], "total": 0}
    criada = client.post(RAIZ, json=corpo_simulacao(), headers=h)
    assert criada.status_code == 201
    sim = criada.get_json()["id"]
    assert criada.headers["Location"].endswith(f"{RAIZ}/{sim}")

    # 3. sem opções, o resultado já traz à vista e fundo
    vazio = client.get(f"{RAIZ}/{sim}/resultado", headers=h).get_json()
    assert vazio["cenarios"]["financiamentos"] == [] and vazio["menor_custo"]["cenario"] == "a_vista"

    # 4. adicionar as 3 opções; a 4ª é recusada
    opcoes = [
        client.post(f"{RAIZ}/{sim}/financiamentos", json=corpo, headers=h).get_json()["id"]
        for corpo in (
            corpo_opcao(),
            corpo_opcao(nome="Banco Y 60x", taxa_juros_mensal=1.5, prazo_meses=60, sistema_amortizacao="SAC", valor_entrada=30000),
            corpo_opcao(nome="Banco Z 36x", taxa_juros_mensal=1.2, prazo_meses=36, valor_entrada=10000),
        )
    ]
    assert client.post(f"{RAIZ}/{sim}/financiamentos", json=corpo_opcao(), headers=h).status_code == 409
    assert client.get(f"{RAIZ}/{sim}/financiamentos", headers=h).get_json()["total"] == 3

    # 5. resultado com os 3 financiamentos, parcelas e modo aporte
    resultado = client.get(f"{RAIZ}/{sim}/resultado", headers=h).get_json()
    assert [f["id"] for f in resultado["cenarios"]["financiamentos"]] == opcoes
    assert resultado["cenarios"]["financiamentos"][0]["custo_total"] == 137128.07
    assert resultado["cenarios"]["financiamentos"][1]["custo_total"] == 124737.5
    assert len(resultado["series"]) == 61
    parcelas = client.get(f"{RAIZ}/{sim}/financiamentos/{opcoes[0]}/parcelas", headers=h).get_json()
    assert len(parcelas["parcelas"]) == 48 and parcelas["totais"]["custo_total"] == 137128.07
    assert client.get(f"{RAIZ}/{sim}/resultado?aporte_mensal=1500", headers=h).get_json()["cenarios"]["fundo"]["mes_da_meta"] == 46

    # 6. editar a simulação muda o resultado; a edição que invalidaria uma opção é recusada
    assert client.put(f"{RAIZ}/{sim}", json=corpo_simulacao(valor_veiculo=30000, valor_entrada=0), headers=h).status_code == 422
    assert client.put(f"{RAIZ}/{sim}", json=corpo_simulacao(valor_veiculo=100000), headers=h).status_code == 200
    assert client.get(f"{RAIZ}/{sim}/resultado", headers=h).get_json()["cenarios"]["a_vista"] == {"custo_total": 100000.0}

    # 7. excluir uma opção e depois a simulação
    assert client.delete(f"{RAIZ}/{sim}/financiamentos/{opcoes[2]}", headers=h).status_code == 204
    assert len(client.get(f"{RAIZ}/{sim}/resultado", headers=h).get_json()["cenarios"]["financiamentos"]) == 2
    assert client.delete(f"{RAIZ}/{sim}", headers=h).status_code == 204
    for caminho in (f"{RAIZ}/{sim}", f"{RAIZ}/{sim}/financiamentos", f"{RAIZ}/{sim}/resultado", f"{RAIZ}/{sim}/financiamentos/{opcoes[0]}/parcelas"):
        assert client.get(caminho, headers=h).status_code == 404, caminho
    assert client.get(RAIZ, headers=h).get_json() == {"itens": [], "total": 0}
