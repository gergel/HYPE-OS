"""A belsős diszpótábla felső KÉT sora rögzítve (fejlec_sorok = 2).

A felhasználó kérése: a HYPE 2026 belsős lapján görgetés közben is
látszódjon a felső két sor (szekciók + a nevek sora), hogy tudni lehessen,
kihez kerül a beírás. A frontend a munkalap fejlec_sorok mezőjéből dolgozik
- ez a feltöltés azt állítja 2-re, ha bármiért 2 alá csúszott volna (a
Sheet-szinkron mostantól szintén nem enged 2 alá ezen a lapon, lásd
services/diszpo_sheet_sync.fejlec_sorok_szama). Idempotens: akárhányszor
lefuttatható.

Revision ID: a5d9c27e4b31
Revises: f4c8d16b9e27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a5d9c27e4b31"
down_revision = "f4c8d16b9e27"
branch_labels = None
depends_on = None

#: Ugyanaz a lapnév, mint services/diszpo_sheet_sync.KETSOROS_FEJLECU-ben.
BELSOS_LAP = "BELSŐS DISZPÓSTÁBLA"


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE diszpo_munkalapok SET fejlec_sorok = 2 "
            f"WHERE nev = '{BELSOS_LAP}' AND fejlec_sorok < 2"
        )
    )


def downgrade() -> None:
    # Nem visszafordítható: nem tudjuk, mi volt előtte - de a 2 rögzített sor
    # visszafelé sem árt.
    pass
