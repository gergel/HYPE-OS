"""HYPE 2026: a belsős munkalap NEVEK sora visszakerül a 2. sorba.

A korábbi sor-törlés (a7f3e85c9d24, a 2-14. sor) a nevek sorát is kivitte -
az eredetileg a 2. sorban állt. A nevek szerencsére megvannak az oszlopok
feliratában (diszpo_oszlopok.cimke, a Sheet-átvétel pont ebből a sorból
töltötte): ebből építjük vissza a sort a 2. helyre (idx 1), a többi sor
lejjebb csúszik. A felhasználó kérése szerint ezután PONTOSAN a felső 2 sor
van rögzítve görgetésnél (fejlec_sorok = 2).

Ha a nevek sora már a helyén van (pl. egy közbeni Sheet-szinkron visszahozta),
a migráció nem szúr be duplán, csak a rögzítést állítja - így akárhányszor
lefuttatható.

Revision ID: c1f5a83b7d29
Revises: b9e4f72a6c15
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c1f5a83b7d29"
down_revision = "b9e4f72a6c15"
branch_labels = None
depends_on = None

#: Két lépésben tolunk, hogy az (munkalap_id, idx) egyediség ne üthessön
#: (ugyanaz a minta, mint a routes/diszpo_tabla._tolas és a7f3e85c9d24).
FELRETESZ = 1_000_000


def upgrade() -> None:
    conn = op.get_bind()
    lapok = conn.execute(
        sa.text("SELECT id, nev FROM diszpo_munkalapok WHERE lower(nev) LIKE '%bels%'")
    ).fetchall()
    for lap_id, nev in lapok:
        oszlopok = conn.execute(
            sa.text(
                "SELECT idx, cimke FROM diszpo_oszlopok "
                "WHERE munkalap_id = :m AND cimke IS NOT NULL AND btrim(cimke) <> ''"
            ),
            {"m": lap_id},
        ).fetchall()
        if not oszlopok:
            print(f"'{nev}': nincsenek oszlopfeliratok, a nevek sora nem építhető vissza.")
            continue
        # Ott van-e már a nevek sora a 2. helyen? Akkor a cellái az
        # oszlopfeliratokkal egyeznek - ilyenkor nem szúrunk be duplán.
        egyezes = conn.execute(
            sa.text(
                "SELECT count(*) FROM diszpo_cellak c "
                "JOIN diszpo_oszlopok o ON o.munkalap_id = c.munkalap_id AND o.idx = c.oszlop_idx "
                "WHERE c.munkalap_id = :m AND c.sor_idx = 1 AND c.ertek = o.cimke"
            ),
            {"m": lap_id},
        ).scalar()
        if (egyezes or 0) >= max(3, len(oszlopok) // 2):
            conn.execute(
                sa.text("UPDATE diszpo_munkalapok SET fejlec_sorok = 2 WHERE id = :m"),
                {"m": lap_id},
            )
            print(f"'{nev}': a nevek sora már a helyén van, csak a rögzítés állítva.")
            continue
        # A 2. sortól (idx 1) minden egy hellyel lejjebb csúszik.
        for tabla, oszlop in (("diszpo_sorok", "idx"), ("diszpo_cellak", "sor_idx")):
            conn.execute(
                sa.text(
                    f"UPDATE {tabla} SET {oszlop} = {oszlop} + :felretesz "
                    f"WHERE munkalap_id = :m AND {oszlop} >= 1"
                ),
                {"m": lap_id, "felretesz": FELRETESZ},
            )
            conn.execute(
                sa.text(
                    f"UPDATE {tabla} SET {oszlop} = {oszlop} - :vissza "
                    f"WHERE munkalap_id = :m AND {oszlop} >= :felretesz"
                ),
                {"m": lap_id, "vissza": FELRETESZ - 1, "felretesz": FELRETESZ},
            )
        conn.execute(
            sa.text(
                "INSERT INTO diszpo_sorok (munkalap_id, idx, elvalaszto, rejtett) "
                "VALUES (:m, 1, false, false)"
            ),
            {"m": lap_id},
        )
        for oszlop_idx, cimke in oszlopok:
            conn.execute(
                sa.text(
                    "INSERT INTO diszpo_cellak (munkalap_id, sor_idx, oszlop_idx, ertek) "
                    "VALUES (:m, 1, :o, :e)"
                ),
                {"m": lap_id, "o": oszlop_idx, "e": cimke},
            )
        conn.execute(
            sa.text(
                "UPDATE diszpo_munkalapok SET sor_szam = sor_szam + 1, fejlec_sorok = 2 "
                "WHERE id = :m"
            ),
            {"m": lap_id},
        )
        print(f"'{nev}': a nevek sora visszaépítve a 2. helyre, a felső 2 sor rögzítve.")


def downgrade() -> None:
    # A visszaépített sor törlése nem szükséges - az eredeti állapot sem
    # állítható vissza pontosan.
    pass
