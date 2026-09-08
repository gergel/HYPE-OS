"""Durable portal exports; does not alter existing portal/media records."""
from alembic import op
import sqlalchemy as sa
revision = "l8c5d96e3f17"
down_revision = "k7b4c85d2f06"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("portal_exports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("portal_id", sa.Integer(), sa.ForeignKey("portals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False, unique=True),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("filename", sa.String(240), nullable=False),
        sa.Column("object_key", sa.String(500)),
        sa.Column("object_size", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(64)),
        sa.Column("total_bytes", sa.BigInteger(), nullable=False),
        sa.Column("bytes_done", sa.BigInteger(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("owner", sa.String(36)),
        sa.Column("error", sa.Text()),
        sa.Column("touched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)))
    op.create_index("ix_portal_exports_portal_id", "portal_exports", ["portal_id"])
    op.create_index("ix_portal_exports_state", "portal_exports", ["state"])

def downgrade():
    op.drop_table("portal_exports")
