"""A belsős lap fejléc utáni kitöltő-sorainak TÖRLÉSE (a látott 3-14. sorok).

A felhasználó kérése (képernyőképpel): a HYPE 2026 belsős lapján a 3-14.
sorok törlődjenek - az elrejtés (e2b4c86f9d75, f6c8d94a2e17) helyett
végleges törlés. Ugyanaz a lépés, mint a felület sor-törlése
(routes/diszpo_tabla.sor_torlese), csak egyben: a fejléc és az első érdemi
sor (hónap-elválasztó vagy dátumos nap) közti összes sor törlődik a
celláival együtt, a többi sor felcsúszik, a sor_szam csökken. A határokat
nem égettük be: a fejléc alatti, első érdemi sor előtti ablakot számoljuk -
a képernyőképen ez pont a 3-14. sor (a 15. a JANUÁR elválasztó).
Idempotens: üres ablaknál nem csinál semmit.

Revision ID: a7d5e93c1f28
Revises: f6c8d94a2e17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a7d5e93c1f28"
down_revision = "f6c8d94a2e17"
branch_labels = None
depends_on = None

#: Ugyanaz a lapnév, mint services/diszpo_sheet_sync.KETSOROS_FEJLECU-ben.
BELSOS_LAP = "BELSŐS DISZPÓSTÁBLA"


def upgrade() -> None:
    conn = op.get_bind()
    lap = conn.execute(
        sa.text("SELECT id, fejlec_sorok FROM diszpo_munkalapok WHERE nev = :nev"),
        {"nev": BELSOS_LAP},
    ).first()
    if lap is None:
        return
    hatar = conn.execute(
        sa.text(
            "SELECT MIN(idx) FROM diszpo_sorok "
            "WHERE munkalap_id = :lap AND (elvalaszto = TRUE OR datum IS NOT NULL)"
        ),
        {"lap": lap.id},
    ).scalar()
    if hatar is None or hatar <= lap.fejlec_sorok:
        return
    tol, ig = lap.fejlec_sorok, hatar  # [tol, ig) a törlendő ablak
    darab = ig - tol
    # Kétfázisú eltolás nagy "félretevő" offsettel, mint a felület sor-törlése
    # (routes/diszpo_tabla._tolas): az egyedi (munkalap_id, idx) index miatt a
    # közvetlen -darab eltolás sorfeldolgozási sorrendtől függően ütközne.
    felretesz = 1_000_000
    params = {"lap": lap.id, "tol": tol, "ig": ig, "darab": darab, "f": felretesz}
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
