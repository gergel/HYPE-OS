"""A KASSZA teljes képe - egy helyen, egy szabály szerint.

A készpénz két felületen jelenik meg: a Pénzügyek összesítő kártyáján (mennyi
van a dobozban) és a KP forgalom naplóban (miből jött össze). A kettő ugyanabból
a számításból dolgozik, mert két külön implementáció előbb-utóbb két külön
egyenleget adna - és a kasszánál pont az a kérdés, hogy egyezik-e a szám a
valósággal.

LEGÁLIS ÉS FEKETE. A készpénz-mozgásoknál nem csak az számít, mennyi mozdult,
hanem az is, van-e mögötte SZÁMLA (lásd services/bizonylat.py):

- a **számlás** kiadás elszámolható költség - ez a legális oldal;
- a **számla nélküli** kiadást nem lehet elszámolni: ez az, amit a cég
  szempontjából "feketének" hívunk;
- a **számla nélküli BEVÉTEL** viszont épp ezt fedezi: az a készpénz, ami
  számla nélkül jött be, számla nélkül is költhető el.

Ebből jön a **fekete egyenleg**:

    fekete egyenleg = számla nélküli KIADÁS - számla nélküli BEVÉTEL

Ha ez pozitív, annyi számla nélküli költés nincs lefedve. A KASSZA egyenlege
ettől független, az a teljes forgalom különbsége:

    kassza = MINDEN készpénzes bevétel - MINDEN készpénzes kiadás

MI SZÁMÍT BELE? Csak a MEGTÖRTÉNT mozgás (van fizetési dátum) - egy jövő heti
készpénzes kiadás még nem hiányzik a dobozból -, BRUTTÓBAN (egy doboz pénz nem
tud nettó lenni), és a "nem számít bele" jelölésű sorok nélkül: ami a Pénzügyek
szerint nem történt meg, az a kasszát sem mozgatta.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.finance import Expense, KpForgalom, Revenue
from app.models.project_code import ProjectCode  # noqa: F401  (a selectinload-hoz)
from app.services import bizonylat, elszamolas, fizetesi_mod
from app.services.hu_szoveg import ekezet_nelkul

#: A KP forgalom sor iránya. A Notionben szabad szöveg ("bevetel"/"kiadas"),
#: ezért előtag szerint nézzük.
_KIADAS_ELOTAG = "kiad"


@dataclass
class KasszaSor:
    """Egy készpénz-mozgás. Vagy `be`, vagy `ki` - a másik nulla."""

    id: int
    #: kiadas | bevetel | kp_forgalom
    forras: str
    datum: date | None
    megnevezes: str
    projektkod: str | None = None
    be: float = 0.0
    ki: float = 0.0
    #: Van-e mögötte számla. Ez dönti el, melyik oldalra kerül a legális/fekete
    #: bontásban (lásd a modul leírását).
    van_szamla: bool = False
    #: ÁTVEZETÉS: nem bevétel és nem költés, hanem a saját pénzünk mozgatása a
    #: bankszámla és a kassza között (ATM-felvétel). A kassza egyenlegébe
    #: beleszámít - a doboz tényleg ennyivel lett vastagabb -, de sem a legális,
    #: sem a fekete oldalra nem kerül: van róla banki kivonat, tehát nem
    #: "számla nélküli bevétel", és nem is költés.
    atvezetes: bool = False
    #: A kassza egyenlege EZ UTÁN a sor után - időrendben számolva.
    egyenleg: float = 0.0
    #: Hova visz a sor a felületen.
    href: str | None = None


@dataclass
class Osszesites:
    """Egy időszak készpénz-képe - a négy sarok, amiből minden más kijön."""

    be_szamlaval: float = 0.0
    be_szamla_nelkul: float = 0.0
    ki_szamlaval: float = 0.0
    ki_szamla_nelkul: float = 0.0
    be_szamlaval_db: int = 0
    be_szamla_nelkul_db: int = 0
    ki_szamlaval_db: int = 0
    ki_szamla_nelkul_db: int = 0
    #: ÁTVEZETÉS: a bankszámla és a kassza közti mozgás (ATM-felvétel). A
    #: `be`/`ki` végösszegbe BELESZÁMÍT - a dobozban tényleg ott a pénz -, de a
    #: legális/fekete bontásban külön áll: se nem bevétel, se nem költés.
    be_atvezetes: float = 0.0
    ki_atvezetes: float = 0.0
    be_atvezetes_db: int = 0
    ki_atvezetes_db: int = 0

    @property
    def be(self) -> float:
        return self.be_szamlaval + self.be_szamla_nelkul + self.be_atvezetes

    @property
    def ki(self) -> float:
        return self.ki_szamlaval + self.ki_szamla_nelkul + self.ki_atvezetes

    @property
    def egyenleg(self) -> float:
        return self.be - self.ki

    @property
    def fekete_egyenleg(self) -> float:
        """Amennyi számla nélküli költés NINCS lefedve számla nélküli
        bevétellel. Negatív érték: több a számla nélküli bevétel, mint a
        költés - az nem hiány, hanem tartalék."""
        return self.ki_szamla_nelkul - self.be_szamla_nelkul

    def vedd_hozza(self, sor: KasszaSor) -> None:
        if sor.atvezetes:
            # Se a legális, se a fekete oldalra nem kerül - de a kassza
            # egyenlegét mozgatja, ezért a be/ki végösszegben benne van.
            if sor.be:
                self.be_atvezetes += sor.be
                self.be_atvezetes_db += 1
            if sor.ki:
                self.ki_atvezetes += sor.ki
                self.ki_atvezetes_db += 1
            return
        if sor.be:
            if sor.van_szamla:
                self.be_szamlaval += sor.be
                self.be_szamlaval_db += 1
            else:
                self.be_szamla_nelkul += sor.be
                self.be_szamla_nelkul_db += 1
        if sor.ki:
            if sor.van_szamla:
                self.ki_szamlaval += sor.ki
                self.ki_szamlaval_db += 1
            else:
                self.ki_szamla_nelkul += sor.ki
                self.ki_szamla_nelkul_db += 1


@dataclass
class KasszaKep:
    sorok: list[KasszaSor] = field(default_factory=list)
    #: Az EGÉSZ idő alatti kép, és külön az idei év.
    osszes: Osszesites = field(default_factory=Osszesites)
    idei: Osszesites = field(default_factory=Osszesites)
    #: Hány olyan KIFIZETETT tétel van, amin nincs megjelölve a fizetési mód.
    #: Amíg ez nem nulla, az egyenleg csak közelítés.
    jeloletlen_kiadas: int = 0
    jeloletlen_bevetel: int = 0
    #: Hány KP forgalom sor maradt ki, mert egy kiadáshoz kötődik (azt már a
    #: kiadás soraként számoltuk).
    kp_forgalom_kiadashoz_kotve: int = 0

    @property
    def egyenleg(self) -> float:
        return self.osszes.egyenleg


def _penz(sor) -> float:
    """A mozgatott összeg: BRUTTÓ, nettóra visszaesve.

    A régi, Notionből importált sorokon gyakran csak az egyik van meg - a
    dobozból viszont ÁFÁ-stól ment ki a pénz, tehát a bruttó az igaz szám."""
    brutto = getattr(sor, "brutto", None)
    return float(brutto if brutto is not None else (getattr(sor, "netto", None) or 0))


#: KÉSZPÉNZFELVÉTEL a bankszámláról (ATM). A megnevezésből ismerjük fel.
KESZPENZFELVETEL_JELEK: tuple[str, ...] = ("kp felvetel", "keszpenzfelvetel", "keszpenz felvetel", "atm")

#: Egy "KP felvétel"-szerű sor, ami ÁDÁMOT említi (pl. "KP felvétel ATM-ből
#: (Ádám)") NEM a szokásos ATM-felvétel: ez Ádám SAJÁT kivétele a kasszából -
#: tehát valódi KIADÁS, nem a bankszámla és a kassza közti önmagunknak-
#: átvezetés, mint a sima "KP felvétel". Ezért ELŐBB ezt nézzük, és ha illik,
#: a sor MÁR NEM esik bele az általános "kp felvetel" mintába (lásd
#: keszpenzfelvetel lent).
ADAM_SAJAT_FELVETEL_JEL = "adam"


def keszpenzfelvetel(megnevezes: Any) -> bool:
    """ATM-ből felvett pénz-e ez a sor (a megnevezése szerint) - az Ádámot
    említő sorok kivételek: azok Ádám saját, valódi kiadása, nem bank->kassza
    átvezetés (pl. "KP felvétel ATM-ből (Ádám)")."""
    if not megnevezes:
        return False
    tiszta = ekezet_nelkul(str(megnevezes))
    if ADAM_SAJAT_FELVETEL_JEL in tiszta:
        return False
    return any(jel in tiszta for jel in KESZPENZFELVETEL_JELEK)


def kp_forgalom_iranya(f: KpForgalom) -> tuple[float, bool]:
    """(összeg forintban, kiadás-e) - egy KP forgalom sorból.

    A szabály ebben a sorrendben:

    1. **KÉSZPÉNZFELVÉTEL (ATM) → BEVÉTEL.** Ez erősebb az előjelnél, mert a
       kettő két különböző dobozról beszél: az ATM-ből felvett pénz a
       BANKSZÁMLÁRÓL megy ki (a Notion formulája ezért negatív), de a KASSZÁBA
       ÉRKEZIK - itt pedig a kassza a téma. Ez a néhány sor a legnagyobb
       tételek közt van (több százezres felvételek), tehát rossz irányban
       kétszeres hibát okozna az egyenlegben.
    2. **Az ELŐJEL**: a Notion "Forintban" formulája negatív a kiadásokra
       (lásd models/finance.KpForgalom.forintban). Ez azért kell, mert az
       "Összeg" oszlop előjel nélküli - abból nem derül ki, hogy egy 600 000
       Ft-os sor kivétel volt-e a kasszából vagy betétel.
    3. Ahol a formula-mező nem jött át, a **"Forgalom"** szöveges mező dönt -
       ide esnek a kézzel javított sorok is (lásd
       routes/finance._kp_forgalom_kezi_javitas).
    4. Ha egyik sincs: BEVÉTEL - a tábla erre való, a kiadásoknak amúgy is
       saját táblájuk van."""
    ertek = f.forintban
    osszeg = abs(float(ertek or 0))
    if keszpenzfelvetel(f.megnevezes):
        return osszeg, False
    if ertek is not None and ertek < 0:
        return osszeg, True
    return osszeg, (f.forgalom or "").strip().casefold().startswith(_KIADAS_ELOTAG)


def kep(db: Session, ma: date | None = None) -> KasszaKep:
    """A teljes készpénz-kép: minden mozgás időrendben + az összesítések."""
    ma = ma or date.today()
    szamlas_kiadasok = bizonylat.szamlas_kiadas_ids(db)
    szamlas_bevetelek = bizonylat.szamlas_bevetel_ids(db)
    sorok: list[KasszaSor] = []

    bevetelek = db.scalars(
        select(Revenue)
        .options(selectinload(Revenue.project_code))
        .where(
            Revenue.fizetes_datuma.is_not(None),
            fizetesi_mod.keszpenz_sql(Revenue.fizetes_modja),
            elszamolas.bevetel_beleszamit_sql(Revenue),
        )
    ).all()
    for b in bevetelek:
        pk = b.project_code
        sorok.append(
            KasszaSor(
                id=b.id,
                forras="bevetel",
                datum=b.fizetes_datuma,
                megnevezes=b.nev or (pk.project_nev if pk else None) or "Bevétel",
                projektkod=pk.projektkod if pk else None,
                be=_penz(b),
                van_szamla=bizonylat.van_szamla_bevetel(b, szamlas_bevetelek),
                href=f"/projektek/project-kodok/{b.project_code_id}" if b.project_code_id else None,
            )
        )

    kiadasok = db.scalars(
        select(Expense)
        .options(selectinload(Expense.project_code))
        .where(
            Expense.fizetes_datuma.is_not(None),
            fizetesi_mod.keszpenz_sql(Expense.kifizetes_modja),
            Expense.hozzaadas_a_kiadasokhoz.is_not(False),
        )
    ).all()
    for k in kiadasok:
        pk = k.project_code
        sorok.append(
            KasszaSor(
                id=k.id,
                forras="kiadas",
                datum=k.fizetes_datuma,
                megnevezes=k.megnevezes,
                projektkod=pk.projektkod if pk else None,
                ki=_penz(k),
                van_szamla=bizonylat.van_szamla(k, szamlas_kiadasok),
                href="/penzugyek",
            )
        )

    # A Notionből örökölt "KP FORGALOM" tábla: ezek is valódi készpénz-mozgások,
    # döntően SZÁMLA NÉLKÜLI BEVÉTELEK - épp az a pénz, amiből a számla nélküli
    # költés fedezve van.
    #
    # Ami egy kiadáshoz kötődik (`expense_id`), az KIMARAD: ugyanaz a
    # pénzmozgás már szerepel a kiadás soraként, beszámítva kétszer vonódna le.
    kotve = 0
    for f in db.scalars(select(KpForgalom)).all():
        if f.expense_id is not None:
            kotve += 1
            continue
        osszeg, kiadas_e = kp_forgalom_iranya(f)
        sorok.append(
            KasszaSor(
                id=f.id,
                forras="kp_forgalom",
                datum=f.kiadas_datuma,
                megnevezes=f.megnevezes or "KP forgalom",
                be=0.0 if kiadas_e else osszeg,
                ki=osszeg if kiadas_e else 0.0,
                # Ezekhez nincs bizonylat - ezért is vannak külön nyilvántartva.
                van_szamla=False,
                # …az ATM-felvétel viszont ÁTVEZETÉS: van róla banki kivonat,
                # és nem is bevétel, csak a saját pénzünk került át a
                # bankszámláról a kasszába.
                atvezetes=keszpenzfelvetel(f.megnevezes),
            )
        )

    # Időrendben (a dátum nélküli a végére): a futó egyenleg csak így értelmes.
    sorok.sort(key=lambda s: (s.datum is None, s.datum or date.min, s.forras, s.id))
    eredmeny = KasszaKep(sorok=sorok, kp_forgalom_kiadashoz_kotve=kotve)
    fut = 0.0
    for s in sorok:
        fut += s.be - s.ki
        s.egyenleg = fut
        eredmeny.osszes.vedd_hozza(s)
        if s.datum is not None and s.datum.year == ma.year:
            eredmeny.idei.vedd_hozza(s)

    eredmeny.jeloletlen_kiadas = _jeloletlen(db, Expense, Expense.kifizetes_modja)
    eredmeny.jeloletlen_bevetel = _jeloletlen(db, Revenue, Revenue.fizetes_modja)
    return eredmeny


def _jeloletlen(db: Session, modell, mod_oszlop) -> int:
    """Hány KIFIZETETT tételen nincs megjelölve a fizetési mód.

    Ezek se ide, se oda nem számítanak - a kassza egyenlege addig csak
    közelítés, amíg van ilyen. Egy találgatott egyenleg rosszabb, mint egy
    hiányos: az utóbbin legalább látszik, mennyi hiányzik."""
    from sqlalchemy import func

    feltetel = (
        modell.hozzaadas_a_kiadasokhoz.is_not(False)
        if modell is Expense
        else elszamolas.bevetel_beleszamit_sql(modell)
    )
    return int(
        db.scalar(
            select(func.count())
            .select_from(modell)
            .where(
                modell.fizetes_datuma.is_not(None),
                func.coalesce(func.trim(mod_oszlop), "") == "",
                feltetel,
            )
        )
        or 0
    )


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
