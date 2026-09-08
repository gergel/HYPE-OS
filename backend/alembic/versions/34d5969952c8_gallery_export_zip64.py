"""gallery export jobs (ZIP64), bigint media size, employee tenant key

Revision ID: 34d5969952c8
Revises: 55ae8901b9c5
Create Date: 2026-09-08 08:15:40.195712

Mit csinál:
* ``gallery_export_jobs`` - tartós háttérfeladat-sor a galéria ZIP64 exporthoz.
* ``media_items.size_bytes`` INTEGER -> BIGINT: a 32 bites oszlop egyetlen
  2 147 483 647 bájtnál nagyobb fájl méretét sem tudta tárolni
  ("integer out of range"). PostgreSQL-en ez táblaújraírással jár - nagy
  ``media_items`` táblánál karbantartási ablakban futtasd.
* ``media_items.checksum_sha256`` - opcionális tartalmi hash (az export
  ujjlenyomatába beleszámít).
* ``employees.client_id`` - bérlő-kulcs az ``ugyfel`` szerepkörhöz (a jogosultság-
  ellenőrzés alapja: ügyfél-felhasználó csak a saját Client projektjeit látja).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '34d5969952c8'
down_revision: Union[str, Sequence[str], None] = '55ae8901b9c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_export_status = sa.Enum('queued', 'running', 'ready', 'failed', 'expired', name='gallery_export_status')


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('gallery_export_jobs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('public_id', sa.String(length=36), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=False),
    sa.Column('client_id', sa.Integer(), nullable=False),
    sa.Column('source_fingerprint', sa.String(length=64), nullable=False),
    sa.Column('status', _export_status, nullable=False),
    sa.Column('file_count', sa.Integer(), nullable=False),
    sa.Column('total_source_bytes', sa.BigInteger(), nullable=False),
    sa.Column('expected_archive_bytes', sa.BigInteger(), nullable=False),
    sa.Column('bytes_done', sa.BigInteger(), nullable=False),
    sa.Column('files_done', sa.Integer(), nullable=False),
    sa.Column('object_key', sa.String(length=500), nullable=True),
    sa.Column('object_size', sa.BigInteger(), nullable=True),
    sa.Column('object_etag', sa.String(length=128), nullable=True),
    sa.Column('archive_sha256', sa.String(length=64), nullable=True),
    sa.Column('filename', sa.String(length=255), nullable=True),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('max_attempts', sa.Integer(), nullable=False),
    sa.Column('worker_id', sa.String(length=120), nullable=True),
    sa.Column('lease_expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('next_attempt_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('ready_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('error_code', sa.String(length=50), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('created_by_employee_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ),
    sa.ForeignKeyConstraint(['created_by_employee_id'], ['employees.id'], ),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('project_id', 'source_fingerprint', name='uq_export_project_fingerprint')
    )
    op.create_index('ix_gallery_export_jobs_client', 'gallery_export_jobs', ['client_id'], unique=False)
    op.create_index(op.f('ix_gallery_export_jobs_expires_at'), 'gallery_export_jobs', ['expires_at'], unique=False)
    op.create_index(op.f('ix_gallery_export_jobs_project_id'), 'gallery_export_jobs', ['project_id'], unique=False)
    op.create_index(op.f('ix_gallery_export_jobs_public_id'), 'gallery_export_jobs', ['public_id'], unique=True)
    op.create_index(op.f('ix_gallery_export_jobs_status'), 'gallery_export_jobs', ['status'], unique=False)
    op.create_index('ix_gallery_export_jobs_status_next', 'gallery_export_jobs', ['status', 'next_attempt_at'], unique=False)

    op.add_column('employees', sa.Column('client_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_employees_client_id'), 'employees', ['client_id'], unique=False)
    op.create_foreign_key('fk_employees_client_id', 'employees', 'clients', ['client_id'], ['id'])

    op.add_column('media_items', sa.Column('checksum_sha256', sa.String(length=64), nullable=True))
    op.alter_column('media_items', 'size_bytes',
               existing_type=sa.INTEGER(),
               type_=sa.BigInteger(),
               existing_nullable=True)


def downgrade() -> None:
    """Downgrade schema.

    Figyelem: a BIGINT -> INTEGER visszaalakítás elbukik, ha közben 2 GiB feletti
    méret került az oszlopba (ez szándékos: adatvesztés helyett hiba).
    """
    op.alter_column('media_items', 'size_bytes',
               existing_type=sa.BigInteger(),
               type_=sa.INTEGER(),
               existing_nullable=True)
    op.drop_column('media_items', 'checksum_sha256')
    op.drop_constraint('fk_employees_client_id', 'employees', type_='foreignkey')
    op.drop_index(op.f('ix_employees_client_id'), table_name='employees')
    op.drop_column('employees', 'client_id')
    op.drop_index('ix_gallery_export_jobs_status_next', table_name='gallery_export_jobs')
    op.drop_index(op.f('ix_gallery_export_jobs_status'), table_name='gallery_export_jobs')
    op.drop_index(op.f('ix_gallery_export_jobs_public_id'), table_name='gallery_export_jobs')
    op.drop_index(op.f('ix_gallery_export_jobs_project_id'), table_name='gallery_export_jobs')
    op.drop_index(op.f('ix_gallery_export_jobs_expires_at'), table_name='gallery_export_jobs')
    op.drop_index('ix_gallery_export_jobs_client', table_name='gallery_export_jobs')
    op.drop_table('gallery_export_jobs')
    _export_status.drop(op.get_bind(), checkfirst=True)
