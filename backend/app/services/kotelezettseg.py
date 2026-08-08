"""Mikor esedékes egy kötelezettség, és mi a teendő vele.

Három kérdésre válaszol, és mindhárom ugyanabból a fordulóból következik:

1. MIKOR a következő forduló (`kovetkezo_esedekesseg`);
2. MELY időszakok esedékesek már, amikhez be kell írni a tényleges összeget és
   fel kell tölteni a számlát (`ensure_idoszakok`);
3. KI-nek és MIKOR szóljunk, hogy lejár (`ensure_feladatok`).

Ütemező nincs a rendszerben, ezért a 2. és a 3. IGÉNY SZERINT fut: aki
megnyitja a kötelezettségek oldalát vagy a dashboardot, azzal együtt "utoléri"
a lemaradást. Ez azért működik, mert mindkét művelet idempotens - ugyanarra a
fordulóra sosem keletkezik két időszak vagy két feladat.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.employee import Employee
from app.models.kotelezettseg import Kotelezettseg, KotelezettsegCiklus, KotelezettsegIdoszak
from app.models.task import Task
from app.services import notifications

#: A generált feladatok kategóriája - ez különbözteti meg őket a kézzel
#: felvettektől, és ezen keresztül idempotens az elkészítésük.
KATEGORIA = "Kötelezettség"

#: Meddig nézünk vissza időszakot generálni, ha a kötelezettségnek nincs
#: megadott kezdete. Enélkül egy évek óta futó előfizetés felvitelekor
#: azonnal több tucat üres hónap keletkezne, és elfedné az igazi teendőket.
VISSZAMENOLEG_HONAP = 12

#: Az oldal útvonala - az értesítés linkje mutat ide.
PAGE = "/kotelezettsegek"


def _nap_a_honapban(ev: int, honap: int, nap: int) -> date:
    """A hónap `nap`-adik napja, a hónap végéhez igazítva.

    A 31-i fordulójú előfizetés februárban 28-án (szökőévben 29-én) fordul: a
    szolgáltatók is így csinálják, és enélkül a dátum egyszerűen nem létezne."""
    return date(ev, honap, min(nap, calendar.monthrange(ev, honap)[1]))


def _kovetkezo_minta_szerint(k: Kotelezettseg, tol: date) -> date | None:
    """A minta (`fordulo_nap` / `fordulo_honap`) szerinti első forduló, ami
    `tol`-nál nem korábbi."""
    if k.fordulo_nap is None:
        return None
    if k.ciklus == KotelezettsegCiklus.HAVI:
        jelolt = _nap_a_honapban(tol.year, tol.month, k.fordulo_nap)
        if jelolt >= tol:
            return jelolt
        ev, honap = (tol.year + 1, 1) if tol.month == 12 else (tol.year, tol.month + 1)
        return _nap_a_honapban(ev, honap, k.fordulo_nap)
    if k.ciklus == KotelezettsegCiklus.EVES:
        if k.fordulo_honap is None:
            return None
        jelolt = _nap_a_honapban(tol.year, k.fordulo_honap, k.fordulo_nap)
        return jelolt if jelolt >= tol else _nap_a_honapban(tol.year + 1, k.fordulo_honap, k.fordulo_nap)
    return None


def kovetkezo_esedekesseg(k: Kotelezettseg, ma: date | None = None) -> date | None:
    """A következő forduló dátuma. None = nincs miből kiszámolni.

    A KONKRÉT dátum (`kovetkezo_fordulo`) erősebb a mintánál, amíg el nem
    múlt: egy négy évre előre kifizetett domain nem évente esedékes, hiába
    "éves" a ciklusa. Miután elmúlt, a minta viszi tovább - a határozott idejű
    (EGYSZERI) szerződés viszont nem újul meg magától, ott a múltbeli lejárat
    marad az utolsó szó."""
    ma = ma or date.today()
    if k.kovetkezo_fordulo is not None and (k.kovetkezo_fordulo >= ma or k.ciklus == KotelezettsegCiklus.EGYSZERI):
        return k.kovetkezo_fordulo
    return _kovetkezo_minta_szerint(k, ma)


def _elozo_esedekesseg(k: Kotelezettseg, tol: date) -> date | None:
    """A `tol` előtti (vagy azzal egyező) legutóbbi forduló - az időszakok
    visszafelé generálásához."""
    kovetkezo = kovetkezo_esedekesseg(k, tol)
    if kovetkezo is None:
        return None
    if kovetkezo <= tol:
        return kovetkezo
    if k.ciklus == KotelezettsegCiklus.HAVI:
        ev, honap = (kovetkezo.year - 1, 12) if kovetkezo.month == 1 else (kovetkezo.year, kovetkezo.month - 1)
        return _nap_a_honapban(ev, honap, k.fordulo_nap or kovetkezo.day)
    if k.ciklus == KotelezettsegCiklus.EVES:
        return _nap_a_honapban(kovetkezo.year - 1, kovetkezo.month, kovetkezo.day)
    return None


def esedekessegek(k: Kotelezettseg, ma: date | None = None) -> list[date]:
    """Mely fordulók vannak MÁR MÖGÖTTÜNK (a mai napot is beleértve), amikhez
    tehát összeget és számlát várunk.

    Jövőbeli fordulóra sosem készül időszak: azt még nem vonták le, nincs mit
    beírni hozzá. Ez fontos a több évre előre kifizetett tételeknél is (egy
    2029-es lejáratú domainnél a "előző forduló" számítás magától még mindig a
    jövőben járna) - ezért lépünk visszafelé, amíg a mai napig nem érünk.

    Meddig megyünk vissza:

    - ha van KEZDET, addig (de legfeljebb VISSZAMENOLEG_HONAP hónapig) - aki
      megadta, mikortól él a tétel, az a történetét is látni akarja;
    - ha nincs, CSAK a legutóbbi fordulóig. Egy most felvitt előfizetésnél a
      helyes válasz az, hogy a mostani ciklusra várunk összeget - nem az, hogy
      egy évnyi üres hónapot dobunk a felhasználó nyakába olyan terhelésekről,
      amiket akkor még nem itt vezetett."""
    ma = ma or date.today()

    # Ha KONKRÉT következő forduló van megadva, és az még nem jött el, akkor
    # nincs esedékes időszak - pont ezt jelenti a konkrét dátum. A több évre
    # előre kifizetett domainnél a minta szerinti "tavalyi forduló" sosem
    # létezett (egyszer fizettük ki előre), ezért nem szabad időszakot nyitni rá.
    if k.kovetkezo_fordulo is not None and k.kovetkezo_fordulo > ma:
        return []

    jelenlegi = _elozo_esedekesseg(k, ma)
    if jelenlegi is None or jelenlegi > ma:
        return []
    if k.kezdet is None:
        return [jelenlegi]

    hatar = max(k.kezdet, _honapokkal(ma, -VISSZAMENOLEG_HONAP))
    eredmeny: list[date] = []
    while jelenlegi is not None and jelenlegi >= hatar and len(eredmeny) < 60:
        eredmeny.append(jelenlegi)
        if k.ciklus == KotelezettsegCiklus.EGYSZERI:
            break
        elozo = _elozo_esedekesseg_konkret(k, jelenlegi)
        if elozo is None or elozo >= jelenlegi:
            break
        jelenlegi = elozo
    return sorted(eredmeny)


def _elozo_esedekesseg_konkret(k: Kotelezettseg, naptol: date) -> date | None:
    """A megadott forduló ELŐTTI forduló - egy ciklussal visszalépve."""
    if k.ciklus == KotelezettsegCiklus.HAVI:
        ev, honap = (naptol.year - 1, 12) if naptol.month == 1 else (naptol.year, naptol.month - 1)
        return _nap_a_honapban(ev, honap, k.fordulo_nap or naptol.day)
    if k.ciklus == KotelezettsegCiklus.EVES:
        return _nap_a_honapban(naptol.year - 1, naptol.month, naptol.day)
    return None


def _honapokkal(alap: date, delta: int) -> date:
    ossz = alap.month - 1 + delta
    ev = alap.year + ossz // 12
    honap = ossz % 12 + 1
    return _nap_a_honapban(ev, honap, alap.day)


def ensure_idoszakok(db: Session, ma: date | None = None) -> list[KotelezettsegIdoszak]:
    """Létrehozza a hiányzó (már esedékes) időszakokat, és visszaadja az újakat.

    Ettől "vár" a havi előfizetés minden hónapban egy összeget, az éves pedig
    évfordulónként egyet - anélkül, hogy bárkinek kézzel kellene hónapot
    nyitnia. Csak AKTÍV kötelezettségre fut: egy lemondott előfizetéstől nincs
    mit várni."""
    ma = ma or date.today()
    kotelezettsegek = db.scalars(
        select(Kotelezettseg).options(selectinload(Kotelezettseg.idoszakok)).where(Kotelezettseg.aktiv.is_(True))
    ).all()

    ujak: list[KotelezettsegIdoszak] = []
    for k in kotelezettsegek:
        megvan = {i.esedekesseg for i in k.idoszakok}
        for nap in esedekessegek(k, ma):
            if nap in megvan:
                continue
            idoszak = KotelezettsegIdoszak(
                kotelezettseg_id=k.id,
                esedekesseg=nap,
                # A várt ár és pénzneme az alapértelmezés, de az összeget
                # SZÁNDÉKOSAN üresen hagyjuk: a lényeg, hogy valaki beírja a
                # ténylegesen levont összeget, és egy előre kitöltött szám
                # pont ezt fedné el.
                penznem=k.ar_penznem or "HUF",
            )
            db.add(idoszak)
            ujak.append(idoszak)
    if ujak:
        db.commit()
    return ujak


def hatralevo_napok(k: Kotelezettseg, ma: date | None = None) -> int | None:
    ma = ma or date.today()
    kovetkezo = kovetkezo_esedekesseg(k, ma)
    return None if kovetkezo is None else (kovetkezo - ma).days


def allapot(k: Kotelezettseg, ma: date | None = None) -> str:
    """A kötelezettség állapota a felületnek: inaktiv | lejart | hamarosan |
    rendben | nincs_datum."""
    if not k.aktiv:
        return "inaktiv"
    napok = hatralevo_napok(k, ma)
    if napok is None:
        return "nincs_datum"
    if napok < 0:
        return "lejart"
    if napok <= (k.ertesites_napokkal or 0):
        return "hamarosan"
    return "rendben"


def _feladat_szovege(k: Kotelezettseg, esedekesseg: date) -> str:
    nev = k.nev if not k.csomag else f"{k.nev} – {k.csomag}"
    ige = "lejár" if k.ciklus == KotelezettsegCiklus.EGYSZERI else "fordul"
    return f"{nev} {ige}: {esedekesseg.strftime('%Y.%m.%d.')}"


def ensure_feladatok(db: Session, ma: date | None = None) -> list[Task]:
    """Feladatot (és a felelősnek értesítést) készít a közelgő fordulókról.

    Akkor születik, amikor a fordulóig hátralévő idő a kötelezettség saját
    figyelmeztetési idején belülre ér (`ertesites_napokkal`) - egy éves
    biztosításnál két héttel előbb tudni kell, hogy dönteni kell róla.

    Idempotens: az azonosítás a feladat SZÖVEGE (benne a forduló dátumával) és
    a kategória - ugyanarra a fordulóra sosem keletkezik két feladat, a
    következőre viszont igen. A Task-on nincs generikus rekord-hivatkozás
    (csak project_id), ezért a szöveg a kulcs; ezt tartja egyben a
    `_feladat_szovege`, ami az egyetlen hely, ahol ez a szöveg készül.

    A lejárt fordulóra is készül feladat: éppen az a baj, ha valami már lejárt
    és senki nem tud róla."""
    ma = ma or date.today()
    kotelezettsegek = db.scalars(select(Kotelezettseg).where(Kotelezettseg.aktiv.is_(True))).all()

    esedekes: list[tuple[Kotelezettseg, date]] = []
    for k in kotelezettsegek:
        kovetkezo = kovetkezo_esedekesseg(k, ma)
        if kovetkezo is None:
            continue
        if (kovetkezo - ma).days <= (k.ertesites_napokkal or 0):
            esedekes.append((k, kovetkezo))
    if not esedekes:
        return []

    szovegek = [_feladat_szovege(k, nap) for k, nap in esedekes]
    mar_van = set(
        db.scalars(select(Task.feladat).where(Task.kategoria == KATEGORIA, Task.feladat.in_(szovegek))).all()
    )

    ujak: list[Task] = []
    for (k, nap), szoveg in zip(esedekes, szovegek):
        if szoveg in mar_van:
            continue
        felelos = db.get(Employee, k.felelos_id) if k.felelos_id else None
        feladat = Task(
            feladat=szoveg,
            kategoria=KATEGORIA,
            hatarido=nap,
            leiras=(
                "Ellenőrizd, hogy megújul-e, és a fordulónál töltsd fel a számlát, "
                f"valamint írd be a ténylegesen levont összeget ({PAGE})."
            ),
            felelosok=[felelos] if felelos is not None else [],
        )
        db.add(feladat)
        ujak.append(feladat)
        if felelos is not None:
            notifications.create_notification(
                db,
                employee_id=felelos.id,
                kind="kotelezettseg",
                message=szoveg,
                link=PAGE,
            )

    if ujak:
        db.commit()
    return ujak


def ensure_mindent(db: Session, ma: date | None = None) -> None:
    """Az időszakok és a feladatok utolérése egy hívásban - ezt hívja a
    kötelezettségek oldala és a dashboard."""
    ensure_idoszakok(db, ma)
    ensure_feladatok(db, ma)


def hianyzo_teendo(idoszak: KotelezettsegIdoszak, van_szamla: bool) -> str | None:
    """Mi hiányzik még egy esedékes időszakhoz? None = kész.

    Két dolog kell hozzá, és mindkettő azért, hogy a könyvelés kész legyen: a
    TÉNYLEGESEN levont összeg és a számla. A sorrend szándékos - az összeg a
    fontosabb, mert az megy a költségekbe."""
    if idoszak.osszeg is None:
        return "Összeg nincs beírva"
    if not van_szamla:
        return "Számla hiányzik"
    return None


def _timedelta_nap(napok: int) -> timedelta:
    return timedelta(days=napok)
