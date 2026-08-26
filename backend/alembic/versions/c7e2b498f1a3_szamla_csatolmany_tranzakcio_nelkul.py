"""szamla csatolmany tranzakcio nelkul

Revision ID: c7e2b498f1a3
Revises: a1f9c3d7e264
Create Date: 2026-08-25 17:00:00.000000

Egy fájlonkénti "kihagyás a bevételekből" jelölésnél a kifizetés dátuma
mostantól nem kötelező - a legtöbbször pont azért marad ki a bevételekből,
mert nincs is valódi tranzakció (beszámítás, valakinek a fizetéséből
levonva…). Lásd models/document_attachment.py, ProjectCode.tranzakcio_nelkul_lezarva
párja.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7e2b498f1a3"
down_revision: Union[str, None] = "a1f9c3d7e264"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "document_attachments",
        sa.Column("tranzakcio_nelkul_lezarva", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("document_attachments", "tranzakcio_nelkul_lezarva", server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("document_attachments", "tranzakcio_nelkul_lezarva")
