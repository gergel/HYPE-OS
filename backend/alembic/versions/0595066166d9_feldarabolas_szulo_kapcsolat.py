"""feldarabolas szulo kapcsolat

Revision ID: 0595066166d9
Revises: f7a30ef86a69
Create Date: 2026-08-04 11:16:57.679704

A több napos forgatásból leválasztott nap mostantól megjegyzi, melyik
projektből származik (lásd services/project_actions.create_feldarabolas).
Ebből tudja a rendszer, hogy darabolás után a NAPOT kell diszponálni, nem az
egész eseményt.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0595066166d9'
down_revision: Union[str, Sequence[str], None] = 'f7a30ef86a69'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'projects',
        sa.Column(
            'feldarabolas_szulo_id',
            sa.Integer(),
            nullable=True,
            comment='Melyik projektből lett leválasztva ez a nap',
        ),
    )
    op.create_foreign_key(
        'fk_projects_feldarabolas_szulo', 'projects', 'projects', ['feldarabolas_szulo_id'], ['id']
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_projects_feldarabolas_szulo', 'projects', type_='foreignkey')
    op.drop_column('projects', 'feldarabolas_szulo_id')
