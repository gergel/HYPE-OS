"""Portál mappa: szülő-mappa (mappán belüli mappa).

A felhasználó kérése: a portálon mappán belülre is lehessen mappát tenni.
A szülő törlésekor a gyerek mappa a főszintre kerül (SET NULL), nem
törlődik vele.

Revision ID: h4e1f52a8c73
Revises: g3d9e41f7b62
Create Date: 2026-09-04
"""

import sqlalchemy as sa
from alembic import op

revision = "h4e1f52a8c73"
down_revision = "g3d9e41f7b62"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("portal_folders", sa.Column("parent_folder_id", sa.Integer(), nullable=True))
    op.create_index("ix_portal_folders_parent_folder_id", "portal_folders", ["parent_folder_id"])
    op.create_foreign_key(
        "fk_portal_folders_parent",
        "portal_folders",
        "portal_folders",
        ["parent_folder_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_portal_folders_parent", "portal_folders", type_="foreignkey")
    op.drop_index("ix_portal_folders_parent_folder_id", table_name="portal_folders")
    op.drop_column("portal_folders", "parent_folder_id")
