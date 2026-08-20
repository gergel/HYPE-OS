"""A vállalási ár magyarázata a projektkódon

Nem minden összeg magyarázza magát, és a 0 Ft a legkevésbé (lásd
models/project_code.vallalasi_ar_magyarazat).

Revision ID: c4a91e7b25d0
Revises: b2f47c1e9d38
"""

import sqlalchemy as sa
from alembic import op

revision = "c4a91e7b25d0"
down_revision = "b2f47c1e9d38"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "project_codes",
        sa.Column(
            "vallalasi_ar_magyarazat",
            sa.Text(),
            nullable=True,
            comment="Miért ennyi a vállalási ár (pl. beszámítva egy fizetésbe)",
        ),
    )


def downgrade() -> None:
    op.drop_column("project_codes", "vallalasi_ar_magyarazat")
