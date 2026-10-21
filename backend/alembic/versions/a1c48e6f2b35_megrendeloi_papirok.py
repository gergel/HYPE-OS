"""Megrendelői papírok: eseti szerződés és TIG + a projektkód kapcsolói

Két új tábla a MEGRENDELŐ felé menő papíroknak, és két kapcsoló a
projektkódon:

- `van_szerzodes`: van-e szerződés a projekt mögött. Ha van, kell hozzá
  megrendelői szerződés ÉS teljesítési igazolás. Alapértéke igaz - a szokásos
  eset az, hogy szerződünk, a kivételt kell jelölni.
- `papir_nelkul` + indok: a teljesítés ellenértéke nem pénzmozgással
  rendeződik (pl. a cégvezető be van jelentve a megrendelőhöz vállalkozóként,
  és annyival kevesebb fizetést vesz fel onnan). Ilyenkor a bevétel nem
  bejövő pénz, hanem el nem költött pénz - és papír sem tartozik hozzá.

Revision ID: a1c48e6f2b35
Revises: f3b8d05e7a91
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1c48e6f2b35"
down_revision: Union[str, Sequence[str], None] = "f3b8d05e7a91"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _papir_oszlopok() -> list[sa.Column]:
    """A két papírtábla azonos mezőkészlete - egy helyen, hogy ne csússzanak el."""
    return [
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_code_id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=True),
        sa.Column("keretszerzodes_id", sa.Integer(), nullable=True),
        sa.Column("contact_id", sa.Integer(), nullable=True),
        sa.Column("ceg_neve", sa.String(255), nullable=True),
        sa.Column("szekhely", sa.String(500), nullable=True),
        sa.Column("adoszam", sa.String(50), nullable=True),
        sa.Column("kepviselo", sa.String(255), nullable=True),
        sa.Column("nyilvantartasi_szam", sa.String(100), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("megbizas_targya", sa.String(255), nullable=True),
        sa.Column("projekt_nev", sa.String(255), nullable=True),
        sa.Column("teljesites_szoveg", sa.String(500), nullable=True),
        sa.Column("netto_osszeg", sa.Numeric(14, 2), nullable=True),
        sa.Column("plusz_afa", sa.Boolean(), nullable=True),
        sa.Column("keltezes", sa.Date(), nullable=True),
        sa.Column("allapot", sa.String(50), nullable=True),
        sa.Column("file_url", sa.String(500), nullable=True),
        sa.Column("file_storage_key", sa.String(500), nullable=True),
        sa.Column("alairt_file_url", sa.String(500), nullable=True),
        sa.Column("alairt_file_storage_key", sa.String(500), nullable=True),
        sa.Column("kihagyas_oka", sa.Text(), nullable=True),
        sa.Column("megjegyzes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
    ]


def _megkotesek() -> list:
    return [
        sa.ForeignKeyConstraint(["project_code_id"], ["project_codes.id"]),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
        sa.ForeignKeyConstraint(["keretszerzodes_id"], ["contracts.id"]),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"]),
        sa.PrimaryKeyConstraint("id"),
    ]


def upgrade() -> None:
    for tabla in ("megrendeloi_szerzodesek", "megrendeloi_tigek"):
        op.create_table(tabla, *_papir_oszlopok(), *_megkotesek())
        op.create_index(op.f(f"ix_{tabla}_project_code_id"), tabla, ["project_code_id"])

    op.add_column(
        "project_codes",
        sa.Column("van_szerzodes", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "project_codes",
        sa.Column("papir_nelkul", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("project_codes", sa.Column("papir_nelkul_indoka", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("project_codes", "papir_nelkul_indoka")
    op.drop_column("project_codes", "papir_nelkul")
    op.drop_column("project_codes", "van_szerzodes")
    op.drop_table("megrendeloi_tigek")
    op.drop_table("megrendeloi_szerzodesek")
