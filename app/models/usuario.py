from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Identity, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.simulacao import Simulacao


class Usuario(db.Model):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    senha_hash: Mapped[str] = mapped_column(String(255))
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Cascata só no ORM: o banco usa ON DELETE RESTRICT nas chaves estrangeiras.
    simulacoes: Mapped[list["Simulacao"]] = relationship(
        back_populates="usuario", cascade="all, delete-orphan"
    )
