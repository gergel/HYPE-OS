"""keretszerzodes idoszakok, tobb szerepkor

Három, egymástól független bővítés:

1. contracts.aktiv - a keretszerződés kézi be-/kikapcsolója. Alapból mindegyik
   aktív (eddig is így viselkedtek).
2. contract_periods - a keretszerződés érvényességi időszakai. Egy emberrel
   nem feltétlenül folyamatos a viszony: van egy időszakra, aztán fél évig
   nincs, majd újra. Üres időszak-lista = időbeli korlát nélkül érvényes,
   tehát a meglévő adat viselkedése nem változik.
3. employees.tovabbi_szerepkorok - egy embernek több szerepköre is lehet (pl.
   admin ÉS adminisztráció). Az elsődleges marad az employees.role oszlopban,
   ez a lista a továbbiakat tartja.
4. tasks.project_id - melyik projekthez tartozik a feladat. A lefutott
   projektek után automatikusan születő papírozás-feladat ez alapján tudja,
   hogy egy projekthez már készített egyet (lásd
   services/papirozas_feladatok.py).

Revision ID: 1f535034bcb3
Revises: 4571c059cbef
Create Date: 2026-08-07 09:05:11.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1f535034bcb3'
down_revision: Union[str, Sequence[str], None] = '4571c059cbef'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("contracts", sa.Column("aktiv", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_table(
        "contract_periods",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("contract_id", sa.Integer(), nullable=False),
        # Nyitott kezdet = "a kezdetektől", nyitott vég = "azóta is él".
        sa.Column("kezdet", sa.Date(), nullable=True),
        sa.Column("veg", sa.Date(), nullable=True),
        sa.Column("megjegyzes", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["contract_id"], ["contracts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_contract_periods_contract_id", "contract_periods", ["contract_id"])
    op.add_column("employees", sa.Column("tovabbi_szerepkorok", sa.JSON(), nullable=True))
    op.add_column("tasks", sa.Column("project_id", sa.Integer(), nullable=True))
    op.create_foreign_key("tasks_project_id_fkey", "tasks", "projects", ["project_id"], ["id"])
    op.create_index("ix_tasks_project_id", "tasks", ["project_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_tasks_project_id", table_name="tasks")
    op.drop_constraint("tasks_project_id_fkey", "tasks", type_="foreignkey")
    op.drop_column("tasks", "project_id")
    op.drop_column("employees", "tovabbi_szerepkorok")
    op.drop_index("ix_contract_periods_contract_id", table_name="contract_periods")
    op.drop_table("contract_periods")
    op.drop_column("contracts", "aktiv")
