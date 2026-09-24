"""Lara: beszélgetés + a tudás visszakövethetősége + szakmai eval-esetek.

A 2026-09 fejlesztés (lásd docs/admin-agent/lara-fejlesztes-2026-09.md):

- `aa_memory_chunks`: a tudás fajtája, bizonyíték-szintje, hatóköre,
  érvényessége, verziója, jóváhagyója, üzleti ügye, felhasználása és a
  használhatóvá válás ideje. Minden új oszlop üres vagy alapértékes: a
  meglévő tudás VÁLTOZATLAN marad (nincs adat-átírás).
- `aa_eval_cases`: szabályverzióhoz kötött szakmai esetek jelölése.
- `aa_beszelgetesek` / `aa_beszelgetes_uzenetek`: a „Kérdezz Larától”
  felület beszélgetései.

Csak additív, visszafordítható séma-módosítás.

Revision ID: q0k7h18e5f29
Revises: p9j6g07d4e18
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "q0k7h18e5f29"
down_revision = "p9j6g07d4e18"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("aa_memory_chunks", sa.Column("tudas_fajta", sa.String(30), nullable=True))
    op.create_index("ix_aa_memory_chunks_tudas_fajta", "aa_memory_chunks", ["tudas_fajta"])
    op.add_column("aa_memory_chunks", sa.Column("bizonyitek_szint", sa.String(20), nullable=True))
    op.add_column("aa_memory_chunks", sa.Column("hatokor_reszletek", JSONB(), nullable=True))
    op.add_column("aa_memory_chunks", sa.Column("ervenyes_tol", sa.DateTime(timezone=True), nullable=True))
    op.add_column("aa_memory_chunks", sa.Column("ervenyes_ig", sa.DateTime(timezone=True), nullable=True))
    op.add_column("aa_memory_chunks", sa.Column("verzio", sa.Integer(), nullable=False, server_default="1"))
    op.add_column(
        "aa_memory_chunks",
        sa.Column(
            "elozo_verzio_id", sa.Integer(), sa.ForeignKey("aa_memory_chunks.id", ondelete="SET NULL"), nullable=True
        ),
    )
    op.add_column(
        "aa_memory_chunks",
        sa.Column("jovahagyta_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True),
    )
    op.add_column("aa_memory_chunks", sa.Column("jovahagyva_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("aa_memory_chunks", sa.Column("felhasznalhato_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("aa_memory_chunks", sa.Column("ugy_kulcs", sa.String(200), nullable=True))
    op.create_index("ix_aa_memory_chunks_ugy_kulcs", "aa_memory_chunks", ["ugy_kulcs"])
    op.add_column("aa_memory_chunks", sa.Column("felhasznalva_db", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("aa_memory_chunks", sa.Column("utolso_felhasznalas_at", sa.DateTime(timezone=True), nullable=True))

    op.add_column(
        "aa_eval_cases",
        sa.Column(
            "szabaly_id", sa.Integer(), sa.ForeignKey("aa_playbook_rules.id", ondelete="CASCADE"), nullable=True
        ),
    )
    op.create_index("ix_aa_eval_cases_szabaly_id", "aa_eval_cases", ["szabaly_id"])
    op.add_column("aa_eval_cases", sa.Column("szabaly_verzio", sa.Integer(), nullable=True))
    op.add_column("aa_eval_cases", sa.Column("eset_fajta", sa.String(20), nullable=True))

    op.create_table(
        "aa_beszelgetesek",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cim", sa.String(200), nullable=False, server_default="Új beszélgetés"),
        sa.Column("mod", sa.String(20), nullable=False, server_default="kerdez"),
        sa.Column("osszefoglalo", sa.Text(), nullable=True),
        sa.Column("archivalva", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_aa_beszelgetesek_employee_id", "aa_beszelgetesek", ["employee_id"])
    op.create_table(
        "aa_beszelgetes_uzenetek",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "beszelgetes_id", sa.Integer(), sa.ForeignKey("aa_beszelgetesek.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("szerep", sa.String(20), nullable=False),
        sa.Column("szoveg", sa.Text(), nullable=False),
        sa.Column("adat", JSONB(), nullable=True),
        sa.Column("ertekeles", sa.String(20), nullable=True),
        sa.Column("ertekeles_megjegyzes", sa.Text(), nullable=True),
        sa.Column("ertekelve_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_aa_beszelgetes_uzenetek_beszelgetes_id", "aa_beszelgetes_uzenetek", ["beszelgetes_id"])


def downgrade() -> None:
    op.drop_index("ix_aa_beszelgetes_uzenetek_beszelgetes_id", table_name="aa_beszelgetes_uzenetek")
    op.drop_table("aa_beszelgetes_uzenetek")
    op.drop_index("ix_aa_beszelgetesek_employee_id", table_name="aa_beszelgetesek")
    op.drop_table("aa_beszelgetesek")
    op.drop_column("aa_eval_cases", "eset_fajta")
    op.drop_column("aa_eval_cases", "szabaly_verzio")
    op.drop_index("ix_aa_eval_cases_szabaly_id", table_name="aa_eval_cases")
    op.drop_column("aa_eval_cases", "szabaly_id")
    for oszlop in (
        "utolso_felhasznalas_at", "felhasznalva_db", "felhasznalhato_at", "jovahagyva_at", "jovahagyta_id",
        "elozo_verzio_id", "verzio", "ervenyes_ig", "ervenyes_tol", "hatokor_reszletek", "bizonyitek_szint",
    ):
        op.drop_column("aa_memory_chunks", oszlop)
    op.drop_index("ix_aa_memory_chunks_ugy_kulcs", table_name="aa_memory_chunks")
    op.drop_column("aa_memory_chunks", "ugy_kulcs")
    op.drop_index("ix_aa_memory_chunks_tudas_fajta", table_name="aa_memory_chunks")
    op.drop_column("aa_memory_chunks", "tudas_fajta")
