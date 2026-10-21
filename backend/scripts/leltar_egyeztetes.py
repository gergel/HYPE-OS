"""A Notion "Leltár" adatbázis ÖSSZEVETÉSE a mi Equipment-adatainkkal, a
készlet-mennyiség (Equipment.osszes_mennyiseg) szempontjából.

Miért kell? Mert ha egy stock-tétel (pl. HDMI kábel) mennyisége nem stimmel
vagy hiányzik a HYPE OS-ben, több oka is lehet, és mindegyik máshogy javítandó:

1. **Hiányzik nálunk a tétel** (nem jött át az importtal, vagy azóta született
   a Notionben);
2. **Más a mennyiség** ugyanazon a tételen (a Notionben azóta módosították,
   vagy nálunk valaki felülírta);
3. **Rossz a "Track mode" besorolás** - ha a Notion "Track mode" mezőjének
   szövege nem illik egyik ismert kulcsszóra sem (lásd
   notion_import/importers._normalize_track_mode), a tétel tévesen "Egyedi"
   (asset) lesz "Készlet" (stock) helyett, és emiatt a felület máshogy bánik
   vele, még ha a mennyiség maga esetleg helyesen át is jött.

A script mindhármat megmutatja: a "Track mode" mező TÉNYLEGES értékeit (hogy
kiderüljön, ismer-e a kulcsszó-lista minden valós alakot), aztán tételesen az
eltéréseket a mennyiségben.

Használat a backend/ könyvtárból (NOTION_API_KEY szükséges - lásd
notion_import/run_all.py a hosszú futás miatti admin-végpontos indításról,
ez a script viszont egyetlen, gyors adatbázisra néz, tehát `railway ssh`
alatt is biztonságosan végigfut):

    NOTION_API_KEY=... python scripts/leltar_egyeztetes.py
"""

import sys
from collections import Counter
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.models.equipment import Equipment  # noqa: E402
from app.models.notion_import import NotionImportMap  # noqa: E402
from app.notion_import import database_ids as db_ids  # noqa: E402
from app.notion_import.client import NotionClient, extract_properties  # noqa: E402
from app.notion_import.importers import _normalize_track_mode  # noqa: E402


def main() -> int:
    db = SessionLocal()
    client = NotionClient()
    try:
        lekepezes = {
            m.notion_page_id: m.entity_id
            for m in db.scalars(select(NotionImportMap).where(NotionImportMap.entity_type == "Equipment")).all()
        }
        id_szerint = {e.id: e for e in db.scalars(select(Equipment)).all()}

        track_mode_ertekek: Counter[str] = Counter()
        hianyzik: list[str] = []
        elter: list[str] = []
        nulla_de_stock: list[str] = []
        rossz_besorolas: list[str] = []

        oldalak = list(client.query_database(db_ids.LELTAR))
        print(f"{len(oldalak)} sor a Notion 'Leltár' adatbázisban.\n")

        for page in oldalak:
            props = extract_properties(page, client)
            nev = str(props.get("Name") or "(névtelen)")[:42]
            notion_track_mode_raw = props.get("Track mode")
            track_mode_ertekek[str(notion_track_mode_raw)] += 1
            notion_mennyiseg = props.get("Összes mennyiség")
            besorolt_mode = _normalize_track_mode(notion_track_mode_raw)

            mienk_id = lekepezes.get(page["id"])
            mienk = id_szerint.get(mienk_id) if mienk_id else None
            if mienk is None:
                hianyzik.append(f"      {nev:44} Track mode(Notion)={notion_track_mode_raw!r}  mennyiség={notion_mennyiseg!r}")
                continue

            notion_ertek = int(notion_mennyiseg) if isinstance(notion_mennyiseg, (int, float)) else None
            if notion_ertek != mienk.osszes_mennyiseg:
                elter.append(
                    f"      {nev:44} Notion: {notion_ertek!r}   nálunk: {mienk.osszes_mennyiseg!r}"
                    f"   (track_mode nálunk: {mienk.track_mode.value})"
                )
            if besorolt_mode.value != mienk.track_mode.value:
                rossz_besorolas.append(
                    f"      {nev:44} Notion 'Track mode' szöveg: {notion_track_mode_raw!r}"
                    f"   -> besorolva: {besorolt_mode.value}   nálunk mentve: {mienk.track_mode.value}"
                )
            if mienk.track_mode.value == "stock" and (mienk.osszes_mennyiseg or 0) == 0:
                nulla_de_stock.append(f"      {nev:44} (nézd meg: valóban 0 van-e belőle, vagy hiányzik az adat)")

        print("Notion 'Track mode' mező VALÓS értékei - ha itt olyan alak van, ami nem tartalmazza a")
        print("'stock'/'készlet'/'darab' szót, azok a tételek tévesen 'Egyedi'-nek (asset) számítanak:\n")
        for ertek, darab in track_mode_ertekek.most_common():
            besorolas = _normalize_track_mode(None if ertek == "None" else ertek).value
            print(f"    {darab:5d} × {ertek!r:30} -> besorolva: {besorolas}")

        print(f"\nHIÁNYZIK NÁLUNK ({len(hianyzik)} sor):")
        for s in hianyzik[:30] or ["      (nincs ilyen)"]:
            print(s)
        if len(hianyzik) > 30:
            print(f"      … és további {len(hianyzik) - 30} sor")

        print(f"\nMÁS/HIÁNYZÓ MENNYISÉG ({len(elter)} sor):")
        for s in elter[:40] or ["      (nincs ilyen)"]:
            print(s)
        if len(elter) > 40:
            print(f"      … és további {len(elter) - 40} sor")

        print(f"\nROSSZ TRACK MODE BESOROLÁS ({len(rossz_besorolas)} sor):")
        for s in rossz_besorolas[:40] or ["      (nincs ilyen)"]:
            print(s)
        if len(rossz_besorolas) > 40:
            print(f"      … és további {len(rossz_besorolas) - 40} sor")

        print(f"\nSTOCK TÉTEL 0 MENNYISÉGGEL ({len(nulla_de_stock)} sor - ELLENŐRIZENDŐ, nem feltétlenül hiba):")
        for s in nulla_de_stock[:20] or ["      (nincs ilyen)"]:
            print(s)
        if len(nulla_de_stock) > 20:
            print(f"      … és további {len(nulla_de_stock) - 20} sor")

        return 0
    finally:
        client.close()
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
