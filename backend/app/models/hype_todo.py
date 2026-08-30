from datetime import date, datetime

from sqlalchemy import Column, Date, DateTime, ForeignKey, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

#: A "Felelős" mező a Notionban TÖBB embert is tartalmazhat egy feladaton -
#: ellentétben a FLÓRA táblával, ahol ez a mező a valódi adatban mindig
#: legfeljebb egy nevet visel (lásd models/flora_feladat.py).
hype_todo_felelosok = Table(
    "hype_todo_felelosok",
    Base.metadata,
    Column("hype_todo_id", ForeignKey("hype_todo_items.id"), primary_key=True),
    Column("employee_id", ForeignKey("employees.id"), primary_key=True),
)


class HypeTodoItem(TimestampMixin, Base):
    """A HYPE TO-DO LIST Notion-tábla sorai - önálló tábla, NEM a Task
    modellel egyesítve (lásd models/task.py docstringje, ami a régi, nyers
    JSON-alapú, félbehagyott egyesítési kísérlet - ezt tudatosan nem
    folytattuk, a felhasználó kifejezett kérésére önálló táblát kapott)."""

    __tablename__ = "hype_todo_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    feladat: Mapped[str] = mapped_column(String(500), nullable=False)
    #: "Not started" / "In progress" / "Done" / "Ellenőrzés" - a Notion
    #: eredeti angol+magyar kevert értékkészlete, változtatás nélkül átvéve.
    allapot: Mapped[str | None] = mapped_column(String(50))
    leiras: Mapped[str | None] = mapped_column(Text)
    kategoria: Mapped[str | None] = mapped_column(String(100))
    hatarido: Mapped[date | None] = mapped_column(Date)
    #: "Csatolni való" - a Notion adatban ez HELYI FÁJL (lásd DocumentAttachment,
    #: services/attachments.py) VAGY külső link is lehet (pl. Google Sheets) -
    #: utóbbihoz nincs mit feltölteni, ez a mező tárolja a linket magát.
    csatolando_link: Mapped[str | None] = mapped_column(String(1000))
    #: A Notion-oldal eredeti létrehozási időpontja - NEM ugyanaz, mint a
    #: created_at (ami az idehozatal/import időpontja lenne).
    letrehozas_idopontja: Mapped[datetime | None] = mapped_column(DateTime)

    aki_felvezette_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))
    ellenorzes_felelos_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))
    aki_ellenorizte_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))

    aki_felvezette: Mapped["Employee"] = relationship(foreign_keys=[aki_felvezette_id])
    ellenorzes_felelos: Mapped["Employee"] = relationship(foreign_keys=[ellenorzes_felelos_id])
    aki_ellenorizte: Mapped["Employee"] = relationship(foreign_keys=[aki_ellenorizte_id])
    felelosok: Mapped[list["Employee"]] = relationship(secondary=hype_todo_felelosok)

    #: A read-sémának adja a kiosztott munkatársak id-jét (lásd
    #: models/project.py Project.crew_employee_ids - ugyanaz a minta).
    @property
    def felelos_employee_ids(self) -> list[int]:
        return [e.id for e in self.felelosok]
