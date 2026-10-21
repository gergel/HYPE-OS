"""A diszpó szöveges mezőinek ALAPÉRTELMEZETT sablonjai.

A felhasználó kérése: minden új diszpóban (projektben) előre ott legyenek a
kitöltendő vázak - a kontaktoknál a helyszíni/stáb kontakt sorok, a diszpó
szövegében az érkezés/indulás/dresscode/catering/menetrend váz, a briefben
az SD-kártyás emlékeztető. A sablon csak az ÜRES mezőbe kerül: ami már ki
van töltve (kézzel vagy Notion-importból), ahhoz nem nyúlunk.

Három helyen jön létre projekt, mindhárom ezt hívja:
- a felületi felvitel (routes/projects.py before_create),
- a naptár-szinkron (services/google_calendar.py),
- a projekt-másolás (services/project_actions.py)."""

from __future__ import annotations

from typing import Any

KONTAKTOK_SABLON = """Helyszíni kontakt:
-
Stáb kontaktok:
-
-"""

DISZPO_SZOVEG_SABLON = """Érkezés a stúdióba:
Indulás a stúdióból:
Érkezés a helyszínre:
Közlekedés:

Dresscode: szigorúan non-branding fekete, ne jelenjen meg Hype logó se ruhán, se eszközön

Catering: nem biztosított, így igény esetén készüljetek magatoknak kérlek szendviccsel//csokival//gyümölccsel

Timing/menetrend:"""

BRIEF_SABLON = """A napod végén azokat az SD kártyákat amiket használtál hozd fel a stúdióba és a Vágó2-be ragaszd le az egyik asztalra és ide írd rá, hogy mi a projekt kód, mikor voltál forgatni és milyen projekten.
Köszönjük szépen!"""

SABLONOK: dict[str, str] = {
    "kontaktok": KONTAKTOK_SABLON,
    "diszpo_szovege": DISZPO_SZOVEG_SABLON,
    "brief": BRIEF_SABLON,
}


def toltsd_ki_a_sablonokat(data: dict) -> dict:
    """Az üres sablon-mezők kitöltése egy LÉTREHOZÁSI adat-szótáron
    (routes/projects.py before_create)."""
    for mezo, sablon in SABLONOK.items():
        if not (data.get(mezo) or "").strip():
            data[mezo] = sablon
    return data


def toltsd_ki_a_sablonokat_objektumon(project: Any) -> None:
    """Ugyanez egy már megépített Project objektumon (naptár-szinkron,
    projekt-másolás)."""
    for mezo, sablon in SABLONOK.items():
        if not (getattr(project, mezo, None) or "").strip():
            setattr(project, mezo, sablon)


# ── A CATERING-MONDAT SZÁMA ─────────────────────────────────────────────────
# A felhasználó kérése: a sablon catering-mondata a diszpós stáb létszámához
# igazodjon - egy embernek egyes számban („készülj magadnak”), többnek
# többes számban („készüljetek magatoknak”). Csak ezt a két pontos
# szófordulatot cseréljük, a szöveg többi (akár kézzel átírt) részéhez nem
# nyúlunk; ha valaki a mondatot átfogalmazta, nincs mit cserélni.
CATERING_TOBBES = "készüljetek magatoknak kérlek"
CATERING_EGYES = "készülj magadnak kérlek"


def catering_a_letszamhoz(szoveg: str, letszam: int) -> str:
    """A catering-mondat egyes/többes száma a létszám szerint. Stáb nélkül
    (0 fő) nem változtat."""
    if letszam == 1:
        return szoveg.replace(CATERING_TOBBES, CATERING_EGYES)
    if letszam >= 2:
        return szoveg.replace(CATERING_EGYES, CATERING_TOBBES)
    return szoveg


def igazitsd_a_cateringet(project: Any) -> bool:
    """A projekt diszpó-szövegében a catering-mondat igazítása a diszpós stáb
    (project.crew - ők kapják a diszpót) létszámához. Igaz, ha változott."""
    szoveg = getattr(project, "diszpo_szovege", None)
    if not szoveg:
        return False
    uj = catering_a_letszamhoz(szoveg, len(getattr(project, "crew", None) or []))
    if uj == szoveg:
        return False
    project.diszpo_szovege = uj
    return True

