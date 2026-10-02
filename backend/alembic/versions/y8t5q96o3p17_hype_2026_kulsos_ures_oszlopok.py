"""HYPE 2026 külsős lap: a B-E ÜRES oszlopok törlése (a felhasználó kérése).

Élesben a dátum-oszlop (A) és a nap/diszpószám oszlopok közé négy üres
oszlop került (képernyőkép alapján: B, C, D, E). Csak azt az oszlopot
töröljük a B-E közül, ami TÉNYLEG üres: nincs felirata, nincs munkatárshoz
kötve, egyetlen cellájában sincs szöveg, és DÁTUMOS sorban színezés sem (a
fejléc-blokk jelmagyarázat-sorainak „üresen hagyva” jelei nem számítanak -
azok a sor jelmagyarázatához tartoznak, nem az oszlophoz). Amelyik nem üres,
az marad - így egy közben feltöltött oszlop nem tűnhet el. A törlés ugyanaz,
mint a felület oszlop-törlése: a jobbra álló oszlopok balra csúsznak.
Idempotens: üres oszlop híján nem csinál semmit (a törlés után a B-E már a
nap/diszpószám és a nevek oszlopai - azok nem üresek).

Revision ID: y8t5q96o3p17
Revises: x7s4p85n2o06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "y8t5q96o3p17"
down_revision = "x7s4p85n2o06"
branch_labels = None
depends_on = None

EV = 2026
KULSOS_LAP = "KÜLSŐS DISZPÓSTÁBLA"
#: B, C, D, E (0-tól számozva).
JELOLT_OSZLOPOK = (1, 2, 3, 4)
FELRETESZ = 1_000_000


def ures_oszlop(conn, lap_id: int, idx: int) -> bool:
    oszlop = conn.execute(
        sa.text("SELECT cimke, employee_id FROM diszpo_oszlopok WHERE munkalap_id = :l AND idx = :i"),
        {"l": lap_id, "i": idx},
    ).first()
    if oszlop is None or (oszlop.cimke or "").strip() or oszlop.employee_id is not None:
        return False
    tartalom = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM diszpo_cellak c "
            "LEFT JOIN diszpo_sorok s ON s.munkalap_id = c.munkalap_id AND s.idx = c.sor_idx "
            "WHERE c.munkalap_id = :l AND c.oszlop_idx = :i AND ("
            "  (c.ertek IS NOT NULL AND btrim(c.ertek) <> '')"
            "  OR (c.szin IS NOT NULL AND s.datum IS NOT NULL)"
            ")"
        ),
        {"l": lap_id, "i": idx},
    ).scalar()
    return tartalom == 0


def torles(conn) -> list[int]:
    """A törölt oszlopok (eredeti) indexei - a teszt is ezt hívja."""
    lap = conn.execute(
        sa.text("SELECT id FROM diszpo_munkalapok WHERE ev = :ev AND nev = :nev"),
        {"ev": EV, "nev": KULSOS_LAP},
    ).first()
    if lap is None:
        return []
    talalt = [i for i in JELOLT_OSZLOPOK if ures_oszlop(conn, lap.id, i)]
    # Jobbról balra: a még törlendő oszlopok indexe így nem mozdul el.
    for idx in sorted(talalt, reverse=True):
        p = {"l": lap.id, "idx": idx, "f": FELRETESZ}
        conn.execute(sa.text("DELETE FROM diszpo_cellak WHERE munkalap_id = :l AND oszlop_idx = :idx"), p)
        conn.execute(sa.text("DELETE FROM diszpo_oszlopok WHERE munkalap_id = :l AND idx = :idx"), p)
        conn.execute(
            sa.text("UPDATE diszpo_cellak SET oszlop_idx = oszlop_idx + :f WHERE munkalap_id = :l AND oszlop_idx > :idx"),
            p,
        )
        conn.execute(
            sa.text("UPDATE diszpo_cellak SET oszlop_idx = oszlop_idx - :f - 1 WHERE munkalap_id = :l AND oszlop_idx >= :f"),
            p,
        )
        conn.execute(sa.text("UPDATE diszpo_oszlopok SET idx = idx + :f WHERE munkalap_id = :l AND idx > :idx"), p)
        conn.execute(sa.text("UPDATE diszpo_oszlopok SET idx = idx - :f - 1 WHERE munkalap_id = :l AND idx >= :f"), p)
        conn.execute(
            sa.text("UPDATE diszpo_munkalapok SET oszlop_szam = GREATEST(oszlop_szam - 1, 0) WHERE id = :l"), p
        )
    return sorted(talalt)


def upgrade() -> None:
    torles(op.get_bind())


def downgrade() -> None:
    # Üres oszlopok voltak - nincs mit visszaállítani.
    pass
