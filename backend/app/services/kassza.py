"""A HÁZIPÉNZTÁR (kassza) teljes képe - egy helyen, egy szabály szerint.

A készpénz két felületen jelenik meg: a Pénzügyek összesítő kártyáján (mennyi
van a dobozban) és a Házipénztár oldalon (miből jött össze). A kettő ugyanabból
a számításból dolgozik, mert két külön implementáció előbb-utóbb két külön
egyenleget adna.

MI MOZGATJA A HÁZIPÉNZTÁRAT? (a felhasználó 2026-09-24-i döntése, a pénztár
nulláról újraindításával együtt) Pontosan négyféle tétel:

1. **BEVÉTEL** - kizárólag KÉSZPÉNZES projektkód-kifizetés: a projektkód
   számla-lépésénél „Kifizetve / Készpénz”-ként rögzített bevétel-sor (lásd
   services/megrendeloi_szamla.py). Ugyanaz a sor a Bevételek között is
   látszik - külön házipénztár-sor NEM készül hozzá, mert az duplázna.
2. **ÁTVEZETÉS** - ATM-ből felvett készpénz (a `kp_forgalmak` tábla sorai). A
   házipénztár nő, a bankszámla egyenlege ugyanennyivel csökken, de KIADÁS
   NEM keletkezik: ez a saját pénzünk átrakása egyik helyről a másikra.
3. **SIMA KIADÁS** - készpénzben kifizetett kiadás, amihez van számla, vagy
   legalább lesz (nincs rajta a „nem lesz számla” jelölés).
4. **FEKETE KIADÁS** - készpénzben kifizetett kiadás, amire rányomták, hogy
   SOHA nem lesz számlája (`Expense.nincs_szamla`).

    egyenleg = bevétel + átvezetés - sima kiadás - fekete kiadás

Minden összeg BRUTTÓ: egy doboz pénz nem tud nettó lenni.

KEZDŐNAP: 2026.01.01. Az ennél régebbi tételeket úgy kezeljük, mintha nem
léteznének. A dátum nélküli sor megmarad - az nem "régebbi", csak még nincs
kitöltve, és eltüntetve senki nem pótolná.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.finance import Expense, KpForgalom, Revenue
from app.models.project_code import ProjectCode  # noqa: F401  (a selectinload-hoz)
from app.services import attachments, elszamolas
from app.services import fizetesi_mod as fizetesi_mod_szolg
from app.services.hu_szoveg import ekezet_nelkul

#: A KP forgalom sor iránya. A Notionben szabad szöveg ("bevetel"/"kiadas"),
#: ezért előtag szerint nézzük.
_KIADAS_ELOTAG = "kiad"

#: A házipénztár kezdőnapja - ami ennél régebbi, az nem létezik (lásd fent).
KP_KEZDET = date(2026, 1, 1)

#: A tétel FAJTÁJA - a négy közül (lásd a modul leírását).
BEVETEL = "bevetel"
ATVEZETES = "atvezetes"
SIMA_KIADAS = "kiadas"
FEKETE_KIADAS = "fekete_kiadas"


def kp_ervenyes_sql():
    """A kezdőnap óta (vagy dátum nélkül) felvett KP forgalom sorok szűrője -
    MINDEN KP forgalom lekérdezés ezen megy át, hogy a régi sorok sehol ne
    bukkanjanak fel."""
    return or_(KpForgalom.kiadas_datuma.is_(None), KpForgalom.kiadas_datuma >= KP_KEZDET)


def _kezdonap_ota_sql(oszlop):
    return or_(oszlop.is_(None), oszlop >= KP_KEZDET)


@dataclass
class KasszaSor:
    """Egy készpénz-mozgás. Vagy `be`, vagy `ki` - a másik nulla."""

    #: A FORRÁS rekord azonosítója - a `forras` mezővel együtt azonosít.
    id: int
    #: bevetel (Revenue) | kiadas (Expense) | kp_forgalom (átvezetés)
    forras: str
    #: bevetel | atvezetes | kiadas | fekete_kiadas - lásd fent.
    tipus: str
    datum: date | None
    megnevezes: str
    projektkod: str | None = None
    be: float = 0.0
    ki: float = 0.0
    #: Van-e feltöltött számla (csak kiadásnál/bevételnél értelmes).
    van_szamla: bool = False
    #: A házipénztár egyenlege EZ UTÁN a sor után - időrendben számolva.
    egyenleg: float = 0.0
    #: Hova visz a sor a felületen.
    href: str | None = None
    #: Feltöltött bizonylat(ok) - az átvezetés (KP forgalom) sorain.
    csatolmanyok: list[Any] = field(default_factory=list)
    #: A projektkód NYERS azonosítója (a szerkesztéshez).
    project_code_id: int | None = None
    #: Devizás felvezetés nyoma - csak átvezetésnél (lásd services/penznem.py).
    penznem: str | None = None
    arfolyam: float | None = None
    eredeti_penznem: str | None = None
    eredeti_osszeg: float | None = None

    @property
    def atvezetes(self) -> bool:
        return self.tipus == ATVEZETES


@dataclass
class Osszesites:
    """Egy időszak házipénztár-képe - a négy fajta, amiből minden kijön."""

    bevetel: float = 0.0
    bevetel_db: int = 0
    #: ÁTVEZETÉS: a bankszámla és a házipénztár közti mozgás (ATM-felvétel;
    #: ha valaha készpénzt tennénk vissza a bankba, az `atvezetes_ki`).
    atvezetes_be: float = 0.0
    atvezetes_ki: float = 0.0
    atvezetes_db: int = 0
    sima_kiadas: float = 0.0
    sima_kiadas_db: int = 0
    fekete_kiadas: float = 0.0
    fekete_kiadas_db: int = 0

    @property
    def atvezetes(self) -> float:
        """Az átvezetés NETTÓ hatása a házipénztárra (be - ki)."""
        return self.atvezetes_be - self.atvezetes_ki

    @property
    def be(self) -> float:
        return self.bevetel + self.atvezetes_be

    @property
    def ki(self) -> float:
        return self.sima_kiadas + self.fekete_kiadas + self.atvezetes_ki

    @property
    def egyenleg(self) -> float:
        return self.be - self.ki

    def vedd_hozza(self, sor: KasszaSor) -> None:
        if sor.tipus == ATVEZETES:
            self.atvezetes_be += sor.be
            self.atvezetes_ki += sor.ki
            self.atvezetes_db += 1
        elif sor.tipus == BEVETEL:
            self.bevetel += sor.be
            self.bevetel_db += 1
        elif sor.tipus == FEKETE_KIADAS:
            self.fekete_kiadas += sor.ki
            self.fekete_kiadas_db += 1
        else:
            self.sima_kiadas += sor.ki
            self.sima_kiadas_db += 1


@dataclass
class KasszaKep:
    sorok: list[KasszaSor] = field(default_factory=list)
    #: Az EGÉSZ idő alatti kép (a kezdőnap óta), és külön az idei év.
    osszes: Osszesites = field(default_factory=Osszesites)
    idei: Osszesites = field(default_factory=Osszesites)

    @property
    def egyenleg(self) -> float:
        return self.osszes.egyenleg


#: KÉSZPÉNZFELVÉTEL a bankszámláról (ATM). A megnevezésből ismerjük fel.
KESZPENZFELVETEL_JELEK: tuple[str, ...] = ("kp felvetel", "keszpenzfelvetel", "keszpenz felvetel", "atm")

#: Egy "KP felvétel"-szerű sor, ami ÁDÁMOT említi (pl. "KP felvétel ATM-ből
#: (Ádám)") NEM a szokásos ATM-felvétel: ez Ádám SAJÁT kivétele a kasszából.
ADAM_SAJAT_FELVETEL_JEL = "adam"


def keszpenzfelvetel(megnevezes: Any) -> bool:
    """ATM-ből felvett pénz-e ez a sor (a megnevezése szerint) - az Ádámot
    említő sorok kivételek (pl. "KP felvétel ATM-ből (Ádám)")."""
    if not megnevezes:
        return False
    tiszta = ekezet_nelkul(str(megnevezes))
    if ADAM_SAJAT_FELVETEL_JEL in tiszta:
        return False
    return any(jel in tiszta for jel in KESZPENZFELVETEL_JELEK)


def kp_forgalom_iranya(f: KpForgalom) -> tuple[float, bool]:
    """(összeg forintban, kivétel-e) - egy átvezetés-sorból.

    A `kp_forgalmak` tábla sorai mind ÁTVEZETÉSEK (lásd a modul leírását): az
    alapeset az ATM-felvétel, ami a házipénztárba ÉRKEZIK. Kivétel (a
    házipénztárból a bankba tett pénz) csak akkor, ha a sor kifejezetten így
    van jelölve: negatív előjel vagy "kiad…" irány - és akkor sem, ha a
    megnevezése ATM-felvételre utal."""
    ertek = f.forintban
    osszeg = abs(float(ertek or 0))
    if keszpenzfelvetel(f.megnevezes):
        return osszeg, False
    if ertek is not None and ertek < 0:
        return osszeg, True
    return osszeg, (f.forgalom or "").strip().casefold().startswith(_KIADAS_ELOTAG)


def _atvezetesek(db: Session) -> list[KasszaSor]:
    sorok = db.scalars(
        select(KpForgalom).where(kp_ervenyes_sql()).options(selectinload(KpForgalom.project_code))
    ).all()
    csatolmanyok = attachments.list_for_many(db, "kpForgalom", [f.id for f in sorok])
    ki: list[KasszaSor] = []
    for f in sorok:
        osszeg, kivetel = kp_forgalom_iranya(f)
        pk = f.project_code
        ki.append(
            KasszaSor(
                id=f.id,
                forras="kp_forgalom",
                tipus=ATVEZETES,
                datum=f.kiadas_datuma,
                megnevezes=f.megnevezes or "Átvezetés (ATM-felvétel)",
                projektkod=pk.projektkod if pk else None,
                be=0.0 if kivetel else osszeg,
                ki=osszeg if kivetel else 0.0,
                csatolmanyok=csatolmanyok.get(f.id, []),
                project_code_id=f.project_code_id,
                penznem=f.penznem,
                arfolyam=f.arfolyam,
                eredeti_penznem=f.eredeti_penznem,
                eredeti_osszeg=f.eredeti_osszeg,
            )
        )
    return ki


def _bevetelek(db: Session) -> list[KasszaSor]:
    """A készpénzes projektkód-kifizetések. Csak a MEGTÖRTÉNT (fizetési
    dátummal bíró) és az éves bevételbe számító sor - a "nem ezen az úton jött"
    jelölésű nem pénz, ami a dobozba került (lásd services/elszamolas.py)."""
    sorok = db.scalars(
        select(Revenue)
        .where(
            fizetesi_mod_szolg.keszpenz_sql(Revenue.fizetes_modja),
            Revenue.fizetes_datuma.is_not(None),
            Revenue.fizetes_datuma >= KP_KEZDET,
            elszamolas.bevetel_beleszamit_sql(Revenue),
        )
        .options(selectinload(Revenue.project_code))
    ).all()
    szamlas = _szamlas_ids(db, "revenue")
    return [
        KasszaSor(
            id=r.id,
            forras="bevetel",
            tipus=BEVETEL,
            datum=r.fizetes_datuma,
            megnevezes=r.nev or (f"{r.project_code.projektkod} kifizetése" if r.project_code else "Készpénzes bevétel"),
            projektkod=r.project_code.projektkod if r.project_code else None,
            be=elszamolas.brutto_osszeg(r),
            van_szamla=r.id in szamlas,
            href=f"/projektek/project-kodok/{r.project_code_id}" if r.project_code_id else None,
            project_code_id=r.project_code_id,
        )
        for r in sorok
    ]


def _kiadasok(db: Session) -> list[KasszaSor]:
    """A készpénzben KIFIZETETT kiadások - sima vagy fekete a „nem lesz
    számla” jelölés szerint. Az "összesítőbe nem számít" jelölés itt nem
    szűr: a pénz attól még kiment a dobozból."""
    sorok = db.scalars(
        select(Expense)
        .where(
            fizetesi_mod_szolg.keszpenz_sql(Expense.kifizetes_modja),
            Expense.kesz.is_(True),
            _kezdonap_ota_sql(Expense.fizetes_datuma),
        )
        .options(selectinload(Expense.project_code))
    ).all()
    szamlas = _szamlas_ids(db, "expense")
    return [
        KasszaSor(
            id=e.id,
            forras="kiadas",
            tipus=FEKETE_KIADAS if e.nincs_szamla else SIMA_KIADAS,
            datum=e.fizetes_datuma,
            megnevezes=e.megnevezes or "Készpénzes kiadás",
            projektkod=e.project_code.projektkod if e.project_code else None,
            ki=elszamolas.brutto_osszeg(e),
            van_szamla=e.id in szamlas or bool(e.szamla_pdf_urls),
            href=f"/penzugyek/kiadas/{e.id}",
            project_code_id=e.project_code_id,
        )
        for e in sorok
    ]


def _szamlas_ids(db: Session, entity_type: str) -> set[int]:
    from app.services import bizonylat

    return bizonylat._szamlas_ids(db, entity_type)


def kep(db: Session, ma: date | None = None) -> KasszaKep:
    """A teljes házipénztár-kép: minden mozgás időrendben + az összesítések."""
    ma = ma or date.today()
    sorok = _bevetelek(db) + _atvezetesek(db) + _kiadasok(db)

    # Időrendben (a dátum nélküli a végére): a futó egyenleg csak így értelmes.
    sorok.sort(key=lambda s: (s.datum is None, s.datum or date.min, s.forras, s.id))
    eredmeny = KasszaKep(sorok=sorok)
    fut = 0.0
    for s in sorok:
        fut += s.be - s.ki
        s.egyenleg = fut
        eredmeny.osszes.vedd_hozza(s)
        if s.datum is not None and s.datum.year == ma.year:
            eredmeny.idei.vedd_hozza(s)

    return eredmeny


def havi_bontas(kep_: KasszaKep, honapok: list[tuple[int, int]]) -> list[tuple[str, float, float, float]]:
    """(hónap, be, ki, a hónap VÉGI egyenleg) - a kártya oszlopdiagramjához.

    A nyitó egyenleg a megjelenített hónapok ELŐTTI mozgásokból jön: enélkül a
    legutóbbi 12 hónap úgy nézne ki, mintha nulláról kezdenénk."""
    be: dict[tuple[int, int], float] = {}
    ki: dict[tuple[int, int], float] = {}
    for s in kep_.sorok:
        if s.datum is None:
            continue
        kulcs = (s.datum.year, s.datum.month)
        be[kulcs] = be.get(kulcs, 0.0) + s.be
        ki[kulcs] = ki.get(kulcs, 0.0) + s.ki

    elso = min(honapok) if honapok else None
    fut = 0.0
    if elso is not None:
        fut = sum(o for k, o in be.items() if k < elso) - sum(o for k, o in ki.items() if k < elso)

    sorok = []
    for y, m in honapok:
        b = be.get((y, m), 0.0)
        k = ki.get((y, m), 0.0)
        fut += b - k
        sorok.append((f"{y:04d}-{m:02d}", b, k, fut))
    return sorok
