from datetime import date

from sqlalchemy import Date, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

# A tétel szerepe:
#   alapber   - a havi fix rész,
#   extra     - ami hozzáadódik (túlóra, benzin, étkezés…),
#   levonando - ami LEVONÓDIK (előleg, hiányzás, kártérítés…).
#
# A levonandó tétel összegét POZITÍVAN visszük fel, az előjelet a típus adja
# (lásd elojeles_osszeg) - így a felületen nem kell mínusszal bajlódni, és nem
# fordulhat elő, hogy egy elfelejtett mínusz miatt egy levonás hozzáadódik.
#
# Az alapbér azért nem fix konstans a munkatárs törzsadatában, mert hónapról
# hónapra változhat - így minden hónapnak megvan a SAJÁT, visszakereshető
# alapbére.
TETEL_TIPUSOK = ("alapber", "extra", "levonando")

# Megjelenítési/összeadási sorrend: előbb az alapbér, aztán ami hozzáadódik,
# végül ami levonódik - így a lista úgy olvasható, ahogy az összeg összeáll.
TIPUS_SORREND = {"alapber": 0, "extra": 1, "levonando": 2}


def elojeles_osszeg(tipus: str, osszeg: float | None) -> float:
    """A tétel előjeles hozzájárulása a havi összeghez. A levonandó tétel
    MÍNUSZ, minden más plusz."""
    ertek = float(osszeg or 0)
    return -ertek if tipus == "levonando" else ertek


class EmployeeMonthlyItem(TimestampMixin, Base):
    """Egy belsős munkatárs adott havi juttatás-tétele: az alapbér, és a
    hozzáadódó extrák (túlóra, benzin, étkezés…), tételenként projekthez is
    köthetően.

    Ezek a tételek adják ki a havi Belsős TIG összegét: bármelyik módosítása
    újraszámolja a hónap TIG-jének nettó összegét (lásd
    api/routes/internal_performance_certificates.py _ujraszamol_tig_osszeget),
    így aki a TIG-et készíti, már a kész összeget látja - nem neki kell
    összeadnia a hónap közben felmerült extrákat.

    A már véglegesített (kiküldött/kész/kihagyott) TIG összegét NEM írjuk át:
    egy kiküldött igazolás összege nem változhat utólag."""

    __tablename__ = "employee_monthly_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    ev: Mapped[int] = mapped_column(nullable=False, comment="Év, pl. 2026")
    honap: Mapped[int] = mapped_column(nullable=False, comment="Hónap, 1-12")

    tipus: Mapped[str] = mapped_column(String(20), nullable=False, default="extra", comment="alapber | extra")
    megnevezes: Mapped[str] = mapped_column(String(255), nullable=False)
    osszeg: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)

    # Melyik PROJEKTKÓDHOZ kapcsolódik az extra (túlóra, kiszállás). Nem a
    # projekthez: egy projektkód alatt több forgatás is futhat, a költséget
    # viszont a projektkód szintjén tartjuk nyilván (ott áll össze a bevétel
    # és a kiadás is, lásd models/finance.py Expense.project_code_id).
    project_code_id: Mapped[int | None] = mapped_column(ForeignKey("project_codes.id"))
    datum: Mapped[date | None] = mapped_column(Date, comment="A tétel napja a hónapon belül (opcionális)")
    megjegyzes: Mapped[str | None] = mapped_column(String(500))

    # A Notionból ("Belsős extra kiadások") áthozott tételek azonosítója. Saját
    # oszlop, nem a közös NotionImportMap: ugyanaz a Notion-oldal Expense-ként
    # IS bekerül (lásd notion_import/importers_wave2.import_expenses), a közös
    # tábla viszont oldalanként csak egy entitást tud nyilvántartani.
    notion_page_id: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    # Ha ez a tétel egy pénzügyi kiadás-sorral UGYANAZ a költség (a Notion
    # "Belsős extra kiadások" mindkettőként bejön), akkor ide mutat - így a
    # munkatárs adatlapján egyszer szerepel, nem kétszer.
    expense_id: Mapped[int | None] = mapped_column(ForeignKey("expenses.id"))

    employee: Mapped["Employee"] = relationship(back_populates="monthly_items")
    project_code: Mapped["ProjectCode | None"] = relationship()

    __table_args__ = (Index("ix_employee_monthly_items_employee_honap", "employee_id", "ev", "honap"),)
