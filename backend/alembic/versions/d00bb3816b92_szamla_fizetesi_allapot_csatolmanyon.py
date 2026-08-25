"""szamla fizetesi allapot csatolmanyon

Revision ID: d00bb3816b92
Revises: 3fe2fe8c20ce
Create Date: 2026-08-25 15:00:00.000000

Minden egyes feltöltött "szamla" kategóriájú csatolmány KÜLÖN kaphat fizetési
határidőt és kifizetés-dátumot - eddig ez a Project Code egyetlen, közös
mezője volt, holott egy kódhoz több számla is tartozhat (osztott számlázás).
Lásd models/document_attachment.py.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d00bb3816b92"
down_revision: Union[str, None] = "3fe2fe8c20ce"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("document_attachments", sa.Column("fizetesi_hatarido", sa.Date(), nullable=True))
    op.add_column("document_attachments", sa.Column("kifizetve_datuma", sa.Date(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("document_attachments", "kifizetve_datuma")
    op.drop_column("document_attachments", "fizetesi_hatarido")
