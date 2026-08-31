"""A HYPE 2026 DISZPÓSTÁBLA - a Google Sheet táblázat a rendszerben.

Ez a tábla eddig egy Google Sheetben élt, és nem csak beosztás volt: a CELLA
SZÍNE hordozta a legfontosabb adatot, azt, hogy ki melyik nap DOLGOZOTT. Ebből
derül ki, hány munkanapja van valakinek egy hónapban - és ez dönti el, mikor
fogy el a szerződött napjainak száma (lásd services/munkanap_szamlalo.py és
services/belsos_koltseg.py).

MIÉRT GENERIKUS RÁCS? Mert a munkafüzetnek hat munkalapja van, és mind más
alakú: a belsős tábla 25 oszlop emberekkel, a külsős 146 oszlop
kategóriákkal, az AUTÓK egy sima lista, a PROJECT KÓDOK egy másik. Egy
"mindent tudó" séma vagy csak az egyiket szolgálná ki, vagy annyi kivétellel
lenne tele, hogy senki nem érti. A rács viszont mindet elbírja, és pontosan
azt adja vissza, amit a felhasználó lát a Sheetben.

A JELENTÉS ott van, ahol kell: az OSZLOP tudja, melyik munkatárs ő
(`employee_id`), a SOR tudja, melyik naphoz tartozik (`datum`) - ez a két
kapcsolat teszi a rácsot számolhatóvá.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

#: A cella SZÍNEI - a jelentésükkel, nem a hexakóddal. A Sheetben a szín az
#: adat, tehát nálunk sem lehet puszta formázás: a munkanap-számlálás ebből
#: dolgozik (lásd services/munkanap_szamlalo.py).
#:
#: - `zold`   - aznap DOLGOZOTT (a vágóknál: terepen dolgozott);
#: - `kek`    - a VÁGÓK munkanapja (irodában) - ugyanúgy munkanap;
#: - `feher`  - munkanap volt, de nem kaptunk neki munkát - EZ IS MUNKANAP;
#: - `piros`  - nem munkanap (szabadnap);
#: - `szurke` - nem releváns (akkor még nem dolgozott nálunk).
SZIN_ZOLD = "zold"
SZIN_KEK = "kek"
SZIN_FEHER = "feher"
SZIN_PIROS = "piros"
SZIN_SZURKE = "szurke"

SZINEK: tuple[str, ...] = (SZIN_ZOLD, SZIN_KEK, SZIN_FEHER, SZIN_PIROS, SZIN_SZURKE)

#: MUNKANAPNAK számító színek. A fehér is köztük van, és ez a lényeg: az a nap
#: is munkanap volt, csak nem tudtunk rá munkát adni - a szerződött napokból
#: ugyanúgy fogy.
MUNKANAP_SZINEK: frozenset[str] = frozenset({SZIN_ZOLD, SZIN_KEK, SZIN_FEHER})


class DiszpoMunkalap(TimestampMixin, Base):
    """Egy munkalap (fül) a táblázatból."""

    __tablename__ = "diszpo_munkalapok"

    id: Mapped[int] = mapped_column(primary_key=True)
    #: A fül neve, ahogy a Sheetben áll ("BELSŐS DISZPÓSTÁBLA").
    nev: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    #: Balról jobbra a fülek sorrendje - a felület ebben mutatja őket.
    sorrend: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Hány sor és oszlop tartozik hozzá (a tartalom határa, nem a Sheet
    #: elvi 1000 sora) - a felület ennyit rajzol ki.
    sor_szam: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    oszlop_szam: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Hány felső sor a FEJLÉC (a belsősnél kettő: a csoportok és a nevek) -
    #: ezeket a felület odaragasztja a tetejére görgetéskor.
    fejlec_sorok: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    oszlopok: Mapped[list["DiszpoOszlop"]] = relationship(
        back_populates="munkalap", cascade="all, delete-orphan", order_by="DiszpoOszlop.idx"
    )
    sorok: Mapped[list["DiszpoSor"]] = relationship(
        back_populates="munkalap", cascade="all, delete-orphan", order_by="DiszpoSor.idx"
    )
    cellak: Mapped[list["DiszpoCella"]] = relationship(
        back_populates="munkalap", cascade="all, delete-orphan"
    )


class DiszpoOszlop(TimestampMixin, Base):
    """Egy oszlop - és ami a lényeg: KIÉ.

    Az `employee_id` teszi a rácsot számolhatóvá: enélkül csak annyit tudnánk,
    hogy a "GERI" feliratú oszlopban zöld van, azt nem, hogy melyik
    munkatársunkról szól. A kötés az importnál névre megy, és a felületen
    javítható - két Gergely között egy szkript nem tud dönteni."""

    __tablename__ = "diszpo_oszlopok"
    __table_args__ = (UniqueConstraint("munkalap_id", "idx", name="uq_diszpo_oszlop"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    munkalap_id: Mapped[int] = mapped_column(
        ForeignKey("diszpo_munkalapok.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: 0-tól számozva (0 = "A" oszlop).
    idx: Mapped[int] = mapped_column(Integer, nullable=False)
    #: Az oszlop felirata ("GERI", "DÁTUM").
    cimke: Mapped[str | None] = mapped_column(String(255))
    #: Melyik szekcióhoz tartozik ("CAMERA CREW", "UTÓMUNKA OSZTÁLY").
    csoport: Mapped[str | None] = mapped_column(String(100))
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"), index=True)
    #: Elrejtett oszlop: a felület nem mutatja (pl. aki már nem dolgozik
    #: velünk), de az adata és a munkanap-számítása változatlanul él. A
    #: sheet-szinkron a feliraton (cimke) át megőrzi - lásd
    #: services/diszpo_sheet_sync.py.
    rejtett: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    munkalap: Mapped["DiszpoMunkalap"] = relationship(back_populates="oszlopok")
    employee = relationship("Employee")


class DiszpoSor(TimestampMixin, Base):
    """Egy sor - és ami a lényeg: MELYIK NAP.

    A dátum nem minden soron áll ott: egy naphoz két diszpó is tartozhat, és
    olyankor a második sor dátum-mezője üres a Sheetben. Az import ezért
    TOVÁBBVISZI az utolsó látott dátumot - különben a második diszpó napja
    eltűnne a számolásból."""

    __tablename__ = "diszpo_sorok"
    __table_args__ = (UniqueConstraint("munkalap_id", "idx", name="uq_diszpo_sor"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    munkalap_id: Mapped[int] = mapped_column(
        ForeignKey("diszpo_munkalapok.id", ondelete="CASCADE"), nullable=False, index=True
    )
    idx: Mapped[int] = mapped_column(Integer, nullable=False)
    datum: Mapped[date | None] = mapped_column(Date, index=True)
    #: A hét napja, ahogy a táblázatban áll ("csütörtök").
    nap: Mapped[str | None] = mapped_column(String(20))
    #: Hányadik diszpó ezen a napon (a Sheet "DISZPÓSZÁM" oszlopa).
    diszposzam: Mapped[int | None] = mapped_column(Integer)
    #: Hónap-elválasztó sor ("❄️ JANUÁR ❄️") - nem munkanap, csak felirat.
    elvalaszto: Mapped[bool] = mapped_column(default=False, nullable=False)

    munkalap: Mapped["DiszpoMunkalap"] = relationship(back_populates="sorok")


class DiszpoCella(TimestampMixin, Base):
    """Egy cella: a szövege és a SZÍNE.

    Csak azok a cellák léteznek, amikben van valami - se szöveg, se szín
    nélküli cellát nem tárolunk (a belsős munkalapon is a felük üres)."""

    __tablename__ = "diszpo_cellak"
    __table_args__ = (UniqueConstraint("munkalap_id", "sor_idx", "oszlop_idx", name="uq_diszpo_cella"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    munkalap_id: Mapped[int] = mapped_column(
        ForeignKey("diszpo_munkalapok.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sor_idx: Mapped[int] = mapped_column(Integer, nullable=False)
    oszlop_idx: Mapped[int] = mapped_column(Integer, nullable=False)
    ertek: Mapped[str | None] = mapped_column(Text)
    #: A SZINEK egyike - vagy None, ha nincs kiszínezve. Ismeretlen (a
    #: táblázatból hozott, nálunk nem nevesített) szín itt nem marad meg: a
    #: jelentés nélküli szín csak zavarna a számolásnál.
    szin: Mapped[str | None] = mapped_column(String(20), index=True)

    munkalap: Mapped["DiszpoMunkalap"] = relationship(back_populates="cellak")
