"""Munkafelajánlások (ajánlatkérések): feladat + meghívottak + árajánlatok.

A folyamat: feladat -> külsősök meghívása személyes linkkel -> árajánlatok a
válaszadási határidőig -> belső kiválasztás a határidő UTÁN -> értesítések.
Senki nem kapja meg automatikusan a munkát (lásd models/munkafelajanlas.py).

Revision ID: z3r0q41n8p42
Revises: y2q9p30m7o41
"""

import sqlalchemy as sa
from alembic import op

revision = "z3r0q41n8p42"
down_revision = "y2q9p30m7o41"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ajanlatkeresek",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("projekt_nev", sa.String(length=255), nullable=False),
        sa.Column("munkakor", sa.String(length=255), nullable=False),
        sa.Column("leiras", sa.Text(), nullable=True),
        sa.Column("helyszin", sa.String(length=500), nullable=True),
        sa.Column("munkavegzes_idopont", sa.String(length=255), nullable=True),
        sa.Column("teljesitesi_hatarido", sa.String(length=255), nullable=True),
        sa.Column("valaszadasi_hatarido", sa.DateTime(), nullable=True),
        sa.Column("allapot", sa.String(length=30), nullable=False, server_default="piszkozat"),
        sa.Column("kapcsolattarto_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=True),
        sa.Column("letrehozta_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=True),
        # Szándékosan nem FK (körkörös függés lenne a meghívott-táblával) -
        # az épséget a zárolt kiválasztás-művelet tartja.
        sa.Column("nyertes_meghivott_id", sa.Integer(), nullable=True),
        sa.Column("elfogadott_osszeg", sa.Numeric(14, 2), nullable=True),
        sa.Column("elfogadott_penznem", sa.String(length=10), nullable=True),
        sa.Column("elfogadott_brutto", sa.Boolean(), nullable=True),
        sa.Column("lezarva", sa.DateTime(), nullable=True),
        sa.Column("lezaras_megjegyzes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "ajanlat_meghivottak",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "ajanlatkeres_id", sa.Integer(), sa.ForeignKey("ajanlatkeresek.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("email_cim", sa.String(length=255), nullable=True),
        sa.Column("meghivo_kikuldve", sa.DateTime(), nullable=True),
        sa.Column("meghivo_hiba", sa.Text(), nullable=True),
        sa.Column("eredmeny_kikuldve", sa.DateTime(), nullable=True),
        sa.Column("eredmeny_hiba", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("ajanlatkeres_id", "employee_id", name="uq_ajanlat_meghivott"),
    )
    op.create_index("ix_ajanlat_meghivottak_token", "ajanlat_meghivottak", ["token"], unique=True)
    op.create_table(
        "munka_arajanlatok",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "meghivott_id",
            sa.Integer(),
            sa.ForeignKey("ajanlat_meghivottak.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("osszeg", sa.Numeric(14, 2), nullable=False),
        sa.Column("penznem", sa.String(length=10), nullable=False, server_default="HUF"),
        sa.Column("brutto", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("megjegyzes", sa.Text(), nullable=True),
        sa.Column("vallalja", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("bekuldve", sa.DateTime(), nullable=True),
        sa.Column("modositva", sa.DateTime(), nullable=True),
        sa.Column("visszavonva", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("munka_arajanlatok")
    op.drop_index("ix_ajanlat_meghivottak_token", table_name="ajanlat_meghivottak")
    op.drop_table("ajanlat_meghivottak")
    op.drop_table("ajanlatkeresek")
