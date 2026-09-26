"""Verificação estrutural do Swagger (`/apispec.json`): as regras do projeto, sem dependência externa.

Cada regra reporta a operação que a quebrou ("POST /api/simulacoes: falta `summary`"), para o erro de
uma docstring ser localizado sem abrir o documento.
"""
import re

import pytest
from flask import Flask

from app import create_app

PUBLICAS = {("POST", "/api/auth/registrar"), ("POST", "/api/auth/login"), ("GET", "/api/saude")}
METODOS = {"get", "post", "put", "delete", "patch"}
TAGS_NA_ORDEM = ["Saúde", "Autenticação", "Simulações", "Financiamentos", "Índices"]
REF = re.compile(r"^#/components/schemas/(\w+)$")


@pytest.fixture(scope="module")
def especificacao(app):
    resposta = app.test_client().get("/apispec.json")
    assert resposta.status_code == 200, "o /apispec.json não foi gerado (YAML de alguma docstring inválido?)"
    return resposta.get_json()


def operacoes(especificacao):
    for caminho, itens in especificacao["paths"].items():
        for metodo, operacao in itens.items():
            if metodo in METODOS:
                yield metodo.upper(), caminho, operacao


def nome(metodo, caminho):
    return f"{metodo} {caminho}"


def referencias(objeto):
    """Todos os nomes de schema citados por `$ref` dentro de um trecho do documento."""
    if isinstance(objeto, dict):
        for chave, valor in objeto.items():
            if chave == "$ref":
                yield valor
            else:
                yield from referencias(valor)
    elif isinstance(objeto, list):
        for valor in objeto:
            yield from referencias(valor)


def problemas(regra):
    return [texto for texto in regra if texto]


# ---------------------------------------------------------------------- documento

def test_e_openapi_3_0(especificacao):
    assert re.fullmatch(r"3\.0\.\d+", especificacao["openapi"])
    assert especificacao["info"]["title"] and especificacao["info"]["version"] and especificacao["info"]["description"]


def test_todo_ref_resolve_e_todo_schema_e_usado(especificacao):
    schemas = especificacao["components"]["schemas"]
    citados = list(referencias(especificacao["paths"])) + list(referencias(schemas))
    quebrados = sorted({r for r in citados if not (REF.match(r) and REF.match(r).group(1) in schemas)})
    assert not quebrados, f"$ref sem schema correspondente: {quebrados}"
    usados = {REF.match(r).group(1) for r in citados}
    assert not set(schemas) - usados, f"schemas sem uso: {sorted(set(schemas) - usados)}"


def test_bearer_auth_declarado(especificacao):
    esquema = especificacao["components"]["securitySchemes"]["BearerAuth"]
    assert (esquema["type"], esquema["scheme"], esquema["bearerFormat"]) == ("http", "bearer", "JWT")


def test_tags_de_topo_na_ordem_e_cobrem_as_usadas(especificacao):
    assert [t["name"] for t in especificacao["tags"]] == TAGS_NA_ORDEM
    assert all(t.get("description") for t in especificacao["tags"])
    usadas = {tag for _, _, operacao in operacoes(especificacao) for tag in operacao["tags"]}
    assert usadas <= set(TAGS_NA_ORDEM), f"tags usadas e não declaradas: {sorted(usadas - set(TAGS_NA_ORDEM))}"


def test_o_texto_geral_documenta_a_api_externa_e_o_erro_500(especificacao):
    texto = especificacao["info"]["description"]
    for esperado in ("Banco Central", "api.bcb.gov.br", "Cadastro", "Licença", "4389", "13522", "500", "Erro interno do servidor"):
        assert esperado in texto, f"falta no texto geral: {esperado}"


# ---------------------------------------------------------------------- operações

def test_toda_operacao_tem_summary_tag_e_descricao_nas_respostas(especificacao):
    faltas = []
    for metodo, caminho, operacao in operacoes(especificacao):
        rotulo = nome(metodo, caminho)
        faltas += [f"{rotulo}: falta `summary`"] * (not operacao.get("summary"))
        faltas += [f"{rotulo}: falta `description`"] * (not operacao.get("description"))
        faltas += [f"{rotulo}: falta `tags`"] * (not operacao.get("tags"))
        faltas += [f"{rotulo}: sem `responses`"] * (not operacao.get("responses"))
        faltas += [f"{rotulo}: resposta {codigo} sem `description`" for codigo, r in operacao.get("responses", {}).items() if not r.get("description")]
    assert not faltas, "\n".join(faltas)


def test_operacoes_protegidas_tem_security_e_401_e_so_tres_sao_publicas(especificacao):
    faltas = []
    publicas = set()
    for metodo, caminho, operacao in operacoes(especificacao):
        rotulo = nome(metodo, caminho)
        if operacao.get("security") is None:
            publicas.add((metodo, caminho))
            continue
        faltas += [f"{rotulo}: `security` deve ser BearerAuth"] * (operacao["security"] != [{"BearerAuth": []}])
        faltas += [f"{rotulo}: protegida sem resposta 401"] * ("401" not in operacao["responses"])
    assert not faltas, "\n".join(faltas)
    assert publicas == PUBLICAS, f"rotas públicas inesperadas: {sorted(publicas ^ PUBLICAS)}"


