"""Külsős TIG: a számla fizetési határideje és az utalás dátuma

Eddig csak a Belsős TIG-en volt ez a két dátum, a külsős (alvállalkozói)
oldalon nem: ott a kifizetés dátuma mindig az a nap lett, amikor valaki
rákattintott a "kifizetve" gombra. A valóságban a jelölés gyakran napokkal a
tényleges utalás után történik meg, a határidő pedig a számlán szerepel - így
mindkettőt meg kell tudni adni (lásd
models/performance_certificate.PerformanceCertificate).

Revision ID: d1a4e6b3c827
Revises: c7f3a20d9e14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d1a4e6b3c827"
down_revision: Union[str, Sequence[str], None] = "c7f3a20d9e14"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "performance_certificates",
        sa.Column("fizetesi_hatarido", sa.Date(), nullable=True, comment="A számla fizetési határideje"),
    )
    op.add_column(
        "performance_certificates",
        sa.Column("utalas_datuma", sa.Date(), nullable=True, comment="Mikor utaltuk el ténylegesen"),
    )
    # A már kifizetett TIG-eknél tudjuk, mikor ment el a pénz: a hozzájuk
    # tartozó Kiadás sor fizetési dátuma ez. Enélkül minden korábbi kifizetés
    # dátum nélkül maradna a papíron, pedig az adat megvan.
    op.execute(
        """
        UPDATE performance_certificates AS pc
        SET utalas_datuma = e.fizetes_datuma,
            fizetesi_hatarido = e.fizetes_hatarideje
        FROM expenses AS e
        WHERE pc.expense_id = e.id AND pc.szamla_kifizetve IS TRUE
        """
    )


def downgrade() -> None:
    op.drop_column("performance_certificates", "utalas_datuma")
    op.drop_column("performance_certificates", "fizetesi_hatarido")
