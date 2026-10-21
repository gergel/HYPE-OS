"""Strukturált számla-piszkozat, hiányzó dokumentumok utókövetése, audit-napló.

- `bejovo_szamlak`: az állapot-oszlop 20 -> 30 karakter (a
  `hianyzo_dokumentumok` állapot 20-nál hosszabb; a bővítés Postgresben csak
  metaadat-változás, a meglévő sorokhoz nem nyúl), valamint a strukturált
  piszkozat mezői (hivatkozott projektkód és forgatási nap, azonosított
  partner, fedező szerződés, érvényesítési eredmény). Minden új oszlop üres.
- `automatizalas_audit`: az automatikus műveletek és gépi adategyeztetések
  hozzáfűzhető naplója.
- `utokovetes_dokumentumok`: az utókövetési mátrix emlékeztető-adatai
  (darabszám, utolsó értesítés, állapot az értesítéskor).

Csak additív, visszafordítható séma-módosítás; adat-átírás nincs.

Revision ID: r1m8j29g6h40
Revises: q0k7h18e5f29
"""

import sqlalchemy as sa
from alembic import op

revision = "r1m8j29g6h40"
down_revision = "q0k7h18e5f29"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "bejovo_szamlak", "allapot", existing_type=sa.String(20), type_=sa.String(30), existing_nullable=False
    )
    op.add_column("bejovo_szamlak", sa.Column("hivatkozott_projektkod", sa.String(50), nullable=True))
    op.add_column("bejovo_szamlak", sa.Column("hivatkozott_forgatas_datuma", sa.Date(), nullable=True))
    op.add_column(
        "bejovo_szamlak",
        sa.Column(
            "partner_vallalkozas_id",
            sa.Integer(),
            sa.ForeignKey("vallalkozasok.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "bejovo_szamlak",
        sa.Column("partner_employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True),
    )
    op.add_column(
        "bejovo_szamlak",
        sa.Column("szerzodes_id", sa.Integer(), sa.ForeignKey("contracts.id", ondelete="SET NULL"), nullable=True),
    )
    op.add_column("bejovo_szamlak", sa.Column("validacio", sa.JSON(), nullable=True))

    op.create_table(
        "automatizalas_audit",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tortent_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("szereplo", sa.String(20), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True),
        sa.Column("muvelet", sa.String(60), nullable=False),
        sa.Column("eroforras_tipus", sa.String(40), nullable=False),
        sa.Column("eroforras_id", sa.Integer(), nullable=True),
        sa.Column("eredmeny", sa.String(20), nullable=False, server_default="ok"),
        sa.Column("reszletek", sa.JSON(), nullable=True),
    )
    op.create_index("ix_automatizalas_audit_tortent_at", "automatizalas_audit", ["tortent_at"])
    op.create_index("ix_automatizalas_audit_muvelet", "automatizalas_audit", ["muvelet"])
    op.create_index("ix_automatizalas_audit_eroforras", "automatizalas_audit", ["eroforras_tipus", "eroforras_id"])

    op.create_table(
        "utokovetes_dokumentumok",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("szamlazo_kulcs", sa.String(20), nullable=False),
        sa.Column("dokumentum_tipus", sa.String(20), nullable=False),
        sa.Column("emlekezteto_db", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("utolso_ertesites_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("utolso_ertesites_csatorna", sa.String(20), nullable=True),
        sa.Column("utolso_ertesites_megjegyzes", sa.Text(), nullable=True),
        sa.Column("allapot_ertesiteskor", sa.String(30), nullable=True),
        sa.Column(
            "utolso_ertesito_employee_id",
            sa.Integer(),
            sa.ForeignKey("employees.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("project_id", "szamlazo_kulcs", "dokumentum_tipus", name="uq_utokovetes_dokumentum"),
    )
    op.create_index("ix_utokovetes_dokumentumok_project_id", "utokovetes_dokumentumok", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_utokovetes_dokumentumok_project_id", table_name="utokovetes_dokumentumok")
    op.drop_table("utokovetes_dokumentumok")
    op.drop_index("ix_automatizalas_audit_eroforras", table_name="automatizalas_audit")
    op.drop_index("ix_automatizalas_audit_muvelet", table_name="automatizalas_audit")
    op.drop_index("ix_automatizalas_audit_tortent_at", table_name="automatizalas_audit")
    op.drop_table("automatizalas_audit")
    op.drop_column("bejovo_szamlak", "validacio")
    op.drop_column("bejovo_szamlak", "szerzodes_id")
    op.drop_column("bejovo_szamlak", "partner_employee_id")
    op.drop_column("bejovo_szamlak", "partner_vallalkozas_id")
    op.drop_column("bejovo_szamlak", "hivatkozott_forgatas_datuma")
    op.drop_column("bejovo_szamlak", "hivatkozott_projektkod")
    # A `hianyzo_dokumentumok` állapotú sorok visszalépés előtt "pontositas"
    # állapotba kerülnek, különben nem férnének a szűkebb oszlopba.
    op.execute("UPDATE bejovo_szamlak SET allapot = 'pontositas' WHERE length(allapot) > 20")
    op.alter_column(
        "bejovo_szamlak", "allapot", existing_type=sa.String(30), type_=sa.String(20), existing_nullable=False
    )
