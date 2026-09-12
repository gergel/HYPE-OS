"""Utalások felvezetése: elutalt számlacsomag (ZIP) adminisztrálása.

Egy adag = egy feltöltött ZIP a KÖZÖS utalási dátummal; a tételek a felismert
számlák a megtalált céllal (kiadás / külsős TIG / belsős TIG / új kiadás), a
HYPE/Krumpello elszámolási hellyel és a rögzítés naplójával (lásd
models/utalas_felvezetes.py és services/utalas_felvezetes.py).

Revision ID: u8m5l96i3k17
Revises: t7l4k85h2j06
Create Date: 2026-09-12
"""

from alembic import op
import sqlalchemy as sa

revision = "u8m5l96i3k17"
down_revision = "t7l4k85h2j06"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "utalas_adagok",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nev", sa.String(200)),
        sa.Column("megjegyzes", sa.Text()),
        sa.Column("utalas_datum", sa.Date(), nullable=False),
        sa.Column("zip_fajl_nev", sa.String(255)),
        sa.Column("allapot", sa.String(30), nullable=False, server_default="feldolgozas"),
        sa.Column("hiba_uzenet", sa.Text()),
        sa.Column("fajl_darab", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("kihagyott_fajlok", sa.JSON()),
        sa.Column("letrehozo_employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_table(
        "utalas_tetelek",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "adag_id",
            sa.Integer(),
            sa.ForeignKey("utalas_adagok.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("fajl_nev", sa.String(255)),
        sa.Column("fajl_utvonal", sa.String(500)),
        sa.Column("content_type", sa.String(100)),
        sa.Column("meret_bajt", sa.Integer()),
        sa.Column("fajl_hash", sa.String(64), index=True),
        sa.Column("storage_key", sa.String(500)),
        sa.Column("url", sa.String(500)),
        sa.Column("kinyert", sa.JSON()),
        sa.Column("dokumentum_tipus", sa.String(30)),
        sa.Column("szamlaszam", sa.String(100), index=True),
        sa.Column("kibocsato_nev", sa.String(300)),
        sa.Column("kibocsato_adoszam", sa.String(50)),
        sa.Column("vevo_nev", sa.String(300)),
        sa.Column("netto", sa.Numeric(14, 2)),
        sa.Column("brutto", sa.Numeric(14, 2)),
        sa.Column("penznem", sa.String(10), nullable=False, server_default="HUF"),
        sa.Column("kiallitas_datuma", sa.Date()),
        sa.Column("teljesites_datuma", sa.Date()),
        sa.Column("fizetesi_hatarido", sa.Date()),
        sa.Column("allapot", sa.String(30), nullable=False, server_default="feldolgozas", index=True),
        sa.Column("hiba_uzenet", sa.Text()),
        sa.Column("elszamolas", sa.String(20), nullable=False, server_default="tisztazando"),
        sa.Column("cel_tipus", sa.String(30)),
        sa.Column("cel_expense_id", sa.Integer(), sa.ForeignKey("expenses.id", ondelete="SET NULL")),
        sa.Column(
            "cel_certificate_id",
            sa.Integer(),
            sa.ForeignKey("performance_certificates.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "cel_internal_certificate_id",
            sa.Integer(),
            sa.ForeignKey("internal_performance_certificates.id", ondelete="SET NULL"),
        ),
        sa.Column("uj_kiadas", sa.JSON()),
        sa.Column("javaslat", sa.JSON()),
        sa.Column("utalas_datum", sa.Date()),
        sa.Column("osszeg_elteres_elfogadva", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("duplikatum_tetel_id", sa.Integer(), sa.ForeignKey("utalas_tetelek.id", ondelete="SET NULL")),
        sa.Column("rogzitve_at", sa.DateTime(timezone=True)),
        sa.Column("rogzito_employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL")),
        sa.Column("rogzites_naplo", sa.JSON()),
        sa.Column("visszavonva_at", sa.DateTime(timezone=True)),
        sa.Column("visszavono_employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("utalas_tetelek")
    op.drop_table("utalas_adagok")
