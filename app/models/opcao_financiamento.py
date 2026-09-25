import enum
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Enum,
    ForeignKey,
    Identity,
    Numeric,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.simulacao import Simulacao


class SistemaAmortizacao(enum.Enum):
    PRICE = "PRICE"
    SAC = "SAC"


class OpcaoFinanciamento(db.Model):
    __tablename__ = "opcoes_financiamento"
    __table_args__ = (
        CheckConstraint("taxa_juros_mensal >= 0", name="taxa_juros_nao_negativa"),
        CheckConstraint("prazo_meses > 0", name="prazo_meses_positivo"),
        CheckConstraint("valor_entrada >= 0", name="valor_entrada_nao_negativo"),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    simulacao_id: Mapped[int] = mapped_column(
        ForeignKey("simulacoes.id", ondelete="RESTRICT"), index=True
    )
    nome: Mapped[str] = mapped_column(String(120))
    # Taxa em percentual ao mês (1.99 = 1,99%).
    taxa_juros_mensal: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    prazo_meses: Mapped[int]
    # VARCHAR + CHECK (sem tipo ENUM nativo); create_constraint gera a CHECK.
    sistema_amortizacao: Mapped[SistemaAmortizacao] = mapped_column(
        Enum(
            SistemaAmortizacao,
            native_enum=False,
            create_constraint=True,
            name="sistema_amortizacao_valido",
        )
    )
    valor_entrada: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), server_default=text("0")
    )

    simulacao: Mapped["Simulacao"] = relationship(back_populates="opcoes_financiamento")
