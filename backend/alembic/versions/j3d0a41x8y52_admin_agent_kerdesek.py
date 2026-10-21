"""Lara kérdései (önellenőrző tanulás).

Lara a háttérben összeveti, mit javasolt volna a rögzített munkára a jelenlegi
tudásával, és mi lett a valóság; ahol nem érti az eltérést, kérdést tesz fel.
A válasz (szabály / egyszeri kivétel / magyarázat / hibás rögzítés) tudássá
válik. Additív tábla.

Revision ID: j3d0a41x8y52
Revises: i2c9z30w7x51
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "j3d0a41x8y52"
down_revision = "i2c9z30w7x51"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "aa_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tipus", sa.String(40), nullable=False, server_default="szamla_besorolas"),
        sa.Column("allapot", sa.String(20), nullable=False, server_default="nyitott", index=True),
        sa.Column("kulcs", sa.String(200), nullable=False, index=True),
        sa.Column("partner_nev", sa.String(300), nullable=True),
        sa.Column("kerdes", sa.Text(), nullable=False),
        sa.Column("kontextus", JSONB(), nullable=True),
        sa.Column("valasz_tipus", sa.String(20), nullable=True),
        sa.Column("valasz_szoveg", sa.Text(), nullable=True),
        sa.Column("megvalaszolta_employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True),
        sa.Column("megvalaszolva_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("szabaly_id", sa.Integer(), sa.ForeignKey("aa_playbook_rules.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("aa_questions")
