"""A Notion import futtatása - teljes vagy VÁLOGATOTT.

Ezt hívja mind a `scripts/notion_import.py` CLI (railway ssh-n keresztül
futtatva), mind az admin-only `/api/v1/admin/notion-import` backend végpont
(lásd app/api/routes/admin_import.py), ami a Railway-en FUTÓ backend service
saját processzében indítja el háttérszálon - így egy megszakadt `railway ssh`
kapcsolat többé nem szakítja félbe az importot, mert nem attól a
terminálkapcsolattól függ, hanem a folyamatosan futó szolgáltatás-processztől.

Hogy MIT lehet importálni, azt a katalogus.py írja le (Notion-táblánként egy
sor, a függőségeivel együtt) - ez a modul csak futtatja őket, mindig a
katalógus sorrendjében, mert a körök egymásra épülnek.

A `log` paraméter absztrahálja a kimenetet: a CLI egyszerűen printeli, az admin
végpont pedig egy memóriabeli listába gyűjti (lekérdezhető állapot-lekérdezéssel),
hogy a felhasználó ssh/terminál nélkül, a böngészőből követhesse a haladást."""

from collections.abc import Callable

from sqlalchemy.orm import Session

from app.notion_import import katalogus
from app.notion_import.client import NotionClient
from app.notion_import.engine import run_importer

#: Visszafelé kompatibilitás: a korábbi (név, függvény) párok listája. Az új
#: kód a katalogus.KATALOGUS-t használja, ami a leírásokat is tartalmazza.
ALL_IMPORTERS = [(info.nev, info.fn) for info in katalogus.KATALOGUS]


def find_importer(name: str):
    """Ismeretlen névnél None-t ad vissza - a hívó a NotionClient() (és ezzel a
    NOTION_API_KEY-igény) ELŐTT ellenőrzi, hogy egy elgépelt --only név ne csak
    Notion-hitelesítéssel derüljön ki."""
    info = katalogus.keres(name)
    return info.fn if info is not None else None


def _futtat(
    kivalasztott: list[katalogus.ImporterInfo],
    notion: NotionClient,
    db: Session,
    log: Callable[[str], None],
) -> None:
    """A megadott importerek végigfuttatása, körönként elválasztva.

    A körfejlécet csak akkor írjuk ki, amikor tényleg új körbe lépünk - így egy
    egyelemes futtatás naplója nem lesz tele üres szakaszcímekkel."""
    elozo_kor: int | None = None
    for info in kivalasztott:
        if info.kor != elozo_kor:
            log(f"\n{info.kor}. kör\n" + "=" * 40)
            elozo_kor = info.kor
        result = run_importer(info.nev, db, info.fn, notion, db)
        log(str(result))
        if result.errors or result.file_errors:
            log(result.error_report())


def run_import(
    db: Session,
    nevek: list[str] | None = None,
    log: Callable[[str], None] = print,
) -> None:
    """Import futtatása. `nevek` nélkül (vagy üres listával) MINDENT importál.

    A kiválasztott elemek MINDIG a katalógus sorrendjében futnak, nem abban,
    ahogy megadták őket - lásd katalogus.valogat()."""
    kivalasztott = katalogus.valogat(nevek)
    if not kivalasztott:
        log("Nem választottál ki egyetlen importálandó adatbázist sem.")
        return

    mind = len(kivalasztott) == len(katalogus.KATALOGUS)
    if mind:
        log("HYPE OS - Notion import: MINDEN adatbázis\n" + "=" * 40)
    else:
        log(
            f"HYPE OS - Notion import: {len(kivalasztott)} kiválasztott adatbázis "
            f"({', '.join(i.cimke for i in kivalasztott)})\n" + "=" * 40
        )
        # A hiányzó függőség nem hiba - ha az adat egy korábbi importból már
        # megvan, a részleges futtatás helyes. De ha most először importálunk,
        # ez árulja el, miért nem talál semmit.
        hianyzo = katalogus.hianyzo_fuggosegek(kivalasztott)
        for nev, fuggosegek in hianyzo.items():
            log(
                f"Megjegyzés: a(z) '{nev}' általában ezek UTÁN fut: {', '.join(fuggosegek)}. "
                "Ha azok korábban már lefutottak, ez rendben van."
            )

    # Egy kapcsolat az egész futásra: a Notion rate-limitje miatt az import
    # amúgy is hosszú, felesleges körönként új klienst nyitni.
    notion = NotionClient()
    try:
        _futtat(kivalasztott, notion, db, log)
        log("\n" + "=" * 40 + "\nKész.")
    finally:
        notion.close()


def run_full_import(db: Session, log: Callable[[str], None] = print) -> None:
    """A teljes import - minden katalógus-elem, sorrendben."""
    run_import(db, None, log)


def run_only_import(name: str, importer_fn, db: Session, log: Callable[[str], None] = print) -> None:
    """Egyetlen importer futtatása névvel (a CLI --only kapcsolója).

    Az `importer_fn` paraméter a régi hívási forma miatt maradt; a katalógus
    úgyis a névből oldja fel a függvényt."""
    run_import(db, [name], log)
