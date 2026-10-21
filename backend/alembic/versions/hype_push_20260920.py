"""iPhone notification devices and transactional delivery outbox."""
from alembic import op
import sqlalchemy as sa
revision = "hype_push_20260920"
down_revision = "e8w5v96s3u47"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("push_devices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token", sa.String(512), nullable=False),
        sa.Column("environment", sa.String(12), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("registered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("token", "environment", name="uq_push_token_environment"))
    op.create_index("ix_push_devices_employee_id", "push_devices", ["employee_id"])
    op.create_table("push_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("notification_id", sa.Integer(), sa.ForeignKey("notifications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_id", sa.Integer(), sa.ForeignKey("push_devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result", sa.String(40), nullable=True),
        sa.UniqueConstraint("notification_id", "device_id", name="uq_push_delivery"))
    for field in ["notification_id", "device_id", "next_attempt_at"]:
        op.create_index("ix_push_deliveries_" + field, "push_deliveries", [field])


def downgrade():
    op.drop_table("push_deliveries")
    op.drop_table("push_devices")
