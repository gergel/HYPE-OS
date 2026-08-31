from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class FloraFeladat(TimestampMixin, Base):
    """A FLÓRA Notion-oldal "Design adatbázis" táblájának sorai - a grafikai
    kérések Kanban-táblája (lásd frontend components/FloraContent.tsx), a
    board-oszlopok az `allapot` mező fix értékkészlete (lásd
    services/entity_registry.SELECT_FIELD_OVERRIDES["floraFeladat"])."""

    __tablename__ = "flora_feladatok"

    id: Mapped[int] = mapped_column(primary_key=True)
    megnevezes: Mapped[str] = mapped_column(String(500), nullable=False)
    #: Board-oszlop: ASSETS / BACKLOG / WEEKLY TO DO / PRIO / INPROGREDSS /
    #: REVIEW / CORRECTION / APPROVED / DONE - az "INPROGREDSS" elgépelés a
    #: Notion eredeti adata, szándékosan nem javítva.
    allapot: Mapped[str | None] = mapped_column(String(50))
    #: Notion "Labels" - a "(orange)" színjelölés levágva, csak az ügyfél/
    #: projekt neve marad (lásd az import script cimke_nev függvényét).
    cimke: Mapped[str | None] = mapped_column(String(255))
    hatarido: Mapped[datetime | None] = mapped_column(DateTime)
    kesz_anyag_linkje: Mapped[str | None] = mapped_column(String(1000))
    leiras: Mapped[str | None] = mapped_column(Text)
    letrehozas_idopontja: Mapped[datetime | None] = mapped_column(DateTime)

    felelos_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))
    felvezette_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))

    felelos: Mapped["Employee"] = relationship(foreign_keys=[felelos_id])
    felvezette: Mapped["Employee"] = relationship(foreign_keys=[felvezette_id])
    #: A feladat hozzászólásai - a feladattal együtt törlődnek (egy komment a
    #: feladata nélkül értelmezhetetlen, és idegen kulcsként a törlést is
    #: megakasztaná).
    kommentek: Mapped[list["FloraKomment"]] = relationship(
        back_populates="flora_feladat", order_by="FloraKomment.created_at", cascade="all, delete-orphan"
    )
