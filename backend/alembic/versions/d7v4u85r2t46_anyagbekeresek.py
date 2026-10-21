"""Anyagbekérő és kreatív brief táblái (a felhasználó kérése) - lásd
models/anyagbekeres.py: bekérés, beküldői leadás, mappa, fájl+feltöltési
munkamenet, videóigény, igény-forrás kapcsolat, esemény-napló, ZIP-export.

Revision ID: d7v4u85r2t46
Revises: c6u3t74q1s45
"""

import sqlalchemy as sa
from alembic import op

revision = "d7v4u85r2t46"
down_revision = "c6u3t74q1s45"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "anyagbekeresek",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nev", sa.String(255), nullable=False),
        sa.Column("udvozlo_szoveg", sa.Text(), nullable=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id", ondelete="SET NULL"), nullable=True),
        sa.Column("partner_nev", sa.String(255), nullable=True),
        sa.Column("hatarido", sa.DateTime(), nullable=True),
        sa.Column("felelos_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True),
        sa.Column("letrehozta_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True),
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column("jelszo_hash", sa.String(255), nullable=True),
        sa.Column("link_lejarat", sa.DateTime(), nullable=True),
        sa.Column("allapot", sa.String(20), nullable=False, server_default="nyitott"),
        sa.Column("kell_brief", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("meret_keret_bajt", sa.BigInteger(), nullable=True),
        sa.Column("engedett_tipusok", sa.String(500), nullable=True),
        sa.Column("elore_mappak", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_anyagbekeresek_token", "anyagbekeresek", ["token"], unique=True)
    op.create_index("ix_anyagbekeresek_project_id", "anyagbekeresek", ["project_id"])

    op.create_table(
        "anyag_leadasok",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "anyagbekeres_id", sa.Integer(), sa.ForeignKey("anyagbekeresek.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column("bekuldo_nev", sa.String(255), nullable=False),
        sa.Column("bekuldo_email", sa.String(255), nullable=False),
        sa.Column("bekuldo_ceg", sa.String(255), nullable=True),
        sa.Column("allapot", sa.String(20), nullable=False, server_default="piszkozat"),
        sa.Column("leadva_at", sa.DateTime(), nullable=True),
        sa.Column("felelos_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True),
        sa.Column("belso_megjegyzes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_anyag_leadasok_bekeres", "anyag_leadasok", ["anyagbekeres_id"])
    op.create_index("ix_anyag_leadasok_token", "anyag_leadasok", ["token"], unique=True)

    op.create_table(
        "anyag_mappak",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("leadas_id", sa.Integer(), sa.ForeignKey("anyag_leadasok.id", ondelete="CASCADE"), nullable=False),
        sa.Column("szulo_id", sa.Integer(), sa.ForeignKey("anyag_mappak.id", ondelete="CASCADE"), nullable=True),
        sa.Column("nev", sa.String(255), nullable=False),
        sa.Column("utvonal", sa.String(1000), nullable=False),
        sa.Column("leiras", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("leadas_id", "utvonal", name="uq_anyag_mappa_utvonal"),
    )
    op.create_index("ix_anyag_mappak_leadas", "anyag_mappak", ["leadas_id"])

    op.create_table(
        "anyag_fajlok",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("leadas_id", sa.Integer(), sa.ForeignKey("anyag_leadasok.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mappa_id", sa.Integer(), sa.ForeignKey("anyag_mappak.id", ondelete="SET NULL"), nullable=True),
        sa.Column("eredeti_nev", sa.String(500), nullable=False),
        sa.Column("relativ_utvonal", sa.String(1200), nullable=True),
        sa.Column("storage_key", sa.String(600), nullable=False),
        sa.Column("meret_bajt", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("content_type", sa.String(255), nullable=True),
        sa.Column("allapot", sa.String(20), nullable=False, server_default="feltoltes_alatt"),
        sa.Column("upload_id", sa.String(255), nullable=True),
        sa.Column("kesz_reszek", sa.JSON(), nullable=True),
        sa.Column("kesz_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_anyag_fajlok_leadas", "anyag_fajlok", ["leadas_id"])
    op.create_index("ix_anyag_fajlok_mappa", "anyag_fajlok", ["mappa_id"])
    op.create_index("ix_anyag_fajlok_allapot", "anyag_fajlok", ["allapot"])

    op.create_table(
        "video_igenyek",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("leadas_id", sa.Integer(), sa.ForeignKey("anyag_leadasok.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sorrend", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("nev", sa.String(255), nullable=False),
        sa.Column("leiras", sa.Text(), nullable=True),
        sa.Column("hossz", sa.String(120), nullable=True),
        sa.Column("felulet", sa.String(255), nullable=True),
        sa.Column("keparany", sa.String(30), nullable=True),
        sa.Column("hatarido", sa.DateTime(), nullable=True),
        sa.Column("teljes_anyagbol", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reszletek", sa.JSON(), nullable=True),
        sa.Column("idokodok", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_video_igenyek_leadas", "video_igenyek", ["leadas_id"])

    op.create_table(
        "video_igeny_forrasok",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("igeny_id", sa.Integer(), sa.ForeignKey("video_igenyek.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mappa_id", sa.Integer(), sa.ForeignKey("anyag_mappak.id", ondelete="CASCADE"), nullable=True),
        sa.Column("fajl_id", sa.Integer(), sa.ForeignKey("anyag_fajlok.id", ondelete="CASCADE"), nullable=True),
        sa.UniqueConstraint("igeny_id", "mappa_id", name="uq_igeny_mappa"),
        sa.UniqueConstraint("igeny_id", "fajl_id", name="uq_igeny_fajl"),
    )
    op.create_index("ix_video_igeny_forrasok_igeny", "video_igeny_forrasok", ["igeny_id"])
    op.create_index("ix_video_igeny_forrasok_mappa", "video_igeny_forrasok", ["mappa_id"])
    op.create_index("ix_video_igeny_forrasok_fajl", "video_igeny_forrasok", ["fajl_id"])

    op.create_table(
        "anyag_esemenyek",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "anyagbekeres_id", sa.Integer(), sa.ForeignKey("anyagbekeresek.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("leadas_id", sa.Integer(), sa.ForeignKey("anyag_leadasok.id", ondelete="CASCADE"), nullable=True),
        sa.Column("tipus", sa.String(50), nullable=False),
        sa.Column("adat", sa.JSON(), nullable=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_anyag_esemenyek_bekeres", "anyag_esemenyek", ["anyagbekeres_id"])

    op.create_table(
        "anyag_leadas_exportok",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("leadas_id", sa.Integer(), sa.ForeignKey("anyag_leadasok.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("filename", sa.String(240), nullable=False),
        sa.Column("object_key", sa.String(500), nullable=True),
        sa.Column("object_size", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("total_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("bytes_done", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("touched_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("fingerprint", name="uq_anyag_export_fingerprint"),
    )
    op.create_index("ix_anyag_exportok_leadas", "anyag_leadas_exportok", ["leadas_id"])
    op.create_index("ix_anyag_exportok_state", "anyag_leadas_exportok", ["state"])


def downgrade() -> None:
    op.drop_table("anyag_leadas_exportok")
    op.drop_table("anyag_esemenyek")
    op.drop_table("video_igeny_forrasok")
    op.drop_table("video_igenyek")
    op.drop_table("anyag_fajlok")
    op.drop_table("anyag_mappak")
    op.drop_table("anyag_leadasok")
    op.drop_table("anyagbekeresek")
