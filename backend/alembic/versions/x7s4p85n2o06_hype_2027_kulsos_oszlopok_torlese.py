"""HYPE 2027 külsős lap: a D-G oszlopok törlése (a felhasználó kérése).

A D-G oszlopban (a 2026-os névsor szerint) BALLA BERCI, GINO, PITE és STREAM
TERMINAL állt. A törlés NEM a betűjel, hanem a NÉV alapján megy: ha élesben
közben beszúrtak vagy töröltek egy oszlopot, a betűk elcsúsznak, a nevek nem
- így nem tűnhet el rossz oszlop. Ugyanaz a lépés, mint a felület
oszlop-törlése (routes/diszpo_tabla.oszlop_torlese): a cellák és az oszlop
törlődnek, a jobbra álló oszlopok balra csúsznak, az oszlop_szam csökken.
Idempotens: ha nincs ilyen nevű oszlop, nem csinál semmit.

Revision ID: x7s4p85n2o06
Revises: w6r3o74m1n95
"""

from __future__ import annotations

import unicodedata

import sqlalchemy as sa
from alembic import op

revision = "x7s4p85n2o06"
down_revision = "w6r3o74m1n95"
branch_labels = None
depends_on = None

EV = 2027
KULSOS_LAP = "KÜLSŐS DISZPÓSTÁBLA"
TORLENDO_NEVEK = ("BALLA BERCI", "GINO", "PITE", "STREAM TERMINAL")
#: Az A-C (dátum, nap, diszpószám) oszlopokhoz sosem nyúlunk.
ELSO_NEV_OSZLOP = 3
#: Kétfázisú eltolás - mint a felület _tolas-a: az egyedi (munkalap_id, idx)
#: index miatt a közvetlen -1 eltolás ütközhetne.
FELRETESZ = 1_000_000


def _kulcs(szoveg: str | None) -> str:
    nfkd = unicodedata.normalize("NFKD", (szoveg or "").strip().lower())
    return " ".join("".join(c for c in nfkd if not unicodedata.combining(c)).split())


def torles(conn) -> list[int]:
    """A törölt oszlopok (eredeti) indexei - a teszt is ezt hívja."""
    lap = conn.execute(
        sa.text("SELECT id FROM diszpo_munkalapok WHERE ev = :ev AND nev = :nev"),
        {"ev": EV, "nev": KULSOS_LAP},
    ).first()
    if lap is None:
        return []
    keresett = {_kulcs(n) for n in TORLENDO_NEVEK}
    talalt = [
        idx
        for idx, cimke in conn.execute(
            sa.text("SELECT idx, cimke FROM diszpo_oszlopok WHERE munkalap_id = :l AND idx >= :elso"),
            {"l": lap.id, "elso": ELSO_NEV_OSZLOP},
        )
        if _kulcs(cimke) in keresett
    ]
    # Jobbról balra: így a még törlendő oszlopok indexe nem mozdul el.
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
    # A törölt oszlopok (és a celláik) nem állíthatók vissza.
    pass
