"""Autós kiadás: a rendszám után a megjegyzés, a "Mire ment" a megjegyzésbe.

A felhasználó kérése (2026-10-29): az Autók oldalon felvitt költésnél a
Kiadásokba eddig "RENDSZÁM – Mire ment" került, a megjegyzés külön mezőbe.
Mostantól fordítva (lásd routes/autok.create_auto_kiadas): "RENDSZÁM –
megjegyzés", a "Mire ment" a megjegyzésben. Visszamenőleg is átírjuk azokat
az autós kiadásokat, amelyek a régi "RENDSZÁM – ..." alakban vannak.

Downgrade: visszacseréli (a megjegyzés nélküli soroknál a rendszám marad).

Revision ID: a7u8t9o0c1s2
Revises: r1g2i3a4j5n6
"""

from alembic import op

revision = "a7u8t9o0c1s2"
down_revision = "r1g2i3a4j5n6"
branch_labels = None
depends_on = None

_ELVALASZTO = " – "


def upgrade() -> None:
    op.execute(
        f"""
        UPDATE expenses e
        SET megnevezes = LEFT(
                a.rendszam || COALESCE('{_ELVALASZTO}' || NULLIF(BTRIM(e.megjegyzes), ''), ''), 255),
            megjegyzes = SUBSTRING(e.megnevezes FROM CHAR_LENGTH(a.rendszam || '{_ELVALASZTO}') + 1)
        FROM autok a
        WHERE e.auto_id = a.id
          AND LEFT(e.megnevezes, CHAR_LENGTH(a.rendszam || '{_ELVALASZTO}')) = a.rendszam || '{_ELVALASZTO}'
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        UPDATE expenses e
        SET megnevezes = LEFT(a.rendszam || '{_ELVALASZTO}' || COALESCE(e.megjegyzes, ''), 255),
            megjegyzes = NULLIF(SUBSTRING(e.megnevezes FROM CHAR_LENGTH(a.rendszam || '{_ELVALASZTO}') + 1), '')
        FROM autok a
        WHERE e.auto_id = a.id
          AND (e.megnevezes = a.rendszam
               OR LEFT(e.megnevezes, CHAR_LENGTH(a.rendszam || '{_ELVALASZTO}')) = a.rendszam || '{_ELVALASZTO}')
        """
    )
