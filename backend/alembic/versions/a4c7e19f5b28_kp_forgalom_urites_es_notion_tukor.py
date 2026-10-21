"""KP forgalom kiürítése + teljes Notion-tükör oszlop

A felhasználó kérése: a KP forgalom ürüljön ki TELJESEN ("tök üres legyen"),
és az importnál minden EGY AZ EGYBEN jöjjön át a Notionból. Ez a migráció az
ürítést végzi:

- törli az összes kp_forgalmak sort,
- törli a hozzájuk tartozó Notion-leképezéseket (notion_import_map), hogy a
  következő import minden sort tiszta lappal, friss baseline-nal hozzon
  létre (ne "árva leképezés"-ként),
- törli a KP sorokhoz feltöltött bizonylat-csatolmányok sorait is (a fájlok
  az R2 tárhelyen megmaradnak, de a hivatkozó sorok az üres táblával
  értelmüket vesztik),
- és felveszi a notion_adatok JSON oszlopot, amibe az import a Notion-oldal
  ÖSSZES property-jét nyersen eltükrözi (lásd models/finance.KpForgalom és
  notion_import/importers_wave2.import_kp_forgalom) - így az is átjön, amit
  a tipizált oszlopok nem ismernek.

Revision ID: a4c7e19f5b28
Revises: b91d64e0a7c5
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a4c7e19f5b28"
down_revision: Union[str, Sequence[str], None] = "b91d64e0a7c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "kp_forgalmak",
        sa.Column("notion_adatok", sa.JSON(), nullable=True, comment="A Notion-oldal összes property-je nyersen"),
    )
    kapcsolat = op.get_bind()
    vizsgalo = sa.inspect(kapcsolat)
    if vizsgalo.has_table("document_attachments"):
        kapcsolat.execute(sa.text("DELETE FROM document_attachments WHERE entity_type = 'kpForgalom'"))
    if vizsgalo.has_table("notion_import_map"):
        kapcsolat.execute(sa.text("DELETE FROM notion_import_map WHERE entity_type = 'KpForgalom'"))
    kapcsolat.execute(sa.text("DELETE FROM kp_forgalmak"))


def downgrade() -> None:
    """A törölt adatok nem állíthatók vissza - a Notion-import újratölti őket."""
    op.drop_column("kp_forgalmak", "notion_adatok")
