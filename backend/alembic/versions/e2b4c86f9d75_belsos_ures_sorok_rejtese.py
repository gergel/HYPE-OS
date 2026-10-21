"""A belsős diszpótábla ÜRES kitöltő-sorainak elrejtése.

A felhasználó jelzése: a legutóbbi Sheet-szinkron a belsős lapon a két
fejléc-sor és a JANUÁR elválasztó közé egy rakás üres ("fekete") sort hozott
be (a látott 3-14. sorok). Ezeket rejtjük el: minden olyan sort, ami a
fejléc UTÁN és az első érdemi sor (elválasztó vagy dátumos nap) ELŐTT áll,
nincs dátuma, nem elválasztó, és egyetlen tárolt cellája sincs (se szöveg,
se szín - a cella-tábla csak a nem üres cellákat tartalmazza, lásd
models/diszpo_tabla.DiszpoCella). Elrejtés, nem törlés: az elv ugyanaz,
mint a felület sor-elrejtésénél (DiszpoSor.rejtett), és a munkanap-számolást
üres sor nem érinti. Idempotens: akárhányszor lefuttatható.

A Sheet-szinkron gombja ezzel együtt lekerült a felületről (a felhasználó
kérése: többet ne szinkronizáljon), így a sorok nem jönnek vissza.

Revision ID: e2b4c86f9d75
Revises: d9a3b75e8c64
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e2b4c86f9d75"
down_revision = "d9a3b75e8c64"
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
              AND NOT EXISTS (
                  SELECT 1 FROM diszpo_cellak c
                  WHERE c.munkalap_id = m.id
                    AND c.sor_idx = s.idx
                    AND (COALESCE(TRIM(c.ertek), '') <> '' OR c.szin IS NOT NULL)
              )
            """
        ).bindparams(lap=BELSOS_LAP)
    )


def downgrade() -> None:
    # Nem visszafordítható pontosan (nem tudjuk, melyik sor volt korábban is
    # rejtett) - az üres sorok rejtve hagyása visszafelé sem árt.
    pass
