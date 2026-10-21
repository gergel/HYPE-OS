"""Tranzakció nélküli lezárás a projektkódon

Ahol nincs számla, nincs papír, vagy elmaradt az esemény, ott a legtöbbször
pénzmozgás sem történik - a "mikor érkezett meg a pénz" kérdésre nincs igaz
válasz (lásd models/project_code.tranzakcio_nelkul_lezarva).

Revision ID: e8c1b53f27a4
Revises: d7e2b41f8c96
"""

import sqlalchemy as sa
from alembic import op

revision = "e8c1b53f27a4"
down_revision = "d7e2b41f8c96"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "project_codes",
        sa.Column(
            "tranzakcio_nelkul_lezarva",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("project_codes", "tranzakcio_nelkul_lezarva")
