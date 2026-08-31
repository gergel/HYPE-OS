"""Portál: feltöltő link + mappa/videó megosztó linkek.

- portals.feltolto_token (+feltolto_folder_id): aki a linket kapja, mappát
  hozhat létre és feltölthet (a portálra vagy csak a megadott mappába), de
  nem törölhet;
- portal_folders.share_token / portal_videos.share_token: egyetlen mappa
  vagy egyetlen videó osztható meg linkkel - a link birtokosa csak azt látja.

Revision ID: a7d9e35c1f82
Revises: f4b6d28a9c53
Create Date: 2026-08-31
"""

import sqlalchemy as sa
from alembic import op

revision = "a7d9e35c1f82"
down_revision = "f4b6d28a9c53"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("portals", sa.Column("feltolto_token", sa.String(length=64), nullable=True))
    op.create_unique_constraint("uq_portals_feltolto_token", "portals", ["feltolto_token"])
    op.add_column("portals", sa.Column("feltolto_folder_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_portals_feltolto_folder",
        "portals",
        "portal_folders",
        ["feltolto_folder_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column("portal_folders", sa.Column("share_token", sa.String(length=64), nullable=True))
    op.create_unique_constraint("uq_portal_folders_share_token", "portal_folders", ["share_token"])
    op.add_column("portal_videos", sa.Column("share_token", sa.String(length=64), nullable=True))
    op.create_unique_constraint("uq_portal_videos_share_token", "portal_videos", ["share_token"])


def downgrade() -> None:
    op.drop_constraint("uq_portal_videos_share_token", "portal_videos", type_="unique")
    op.drop_column("portal_videos", "share_token")
    op.drop_constraint("uq_portal_folders_share_token", "portal_folders", type_="unique")
    op.drop_column("portal_folders", "share_token")
    op.drop_constraint("fk_portals_feltolto_folder", "portals", type_="foreignkey")
    op.drop_column("portals", "feltolto_folder_id")
    op.drop_constraint("uq_portals_feltolto_token", "portals", type_="unique")
    op.drop_column("portals", "feltolto_token")
