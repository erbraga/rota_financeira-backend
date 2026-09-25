import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, Identity, Numeric, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


class Indice(enum.Enum):
    SELIC = "SELIC"
    CDI = "CDI"
    IPCA = "IPCA"


class IndiceEconomicoCache(db.Model):
    __tablename__ = "indices_economicos_cache"
    __table_args__ = (UniqueConstraint("indice", "data_referencia"),)

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    # VARCHAR + CHECK (sem tipo ENUM nativo); create_constraint gera a CHECK.
    indice: Mapped[Indice] = mapped_column(
        Enum(Indice, native_enum=False, create_constraint=True, name="indice_valido")
    )
    data_referencia: Mapped[date]
    # Valor como publicado pelo BACEN, em percentual (sem conversão).
    valor: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
