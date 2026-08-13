"""A projektkód SZÖVEGE és a valódi Project Code összekötése.

A rendszerben két helyen él a projektkód: szövegként a projekten és a vágáson
(`projektkod_szoveg` - a Notionból és a naptárból így érkezett), és önálló
rekordként a Project Code táblában. Ha a kettő nincs összekötve, a projektkód
adatlapja nem tudja megmondani, hány forgatás és hány vágás tartozik alá -
pedig pont ez a nyomon követhetőség a lényege.

Ez a modul a szabály: melyik szöveg számít VALÓDI projektkódnak, és melyik
Project Code-hoz tartozik.

**A gyűjtő kódok nem valódiak.** Az importok kényszerből hoztak létre két
gyűjtőt (`NAPTAR-IMPORT`, `ISMERETLEN-NOTION-IMPORT`), hogy legyen hova tenni
azt, aminek nincs kódja. Ezekbe nem kötünk be semmit: amihez nincs valódi
projektkód, az maradjon kötetlen, és akkor kerüljön a helyére, amikor tényleg
megkapja a kódját. Egy gyűjtőbe söpört projekt ugyanis úgy néz ki, mintha
elintéztük volna - pedig épp ellenkezőleg."""

from __future__ import annotations

import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models.deliverable import Deliverable
from app.models.project import Project
from app.models.project_code import ProjectCode

#: Az importok gyűjtő kódjai - lásd services/google_calendar.py és
#: notion_import/importers_wave2.py.
GYUJTO_PROJEKTKODOK: frozenset[str] = frozenset({"NAPTAR-IMPORT", "ISMERETLEN-NOTION-IMPORT"})


def kulcs(kod: str | None) -> str:
    """Összehasonlítható projektkód: kis/nagybetűtől, szóköztől független.

    Szándékosan NEM szigorúbb ennél: a felhasználó megadhat a megszokottól
    eltérő alakot is (más ügyfél kódrendszere, régi sorozat), és ha ő két
    alakot ugyanannak szán, akkor a szóköz vagy a kisbetű ne válassza szét."""
    return re.sub(r"\s+", " ", (kod or "").strip()).casefold()


def valodi(kod: str | None) -> bool:
    """Valódi projektkód-e, vagy csak egy import-gyűjtő (esetleg üres)?"""
    tisztitott = (kod or "").strip()
    return bool(tisztitott) and tisztitott.upper() not in GYUJTO_PROJEKTKODOK


def _kod_index(db: Session) -> dict[str, ProjectCode]:
    """Kulcs -> Project Code. A gyűjtők kimaradnak (lásd a modul leírását).

    Ha ugyanaz a kód kétszer szerepel (import-duplikátum), a KISEBB id nyer:
    az a régebbi, ahhoz tartozik a történet."""
    index: dict[str, ProjectCode] = {}
    for pc in db.scalars(select(ProjectCode).order_by(ProjectCode.id)):
        if not valodi(pc.projektkod):
            continue
        index.setdefault(kulcs(pc.projektkod), pc)
    return index


def keresd(db: Session, kod: str | None) -> ProjectCode | None:
    """A szöveghez tartozó Project Code, vagy None, ha nincs (vagy gyűjtő)."""
    if not valodi(kod):
        return None
    return _kod_index(db).get(kulcs(kod))


def kosd_be(db: Session, sor: Project | Deliverable) -> bool:
    """EGY projekt/vágás bekötése a projektkódja szövege alapján.

    Visszatér: változott-e. A meglévő, valódi kötést nem bántjuk - azt vagy egy
    ember állította be, vagy egy korábbi kötés hozta létre; felülírni csak
    akkor szabad, ha a szöveg MÁSIK kódra mutat."""
    cel = keresd(db, sor.projektkod_szoveg)
    if cel is None:
        return False
    if sor.project_code_id == cel.id:
        return False
    sor.project_code_id = cel.id
    return True


def _gyujto_idk(db: Session) -> set[int]:
    return {
        pc.id
        for pc in db.scalars(select(ProjectCode))
        if (pc.projektkod or "").strip().upper() in GYUJTO_PROJEKTKODOK
    }


def _hivatkozik_ra_valami(db: Session, kod_id: int) -> bool:
    """Mutat-e még bármelyik tábla erre a projektkódra?

    Szándékosan a séma alapján keresi meg a hivatkozókat (projekt, vágás,
    kiadás, bevétel, havi tétel, megrendelői papír...), nem egy kézzel írt
    listából: ha holnap új tábla kapcsolódik a projektkódhoz, azt is látni
    fogja - különben egy "üresnek hitt" kód törlése vinné magával."""
    # Nem sorted_tables: a sorrend itt lényegtelen (csak számolunk), a rendezés
    # viszont a projekt-szerződés körkörös hivatkozásain figyelmeztetést dobna.
    for tabla in Base.metadata.tables.values():
        if tabla.name == "project_codes":
            continue
        for fk in tabla.foreign_keys:
            if fk.column.table.name != "project_codes":
                continue
            if db.scalar(select(func.count()).select_from(tabla).where(fk.parent == kod_id)):
                return True
    return False


def takaritsd_a_gyujtoket(db: Session) -> int:
    """Az ÜRESSÉ vált import-gyűjtő kódok törlése.

    Miután mindent leoldottunk róluk, a gyűjtő már csak egy üres sor a
    projektkódok közt - pont ott, ahol a valódi munkákat keressük. Amelyikre
    még mutat bármi, az marad: azt előbb kézzel kell rendezni."""
    torolt = 0
    for pc in list(db.scalars(select(ProjectCode))):
        if valodi(pc.projektkod) or _hivatkozik_ra_valami(db, pc.id):
            continue
        db.delete(pc)
        torolt += 1
    return torolt


def kosd_ossze_mindent(db: Session) -> dict[str, int]:
    """Minden projekt és vágás bekötése a projektkódja alapján - egy menetben.

    Két dolgot csinál:

    1. **beköt**, ahol a projektkód szövege valódi Project Code-ra mutat;
    2. **leold**, ahol a sor egy GYŰJTŐ kódhoz van kötve. A gyűjtő nem válasz,
       csak egy halom: amíg nincs valódi kódja, ne látszódjon úgy, mintha
       lenne. Ha közben megkapta a valódit, az 1. lépés már bekötötte.

    Végül az így ÜRESSÉ vált gyűjtőket ki is veszi a projektkódok közül.

    Idempotens: újrafuttatva csak azt mozgatja, ami tényleg változott."""
    gyujtok = _gyujto_idk(db)
    eredmeny = {
        "projekt_bekotve": 0, "projekt_leoldva": 0,
        "vagas_bekotve": 0, "vagas_leoldva": 0, "gyujto_torolve": 0,
    }

    for modell, be, le in (
        (Project, "projekt_bekotve", "projekt_leoldva"),
        (Deliverable, "vagas_bekotve", "vagas_leoldva"),
    ):
        for sor in db.scalars(select(modell)):
            if kosd_be(db, sor):
                eredmeny[be] += 1
            elif sor.project_code_id is not None and sor.project_code_id in gyujtok:
                sor.project_code_id = None
                eredmeny[le] += 1

    db.flush()
    eredmeny["gyujto_torolve"] = takaritsd_a_gyujtoket(db)
    return eredmeny
