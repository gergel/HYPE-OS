"""kiadas alvallalkozo projekt

Revision ID: 9cd16b5f721b
Revises: d3f40966c01f
Create Date: 2026-08-28 14:00:00.000000

Egy Kiadás mostantól jelölhető úgy, hogy egy konkrét forgatáshoz
(Project) köti az employee_id embert alvállalkozóként - tőle szerződés
és TIG is kell, de a projekt stábjába (project.crew) nem kerül be,
tehát a diszpó nem hívja be (lásd models/finance.py Expense.
alvallalkozo_project_id megjegyzése).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9cd16b5f721b"
down_revision: Union[str, None] = "d3f40966c01f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("expenses", sa.Column("alvallalkozo_project_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "expenses_alvallalkozo_project_id_fkey",
        "expenses",
        "projects",
        ["alvallalkozo_project_id"],
        ["id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("expenses_alvallalkozo_project_id_fkey", "expenses", type_="foreignkey")
    op.drop_column("expenses", "alvallalkozo_project_id")
