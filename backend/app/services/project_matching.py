"""Ugyanaz a forgatás - két forrásból.

Egy projekt kétfelől is bekerülhet a rendszerbe: a Google Naptárból (lásd
services/google_calendar.py) és a Notion "Main Database"-ből (lásd
notion_import/importers_wave2.import_projects). A két forrásnak MÁS az
azonosítója (naptáresemény-ID, illetve Notion page-ID), ezért magától egyik
sem tudja, hogy a másik ugyanazt a forgatást már behozta - így keletkeztek a
duplikált projektek.

Ez a modul adja a közös szabályt, hogy mikor beszélünk UGYANARRÓL a
forgatásról: azonos NÉV (kis/nagybetűtől és felesleges szóközöktől
függetlenül) és azonos KEZDŐ DÁTUM. Szándékosan szigorú: dátum nélkül nem
párosítunk, mert a puszta névegyezés (pl. "Interjú") két külön forgatás is
lehet.

A szabályt mindkét irány használja:
  - a naptár-szinkron a Notionból már bejött projekthez köti az eseményt,
  - a Notion import a naptárból már bejött projektet frissíti, nem csinál
    másodikat.
"""

from __future__ import annotations

import re
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.notion_import import NotionImportMap
from app.models.project import Project


def nev_kulcs(nev: str | None) -> str:
    """Összehasonlítható projektnév: kis/nagybetű, sorköz és többszörös szóköz
    nélkül. Enélkül a "Interjú  Kovács" és az "interjú Kovács" két külön
    projektnek látszana."""
    return re.sub(r"\s+", " ", (nev or "").strip()).casefold()


def _notionhoz_kotott_idk(db: Session) -> set[int]:
    """Azok a projektek, amiket már egy Notion-oldal hozott létre - ezekhez
    nem köthetünk MÁSIK Notion-oldalt (két Notion-sor két külön forgatás)."""
    return {
        entity_id
        for (entity_id,) in db.execute(
            select(NotionImportMap.entity_id).where(NotionImportMap.entity_type == "Project")
        )
    }


def azonos_forgatas(
    db: Session,
    nev: str | None,
    forgatas_datuma: date | None,
    *,
    kizart_id: int | None = None,
    csak_naptarbol: bool = False,
    csak_naptar_nelkul: bool = False,
    csak_notion_nelkul: bool = False,
) -> Project | None:
    """Ugyanaz a forgatás egy MÁSIK projekt-soron, vagy None.

    `csak_naptarbol`: csak a naptárból létrejött (naptáresemény-ID-vel bíró)
    sorok jöhetnek szóba. `csak_naptar_nelkul`: fordítva, csak azok, amikhez
    MÉG nincs naptáresemény kötve (a naptár-szinkron ilyet keres, hogy
    hozzákösse az eseményt). `csak_notion_nelkul`: csak azok, amiket még nem
    egy Notion-oldal hozott létre."""
    if forgatas_datuma is None:
        return None
    kulcs = nev_kulcs(nev)
    if not kulcs:
        return None

    jeloltek = list(
        db.scalars(select(Project).where(Project.forgatas_datuma == forgatas_datuma)).all()
    )
    if not jeloltek:
        return None
    notionos = _notionhoz_kotott_idk(db) if csak_notion_nelkul else set()

    talalatok = []
    for jelolt in jeloltek:
        if kizart_id is not None and jelolt.id == kizart_id:
            continue
        if nev_kulcs(jelolt.nev) != kulcs:
            continue
        if csak_naptarbol and not jelolt.google_calendar_event_id:
            continue
        if csak_naptar_nelkul and jelolt.google_calendar_event_id:
            continue
        if csak_notion_nelkul and jelolt.id in notionos:
            continue
        talalatok.append(jelolt)
    if not talalatok:
        return None
    # Ha több is illik, a naptárból jött az érdekesebb (azt kell magunkhoz
    # kötni), utána a legrégebbi - az a "fő" sor.
    talalatok.sort(key=lambda p: (0 if p.google_calendar_event_id else 1, p.id))
    return talalatok[0]


# Amit a naptár tölt ki egy projekten (lásd google_calendar.sync_hype_calendar).
# Ha egy naptárból létrejött projekten EZEKEN KÍVÜL nincs semmi, akkor puszta
# naptár-másolat: nyugodtan beolvasztható a párjába.
NAPTAR_MEZOK = (
    "nev",
    "forgatas_datuma",
    "forgatas_datuma_vege",
    "forgatas_kezdes_ido",
    "forgatas_veg_ido",
    "helyszin",
    "description",
    "naptar_szin",
    "nem_diszponalando",
    "google_calendar_event_id",
    "project_code_id",
)


def csak_naptar_adat(projekt: Project) -> bool:
    """Igaz, ha ezen a projekten a naptárból jött adatokon kívül nincs semmi:
    se utómunka, se diszpó-adat, se szerződés, se TIG, se portál - vagyis a
    törlésével nem veszik el semmi, amit a rendszerben csináltak rajta."""
    kapcsoltak = (
        projekt.deliverables,
        projekt.callsheets,
        projekt.assignments,
        projekt.contracts,
        projekt.post_shoot_feedbacks,
        projekt.performance_certificates,
        projekt.media_items,
        projekt.folders,
        projekt.crew,
        projekt.feldarabolt_napok,
    )
    if any(len(kapcsolt) > 0 for kapcsolt in kapcsoltak):
        return False
    if projekt.portal is not None:
        return False
    return True


def olvaszd_be_a_naptar_ikret(db: Session, cel: Project, iker: Project) -> bool:
    """A naptárból létrejött IKER beolvasztása a CÉL projektbe.

    A naptáresemény azonosítója átkerül (innentől a szinkron a cél projektet
    frissíti), a cél üres mezőit pedig kitöltjük az iker adataival. Az ikret
    csak akkor töröljük, ha nincs rajta más adat (lásd csak_naptar_adat) -
    máskülönben megtartjuk, hogy semmi ne vesszen el; ilyenkor False-t adunk
    vissza, és a hívó naplózza."""
    if not csak_naptar_adat(iker):
        return False

    esemeny_id = iker.google_calendar_event_id
    # Előbb az ikerről vesszük le az azonosítót: a naptáreseményhez EGY projekt
    # tartozhat, és a két sor egy pillanatig sem lóghat ugyanarra.
    iker.google_calendar_event_id = None
    db.flush()
    if esemeny_id and not cel.google_calendar_event_id:
        cel.google_calendar_event_id = esemeny_id
    for mezo in ("forgatas_kezdes_ido", "forgatas_veg_ido", "helyszin", "description", "naptar_szin"):
        if getattr(cel, mezo, None) in (None, "") and getattr(iker, mezo, None) not in (None, ""):
            setattr(cel, mezo, getattr(iker, mezo))
    db.delete(iker)
    db.flush()
    return True
