"""Autós kiadás: a Cégnév csak a cég, a rendszám a megjegyzésbe.

A felhasználó kérése (2026-10-29), az a7u8t9o0c1s2 utáni pontosítás: a
Kiadásokban a Cégnév (`megnevezes`) CSAK a partner legyen (pl. "MOL
Budaörs"), a rendszám a "Mire ment"-tel együtt a megjegyzésbe kerüljön:
"RENDSZÁM – Tankolás" (lásd routes/autok.create_auto_kiadas). Partner
nélkül a "Mire ment" áll a Cégnév helyén. Visszamenőleg átírja az előző
migráció utáni alakú ("RENDSZÁM – partner" vagy csak "RENDSZÁM") sorokat.

Downgrade: vissza az a7u8t9o0c1s2 utáni alakra.

Revision ID: b8c9e0g1n2v3
Revises: a7u8t9o0c1s2
"""

from alembic import op

revision = "b8c9e0g1n2v3"
down_revision = "a7u8t9o0c1s2"
branch_labels = None
depends_on = None

_E = " – "


def upgrade() -> None:
    op.execute(
        f"""
        UPDATE expenses e
        SET megnevezes = LEFT(COALESCE(
                NULLIF(SUBSTRING(e.megnevezes FROM CHAR_LENGTH(a.rendszam || '{_E}') + 1), ''),
                NULLIF(BTRIM(e.megjegyzes), ''),
                a.rendszam), 255),
            megjegyzes = a.rendszam || COALESCE('{_E}' || NULLIF(BTRIM(e.megjegyzes), ''), '')
        FROM autok a
        WHERE e.auto_id = a.id
          AND (e.megnevezes = a.rendszam
               OR LEFT(e.megnevezes, CHAR_LENGTH(a.rendszam || '{_E}')) = a.rendszam || '{_E}')
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        UPDATE expenses e
        SET megjegyzes = NULLIF(SUBSTRING(e.megjegyzes FROM CHAR_LENGTH(a.rendszam || '{_E}') + 1), ''),
            megnevezes = LEFT(CASE
                WHEN e.megnevezes = SUBSTRING(e.megjegyzes FROM CHAR_LENGTH(a.rendszam || '{_E}') + 1)
                    THEN a.rendszam
                ELSE a.rendszam || '{_E}' || e.megnevezes
            END, 255)
        FROM autok a
        WHERE e.auto_id = a.id
          AND LEFT(e.megjegyzes, CHAR_LENGTH(a.rendszam || '{_E}')) = a.rendszam || '{_E}'
        """
    )
