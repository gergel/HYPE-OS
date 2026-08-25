"""project code comments

Revision ID: 3fe2fe8c20ce
Revises: c4a8e2f61b37
Create Date: 2026-08-25 12:00:00.000000

Hozzászólás-lehetőség a Project Code oldalakhoz - ugyanaz a chat-szerű minta,
mint az Utómunkánál (lásd models/deliverable_comment.py és
models/project_code_comment.py).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3fe2fe8c20ce"
down_revision: Union[str, None] = "c4a8e2f61b37"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "project_code_comments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_code_id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_code_id"], ["project_codes.id"]),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("project_code_comments")
