"""A Notion HYPE ADMIN projektkódok hiányzó sorainak pótlása.

A felhasználó kérése: a Notion "HYPE ADMIN projektkódok" táblájának minden
kódja legyen meg a rendszerben is. A tábla pillanatképe (795 kód, 2026-09-01)
a repóban utazik (app/data/notion_projektkodok.json - kód, projekt név,
dátum, helyszín, esemény állapota, Notion oldal-azonosító). Ez a migráció
CSAK a hiányzó kódokat szúrja be az alapadatokkal - a meglévőkhöz nem nyúl,
ezért akárhányszor lefuttatható, és a naplóban felsorolja, mit pótolt.

A beszúrt sorhoz a Notion-leképezés (notion_import_map) is bekerül, hogy egy
későbbi teljes Notion-import ugyanezt a rekordot gazdagítsa (ügyfél-kötés,
pénzügyi mezők), ne duplikálja. Az ügyfél-kötést itt nem találgatjuk: ha van
"Ismeretlen ügyfél (Notion import)" placeholder, azt kapja (mint az
importban), különben üresen marad.

Revision ID: e3b7c95a1d48
Revises: d2a6b94e8c31
"""

from __future__ import annotations

import json
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "e3b7c95a1d48"
down_revision = "d2a6b94e8c31"
branch_labels = None
depends_on = None

ADATFAJL = Path(__file__).resolve().parents[2] / "app" / "data" / "notion_projektkodok.json"


def upgrade() -> None:
    conn = op.get_bind()
    jegyzek: list[dict] = json.loads(ADATFAJL.read_text(encoding="utf-8"))

    meglevo = {
        (k or "").strip()
        for (k,) in conn.execute(sa.text("SELECT projektkod FROM project_codes"))
        if k
    }
    ismeretlen_ugyfel_id = conn.execute(
        sa.text("SELECT id FROM clients WHERE nev = 'Ismeretlen ügyfél (Notion import)' ORDER BY id LIMIT 1")
    ).scalar()

    darab = 0
    for sor in jegyzek:
        if sor["kod"] in meglevo:
            continue
        uj_id = conn.execute(
            sa.text(
                "INSERT INTO project_codes "
                "(projektkod, project_nev, datum, helyszin, datum_megjegyzes, esemeny_allapota, penznem, client_id) "
                "VALUES (:kod, :nev, :datum, :helyszin, :datum_megj, :allapot, 'HUF', :client_id) "
                "RETURNING id"
            ),
            {
                "kod": sor["kod"],
                "nev": sor["nev"],
                "datum": sor["datum"],
                "helyszin": sor["helyszin"],
                "datum_megj": sor["datum_megjegyzes"],
                "allapot": sor["esemeny_allapota"],
                "client_id": ismeretlen_ugyfel_id,
            },
        ).scalar()
        # A leképezés az importer kulcsaival ("ProjectCode" + Notion page id) -
        # ütközésnél (a page id már le van képezve) nem nyúlunk hozzá.
        conn.execute(
            sa.text(
                "INSERT INTO notion_import_map (notion_page_id, entity_type, entity_id) "
                "VALUES (:pid, 'ProjectCode', :eid) ON CONFLICT (notion_page_id) DO NOTHING"
            ),
            {"pid": sor["notion_page_id"], "eid": uj_id},
        )
        darab += 1
        print(f"Pótolva: {sor['kod']} - {sor['nev'] or '(névtelen)'}")
    if darab:
        print(f"Összesen {darab} projektkód pótolva a Notionből.")
    else:
        print("Minden Notion-projektkód megvan - nincs pótolnivaló.")


def downgrade() -> None:
    # A pótolt sorok utólag nem különböztethetők meg biztonsággal a kézzel
    # felvittektől - nem törlünk.
    pass
