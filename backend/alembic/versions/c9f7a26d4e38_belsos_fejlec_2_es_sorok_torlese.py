"""Belsős lap: PONTOSAN 2 rögzített fejléc-sor + a köztes sorok törlése.

A felhasználó kérése (képernyőképpel): a belsős lapon csak az első KÉT sor
legyen rögzítve, és a 2. sor meg a JANUÁR elválasztó közti sorok törlődjenek.

Miért nem oldotta meg az előző kör (a7d5e93c1f28)? A legutóbbi Sheet-szinkron
a fejlécet az első DÁTUMOS sorig számolta (diszpo_sheet_sync.
fejlec_sorok_szama) - a beszivárgott üres sorok miatt így a belsős lapon
fejlec_sorok=15 lett: egyrészt 15 sor rögzül a felületen, másrészt az előző
törlő-migráció ablaka (fejlec_sorok-tól az első érdemi sorig) emiatt ÜRES
volt, és nem törölt semmit.

Ez a kör ezért: (1) a fejlécet PONTOSAN 2-re állítja; (2) a 2. sor utáni,
az első hónap-elválasztó (vagy ha nincs, az első dátumos sor) előtti ÖSSZES
sort törli a celláival együtt, a tartalmuktól függetlenül; (3) a többi sort
felcsúsztatja (kétfázisú eltolás az egyedi index miatt, mint
routes/diszpo_tabla._tolas). Idempotens.

Revision ID: c9f7a26d4e38
Revises: b8e6f15c3d29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c9f7a26d4e38"
down_revision = "b8e6f15c3d29"
branch_labels = None
depends_on = None

#: Ugyanaz a lapnév, mint services/diszpo_sheet_sync.KETSOROS_FEJLECU-ben.
BELSOS_LAP = "BELSŐS DISZPÓSTÁBLA"
FEJLEC = 2


def upgrade() -> None:
    conn = op.get_bind()
    lap = conn.execute(
        sa.text("SELECT id, fejlec_sorok FROM diszpo_munkalapok WHERE nev = :nev"),
        {"nev": BELSOS_LAP},
    ).first()
    if lap is None:
        return
    conn.execute(
        sa.text("UPDATE diszpo_munkalapok SET fejlec_sorok = :f WHERE id = :lap AND fejlec_sorok <> :f"),
        {"lap": lap.id, "f": FEJLEC},
    )
    hatar = conn.execute(
        sa.text("SELECT MIN(idx) FROM diszpo_sorok WHERE munkalap_id = :lap AND elvalaszto = TRUE"),
        {"lap": lap.id},
    ).scalar()
    if hatar is None:
        hatar = conn.execute(
            sa.text("SELECT MIN(idx) FROM diszpo_sorok WHERE munkalap_id = :lap AND datum IS NOT NULL"),
            {"lap": lap.id},
        ).scalar()
    if hatar is None or hatar <= FEJLEC:
        return
    darab = hatar - FEJLEC
    felretesz = 1_000_000
    params = {"lap": lap.id, "tol": FEJLEC, "ig": hatar, "darab": darab, "f": felretesz}
    conn.execute(
        sa.text("DELETE FROM diszpo_cellak WHERE munkalap_id = :lap AND sor_idx >= :tol AND sor_idx < :ig"),
        params,
    )
    conn.execute(
        sa.text("DELETE FROM diszpo_sorok WHERE munkalap_id = :lap AND idx >= :tol AND idx < :ig"),
        params,
    )
    conn.execute(
        sa.text("UPDATE diszpo_cellak SET sor_idx = sor_idx + :f WHERE munkalap_id = :lap AND sor_idx >= :ig"),
        params,
    )
    conn.execute(
        sa.text("UPDATE diszpo_cellak SET sor_idx = sor_idx - :f - :darab WHERE munkalap_id = :lap AND sor_idx >= :f"),
        params,
    )
    conn.execute(
        sa.text("UPDATE diszpo_sorok SET idx = idx + :f WHERE munkalap_id = :lap AND idx >= :ig"),
        params,
    )
    conn.execute(
        sa.text("UPDATE diszpo_sorok SET idx = idx - :f - :darab WHERE munkalap_id = :lap AND idx >= :f"),
        params,
    )
    conn.execute(
        sa.text("UPDATE diszpo_munkalapok SET sor_szam = GREATEST(sor_szam - :darab, 0) WHERE id = :lap"),
        params,
    )


def downgrade() -> None:
    # A törölt kitöltő-sorok nem állíthatók vissza - nem is kellenek.
    pass
