from datetime import date

from sqlalchemy import JSON, Boolean, Date, ForeignKey, Numeric, String, Text, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class ProjectCode(TimestampMixin, Base):
    """Pénzügyi egység - 1 Project Code : N Project (forgatás). A pénzügyi mag.

    A 'HYPE ADMIN projektkódok' Notion tábla 81 mezős - a felhasználó döntése alapján
    (2026-07-02) minden mező saját, névvel ellátott oszlopot kap (nem egy közös JSON
    "extra" mezőbe zsúfolva). Kivétel: a puszta Notion buttonök (sosem hordoznak
    adatot), és azok a relationök, amik már úgyis megvannak a mi valódi, fordított
    irányú FK-jainkkal (pl. 'Utómunka'/'Bevételek'/'Forgatások'/'Projekt kiadások'/
    'Belsős extra kiadások' relationök - ezek ugyanazt az adatot duplikálnák, amit a
    Deliverable/Revenue/Project/Expense.project_code_id már helyesen hordoz).

    Sok Notion mező (formula/rollup) egy régi, Notion-oldali számítás pillanatképe -
    ahol van megbízható saját számításunk (pl. összes költség, profit), azt az
    `osszes_koltseg`/`becsult_profit` @property adja élőben, a Notion pillanatkép a
    `*_notion` nevű oszlopokban van, tájékoztató jelleggel."""

    __tablename__ = "project_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    projektkod: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)

    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False)
    contract_id: Mapped[int | None] = mapped_column(ForeignKey("contracts.id"))

    datum: Mapped[date | None] = mapped_column(Date)
    esemeny_allapota: Mapped[str | None] = mapped_column(String(50))
    penznem: Mapped[str] = mapped_column(String(10), default="HUF")
    arfolyam: Mapped[float | None] = mapped_column(Numeric(12, 4))
    szerzodes_url: Mapped[str | None] = mapped_column(String(500))
    tig_statusza: Mapped[str | None] = mapped_column(String(50))
    szamla_statusza: Mapped[str | None] = mapped_column(String(50))

    megjegyzes: Mapped[str | None] = mapped_column(Text)
    teljesites_datuma: Mapped[date | None] = mapped_column(Date)
    utalas_datuma: Mapped[date | None] = mapped_column(Date)
    szamla_url: Mapped[str | None] = mapped_column(String(500))
    tig_alairva_url: Mapped[str | None] = mapped_column(String(500))

    # --- a maradék Notion mezők, egyenként ("Notion property" a kommentben) ---
    teljesites_datum_formazva: Mapped[str | None] = mapped_column(String(255), comment="Teljesítés dátum formáz")
    netto_osszeg: Mapped[float | None] = mapped_column(Numeric(14, 2), comment="Nettó összeg")
    megrendelo_szekhelye: Mapped[str | None] = mapped_column(String(500), comment="Megrendelő  székhelye")
    profit_szazalek_notion: Mapped[dict | None] = mapped_column(JSON, comment="Profit százalék")
    geri_projekt: Mapped[str | None] = mapped_column(String(100), comment="Geri projekt")
    szerzodes_targya: Mapped[str | None] = mapped_column(String(255), comment="Szerződés tárgya")
    keltezes_datum_formazva: Mapped[str | None] = mapped_column(String(255), comment="Keltezés dátum formáz")
    gyartasi_koltseg_notion: Mapped[dict | None] = mapped_column(JSON, comment="Gyártási költség")
    szerzodes_specialis_eset: Mapped[str | None] = mapped_column(Text, comment="Szerződés speciális eset")
    fizetesi_hatarido: Mapped[date | None] = mapped_column(Date, comment="Fizetési határidő")
    megrendelo_nyilvantartasi_szam: Mapped[str | None] = mapped_column(
        String(100), comment="Megrendelő nyilvántartásiszám"
    )
    szerzodes_kuldes: Mapped[bool] = mapped_column(
        Boolean, server_default=false(), default=False, comment="Szerződés küldés"
    )
    osszes_koltseg_notion: Mapped[dict | None] = mapped_column(
        JSON, comment="Összes költség (Notion pillanatkép - élő érték: @property osszes_koltseg)"
    )
    tig_teljesitesi_ido: Mapped[str | None] = mapped_column(String(255), comment="TIG teljesítési idő")
    megrendelo_neve: Mapped[str | None] = mapped_column(String(255), comment="Megrendelő neve")
    osszesen_netto_notion: Mapped[dict | None] = mapped_column(JSON, comment="Összesen nettó")
    megrendelo_adoszama: Mapped[str | None] = mapped_column(String(50), comment="Megrendelő adószáma")
    netto_notion: Mapped[dict | None] = mapped_column(JSON, comment="Nettó")
    helyszin: Mapped[str | None] = mapped_column(String(255), comment="HELYSZÍN")
    datum_megjegyzes: Mapped[str | None] = mapped_column(Text, comment="DÁTUM megjegyzés")
    szerzodes_plusz_afa: Mapped[str | None] = mapped_column(String(100), comment="Szerződés plus ÁFA")
    tig_projektnev: Mapped[str | None] = mapped_column(String(255), comment="TIG projektnév")
    specialis_eset: Mapped[str | None] = mapped_column(Text, comment="Speciális eset")
    szerzodes_helye: Mapped[str | None] = mapped_column(String(100), comment="Szerződés helye")
    szerzodes_netto_osszeg: Mapped[float | None] = mapped_column(Numeric(14, 2), comment="Szerződés nettó összeg")
    megrendeloi_emailek: Mapped[str | None] = mapped_column(Text, comment="megrendelői emailek")
    brutto_notion: Mapped[dict | None] = mapped_column(JSON, comment="Bruttó")
    kulsos_notion_ids: Mapped[dict | None] = mapped_column(JSON, comment="Külsős (relation, nyers Notion page ID-k)")
    alvallalkozok_koltsege_notion: Mapped[dict | None] = mapped_column(JSON, comment="Alvállalkozók költsége")
    darabolva: Mapped[dict | None] = mapped_column(JSON, comment="Darabolva")
    vagasi_koltseg_notion: Mapped[dict | None] = mapped_column(JSON, comment="Vágási költség")
    project_nev: Mapped[str | None] = mapped_column(String(255), comment="PROJECT NÉV")
    szerzodes_statusza: Mapped[str | None] = mapped_column(String(50), comment="Szerződés státusza")
    plusz_afa: Mapped[str | None] = mapped_column(String(100), comment="Plusz ÁFA")
    megerte_e: Mapped[dict | None] = mapped_column(JSON, comment="Megérte-e")
    megrendelo_kepviseloje: Mapped[str | None] = mapped_column(String(255), comment="Megrendelő képviselője")
    szerzodes_projekt_nev: Mapped[str | None] = mapped_column(String(255), comment="Szerződés projekt név")
    teljesites: Mapped[str | None] = mapped_column(Text, comment="Teljesítés")
    tig_kikuldve: Mapped[bool] = mapped_column(
        Boolean, server_default=false(), default=False, comment="TIG kiküldve"
    )
    adminisztracios_tablaban: Mapped[str | None] = mapped_column(String(100), comment="ADMINISZTRÁCIÓS TÁBLÁBAN?")
    tig_specialis: Mapped[str | None] = mapped_column(Text, comment="TIG Speciális")
    keltezes_datuma: Mapped[date | None] = mapped_column(Date, comment="Keltezés dátuma")
    lejart_notion: Mapped[dict | None] = mapped_column(JSON, comment="Lejárt")
    megbizas_targya: Mapped[str | None] = mapped_column(String(255), comment="Megbízás tárgya")
    belsos_koltseg_akkor: Mapped[float | None] = mapped_column(Numeric(14, 2), comment="Belsős költség akkor")
    vallalasi_ar_notion: Mapped[dict | None] = mapped_column(JSON, comment="Vállalási ár")
    tovabbi_dokumentumok: Mapped[dict | None] = mapped_column(JSON, comment="További dokumentumok (files)")
    utomunkak_notion: Mapped[dict | None] = mapped_column(JSON, comment="Utómunkák (formula szöveg)")
    bevetel_formaja: Mapped[str | None] = mapped_column(String(100), comment="Bevétel formája")
    darabolas_notion_ids: Mapped[dict | None] = mapped_column(
        JSON, comment="HYPE ADMIN PROJEKTKÓDOK DARABOLÁS (relation, nyers Notion page ID-k)"
    )
    megrendelo_email: Mapped[str | None] = mapped_column(String(255), comment="Megrendelő email")
    forintban_notion: Mapped[dict | None] = mapped_column(JSON, comment="Forintban")
    szerzodes_keltezes_datuma: Mapped[date | None] = mapped_column(Date, comment="Szerződés keltezés dátuma")
    belsos_koltseg_notion: Mapped[dict | None] = mapped_column(JSON, comment="Belsős költség")
    belso_plusz_koltseg_notion: Mapped[dict | None] = mapped_column(JSON, comment="Belső plusz költség")
    tig_url: Mapped[str | None] = mapped_column(String(500), comment="TIG url")

    client: Mapped["Client"] = relationship(back_populates="project_codes")
    contract: Mapped["Contract"] = relationship(back_populates="project_codes")
    projects: Mapped[list["Project"]] = relationship(back_populates="project_code")
    expenses: Mapped[list["Expense"]] = relationship(back_populates="project_code")
    revenues: Mapped[list["Revenue"]] = relationship(back_populates="project_code")
    deliverables: Mapped[list["Deliverable"]] = relationship(back_populates="project_code")

    @property
    def osszes_koltseg(self) -> float:
        """Számított: belsos + alvallalkozok + vagasi koltseg. Lásd FinanceService."""
        return sum(e.brutto or 0 for e in self.expenses)

    @property
    def becsult_profit(self) -> float:
        bevetel = sum(r.brutto or 0 for r in self.revenues)
        return bevetel - self.osszes_koltseg