def test_operacoes_com_corpo_tem_request_body_e_400_415_422(especificacao):
    faltas = []
    for metodo, caminho, operacao in operacoes(especificacao):
        rotulo = nome(metodo, caminho)
        if metodo not in ("POST", "PUT"):
            faltas += [f"{rotulo}: {metodo} não deveria ter `requestBody`"] * ("requestBody" in operacao)
            continue
        corpo = operacao.get("requestBody")
        if not corpo:
            faltas.append(f"{rotulo}: falta `requestBody`")
            continue
        faltas += [f"{rotulo}: `requestBody` deve ser obrigatório"] * (corpo.get("required") is not True)
        faltas += [f"{rotulo}: `requestBody` deve ser application/json"] * ("application/json" not in corpo.get("content", {}))
        faltas += [f"{rotulo}: falta a resposta {codigo}" for codigo in ("400", "415", "422") if codigo not in operacao["responses"]]
    assert not faltas, "\n".join(faltas)


def test_respostas_de_erro_apontam_para_o_schema_erro_e_o_sucesso_para_um_schema(especificacao):
    faltas = []
    for metodo, caminho, operacao in operacoes(especificacao):
        for codigo, resposta in operacao["responses"].items():
            conteudo = resposta.get("content", {}).get("application/json")
            rotulo = f"{nome(metodo, caminho)} → {codigo}"
            if codigo == "204":
                faltas += [f"{rotulo}: 204 não tem corpo"] * ("content" in resposta)
            elif not conteudo or not conteudo.get("schema"):
                faltas.append(f"{rotulo}: sem `content`/`schema`")
            elif codigo[0] in "45" and conteudo["schema"] != {"$ref": "#/components/schemas/Erro"} and (metodo, caminho, codigo) != ("GET", "/api/saude", "200"):
                faltas.append(f"{rotulo}: erro deve apontar para o schema Erro")
    assert not faltas, "\n".join(faltas)


def test_parametros_de_caminho_estao_declarados_e_descritos(especificacao):
    faltas = []
    for metodo, caminho, operacao in operacoes(especificacao):
        esperados = set(re.findall(r"\{(\w+)\}", caminho))
        declarados = {p["name"]: p for p in operacao.get("parameters", []) if p["in"] == "path"}
        faltas += [f"{nome(metodo, caminho)}: parâmetro de caminho `{p}` não declarado" for p in esperados - set(declarados)]
        faltas += [f"{nome(metodo, caminho)}: `{n}` sem `description`" for n, p in declarados.items() if not p.get("description")]
        faltas += [f"{nome(metodo, caminho)}: `{n}` deve ser `required`" for n, p in declarados.items() if p.get("required") is not True]
    assert not faltas, "\n".join(faltas)


def test_nao_ha_get_de_uma_opcao_so_nem_rotas_de_indice_alem_de_cdi_e_ipca(especificacao):
    caminhos = especificacao["paths"]
    assert "get" not in caminhos["/api/simulacoes/{simulacao_id}/financiamentos/{financiamento_id}"]
    assert caminhos["/api/indices/{indice}"]["get"]["parameters"][0]["schema"]["enum"] == ["cdi", "ipca"]


# ---------------------------------------------------------------------- documentação x rotas reais

def converter(regra):
    return re.sub(r"<(?:\w+:)?(\w+)>", r"{\1}", regra)


def test_os_caminhos_do_documento_sao_exatamente_as_rotas_da_api(app, especificacao):
    reais = {
        (metodo, converter(regra.rule))
        for regra in app.url_map.iter_rules()
        if regra.rule.startswith("/api/")
        for metodo in regra.methods - {"HEAD", "OPTIONS"}
    }
    documentadas = {(metodo, caminho) for metodo, caminho, _ in operacoes(especificacao)}
    assert not reais - documentadas, f"rotas sem documentação: {sorted(reais - documentadas)}"
    assert not documentadas - reais, f"documentação de rota que não existe: {sorted(documentadas - reais)}"
    assert len(documentadas) == 16


# ---------------------------------------------------------------------- o que o texto geral promete

def test_erro_interno_devolve_500_generico_sem_detalhes(caplog):
    aplicacao = create_app({"SQLALCHEMY_DATABASE_URI": "postgresql+psycopg://x:y@127.0.0.1:1/x_test", "TESTING": True})

    @aplicacao.get("/_explode")
    def explodir():
        raise RuntimeError("segredo interno que não pode vazar: senha=123")

    resposta = aplicacao.test_client().get("/_explode")
    assert resposta.status_code == 500
    assert resposta.get_json() == {"erro": "Erro interno do servidor"}
    assert "segredo interno" not in resposta.get_data(as_text=True)
    assert "segredo interno" in caplog.text  # o motivo fica só no log


def test_docstring_sem_yaml_valido_derruba_o_apispec_e_este_teste_percebe():
    """Controle: prova que o `especificacao` acima falharia com uma docstring quebrada."""
    aplicacao = create_app({"SQLALCHEMY_DATABASE_URI": "postgresql+psycopg://x:y@127.0.0.1:1/x_test", "TESTING": True})

    @aplicacao.get("/api/_quebrada")
    def quebrada():
        """Rota de teste.
        ---
        tags:
          - Saúde
        responses:
          200:
            description: texto com dois pontos: quebra o YAML
        """
        return {}

    assert aplicacao.test_client().get("/apispec.json").status_code == 500
