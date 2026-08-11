"""Krumpello kezdőadat betöltése a kassza-táblázatból

A "HYPE PRODUCTIONS KFT. 2026 - PÉNZÜGY" munkafüzet KRUMPELLO - KASSZA és
KRUMPELLO - MUNKABÉR lapjainak teljes tartalma: 25 kassza-nap, 122 kiadás,
7 dolgozó és 70 munkanap. A forrás:
`backend/app/data/krumpello_kezdoadat.json` (a scripts/krumpello_import.py
kimenete), lásd docs/kezikonyv/14-krumpello.md.

MIÉRT MIGRÁCIÓ, ÉS NEM CSAK A SZKRIPT? Mert a szkripthez le kell tölteni a
munkafüzetet és kézzel lefuttatni valahol, ahol lát az adatbázisra - a
migráció viszont a deployjal magától lefut, tehát az adat ott lesz minden
környezetben, ugyanabban az állapotban. A szkript ettől nem lesz fölösleges:
a KÉSŐBBI frissítéseket (új hónapok) továbbra is azzal lehet behúzni.

IDEMPOTENS: minden sort csak akkor szúr be, ha még nincs ott - ugyanazokkal a
kulcsokkal, amiket a szkript is használ (nap: dátum; kiadás: forrás +
kedvezményezett + dátum + megnevezés + bruttó; munkaóra: dolgozó + dátum). Így
akkor sem duplikál, ha valaki előbb a szkriptet futtatta le.

A DOWNGRADE SZÁNDÉKOSAN NEM TÖRÖL. Egy adat-migráció visszavonása itt azt
jelentené, hogy pénzügyi sorokat dobunk el - és mire valaki visszalép, azok a
sorok már kézzel javítva lehetnek. Ha tényleg ki kell üríteni, azt tudatosan,
a felületen vagy kézzel kell megtenni, nem egy séma-visszalépés
mellékhatásaként.

Revision ID: c5b71e29d840
Revises: b8d3f1a06c47
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c5b71e29d840"
down_revision: Union[str, Sequence[str], None] = "b8d3f1a06c47"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: backend/alembic/versions/ -> backend/app/data/
ADAT_FAJL = Path(__file__).resolve().parents[2] / "app" / "data" / "krumpello_kezdoadat.json"


def _datum(ertek: str | None):
    return sa.text(f"'{ertek}'") if ertek else None


def upgrade() -> None:
    if not ADAT_FAJL.exists():
        # Nem állítjuk meg a migrációt: a séma ettől még helyes, csak az adat
        # marad üresen - azt a szkripttel pótolni lehet.
        print(f"[krumpello] Nincs kezdőadat-fájl ({ADAT_FAJL}), az adatbetöltés kimarad.")
        return

    adat = json.loads(ADAT_FAJL.read_text(encoding="utf-8"))
    kapcsolat = op.get_bind()

    beszurt_nap = beszurt_kiadas = beszurt_dolgozo = beszurt_ora = 0

    # ── Napi kassza ──────────────────────────────────────────────────────────
    letezo_napok = {
        sor[0] for sor in kapcsolat.execute(sa.text("SELECT datum FROM krumpello_napok")).fetchall()
    }
    letezo_napok = {str(d) for d in letezo_napok}
    for nap in adat.get("napok", []):
        if nap["datum"] in letezo_napok:
            continue
        kapcsolat.execute(
            sa.text(
                "INSERT INTO krumpello_napok "
                "(datum, brutto_kp, brutto_kartya, netto_kp, netto_kartya, "
                " borravalo_kp, borravalo_kartya, extra) "
                "VALUES (:datum, :brutto_kp, :brutto_kartya, :netto_kp, :netto_kartya, "
                " :borravalo_kp, :borravalo_kartya, :extra)"
            ),
            nap,
        )
        beszurt_nap += 1

    # ── Kiadások ─────────────────────────────────────────────────────────────
    letezo_kiadas = {
        (sor[0], sor[1], str(sor[2]) if sor[2] else None, sor[3], float(sor[4]) if sor[4] is not None else None)
        for sor in kapcsolat.execute(
            sa.text("SELECT forras, kedvezmenyezett, datum, megnevezes, brutto FROM krumpello_kiadasok")
        ).fetchall()
    }
    for k in adat.get("kiadasok", []):
        kulcs = (k["forras"], k["kedvezmenyezett"], k["datum"], k["megnevezes"], k["brutto"])
        if kulcs in letezo_kiadas:
            continue
        letezo_kiadas.add(kulcs)
        kapcsolat.execute(
            sa.text(
                "INSERT INTO krumpello_kiadasok "
                "(forras, kedvezmenyezett, datum, megnevezes, netto, afa, brutto) "
                "VALUES (:forras, :kedvezmenyezett, :datum, :megnevezes, :netto, :afa, :brutto)"
            ),
            k,
        )
        beszurt_kiadas += 1

    # ── Dolgozók és munkaóra ────────────────────────────────────────────────
    letezo_dolgozok = {
        str(sor[1]).casefold(): sor[0]
        for sor in kapcsolat.execute(sa.text("SELECT id, nev FROM krumpello_dolgozok")).fetchall()
    }
    for w in adat.get("dolgozok", []):
        dolgozo_id = letezo_dolgozok.get(w["nev"].casefold())
        if dolgozo_id is None:
            kapcsolat.execute(
                sa.text(
                    "INSERT INTO krumpello_dolgozok (nev, alap_orabar, aktiv) "
                    "VALUES (:nev, :alap_orabar, :aktiv)"
                ),
                {"nev": w["nev"], "alap_orabar": w["alap_orabar"], "aktiv": w.get("aktiv", True)},
            )
            dolgozo_id = kapcsolat.execute(
                sa.text("SELECT id FROM krumpello_dolgozok WHERE nev = :nev"), {"nev": w["nev"]}
            ).scalar()
            letezo_dolgozok[w["nev"].casefold()] = dolgozo_id
            beszurt_dolgozo += 1

        letezo_orak = {
            str(sor[0])
            for sor in kapcsolat.execute(
                sa.text("SELECT datum FROM krumpello_munkaorak WHERE dolgozo_id = :id"),
                {"id": dolgozo_id},
            ).fetchall()
        }
        for m in w.get("munkaorak", []):
            if m["datum"] in letezo_orak:
                continue
            kapcsolat.execute(
                sa.text(
                    "INSERT INTO krumpello_munkaorak "
                    "(dolgozo_id, datum, ora, orabar, fizetes, borravalo, megjegyzes) "
                    "VALUES (:dolgozo_id, :datum, :ora, :orabar, :fizetes, :borravalo, :megjegyzes)"
                ),
                {**m, "dolgozo_id": dolgozo_id},
            )
            beszurt_ora += 1

    print(
        f"[krumpello] Betöltve - nap: {beszurt_nap}, kiadás: {beszurt_kiadas}, "
        f"dolgozó: {beszurt_dolgozo}, munkaóra: {beszurt_ora}"
    )


def downgrade() -> None:
    """Szándékosan üres - lásd a modul leírását: pénzügyi sorokat nem dobunk el
    egy séma-visszalépés mellékhatásaként."""
