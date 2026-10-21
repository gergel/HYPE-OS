"""Ki számláz egy adott projekten egy adott stábtag munkájáért.

Alapesetben mindenki a saját nevében számláz - ilyenkor NINCS sor ebben a
táblában. Ez a tábla csak az ELTÉRÉST rögzíti:

- "Balla Berci munkáját ezen a projekten Ladányi Máté számlázza"
  -> szamlazo_employee_id = Ladányi
- "Ezt az embert a XY Kft. küldte, a cég számláz érte"
  -> szamlazo_vallalkozas_id = XY Kft.

Miért a (projekt, ember) páron és nem az emberen? Mert a felhasználó szerint
ugyanaz az ember "ma innen számláz, holnap saját névről, utána egy harmadik
helyről" - egy emberre akasztott cég-mutató hazudna. A vállalkozáshoz tartozás
(models/vallalkozas.py VallalkozasTag) ezért csak előtöltési JAVASLAT, az
igazság itt van.

Fontos, hogy a lefedett ember (Berci) STÁBTAG marad a projekten: kap diszpót,
rajta van a projekten, a jövedelmezőségben is szerepel. Csak a szerződés és a
TIG megy a másik fél nevére - lásd api/routes/subcontractor_contracts.py
_szamlazo_csoportok, illetve models/performance_certificate.py
PerformanceCertificateTetel.

Miért külön tábla és nem oszlop a project_crew kapcsolótáblán? Mert a stáblista
mentése (PATCH crew_employee_ids) a teljes listát cseréli - egy társított
oszlopot minden egyes stáb-módosítás kitörölne. Külön táblában a beállítás
túléli a stáblista szerkesztését."""

from sqlalchemy import Boolean, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class ProjectSzamlazo(TimestampMixin, Base):
    """Egy (projekt, stábtag) páron a számlázó fél felülírása."""

    __tablename__ = "project_szamlazok"
    __table_args__ = (UniqueConstraint("project_id", "employee_id", name="uq_project_szamlazo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: A LEFEDETT ember - aki a munkát végezte, de nem ő számláz érte.
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )

    #: A számlázó fél: pontosan az egyik van kitöltve (lásd szamlazo_kulcs).
    szamlazo_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"))
    szamlazo_vallalkozas_id: Mapped[int | None] = mapped_column(ForeignKey("vallalkozasok.id", ondelete="CASCADE"))

    #: Ez az ember a projekten NEM résztvevőként, hanem PROJEKT KIADÁSKÉNT van
    #: elszámolva - jellemzően azért, mert a díja egy másik tételben (pl. a
    #: technika bérleti árában) már benne van.
    #:
    #: Ilyenkor nem kell tőle sem szerződés, sem TIG: nem a munkájáért fizetünk
    #: neki külön, hanem a kiadás fedezi. Stábtag attól még marad - kap diszpót,
    #: rajta van a projekten -, csak a papírozásból esik ki.
    #:
    #: Utólag is állítható: sokszor csak a számla megérkezésekor derül ki, hogy
    #: valakinek a díja már egy másik tételben szerepel.
    kiadaskent_elszamolva: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    #: HOVA és MIÉRT került a kiadásba - a jelöléskor kötelező megadni.
    #:
    #: Enélkül a jelölés csak annyit mondana, hogy "ettől az embertől nem kell
    #: papír", de azt nem, hogy hol keresd a pénzt. Fél év múlva - vagy egy
    #: könyvelői kérdésnél - pont ez a kérdés: melyik tételben van benne.
    #:
    #: Külön mező a `megjegyzes`-től: azt a számlázó fél beállítása írja, és egy
    #: számlázó-módosítás elfújná ezt a magyarázatot.
    kiadas_megjegyzes: Mapped[str | None] = mapped_column(Text)

    #: MENNYIÉRT vállalja ez az ember EZT a napot - a diszpó írásakor, a
    #: stábtag felvételekor lebeszélt nettó díj.
    #:
    #: Miért kell? Mert a szerződést és a TIG-et hetekkel később, más ember
    #: adminisztrálja, mint aki a stábtaggal megbeszélte a díjat - és a
    #: papírra pont ez az összeg kell. Enélkül vagy visszakeresi valaki egy
    #: üzenetváltásból, vagy tippel. Ha itt meg van adva, a szerződés és a TIG
    #: piszkozata automatikusan ezzel az összeggel nyílik meg (lásd
    #: services/megbeszelt_dij.py).
    #:
    #: NEM kötelező: van, akivel nincs előre lebeszélve a díj (a felvételkor a
    #: kérdés kihagyható), és ilyenkor sor sem keletkezik.
    #:
    #: A napidíj a projekt PÉNZÜGYI oldalán nem számít semminek - az továbbra
    #: is a TIG-eken és a Kiadás sorokon áll, mert a megbeszélt díj csak
    #: megállapodás, nem kifizetés.
    megbeszelt_dij: Mapped[float | None] = mapped_column(
        Numeric(12, 2), comment="Ennyiért vállalja ezt a napot - nettó"
    )
    #: A díj magyarázata: mi van benne (pl. "saját kamerával", "két nap egyben",
    #: "utazás nélkül"). Fél év múlva a puszta összeg nem mondja meg, miért
    #: annyi - a szerződés készítője pedig pont ezt keresi.
    dij_megjegyzes: Mapped[str | None] = mapped_column(Text)

    megjegyzes: Mapped[str | None] = mapped_column(String(255))

    project: Mapped["Project"] = relationship(back_populates="szamlazok")
    employee: Mapped["Employee"] = relationship(foreign_keys=[employee_id])
    szamlazo_employee: Mapped["Employee | None"] = relationship(foreign_keys=[szamlazo_employee_id])
    szamlazo_vallalkozas: Mapped["Vallalkozas | None"] = relationship()
