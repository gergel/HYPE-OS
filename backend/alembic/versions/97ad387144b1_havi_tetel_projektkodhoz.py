"""havi tetel projektkodhoz

A havi tételek (túlóra, benzin…) mostantól PROJEKTKÓDHOZ kapcsolódnak, nem
egyetlen projekthez: egy projektkód alatt több forgatás is futhat, a költséget
viszont a projektkód szintjén tartjuk nyilván - ott áll össze a bevétel és a
kiadás is (lásd models/finance.py Expense.project_code_id).

A már felvitt tételek projektjét a projekt SAJÁT projektkódjára fordítjuk át,
hogy semmilyen hozzárendelés ne vesszen el.

Revision ID: 97ad387144b1
Revises: 87f2d59b2232
Create Date: 2026-08-05 07:25:00.761603

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '97ad387144b1'
down_revision: Union[str, Sequence[str], None] = '87f2d59b2232'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("employee_monthly_items", sa.Column("project_code_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_employee_monthly_items_project_code",
        "employee_monthly_items",
        "project_codes",
        ["project_code_id"],
        ["id"],
    )
    # A meglévő projekt-hozzárendelés átfordítása a projekt projektkódjára.
    op.execute(
        """
        UPDATE employee_monthly_items i
        SET project_code_id = p.project_code_id
        FROM projects p
        WHERE p.id = i.project_id AND i.project_id IS NOT NULL
        """
    )
    op.drop_column("employee_monthly_items", "project_id")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column("employee_monthly_items", sa.Column("project_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_employee_monthly_items_project", "employee_monthly_items", "projects", ["project_id"], ["id"]
    )
    # Visszafelé nem egyértelmű a leképezés (egy projektkód alatt több projekt
    # is lehet) - a projektkód ELSŐ projektjét vesszük, ez a legjobb közelítés.
    op.execute(
        """
        UPDATE employee_monthly_items i
        SET project_id = (
            SELECT p.id FROM projects p WHERE p.project_code_id = i.project_code_id ORDER BY p.id LIMIT 1
        )
        WHERE i.project_code_id IS NOT NULL
        """
    )
    op.drop_column("employee_monthly_items", "project_code_id")
