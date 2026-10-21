"""Krumpello munkabér: bejelentés, utalás és készpénz szétválasztása.

Az alapkérdés, amire ez a modul válaszol: **egy ledolgozott napból mennyi megy
utalással, és mennyit kell készpénzben odaadni?**

A szabály a valóságot követi:

- ha az ember arra a napra **be volt jelentve** (EFO vagy határozott idejű
  munkaszerződés), akkor a **bejelentett napi bér** utalással megy - az
  szerepel a bérszámfejtésben -, a fölötte lévő rész pedig készpénzben;
- ha **nem volt bejelentve**, az egész napi bér készpénz.

Képlettel: `készpénz = óra × órabér − bejelentett napi bér`.

A bejelentés az IDŐSZAKHOZ tartozik (lásd models/krumpello.KrumpelloIdoszak):
ugyanaz az ember nyáron EFO-val, ősztől szerződéssel dolgozik. A napon
felülírható, mert van kivétel - egy beugrás a szerződéses időszak közepén,
amire aznap nem jelentették be.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.krumpello import (
    ALAP_BEJELENTES,
    BEJELENTES_CIMKEK,
    KrumpelloIdoszak,
    KrumpelloMunkaora,
)


def _f(ertek) -> float:
    return float(ertek) if ertek is not None else 0.0


def idoszak_a_napra(idoszakok: list[KrumpelloIdoszak], nap: date) -> KrumpelloIdoszak | None:
    """Melyik időszakba esik ez a nap? A nyitott vég a végtelenig tart.

    Egy emberre az időszakok nem fedhetik egymást (a mentés ezt ellenőrzi),
    tehát legfeljebb egy találat van - de ha mégis több lenne (kézzel javított
    régi adat), a LEGKORÁBBAN kezdődőt vesszük, hogy a válasz determinisztikus
    legyen, ne a lekérdezés sorrendjétől függjön."""
    talalatok = [
        i for i in idoszakok if i.kezdet <= nap and (i.veg is None or nap <= i.veg)
    ]
    return min(talalatok, key=lambda i: (i.kezdet, i.id)) if talalatok else None


@dataclass
class NapiBontas:
    """Egy munkanap pénzügyi bontása."""

    munkaora_id: int
    datum: date
    ora: float = 0.0
    orabar: float = 0.0
    #: A napra járó teljes bér (a tárolt `fizetes`, ami alapból óra × órabér).
    jarandosag: float = 0.0
    borravalo: float = 0.0

    #: Ténylegesen érvényes bejelentés (a napé, vagy örökölve az időszakból).
    bejelentes: str = ALAP_BEJELENTES
    #: Honnan jött: "nap" (kézzel felülírva) vagy "idoszak" (örökölt).
    bejelentes_forrasa: str = "idoszak"
    idoszak_id: int | None = None

    #: A bejelentett napi bér - ennyi megy UTALÁSSAL.
    utalando: float = 0.0
    #: A maradék, ami KÉSZPÉNZBEN jár.
    keszpenz: float = 0.0

    kifizetve: bool = False
    kifizetes_datuma: date | None = None

    @property
    def bejelentve(self) -> bool:
        return self.bejelentes != "nincs"

    @property
    def bejelentes_cimke(self) -> str:
        return BEJELENTES_CIMKEK.get(self.bejelentes, self.bejelentes)

    @property
    def tulfizetett(self) -> bool:
        """A bejelentett napi bér TÖBB, mint amennyit aznap ledolgozott.

        Nem hiba, csak figyelemre méltó: rövid napon a fix bejelentett bér
        magasabb lehet a ledolgozott óráknál, ilyenkor nincs készpénz, sőt az
        utalás "előre fizet". Az időszak szintjén ez kiegyenlítődik, ezért az
        összesítésben nem vágjuk nullára - csak jelezzük."""
        return self.keszpenz < 0


def bontsd_a_napot(
    munkaora: KrumpelloMunkaora, idoszakok: list[KrumpelloIdoszak]
) -> NapiBontas:
    """Egy munkanap bontása utalandóra és készpénzre."""
    idoszak = idoszak_a_napra(idoszakok, munkaora.datum)

    # A NAPON megadott érték erősebb az időszakénál: az a kivétel, amit
    # kifejezetten rögzítettek.
    if munkaora.bejelentes:
        bejelentes, forras = munkaora.bejelentes, "nap"
    elif idoszak is not None:
        bejelentes, forras = idoszak.bejelentes, "idoszak"
    else:
        bejelentes, forras = ALAP_BEJELENTES, "idoszak"

    if munkaora.bejelentett_napi_ber is not None:
        napi_ber = _f(munkaora.bejelentett_napi_ber)
    elif idoszak is not None:
        napi_ber = _f(idoszak.napi_ber)
    else:
        napi_ber = 0.0

    jarandosag = _f(munkaora.fizetes)
    # Bejelentés nélkül nincs utalás: az egész nap készpénz. Enélkül egy
    # ottfelejtett napi bér némán utalássá tenné a nem bejelentett napot is.
    utalando = napi_ber if bejelentes != "nincs" else 0.0

    return NapiBontas(
        munkaora_id=munkaora.id,
        datum=munkaora.datum,
        ora=_f(munkaora.ora),
        orabar=_f(munkaora.orabar),
        jarandosag=jarandosag,
        borravalo=_f(munkaora.borravalo),
        bejelentes=bejelentes,
        bejelentes_forrasa=forras,
        idoszak_id=idoszak.id if idoszak else None,
        utalando=utalando,
        keszpenz=round(jarandosag - utalando, 2),
        kifizetve=munkaora.kifizetve,
        kifizetes_datuma=munkaora.kifizetes_datuma,
    )


@dataclass
class Elszamolas:
    """Egy időszak (vagy tetszőleges napcsoport) összesítése."""

    napok_szama: int = 0
    ora_osszesen: float = 0.0
    jarandosag: float = 0.0
    utalando: float = 0.0
    keszpenz: float = 0.0
    borravalo: float = 0.0
    #: Amit már kifizettünk, illetve ami még hátravan - a járandóságból.
    kifizetett: float = 0.0
    hatralek: float = 0.0
    kifizetett_napok: int = 0
    #: Bejelentés szerinti napszám, hogy a bérszámfejtéssel egyeztethető legyen.
    napok_bejelentesenkent: dict[str, int] = field(default_factory=dict)
    bontasok: list[NapiBontas] = field(default_factory=list)

    @property
    def teljesen_kifizetve(self) -> bool:
        return self.napok_szama > 0 and self.kifizetett_napok == self.napok_szama


def szamold_ki(bontasok: list[NapiBontas]) -> Elszamolas:
    """Napi bontásokból időszak-összesítő.

    A készpénzt SZÁNDÉKOSAN előjelesen adjuk össze: ha egy rövid napon a
    bejelentett bér többet fizetett, mint amennyi járt, az a következő napok
    készpénzéből jön le - pont úgy, ahogy a valóságban is kiegyenlítődik egy
    időszak végén."""
    e = Elszamolas(napok_szama=len(bontasok), bontasok=bontasok)
    for b in bontasok:
        e.ora_osszesen += b.ora
        e.jarandosag += b.jarandosag
        e.utalando += b.utalando
        e.keszpenz += b.keszpenz
        e.borravalo += b.borravalo
        e.napok_bejelentesenkent[b.bejelentes] = e.napok_bejelentesenkent.get(b.bejelentes, 0) + 1
        if b.kifizetve:
            e.kifizetett += b.jarandosag
            e.kifizetett_napok += 1
        else:
            e.hatralek += b.jarandosag
    for mezo in ("ora_osszesen", "jarandosag", "utalando", "keszpenz", "borravalo", "kifizetett", "hatralek"):
        setattr(e, mezo, round(getattr(e, mezo), 2))
    return e


def idoszak_napjai(db: Session, idoszak: KrumpelloIdoszak) -> list[KrumpelloMunkaora]:
    """Az időszakba eső munkaóra-sorok - dátum szerint, nem idegen kulccsal.

    Lásd models/krumpello.KrumpelloIdoszak: így egy utólag felvitt nap magától
    a helyére kerül."""
    stmt = select(KrumpelloMunkaora).where(
        KrumpelloMunkaora.dolgozo_id == idoszak.dolgozo_id,
        KrumpelloMunkaora.datum >= idoszak.kezdet,
    )
    if idoszak.veg is not None:
        stmt = stmt.where(KrumpelloMunkaora.datum <= idoszak.veg)
    return list(db.scalars(stmt.order_by(KrumpelloMunkaora.datum, KrumpelloMunkaora.id)))


def dolgozo_idoszakai(db: Session, dolgozo_id: int) -> list[KrumpelloIdoszak]:
    return list(
        db.scalars(
            select(KrumpelloIdoszak)
            .where(KrumpelloIdoszak.dolgozo_id == dolgozo_id)
            .order_by(KrumpelloIdoszak.kezdet)
        )
    )


def idoszak_elszamolasa(db: Session, idoszak: KrumpelloIdoszak) -> Elszamolas:
    """Egy időszak teljes elszámolása, napi bontással együtt."""
    idoszakok = dolgozo_idoszakai(db, idoszak.dolgozo_id)
    return szamold_ki([bontsd_a_napot(m, idoszakok) for m in idoszak_napjai(db, idoszak)])


def atfedes(
    idoszakok: list[KrumpelloIdoszak], kezdet: date, veg: date | None, kihagyott_id: int | None = None
) -> KrumpelloIdoszak | None:
    """Van-e ütköző időszak? Az elsőt adja vissza, vagy None.

    Azért kell tiltani az átfedést, mert az időszak a napok BEJELENTÉSÉT
    hordozza: két egymást fedő időszakból nem lehetne eldönteni, melyik
    szerint kell elszámolni azt a napot - és a válasz némán a lekérdezés
    sorrendjétől függne."""
    for i in idoszakok:
        if kihagyott_id is not None and i.id == kihagyott_id:
            continue
        # Két intervallum akkor fed át, ha mindkettő kezdete a másik vége előtt
        # (vagy egyenlő) van. A nyitott vég a végtelent jelenti.
        i_veg_ok = i.veg is None or kezdet <= i.veg
        uj_veg_ok = veg is None or i.kezdet <= veg
        if i_veg_ok and uj_veg_ok:
            return i
    return None
