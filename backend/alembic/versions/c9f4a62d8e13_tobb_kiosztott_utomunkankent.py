"""Több embert is lehessen kiosztani egy utómunkára.

Új deliverable_kiosztottak társítási tábla (a kanonikus forrás), a meglévő
egyértékű assigned_to_employee_id oszlop tükörként megmarad (mindig az első
kiosztott) - a meglévő kiosztásokat átemeljük a táblába.

Revision ID: c9f4a62d8e13
Revises: b7e2a91c4f60
Create Date: 2026-08-31
"""

import sqlalchemy as sa
from alembic import op

revision = "c9f4a62d8e13"
down_revision = "b7e2a91c4f60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "deliverable_kiosztottak",
        sa.Column("deliverable_id", sa.Integer(), sa.ForeignKey("deliverables.id"), primary_key=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), primary_key=True),
    )
    # A meglévő egyszemélyes kiosztások átemelése - semmi nem veszik el.
    op.execute(
        "INSERT INTO deliverable_kiosztottak (deliverable_id, employee_id) "
        "SELECT id, assigned_to_employee_id FROM deliverables "
        "WHERE assigned_to_employee_id IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_table("deliverable_kiosztottak")
