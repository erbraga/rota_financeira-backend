"""`GET /api/indices/{cdi|ipca}`: cache, TTL, falhas do BACEN e erros, tudo contra o servidor falso.

Nenhum teste toca a rede real: a fixture `so_servidor_local` recusa qualquer URL fora de 127.0.0.1.
O TTL é vencido reescrevendo `atualizado_em` no banco (nunca com `sleep`).
"""
import calendar
import socket
import threading
import time
from datetime import date, datetime

import pytest
import requests
from sqlalchemy import text

from app.extensions import db
from tests.integrations.servidor_falso import CDI, IPCA, serie

RAIZ = "/api/indices"
NAO_ENCONTRADO = {"erro": "Índice não encontrado"}
INDISPONIVEL = {"erro": "Dados do Banco Central indisponíveis no momento"}
PERIODOS = {"1m": 1, "3m": 3, "6m": 6, "12m": 12, "24m": 24, "60m": 60}
MODOS_DE_FALHA = ["500", "503", "406", "404_outro", "html", "quebrado", "linha_invalida", "objeto"]
MODOS_SEM_DADOS = ["404_sem_dados", "vazio"]
CAMPOS = {"indice", "descricao", "unidade", "serie_sgs", "sugestao", "periodo", "pontos", "atualizado_em", "desatualizado"}


@pytest.fixture(autouse=True)
def so_servidor_local(monkeypatch):
    original = requests.get

    def guardado(url, *args, **kwargs):
        assert url.startswith("http://127.0.0.1:"), f"tentativa de acesso à rede real: {url}"
        return original(url, *args, **kwargs)

    monkeypatch.setattr(requests, "get", guardado)


@pytest.fixture
def cabecalho(usuario):
    return usuario.cabecalho


def meses_antes(dia, meses):
    total = dia.year * 12 + dia.month - 1 - meses
    ano, mes = divmod(total, 12)
    mes += 1
    return date(ano, mes, min(dia.day, calendar.monthrange(ano, mes)[1]))


def esperado(codigo, hoje, meses=60):
    inicio = meses_antes(hoje, meses)
    return [(d, float(v)) for d, v in serie(codigo, hoje) if inicio <= d <= hoje]


def consultar(client, cabecalho, indice="cdi", consulta=""):
    return client.get(f"{RAIZ}/{indice}{consulta}", headers=cabecalho)


def cache(app, indice="CDI"):
    with app.app_context():
        linhas = db.session.execute(
            text("SELECT data_referencia, valor, atualizado_em FROM indices_economicos_cache WHERE indice = :i ORDER BY 1"),
            {"i": indice},
        ).all()
    return linhas


def total_no_cache(app):
    with app.app_context():
        return db.session.execute(text("SELECT count(*) FROM indices_economicos_cache")).scalar()


def envelhecer(app, horas=13):
    with app.app_context():
        db.session.execute(text("UPDATE indices_economicos_cache SET atualizado_em = now() - make_interval(hours => :h)"), {"h": horas})
        db.session.commit()


def porta_fechada():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ---------------------------------------------------------------------- cache vazio → BACEN → cache

def test_cache_vazio_consulta_o_bacen_uma_vez_e_grava(app, client, cabecalho, servidor_falso):
    resposta = consultar(client, cabecalho)
    corpo = resposta.get_json()
    hoje = servidor_falso.hoje
    assert resposta.status_code == 200 and set(corpo) == CAMPOS
    assert (corpo["indice"], corpo["descricao"], corpo["unidade"], corpo["serie_sgs"]) == ("CDI", "Taxa CDI anualizada, base 252", "% a.a.", 4389)
    assert corpo["desatualizado"] is False and corpo["atualizado_em"]
    assert servidor_falso.numero_de_chamadas() == 1
    codigo, inicial, final = servidor_falso.chamadas[0]
    assert (codigo, inicial, final) == (CDI, meses_antes(hoje, 60).strftime("%d/%m/%Y"), hoje.strftime("%d/%m/%Y"))
    linhas = esperado(CDI, hoje)
    assert [(l[0], float(l[1])) for l in cache(app)] == linhas  # janela de 60 meses, valores como publicados


def test_sugestao_e_o_ultimo_valor_publicado_ate_hoje(client, cabecalho, servidor_falso):
    corpo = consultar(client, cabecalho).get_json()
    ultima_data, ultimo_valor = esperado(CDI, servidor_falso.hoje)[-1]
    assert corpo["sugestao"] == {"valor": ultimo_valor, "data_referencia": ultima_data.isoformat()}
    assert ultima_data < servidor_falso.hoje  # o CDI é publicado com defasagem de pelo menos 1 dia


