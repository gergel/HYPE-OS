from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class PerformanceCertificate(TimestampMixin, Base):
    """Teljesítési igazolás (TIG) - eseti, projektenkénti dokumentum minden
    nem belsős stábtaghoz (külsős VAGY keretszerződéses is - a TIG a konkrét
    munka elvégzését igazolja, függetlenül attól, hogy van-e a megbízottnak
    egyébként álló keretszerződése), miután az adott projekten mindenkinek
    megvan a (eseti) szerződése (Contract.szerzodes_allapota "Kiküldve" vagy
    "Kihagyva" mindenkinél, akinek egyáltalán kellett) - lásd
    api/routes/performance_certificates.py. Ugyanaz a kétlépéses (mentés majd
    generálás-és-küldés, vagy kihagyás) életciklus, mint az eseti
    szerződéseknél (Contract), de külön táblában, mert ez egy másik,
    önállóan kezelt dokumentum."""

    __tablename__ = "performance_certificates"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)

    allapot: Mapped[str | None] = mapped_column(String(50), comment="TIG állapot")
    file_url: Mapped[str | None] = mapped_column(String(500), comment="Generált TIG Google Docs linkje")

    ceg_neve: Mapped[str | None] = mapped_column(String(255))
    szekhely: Mapped[str | None] = mapped_column(String(255))
    adoszam: Mapped[str | None] = mapped_column(String(50))
    megbizas_targya: Mapped[str | None] = mapped_column(String(255))
    netto_osszeg: Mapped[float | None] = mapped_column(Numeric(12, 2), comment="Nettó TIG")
    plusz_afa: Mapped[bool | None] = mapped_column(Boolean)
    teljesites_kezdete: Mapped[date | None] = mapped_column(Date)
    teljesites_vege: Mapped[date | None] = mapped_column(Date)
    keltezes: Mapped[date | None] = mapped_column(Date, comment="Keltezési idő")
    email: Mapped[str | None] = mapped_column(String(255))

    # Számla feltöltése + kifizetése - a TIG kiküldése után jövő lépés
    # (lásd api/routes/performance_certificates.py /szamla és
    # /szamla-kifizetve végpontjai): a kifizetés automatikusan létrehoz egy
    # Expense sort a megfelelő ProjectCode-hoz kötve, hogy a Pénzügy ->
    # Kiadások összesítőben megjelenjen.
    szamla_url: Mapped[str | None] = mapped_column(String(500), comment="Feltöltött számla fájl URL-je")
    szamla_storage_key: Mapped[str | None] = mapped_column(String(500))
    szamla_kifizetve: Mapped[bool] = mapped_column(Boolean, default=False)
    expense_id: Mapped[int | None] = mapped_column(ForeignKey("expenses.id"))

    project: Mapped["Project"] = relationship(back_populates="performance_certificates")
    employee: Mapped["Employee"] = relationship(back_populates="performance_certificates")
