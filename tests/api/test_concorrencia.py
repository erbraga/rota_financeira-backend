"""Corrida real (duas threads, uma conexão de banco cada) nas regras que dependem do `FOR UPDATE`.

A sobreposição é forçada por uma pausa dentro da gravação (ouvinte SQLAlchemy `before_insert` /
`before_update`), depois de a regra ter sido conferida e antes do commit. Cada cenário tem um
CONTROLE sem bloqueio (`obter_simulacao(..., bloquear=False)`) que precisa FURAR a regra: é o que prova
que o teste enxerga a corrida e que a proteção vem do bloqueio, não de sorte.
"""
import threading
import time
from contextlib import contextmanager

import pytest
from sqlalchemy import event, text

from app.extensions import db
from app.models import OpcaoFinanciamento, Simulacao

RAIZ = "/api/simulacoes"
PAUSA = 0.3  # segundos dentro da gravação
ATRASO_DO_SEGUNDO = 0.08  # o segundo pedido entra enquanto o primeiro ainda grava


@contextmanager
def pausa_na_gravacao(modelo, evento):
    def dormir(*_):
        time.sleep(PAUSA)

    event.listen(modelo, evento, dormir)
    try:
        yield
    finally:
        event.remove(modelo, evento, dormir)


def sem_bloqueio(monkeypatch, *modulos):
    """Controle: as rotas passam a obter a simulação sem `FOR UPDATE`."""
    for modulo in modulos:
        original = modulo.obter_simulacao
        monkeypatch.setattr(
            modulo, "obter_simulacao",
            lambda usuario, simulacao_id, bloquear=False, _original=original: _original(usuario, simulacao_id, bloquear=False),
        )


def disparar(app, pedidos):
    """Executa os pedidos `(método, caminho, corpo, cabeçalho)` em threads, o 2º logo após o 1º."""
    status = [None] * len(pedidos)

    def executar(i, metodo, caminho, corpo, cabecalho):
        status[i] = getattr(app.test_client(), metodo)(caminho, json=corpo, headers=cabecalho).status_code

    threads = [threading.Thread(target=executar, args=(i, *pedido)) for i, pedido in enumerate(pedidos)]
    for thread in threads:
        thread.start()
        time.sleep(ATRASO_DO_SEGUNDO)
    for thread in threads:
        thread.join(timeout=20)
        assert not thread.is_alive(), "requisição travada"
    assert None not in status, "uma das requisições estourou"
    return status


def consultar(app, sql, **parametros):
    with app.app_context():
        return db.session.execute(text(sql), parametros).all()


# ---------------------------------------------------------------------- limite de 3 opções

@pytest.fixture
def com_duas_opcoes(client, usuario, corpo_simulacao, corpo_opcao):
    sim = client.post(RAIZ, json=corpo_simulacao(), headers=usuario.cabecalho).get_json()["id"]
    for n in range(2):
        assert client.post(f"{RAIZ}/{sim}/financiamentos", json=corpo_opcao(nome=f"O{n}"), headers=usuario.cabecalho).status_code == 201
    return sim


def dois_posts(usuario, sim, corpo_opcao):
    url = f"{RAIZ}/{sim}/financiamentos"
    return [("post", url, corpo_opcao(nome="Corrida A"), usuario.cabecalho), ("post", url, corpo_opcao(nome="Corrida B"), usuario.cabecalho)]


def test_dois_posts_simultaneos_na_ultima_vaga_so_um_vence(app, usuario, com_duas_opcoes, corpo_opcao):
    with pausa_na_gravacao(OpcaoFinanciamento, "before_insert"):
        status = disparar(app, dois_posts(usuario, com_duas_opcoes, corpo_opcao))
    assert sorted(status) == [201, 409]
    assert consultar(app, "SELECT count(*) FROM opcoes_financiamento") == [(3,)]


