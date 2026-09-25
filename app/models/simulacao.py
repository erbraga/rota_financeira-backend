from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.opcao_financiamento import OpcaoFinanciamento
    from app.models.usuario import Usuario


class Simulacao(db.Model):
    __tablename__ = "simulacoes"
    __table_args__ = (
        CheckConstraint("valor_veiculo > 0", name="valor_veiculo_positivo"),
        CheckConstraint("valor_entrada >= 0", name="valor_entrada_nao_negativo"),
        CheckConstraint("valor_entrada <= valor_veiculo", name="valor_entrada_maximo"),
        CheckConstraint("taxa_fundo_rendimento >= 0", name="taxa_fundo_nao_negativa"),
        CheckConstraint("prazo_meses_fundo > 0", name="prazo_meses_fundo_positivo"),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT"), index=True
    )
    nome: Mapped[str] = mapped_column(String(120))
    valor_veiculo: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    valor_entrada: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), server_default=text("0")
    )
    # Taxas em percentual ao ano (12.5 = 12,5%); o IPCA pode ser negativo.
    taxa_ipca_projetada: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    taxa_fundo_rendimento: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    prazo_meses_fundo: Mapped[int]
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    usuario: Mapped["Usuario"] = relationship(back_populates="simulacoes")
    # Cascata só no ORM: o banco usa ON DELETE RESTRICT nas chaves estrangeiras.
    opcoes_financiamento: Mapped[list["OpcaoFinanciamento"]] = relationship(
        back_populates="simulacao",
        cascade="all, delete-orphan",
        order_by="OpcaoFinanciamento.id",
    )