def test_numeros_como_numero_json_e_datas_iso(client, cabecalho, servidor_falso):
    corpo = consultar(client, cabecalho).get_json()
    assert isinstance(corpo["sugestao"]["valor"], float) and isinstance(corpo["serie_sgs"], int)
    assert all(isinstance(p["valor"], float) and len(p["data"]) == 10 for p in corpo["pontos"])
    assert datetime.fromisoformat(corpo["atualizado_em"]).tzinfo is not None
    assert corpo["periodo"]["fim"] == servidor_falso.hoje.isoformat()


def test_ipca_usa_a_serie_13522_e_a_sugestao_e_o_ultimo_mes_no_dia_1(app, client, cabecalho, servidor_falso):
    corpo = consultar(client, cabecalho, "ipca").get_json()
    ultima_data, ultimo_valor = esperado(IPCA, servidor_falso.hoje)[-1]
    assert (corpo["indice"], corpo["serie_sgs"], corpo["unidade"]) == ("IPCA", 13522, "% a.a.")
    assert corpo["sugestao"] == {"valor": ultimo_valor, "data_referencia": ultima_data.isoformat()} and ultima_data.day == 1
    assert [(l[0], float(l[1])) for l in cache(app, "IPCA")] == esperado(IPCA, servidor_falso.hoje)
    assert servidor_falso.chamadas[0][0] == IPCA


def test_cada_indice_tem_o_proprio_cache(client, cabecalho, servidor_falso):
    consultar(client, cabecalho, "cdi")
    consultar(client, cabecalho, "ipca")
    assert [c[0] for c in servidor_falso.chamadas] == [CDI, IPCA]
    consultar(client, cabecalho, "cdi")
    consultar(client, cabecalho, "ipca")
    assert servidor_falso.numero_de_chamadas() == 2


# ---------------------------------------------------------------------- TTL

def test_repetir_dentro_do_ttl_sai_do_cache(client, cabecalho, servidor_falso):
    primeira = consultar(client, cabecalho).get_json()
    segunda = consultar(client, cabecalho).get_json()
    assert servidor_falso.numero_de_chamadas() == 1
    assert segunda == primeira and segunda["desatualizado"] is False


def test_apos_o_ttl_consulta_de_novo_renova_o_cache_e_nao_duplica(app, client, cabecalho, servidor_falso):
    primeira = consultar(client, cabecalho).get_json()
    antes = cache(app)
    envelhecer(app, 13)  # TTL padrão: 12 h
    segunda = consultar(client, cabecalho).get_json()
    assert servidor_falso.numero_de_chamadas() == 2
    assert segunda["atualizado_em"] > primeira["atualizado_em"] and segunda["desatualizado"] is False
    depois = cache(app)
    assert [(l[0], l[1]) for l in depois] == [(l[0], l[1]) for l in antes]  # mesmas linhas, sem duplicar


def test_ttl_e_configuravel_por_ambiente(app, client, cabecalho, servidor_falso, monkeypatch):
    consultar(client, cabecalho)
    envelhecer(app, 13)
    monkeypatch.setitem(app.config, "INDICES_TTL_HORAS", 24)
    assert consultar(client, cabecalho).get_json()["desatualizado"] is False
    assert servidor_falso.numero_de_chamadas() == 1  # com TTL de 24 h, 13 h ainda vale


def test_o_upsert_atualiza_o_valor_de_uma_data_ja_gravada(app, client, cabecalho, servidor_falso):
    consultar(client, cabecalho)
    data = cache(app)[-1][0]
    with app.app_context():
        db.session.execute(text("UPDATE indices_economicos_cache SET valor = 99 WHERE indice = 'CDI' AND data_referencia = :d"), {"d": data})
        db.session.commit()
    envelhecer(app)
    consultar(client, cabecalho)
    assert float(cache(app)[-1][1]) == esperado(CDI, servidor_falso.hoje)[-1][1]  # voltou ao valor publicado


# ---------------------------------------------------------------------- períodos

@pytest.mark.parametrize("periodo, meses", PERIODOS.items())
def test_periodo_filtra_o_cache_e_nao_consulta_o_bacen(client, cabecalho, servidor_falso, periodo, meses):
    consultar(client, cabecalho)  # enche o cache (1 chamada)
    corpo = consultar(client, cabecalho, consulta=f"?periodo={periodo}").get_json()
    hoje = servidor_falso.hoje
    assert servidor_falso.numero_de_chamadas() == 1
    assert corpo["periodo"] == {"inicio": meses_antes(hoje, meses).isoformat(), "fim": hoje.isoformat()}
    datas = [p["data"] for p in corpo["pontos"]]
    assert datas == sorted(datas) and datas
    assert datas[0] >= corpo["periodo"]["inicio"] and datas[-1] <= corpo["periodo"]["fim"]
    assert [(p["data"], p["valor"]) for p in corpo["pontos"]] == [(d.isoformat(), v) for d, v in esperado(CDI, hoje, meses)]


