"""A kiadások FIZETÉSI MÓDJÁNAK visszamenőleges kitöltése a nevükből.

A fizetési mód mezőt később vezettük be (lásd services/fizetesi_mod.py), ezért
a Notionből örökölt kiadásokon üres - a kassza egyenlege viszont ebből számol.
Szerencsére a legtöbb sornál a NÉV maga a válasz: "Alap bér", "Bankkártya",
"Előfizetés". Ez a script ezeket tölti ki.

MIT NEM CSINÁL:

- nem ír felül semmit, aminél már van fizetési mód - amit valaki kézzel
  beállított, az erősebb, mint egy név-alapú következtetés;
- nem tippel. Amit nem lehet egyértelműen felismerni (pl. "Parkolás"), az
  üresen marad, és a végén ki is listázzuk - egy tippelt fizetési mód a kassza
  egyenlegét hazudná meg, márpedig épp azért van ez a mező.

Használat:

    python scripts/fizetesi_mod_kitoltese.py              # csak megmutatja
    python scripts/fizetesi_mod_kitoltese.py --vegrehajt  # ténylegesen ír

Alapból PRÓBA: kiírja, mit tenne, és nem nyúl az adatokhoz. Így a szabály
előbb ellenőrizhető a valódi adaton, mint ahogy ír.
"""

import sys
from collections import Counter
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy import or_, select  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.models.finance import Expense  # noqa: E402
from app.services import fizetesi_mod  # noqa: E402


def main() -> int:
    vegrehajt = "--vegrehajt" in sys.argv
    db = SessionLocal()
    try:
        # Csak a MEGJELÖLETLEN sorok - a kézzel beállított mód erősebb.
        sorok = db.scalars(
            select(Expense).where(
                or_(Expense.kifizetes_modja.is_(None), Expense.kifizetes_modja == "")
            )
        ).all()
        print(f"{len(sorok)} kiadáson nincs fizetési mód.\n")

        kitoltve: Counter[str] = Counter()
        ismeretlen: Counter[str] = Counter()
        for kiadas in sorok:
            # A TÍPUS ("Kiadás formája") a legerősebb jel - ez az a mező, ami a
            # Notionben eleve tartalmazza a "Bankkártya"/"Előfizetés" értéket.
            # A megnevezés csak utána jön: az a Kiadások táblán a
            # kedvezményezett neve, ami ritkábban árulkodó.
            mod = fizetesi_mod.kikovetkeztetett_mod(
                kiadas.tipus, kiadas.megnevezes, kiadas.fedezes
            )
            # Az összesítésben a TÍPUS a beszédes: a "Bérlés" egyetlen sorként
            # látszik, nem húsz kedvezményezett néven szétszórva. Típus nélküli
            # sornál marad a megnevezés.
            cimke = (kiadas.tipus or kiadas.megnevezes or "(névtelen)")[:60]
            if mod is None:
                ismeretlen[cimke] += 1
                continue
            kitoltve[f"{cimke} → {mod}"] += 1
            if vegrehajt:
                kiadas.kifizetes_modja = mod

        print("KITÖLTHETŐ:")
        if not kitoltve:
            print("  (egy sor sem ismerhető fel a nevéből)")
        for cimke, darab in kitoltve.most_common():
            print(f"  {darab:5d} × {cimke}")

        print("\nMARAD ÜRESEN (nem ismerhető fel egyértelműen):")
        if not ismeretlen:
            print("  (nincs ilyen)")
        for nev, darab in ismeretlen.most_common(40):
            print(f"  {darab:5d} × {nev}")
        if len(ismeretlen) > 40:
            print(f"  … és további {len(ismeretlen) - 40} különböző megnevezés")

        osszesen = sum(kitoltve.values())
        if vegrehajt:
            db.commit()
            print(f"\nKÉSZ: {osszesen} kiadás fizetési módja beállítva.")
        else:
            print(
                f"\nPRÓBA: {osszesen} kiadás fizetési módja lenne beállítva. "
                "Az írás a --vegrehajt kapcsolóval indul."
            )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
