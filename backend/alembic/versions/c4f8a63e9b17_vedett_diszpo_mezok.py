"""A projekt diszpó-állapot mezőinek eltávolítás-konfigja törlődik.

Ez volt a "Kiküldve" jelzés eltűnésének utolsó, tényleges oka: a mezők
rendszerszintű eltávolítása (Beállítások) MINDEN API-válaszból kidobta a
diszpo/elozetes_diszpo_kuldes mezőt - a küldés-zár az adatbázisból tudta,
hogy a diszpó kiment (ezért nem engedte újraküldeni), a felület viszont
üresnek látta, és újratöltés után mindenkinél eltűnt a jelzés. A mezők
mostantól védettek (lásd services/entity_fields.PROTECTED_ENTITY_FIELDS),
a meglévő elrejtő sorokat pedig ez a migráció törli - ugyanaz a minta, mint
a b7e2a91c4f60 (utómunka kiosztás/állapot).

Revision ID: c4f8a63e9b17
Revises: a8c5f92b3d16
"""

from __future__ import annotations

from alembic import op

revision = "c4f8a63e9b17"
down_revision = "a8c5f92b3d16"
branch_labels = None
depends_on = None

VEDETT = (
    "diszpo",
    "elozetes_diszpo_kuldes",
    "elozetes_kikuldve_at",
    "diszpo_kikuldve_at",
    "nem_diszponalando",
    "feldarabolas_szulo_id",
)


def upgrade() -> None:
    op.execute(
        "DELETE FROM entity_field_configs WHERE entity_type = 'project' "
        f"AND field_name IN ({', '.join(repr(m) for m in VEDETT)})"
    )


def downgrade() -> None:
    # Az eltávolítás-konfig törlése nem állítható vissza (nem tudjuk, ki és
    # mikor távolította el) - és nem is szabad: a mezők védettek.
    pass
