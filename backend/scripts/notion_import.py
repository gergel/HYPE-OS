"""Fázis 2 (docs/hype_os_build_roadmap.md): a HYPE Notion workspace idempotens
importja a HYPE OS Postgres-ébe, három körben.

FONTOS: ha `railway ssh` alatt futtatva a kapcsolat rendszeresen megszakad,
mielőtt a teljes import lefutna (ez a folyamat órákig is eltarthat a Notion API
rate limitje miatt), NE ezt a CLI szkriptet használd - helyette indítsd az
importot a Beállítások oldalról (admin-only gomb), ami a Railway-en FUTÓ
backend service saját processzében, egy háttérszálon fut le (lásd
app/api/routes/admin_import.py) - ez teljesen független az ssh/böngésző
kapcsolat élettartamától, csak magának a backend service-nek kell futnia.

Használat (Railway-en, `railway ssh` után, ahol a NOTION_API_KEY env var be van
állítva a backend service Variables fülén):

    python scripts/notion_import.py                   # teljes import (mind a 3 kör)
    python scripts/notion_import.py --only Equipment  # csak egyetlen adatbázis
    python scripts/notion_import.py --only Employee --only Rate   # több, kiválasztva
    python scripts/notion_import.py --lista           # mit lehet importálni

A választható adatbázisokat a app/notion_import/katalogus.py sorolja fel (a
felület, a CLI és a teljes import ugyanabból dolgozik). Ugyanez a választás a
Beállítások oldalon kattintással is elérhető.

Bármikor újrafuttatható - a NotionImportMap tábla (notion_page_id -> a mi entitásunk)
miatt nem duplikál, csak frissíti a már importált rekordokat. A körök egymásra épülnek
(relation-feloldás), ezért teljes importnál mindig ugyanabban a sorrendben futnak, egy
futtatáson belül. A --only kapcsoló ETTŐL FÜGGETLENÜL, önmagában futtat egyetlen
importert - az Equipment ('Leltár') ehhez biztonságos, mert nem függ semmilyen más
entitás előzetes importjától (a Projektekkel/Stock igényekkel való összekötés külön,
a Project- és Stock igények-importerekben történik, nem itt).

A legtöbb entitás egy `extra` JSON mezőt is kap: ez tartalmazza azokat a Notion
mezőket, amik nem kaptak saját oszlopot (jórészt Notion formula/rollup - ugyanazt a
számítást mi Python oldalon, dinamikusan végezzük el, lásd pl. ProjectCode.becsult_profit).
Semmilyen adat nem vész el, csak a ritkán használt/redundáns mezők nem kapnak külön,
tipizált oszlopot - így a séma nem dagad szét a Notion 60+ mezős tábláival.

Amit ez a script (még mindig, szándékosan) NEM importál, és miért:
- 4 névre szabott elszámolás-klón (Bükfa Kristóf, Salamon Zalán, Fábián Péter, Nemes
  Attila adatbázis), 2025 CEU RecruiTECH Blue, 2025 beosztása, New form: a
  hype_os_migration_map.md döntése szerint adatmigráció nélkül törlődnek.
- Leltárak, Leltár tételek: audit-jellegű táblák, nálunk nincs önálló entitásuk.
- "Kreatív team database": a discovery alapján kiderült, hogy ez valójában egy
  ügyfél-onboarding/sales pipeline tábla, NEM crew-lista (a migrációs doksi
  feltételezése ezen a ponton téves volt). A felhasználó döntése (2026-07-02):
  egyelőre kimarad.
- "Belsős" / "Külsős": ezek TIG/számla-nyilvántartó táblák, nem employee-directory -
  az Employee-t a "Külsős és belsős" (a valódi crew-directory) tábla adja.
- Callsheet <- 'Operatőri diszpó' és Assignment <- 'Eszközkivitel': a forrás táblákban
  nincs relation mező a Main Database-hez, csak szabad szöveges 'Projektkód'. A
  felhasználó döntése (2026-07-02): "csak tesztek voltak, nincs szükség rájuk" - kimaradnak.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal  # noqa: E402
from app.notion_import import katalogus  # noqa: E402
from app.notion_import.run_all import run_import  # noqa: E402


def _lista_kiirasa() -> None:
    print("Importálható adatbázisok:\n")
    for info in katalogus.KATALOGUS:
        print(f"  {info.nev:28} {info.kor}. kör  <- {', '.join(info.forrasok)}")
        print(f"  {'':28} {info.leiras}")


def main() -> None:
    argumentumok = sys.argv[1:]
    if argumentumok and argumentumok[0] in ("--lista", "--list"):
        _lista_kiirasa()
        return

    # Több --only is megadható: "--only Employee --only Rate".
    nevek: list[str] = []
    i = 0
    while i < len(argumentumok):
        if argumentumok[i] != "--only" or i + 1 >= len(argumentumok):
            print("Használat: python scripts/notion_import.py [--only <név> ...] [--lista]")
            sys.exit(1)
        nevek.append(argumentumok[i + 1])
        i += 2

    if nevek:
        ismeretlen = katalogus.ismeretlen_nevek(nevek)
        if ismeretlen:
            print(f"Ismeretlen adatbázis: {', '.join(ismeretlen)}.\n")
            _lista_kiirasa()
            sys.exit(1)

    db = SessionLocal()
    try:
        run_import(db, nevek or None)
    finally:
        db.close()


if __name__ == "__main__":
    main()
