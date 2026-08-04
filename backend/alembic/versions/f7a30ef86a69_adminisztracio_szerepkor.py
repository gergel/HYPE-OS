"""adminisztracio szerepkor

Revision ID: f7a30ef86a69
Revises: 47f2025091fb
Create Date: 2026-08-04 11:01:20.759674

Új szerepkör: "adminisztracio" - aki a projektek teljes papírozásáért felel
(belsős TIG, külsős TIG + alvállalkozói szerződés, megrendelői szerződés +
TIG). A dashboard "Teendőim" widgete nekik külön felhozza a hiányzó papírokat
(lásd routes/dashboard.py _papirozas_tasks).

A downgrade nem tudja egyszerűen eltávolítani az értéket a Postgres enum
típusból (ALTER TYPE ... DROP VALUE nem létezik), ezért a típust újraépíti - az
addigra adminisztrációs szerepkört kapott munkatársak "operator"-ra esnek
vissza, ami a rendszer alapértelmezett szerepköre.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f7a30ef86a69'
down_revision: Union[str, Sequence[str], None] = '47f2025091fb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Az ALTER TYPE ... ADD VALUE nem futhat tranzakcióblokkban a régebbi
    # Postgres-eken, ezért COMMIT-tal zárjuk az alembic által nyitott
    # tranzakciót. Az IF NOT EXISTS miatt újrafuttatva sem hibázik.
    op.execute("COMMIT")
    op.execute("ALTER TYPE system_role ADD VALUE IF NOT EXISTS 'adminisztracio'")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("UPDATE employees SET role = 'operator' WHERE role = 'adminisztracio'")
    op.execute("ALTER TYPE system_role RENAME TO system_role_regi")
    op.execute("CREATE TYPE system_role AS ENUM ('admin', 'operator', 'vago', 'ugyfel')")
    op.execute(
        "ALTER TABLE employees ALTER COLUMN role TYPE system_role USING role::text::system_role"
    )
    op.execute("DROP TYPE system_role_regi")
