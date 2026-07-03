from datetime import date
from enum import StrEnum

from sqlalchemy import JSON, Boolean, Date, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class ContractType(StrEnum):
    """Keretszerződés (ügyféllel) vagy alvállalkozói/eseti (crew-val)."""

    KERETSZERZODES = "kereto"
    ALVALLALKOZOI = "alvallalkozoi"


class Contract(TimestampMixin, Base):
    """Szerződés - Keretszerződés + Alvállalkozó keretszerződés egyesítve, tipus mezővel."""

    __tablename__ = "contracts"

    id: Mapped[int] = mapped_column(primary_key=True)
    tipus: Mapped[ContractType] = mapped_column(
        Enum(ContractType, name="contract_type", values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )

    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id"))
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))

    ceg_neve: Mapped[str | None] = mapped_column(String(255))
    szekhely: Mapped[str | None] = mapped_column(String(255))
    adoszam: Mapped[str | None] = mapped_column(String(50))
    megbizas_targya: Mapped[str | None] = mapped_column(String(255))
    szerzodes_allapota: Mapped[str | None] = mapped_column(String(50))
    szerzodes_file_url: Mapped[str | None] = mapped_column(String(500))
    keltezes: Mapped[date | None] = mapped_column(Date)
    alairva: Mapped[bool] = mapped_column(Boolean, default=False)
    extra: Mapped[dict | None] = mapped_column(JSON)

    client: Mapped["Client"] = relationship(back_populates="contracts")
    employee: Mapped["Employee"] = relationship(back_populates="contracts")
    project_codes: Mapped[list["ProjectCode"]] = relationship(back_populates="contract")
