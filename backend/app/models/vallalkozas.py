"""Vállalkozás (számlázó cég) - az a fél, aki a munkáról a SZÁMLÁT állítja ki.

Miért kell külön entitás? Két, a gyakorlatból jövő helyzet miatt, amit az
"ember = számlázó" feltevés nem tud leírni:

1. Egy forgatáson olyan emberek dolgoznak, akikkel MAGUKKAL nincs szerződésünk,
   viszont az őket küldő céggel igen. Nekik nem kell külön eseti szerződés -
   a cég keretszerződése fedi őket.
2. Egy ember más nevében számláz (a projekt két stábtagjának egy számlája
   van), vagy több projektet egyben számláz.

Mindkettőt ugyanaz a fogalom oldja meg: a projekt-beosztáshoz tartozik egy
SZÁMLÁZÓ FÉL (lásd models/project.py ProjectCrewMember), ami alapból maga az
ember, de lehet másik ember vagy egy Vallalkozas is.

A cégadatok (székhely, adószám, képviselő) ugyanazok a mezők, amik ma az
Employee-n ülnek - ott maradnak, mert az "ember a saját nevében számláz" eset
továbbra is ezekből tölt elő. Ez a tábla az az eset, amikor a cég önállóan is
számlázó fél (több emberrel).

A tagság (ki tartozik ide) SZÁNDÉKOSAN csak JAVASLAT, nem szabály: a felhasználó
szerint ugyanaz az ember "ma innen számláz, holnap saját névről, utána egy
harmadik helyről", tehát az igazságot mindig a projekt-beosztáson lévő számlázó
fél hordozza. A tagsági lista abból áll, hogy stábba vételkor mit ajánljunk fel,
és hogy meg lehessen nézni: "kik tartoznak ehhez a céghez"."""

from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class Vallalkozas(TimestampMixin, Base):
    """Egy számlázó cég."""

    __tablename__ = "vallalkozasok"

    id: Mapped[int] = mapped_column(primary_key=True)
    nev: Mapped[str] = mapped_column(String(255), nullable=False)

    szekhely: Mapped[str | None] = mapped_column(String(500))
    adoszam: Mapped[str | None] = mapped_column(String(50), index=True)
    kepviselo: Mapped[str | None] = mapped_column(String(255))
    nyilvantartasi_szam: Mapped[str | None] = mapped_column(String(100))
    email: Mapped[str | None] = mapped_column(String(255))
    megbizas_targya: Mapped[str | None] = mapped_column(String(255))
    plusz_afa: Mapped[bool | None] = mapped_column(Boolean)
    megjegyzes: Mapped[str | None] = mapped_column(Text)
    #: Kikapcsolható, ha már nem dolgozunk vele - a régi projektek adatai
    #: megmaradnak, csak új beosztásnál nem ajánljuk fel.
    aktiv: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    tagok: Mapped[list["VallalkozasTag"]] = relationship(
        back_populates="vallalkozas", cascade="all, delete-orphan", order_by="VallalkozasTag.id"
    )
    contracts: Mapped[list["Contract"]] = relationship(back_populates="vallalkozas")


class VallalkozasTag(TimestampMixin, Base):
    """Ki tartozik ehhez a céghez.

    Az időszak (kezdet/veg) opcionális és tájékoztató: a cégváltás időben
    változhat, de mivel a tényleges számlázó felet beosztásonként rögzítjük,
    ebből a listából nem vezetünk le jogosultságot - csak előtöltést és
    áttekintést."""

    __tablename__ = "vallalkozas_tagok"
    __table_args__ = (UniqueConstraint("vallalkozas_id", "employee_id", name="uq_vallalkozas_tag"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    vallalkozas_id: Mapped[int] = mapped_column(
        ForeignKey("vallalkozasok.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    kezdet: Mapped[date | None] = mapped_column(Date)
    veg: Mapped[date | None] = mapped_column(Date)
    megjegyzes: Mapped[str | None] = mapped_column(String(255))

    vallalkozas: Mapped["Vallalkozas"] = relationship(back_populates="tagok")
    employee: Mapped["Employee"] = relationship(back_populates="vallalkozas_tagsagok")
