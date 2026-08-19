"""Deviza összegek felvezetése - EGY szabály, egy helyen.

A könyvelésünk forintban vezet. Egy euróban vagy dollárban kiállított számla
attól még létezik: a bolti valóság az, hogy a papíron EUR van, a bankban meg
forint, és a kettő között egy adott napi árfolyam áll.

A rendszer ezt úgy oldja meg, hogy **a tárolt összeg MINDIG forint**:

- amit a felhasználó beír, az a beállított pénznemben értendő;
- ha az nem forint, KÖTELEZŐ az árfolyam - enélkül a beírt szám nem is
  értelmezhető: a "1500" lehet másfél ezer forint és hatszázezer is;
- a szerver átszámolja, és a `netto`/`brutto` mezőbe már a forint kerül.

Az EREDETI adat (pénznem, összeg, árfolyam) külön mezőkben megmarad. Ez nem
nosztalgia: fél év múlva egy 592 500 Ft-os sor mögött senki nem tudná, hogy az
1 500 EUR volt 395-ös árfolyamon - márpedig a számlán ez áll, és a könyvelés
ezt kéri számon.

Miért nem a meglévő `penznem` mezőben marad az "EUR"? Mert az azt mondaná, hogy
a sor összege euró - és minden összesítő (éves kiadás, projekt-profit,
autó-költség) vagy hamisan adna hozzá 1500-at a forintokhoz, vagy - ahogy az
autók oldala tette - némán KIHAGYNÁ a nem forintos sorokat. Egy összeg egy
pénznemben van, és nálunk az a forint.
"""

from __future__ import annotations

from typing import Any

#: Amiben számlát szoktunk kapni/kiállítani. Bővíthető - a szabály nem függ
#: attól, hány pénznem van benne.
PENZNEMEK: tuple[str, ...] = ("HUF", "EUR", "USD")

FORINT = "HUF"


class PenznemHiba(ValueError):
    """A felület ezt az üzenetet mutatja - ezért magyarul, teljes mondatban."""


def normalizald(penznem: Any) -> str:
    """Üres/ismeretlen -> forint, egyébként nagybetűs kód."""
    if penznem is None:
        return FORINT
    szoveg = str(penznem).strip().upper()
    return szoveg or FORINT


def devizas(penznem: Any) -> bool:
    return normalizald(penznem) != FORINT


def forintra(osszeg: Any, arfolyam: Any) -> float | None:
    """Az összeg forintban, a megadott árfolyamon. Kerekítve, mert innentől ez
    a szám megy az összesítőkbe - egy le nem kerekített tizedtört forint csak
    zajt visz a végösszegekbe."""
    if osszeg is None:
        return None
    return round(float(osszeg) * float(arfolyam), 2)


def ellenorizd(penznem: Any, arfolyam: Any) -> None:
    """Értelmes-e így felvezetni? Devizánál árfolyam nélkül NEM."""
    kod = normalizald(penznem)
    if kod not in PENZNEMEK:
        raise PenznemHiba(
            f"Ismeretlen pénznem: {kod}. Választható: {', '.join(PENZNEMEK)}."
        )
    if kod == FORINT:
        return
    if arfolyam is None or float(arfolyam) <= 0:
        raise PenznemHiba(
            f"{kod} összeghez add meg az árfolyamot is (hány forint egy {kod}) - "
            "enélkül nem tudjuk, mennyi a tétel forintban."
        )


def valtsd_at(adat: dict, *, mezok: tuple[str, ...] = ("netto", "brutto")) -> dict:
    """A beküldött adat átváltása forintra, HELYBEN.

    Amit kap: a create/update payload dictje, ahogy a felület küldi - a
    `netto`/`brutto` a `penznem` szerinti pénznemben. Amit hagy maga után: a
    `netto`/`brutto` forintban, a `penznem` "HUF"-on, és az eredeti adat az
    `eredeti_*` mezőkben.

    CSAK AKKOR nyúl hozzá, ha a kérés maga hozza a `penznem` mezőt - vagyis a
    felhasználó most mondja meg, milyen pénznemben érti a beírt összeget. Egy
    utólagos, önmagában álló összeg-javítás (pl. a listában a nettó cella
    átírása) tehát forintos javítás marad, és nem írja felül azt, HOGYAN
    vezették fel a tételt. Az `eredeti_*` mezők a felvezetés tényét őrzik, nem
    a mindenkori összeget - ezért a felület is múlt időben írja ki őket."""
    if "penznem" not in adat:
        return adat
    penznem = normalizald(adat.get("penznem"))
    arfolyam = adat.get("arfolyam")
    ellenorizd(penznem, arfolyam)
    if penznem == FORINT:
        # Forintra visszaállítva az eredeti-adat is elveszti az értelmét:
        # különben egy korábbi EUR-os felvezetés nyoma ott ragadna a soron, és
        # a felület azt írná ki alá, hogy "1 500 EUR × 395".
        adat["penznem"] = FORINT
        adat["eredeti_penznem"] = None
        adat["arfolyam"] = None
        for mezo in mezok:
            adat[f"eredeti_{mezo}"] = None
        return adat

    adat["eredeti_penznem"] = penznem
    for mezo in mezok:
        eredeti = adat.get(mezo)
        adat[f"eredeti_{mezo}"] = eredeti
        adat[mezo] = forintra(eredeti, arfolyam)
    # A SOR pénzneme forint marad: az összege innentől forint.
    adat["penznem"] = FORINT
    return adat


#: A pénznem MAGYAR NEVE - a papírokra kiírt "összeg betűvel" után ez kerül
#: ("ötezer euró"). Ismeretlen kódnál marad a kód maga: jobb egy szokatlan
#: rövidítés, mint egy rossz szó.
PENZNEM_SZOVEG: dict[str, str] = {
    "HUF": "forint",
    "EUR": "euró",
    "USD": "dollár",
}


def szoveggel(penznem: Any) -> str:
    kod = normalizald(penznem)
    return PENZNEM_SZOVEG.get(kod, kod)
