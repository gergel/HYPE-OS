"""A strukturált bejövő számla-piszkozat (POST /bejovo-szamlak/draft) bemeneti
érvényesítési szabályai.

Két szint van, és ez szándékos:

1. ITT (422-es válasz): ami nélkül a piszkozat értelmetlen vagy belsőleg
   ellentmondásos - hibás formátumú adószám, üres számlaszám, negatív összeg,
   egymást ki nem adó nettó/ÁFA/bruttó, a kiállításnál korábbi határidő.
2. A SZOLGÁLTATÁSBAN (services/szamla_draft.py, a piszkozat `validacio`
   mezője): ami a törzsadattal való összevetésből derül ki - ismeretlen
   partner, hiányzó keretszerződés vagy TIG, eltérő összeg. Ezek nem
   utasítják el a beküldést, hanem állapotot és előkészítési opciókat adnak."""

from __future__ import annotations

import re
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

#: Az összegek eltérésének tűréshatára (kerekítés) forintban.
OSSZEG_TURES = Decimal("1")

_PROJEKTKOD_KARAKTEREK = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _/.-]*$")
_VEZERLO = re.compile(r"[\x00-\x1f\x7f]")


def adoszam_szamjegyei(adoszam: str | None) -> str:
    return "".join(ch for ch in (adoszam or "") if ch.isdigit())


def adoszam_normalizalas(ertek: str) -> str:
    """Magyar adószám: 8 jegyű törzsszám, vagy 11 jegyű teljes adószám
    (xxxxxxxx-y-zz, ahol y az ÁFA-kód 1-5), vagy közösségi adószám (HU +
    8 jegy). Vissza: a kötőjeles kanonikus alak (8 jegynél maga a törzsszám)."""
    nyers = (ertek or "").strip().upper().replace(" ", "")
    if nyers.startswith("HU"):
        nyers = nyers[2:]
    if not re.fullmatch(r"[0-9-]+", nyers):
        raise ValueError("Az adószám csak számjegyeket és kötőjelet tartalmazhat (vagy HU + 8 jegy).")
    jegyek = adoszam_szamjegyei(nyers)
    if len(jegyek) == 8:
        return jegyek
    if len(jegyek) == 11:
        if jegyek[8] not in "12345":
            raise ValueError("Az adószám 9. jegye (ÁFA-kód) csak 1-5 lehet.")
        return f"{jegyek[:8]}-{jegyek[8]}-{jegyek[9:]}"
    raise ValueError("Az adószám 8 jegyű törzsszám vagy 11 jegyű teljes adószám (xxxxxxxx-y-zz) lehet.")


