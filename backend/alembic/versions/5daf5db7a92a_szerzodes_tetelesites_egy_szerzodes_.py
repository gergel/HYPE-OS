"""Szerzodes tetelesites: egy szerzodes tobb munkara

Egy eseti szerzodes eddig pontosan egy (projekt, ember) parrol szolt. Mostantol
tetelei vannak - ugyanugy, mint a TIG-nek -, hogy harom nap forgatasrol egy
szerzodes is kesziteni lehessen, az osszevont TIG melle.

A meglevo szerzodesek egyteteless valnak: pontosan azt fedik, amirol eddig is
szoltak.

Revision ID: 5daf5db7a92a
Revises: 7b2196c6e985
Create Date: 2026-08-08 06:18:17.199406

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5daf5db7a92a'
down_revision: Union[str, Sequence[str], None] = '7b2196c6e985'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('contract_tetelek',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('contract_id', sa.Integer(), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=False),
    sa.Column('employee_id', sa.Integer(), nullable=False),
    sa.Column('netto_osszeg', sa.Numeric(precision=12, scale=2), nullable=True, comment='Ebből ennyi az övé - ha tudható'),
    sa.Column('megnevezes', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['contract_id'], ['contracts.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('contract_id', 'project_id', 'employee_id', name='uq_szerzodes_tetel')
    )
    op.create_index(op.f('ix_contract_tetelek_contract_id'), 'contract_tetelek', ['contract_id'], unique=False)
    op.create_index(op.f('ix_contract_tetelek_employee_id'), 'contract_tetelek', ['employee_id'], unique=False)
    op.create_index(op.f('ix_contract_tetelek_project_id'), 'contract_tetelek', ['project_id'], unique=False)

    # A meglévő, PROJEKTHEZ KÖTÖTT eseti szerződések egytételessé válnak. A
    # keretszerződések (project_id IS NULL) kimaradnak: azok nem egy konkrét
    # munkáról szólnak. Enélkül a tételek szerint számoló utókövetés az összes
    # régi szerződést "hiányzónak" látná.
    op.execute(
        sa.text(
            """
            INSERT INTO contract_tetelek (contract_id, project_id, employee_id, netto_osszeg, megnevezes)
            SELECT id, project_id, employee_id, netto_osszeg, megbizas_targya
            FROM contracts
            WHERE tipus = 'alvallalkozoi'
              AND project_id IS NOT NULL
              AND employee_id IS NOT NULL
            """
        )
    )
    op.alter_column('contracts', 'teljesites_kezdete',
               existing_type=sa.DATE(),
               comment='Teljesítés kezdete (régi, dátumpáros adat)',
               existing_comment='Teljesítés kezdete',
               existing_nullable=True)
    op.alter_column('contracts', 'teljesites_vege',
               existing_type=sa.DATE(),
               comment='Teljesítés vége (régi, dátumpáros adat)',
               existing_comment='Teljesítés vége',
               existing_nullable=True)
    op.alter_column('internal_performance_certificates', 'megbizas_targya',
               existing_type=sa.VARCHAR(length=255),
               comment='Alapból a munkatárs adatlapjáról jön, de TIG-enként átírható',
               existing_nullable=True)
    op.alter_column('internal_performance_certificates', 'teljesites_datuma',
               existing_type=sa.DATE(),
               comment='Ebből jön az igazolt hónap: MINDIG az azt megelőző hónap',
               existing_nullable=True)
    op.alter_column('internal_performance_certificates', 'keltezes',
               existing_type=sa.DATE(),
               comment='A dokumentum keltezése',
               existing_nullable=True)
    op.alter_column('internal_performance_certificates', 'file_url',
               existing_type=sa.VARCHAR(length=500),
               comment='A kiküldött TIG dokumentum Drive linkje',
               existing_nullable=True)
    op.alter_column('performance_certificates', 'teljesites_szoveg',
               existing_type=sa.VARCHAR(length=255),
               comment='Teljesítés ideje - szabad szöveg',
               existing_nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('performance_certificates', 'teljesites_szoveg',
               existing_type=sa.VARCHAR(length=255),
               comment=None,
               existing_comment='Teljesítés ideje - szabad szöveg',
               existing_nullable=True)
    op.alter_column('internal_performance_certificates', 'file_url',
               existing_type=sa.VARCHAR(length=500),
               comment=None,
               existing_comment='A kiküldött TIG dokumentum Drive linkje',
               existing_nullable=True)
    op.alter_column('internal_performance_certificates', 'keltezes',
               existing_type=sa.DATE(),
               comment=None,
               existing_comment='A dokumentum keltezése',
               existing_nullable=True)
    op.alter_column('internal_performance_certificates', 'teljesites_datuma',
               existing_type=sa.DATE(),
               comment=None,
               existing_comment='Ebből jön az igazolt hónap: MINDIG az azt megelőző hónap',
               existing_nullable=True)
    op.alter_column('internal_performance_certificates', 'megbizas_targya',
               existing_type=sa.VARCHAR(length=255),
               comment=None,
               existing_comment='Alapból a munkatárs adatlapjáról jön, de TIG-enként átírható',
               existing_nullable=True)
    op.alter_column('contracts', 'teljesites_vege',
               existing_type=sa.DATE(),
               comment='Teljesítés vége',
               existing_comment='Teljesítés vége (régi, dátumpáros adat)',
               existing_nullable=True)
    op.alter_column('contracts', 'teljesites_kezdete',
               existing_type=sa.DATE(),
               comment='Teljesítés kezdete',
               existing_comment='Teljesítés kezdete (régi, dátumpáros adat)',
               existing_nullable=True)
    op.drop_index(op.f('ix_contract_tetelek_project_id'), table_name='contract_tetelek')
    op.drop_index(op.f('ix_contract_tetelek_employee_id'), table_name='contract_tetelek')
    op.drop_index(op.f('ix_contract_tetelek_contract_id'), table_name='contract_tetelek')
    op.drop_table('contract_tetelek')
