"""Az anyag_fajlok.upload_id oszlop bővítése VARCHAR(255) -> VARCHAR(1024).

A Cloudflare R2 multipart UploadId-je hosszú base64-token (több száz karakter
is lehet), a régi 255-ös mezőbe nem fért be, és a feltöltés indítása
"value too long for type character varying(255)" hibával elbukott. A
media-portál ugyanezt az UploadId-t nem tárolja adatbázisban (csak a kliensnek
adja vissza), ezért ott nem jött elő - az anyagbekérőnél viszont a
folytatható feltöltés miatt el kell menteni.

Revision ID: e8w5v96s3u47
Revises: d7v4u85r2t46
"""

import sqlalchemy as sa
from alembic import op

revision = "e8w5v96s3u47"
down_revision = "d7v4u85r2t46"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "anyag_fajlok",
        "upload_id",
        type_=sa.String(1024),
        existing_type=sa.String(255),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "anyag_fajlok",
        "upload_id",
        type_=sa.String(255),
        existing_type=sa.String(1024),
        existing_nullable=True,
    )
