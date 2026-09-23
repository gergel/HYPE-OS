"""Lara: egyetlen felelős — Vidor Gergely.

A felhasználó kérése: Laránál mindenért Vidor Gergely a felelős, minden
ellenőrzés/jóváhagyás hozzá fut be, és egyelőre másnak Lara semmit nem küld.

- `aa_settings.limitek.csak_felelosnek = true` (a kód alapértéke is ez);
- `aa_settings.limitek.felelos_employee_id` = a „Vidor Gergely" nevű AKTÍV
  munkatárs (ékezet / sorrend nem számít) — ha nincs ilyen, a mező üres marad,
  és a Beállításokban kell kiválasztani (addig Lara senkinek nem küld);
- a nyitott Lara-feladatok felelőse ő lesz.

Csak adat-módosítás. Revision ID: n7h4e85b2c96, Revises: m6g3d74a1b85
"""

import json
import unicodedata

import sqlalchemy as sa
from alembic import op

revision = "n7h4e85b2c96"
down_revision = "m6g3d74a1b85"
branch_labels = None
depends_on = None


def _kulcs(nev: str | None) -> frozenset[str]:
    s = unicodedata.normalize("NFKD", (nev or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return frozenset(t for t in "".join(c if c.isalnum() else " " for c in s).split() if t)


def upgrade() -> None:
    conn = op.get_bind()
    cel = _kulcs("Vidor Gergely")
    felelos = next(
        (
            r.id
            for r in conn.execute(sa.text("SELECT id, full_name FROM employees WHERE is_active IS TRUE ORDER BY id"))
            if _kulcs(r.full_name) == cel
        ),
        None,
    )
    beallitas = {"csak_felelosnek": True}
    if felelos is not None:
        beallitas["felelos_employee_id"] = felelos
    conn.execute(
        sa.text(
            "UPDATE aa_settings SET limitek = "
            "(CASE WHEN jsonb_typeof(limitek) = 'object' THEN limitek ELSE '{}'::jsonb END) || CAST(:b AS jsonb) "
            "WHERE id = 1"
        ),
        {"b": json.dumps(beallitas)},
    )
    if felelos is not None:
        conn.execute(
            sa.text(
                "UPDATE aa_tasks SET felelos_id = :f "
                "WHERE allapot NOT IN ('completed', 'rejected', 'cancelled')"
            ),
            {"f": felelos},
        )


def downgrade() -> None:
    op.execute(
        "UPDATE aa_settings SET limitek = limitek - 'csak_felelosnek' - 'felelos_employee_id' "
        "WHERE id = 1 AND jsonb_typeof(limitek) = 'object'"
    )