def test_periodos_maiores_trazem_mais_pontos_e_a_sugestao_nao_muda(client, cabecalho, servidor_falso):
    corpos = {p: consultar(client, cabecalho, consulta=f"?periodo={p}").get_json() for p in PERIODOS}
    tamanhos = [len(corpos[p]["pontos"]) for p in PERIODOS]
    assert tamanhos == sorted(set(tamanhos))  # estritamente crescente
    assert len({str(c["sugestao"]) for c in corpos.values()}) == 1
    assert servidor_falso.numero_de_chamadas() == 1


def test_sem_periodo_vale_12m(client, cabecalho, servidor_falso):
    assert consultar(client, cabecalho).get_json() == consultar(client, cabecalho, consulta="?periodo=12m").get_json()


@pytest.mark.parametrize(
    "consulta",
    ["?periodo=13m", "?periodo=abc", "?periodo=0", "?periodo=-1", "?periodo=12M", "?periodo=", "?periodo=12", "?periodo=1m&periodo=3m", "?x=1", "?periodo=1m&x=1"],
)
def test_periodo_invalido_da_422_em_portugues_sem_consultar_o_bacen(client, cabecalho, servidor_falso, consulta):
    resposta = consultar(client, cabecalho, consulta=consulta)
    corpo = resposta.get_json()
    assert resposta.status_code == 422 and corpo["erro"] == "Dados inválidos" and corpo["detalhes"]
    if "x=1" not in consulta and "periodo=1m&" not in consulta:
        assert corpo["detalhes"]["periodo"] == ["O período deve ser um destes: 1m, 3m, 6m, 12m, 24m, 60m."]
    assert not any(e in resposta.get_data(as_text=True) for e in ("Not a valid", "Unknown field", "Must be one of"))
    assert servidor_falso.numero_de_chamadas() == 0


# ---------------------------------------------------------------------- 404 e 401

@pytest.mark.parametrize("indice", ["selic", "CDI", "IPCA", "Cdi", "abc", "ipca1", "cdi%20", "1", "sgs"])
def test_indice_desconhecido_da_404_sem_consultar_nem_gravar(app, client, cabecalho, servidor_falso, indice):
    resposta = consultar(client, cabecalho, indice)
    assert resposta.status_code == 404 and resposta.get_json() == NAO_ENCONTRADO
    assert servidor_falso.numero_de_chamadas() == 0 and total_no_cache(app) == 0


def test_o_404_do_indice_vem_antes_do_422_do_periodo(client, cabecalho, servidor_falso):
    assert consultar(client, cabecalho, "selic", "?periodo=abc").status_code == 404


@pytest.mark.parametrize("indice", ["cdi", "ipca", "selic"])
def test_401_sem_credencial_valida_vem_antes_de_tudo(client, servidor_falso, credenciais_recusadas, indice):
    for descricao, cabecalhos, mensagem in credenciais_recusadas:
        resposta = client.get(f"{RAIZ}/{indice}?periodo=abc", headers=cabecalhos)
        assert resposta.status_code == 401 and resposta.get_json() == {"erro": mensagem}, descricao
        assert resposta.headers.get("WWW-Authenticate") == "Bearer", descricao
    assert servidor_falso.numero_de_chamadas() == 0


# ---------------------------------------------------------------------- BACEN fora do ar COM cache

@pytest.mark.parametrize("modo", MODOS_DE_FALHA + MODOS_SEM_DADOS)
def test_falha_do_bacen_com_cache_serve_os_dados_antigos_marcados(app, client, cabecalho, servidor_falso, modo):
    antes = consultar(client, cabecalho).get_json()
    linhas = cache(app)
    envelhecer(app)
    linhas_envelhecidas = cache(app)
    servidor_falso.modo = modo
    resposta = consultar(client, cabecalho)
    corpo = resposta.get_json()
    assert resposta.status_code == 200 and corpo["desatualizado"] is True
    assert corpo["pontos"] == antes["pontos"] and corpo["sugestao"] == antes["sugestao"]
    assert corpo["atualizado_em"] < antes["atualizado_em"]  # o `atualizado_em` real, sem renovar
    assert cache(app) == linhas_envelhecidas and len(linhas_envelhecidas) == len(linhas)  # nada novo gravado


