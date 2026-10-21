"""Diszpó-sablonok backfill a JÖVŐBELI forgatások üres mezőibe.

A felhasználó kérése: a kontaktok, a diszpó szövege és a brief mindig az
alapértelmezett sablonnal induljon (lásd services/diszpo_sablon.py - az új
projekteknél a létrehozás tölti ki). Ez a kör a MÁR LÉTEZŐ, de még el nem
kezdődött forgatásokat hozza szinkronba: a mai naptól kezdődő (vagy dátum
nélküli, tehát még üres váz) projektek ÜRES mezőibe írja a sablont - ami ki
van töltve, ahhoz nem nyúl. A régi, lezajlott forgatásokat békén hagyja.
Idempotens.

Revision ID: d1a8b37e5f49
Revises: c9f7a26d4e38
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.services.diszpo_sablon import SABLONOK

revision = "d1a8b37e5f49"
down_revision = "c9f7a26d4e38"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    for mezo, sablon in SABLONOK.items():
        conn.execute(
            sa.text(
                f"UPDATE projects SET {mezo} = :sablon "
                f"WHERE COALESCE(TRIM({mezo}), '') = '' "
                "AND (forgatas_datuma IS NULL OR forgatas_datuma >= CURRENT_DATE)"
            ),
            {"sablon": sablon},
        )


def downgrade() -> None:
    # A sablon-szöveg visszaszedése nem szükséges - kézzel bármikor törölhető.
    pass
