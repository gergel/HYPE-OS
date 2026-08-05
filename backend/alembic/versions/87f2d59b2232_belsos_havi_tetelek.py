"""belsos havi tetelek

Egy belsős munkatárs havi juttatás-tételei: az alapbér és a hozzáadódó extrák
(túlóra, benzin, étkezés…), projekthez is köthetően. Ezekből számolódik a havi
Belsős TIG összege - lásd models/employee_monthly_item.py.

A meglévő TIG-eket NEM bontjuk fel tételekre: ott csak egy végösszeg van, és
nem tudjuk visszafejteni, miből állt össze. Azok maradnak úgy, ahogy vannak;
az új hónapok viszont már tételesen épülnek.

Revision ID: 87f2d59b2232
Revises: 6c7b340e83b9
Create Date: 2026-08-05 06:42:02.508867

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '87f2d59b2232'
down_revision: Union[str, Sequence[str], None] = '6c7b340e83b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "employee_monthly_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("ev", sa.Integer(), nullable=False, comment="Év, pl. 2026"),
        sa.Column("honap", sa.Integer(), nullable=False, comment="Hónap, 1-12"),
        sa.Column("tipus", sa.String(length=20), nullable=False, server_default="extra", comment="alapber | extra"),
        sa.Column("megnevezes", sa.String(length=255), nullable=False),
        sa.Column("osszeg", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("datum", sa.Date(), nullable=True, comment="A tétel napja a hónapon belül (opcionális)"),
        sa.Column("megjegyzes", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_employee_monthly_items_employee_honap",
        "employee_monthly_items",
        ["employee_id", "ev", "honap"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_employee_monthly_items_employee_honap", table_name="employee_monthly_items")
    op.drop_table("employee_monthly_items")
