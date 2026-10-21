"""contract tig projektkod forgatas nelkul

Revision ID: 73200ef6946b
Revises: 9cd16b5f721b
Create Date: 2026-08-28 16:00:00.000000

Forgatás nélküli (tisztán ügynökségi feladatra szóló) alvállalkozói eseti
szerződés és TIG a projektkódhoz köthető, nem csak egy konkrét Projecthez:

- contracts.project_code_id (új, nullable) - a project_id és a
  project_code_id közül egyszerre csak az egyik van kitöltve.
- performance_certificates.project_id NOT NULL -> nullable, és
  performance_certificates.project_code_id (új, nullable) ugyanazzal a
  szabállyal.

Lásd models/contract.py Contract.project_code_id és
models/performance_certificate.py PerformanceCertificate.project_code_id.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "73200ef6946b"
down_revision: Union[str, None] = "9cd16b5f721b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("contracts", sa.Column("project_code_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "contracts_project_code_id_fkey", "contracts", "project_codes", ["project_code_id"], ["id"]
    )

    op.alter_column("performance_certificates", "project_id", existing_type=sa.Integer(), nullable=True)
    op.add_column("performance_certificates", sa.Column("project_code_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "performance_certificates_project_code_id_fkey",
        "performance_certificates",
        "project_codes",
        ["project_code_id"],
        ["id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "performance_certificates_project_code_id_fkey", "performance_certificates", type_="foreignkey"
    )
    op.drop_column("performance_certificates", "project_code_id")
    op.alter_column("performance_certificates", "project_id", existing_type=sa.Integer(), nullable=False)

    op.drop_constraint("contracts_project_code_id_fkey", "contracts", type_="foreignkey")
    op.drop_column("contracts", "project_code_id")
