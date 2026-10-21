"""Lara önellenőrzése — ADATKÖR és a válaszok beszámítása.

A felhasználó észrevétele: telik az idő, válaszolt is Lara kérdéseire, a
találati arány mégsem lett jobb — és az önellenőrzés mindig ugyanazokon az
adatokon fut, nem véletlen adagon vagy az összes elérhető adaton.

1. **Adatkör** (`Idoszak`): mit kér le az önellenőrzés (a jóslathoz „társként"
   használt rekordok köre) és mit ÉRTÉKEL (amit számol / amiről kérdez).
   * fő kör: a tanulás kezdete óta minden (mint eddig);
   * VIZSGA: a teljes múlt a társ-adat, de csak a tanulás kezdete ELŐTTI
     rekordokat értékeli — futásonként egy VÉLETLEN adagot (a mag minden
     futásnál más), vagy kézzel a teljes régi adatot.
2. **Válasz-kategóriák**: egy megválaszolt eltérés nem „hiba" többé:
   * „hibás rögzítés" → Lara javaslata volt a jó (`lara_helyes`);
   * „mindig így" / „magyarázat" → Lara megtanulta (`tanult`);
   * „egyszeri kivétel" és „nem releváns" → nem számít a pontosságba.
   A vak (szigorú) találati arány változatlanul megmarad mellette.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone

#: A vizsga alapértelmezett mintája a régi adatból (futásonként).
ALAP_MINTA_ARANY = 0.3


def _aware(d: datetime | None) -> datetime | None:
    if d is None:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


@dataclass(frozen=True)
class Idoszak:
    #: lekérés alsó határa (created_at >= tol); None = a teljes múlt
    tol: datetime | None
    #: ha meg van adva, csak az ennél KORÁBBI rekordokat értékeli (vizsga)
    ertekel_ig: datetime | None = None
    #: véletlen minta aránya az értékelt rekordokból (1.0 = mind)
    arany: float = 1.0
    #: a minta magja — futásonként más, így más adag kerül sorra
    mag: str = ""
    nev: str = "fo"

    def feltetelek(self, oszlop) -> list:
        return [oszlop >= self.tol] if self.tol is not None else []

    def ertekel(self, azon: str, ido: datetime | None) -> bool:
        if self.ertekel_ig is not None:
            i = _aware(ido)
            if i is None or i >= _aware(self.ertekel_ig):
                return False
        if self.arany >= 1:
            return True
        h = int(hashlib.sha256(f"{self.mag}|{azon}".encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
        return h < self.arany

    @property
    def vizsga(self) -> bool:
        return self.nev != "fo"


def idoszak(kezdet_vagy_idoszak) -> Idoszak:
    """Visszafelé kompatibilis: a régi hívók `kezdet` datetime-ot adnak."""
    if isinstance(kezdet_vagy_idoszak, Idoszak):
        return kezdet_vagy_idoszak
    return Idoszak(tol=kezdet_vagy_idoszak)


KATEGORIA = {
    "hibas": "lara_helyes",
    "mindig": "tanult",
    "magyarazat": "tanult",
    "kivetel": "kivetel",
    "elvet": "nem_relevans",
}


def beszamit(stat, valasz_tipus: str | None) -> None:
    """Egy megválaszolt eltérés beszámítása a statisztikába."""
    stat["megmagyarazva"] += 1
    stat[KATEGORIA.get(valasz_tipus or "", "tanult")] += 1


def terulet_osszegzes(c, nem_tudta: bool = True) -> dict:
    """Egy terület statisztikája: a vak találati arány (szigorú) ÉS a
    válaszok utáni pontosság (a kivétel / nem releváns kimarad; a „hibás
    rögzítés" Lara javára, a megtanult eset helyesnek számít)."""
    n = c["egyezik"] + c["elter"] + (c["nem_tudta"] if nem_tudta else 0)
    ki = c["kivetel"] + c["nem_relevans"]
    jo = c["egyezik"] + c["lara_helyes"] + c["tanult"]
    return {
        "ellenorzott": n,
        "egyezik": c["egyezik"],
        "elter": c["elter"],
        "nem_tudta": c["nem_tudta"] if nem_tudta else 0,
        "megmagyarazva": c["megmagyarazva"],
        "lara_helyes": c["lara_helyes"],
        "tanult": c["tanult"],
        "kivetel": ki,
        "nyitott_elteres": max(0, n - c["egyezik"] - c["megmagyarazva"]),
        "talalati_arany": round(c["egyezik"] / n, 3) if n else None,
        "pontossag": round(jo / (n - ki), 3) if n - ki > 0 else None,
    }
