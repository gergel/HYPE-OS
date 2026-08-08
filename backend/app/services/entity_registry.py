"""Entity_type string -> SQLAlchemy modell megfeleltetés, a mező-láthatóság
Beállítások oldalának mezőtípus-lekérdezéséhez (lásd routes/field_visibility.py
"schema" végpontja) - null értékű boolean/date mezőknél a frontend a nyers
JSON értékből (null) nem tudja eldönteni, hogy checkbox vagy dátum-inputot
kell-e megjelenítenie, ezért a backend a tényleges oszloptípusból adja meg.

Két módon ismerjük fel a Notion "select" mezőket:
1. Valódi DB enum oszlopok (pl. Employee.tipus/role) - ezeknél a teljes
   definiált értékkészletet adjuk vissza (nem csak az aktuálisan használt
   értékeket), ez mindig megbízható.
2. Szöveges oszlopok, amiknek kevés, rövid, ismétlődő értéke van a táblában
   (lásd _select_options) - ez egy tényleges adaton alapuló heurisztika, mert
   az eredeti Notion property-típusokat és színeket nem tároltuk el
   importáláskor. Az azonosító-jellegű mezőket (név, email, URL stb.) explicit
   kizárjuk, mert ezeknél a véletlen adatismétlődés (pl. több "No Email Ember"
   nevű Notion-import placeholder) hamis select-találatot adna."""

from datetime import date, datetime, time
from decimal import Decimal
from typing import TypedDict

from sqlalchemy import Enum as SAEnum
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.campaign import Campaign
from app.models.client import Client, Contact
from app.models.contract import Contract
from app.models.deliverable import Deliverable
from app.models.employee import Employee
from app.models.equipment import Assignment, Equipment
from app.models.feedback import Feedback
from app.models.finance import Expense, Revenue
from app.models.kotelezettseg import KotelezettsegIdoszak
from app.models.project import Project
from app.models.project_code import ProjectCode
from app.models.rate import Rate
from app.models.task import Task
from app.models.timesheet import Timesheet

ENTITY_MODELS: dict[str, type] = {
    "project": Project,
    "client": Client,
    "projectCode": ProjectCode,
    "employee": Employee,
    "equipment": Equipment,
    "campaign": Campaign,
    "task": Task,
    "expense": Expense,
    "revenue": Revenue,
    "deliverable": Deliverable,
    # Ezeknek nincs saját részletnézet-oldaluk, a generikus /rekord/... adatlap
    # nyitja meg őket (lásd frontend lib/recordEntities.ts) - a mezőtípusok
    # (dátum/szám/select) ide is ugyanúgy kellenek a szerkesztéshez.
    "contact": Contact,
    "contract": Contract,
    "rate": Rate,
    "timesheet": Timesheet,
    "feedback": Feedback,
    "assignment": Assignment,
    # Egy kötelezettség egy fordulója - csatolmányt (számlát) fogad.
    "kotelezettsegIdoszak": KotelezettsegIdoszak,
}

SELECT_LIKE_MAX_DISTINCT = 20
SELECT_LIKE_MAX_VALUE_LENGTH = 60

# Explicit módon deklarált select-opciólisták olyan szöveges mezőkhöz, ahol a
# tényleges DB-adat (még) nem fedi le a Notion select-mező teljes, elvárt
# értékkészletét (pl. üres sandbox, vagy egy státusz, amit még sosem
# választottak) - ezek MINDIG felülírják a lenti heurisztikát/valódi
# enum-detektálást, mert a felhasználó explicit megadta a pontos listát.
SELECT_FIELD_OVERRIDES: dict[str, dict[str, list[str]]] = {
    "expense": {
        "kifizetes_modja": ["Készpénz", "Átutalás", "Bankkártya"],
    },
    "equipment": {
        "allapot": ["Jó", "Szerelendő", "Selejt", "Elhagyva", "Szervíz", "Szerelve"],
        "hasznalhato": ["Használható", "Nem használható"],
        "kategoria": [
            "Iroda (adatároló)",
            "Irodai",
            "Optika",
            "Egyéb",
            "Kártya",
            "Akkumulátor",
            "Mozgatók",
            "Hang",
            "Statív",
            "Világítás",
            "Lámpa állvány",
            "Kamera",
            "220V",
            "Drón",
            "Táska",
        ],
    },
}

