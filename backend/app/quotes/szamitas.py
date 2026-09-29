"""Az árajánlat összegzése - tiszta függvények, egész forintban.

Sor összege = alkalom × mennyiség × egységár × (1 − sorkedvezmény%/100),
forintra kerekítve. A nettó végösszeg a NEM opcionális sorok összege mínusz
az ajánlat kedvezménye (százalék a részösszegből + fix összeg, legfeljebb a
részösszegig). Az ÁFA és a bruttó csak kijelzés. Havidíjas módban a havidíj
a végösszeg / hónapok száma."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable, Protocol


def _d(x) -> Decimal:
    return Decimal(str(x if x is not None else 0))


def kerekit(x: Decimal) -> int:
    return int(x.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def sor_osszeg(alkalom, mennyiseg, egysegar, sorkedvezmeny=0) -> int:
    return kerekit(_d(alkalom) * _d(mennyiseg) * _d(egysegar) * (1 - _d(sorkedvezmeny) / 100))


class SorLike(Protocol):
    occasions: object
    quantity: object
    unit_price: int
    line_discount_percent: object
    is_optional: bool


@dataclass(frozen=True)
class Osszesites:
    reszosszeg: int
    kedvezmeny: int
    netto: int
    afa: int
    brutto: int
    opcionalis: int
    havidij: int | None

    def dict(self) -> dict:
        return self.__dict__.copy()


def osszesit(
    sorok: Iterable[SorLike], *, kedvezmeny_szazalek=0, kedvezmeny_osszeg=0, afa_szazalek=27,
    arazas: str = "one_off", honapok: int = 12,
) -> Osszesites:
    resz = opcio = 0
    for s in sorok:
        o = sor_osszeg(s.occasions, s.quantity, s.unit_price, s.line_discount_percent)
        if s.is_optional:
            opcio += o
        else:
            resz += o
    kedv = kerekit(_d(resz) * _d(kedvezmeny_szazalek) / 100) + int(kedvezmeny_osszeg or 0)
    kedv = max(0, min(kedv, resz))
    netto = resz - kedv
    afa = kerekit(_d(netto) * _d(afa_szazalek) / 100)
    havidij = kerekit(_d(netto) / honapok) if arazas == "monthly" and honapok and honapok > 0 else None
    return Osszesites(resz, kedv, netto, afa, netto + afa, opcio, havidij)
