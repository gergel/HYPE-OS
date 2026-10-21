"""A MEGRENDELŐI papírok átvétele a projektkódokból.

A HYPE ADMIN projektkódok Notion-táblában minden projekthez ott van, hogy
készült-e megrendelői szerződés és teljesítési igazolás - milyen névre, milyen
dátummal és összeggel -, és oda vannak feltöltve maguk a papírok is.

Ezt a ProjectCode import már áthozza, de LAPOS MEZŐKBE (`szerzodes_statusza`,
`tig_statusza`, `megrendelo_neve`, ...) és általános csatolmányokba. Ez a
lépés abból csinál valódi `MegrendeloiSzerzodes` / `MegrendeloiTig` rekordot,
hogy a régi papírok is megjelenjenek a gyűjtőoldalakon, és ne "hiányzó
papírként" álljanak örökre a teendők között.

MIÉRT NEM A ProjectCode IMPORTERÉBEN? Mert nem a Notionból olvas: a saját
adatbázisunkban már meglévő projektkódokból és csatolmányokból dolgozik.
Külön lépésként újrafuttatható anélkül, hogy az egész projektkód-táblát újra
le kellene kérni a Notiontól - és pontosan ugyanaz a kód fut, mint az
adatmigrációban, ami a MÁR importált adaton egyszer végigment (lásd
services/megrendeloi_papir_atvetel.py).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.notion_import.client import NotionClient
from app.notion_import.engine import ImportResult
from app.services import megrendeloi_papir_atvetel


def import_megrendeloi_papirok(client: NotionClient, db: Session) -> ImportResult:
    """MegrendeloiSzerzodes + MegrendeloiTig <- a már importált projektkódok.

    A `client` paraméter a katalógus egységes hívási formája miatt van itt -
    ez a lépés nem hív Notiont."""
    result = ImportResult(entity_type="MegrendeloiSzerzodes+MegrendeloiTig")
    try:
        merleg = megrendeloi_papir_atvetel.vedd_at_mindent(db)
        db.flush()
    except Exception as exc:  # noqa: BLE001 - a futás egyben van, egy hiba se vigye el a naplót
        result.errors.append(f"A megrendelői papírok átvétele elhasalt: {type(exc).__name__}: {exc}")
        return result

    result.created = merleg.szerzodes_letrejott + merleg.tig_letrejott
    result.updated = merleg.szerzodes_frissult + merleg.tig_frissult
    result.skipped = merleg.kihagyott_projektkod
    return result