def test_timeout_do_bacen_com_cache_serve_o_cache_dentro_do_timeout(app, client, cabecalho, servidor_falso, monkeypatch):
    consultar(client, cabecalho)
    envelhecer(app)
    monkeypatch.setitem(app.config, "BACEN_TIMEOUT_SEGUNDOS", 0.3)
    servidor_falso.atraso = 1.5
    inicio = time.perf_counter()
    corpo = consultar(client, cabecalho).get_json()
    assert corpo["desatualizado"] is True and time.perf_counter() - inicio < 1.2


def test_conexao_recusada_com_cache_serve_o_cache(app, client, cabecalho, servidor_falso, monkeypatch):
    consultar(client, cabecalho)
    envelhecer(app)
    monkeypatch.setitem(app.config, "BACEN_URL_BASE", f"http://127.0.0.1:{porta_fechada()}/bcdata.sgs")
    assert consultar(client, cabecalho).get_json()["desatualizado"] is True


def test_o_cache_volta_ao_normal_quando_o_bacen_volta(app, client, cabecalho, servidor_falso):
    consultar(client, cabecalho)
    envelhecer(app)
    servidor_falso.modo = "500"
    assert consultar(client, cabecalho).get_json()["desatualizado"] is True
    servidor_falso.modo = None
    assert consultar(client, cabecalho).get_json()["desatualizado"] is False


# ---------------------------------------------------------------------- BACEN fora do ar SEM cache

@pytest.mark.parametrize("modo", MODOS_DE_FALHA + MODOS_SEM_DADOS)
def test_falha_do_bacen_sem_cache_da_503_generico_e_nao_grava(app, client, cabecalho, servidor_falso, modo):
    servidor_falso.modo = modo
    resposta = consultar(client, cabecalho)
    assert resposta.status_code == 503 and resposta.get_json() == INDISPONIVEL
    texto = resposta.get_data(as_text=True)
    assert not any(vazado in texto for vazado in ("127.0.0.1", "Manuten", "Traceback", "bcdata", "Internal Server"))
    assert total_no_cache(app) == 0


def test_timeout_e_conexao_recusada_sem_cache_dao_503(app, client, cabecalho, servidor_falso, monkeypatch):
    monkeypatch.setitem(app.config, "BACEN_TIMEOUT_SEGUNDOS", 0.3)
    servidor_falso.atraso = 1.5
    inicio = time.perf_counter()
    assert consultar(client, cabecalho, "ipca").get_json() == INDISPONIVEL
    assert time.perf_counter() - inicio < 1.2
    monkeypatch.setitem(app.config, "BACEN_URL_BASE", f"http://127.0.0.1:{porta_fechada()}/bcdata.sgs")
    assert consultar(client, cabecalho).status_code == 503
    assert total_no_cache(app) == 0


def test_com_o_bacen_fora_do_ar_o_resto_da_api_continua_funcionando(client, cabecalho, servidor_falso):
    servidor_falso.modo = "500"
    assert consultar(client, cabecalho).status_code == 503
    assert client.get("/api/saude").status_code == 200
    assert client.get("/api/simulacoes", headers=cabecalho).status_code == 200
    assert client.get("/apidocs/").status_code == 200


# ---------------------------------------------------------------------- dados do BACEN

def test_datas_futuras_do_bacen_nao_entram_no_cache_nem_na_resposta(app, client, cabecalho, servidor_falso):
    servidor_falso.modo = "futuro"  # a série normal (últimas 3 linhas) + 3 linhas futuras com valor 99,99
    corpo = consultar(client, cabecalho).get_json()
    hoje = servidor_falso.hoje.isoformat()
    assert all(p["data"] <= hoje for p in corpo["pontos"]) and corpo["sugestao"]["valor"] != 99.99
    assert all(l[0].isoformat() <= hoje and float(l[1]) != 99.99 for l in cache(app))


def test_consultas_simultaneas_com_cache_vazio_dao_200_e_nao_duplicam(app, cabecalho, servidor_falso):
    respostas = []

    def chamar():
        respostas.append(app.test_client().get(f"{RAIZ}/cdi", headers=cabecalho))

    threads = [threading.Thread(target=chamar) for _ in range(6)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert [r.status_code for r in respostas] == [200] * 6
    assert len({r.get_json()["sugestao"]["data_referencia"] for r in respostas}) == 1
    datas = [l[0] for l in cache(app)]
    assert len(datas) == len(set(datas)) == len(esperado(CDI, servidor_falso.hoje))
