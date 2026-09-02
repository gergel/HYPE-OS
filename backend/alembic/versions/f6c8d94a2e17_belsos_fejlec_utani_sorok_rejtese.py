"""A belsős lapon a fejléc és az első érdemi sor közti MINDEN sor elrejtése.

A felhasználó kérése: a HYPE 2026 belsős lapján a látott 3-14. sorok
tűnjenek el. Az előző kör (e2b4c86f9d75) csak a teljesen üres sorokat
rejtette - ha a szinkronnal bekerült sorokban maradt szín vagy
szemét-tartalom, azokat nem fogta meg. Ez a kör ezért a POZÍCIÓ alapján
dolgozik: a fejléc utáni, az első érdemi sor (hónap-elválasztó vagy dátumos
nap) ELŐTTI összes sort elrejti, a tartalmától függetlenül - érdemi sor a
fejléc és a január közt nem létezhet. Elrejtés, nem törlés (DiszpoSor.rejtett),
és idempotens: akárhányszor lefuttatható.

Revision ID: f6c8d94a2e17
Revises: e2b4c86f9d75
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f6c8d94a2e17"
down_revision = "e2b4c86f9d75"
branch_labels = None
depends_on = None

#: Ugyanaz a lapnév, mint services/diszpo_sheet_sync.KETSOROS_FEJLECU-ben.
BELSOS_LAP = "BELSŐS DISZPÓSTÁBLA"


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE diszpo_sorok s
            SET rejtett = TRUE
            FROM diszpo_munkalapok m
            WHERE s.munkalap_id = m.id
              AND m.nev = :lap
              AND s.rejtett = FALSE
              AND s.elvalaszto = FALSE
              AND s.datum IS NULL
              AND s.idx >= m.fejlec_sorok
              AND s.idx < (
                  SELECT COALESCE(MIN(e.idx), -1) FROM diszpo_sorok e
                  WHERE e.munkalap_id = m.id
                    AND (e.elvalaszto = TRUE OR e.datum IS NOT NULL)
              )
            """
        ).bindparams(lap=BELSOS_LAP)
    )


def downgrade() -> None:
    # Nem visszafordítható pontosan (nem tudjuk, melyik sor volt korábban is
    # rejtett) - a kitöltő-sorok rejtve hagyása visszafelé sem árt.
    pass
