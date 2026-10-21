"""A RÉGI portál-adatbázis felderítése - CSAK OLVAS, semmit nem ír.

Mielőtt bármit átemelnénk a különálló client-portál projekt (Hype-repo-main)
adatbázisából, tudni kell, pontosan milyen táblái és oszlopai vannak: a HYPE OS
portál-modellje ugyan annak a portja, de a régi séma ettől még eltérhet
(oszlopnevek, extra mezők, más kulcs-konvenció az R2-n).

Ez a szkript kiírja a táblákat, oszlopokat, sorszámokat, és a FÁJLRA MUTATÓ
oszlopokból (key/url/path/file/src a névben) néhány valódi mintaértéket - ez
utóbbi a legfontosabb: ebből derül ki, milyen kulcs-formátumban vannak a
képek/videók a régi bucketben, és ez alapján írható meg a tényleges átemelés.

Használat (a régi DB olvasási joga elég):

    LEGACY_DATABASE_URL=postgresql+psycopg://user:pass@host:5432/db \\
        python scripts/legacy_portal_inspect.py

    python scripts/legacy_portal_inspect.py --source-url postgresql+psycopg://... \\
        --table portal_videos --samples 5

A kimenet nyugodtan megosztható: jelszót/tokent nem ír ki, és a mintaértékeket
a --samples 0 kapcsolóval teljesen ki lehet hagyni, ha a fájlnevek maguk is
érzékenyek lennének.
"""

from __future__ import annotations

import argparse
import os
import sys

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

#: Ezekből a szórészletekből következtetünk arra, hogy egy oszlop fájlra mutat.
FAJL_JELEK = ("key", "url", "path", "file", "src", "thumb", "cover", "hls", "mp4")


def _normalizald(url: str) -> str:
    """A 'postgres://' / 'postgresql://' alakot psycopg3 driverre írjuk át -
    ugyanaz a kényelmi lépés, mint a fő alkalmazásban (core/config.py)."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


def _sorszam(engine: Engine, tabla: str) -> str:
    try:
        with engine.connect() as conn:
            return str(conn.execute(text(f'SELECT count(*) FROM "{tabla}"')).scalar_one())
    except Exception as exc:  # pragma: no cover - felderítés, a hiba is információ
        return f"? ({type(exc).__name__})"


def _mintak(engine: Engine, tabla: str, oszlop: str, darab: int) -> list[str]:
    """Néhány valódi, nem üres érték az adott oszlopból.

    Szándékosan a LEGRÖVIDEBB értékeket sem szűrjük: egy üres string és egy
    teljes URL közti különbség maga is információ arról, mennyire megbízható az
    oszlop. Hibát nem dobunk - egy nem szöveges oszlop egyszerűen kimarad."""
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    f'SELECT DISTINCT "{oszlop}"::text AS ertek FROM "{tabla}" '
                    f'WHERE "{oszlop}" IS NOT NULL LIMIT :n'
                ),
                {"n": darab},
            ).fetchall()
        return [r.ertek for r in rows]
    except Exception:
        return []


def main() -> int:
    parser = argparse.ArgumentParser(description="A régi portál-adatbázis szerkezetének kiírása (csak olvas).")
    parser.add_argument(
        "--source-url",
        default=os.environ.get("LEGACY_DATABASE_URL", ""),
        help="A RÉGI adatbázis kapcsolati URL-je (vagy a LEGACY_DATABASE_URL környezeti változó).",
    )
    parser.add_argument("--table", action="append", help="Csak ezt a táblát nézd (többször is megadható).")
    parser.add_argument(
        "--samples",
        type=int,
        default=3,
        help="Hány mintaértéket írjon ki a fájlra mutató oszlopokból (0 = egyet se).",
    )
    args = parser.parse_args()

    if not args.source_url:
        print(
            "Hiányzik a régi adatbázis URL-je. Add meg a --source-url kapcsolóval, "
            "vagy a LEGACY_DATABASE_URL környezeti változóban.",
            file=sys.stderr,
        )
        return 2

    engine = create_engine(_normalizald(args.source_url))
    inspector = inspect(engine)
    tablak = sorted(inspector.get_table_names())
    if args.table:
        kert = set(args.table)
        hianyzik = kert - set(tablak)
        if hianyzik:
            print(f"Nincs ilyen tábla: {', '.join(sorted(hianyzik))}", file=sys.stderr)
        tablak = [t for t in tablak if t in kert]

    if not tablak:
        print("Nem találtam táblát ebben az adatbázisban.")
        return 1

    print(f"{len(tablak)} tábla\n")
    for tabla in tablak:
        print(f"── {tabla}  ({_sorszam(engine, tabla)} sor)")
        for oszlop in inspector.get_columns(tabla):
            nev = oszlop["name"]
            tipus = str(oszlop["type"])
            jelzo = "" if oszlop.get("nullable", True) else "  NOT NULL"
            print(f"     {nev:<28} {tipus}{jelzo}")
            if args.samples > 0 and any(jel in nev.lower() for jel in FAJL_JELEK):
                for ertek in _mintak(engine, tabla, nev, args.samples):
                    rovid = ertek if len(ertek) <= 160 else ertek[:157] + "..."
                    print(f"        pl. {rovid}")
        print()

    print(
        "Következő lépés: a fenti kimenet alapján írható meg a tényleges átemelés "
        "(lásd docs/kezikonyv/12-migracio.md)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
