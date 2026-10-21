"""Vágói játék: a kimenet-tábla egyedi kényszerének feloldása.

A felhasználó kérése: ha az anyag javításból vagy aktuálisból KÖZVETLENÜL
kerül kiküldés-féle állapotba, arra is járjon a jóváhagyás plusz pontja -
egy anyagnak így legfeljebb két kimenete lehet (egy korábbi javítás-levonás
és egy későbbi jóváhagyás). Az egyedi deliverable_id kényszer helyére sima
index kerül; a fajtánkénti egyszeriséget a kód őrzi
(services/vagoi_jatek.rogzitsd_kimenetet).

Revision ID: i5f2a63b9d84
Revises: h4e1f52a8c73
Create Date: 2026-09-04
"""

from alembic import op

revision = "i5f2a63b9d84"
down_revision = "h4e1f52a8c73"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_vago_ellenorzes_kimenet", "vago_ellenorzes_kimenetek", type_="unique")
    op.create_index(
        "ix_vago_ellenorzes_kimenetek_deliverable_id", "vago_ellenorzes_kimenetek", ["deliverable_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_vago_ellenorzes_kimenetek_deliverable_id", table_name="vago_ellenorzes_kimenetek")
    op.create_unique_constraint("uq_vago_ellenorzes_kimenet", "vago_ellenorzes_kimenetek", ["deliverable_id"])
