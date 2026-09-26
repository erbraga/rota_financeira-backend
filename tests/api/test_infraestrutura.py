"""A própria infraestrutura de testes de integração: banco, esquema, limpeza e fixtures."""
from alembic.script import ScriptDirectory
from sqlalchemy import text

from app.extensions import db
from app.models import Usuario
from tests.banco_de_teste import conectar_ao_banco_de_teste, url_do_banco_de_teste
from tests.conftest import RAIZ, limpar_banco

TABELAS_ESPERADAS = {"usuarios", "simulacoes", "opcoes_financiamento", "indices_economicos_cache"}


def _consultar(app, consulta):
    with app.app_context():
        return db.session.execute(text(consulta)).all()


def test_usa_bd_test(app):
    [(nome,)] = _consultar(app, "SELECT current_database()")
    assert nome == url_do_banco_de_teste().database
    assert nome.endswith("_test")
    assert nome != app.config["SQLALCHEMY_DATABASE_URI"].rsplit("/", 1)[-1] or nome == "bd_test"


def test_o_esquema_vem_da_migration(app):
    cabeca = ScriptDirectory(str(RAIZ / "migrations")).get_current_head()
    [(revisao,)] = _consultar(app, "SELECT version_num FROM alembic_version")
    assert revisao == cabeca
    tabelas = {t for (t,) in _consultar(app, "SELECT tablename FROM pg_tables WHERE schemaname = 'public'")}
    assert tabelas == TABELAS_ESPERADAS | {"alembic_version"}


def test_toda_restricao_nomeada_dos_models_existe_no_banco(app):
    esperadas = {
        str(restricao.name)
        for tabela in db.metadata.sorted_tables
        for restricao in tabela.constraints
        if restricao.name
    }
    assert any(nome.startswith("ck_") for nome in esperadas) and any(nome.startswith("uq_") for nome in esperadas)
    existentes = {nome for (nome,) in _consultar(app, "SELECT conname FROM pg_constraint")}
    assert esperadas <= existentes, f"faltam no banco: {sorted(esperadas - existentes)}"


def test_1_deixa_dados_no_banco(usuario):
    """Par com o teste 2: o segundo só passa se a limpeza automática funcionar."""
    assert usuario.id == 1


def test_2_encontra_o_banco_vazio_e_com_identidade_zerada(app, usuario):
    assert usuario.id == 1  # RESTART IDENTITY: o primeiro usuário de cada teste é o de id 1
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count()).select_from(Usuario)) == 1


def test_limpar_banco_zera_todas_as_tabelas(app, usuario):
    limpar_banco(app)
    for tabela in TABELAS_ESPERADAS:
        assert _consultar(app, f"SELECT count(*) FROM {tabela}") == [(0,)], tabela


def test_o_banco_de_desenvolvimento_nao_e_usado(app):
    url = url_do_banco_de_teste()
    with conectar_ao_banco_de_teste(url) as conexao:
        [(usuarios,)] = conexao.execute("SELECT count(*) FROM usuarios").fetchall()
    assert usuarios == 0  # nada de dev: o banco de teste começa cada teste vazio
    assert url.database.endswith("_test")


def test_fixtures_de_usuario_e_token_funcionam(client, usuario, outro_usuario):
    assert usuario.id != outro_usuario.id
    resposta = client.get("/api/auth/perfil", headers=usuario.cabecalho)
    assert resposta.status_code == 200 and resposta.get_json()["email"] == "ana@exemplo.com"
    assert client.get("/api/auth/perfil", headers=outro_usuario.cabecalho).get_json()["email"] == "beto@exemplo.com"


def test_corpos_de_exemplo_sao_aceitos_pela_api(client, usuario, corpo_simulacao, corpo_opcao):
    criada = client.post("/api/simulacoes", json=corpo_simulacao(), headers=usuario.cabecalho)
    assert criada.status_code == 201
    opcao = client.post(f"/api/simulacoes/{criada.get_json()['id']}/financiamentos", json=corpo_opcao(), headers=usuario.cabecalho)
    assert opcao.status_code == 201


def test_servidor_falso_e_apontado_por_bacen_url_base(app, client, usuario, servidor_falso):
    assert app.config["BACEN_URL_BASE"] == servidor_falso.url_base
    resposta = client.get("/api/indices/cdi", headers=usuario.cabecalho)
    assert resposta.status_code == 200
    assert servidor_falso.numero_de_chamadas() == 1
