"""Lara tanulási/értékelési táblák (Fázis F): memory_chunks, eval_cases,
eval_runs, learning_runs, agent_releases, outbox. Additív; nem bánt meglévő
táblát. Az embedding pgvector NÉLKÜL is működik (JSONB), a keresés fallbackje
pontos/szöveges (lásd admin_agent/memory.py).

Revision ID: h1b8y29v6w50
Revises: g0a7x18u5v49
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "h1b8y29v6w50"
down_revision = "g0a7x18u5v49"
branch_labels = None
depends_on = None


def _ts_cols():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    ]


def upgrade() -> None:
    op.create_table(
        "aa_agent_releases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("verzio", sa.String(40), nullable=False),
        sa.Column("tipus", sa.String(20), nullable=False, server_default="rules"),
        sa.Column("leiras", sa.Text(), nullable=True),
        sa.Column("config", JSONB(), nullable=True),
        sa.Column("allapot", sa.String(20), nullable=False, server_default="jelolt", index=True),
        sa.Column("eval_run_id", sa.Integer(), nullable=True),
        sa.Column("aktivalta_employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True),
        sa.Column("aktivalva_at", sa.DateTime(timezone=True), nullable=True),
        *_ts_cols(),
    )
    op.create_table(
        "aa_eval_cases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nev", sa.String(200), nullable=False),
        sa.Column("tipus", sa.String(30), nullable=False, index=True),
        sa.Column("altipus", sa.String(60), nullable=True),
        sa.Column("bemenet", JSONB(), nullable=False),
        sa.Column("elvart", JSONB(), nullable=True),
        sa.Column("halmaz", sa.String(20), nullable=False, server_default="szintetikus", index=True),
        sa.Column("forras", sa.String(120), nullable=True),
        sa.Column("ervenyes", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_ts_cols(),
    )
    op.create_table(
        "aa_eval_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("release_id", sa.Integer(), sa.ForeignKey("aa_agent_releases.id", ondelete="SET NULL"), nullable=True),
        sa.Column("allapot", sa.String(20), nullable=False, server_default="futott"),
        sa.Column("osszes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sikeres", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("kritikus_hiba", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("atment", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("eredmeny", JSONB(), nullable=True),
        sa.Column("kezdes_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("veg_at", sa.DateTime(timezone=True), nullable=True),
        *_ts_cols(),
    )
    op.create_table(
        "aa_learning_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("trigger", sa.String(40), nullable=False, server_default="manual"),
        sa.Column("allapot", sa.String(20), nullable=False, server_default="futott"),
        sa.Column("feldolgozott_korrekciok", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("uj_szabaly_jeloltek", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("uj_pelda_jeloltek", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sop_keresek", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("kurzor", sa.String(60), nullable=True),
        sa.Column("osszefoglalo", JSONB(), nullable=True),
        sa.Column("kezdes_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("veg_at", sa.DateTime(timezone=True), nullable=True),
        *_ts_cols(),
    )
    op.create_table(
        "aa_memory_chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("hatokor", sa.String(60), nullable=False, index=True),
        sa.Column("tartalom", sa.Text(), nullable=False),
        sa.Column("forras", sa.String(120), nullable=True),
        sa.Column("forras_verzio", sa.String(120), nullable=True),
        sa.Column("minosites", sa.String(20), nullable=False, server_default="jovahagyott"),
        sa.Column("tanulasi_halmaz", sa.String(20), nullable=False, server_default="jovahagyott", index=True),
        sa.Column("embedding", JSONB(), nullable=True),
        sa.Column("embedding_modell", sa.String(120), nullable=True),
        sa.Column("embedding_dim", sa.Integer(), nullable=True),
        sa.Column("ervenyes", sa.Boolean(), nullable=False, server_default=sa.true(), index=True),
        sa.Column("visszavont", sa.Boolean(), nullable=False, server_default=sa.false()),
        *_ts_cols(),
    )
    op.create_table(
        "aa_outbox",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("esemeny_tipus", sa.String(60), nullable=False, index=True),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("allapot", sa.String(20), nullable=False, server_default="pending", index=True),
        sa.Column("probalkozasok", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("kovetkezo_probalkozas_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("kulso_azonosito", sa.String(255), nullable=True),
        sa.Column("hiba", sa.Text(), nullable=True),
        sa.Column("feldolgozva_at", sa.DateTime(timezone=True), nullable=True),
        *_ts_cols(),
    )


def downgrade() -> None:
    for t in ("aa_outbox", "aa_memory_chunks", "aa_learning_runs", "aa_eval_runs", "aa_eval_cases", "aa_agent_releases"):
        op.drop_table(t)
