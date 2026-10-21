"""Utómunkák vinyó-mezőjének igazítása a felhasználó Excel-jegyzékéhez.

A felhasználó 2026-09-01-én leadott egy teljes vinyó-jegyzéket
(Vinyok_projektek.xlsx, forrása a Notion Utómunka adatbázis "Vinyók" mezője) -
a kérése: minden utómunka PONTOSAN arra a vinyóra (vagy vinyókra) legyen
állítva, ami a jegyzékben szerepel; ami nálunk megvan, de a jegyzékben nincs,
az marad, ahol most van.

A jegyzék a repóban utazik (app/data/vinyok_projektek.json - név -> vinyó
lista), az egyeztetés az utómunka NEVE szerint történik, kisbetű- és
szóköz-türelmesen: a jegyzék ugyanabból a Notion-táblából készült, amiből az
utómunkák is importálódtak, tehát a név a természetes kulcs. Ahol ugyanaz a
név több vinyón szerepel, az utómunka az összeset megkapja (a `vinyok` mező
lista). Csak azt a sort írjuk, ahol az érték ténylegesen eltér - a migráció
akárhányszor lefuttatható.

Revision ID: e5a7c31d8f92
Revises: d3f8b92c6e41
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "e5a7c31d8f92"
down_revision = "d3f8b92c6e41"
branch_labels = None
depends_on = None

JEGYZEK = Path(__file__).resolve().parents[2] / "app" / "data" / "vinyok_projektek.json"


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip()).casefold()


def upgrade() -> None:
    jegyzek: dict[str, list[str]] = json.loads(JEGYZEK.read_text(encoding="utf-8"))
    nev_vinyok = {_norm(nev): vinyok for nev, vinyok in jegyzek.items()}

    conn = op.get_bind()
    sorok = conn.execute(
        sa.text("SELECT id, projekt_neve, vinyok FROM deliverables WHERE projekt_neve IS NOT NULL")
    ).fetchall()

    frissitett = talalat = 0
    for sor_id, nev, jelenlegi in sorok:
        vinyok = nev_vinyok.get(_norm(nev or ""))
        if vinyok is None:
            # Nincs a jegyzékben - marad, ahol most van (a felhasználó kérése).
            continue
        talalat += 1
        # A tárolt érték JSON (lista vagy None) - a driver dict/list-ként adja
        # vissza, de szövegként is jöhet régi sorokból.
        if isinstance(jelenlegi, str):
            try:
                jelenlegi = json.loads(jelenlegi)
            except ValueError:
                jelenlegi = None
        if isinstance(jelenlegi, list) and sorted(str(v) for v in jelenlegi) == vinyok:
            continue
        conn.execute(
            sa.text("UPDATE deliverables SET vinyok = :vinyok WHERE id = :id"),
            {"vinyok": json.dumps(vinyok, ensure_ascii=False), "id": sor_id},
        )
        frissitett += 1
    print(f"Vinyó-igazítás: {talalat} utómunka szerepel a jegyzékben, {frissitett} frissítve.")


def downgrade() -> None:
    # Nem visszafordítható - a korábbi vinyó-értékeket nem őrizzük meg.
    pass
