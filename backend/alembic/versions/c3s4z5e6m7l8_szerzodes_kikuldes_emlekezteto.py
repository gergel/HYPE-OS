"""Alvállalkozói szerződés: a kiküldés nyoma és az aláírás-emlékeztető.

`contracts.kikuldve_at`, `kikuldott_cim`, `kikuldott_targy`,
`gmail_thread_id`, `gmail_rfc_message_id`, `emlekezteto_kuldve_at`,
`emlekezteto_db`. Csak új oszlopok - meglévő adat nem változik (az
`emlekezteto_db` 0-val indul). Visszafordítható.

Revision ID: c3s4z5e6m7l8
Revises: b2e3q4u5i6p7
"""

import sqlalchemy as sa
from alembic import op

revision = "c3s4z5e6m7l8"
down_revision = "b2e3q4u5i6p7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("contracts", sa.Column("kikuldve_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("contracts", sa.Column("kikuldott_cim", sa.String(255), nullable=True))
    op.add_column("contracts", sa.Column("kikuldott_targy", sa.String(500), nullable=True))
    op.add_column("contracts", sa.Column("gmail_thread_id", sa.String(255), nullable=True))
    op.add_column("contracts", sa.Column("gmail_rfc_message_id", sa.String(500), nullable=True))
    op.add_column("contracts", sa.Column("emlekezteto_kuldve_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "contracts", sa.Column("emlekezteto_db", sa.Integer(), nullable=False, server_default="0")
    )


def downgrade() -> None:
    for oszlop in (
        "emlekezteto_db",
        "emlekezteto_kuldve_at",
        "gmail_rfc_message_id",
        "gmail_thread_id",
        "kikuldott_targy",
        "kikuldott_cim",
        "kikuldve_at",
    ):
        op.drop_column("contracts", oszlop)
