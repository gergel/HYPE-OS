"""MENNYIÉRT csináltuk ezt a munkát - egy helyen, egy szabály szerint.

A vállalási ár három helyen szerepelhet: a megrendelői TIG-en, az eseti
szerződésen, és magán a projektkódon (a Notionból örökölt "Nettó összeg" +
"Plusz ÁFA" mezőkben). Ezt eddig két modul számolta ki külön-külön - a
számla-lépés és a projektkód bevétel-számítása -, ami előbb-utóbb elcsúszott
volna egymástól.

A SORREND maga is információ:

1. a **TIG** a legerősebb: az igazolja, mit végeztünk el ténylegesen, és arról
   megy ki a számla;
2. az **eseti szerződés**: amiben megállapodtunk;
3. a **projektkód** saját mezői: ide írja be az, aki tudja az összeget - és ez
   sokszor más ember, mint aki a papírokat készíti.

A bruttót nem tároljuk külön: a "+ÁFA" jelölőből számoljuk, ugyanúgy, ahogy a
papírok teszik. Egy külön tárolt bruttót senki nem tartana karban.
"""

from __future__ import annotations

from typing import Any

from app.services import penznem as penznem_szolg

AFA_SZORZO = 1.27


def plusz_afa_e(ertek: Any) -> bool:
    """A projektkód "Plusz ÁFA" mezője a Notionból SZÖVEG ("+ ÁFA", "+ÁFA",
    "nem"), a papírokon viszont igen/nem. Egy helyen döntjük el, mi számít
    ÁFÁ-snak, hogy a kétféle tárolás ne adjon kétféle bruttót."""
    if ertek is None:
        return False
    if isinstance(ertek, bool):
        return ertek
    return "afa" in str(ertek).casefold().replace("á", "a")


def brutto(netto: float | None, plusz_afa: Any) -> float | None:
    if netto is None:
        return None
    return round(float(netto) * AFA_SZORZO, 2) if plusz_afa_e(plusz_afa) else float(netto)


def szamlazott_osszeg(pk) -> tuple[float | None, float | None]:
    """(nettó, bruttó) - amennyiért ez a munka ment, a fenti sorrendben."""
    for papir in (*(pk.megrendeloi_tigek or []), *(pk.megrendeloi_szerzodesek or [])):
        if papir.netto_osszeg is not None:
            netto = float(papir.netto_osszeg)
            return netto, brutto(netto, papir.plusz_afa)
    for ertek in (pk.netto_osszeg, pk.szerzodes_netto_osszeg):
        if ertek is not None:
            netto = float(ertek)
            return netto, brutto(netto, pk.plusz_afa)
    return None, None


def forintban(pk) -> tuple[float | None, float | None]:
    """Ugyanaz, mint a szamlazott_osszeg(), csak FORINTBAN.

    A vállalási ár lehet euróban vagy dollárban (a projektkód `penznem` +
    `arfolyam` mezője) - a bevétel viszont forintban kerül a rendszerbe, mert a
    könyvelésünk abban vezet, és az összesítők egy pénznemet ismernek (lásd
    services/penznem.py). Ez a függvény adja azt a számot, ami ténylegesen a
    Pénzügyekbe kerül.

    Árfolyam nélküli devizás kód esetén None-t adunk vissza a szám helyett:
    egy devizás összeget árfolyam nélkül forintként kezelni nagyságrendi
    hiba lenne (1 500 EUR nem 1 500 Ft), és jobb, ha látszik a hiány."""
    netto, brutto_ertek = szamlazott_osszeg(pk)
    if not penznem_szolg.devizas(getattr(pk, "penznem", None)):
        return netto, brutto_ertek
    arfolyam = getattr(pk, "arfolyam", None)
    if arfolyam is None or float(arfolyam) <= 0:
        return None, None
    return (
        penznem_szolg.forintra(netto, arfolyam),
        penznem_szolg.forintra(brutto_ertek, arfolyam),
    )