# Azonosító-jellegű/szabad szöveges mezők - ezeket sosem tekintjük select-nek,
# még akkor sem, ha a jelenlegi adatban véletlenül kevés/ismétlődő értékük van.
NOT_SELECT_NAME_PATTERN_FRAGMENTS = (
    "nev",
    "name",
    # A képviselő egy SZEMÉLY neve: bárki lehet, nem egy rögzített lista. Ha
    # select lenne, csak a már előfordult neveket lehetne kiválasztani - egy új
    # embert nem lehetne felvenni.
    "kepvisel",
    "email",
    "telefon",
    "phone",
    "cim",
    "url",
    "leiras",
    "description",
    "jegyzet",
    "megjegyzes",
    "comment",
    "szoveg",
    "text",
    "brief",
    "notion_ids",
    "serial",
    "szam",
    "code",
    "kod",
)


class FieldTypeInfo(TypedDict, total=False):
    type: str
    options: list[str]
    #: Select mezőnél: a listán kívüli, ÚJ érték is megadható (a felület
    #: helyben engedi beírni). Lásd NYITOTT_SELECT_MEZOK.
    allow_new: bool


# Olyan mezők, amiknek van egy kialakult értékkészlete (érdemes listából
# választani), de a lista nem zárt: időnként kell egy új érték, és azt ott
# helyben kell tudni felvenni, nem egy beállítás-oldalon.
#
# A "megbízás tárgya" a szerződéseken/TIG-eken megjelenő szöveg - jellemzően
# ugyanaz a pár megnevezés ismétlődik ("Operatőri munka", "Vágás"...), de egy
# új munkatípus bármikor előfordulhat. Az értékkészletet a MEGLÉVŐ adatból
# szedjük össze (több táblából, mert ugyanaz a szöveg mindegyiken szerepel),
# így nincs külön karbantartandó lista.
NYITOTT_SELECT_MEZOK: dict[str, tuple[str, ...]] = {
    "employee": ("megbizas_targya",),
    "contract": ("megbizas_targya",),
    "project": ("megbizas_targya",),
}


def _megbizas_targya_opciok(db: Session) -> list[str]:
    """A "megbízás tárgya" eddig előfordult értékei - ábécé szerint."""
    ertekek: set[str] = set()
    for model in (Employee, Contract):
        oszlop = getattr(model, "megbizas_targya", None)
        if oszlop is None:
            continue
        for (ertek,) in db.execute(select(oszlop).where(oszlop.is_not(None)).distinct()):
            szoveg = (ertek or "").strip()
            if szoveg:
                ertekek.add(szoveg)
    return sorted(ertekek, key=lambda s: s.lower())


def _select_options(name: str, db: Session, column) -> list[str] | None:
    """Ha egy szöveges oszlopnak kevés (<= SELECT_LIKE_MAX_DISTINCT), rövid és
    ismétlődő értéke van a táblában, azt Notion select-mezőnek tekintjük, és
    visszaadjuk a lehetséges értékeket (legördülő listához, lásd
    EditableDetailGrid) - máskülönben None (valószínűleg szabad szöveg)."""
    lowered = name.lower()
    if any(fragment in lowered for fragment in NOT_SELECT_NAME_PATTERN_FRAGMENTS):
        return None
    rows = db.execute(
        select(column, func.count()).where(column.is_not(None)).group_by(column).order_by(func.count().desc())
    ).all()
    if not rows or len(rows) > SELECT_LIKE_MAX_DISTINCT:
        return None
    if not any(count > 1 for _, count in rows):
        return None
    values = [value for value, _ in rows]
    if any(len(v) > SELECT_LIKE_MAX_VALUE_LENGTH or "\n" in v for v in values):
        return None
    return values


