"""4. hullám: a HYPE TO-DO LIST, ÁGI To-Do lista és FLÓRA Design adatbázis -
mindhárom ÖNÁLLÓ táblaként (nem a régi, félbehagyott Task-egyesítés
folytatásaként, lásd models/task.py docstringje és models/hype_todo.py,
models/agi_todo.py, models/flora_feladat.py megjegyzéseit).

Csak az Employee importra épülnek (a személy-mezők feloldásához) - a Main
Database-lánctól függetlenek, ezért bármikor futtathatók."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agi_todo import AgiTodoItem
from app.models.employee import Employee
from app.models.flora_feladat import FloraFeladat
from app.models.hype_todo import HypeTodoItem
from app.notion_import import database_ids as db_ids, files
from app.notion_import.client import NotionClient, as_date, as_datetime, extract_properties
from app.notion_import.engine import ImportResult, resolve_relation_id, resolve_relation_ids, safe_upsert
from app.notion_import.importers import _text, _url


def _valtozatlan_link(eredeti: list | None, ujak: list | None) -> str | None:
    """Az első URL, amit files.atemel_mindent NEM emelt át az R2-re (tehát
    külső link maradt, pl. Google Drive) - a ténylegesen feltöltött Notion-
    fájlok már a DocumentAttachment táblában vannak, azokat nem kell
    duplikálni egy szöveges linkmezőben is."""
    if not eredeti or not ujak:
        return None
    for e, u in zip(eredeti, ujak):
        if e == u and isinstance(u, str) and u.startswith(("http://", "https://")):
            return u
    return None


def import_hype_todo(client: NotionClient, db: Session) -> ImportResult:
    """HypeTodoItem <- HYPE TO-DO LIST (önálló tábla, lásd models/hype_todo.py)."""
    result = ImportResult(entity_type="HypeTodoItem")
    for page in client.query_database(db_ids.HYPE_TODO_LIST):
        props = extract_properties(page, client)
        feladat = _text(props.get("Feladat"))
        if not feladat:
            result.skipped += 1
            continue

        felelos_ids = resolve_relation_ids(db, "Employee", props.get("Felelős") or [])
        csatolni_valo_eredeti = props.get("Csatolni való") or []

        obj = safe_upsert(
            db,
            result,
            HypeTodoItem,
            "HypeTodoItem",
            page["id"],
            {
                "feladat": feladat,
                "allapot": _text(props.get("Állapot")),
                "leiras": _text(props.get("Leírás")),
                "kategoria": _text(props.get("Kategória")),
                "hatarido": as_date(props.get("Határidő")),
                "letrehozas_idopontja": as_datetime(props.get("Létrehozás időpontja")),
                "aki_felvezette_id": resolve_relation_id(db, "Employee", props.get("Aki felvezette") or []),
                "ellenorzes_felelos_id": resolve_relation_id(db, "Employee", props.get("Ellenőrzés felelős") or []),
                "aki_ellenorizte_id": resolve_relation_id(
                    db, "Employee", props.get("Aki ellenőrizte/készbe rakta") or []
                ),
            },
            label=f"HYPE TO-DO '{feladat}'",
        )
        if obj is None:
            continue
        if felelos_ids:
            obj.felelosok = db.scalars(select(Employee).where(Employee.id.in_(felelos_ids))).all()
        ujak = files.atemel_mindent(db, props, entity_type="hypeTodo", entity_id=obj.id, result=result)
        obj.csatolando_link = _valtozatlan_link(csatolni_valo_eredeti, ujak.get("Csatolni való"))
    return result


def import_agi_todo(client: NotionClient, db: Session) -> ImportResult:
    """AgiTodoItem <- Ági to do list (önálló tábla, lásd models/agi_todo.py).

    Az "Ügyfél" mezőt sima címkeként (select) kezeljük, nem a Client táblára
    mutató kapcsolatként - ezt élesben, az első futtatás után érdemes
    ellenőrizni (ha ott valójában relation, a mező üresen fog maradni, mert a
    _text() egy Notion page-ID listát nem tud szöveggé alakítani értelmesen)."""
    result = ImportResult(entity_type="AgiTodoItem")
    for page in client.query_database(db_ids.AGI_TODO_LIST):
        props = extract_properties(page, client)
        feladat = _text(props.get("Feladat"))
        if not feladat:
            result.skipped += 1
            continue

        files_eredeti = props.get("Files & media") or []

        obj = safe_upsert(
            db,
            result,
            AgiTodoItem,
            "AgiTodoItem",
            page["id"],
            {
                "feladat": feladat,
                "allapot": _text(props.get("Állapot")),
                "ugyfel": _text(props.get("Ügyfél")),
                "hatarido": as_date(props.get("Határidő")),
                "leiras": _text(props.get("Leírás")),
                "kovetkezo_lepes": _text(props.get("Következő lépés")),
            },
            label=f"ÁGI feladat '{feladat}'",
        )
        if obj is None:
            continue
        ujak = files.atemel_mindent(db, props, entity_type="agiTodo", entity_id=obj.id, result=result)
        obj.csatolt_link = _valtozatlan_link(files_eredeti, ujak.get("Files & media"))
    return result


def import_flora_design(client: NotionClient, db: Session) -> ImportResult:
    """FloraFeladat <- FLÓRA "Design adatbázis" (önálló tábla, lásd
    models/flora_feladat.py) - a Kanban board `Állapot` oszlopa adja a
    board-oszlopokat (lásd services/entity_registry.SELECT_FIELD_OVERRIDES)."""
    result = ImportResult(entity_type="FloraFeladat")
    for page in client.query_database(db_ids.FLORA_DESIGN):
        props = extract_properties(page, client)
        megnevezes = _text(props.get("Megnevezés"))
        if not megnevezes:
            result.skipped += 1
            continue

        obj = safe_upsert(
            db,
            result,
            FloraFeladat,
            "FloraFeladat",
            page["id"],
            {
                "megnevezes": megnevezes,
                "allapot": _text(props.get("Állapot")),
                "cimke": _text(props.get("Labels")),
                "hatarido": as_datetime(props.get("Határidő")),
                "kesz_anyag_linkje": _url(props.get("Kész anyag linkje")),
                "leiras": _text(props.get("Leírás")),
                "letrehozas_idopontja": as_datetime(props.get("Created time")),
                "felelos_id": resolve_relation_id(db, "Employee", props.get("Felelős") or []),
                "felvezette_id": resolve_relation_id(db, "Employee", props.get("Felvezette") or []),
            },
            label=f"FLÓRA '{megnevezes}'",
        )
        if obj is None:
            continue
        files.atemel_mindent(db, props, entity_type="floraFeladat", entity_id=obj.id, result=result)
    return result
