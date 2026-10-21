"""mezokezeles: eltavolitott es sajat mezok

Revision ID: 47f2025091fb
Revises: f84bc9c23580
Create Date: 2026-08-04 09:42:23.632729

Három új tábla a mezőkezeléshez (lásd models/entity_field.py):

  * entity_field_configs - mely (Notionből áthozott) mezők lettek eltávolítva
    a rendszerből, ki és mikor távolította el, és kiürítettük-e az adatukat,
  * custom_field_defs    - admin által létrehozott saját mezők definíciója,
  * custom_field_values  - a saját mezők értékei rekordonként.

Az autogenerate által javasolt, oszlop-KOMMENT módosításokat szándékosan
kihagytuk: azok csak dokumentációs szövegek korábbi migrációkból, a mostani
változtatáshoz nincs közük.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '47f2025091fb'
down_revision: Union[str, Sequence[str], None] = 'f84bc9c23580'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'entity_field_configs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('field_name', sa.String(length=100), nullable=False),
        sa.Column('hidden', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('removed_by_employee_id', sa.Integer(), nullable=True),
        sa.Column('removed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('data_wiped', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.ForeignKeyConstraint(['removed_by_employee_id'], ['employees.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('entity_type', 'field_name', name='uq_entity_field_config'),
    )
    op.create_table(
        'custom_field_defs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('field_key', sa.String(length=100), nullable=False),
        sa.Column('label', sa.String(length=200), nullable=False),
        sa.Column('field_type', sa.String(length=20), nullable=False, server_default='text'),
        sa.Column('options', sa.JSON(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_by_employee_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['created_by_employee_id'], ['employees.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('entity_type', 'field_key', name='uq_custom_field_def'),
    )
    op.create_table(
        'custom_field_values',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('record_id', sa.Integer(), nullable=False),
        sa.Column('field_key', sa.String(length=100), nullable=False),
        sa.Column('value', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('entity_type', 'record_id', 'field_key', name='uq_custom_field_value'),
    )
    # A rekord adatlapja mindig (entity_type, record_id) szerint kérdez -
    # enélkül minden megnyitás teljes táblát olvasna.
    op.create_index('ix_custom_field_values_record', 'custom_field_values', ['entity_type', 'record_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_custom_field_values_record', table_name='custom_field_values')
    op.drop_table('custom_field_values')
    op.drop_table('custom_field_defs')
    op.drop_table('entity_field_configs')
