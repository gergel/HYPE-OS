"""employee documents table replaces munkaszerzodes url

Revision ID: 268cc84003f1
Revises: e5bbcbeac48b
Create Date: 2026-07-07 08:13:59.202774

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '268cc84003f1'
down_revision: Union[str, Sequence[str], None] = 'e5bbcbeac48b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "employee_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.drop_column("employees", "munkaszerzodes_url")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column("employees", sa.Column("munkaszerzodes_url", sa.String(length=500), nullable=True))
    op.drop_table("employee_documents")
