"""A KP forgalom tábla TÖRLÉSE és tiszta újraimportja a Notionből.

Mikor kell ez? Amikor a mi táblánk és a Notion tábla már nem ugyanannyi sorból
áll - például mert egy Notion-sort azóta töröltek (az import sosem töröl:
idempotens, de csak hozzáad és frissít), vagy mert egy elveszett leképezés miatt
egy sor kétszer jött át. Ilyenkor a legtisztább, ha a mi oldalunkat nulláról
építjük újra.

MIT CSINÁL, ebben a sorrendben:

1. megmutatja, mi van most nálunk (darabszám, összeg, irány szerint);
2. TÖRLI az összes `kp_forgalmak` sort ÉS a hozzájuk tartozó Notion-leképezést
   (`notion_import_map`) - az utóbbi nélkül az újraimport a régi, már nem létező
   rekordokra mutató leképezéseket próbálná újrahasznosítani;
3. lefuttatja a KP forgalom importert (ugyanaz, mint
   `notion_import.py --only KpForgalom`);
4. megmutatja, mi lett belőle - hogy egy pillantással látszódjon, stimmel-e a
   darabszám a Notionnel.

Használat a backend/ könyvtárból:

    python scripts/kp_forgalom_ujraimport.py                    # csak megmutatja
    NOTION_API_KEY=... python scripts/kp_forgalom_ujraimport.py --vegrehajt

Alapból PRÓBA: kiírja, mit törölne, és nem nyúl semmihez. A törlés
VISSZAVONHATATLAN, ezért külön kapcsoló kell hozzá.

FIGYELEM: ami nálunk KÉZZEL készült vagy kézzel lett javítva, azt is elviszi -
a script ezért külön megszámolja és kilistázza ezeket, mielőtt bármit törölne.
"""

import sys
from collections import Counter
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, select  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.models.finance import KpForgalom  # noqa: E402
from app.models.notion_import import NotionImportMap  # noqa: E402
from app.notion_import.run_all import run_import  # noqa: E402
from app.services import kassza as kassza_szolg  # noqa: E402

ENTITAS = "KpForgalom"


def _ft(ertek: float) -> str:
    return f"{ertek:>14,.0f} Ft".replace(",", " ")


def allapot(db, cimke: str) -> list[KpForgalom]:
    """Mi van most a táblában - darabszám, irány, összeg."""
    sorok = db.scalars(select(KpForgalom)).all()
    iranyok: Counter[str] = Counter()
    be = ki = 0.0
    for f in sorok:
        osszeg, kiadas_e = kassza_szolg.kp_forgalom_iranya(f)
        iranyok["kiadás" if kiadas_e else "bevétel"] += 1
        if kiadas_e:
            ki += osszeg
        else:
            be += osszeg

    print(f"── {cimke} ──")
    print(f"  {len(sorok)} sor a kp_forgalmak táblában")
    for irany, darab in iranyok.most_common():
        print(f"      {darab:5d} × {irany}")
    print(f"  bevétel összesen: {_ft(be)}")
    print(f"  kiadás összesen:  {_ft(ki)}")
    print(f"  egyenleg:         {_ft(be - ki)}\n")
    return sorok


def kezi_sorok(db, sorok: list[KpForgalom]) -> list[KpForgalom]:
    """Ami NEM a Notionből jött, vagy azóta kézzel javították.

    Ezek vesznek el a törléssel, ezért külön kiírjuk őket - egy törlés után
    nincs hova visszanyúlni. Kétféle van:

    - **nincs Notion-leképezése**: itt vették fel kézzel;
    - **kézzel javított**: az irány be van állítva, de az importált
      formula-érték nincs meg - épp ezt teszi a kézi javítás (lásd
      routes/finance._kp_forgalom_kezi_javitas)."""
    lekepezettek = {
        m.entity_id
        for m in db.scalars(select(NotionImportMap).where(NotionImportMap.entity_type == ENTITAS)).all()
    }
    return [
        f
        for f in sorok
        if f.id not in lekepezettek or (f.forgalom and f.forintban_notion is None)
    ]


def main() -> int:
    vegrehajt = "--vegrehajt" in sys.argv
    db = SessionLocal()
    try:
        sorok = allapot(db, "MOST")

        veszendo = kezi_sorok(db, sorok)
        if veszendo:
            print(f"  FIGYELEM: {len(veszendo)} sor kézi eredetű vagy kézzel javított - ezek is elvesznek:")
            for f in veszendo[:20]:
                print(f"      #{f.id} {(f.megnevezes or '(névtelen)')[:50]}")
            if len(veszendo) > 20:
                print(f"      … és további {len(veszendo) - 20} sor")
            print()

        lekepezes_db = db.scalar(
            select(NotionImportMap).where(NotionImportMap.entity_type == ENTITAS).exists().select()
        )
        if not vegrehajt:
            print(
                f"PRÓBA: {len(sorok)} sor és a hozzájuk tartozó Notion-leképezések törlődnének, "
                "majd újraindulna a KP forgalom import.\n"
                "A tényleges futtatás: NOTION_API_KEY=... python scripts/kp_forgalom_ujraimport.py --vegrehajt"
            )
            return 0

        # 1. TÖRLÉS - a leképezés is, különben az újraimport a már nem létező
        #    rekordokra mutató sorokat próbálná újrahasznosítani.
        torolt = db.execute(delete(KpForgalom)).rowcount
        torolt_lekepezes = db.execute(
            delete(NotionImportMap).where(NotionImportMap.entity_type == ENTITAS)
        ).rowcount
        db.commit()
        print(f"TÖRÖLVE: {torolt} sor, {torolt_lekepezes} Notion-leképezés (volt leképezés: {bool(lekepezes_db)}).\n")

        # 2. ÚJRAIMPORT - ugyanaz, mint notion_import.py --only KpForgalom.
        run_import(db, [ENTITAS])
        db.commit()

        print()
        allapot(db, "ÚJRAIMPORT UTÁN")
        print("Vesd össze a Notionnel: python scripts/kp_forgalom_egyeztetes.py --notion")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
