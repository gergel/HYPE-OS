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

from sqlalchemy import delete, func, inspect, select, update
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


def keresd(db: Session, kod: str | None, index: dict[str, ProjectCode] | None = None) -> ProjectCode | None:
    """A szöveghez tartozó Project Code, vagy None, ha nincs (vagy gyűjtő).

    Az `index` egy már felépített kulcs->kód szótár. EGY sor mentésénél nem kell
    (olyankor egy lekérdezés az egész), TÖMEGES futásnál viszont muszáj: enélkül
    soronként újraolvasnánk az összes projektkódot - ezer sornál ez ezer teljes
    tábla-beolvasás, ami éles adaton már percekben mérhető."""
    if not valodi(kod):
        return None
    return (_kod_index(db) if index is None else index).get(kulcs(kod))


def kosd_be(
    db: Session, sor: Project | Deliverable, index: dict[str, ProjectCode] | None = None
) -> bool:
    """EGY projekt/vágás bekötése a projektkódja szövege alapján.

    Visszatér: változott-e. A meglévő, valódi kötést nem bántjuk - azt vagy egy
    ember állította be, vagy egy korábbi kötés hozta létre; felülírni csak
    akkor szabad, ha a szöveg MÁSIK kódra mutat."""
    cel = keresd(db, sor.projektkod_szoveg, index)
    if cel is None:
        return False
    if sor.project_code_id == cel.id:
        return False
    sor.project_code_id = cel.id
    return True


def _kod_id_index(db: Session) -> dict[str, int]:
    """Kulcs -> Project Code AZONOSÍTÓ - a tömeges futáshoz.

    Ugyanaz a szabály, mint a `_kod_index`-nél, csak két oszlopot olvas: a
    migráció így nem függ a modell mai oszloplistájától (egy később hozzáadott
    oszlopot a régi séma még nem ismer), és nagyságrenddel kevesebbet olvas."""
    index: dict[str, int] = {}
    for kod_id, kod in db.execute(
        select(ProjectCode.id, ProjectCode.projektkod).order_by(ProjectCode.id)
    ).all():
        if valodi(kod):
            index.setdefault(kulcs(kod), kod_id)
    return index


def _gyujto_idk(db: Session) -> set[int]:
    return {
        kod_id
        for kod_id, kod in db.execute(select(ProjectCode.id, ProjectCode.projektkod)).all()
        if (kod or "").strip().upper() in GYUJTO_PROJEKTKODOK
    }


def _hivatkozik_ra_valami(db: Session, kod_id: int) -> bool:
    """Mutat-e még bármelyik tábla erre a projektkódra?

    Szándékosan a séma alapján keresi meg a hivatkozókat (projekt, vágás,
    kiadás, bevétel, havi tétel, megrendelői papír...), nem egy kézzel írt
    listából: ha holnap új tábla kapcsolódik a projektkódhoz, azt is látni
    fogja - különben egy "üresnek hitt" kód törlése vinné magával."""
    # Nem sorted_tables: a sorrend itt lényegtelen (csak számolunk), a rendezés
    # viszont a projekt-szerződés körkörös hivatkozásain figyelmeztetést dobna.
    #
    # Csak a TÉNYLEG LÉTEZŐ táblákat kérdezzük: ez a függvény adatmigrációból is
    # fut, ahol a séma még régebbi, mint a mai modellek - egy később bevezetett
    # tábla lekérdezése ott hibával állítaná meg a deployt.
    letezo = set(inspect(db.get_bind()).get_table_names())
    for tabla in Base.metadata.tables.values():
        if tabla.name == "project_codes" or tabla.name not in letezo:
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
    # Csak a NEM valódi (gyűjtő) kódokat nézzük végig - a valódiakhoz hozzá sem
    # nyúlunk, tehát fölösleges lenne végigkérdezni rájuk a hivatkozásokat.
    for kod_id, kod in db.execute(select(ProjectCode.id, ProjectCode.projektkod)).all():
        if valodi(kod) or _hivatkozik_ra_valami(db, kod_id):
            continue
        db.execute(delete(ProjectCode).where(ProjectCode.id == kod_id))
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
    # Az index EGYSZER épül fel az egész futásra: soronként újraépítve minden
    # projekt/vágás egy teljes projektkód-beolvasást jelentene (pár ezer sornál
    # ez percekben mérhető, és a migrációt futtató deploy elhasal rajta).
    #
    # Csak azt a HÁROM oszlopot olvassuk, ami a döntéshez kell, és kötegelt
    # UPDATE-tel írunk. Nem csak gyors: egy adatmigráció így nem függ a mai
    # modell teljes oszloplistájától - egy később hozzáadott oszlop különben
    # visszamenőleg elrontaná ezt a lépést (a régi séma még nem ismeri).
    index = _kod_id_index(db)
    eredmeny = {
        "projekt_bekotve": 0, "projekt_leoldva": 0,
        "vagas_bekotve": 0, "vagas_leoldva": 0, "gyujto_torolve": 0,
    }

    for modell, be, le in (
        (Project, "projekt_bekotve", "projekt_leoldva"),
        (Deliverable, "vagas_bekotve", "vagas_leoldva"),
    ):
        bekotendo: dict[int, list[int]] = {}
        leoldando: list[int] = []
        sorok = db.execute(
            select(modell.id, modell.projektkod_szoveg, modell.project_code_id)
        ).all()
        for sor_id, szoveg, kod_id in sorok:
            cel = index.get(kulcs(szoveg)) if valodi(szoveg) else None
            if cel is not None and cel != kod_id:
                bekotendo.setdefault(cel, []).append(sor_id)
            elif cel is None and kod_id is not None and kod_id in gyujtok:
                leoldando.append(sor_id)

        for cel, sor_idk in bekotendo.items():
            db.execute(update(modell).where(modell.id.in_(sor_idk)).values(project_code_id=cel))
            eredmeny[be] += len(sor_idk)
        if leoldando:
            db.execute(update(modell).where(modell.id.in_(leoldando)).values(project_code_id=None))
            eredmeny[le] += len(leoldando)

    # A tömeges UPDATE a session-ben lévő példányokat nem frissíti - a hívó
    # (és a rá következő gyűjtő-takarítás) friss adatot lásson.
    db.expire_all()
    db.flush()
    eredmeny["gyujto_torolve"] = takaritsd_a_gyujtoket(db)
    return eredmeny
