"""Több feltöltő link portálonként (a felhasználó kérése): a portals-on ülő
egyetlen feltolto_token helyett külön portal_feltolto_linkek tábla - egy
portálon több link is élhet egyszerre, akár mappánként külön, és mindegyik
önállóan vonható vissza. A már kint lévő (kiküldött) linkek NEM halhatnak
meg: a meglévő tokeneket átmozgatjuk az új táblába.

Revision ID: l8c5d96e3a17
Revises: l8c5d96e3f17
Create Date: 2026-09-08
"""

import sqlalchemy as sa
from alembic import op

revision = "l8c5d96e3a17"
down_revision = "l8c5d96e3f17"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "portal_feltolto_linkek",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "portal_id",
            sa.Integer(),
            sa.ForeignKey("portals.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        # A mappa törlésekor a rá szűkített link is megszűnik (CASCADE) -
        # SET NULL itt veszélyes lenne: a szűkített link némán az EGÉSZ
        # portálra tágulna.
        sa.Column(
            "folder_id",
            sa.Integer(),
            sa.ForeignKey("portal_folders.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
        sa.Column("token", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    # A már kiadott linkek átmentése - a kint lévő címek tovább élnek.
    op.execute(
        """
        INSERT INTO portal_feltolto_linkek (portal_id, folder_id, token)
        SELECT id, feltolto_folder_id, feltolto_token
        FROM portals
        WHERE feltolto_token IS NOT NULL
        """
    )
    op.drop_column("portals", "feltolto_token")
    op.drop_column("portals", "feltolto_folder_id")


def downgrade() -> None:
    op.add_column("portals", sa.Column("feltolto_token", sa.String(64), nullable=True))
    op.add_column("portals", sa.Column("feltolto_folder_id", sa.Integer(), nullable=True))
    op.create_unique_constraint("uq_portals_feltolto_token", "portals", ["feltolto_token"])
    op.create_foreign_key(
        "fk_portals_feltolto_folder_id",
        "portals",
        "portal_folders",
        ["feltolto_folder_id"],
        ["id"],
        ondelete="SET NULL",
    )
    # Portálonként csak EGY link fér vissza a régi modellbe - a legrégebbit
    # (legkisebb id) tartjuk meg, a többi elveszik.
    op.execute(
        """
        UPDATE portals p
        SET feltolto_token = l.token, feltolto_folder_id = l.folder_id
        FROM (
            SELECT DISTINCT ON (portal_id) portal_id, token, folder_id
            FROM portal_feltolto_linkek
            ORDER BY portal_id, id
        ) l
        WHERE l.portal_id = p.id
        """
    )
    op.drop_table("portal_feltolto_linkek")
