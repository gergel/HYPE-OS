"""A Google-táblázatban vezetett előfizetés-lista beolvasása.

A táblázat emberek által, szabad szöveggel készült - ugyanaz az adat tucatnyi
alakban szerepel benne ("Minden hónap 7.-e" / "minden hónap 7", "401,64 € / év"
/ "29,99USD/hó" / "790ft/hó"). Ez a modul az a hely, ahol ezt a szabadságot
gépi mezőkké fordítjuk; a többi kód már csak tiszta dátumot, számot és
pénznemet lát.

Amit szándékosan NEM csinál: nem talál ki adatot. Amit nem tud értelmezni, azt
az eredeti szövegével együtt a megjegyzésbe teszi, és a sor bekerül - egy
elveszett sor rosszabb, mint egy hiányos.

A beolvasás a táblázat CSV-exportját kéri le (`/export?format=csv`), tehát a
megosztásnak legalább "a link birtokában megtekintheti" szintűnek kell lennie.
"""

from __future__ import annotations

import csv
import io
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date

import httpx

HONAP_NEVEK = {
    "januar": 1, "februar": 2, "marcius": 3, "aprilis": 4, "majus": 5, "junius": 6,
    "julius": 7, "augusztus": 8, "szeptember": 9, "oktober": 10, "november": 11, "december": 12,
}

#: Az összegző sor nem előfizetés - a táblázat aljára írt szumma.
KIHAGYANDO_NEVEK = {"osszegzes", "osszesen", "sum", "total"}


