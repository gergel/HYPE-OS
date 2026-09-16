"""MUNKAFELAJÁNLÁSOK (ajánlatkérések) - a felhasználó által megadott folyamat:

feladat létrehozása -> külsősök kiválasztása -> ajánlatkérés kiküldése ->
árajánlatok gyűjtése a válaszadási határidőig -> BELSŐ kiválasztás a határidő
után -> a kiválasztott és a többi meghívott értesítése.

SENKI nem kapja meg automatikusan a munkát a jelentkezés vagy az ajánlat
beküldésének pillanatában - a korábbi "első elfogadóé a munka" elv és az
előre megadott díjazás kifejezetten tilos: az árat a meghívott külsősök
ajánlják meg, és a döntést ember hozza, a határidő lejárta után."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

#: Az ajánlatkérés TÁROLT állapotai. A "dontesre_var" szándékosan NEM tárolt:
#: az az "ajanlatadas" állapot lejárt határidejű alakja, és a szerver mindig a
#: pillanatnyi időből számolja (lásd services/munkafelajanlas.effektiv_allapot)
#: - így nincs szükség időzített állapot-átbillentő folyamatra, és nem is
#: csúszhat el.
AJANLATKERES_ALLAPOTOK = ("piszkozat", "ajanlatadas", "kiosztva", "lezarva_nyertes_nelkul", "visszavonva")


class Ajanlatkeres(TimestampMixin, Base):
    """Egy meghirdetett pozíció (projekt + munkakör) ajánlatkérése.

    Egy projekt különböző munkakörei KÜLÖN ajánlatkérések (a felhasználó
    kérése): saját meghívottakkal, határidővel, ajánlatokkal és kiválasztással."""

    __tablename__ = "ajanlatkeresek"

    id: Mapped[int] = mapped_column(primary_key=True)
    #: A MEGLÉVŐ projektek közül választva (a felhasználó kérése) - a
    #: projekt_nev ennek a pillanatképe, hogy a levelek és a lista akkor is
    #: pontosak maradjanak, ha a projektet később átnevezik/törlik.
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"))
    projekt_nev: Mapped[str] = mapped_column(String(255), nullable=False)
    munkakor: Mapped[str] = mapped_column(String(255), nullable=False)
    leiras: Mapped[str | None] = mapped_column(Text, comment="Rövid feladatleírás")
    helyszin: Mapped[str | None] = mapped_column(String(500))
    #: SZABAD SZÖVEG (nem dátum-oszlop): a munkavégzés lehet tartomány
    #: ("okt. 12-14.") vagy feltételes ("esőnap: okt. 20.") - a válaszadási
    #: határidőtől kifejezetten elkülönítve kezeljük (a felhasználó kérése).
    munkavegzes_idopont: Mapped[str | None] = mapped_column(String(255), comment="A munkavégzés várható időpontja")
    teljesitesi_hatarido: Mapped[str | None] = mapped_column(String(255), comment="Esetleges teljesítési határidő")
    #: A VÁLASZADÁSI határidő - eddig lehet ajánlatot beküldeni/módosítani.
    #: UTC-ben tárolva (tz nélkül); a felület magyar idő (Europe/Budapest)
    #: szerint kéri be és mutatja (lásd services/munkafelajanlas).
    valaszadasi_hatarido: Mapped[datetime | None] = mapped_column(DateTime, comment="Válaszadási határidő (UTC)")
    allapot: Mapped[str] = mapped_column(String(30), nullable=False, default="piszkozat", server_default="piszkozat")

    kapcsolattarto_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))
    letrehozta_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))

    #: A NYERTES meghívott. Szándékosan sima Integer, nem ForeignKey: a
    #: meghívott-tábla erre a táblára mutat, egy oda-vissza FK körkörös
    #: függőség lenne a sémában - az épséget a kiválasztás zárolt művelete
    #: tartja (lásd services/munkafelajanlas.kivalasztas).
    nyertes_meghivott_id: Mapped[int | None] = mapped_column(Integer)
    #: A döntéskor ELFOGADOTT feltételek tartós másolata (a felhasználó
    #: kérése): ha az ajánlat sora később bármiért változna, a megállapodás
    #: akkor is ez marad.
    elfogadott_osszeg: Mapped[float | None] = mapped_column(Numeric(14, 2))
    elfogadott_penznem: Mapped[str | None] = mapped_column(String(10))
    elfogadott_brutto: Mapped[bool | None] = mapped_column(Boolean)
    lezarva: Mapped[datetime | None] = mapped_column(DateTime, comment="A döntés/lezárás időpontja (UTC)")
    lezaras_megjegyzes: Mapped[str | None] = mapped_column(Text)

    kapcsolattarto: Mapped["Employee"] = relationship(foreign_keys=[kapcsolattarto_id])
    letrehozta: Mapped["Employee"] = relationship(foreign_keys=[letrehozta_id])
    meghivottak: Mapped[list["AjanlatMeghivott"]] = relationship(
        back_populates="ajanlatkeres", cascade="all, delete-orphan", order_by="AjanlatMeghivott.id"
    )


class AjanlatMeghivott(TimestampMixin, Base):
    """Egy meghívott külsős egy ajánlatkérésen - saját, személyre szóló
    tokennel (a címzettek nem látják egymást), és a KÜLDÉSEK könyvelésével:
    a meghívó és az eredmény-értesítő kiküldése/hibája külön-külön rögzül,
    hogy az újrapróbálás csak a sikertelen leveleket ismételje."""

    __tablename__ = "ajanlat_meghivottak"
    __table_args__ = (UniqueConstraint("ajanlatkeres_id", "employee_id", name="uq_ajanlat_meghivott"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    ajanlatkeres_id: Mapped[int] = mapped_column(ForeignKey("ajanlatkeresek.id", ondelete="CASCADE"), nullable=False)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    #: A személyes link tokenje - ebből nyílik a publikus ajánlati oldal.
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    #: A kiküldéskor használt cím pillanatképe - ha az adatlapon később
    #: átírják, attól még látszik, hova ment a levél.
    email_cim: Mapped[str | None] = mapped_column(String(255))

    meghivo_kikuldve: Mapped[datetime | None] = mapped_column(DateTime)
    meghivo_hiba: Mapped[str | None] = mapped_column(Text)
    eredmeny_kikuldve: Mapped[datetime | None] = mapped_column(DateTime)
    eredmeny_hiba: Mapped[str | None] = mapped_column(Text)

    ajanlatkeres: Mapped[Ajanlatkeres] = relationship(back_populates="meghivottak")
    employee: Mapped["Employee"] = relationship()
    #: A meghívott (legfeljebb egy) árajánlata.
    ajanlat: Mapped["MunkaArajanlat | None"] = relationship(
        back_populates="meghivott", cascade="all, delete-orphan", uselist=False
    )


class MunkaArajanlat(TimestampMixin, Base):
    """Egy meghívott beküldött árajánlata. A határidőig módosítható és
    visszavonható (a visszavonást jelezzük, nem töröljük a sort - a belső
    összehasonlító táblán látszania kell, mi történt)."""

    __tablename__ = "munka_arajanlatok"

    id: Mapped[int] = mapped_column(primary_key=True)
    meghivott_id: Mapped[int] = mapped_column(
        ForeignKey("ajanlat_meghivottak.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    #: A TELJES feladatra ajánlott vállalási összeg.
    osszeg: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    penznem: Mapped[str] = mapped_column(String(10), nullable=False, default="HUF", server_default="HUF")
    #: Az összeg bruttó-e (False = nettó) - a felületen kötelező, egyértelmű jelölés.
    brutto: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    megjegyzes: Mapped[str | None] = mapped_column(Text, comment="Megjegyzés / vállalási feltétel")
    #: A meghívott megerősítette, hogy az időpont és a feladat vállalható.
    vallalja: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    bekuldve: Mapped[datetime | None] = mapped_column(DateTime, comment="Első beküldés (UTC)")
    modositva: Mapped[datetime | None] = mapped_column(DateTime, comment="Utolsó módosítás (UTC)")
    visszavonva: Mapped[datetime | None] = mapped_column(DateTime, comment="Visszavonás időpontja (UTC)")

    meghivott: Mapped[AjanlatMeghivott] = relationship(back_populates="ajanlat")
