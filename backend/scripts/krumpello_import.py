"""A Krumpello kassza és munkabér áthozatala a Google Sheets táblázatból.

A FELDOLGOZÓ LOGIKA a services/krumpello_sheet_sync.py-ba költözött: a
felületről indítható háttér-szinkron (Krumpelló oldal, "Szinkron a
táblázattal" gomb) és ez a parancssori script ugyanazt a kódot futtatja.

Használat:

    # 1. a munkafüzet letöltése .xlsx-ként (Fájl -> Letöltés -> Excel)
    # 2. majd:
    python scripts/krumpello_import.py penzugy.xlsx
    python scripts/krumpello_import.py penzugy.xlsx --szarazon   # csak jelentés
    python scripts/krumpello_import.py penzugy.xlsx --felulir    # a táblázat az igazság

IDEMPOTENS: kétszer lefuttatva sem duplikál."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import openpyxl

from app.core.database import SessionLocal
from app.services import krumpello_sheet_sync


def importal(xlsx: Path, *, szarazon: bool, felulir: bool) -> None:
    wb = openpyxl.load_workbook(xlsx, data_only=True)
    db = SessionLocal()
    try:
        osszegzes = krumpello_sheet_sync.szinkron(db, wb, felulir=felulir, naplo=print)
        if szarazon:
            db.rollback()
            print("\nSZÁRAZ FUTÁS - semmi nem került mentésre.")
        else:
            db.commit()
            print("\nMentve. " + osszegzes["uzenet"])
    finally:
        db.close()


def main() -> None:
    p = argparse.ArgumentParser(description="Krumpello kassza + munkabér importálása .xlsx-ből")
    p.add_argument("xlsx", type=Path, help="A letöltött munkafüzet")
    p.add_argument("--szarazon", action="store_true", help="Csak jelentés, mentés nélkül")
    p.add_argument(
        "--felulir",
        action="store_true",
        help="A már meglévő NAPI sorokat is felülírja a táblázat értékeivel",
    )
    args = p.parse_args()
    if not args.xlsx.exists():
        raise SystemExit(f"Nincs ilyen fájl: {args.xlsx}")
    importal(args.xlsx, szarazon=args.szarazon, felulir=args.felulir)


if __name__ == "__main__":
    main()
