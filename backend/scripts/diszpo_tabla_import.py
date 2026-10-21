"""A HYPE 2026 Google Sheet táblázat átvétele - MINDEN munkalappal és SZÍNNEL.

    python scripts/diszpo_tabla_import.py                     # próba, nem ír
    python scripts/diszpo_tabla_import.py --vegrehajt         # élesben
    python scripts/diszpo_tabla_import.py --fajl hype.xlsx    # helyi fájlból

A tényleges logika a services/diszpo_sheet_sync.py-ban él - ugyanazt a
szinkront a felület is tudja indítani (lásd routes/diszpo_tabla.py
"sheet-sync" végpontja). Ez a szkript a parancssori burkolat maradt.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal  # noqa: E402
from app.services import diszpo_sheet_sync as sync  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--vegrehajt", action="store_true", help="Ténylegesen írja az adatbázist.")
    parser.add_argument("--fajl", help="Helyi .xlsx (letöltés helyett).")
    parser.add_argument("--tablazat-id", default=sync.TABLAZAT_ID)
    parser.add_argument("--munkalap", action="append", help="Csak ezt a munkalapot (többször megadható).")
    args = parser.parse_args()

    if args.fajl:
        adat = Path(args.fajl).read_bytes()
        print(f"Helyi fájl: {args.fajl}")
    else:
        print("Letöltés a Google Sheetsből…")
        adat = sync.letoltes(args.tablazat_id)

    db = SessionLocal()
    try:
        print(f"\n{'PRÓBA (nem ír)' if not args.vegrehajt else 'VÉGREHAJTÁS'}\n")
        osszes_uzenet: list[str] = []
        for o in sync.teljes_szinkron(db, adat, vegrehajt=args.vegrehajt, munkalapok=args.munkalap):
            felulir = " (a meglévő tartalmat CSERÉLI)" if o["felulir"] else ""
            print(
                f"  {o['munkalap']:<24} {o['sorok']:>4} sor x {o['oszlopok']:>3} oszlop, "
                f"{o['cellak']:>6} cella ({o['szines']} színes), "
                f"{o['emberhez_kotve']} oszlop emberhez kötve{felulir}"
            )
            osszes_uzenet.extend(o["uzenetek"])

        if osszes_uzenet:
            print("\nAMIT KÉZZEL KELL RENDEZNI (az oszlop-ember kötés üresen maradt):")
            for u in dict.fromkeys(osszes_uzenet):
                print("  -", u)

        if not args.vegrehajt:
            print("\nEz csak PRÓBA volt. Éles futtatás: --vegrehajt")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
