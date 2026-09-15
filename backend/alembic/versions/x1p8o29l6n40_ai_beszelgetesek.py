"""AI Assistant: tartós beszélgetések, fájlok és művelet-napló.

Az asszisztens műveleti végrehajtásának alapjai (a felhasználó kérése):
- ai_beszelgetesek: folytatható beszélgetés-szálak;
- ai_uzenetek: üzenetek + folyamat-események + kártyák;
- ai_fajlok: a chathez csatolt fájlok (R2-hivatkozással);
- ai_muveletek: minden írás naplója + függő jóváhagyások + idempotencia.

Revision ID: x1p8o29l6n40
Revises: w0o7n18k5m39
Create Date: 2026-09-15
"""

from alembic import op
import sqlalchemy as sa

revision = "x1p8o29l6n40"
down_revision = "w0o7n18k5m39"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_beszelgetesek",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cim", sa.String(200)),
        sa.Column("fut", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("leallitas_kert", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ai_beszelgetesek_employee_id", "ai_beszelgetesek", ["employee_id"])

    op.create_table(
        "ai_uzenetek",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("beszelgetes_id", sa.Integer(), sa.ForeignKey("ai_beszelgetesek.id", ondelete="CASCADE"), nullable=False),
        sa.Column("szerep", sa.String(20), nullable=False),
        sa.Column("szoveg", sa.Text()),
        sa.Column("adat", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ai_uzenetek_beszelgetes_id", "ai_uzenetek", ["beszelgetes_id"])

    op.create_table(
        "ai_fajlok",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("beszelgetes_id", sa.Integer(), sa.ForeignKey("ai_beszelgetesek.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fajl_nev", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100)),
        sa.Column("meret_bajt", sa.Integer()),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("url", sa.String(500)),
        sa.Column("felhasznalva", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ai_fajlok_beszelgetes_id", "ai_fajlok", ["beszelgetes_id"])

    op.create_table(
        "ai_muveletek",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("beszelgetes_id", sa.Integer(), sa.ForeignKey("ai_beszelgetesek.id", ondelete="CASCADE"), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL")),
        sa.Column("idempotencia_kulcs", sa.String(120)),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("path", sa.String(500), nullable=False),
        sa.Column("keres", sa.JSON()),
        sa.Column("osszefoglalo", sa.Text()),
        sa.Column("allapot", sa.String(20), nullable=False, server_default="fuggo"),
        sa.Column("valasz_status", sa.Integer()),
        sa.Column("valasz", sa.JSON()),
        sa.Column("vegrehajtva_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("beszelgetes_id", "idempotencia_kulcs", name="uq_ai_muvelet_idem"),
    )
    op.create_index("ix_ai_muveletek_beszelgetes_id", "ai_muveletek", ["beszelgetes_id"])
    op.create_index("ix_ai_muveletek_allapot", "ai_muveletek", ["allapot"])


def downgrade() -> None:
    op.drop_table("ai_muveletek")
    op.drop_table("ai_fajlok")
    op.drop_table("ai_uzenetek")
    op.drop_table("ai_beszelgetesek")
