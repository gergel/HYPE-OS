"""Munkafelajánlás: mentett, elnevezett címzett-listák.

Pl. az "Operatőrök" lista egyszer összeáll, és onnantól egy kattintással
behívható a meghívottak közé (lásd models/munkafelajanlas.CimzettLista).

Revision ID: b5t2s63p0r44
Revises: a4s1r52o9q43
"""

import sqlalchemy as sa
from alembic import op

revision = "b5t2s63p0r44"
down_revision = "a4s1r52o9q43"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ajanlat_cimzett_listak",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nev", sa.String(length=255), nullable=False, unique=True),
        sa.Column("employee_ids", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("ajanlat_cimzett_listak")
