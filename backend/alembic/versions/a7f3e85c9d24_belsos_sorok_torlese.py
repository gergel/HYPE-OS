"""HYPE 2026: a belsős munkalap 2-14. sorának törlése.

A felhasználó kérése: a belsős munkalapról a 2.-14. sor (13 sor, a fejléc
alattiak) kerüljön ki, a tartalmával együtt - a többi sor feljebb csúszik.
Ugyanaz a művelet, mint a felület sor-törlése (lásd
routes/diszpo_tabla.sor_torlese), csak egyben a 13 sorra.

FONTOS: a Google Sheet-átvétel CSERÉLI a sorokat (lásd
services/diszpo_sheet_sync.py) - ha a sorok a Sheetben megmaradnak, egy
következő szinkron visszahozza őket. A tartós eltüntetéshez a Sheetből is
törölni kell őket.

Revision ID: a7f3e85c9d24
Revises: e9c6d51b8a37
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a7f3e85c9d24"
down_revision = "e9c6d51b8a37"
branch_labels = None
depends_on = None

#: A felületen 2.-14. sor = idx 1..13 (0-tól számozva).
TOL, IG = 1, 13
DARAB = IG - TOL + 1
#: Két lépésben tolunk, hogy az (munkalap_id, idx) egyediség ne üthessön
#: (ugyanaz a minta, mint a routes/diszpo_tabla._tolas).
FELRETESZ = 1_000_000


def upgrade() -> None:
    conn = op.get_bind()
    lapok = conn.execute(
        sa.text("SELECT id, nev, sor_szam FROM diszpo_munkalapok WHERE lower(nev) LIKE '%bels%'")
    ).fetchall()
    for lap_id, nev, sor_szam in lapok:
        if (sor_szam or 0) <= IG + 1:
            print(f"'{nev}': csak {sor_szam} sora van, a 2-14. sor törlése kihagyva.")
            continue
        conn.execute(
            sa.text("DELETE FROM diszpo_cellak WHERE munkalap_id = :m AND sor_idx BETWEEN :tol AND :ig"),
            {"m": lap_id, "tol": TOL, "ig": IG},
        )
        conn.execute(
            sa.text("DELETE FROM diszpo_sorok WHERE munkalap_id = :m AND idx BETWEEN :tol AND :ig"),
            {"m": lap_id, "tol": TOL, "ig": IG},
        )
        for tabla, oszlop in (("diszpo_sorok", "idx"), ("diszpo_cellak", "sor_idx")):
            conn.execute(
                sa.text(
                    f"UPDATE {tabla} SET {oszlop} = {oszlop} + :felretesz "
                    f"WHERE munkalap_id = :m AND {oszlop} > :ig"
                ),
                {"m": lap_id, "ig": IG, "felretesz": FELRETESZ},
            )
            conn.execute(
                sa.text(
                    f"UPDATE {tabla} SET {oszlop} = {oszlop} - :vissza "
                    f"WHERE munkalap_id = :m AND {oszlop} >= :felretesz"
                ),
                {"m": lap_id, "vissza": FELRETESZ + DARAB, "felretesz": FELRETESZ},
            )
        conn.execute(
            sa.text("UPDATE diszpo_munkalapok SET sor_szam = GREATEST(sor_szam - :darab, 0) WHERE id = :m"),
            {"m": lap_id, "darab": DARAB},
        )
        print(f"'{nev}': a 2-14. sor törölve, a többi feljebb csúszott.")


def downgrade() -> None:
    # A törölt sorok tartalma nem állítható vissza.
    pass
