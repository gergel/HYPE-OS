"""Állapothoz kötött automatikus kiosztás az utómunkán.

A deliverable_status_configs új oszlopa mondja meg, hogy egy állapotba
kerülő anyagot kikre kell automatikusan kiosztani (pl. Ellenőrzés/Beérkező
-> az ellenőr, Kiküldhető -> akik kiküldik). A lista a "Nézet beállítása"
panelen szerkeszthető - a konkrét embereket ott kell megadni, mert a
rendszer névből nem találhatja ki biztonságosan, ki kicsoda.

Revision ID: e2b7c94f1a58
Revises: c9f4a62d8e13
Create Date: 2026-08-31
"""

import sqlalchemy as sa
from alembic import op

revision = "e2b7c94f1a58"
down_revision = "c9f4a62d8e13"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("deliverable_status_configs", sa.Column("auto_kiosztott_employee_ids", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("deliverable_status_configs", "auto_kiosztott_employee_ids")
