"""A Notion "KP forgalom" adatbázis ÖSSZEVETÉSE a mi adatainkkal, tételenként.

Miért kell? Mert ha a KP forgalom oldalon nem stimmel egy összeg, három
különböző dolog lehet mögötte, és mindhárom máshogy javítandó:

1. **Hiányzik nálunk egy sor** (nem jött át az importtal, vagy azóta született);
2. **Más az összeg** ugyanazon a soron (a Notionben javították utólag);
3. **Máshogy értelmezzük** (irány, pénznem, kiadáshoz kötés) - ilyenkor a
   darabszám és a végösszeg is stimmelhet külön-külön, mégis mást mutat a
   felület.

A script mind a hármat megmutatja: darabszám és végösszeg mindkét oldalon,
aztán tételesen az eltérések.

Használat a backend/ könyvtárból:

    # csak a MI oldalunk (Notion nélkül) - darabszám, összegek, mezőértékek
    python scripts/kp_forgalom_egyeztetes.py

    # tételes összevetés a Notionnel
    NOTION_API_KEY=... python scripts/kp_forgalom_egyeztetes.py --notion

A Notion-kulcsot NE írd bele semmilyen fájlba: add meg a parancs elején, ahogy
fent - vagy a Railway service Variables fülén, és onnan futtasd.
"""

import sys
from collections import Counter
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.models.finance import KpForgalom  # noqa: E402
from app.models.notion_import import NotionImportMap  # noqa: E402
from app.services import kassza as kassza_szolg  # noqa: E402
from app.services import penznem as penznem_szolg  # noqa: E402


def _ft(ertek: float | None) -> str:
    return f"{(ertek or 0):>15,.0f} Ft".replace(",", " ")


def sajat_oldal(db) -> dict[str, KpForgalom]:
    """A MI KP forgalom soraink, Notion-azonosító szerint kulcsolva."""
    sorok = db.scalars(select(KpForgalom)).all()
    print(f"── A MI ADATAINK ──\n{len(sorok)} sor a kp_forgalmak táblában.\n")

    osszeg = sum(kassza_szolg._kp_forgalom_osszege(f) for f in sorok)
    kotott = sum(1 for f in sorok if f.expense_id is not None)
    datum_nelkul = sum(1 for f in sorok if f.kiadas_datuma is None)
    ertek_nelkul = [f for f in sorok if kassza_szolg._kp_forgalom_osszege(f) == 0]

    print(f"  végösszeg (forintban):       {_ft(osszeg)}")
    print(f"  ebből kiadáshoz kötve:       {kotott:>5d} sor (ezek KIMARADNAK a naplóból)")
    print(f"  dátum nélküli sor:           {datum_nelkul:>5d} (ezek nem kerülnek az IDEI bontásba)")
    print(f"  NULLA összeggel számolt sor: {len(ertek_nelkul):>5d}")
    for f in ertek_nelkul[:10]:
        print(
            f"      #{f.id} {(f.megnevezes or '(névtelen)')[:34]:36} "
            f"összeg={f.osszeg} pénznem={f.penznem!r} forintban_notion={f.forintban_notion}"
        )
    if len(ertek_nelkul) > 10:
        print(f"      … és további {len(ertek_nelkul) - 10} sor")

    # A mezőértékek eloszlása: ebből derül ki, mit jelentenek a szabad szöveges
    # Notion-mezők, amikre a szabályaink épülnek.
    for mezo in ("forgalom", "legalis", "penznem"):
        darabok = Counter(getattr(f, mezo) for f in sorok)
        print(f"\n  {mezo}:")
        for ertek, darab in darabok.most_common(12):
            kieg = ""
            if mezo == "penznem":
                kieg = " (DEVIZÁS!)" if penznem_szolg.devizas(ertek) else ""
            print(f"      {darab:5d} × {ertek!r}{kieg}")

    # A Notion page ID -> a mi rekordunk leképezése külön táblában áll (ez teszi
    # idempotenssé az importot), lásd models/notion_import.py.
    lekepezes = db.scalars(
        select(NotionImportMap).where(NotionImportMap.entity_type == "KpForgalom")
    ).all()
    id_szerint = {f.id: f for f in sorok}
    parositva = {m.notion_page_id: id_szerint[m.entity_id] for m in lekepezes if m.entity_id in id_szerint}
    arva = len(lekepezes) - len(parositva)
    if arva:
        print(f"\n  {arva} Notion-leképezés mutat NEM LÉTEZŐ sorra (törölték nálunk).")
    return parositva


def notion_oldal(db, sajat: dict) -> None:
    """A Notion "KP forgalom" adatbázis, tételesen összevetve a mi sorainkkal."""
    from app.notion_import import database_ids as db_ids
    from app.notion_import.client import NotionClient, extract_properties

    client = NotionClient()
    oldalak = list(client.query_database(db_ids.KP_FORGALOM))
    print(f"\n── A NOTIONBEN ──\n{len(oldalak)} sor a 'KP forgalom' adatbázisban.\n")

    notion_osszeg = 0.0
    hianyzik: list[str] = []
    elter: list[str] = []
    for page in oldalak:
        props = extract_properties(page, client)
        osszeg = props.get("Összeg")
        forintban = props.get("Forintban")
        ertek = float(forintban if forintban is not None else (osszeg or 0))
        notion_osszeg += ertek
        nev = str(props.get("Megnevezés") or "(névtelen)")[:40]

        mienk = sajat.get(page["id"])
        if mienk is None:
            hianyzik.append(f"      {nev:42} {_ft(ertek)}")
            continue
        miertek = kassza_szolg._kp_forgalom_osszege(mienk)
        if round(miertek, 2) != round(ertek, 2):
            elter.append(f"      {nev:42} Notion: {_ft(ertek)}   nálunk: {_ft(miertek)}")

    print(f"  végösszeg:                   {_ft(notion_osszeg)}")
    print(f"\n  HIÁNYZIK NÁLUNK ({len(hianyzik)} sor):")
    for s in hianyzik[:25] or ["      (nincs ilyen)"]:
        print(s)
    if len(hianyzik) > 25:
        print(f"      … és további {len(hianyzik) - 25} sor")

    print(f"\n  MÁS AZ ÖSSZEG ({len(elter)} sor):")
    for s in elter[:25] or ["      (nincs ilyen)"]:
        print(s)
    if len(elter) > 25:
        print(f"      … és további {len(elter) - 25} sor")

    notion_idk = {p["id"] for p in oldalak}
    tobblet = [f for kulcs, f in sajat.items() if kulcs not in notion_idk]
    print(f"\n  NÁLUNK VAN, A NOTIONBEN NINCS ({len(tobblet)} sor):")
    for f in tobblet[:25]:
        print(f"      #{f.id} {(f.megnevezes or '(névtelen)')[:40]}")
    if not tobblet:
        print("      (nincs ilyen)")


def main() -> int:
    db = SessionLocal()
    try:
        sajat = sajat_oldal(db)
        if "--notion" in sys.argv:
            notion_oldal(db, sajat)
        else:
            print("\n(A Notionnel való összevetéshez: NOTION_API_KEY=... … --notion)")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
