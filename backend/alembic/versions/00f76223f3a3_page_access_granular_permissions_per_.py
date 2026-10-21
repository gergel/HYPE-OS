"""page access granular permissions per action

Revision ID: 00f76223f3a3
Revises: 97f6c63d7b1d
Create Date: 2026-07-06 08:08:43.877669

"""
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '00f76223f3a3'
down_revision: Union[str, Sequence[str], None] = '97f6c63d7b1d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FULL_ACCESS = ["view", "edit", "create", "delete"]


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('page_access_configs', sa.Column('page_permissions', sa.JSON(), nullable=True))

    # Meglévő sorok: a régi allowed_pages listát alakítjuk page_permissions
    # dict-té, minden benne szereplő oldalnak teljes (view+edit+create+delete)
    # jogot adva - ez pontosan ugyanaz a viselkedés, mint eddig volt (a régi
    # rendszer nem különböztetett meg műveleteket, csak láthatóságot).
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, allowed_pages FROM page_access_configs")).fetchall()
    for row in rows:
        if row.allowed_pages:
            perms = {page: FULL_ACCESS for page in row.allowed_pages}
            conn.execute(
                sa.text("UPDATE page_access_configs SET page_permissions = :perms WHERE id = :id"),
                {"perms": json.dumps(perms), "id": row.id},
            )

    op.drop_column('page_access_configs', 'allowed_pages')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('page_access_configs', sa.Column('allowed_pages', postgresql.JSON(astext_type=sa.Text()), autoincrement=False, nullable=True))

    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, page_permissions FROM page_access_configs")).fetchall()
    for row in rows:
        if row.page_permissions:
            pages = list(row.page_permissions.keys())
            conn.execute(
                sa.text("UPDATE page_access_configs SET allowed_pages = :pages WHERE id = :id"),
                {"pages": json.dumps(pages), "id": row.id},
            )

    op.drop_column('page_access_configs', 'page_permissions')