def _ekezet_nelkul(szoveg: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", szoveg.lower()) if not unicodedata.combining(c))


def _tiszta(szoveg: str | None) -> str:
    """Sortörés és nem törő szóköz nélküli, összenyomott szöveg."""
    return re.sub(r"\s+", " ", (szoveg or "").replace("\xa0", " ")).strip()


# ─────────────────────────────────────────────────────────────────────────────
# Forduló
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class Fordulo:
    """Amit a "Forduló" oszlopból ki lehetett olvasni."""

    nap: int | None = None
    honap: int | None = None
    #: Konkrét dátum, ha az oszlop évet is tartalmazott ("2029.06.17").
    datum: date | None = None


def parse_fordulo(szoveg: str | None) -> Fordulo | None:
    """A "Forduló" oszlop értelmezése. None = nem sikerült.

    Négy alakot ismer, ebben a sorrendben (a konkrét dátum a legerősebb):
    "2029.06.17", "2027. május 15.", "Minden hónap 7.-e", "Szeptember 03."."""
    nyers = _tiszta(szoveg)
    if not nyers:
        return None
    e = _ekezet_nelkul(nyers)

    m = re.match(r"^(\d{4})[.\s]+(\d{1,2})[.\s]+(\d{1,2})", e)
    if m:
        ev, honap, nap = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return _datum_fordulo(ev, honap, nap)

    m = re.match(r"^(\d{4})\.?\s*([a-z]+)\s*(\d{1,2})", e)
    if m and m.group(2) in HONAP_NEVEK:
        return _datum_fordulo(int(m.group(1)), HONAP_NEVEK[m.group(2)], int(m.group(3)))

    m = re.search(r"minden\s+ho?nap\D*(\d{1,2})", e)
    if m:
        return Fordulo(nap=int(m.group(1)))

    m = re.match(r"^([a-z]+)\s*(\d{1,2})", e)
    if m and m.group(1) in HONAP_NEVEK:
        return Fordulo(nap=int(m.group(2)), honap=HONAP_NEVEK[m.group(1)])
    return None


def _datum_fordulo(ev: int, honap: int, nap: int) -> Fordulo | None:
    try:
        d = date(ev, honap, nap)
    except ValueError:
        return None
    return Fordulo(nap=nap, honap=honap, datum=d)


# ─────────────────────────────────────────────────────────────────────────────
# Ár
# ─────────────────────────────────────────────────────────────────────────────

PENZNEM_JELEK: list[tuple[str, str]] = [
    ("eur", "EUR"), ("€", "EUR"),
    ("usd", "USD"), ("$", "USD"),
    ("huf", "HUF"), ("ft", "HUF"),
]


def parse_penznem(szoveg: str | None) -> str | None:
    e = _ekezet_nelkul(_tiszta(szoveg))
    for jel, kod in PENZNEM_JELEK:
        if jel in e:
            return kod
    return None


def parse_osszeg(szoveg: str | None) -> float | None:
    """Az első szám kiolvasása, magyar és angol tizedesjellel egyaránt.

    A nehézséget az adja, hogy a vessző és a pont is lehet tizedes- VAGY
    ezreselválasztó ugyanabban az oszlopban: "401,64 €" (tizedes) és
    "17.990 HUF" (ezres). A szabály, amit használunk: ha mindkét jel szerepel,
    az UTOLSÓ a tizedesjel; ha csak az egyik, akkor tizedesnek vesszük, ha
    pontosan két számjegy áll utána - háromnál ezres elválasztó."""
    nyers = _tiszta(szoveg).replace(" ", "")
    if not nyers:
        return None
    m = re.search(r"\d[\d.,]*", nyers)
    if not m:
        return None
    szam = m.group(0).rstrip(".,")
    if "," in szam and "." in szam:
        tizedes = max(szam.rfind(","), szam.rfind("."))
        egesz = re.sub(r"[.,]", "", szam[:tizedes])
        return float(f"{egesz}.{szam[tizedes + 1:]}")
    for jel in (",", "."):
        if jel in szam:
            elotte, _, utana = szam.rpartition(jel)
            if len(utana) == 2 and jel not in elotte:
                return float(f"{elotte.replace(jel, '')}.{utana}")
            return float(re.sub(r"[.,]", "", szam))
    return float(szam)


# ─────────────────────────────────────────────────────────────────────────────
# Sorok
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ImportSor:
    """Egy táblázatsor gépi alakban - ebből készül a Kotelezettseg."""

    nev: str
    csomag: str | None = None
    ciklus: str = "havi"
    fordulo: Fordulo | None = None
    osztaly: str | None = None
    felelos_nev: str | None = None
    aktiv: bool = True
    ar_osszeg: float | None = None
    ar_penznem: str = "HUF"
    huf_becsles_honap: float | None = None
    huf_becsles_ev: float | None = None
    szamla_forras: str | None = None
    kartya: str | None = None
    megjegyzes: str | None = None


def _oszlop(sor: dict[str, str], *nevek: str) -> str:
    """Oszlop keresése a fejléc apró eltéréseitől függetlenül (a valódi
    táblázatban pl. "Forduló " szóközzel a végén szerepel)."""
    kulcsok = {_ekezet_nelkul(_tiszta(k)): k for k in sor if k}
    for nev in nevek:
        kulcs = kulcsok.get(_ekezet_nelkul(nev))
        if kulcs is not None:
            return sor.get(kulcs) or ""
    return ""


def _ciklus(mod: str, fordulo: Fordulo | None) -> str:
    """Havi vagy éves - a szöveges "Előfizetés módja" oszlopból.

    Ha az oszlop üres, a fordulóból következtetünk: hónap nélküli nap = havi
    (a "minden hónap 7-e" alak), hónappal együtt = éves."""
    e = _ekezet_nelkul(mod)
    if "hav" in e:
        return "havi"
    if "ev" in e:
        return "eves"
    if fordulo is not None and fordulo.honap is not None:
        return "eves"
    return "havi"


def parse_sorok(csv_szoveg: str) -> list[ImportSor]:
    """A CSV feldolgozása. A név nélküli és az összegző sorokat kihagyja."""
    eredmeny: list[ImportSor] = []
    for sor in csv.DictReader(io.StringIO(csv_szoveg)):
        nev = _tiszta(_oszlop(sor, "Előfizetés", "Megnevezés", "Név"))
        if not nev or _ekezet_nelkul(nev) in KIHAGYANDO_NEVEK:
            continue

        fordulo = parse_fordulo(_oszlop(sor, "Forduló", "Fordulo"))
        fordulo_nyers = _tiszta(_oszlop(sor, "Forduló", "Fordulo"))
        ar_szoveg = _oszlop(sor, "Ára az utolsó fizetéskor", "Ár")
        ciklus_ar = _oszlop(sor, "Ár / év") if _ciklus(_oszlop(sor, "Előfizetés módja"), fordulo) == "eves" else _oszlop(sor, "Ár / hónap")

        megjegyzesek = [
            _tiszta(_oszlop(sor, "Megjegyzés")),
            _tiszta(_oszlop(sor, "MEGJEGYZÉS")),
        ]
        # Amit nem tudtunk értelmezni, azt megőrizzük - inkább legyen ott
        # szövegként, mint hogy elvesszen.
        if fordulo is None and fordulo_nyers:
            megjegyzesek.append(f"Forduló a táblázatban: {fordulo_nyers}")

        eredmeny.append(
            ImportSor(
                nev=nev,
                csomag=_tiszta(_oszlop(sor, "Csomag")) or None,
                ciklus=_ciklus(_oszlop(sor, "Előfizetés módja"), fordulo),
                fordulo=fordulo,
                osztaly=_tiszta(_oszlop(sor, "Osztály")) or None,
                felelos_nev=_tiszta(_oszlop(sor, "Felelős")) or None,
                aktiv="nem" not in _ekezet_nelkul(_oszlop(sor, "Aktivitás")),
                # Az ár elsősorban az "Ára az utolsó fizetéskor" oszlopból: az
                # a TÉNYLEG fizetett összeg. A számolt "Ár / hónap" és "Ár /
                # év" oszlopok a táblázatban helyenként ellentmondanak
                # egymásnak (az Adobe-nál pl. a havi ár tizenkétszerese nem
                # egyezik a beírt évessel), ezért csak tartaléknak használjuk.
                ar_osszeg=parse_osszeg(ar_szoveg) if _tiszta(ar_szoveg) else parse_osszeg(ciklus_ar),
                ar_penznem=(parse_penznem(ar_szoveg) or parse_penznem(ciklus_ar) or "HUF"),
                huf_becsles_honap=parse_osszeg(_oszlop(sor, "HUF kerekítés /hó")),
                huf_becsles_ev=parse_osszeg(_oszlop(sor, "HUF kerekítés /év")),
                szamla_forras=_tiszta(_oszlop(sor, "Számla email")) or None,
                kartya=_tiszta(_oszlop(sor, "Terhelt kártya")) or None,
                megjegyzes="\n".join(m for m in megjegyzesek if m) or None,
            )
        )
    return eredmeny


def csv_url(megosztott_url: str) -> str:
    """A megosztott táblázat-linkből a CSV-export URL-je.

    Azért fogadunk el sima megosztási linket, mert a felhasználó azt tudja
    kimásolni a böngészőből - az export-URL-t nem."""
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", megosztott_url or "")
    if not m:
        raise ValueError("Ez nem Google Táblázat link (nem található benne /spreadsheets/d/…).")
    azonosito = m.group(1)
    gid = re.search(r"[#&?]gid=(\d+)", megosztott_url or "")
    alap = f"https://docs.google.com/spreadsheets/d/{azonosito}/export?format=csv"
    return f"{alap}&gid={gid.group(1)}" if gid else alap


def letolt(megosztott_url: str, *, timeout: float = 30.0) -> str:
    """A táblázat CSV-tartalma. A megosztásnak nyilvánosnak (link birtokában
    megtekinthetőnek) kell lennie - enélkül a Google bejelentkező oldalt ad
    vissza, amit HTML-ként ismerünk fel."""
    url = csv_url(megosztott_url)
    valasz = httpx.get(url, timeout=timeout, follow_redirects=True)
    valasz.raise_for_status()
    tipus = valasz.headers.get("content-type", "")
    if "text/csv" not in tipus:
        raise ValueError(
            "A táblázat nem érhető el CSV-ként. Állítsd a megosztást "
            '"Bárki a link birtokában – Megtekintő" szintre, majd próbáld újra.'
        )
    return valasz.text