def _utomunka_allapotok(db: Session, column) -> list[str]:
    """Az utómunka választható állapotai: elöl a BEÁLLÍTOTT állapotok (a tábla
    oszlop-sorrendjében), utánuk minden olyan érték, ami az adatokban szerepel,
    de még nincs beállítva."""
    from app.models.deliverable_status import DeliverableStatusConfig

    beallitott = [
        sor.allapot
        for sor in db.query(DeliverableStatusConfig)
        .order_by(DeliverableStatusConfig.sorrend, DeliverableStatusConfig.id)
        .all()
    ]
    hasznalatban = [
        ertek
        for (ertek,) in db.execute(select(column).where(column.is_not(None)).distinct()).all()
        if ertek and ertek not in beallitott
    ]
    return beallitott + sorted(hasznalatban)


def _sajat_mezok_tipusai(entity_type: str, db: Session) -> dict[str, FieldTypeInfo]:
    """Az admin által létrehozott saját mezők típusai - körkörös import
    elkerülésére itt, függvényen belül importálva (az entity_fields modul
    ebből a modulból veszi az ENTITY_MODELS-t)."""
    from app.services.entity_fields import custom_defs

    result: dict[str, FieldTypeInfo] = {}
    for mezo in custom_defs(db, entity_type):
        if mezo.field_type == "select":
            result[mezo.field_key] = {"type": "select", "options": list(mezo.options or [])}
        else:
            result[mezo.field_key] = {"type": mezo.field_type}
    return result


def get_field_types(entity_type: str, db: Session | None = None) -> dict[str, FieldTypeInfo]:
    """{mezőnév: {"type": "boolean"|"date"|"datetime"|"time"|"number"|"select"|"text", "options"?: [...]}}
    egy entitástípushoz. Az "options" csak "select" típusnál van jelen. db
    hiányában a szöveges mezők mindig sima "text"-ként jönnek vissza (nincs
    select-detektálás adat nélkül)."""
    model = ENTITY_MODELS.get(entity_type)
    if model is None:
        return {}
    result: dict[str, FieldTypeInfo] = {}
    overrides = SELECT_FIELD_OVERRIDES.get(entity_type, {})
    # Az eltávolított mezők nem részei a rendszernek: a mezőtípusok között sem
    # szerepelnek (lásd services/entity_fields.py).
    eltavolitott: set[str] = set()
    if db is not None:
        from app.services.entity_fields import hidden_fields

        eltavolitott = hidden_fields(db, entity_type)
    nyitott = NYITOTT_SELECT_MEZOK.get(entity_type, ())
    for name, column in model.__table__.columns.items():
        if name in eltavolitott:
            continue
        if name in nyitott and db is not None:
            result[name] = {
                "type": "select",
                "options": _megbizas_targya_opciok(db),
                "allow_new": True,
            }
            continue
        if entity_type == "deliverable" and name == "allapot" and db is not None:
            # Az utómunka-állapotok a TÁBLA beállításából jönnek, a beállított
            # sorrendben - így egy állapot akkor is választható (és oszlopként
            # is látszik), ha épp EGYETLEN anyag sincs benne. Enélkül egy üres
            # állapot (pl. "Javítás") egyszerűen eltűnne a felületről, és nem
            # is lehetne rátenni semmit. Új érték helyben is felvehető.
            result[name] = {
                "type": "select",
                "options": _utomunka_allapotok(db, column),
                "allow_new": True,
            }
            continue
        if name in overrides:
            result[name] = {"type": "select", "options": overrides[name]}
            continue
        if isinstance(column.type, SAEnum):
            result[name] = {"type": "select", "options": list(column.type.enums)}
            continue
        py_type = getattr(column.type, "python_type", None)
        if py_type is bool:
            result[name] = {"type": "boolean"}
        elif py_type is date:
            result[name] = {"type": "date"}
        elif py_type is datetime:
            result[name] = {"type": "datetime"}
        elif py_type is time:
            # Napon belüli időpont (pl. forgatás kezdete/vége) - a frontend
            # ebből tudja, hogy <input type="time"> kell, ne szabad szöveg.
            result[name] = {"type": "time"}
        elif py_type in (int, float, Decimal):
            result[name] = {"type": "number"}
        elif py_type is str and db is not None:
            options = _select_options(name, db, column)
            result[name] = {"type": "select", "options": options} if options else {"type": "text"}
        else:
            result[name] = {"type": "text"}
    if db is not None:
        result.update(_sajat_mezok_tipusai(entity_type, db))
    return result