def test_controle_sem_bloqueio_fura_o_limite_de_tres_opcoes(app, monkeypatch, usuario, com_duas_opcoes, corpo_opcao):
    import app.routes.financiamentos as rota

    sem_bloqueio(monkeypatch, rota)
    with pausa_na_gravacao(OpcaoFinanciamento, "before_insert"):
        status = disparar(app, dois_posts(usuario, com_duas_opcoes, corpo_opcao))
    assert status == [201, 201]  # sem o FOR UPDATE, os dois passam
    assert consultar(app, "SELECT count(*) FROM opcoes_financiamento") == [(4,)]  # a regra foi furada


# ---------------------------------------------------------------------- entrada da opção < valor do veículo

@pytest.fixture
def com_uma_opcao(client, usuario, corpo_simulacao, corpo_opcao):
    sim = client.post(RAIZ, json=corpo_simulacao(), headers=usuario.cabecalho).get_json()["id"]  # veículo 95.000
    opcao = client.post(f"{RAIZ}/{sim}/financiamentos", json=corpo_opcao(valor_entrada=20000), headers=usuario.cabecalho).get_json()["id"]
    return sim, opcao


def par_de_puts(usuario, sim, opcao, corpo_simulacao, corpo_opcao, sim_primeiro):
    """Cada um é válido sozinho (veículo 50.000 > entrada 20.000; entrada 60.000 < veículo 95.000), juntos não."""
    baixa_o_veiculo = ("put", f"{RAIZ}/{sim}", corpo_simulacao(valor_veiculo=50000, valor_entrada=0), usuario.cabecalho)
    sobe_a_entrada = ("put", f"{RAIZ}/{sim}/financiamentos/{opcao}", corpo_opcao(valor_entrada=60000), usuario.cabecalho)
    return [baixa_o_veiculo, sobe_a_entrada] if sim_primeiro else [sobe_a_entrada, baixa_o_veiculo]


def entrada_maior_ou_igual_ao_veiculo(app):
    return consultar(
        app,
        "SELECT o.valor_entrada, s.valor_veiculo FROM opcoes_financiamento o JOIN simulacoes s ON s.id = o.simulacao_id "
        "WHERE o.valor_entrada >= s.valor_veiculo",
    )


@pytest.mark.parametrize("sim_primeiro", [True, False], ids=["put_da_simulacao_primeiro", "put_da_opcao_primeiro"])
def test_puts_simultaneos_nunca_deixam_a_entrada_igual_ou_maior_que_o_veiculo(app, usuario, com_uma_opcao, corpo_simulacao, corpo_opcao, sim_primeiro):
    sim, opcao = com_uma_opcao
    pedidos = par_de_puts(usuario, sim, opcao, corpo_simulacao, corpo_opcao, sim_primeiro)
    with pausa_na_gravacao(Simulacao, "before_update"), pausa_na_gravacao(OpcaoFinanciamento, "before_update"):
        status = disparar(app, pedidos)
    assert sorted(status) == [200, 422]  # o primeiro vence; o segundo já enxerga o resultado dele
    assert status[0] == 200
    assert entrada_maior_ou_igual_ao_veiculo(app) == []


@pytest.mark.parametrize("sim_primeiro", [True, False], ids=["put_da_simulacao_primeiro", "put_da_opcao_primeiro"])
def test_controle_sem_bloqueio_fura_a_regra_da_entrada(app, monkeypatch, usuario, com_uma_opcao, corpo_simulacao, corpo_opcao, sim_primeiro):
    import app.routes.financiamentos as rota_de_opcoes
    import app.routes.simulacoes as rota_de_simulacoes

    sim, opcao = com_uma_opcao
    sem_bloqueio(monkeypatch, rota_de_simulacoes, rota_de_opcoes)
    pedidos = par_de_puts(usuario, sim, opcao, corpo_simulacao, corpo_opcao, sim_primeiro)
    with pausa_na_gravacao(Simulacao, "before_update"), pausa_na_gravacao(OpcaoFinanciamento, "before_update"):
        status = disparar(app, pedidos)
    assert status == [200, 200]  # sem o FOR UPDATE, os dois passam
    assert entrada_maior_ou_igual_ao_veiculo(app) == [(60000, 50000)]  # a regra foi furada
