"""A Krumpello ÖSSZESÍTŐ - ugyanaz a számolás, mint a kassza-táblázat jobb
szélén álló blokké.

Miért egy az egyben azt reprodukálja? Mert a napi munka ma abban a
táblázatban folyik, és amíg mindkettő él, egy eltérő számítás azonnal
bizalmatlanná tenné a rendszert ("melyik a jó szám?"). A képlet tehát nem
találgatás - a bevezetéskor tételesen egyeztetve lett a táblázat saját
összegeivel, mind a hét soron.

A három egyenleg mást mér, ezért nem adhatók össze:

- SZÁMLA EGYENLEG: ami a bankszámlán mozgott (kártyás bevétel mínusz utalás).
- KÉSZPÉNZ EGYENLEG: ami a kasszában van (készpénzes bevétel + borravaló
  mínusz készpénzes kiadás) - ezt lehet fizikailag megszámolni.
- EXTRA EGYENLEG: a SZÁMLA NÉLKÜLI mozgások összege. Ez a modul lényege: az
  extra bevétel és az extra kiadás külön-külön nem mond semmit, együtt viszont
  megmondja, hogy az elszámolatlan pénz pluszban vagy mínuszban áll.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.krumpello import EXTRA_FORRAS, KrumpelloKiadas, KrumpelloMunkaora, KrumpelloNap


def _f(ertek) -> float:
    """Decimal/None -> float. A Numeric oszlopok Decimal-ként jönnek vissza, és
    a Decimal + float TypeError-t dob."""
    return float(ertek) if ertek is not None else 0.0


@dataclass
class Bevetel:
    brutto_kp: float = 0.0
    brutto_kartya: float = 0.0
    netto_kp: float = 0.0
    netto_kartya: float = 0.0
    borravalo_kp: float = 0.0
    borravalo_kartya: float = 0.0
    extra: float = 0.0

    @property
    def brutto(self) -> float:
        return self.brutto_kp + self.brutto_kartya

    @property
    def netto(self) -> float:
        return self.netto_kp + self.netto_kartya

    @property
    def borravalo(self) -> float:
        return self.borravalo_kp + self.borravalo_kartya


@dataclass
class KiadasBontas:
    netto: float = 0.0
    afa: float = 0.0
    brutto: float = 0.0


def _idoszak_szures(stmt, mezo, tol: date | None, ig: date | None):
    if tol is not None:
        stmt = stmt.where(mezo >= tol)
    if ig is not None:
        stmt = stmt.where(mezo <= ig)
    return stmt


def bevetel_osszesito(db: Session, tol: date | None = None, ig: date | None = None) -> Bevetel:
    oszlopok = (
        KrumpelloNap.brutto_kp,
        KrumpelloNap.brutto_kartya,
        KrumpelloNap.netto_kp,
        KrumpelloNap.netto_kartya,
        KrumpelloNap.borravalo_kp,
        KrumpelloNap.borravalo_kartya,
        KrumpelloNap.extra,
    )
    stmt = _idoszak_szures(select(*[func.sum(o) for o in oszlopok]), KrumpelloNap.datum, tol, ig)
    sor = db.execute(stmt).one()
    return Bevetel(*[_f(v) for v in sor])


def kiadas_osszesito(db: Session, tol: date | None = None, ig: date | None = None) -> dict[str, KiadasBontas]:
    """Forrásonkénti kiadás-bontás.

    A dátum szerinti szűrés a dátum NÉLKÜLI sorokat kihagyja - ezek jellemzően
    még nem beazonosított tételek. Szűretlen (teljes) lekérdezésnél viszont
    benne vannak, hogy a végösszeg ne legyen kevesebb a valóságnál.
    """
    stmt = _idoszak_szures(
        select(
            KrumpelloKiadas.forras,
            func.sum(KrumpelloKiadas.netto),
            func.sum(KrumpelloKiadas.afa),
            func.sum(KrumpelloKiadas.brutto),
        ).group_by(KrumpelloKiadas.forras),
        KrumpelloKiadas.datum,
        tol,
        ig,
    )
    eredmeny: dict[str, KiadasBontas] = {}
    for forras, netto, afa, brutto in db.execute(stmt).all():
        eredmeny[forras] = KiadasBontas(netto=_f(netto), afa=_f(afa), brutto=_f(brutto))
    return eredmeny


def munkaber_osszesen(db: Session, tol: date | None = None, ig: date | None = None) -> tuple[float, float, float]:
    """(ledolgozott óra, kifizetett bér, borravaló) az időszakban."""
    stmt = _idoszak_szures(
        select(
            func.sum(KrumpelloMunkaora.ora),
            func.sum(KrumpelloMunkaora.fizetes),
            func.sum(KrumpelloMunkaora.borravalo),
        ),
        KrumpelloMunkaora.datum,
        tol,
        ig,
    )
    ora, fizetes, borravalo = db.execute(stmt).one()
    return _f(ora), _f(fizetes), _f(borravalo)


@dataclass
class Osszesito:
    bevetel: Bevetel
    kiadas: dict[str, KiadasBontas]
    #: (számla, készpénz) egyenleg nettó és bruttó szinten.
    szamla_egyenleg_netto: float
    szamla_egyenleg_brutto: float
    keszpenz_egyenleg_netto: float
    keszpenz_egyenleg_brutto: float
    #: A modul kulcsszáma: extra bevétel - extra kiadás. Negatív = több
    #: számlázatlan pénz ment ki, mint amennyi bejött.
    extra_bevetel: float
    extra_kiadas: float
    extra_egyenleg: float
    munkaora: float
    munkaber: float
    munkaber_borravalo: float


def osszesito(db: Session, tol: date | None = None, ig: date | None = None) -> Osszesito:
    bev = bevetel_osszesito(db, tol, ig)
    kiad = kiadas_osszesito(db, tol, ig)
    ures = KiadasBontas()
    utalas = kiad.get("utalas", ures)
    keszpenz = kiad.get("keszpenz", ures)
    extra_kiadas = kiad.get(EXTRA_FORRAS, ures).brutto
    ora, ber, borravalo = munkaber_osszesen(db, tol, ig)

    return Osszesito(
        bevetel=bev,
        kiadas=kiad,
        # A kártyás bevétel a bankszámlára fut be, onnan mennek az utalások.
        szamla_egyenleg_netto=bev.netto_kartya - utalas.netto,
        szamla_egyenleg_brutto=bev.brutto_kartya - utalas.brutto,
        # A borravaló SZÁNDÉKOSAN nincs benne: az a dolgozóké, nem a cég pénze -
        # csak fizikailag halad át a kasszán. A táblázat is így számol.
        #
        # EGY PONTON ELTÉRÜNK A TÁBLÁZATTÓL, tudatosan: ott a készpénz-egyenleg
        # NETTÓ sora a KÁRTYÁS nettóra hivatkozik (=AJ12-AJ26, ugyanaz az AJ12,
        # amit a számla-egyenleg is használ), tehát egy lehúzott képlet
        # elgépelése - a kártyás bevételt vonja össze a készpénzes kiadással.
        # A bruttó sora (=AJ8-AJ28) helyesen a készpénzes bevételből indul. Itt
        # a nettó is a készpénzes bevételből számol, ezért ez az egy szám
        # eltér a táblázatétól - és ez a helyes, nem a másik.
        keszpenz_egyenleg_netto=bev.netto_kp - keszpenz.netto,
        keszpenz_egyenleg_brutto=bev.brutto_kp - keszpenz.brutto,
        extra_bevetel=bev.extra,
        extra_kiadas=extra_kiadas,
        extra_egyenleg=bev.extra - extra_kiadas,
        munkaora=ora,
        munkaber=ber,
        munkaber_borravalo=borravalo,
    )
