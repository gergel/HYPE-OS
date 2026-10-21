"""Egész szám magyar szöveges kiírása (pl. 350000 -> 'háromszázötven-ezer') - a
csatolt 'kulsos-eseti-szerzodes' program gdocs.py-jának 1:1 portja, az eseti
alvállalkozói szerződés PDF-jén a nettó összeg szövegesen kiírt változatához."""

from __future__ import annotations


def _szazas(x: int) -> str:
    return ["", "száz", "kettőszáz", "háromszáz", "négyszáz", "ötszáz", "hatszáz", "hétszáz", "nyolcszáz", "kilencszáz"][x]


def _tizes(x: int) -> str:
    return ["", "tizen", "huszon", "harminc", "negyven", "ötven", "hatvan", "hetven", "nyolcvan", "kilencven"][x]


def _tizes2(x: int) -> str:
    return ["", "tíz", "húsz", "harminc", "negyven", "ötven", "hatvan", "hetven", "nyolcvan", "kilencven"][x]


def _egyes(x: int) -> str:
    return ["", "egy", "kettő", "három", "négy", "öt", "hat", "hét", "nyolc", "kilenc"][x]


def szam_betukkel(szam: float) -> str:
    va = str(int(szam))
    if len(va) > 9:
        return "Túl hosszú a szám!"
    ki = ""
    i = 1
    elozo = 0
    while len(va) > 0:
        e = int(va[-1])
        if i == 7:
            ki = "millió-" + ki
        if i == 4:
            ki = "ezer-" + ki
        if i % 3 == 1:
            ki = _egyes(e) + ki
        if i % 3 == 2:
            if elozo == 0:
                ki = _tizes2(e) + ki
            else:
                ki = _tizes(e) + ki
        if i % 3 == 0:
            ki = _szazas(e) + ki
        i += 1
        elozo = e
        va = va[:-1]
    if int(szam) % 1000000 == 0:
        ki = ki[:-5]
    idx = ki.find("-ezer-")
    if idx > -1:
        ki = ki[: idx + 1] + ki[idx + 6 :]
    if ki and ki[-1] == "-":
        ki = ki[:-1]
    return ki
