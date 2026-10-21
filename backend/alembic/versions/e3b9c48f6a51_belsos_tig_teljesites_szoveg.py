"""Belsős TIG: a teljesítés szabad szövegként (teljesites_szoveg).

A felhasználó kérése: a teljesítés dátuma mezőbe bármit meg lehessen adni
(pl. "2026.06.01-2026.06.30."). A dátum-oszlop megmarad a hónap-besoroláshoz
- a szövegből dátumot próbálunk kiolvasni (lásd
routes/internal_performance_certificates._teljesites_szovegbol_datum).
Szándékosan NINCS backfill: a régi rekordoknál a mező üres marad, így a TIG
dokumentum {{tido}} mezője náluk változatlanul a hónap szövegét kapja - a
felület a meglévő dátumot mutatja kezdőértékként.

Revision ID: e3b9c48f6a51
Revises: d1a8b37e5f49
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e3b9c48f6a51"
down_revision = "d1a8b37e5f49"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "internal_performance_certificates",
        sa.Column("teljesites_szoveg", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("internal_performance_certificates", "teljesites_szoveg")
