"""A FIZETÉSI MÓD visszamenőleges kitöltése - kiadásokon és bevételeken.

A fizetési mód mezőt később vezettük be (lásd services/fizetesi_mod.py), ezért
a Notionből örökölt sorokon üres - a kassza egyenlege viszont ebből számol.
Szerencsére a Notionben ott van ugyanez, csak MÁS mezőben:

- a kiadásnál a **"Kiadás formája"** (nálunk `Expense.tipus`): keveri a kiadás
  fajtáját és a fizetés útját, van benne "Bérlés" és "Alap bér", de
  "Bankkártya" és "Előfizetés" is;
- a bevételnél a **"Bevétel formája"** (nálunk `Revenue.bevetel_formaja`):
  ebben áll, hogy utalással vagy készpénzben jött-e a pénz.

Ez a script mindkettőt átviszi a saját fizetési mód mezőjébe.

MIT NEM CSINÁL:

- nem ír felül semmit, aminél már van fizetési mód - amit valaki kézzel
  beállított, az erősebb, mint egy név-alapú következtetés;
- a KIADÁSOKNÁL nem tippel. Amit nem lehet egyértelműen felismerni
  ("Parkolás"), az üresen marad, és a végén ki is listázzuk - egy tippelt
  fizetési mód a kassza egyenlegét hazudná meg, márpedig épp azért van ez a
  mező.

A BEVÉTELEKNÉL viszont a maradék is kap választ: ami se készpénznek, se
pénzmozgás nélkülinek nem ismerhető fel, az ÁTUTALÁS (lásd
fizetesi_mod.BEVETEL_ALAPERTELMEZES) - a készpénzt a "Bevétel formája" megnevezi,
tehát ami marad, az a számlára érkezett. A jelentésben külön soron látszik,
hány sor jött innen és nem a saját mezőjéből.

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
from app.models.finance import Expense, Revenue  # noqa: E402
from app.services import fizetesi_mod  # noqa: E402

#: Ennyi különböző megnevezést sorolunk fel a "marad üresen" listában.
LISTA_HOSSZ = 40


def _jelentes(cimke: str, kitoltve: Counter[str], ismeretlen: Counter[str], vegrehajt: bool) -> int:
    """A két lista kiírása - ugyanaz a kiadásokra és a bevételekre."""
    print(f"KITÖLTHETŐ {cimke}:")
    if not kitoltve:
        print("  (egy sor sem ismerhető fel)")
    for szoveg, darab in kitoltve.most_common():
        print(f"  {darab:5d} × {szoveg}")

    print(f"\nMARAD ÜRESEN {cimke} (nem ismerhető fel egyértelműen):")
    if not ismeretlen:
        print("  (nincs ilyen)")
    for nev, darab in ismeretlen.most_common(LISTA_HOSSZ):
        print(f"  {darab:5d} × {nev}")
    if len(ismeretlen) > LISTA_HOSSZ:
        print(f"  … és további {len(ismeretlen) - LISTA_HOSSZ} különböző érték")

    osszesen = sum(kitoltve.values())
    ige = "beállítva" if vegrehajt else "lenne beállítva"
    print(f"\n{osszesen} {cimke} fizetési módja {ige}.\n")
    return osszesen


def kiadasok(db, vegrehajt: bool) -> int:
    # Csak a MEGJELÖLETLEN sorok - a kézzel beállított mód erősebb.
    sorok = db.scalars(
        select(Expense).where(or_(Expense.kifizetes_modja.is_(None), Expense.kifizetes_modja == ""))
    ).all()
    print(f"── KIADÁSOK ──\n{len(sorok)} kiadáson nincs fizetési mód.\n")

    kitoltve: Counter[str] = Counter()
    ismeretlen: Counter[str] = Counter()
    for kiadas in sorok:
        # A TÍPUS ("Kiadás formája") a legerősebb jel - ez az a mező, ami a
        # Notionben eleve tartalmazza a "Bankkártya"/"Előfizetés" értéket.
        # A megnevezés csak utána jön: az a Kiadások táblán a kedvezményezett
        # neve, ami ritkábban árulkodó.
        mod = fizetesi_mod.kikovetkeztetett_mod(kiadas.tipus, kiadas.megnevezes, kiadas.fedezes)
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

    return _jelentes("kiadás", kitoltve, ismeretlen, vegrehajt)


def bevetelek(db, vegrehajt: bool) -> int:
    sorok = db.scalars(
        select(Revenue).where(or_(Revenue.fizetes_modja.is_(None), Revenue.fizetes_modja == ""))
    ).all()
    print(f"── BEVÉTELEK ──\n{len(sorok)} bevételen nincs fizetési mód.\n")

    kitoltve: Counter[str] = Counter()
    ismeretlen: Counter[str] = Counter()
    for bevetel in sorok:
        # A "Bevétel formája" a Notionben pont ezt mondja meg. A `nev` csak
        # másodlagos: az a munka neve, nem a fizetés módja - de ha valaki oda
        # írta be ("KP-ban"), az is válasz.
        #
        # Az ENGEDETT lista szűkít: bevételnél kártya nem lehet (nem fogadunk
        # kártyát, lásd fizetesi_mod.BEVETEL_MODOK). Enélkül egy "kártyás"
        # szövegű sor olyan módot kapna, ami a bevétel-választóban nincs is
        # benne - és onnantól se nem szerkeszthető, se nem összesíthető.
        mod = fizetesi_mod.kikovetkeztetett_mod(
            bevetel.bevetel_formaja,
            bevetel.mikor_fizetett,
            bevetel.nev,
            engedett=fizetesi_mod.BEVETEL_MODOK,
        )
        cimke = (bevetel.bevetel_formaja or bevetel.nev or "(nincs forma)")[:60]
        if mod is None:
            # A BEVÉTELNÉL a maradék is kap választ: ami se készpénznek, se
            # pénzmozgás nélkülinek nem ismerhető fel, az átutalás (lásd
            # fizetesi_mod.BEVETEL_ALAPERTELMEZES). Külön soron jelezzük,
            # hogy látszódjon, hány sor jött ONNAN, és nem a saját mezőjéből.
            mod = fizetesi_mod.BEVETEL_ALAPERTELMEZES
            kitoltve[f"{cimke} → {mod} (alapértelmezés)"] += 1
        else:
            kitoltve[f"{cimke} → {mod}"] += 1
        if vegrehajt:
            bevetel.fizetes_modja = mod

    return _jelentes("bevétel", kitoltve, ismeretlen, vegrehajt)


def main() -> int:
    vegrehajt = "--vegrehajt" in sys.argv
    db = SessionLocal()
    try:
        osszesen = kiadasok(db, vegrehajt) + bevetelek(db, vegrehajt)
        if vegrehajt:
            db.commit()
            print(f"KÉSZ: összesen {osszesen} sor fizetési módja beállítva.")
        else:
            print(
                f"PRÓBA: összesen {osszesen} sor fizetési módja lenne beállítva. "
                "Az írás a --vegrehajt kapcsolóval indul."
            )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
