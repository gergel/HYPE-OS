"""Vágói játék: az ellenőrzés kimenete is pontot ér.

Ha az ellenőrzésbe tett anyag javítás nélkül megy tovább (kiküldésre vár /
kész kiküldve), +100 pont annak, aki ellenőrzésbe tette; ha javításba kerül,
-20 (lásd models/vagoi_jatek.VagoEllenorzesKimenet).

Revision ID: c1f7a83e6d29
Revises: b6d3f95a2c47
Create Date: 2026-08-31
"""

import sqlalchemy as sa
from alembic import op

revision = "c1f7a83e6d29"
down_revision = "b6d3f95a2c47"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vago_ellenorzes_kimenetek",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("deliverable_id", sa.Integer(), sa.ForeignKey("deliverables.id"), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False, index=True),
        sa.Column("idopont", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("kimenet", sa.String(length=20), nullable=False),
        sa.Column("pont", sa.Integer(), nullable=False),
        sa.Column("allapot", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("deliverable_id", name="uq_vago_ellenorzes_kimenet"),
    )


def downgrade() -> None:
    op.drop_table("vago_ellenorzes_kimenetek")
