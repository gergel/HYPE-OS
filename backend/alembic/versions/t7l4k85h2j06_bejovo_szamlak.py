"""Beérkező számlák: érkeztető-piszkozatok és a feldolgozott levelek naplója.

A számla e-mailben (szamla@hypestab.hu) vagy az AI Assistantba dobva érkezik,
a rendszer kiolvassa és besorolási javaslattal, tartósan mentett piszkozatként
teszi az ellenőrző elé - a tényleges pénzügyi rekord csak a jóváhagyáskor jön
létre (lásd models/bejovo_szamla.py és services/szamla_erkeztetes.py).

Revision ID: t7l4k85h2j06
Revises: s6k3j74g1i95
Create Date: 2026-09-12
"""

from alembic import op
import sqlalchemy as sa

revision = "t7l4k85h2j06"
down_revision = "s6k3j74g1i95"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bejovo_szamlak",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("forras", sa.String(20), nullable=False, server_default="kezi"),
        sa.Column("allapot", sa.String(20), nullable=False, server_default="feldolgozas", index=True),
        sa.Column("hiba_uzenet", sa.Text()),
        sa.Column("fajl_nev", sa.String(255)),
        sa.Column("storage_key", sa.String(500)),
        sa.Column("url", sa.String(500)),
        sa.Column("content_type", sa.String(100)),
        sa.Column("meret_bajt", sa.Integer()),
        sa.Column("fajl_hash", sa.String(64), index=True),
        sa.Column(
            "valtozat_szamla_id",
            sa.Integer(),
            sa.ForeignKey("bejovo_szamlak.id", ondelete="SET NULL"),
            index=True,
        ),
        sa.Column("email_uzenet_id", sa.String(300), index=True),
        sa.Column("email_felado", sa.String(300)),
        sa.Column("email_targy", sa.String(500)),
        sa.Column("email_beerkezes", sa.DateTime(timezone=True)),
        sa.Column("email_szoveg", sa.Text()),
        sa.Column("dokumentum_tipus", sa.String(30)),
        sa.Column("szamlaszam", sa.String(100), index=True),
        sa.Column("kibocsato_nev", sa.String(300)),
        sa.Column("kibocsato_adoszam", sa.String(50)),
        sa.Column("vevo_nev", sa.String(300)),
        sa.Column("vevo_adoszam", sa.String(50)),
        sa.Column("kiallitas_datuma", sa.Date()),
        sa.Column("teljesites_datuma", sa.Date()),
        sa.Column("fizetesi_hatarido", sa.Date()),
        sa.Column("netto", sa.Numeric(14, 2)),
        sa.Column("afa_osszeg", sa.Numeric(14, 2)),
        sa.Column("brutto", sa.Numeric(14, 2)),
        sa.Column("penznem", sa.String(3), nullable=False, server_default="HUF"),
        sa.Column("irany", sa.String(15)),
        sa.Column("kinyert", sa.JSON()),
        sa.Column("javaslat", sa.JSON()),
        sa.Column("felhasznaloi_utasitas", sa.Text()),
        sa.Column("cel_tipus", sa.String(30)),
        sa.Column("cel_project_code_id", sa.Integer(), sa.ForeignKey("project_codes.id", ondelete="SET NULL")),
        sa.Column("cel_project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="SET NULL")),
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
        sa.Column(
            "cel_kotelezettseg_idoszak_id",
            sa.Integer(),
            sa.ForeignKey("kotelezettseg_idoszakok.id", ondelete="SET NULL"),
        ),
        sa.Column("cel_auto_id", sa.Integer(), sa.ForeignKey("autok.id", ondelete="SET NULL")),
        sa.Column("cel_kp_forgalom_id", sa.Integer(), sa.ForeignKey("kp_forgalmak.id", ondelete="SET NULL")),
        sa.Column("cel_employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL")),
        sa.Column("letrehozo_employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL")),
        sa.Column("jovahagyo_employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL")),
        sa.Column("jovahagyva_at", sa.DateTime(timezone=True)),
        sa.Column("rogzitett_expense_id", sa.Integer(), sa.ForeignKey("expenses.id", ondelete="SET NULL")),
        sa.Column("rogzites_naplo", sa.JSON()),
        sa.Column("duplikatum_bejovo_id", sa.Integer(), sa.ForeignKey("bejovo_szamlak.id", ondelete="SET NULL")),
        sa.Column("duplikatum_megjegyzes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_table(
        "bejovo_emailek",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("gmail_uzenet_id", sa.String(300), nullable=False),
        sa.Column("felado", sa.String(300)),
        sa.Column("targy", sa.String(500)),
        sa.Column("beerkezes", sa.DateTime(timezone=True)),
        sa.Column("allapot", sa.String(30), nullable=False, server_default="feldolgozva"),
        sa.Column("megjegyzes", sa.Text()),
        sa.Column("letrehozott_szamla_db", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("gmail_uzenet_id", name="uq_bejovo_email_uzenet"),
    )


def downgrade() -> None:
    op.drop_table("bejovo_emailek")
    op.drop_table("bejovo_szamlak")