def _ket_tizedes(ertek: Decimal | None) -> Decimal | None:
    if ertek is None:
        return None
    return ertek.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class SzamlaDraftIn(BaseModel):
    """A feldolgozó (AI-kiolvasó, Lara vagy ember) által beküldött,
    strukturált számlaadat."""

    partner_adoszam: str = Field(..., description="A számla kibocsátójának adószáma")
    partner_nev: str = Field(..., min_length=2, max_length=300)
    szamlaszam: str = Field(..., min_length=1, max_length=100)
    netto: Decimal | None = None
    afa_osszeg: Decimal | None = None
    brutto: Decimal | None = None
    penznem: str = "HUF"
    fizetesi_hatarido: date | None = None
    kiallitas_datuma: date | None = None
    teljesites_datuma: date | None = None
    projektkod: str | None = Field(None, max_length=50)
    forgatas_datuma: date | None = Field(None, description="A számlán hivatkozott forgatási nap")
    #: Ki állította elő az adatot - ettől függ az audit-napló szereplője.
    kinyero: Literal["ai", "lara", "szabaly", "kezi"] = "ai"
    #: Mezőnkénti bizonyosság (0-1) a kinyerőtől - csak eltároljuk, döntést
    #: nem alapozunk rá.
    mezo_bizonyossag: dict[str, float] | None = None
    megjegyzes: str | None = Field(None, max_length=2000)

    @field_validator("partner_adoszam")
    @classmethod
    def _adoszam(cls, v: str) -> str:
        return adoszam_normalizalas(v)

    @field_validator("partner_nev", "szamlaszam")
    @classmethod
    def _szoveg(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("Nem lehet üres.")
        if _VEZERLO.search(v):
            raise ValueError("Vezérlőkaraktert nem tartalmazhat.")
        return v

    @field_validator("penznem")
    @classmethod
    def _penznem(cls, v: str) -> str:
        v = (v or "").strip().upper()
        if not re.fullmatch(r"[A-Z]{3}", v):
            raise ValueError("A pénznem háromjegyű ISO-kód (pl. HUF, EUR).")
        return v

    @field_validator("projektkod")
    @classmethod
    def _projektkod(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip().upper()
        if not v:
            return None
        if not _PROJEKTKOD_KARAKTEREK.fullmatch(v):
            raise ValueError("A projektkód csak betűt, számot, szóközt és - _ / . jelet tartalmazhat.")
        return v

    @field_validator("netto", "afa_osszeg", "brutto")
    @classmethod
    def _nemnegativ(cls, v: Decimal | None) -> Decimal | None:
        if v is None:
            return None
        if v < 0:
            raise ValueError(
                "Negatív összeg nem piszkozható ezen az úton (sztornó/módosító számlát az érkeztetőben kezelj)."
            )
        if v > Decimal("1000000000"):
            raise ValueError("Az összeg irreálisan nagy (1 milliárd felett).")
        return _ket_tizedes(v)

    @field_validator("mezo_bizonyossag")
    @classmethod
    def _bizonyossag(cls, v: dict[str, float] | None) -> dict[str, float] | None:
        if v is None:
            return None
        for kulcs, ertek in v.items():
            if not 0 <= ertek <= 1:
                raise ValueError(f"A(z) {kulcs} bizonyossága 0 és 1 közötti szám legyen.")
        return v

    @model_validator(mode="after")
    def _osszegek_es_datumok(self) -> "SzamlaDraftIn":
        megadott = [x for x in (self.netto, self.afa_osszeg, self.brutto) if x is not None]
        if len(megadott) < 2:
            raise ValueError("A nettó, ÁFA és bruttó összegből legalább kettőt meg kell adni.")
        if self.netto is None:
            self.netto = _ket_tizedes(self.brutto - self.afa_osszeg)
        elif self.afa_osszeg is None:
            self.afa_osszeg = _ket_tizedes(self.brutto - self.netto)
        elif self.brutto is None:
            self.brutto = _ket_tizedes(self.netto + self.afa_osszeg)
        if self.netto < 0 or self.afa_osszeg < 0:
            raise ValueError("A megadott összegekből negatív nettó vagy ÁFA adódik - ellenőrizd az értékeket.")
        if abs(self.netto + self.afa_osszeg - self.brutto) > OSSZEG_TURES:
            raise ValueError(
                f"Az összegek nem adják ki egymást: nettó {self.netto} + ÁFA {self.afa_osszeg} ≠ bruttó {self.brutto}."
            )
        if self.fizetesi_hatarido and self.kiallitas_datuma and self.fizetesi_hatarido < self.kiallitas_datuma:
            raise ValueError("A fizetési határidő nem lehet korábbi a kiállítás dátumánál.")
        if self.teljesites_datuma and self.kiallitas_datuma and (self.kiallitas_datuma - self.teljesites_datuma).days > 400:
            raise ValueError("A teljesítés több mint egy évvel a kiállítás előtt volt - ellenőrizd a dátumokat.")
        return self


class Megerosites(BaseModel):
    """Pénzügyi állapotváltozás explicit megerősítése.

    A `ellenorzo_kod` a piszkozat pénzügyi adatainak ujjlenyomata (lásd
    services/szamla_draft.ellenorzo_kod): ha a felhasználó által látott adat
    azóta megváltozott (más összeg, más cél), a kód nem egyezik, és a
    megerősítés nem érvényes."""

    megerositve: bool
    ellenorzo_kod: str = Field(..., min_length=8, max_length=64)
