"""Garantias transversais do pacote de cálculo: pureza, desempenho e contexto do Decimal."""
import ast
import sys
import time
from decimal import Decimal, getcontext
from pathlib import Path

from app.services.calculo.financiamento import custo_total_financiamento, tabela_price, tabela_sac
from app.services.calculo.fundo import aporte_para_meta, meses_para_meta, serie_fundo
from app.services.calculo.preco import preco_corrigido, serie_preco_corrigido

D = Decimal
RAIZ = Path(__file__).resolve().parents[2]


PACOTE = RAIZ / "app" / "services" / "calculo"


def _imports(arquivo):
    """Nomes de módulo importados por um arquivo (import x / from x import y)."""
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            yield from (alias.name for alias in no.names)
        elif isinstance(no, ast.ImportFrom):
            yield no.module


def test_pacote_so_importa_biblioteca_padrao_e_o_proprio_pacote():
    # Pureza verificada no código-fonte (decisão 9 da spec): o cálculo não depende de Flask,
    # SQLAlchemy, Marshmallow nem de outras partes de `app`. (Importar o pacote em tempo de
    # execução carrega `app/__init__.py`, que é a aplicação; isso não conta.)
    arquivos = sorted(PACOTE.glob("*.py"))
    assert {a.name for a in arquivos} >= {"__init__.py", "base.py", "preco.py", "financiamento.py", "fundo.py"}
    for arquivo in arquivos:
        for modulo in _imports(arquivo):
            raiz = modulo.split(".")[0]
            permitido = raiz in sys.stdlib_module_names or modulo.startswith("app.services.calculo")
            assert permitido, f"{arquivo.name} importa {modulo}"


def _pior_caso():
    valor = D("9999999.00")
    tabelas = [f(valor, D(20), 72) for f in (tabela_price, tabela_sac, tabela_price)]
    [custo_total_financiamento(D(0), t) for t in tabelas]
    meta = preco_corrigido(valor, D(100), 60)
    serie_preco_corrigido(valor, D(100), 60)
    aporte = aporte_para_meta(meta, D(0), D(100), 60)
    serie_fundo(D(0), aporte, D(100), 60)
    meses_para_meta(valor, D(100), D(0), aporte, D(100))


def test_pior_caso_de_uma_simulacao_e_rapido():
    _pior_caso()  # aquece
    inicio = time.perf_counter()
    _pior_caso()
    assert time.perf_counter() - inicio < 0.1


def test_contexto_global_do_decimal_nao_muda():
    contexto = getcontext()
    antes = (contexto.prec, contexto.rounding, contexto.Emax, contexto.Emin, dict(contexto.traps))
    _pior_caso()
    depois = (contexto.prec, contexto.rounding, contexto.Emax, contexto.Emin, dict(contexto.traps))
    assert depois == antes
