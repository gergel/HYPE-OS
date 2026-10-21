"""Per-person notification preferences."""
from alembic import op
import sqlalchemy as sa
revision = "hype_preferences_20260921"
down_revision = "hype_push_20260920"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("notification_preferences",
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("kind", sa.String(30), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()))

def downgrade():
    op.drop_table("notification_preferences")
