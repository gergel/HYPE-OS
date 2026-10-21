"""Az utómunka beépített funkcióihoz tartozó mezők eltávolításának visszavonása.

Ha az admin a Beállításokban eltávolította az assigned_to_employee_id vagy az
allapot mezőt a deliverable entitásról, az NÉMÁN törte el a Kiosztás kártyát
és az állapot-táblát: a generikus PATCH kihagyta az írásukat, a válaszból is
kimaradtak - a felület hibaüzenet nélkül "felejtette el" a mentést. Ezek a
mezők mostantól védettek (lásd services/entity_fields.PROTECTED_ENTITY_FIELDS),
a már megtörtént eltávolításukat pedig ez a migráció vonja vissza.

Revision ID: b7e2a91c4f60
Revises: a4c7e19f5b28
Create Date: 2026-08-31
"""

from alembic import op

revision = "b7e2a91c4f60"
down_revision = "a4c7e19f5b28"
branch_labels = None
depends_on = None

VEDETT = ("assigned_to_employee_id", "allapot")


def upgrade() -> None:
    op.execute(
        "DELETE FROM entity_field_configs WHERE entity_type = 'deliverable' "
        f"AND field_name IN ({', '.join(repr(m) for m in VEDETT)})"
    )


def downgrade() -> None:
    # Az eltávolítás-konfig törlése nem állítható vissza (nem tudjuk, ki és
    # mikor távolította el) - és nem is szabad: a mezők védettek.
    pass
