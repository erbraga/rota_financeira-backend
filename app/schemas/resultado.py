"""Saídas de `/parcelas` e `/resultado` (contrato com o frontend) e o parâmetro `aporte_mensal`.

Os números saem como número JSON (a conversão de `Decimal` para `float` acontece só aqui, na
saída, como nas Etapas 4 e 5) e `null` é preservado onde uma série terminou ou a meta não foi
alcançada. As funções `*_para_documento` montam o documento a partir do resultado puro.
"""
from decimal import Decimal

from marshmallow import Schema, fields

from app.schemas.base import EntradaSchema, campo_decimal
from app.schemas.simulacao import VALOR_MAXIMO, SimulacaoSaidaSchema


def _numero():
    return fields.Float(allow_none=True)


# ------------------------------------------------------------------ /parcelas


class ParcelaSchema(Schema):
    numero = fields.Integer()
    valor_parcela = fields.Float()
    juros = fields.Float()
    amortizacao = fields.Float()
    saldo_devedor = fields.Float()  # saldo após o pagamento da parcela


class FinanciamentoResumoSchema(Schema):
    id = fields.Integer()
    nome = fields.String()
    sistema_amortizacao = fields.String()
    valor_financiado = fields.Float()
    valor_entrada = fields.Float()
    taxa_juros_mensal = fields.Float()
    prazo_meses = fields.Integer()


class TotaisFinanciamentoSchema(Schema):
    total_pago = fields.Float()
    total_juros = fields.Float()
    custo_total = fields.Float()


class ParcelasSchema(Schema):
    financiamento = fields.Nested(FinanciamentoResumoSchema)
    parcelas = fields.List(fields.Nested(ParcelaSchema))
    totais = fields.Nested(TotaisFinanciamentoSchema)


def parcelas_para_documento(f):
    """`f`: `FinanciamentoCalculado` (calculo.cenarios)."""
    opcao = f.opcao
    return {
        "financiamento": {
            "id": opcao.id,
            "nome": opcao.nome,
            "sistema_amortizacao": opcao.sistema,
            "valor_financiado": f.valor_financiado,
            "valor_entrada": opcao.valor_entrada,
            "taxa_juros_mensal": opcao.taxa_juros_mensal,
            "prazo_meses": opcao.prazo_meses,
        },
        "parcelas": list(f.tabela.parcelas),
        "totais": {
            "total_pago": f.total_pago,
            "total_juros": f.total_juros,
            "custo_total": f.custo_total,
        },
    }


# ----------------------------------------------------------------- /resultado


class FinanciamentoResultadoSchema(FinanciamentoResumoSchema):
    primeira_parcela = fields.Float()
    ultima_parcela = fields.Float()
    total_pago = fields.Float()
    total_juros = fields.Float()
    custo_total = fields.Float()

    class Meta:
        exclude = ("taxa_juros_mensal",)


class FundoResultadoSchema(Schema):
    capital_inicial = fields.Float()
    aporte_mensal = fields.Float()
    prazo_meses = fields.Integer()  # meses simulados
    mes_da_meta = fields.Integer(allow_none=True)
    alcanca_a_meta = fields.Boolean()
    preco_na_compra = _numero()
    total_aportado = fields.Float()
    rendimento = fields.Float()
    saldo_final = fields.Float()
    custo_total = _numero()


class AVistaSchema(Schema):
    custo_total = fields.Float()


class CenariosSchema(Schema):
    a_vista = fields.Nested(AVistaSchema)
    financiamentos = fields.List(fields.Nested(FinanciamentoResultadoSchema))
    fundo = fields.Nested(FundoResultadoSchema)


class MenorCustoSchema(Schema):
    cenario = fields.String()
    id = fields.Integer(allow_none=True)


class PontoSerieSchema(Schema):
    mes = fields.Integer()
    preco_corrigido = fields.Float()
    saldo_fundo = _numero()
    saldo_devedor = fields.Dict(keys=fields.String(), values=_numero())


class ResultadoSchema(Schema):
    simulacao = fields.Nested(
        SimulacaoSaidaSchema,
        only=(
            "id",
            "nome",
            "valor_veiculo",
            "valor_entrada",
            "taxa_ipca_projetada",
            "taxa_fundo_rendimento",
            "prazo_meses_fundo",
        ),
    )
    cenarios = fields.Nested(CenariosSchema)
    menor_custo = fields.Nested(MenorCustoSchema)
    series = fields.List(fields.Nested(PontoSerieSchema))


def resultado_para_documento(simulacao, resultado):
    """`simulacao`: o model (id, nome, ...); `resultado`: `Resultado` (calculo.cenarios)."""
    return {
        "simulacao": simulacao,
        "cenarios": {
            "a_vista": {"custo_total": resultado.a_vista_custo_total},
            "financiamentos": [
                {
                    "id": f.opcao.id,
                    "nome": f.opcao.nome,
                    "sistema_amortizacao": f.opcao.sistema,
                    "valor_financiado": f.valor_financiado,
                    "valor_entrada": f.opcao.valor_entrada,
                    "prazo_meses": f.opcao.prazo_meses,
                    "primeira_parcela": f.primeira_parcela,
                    "ultima_parcela": f.ultima_parcela,
                    "total_pago": f.total_pago,
                    "total_juros": f.total_juros,
                    "custo_total": f.custo_total,
                }
                for f in resultado.financiamentos
            ],
            "fundo": resultado.fundo,
        },
        "menor_custo": resultado.menor_custo,
        "series": list(resultado.series),
    }


# ------------------------------------------------------------ parâmetro de consulta


class ConsultaResultadoSchema(EntradaSchema):
    """`?aporte_mensal=` (opcional): 0 a 9.999.999,00, até 2 casas. Recusa parâmetros desconhecidos."""

    aporte_mensal = campo_decimal(
        "O aporte mensal", "0", VALOR_MAXIMO, 2, exibir_casas=2, load_default=None
    )
