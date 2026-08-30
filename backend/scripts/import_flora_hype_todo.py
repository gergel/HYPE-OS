"""A HYPE TO-DO LIST és a FLÓRA Notion-oldalak átvétele kézzel exportált
Markdown & CSV export-mappákból (Notion connector nem volt elérhető, ezért
nem a notion_import csővezetéken, hanem egy kézi exportból történik az átvétel).

    python scripts/import_flora_hype_todo.py \\
        --hype-todo-dir "/ut/HYPE TO-DO LIST export/Private & Shared" \\
        --flora-dir "/ut/FLORA export/Private & Shared"          # próba, nem ír
    python scripts/import_flora_hype_todo.py ... --vegrehajt      # élesben

A `--hype-todo-dir`/`--flora-dir` a Notion "Export → Markdown & CSV" gombjával
letöltött, kicsomagolt export "Private & Shared" mappájára mutat - abban van a
"<Oldalnév> ..._all.csv" (minden mező, minden sor) és a csatolt fájlok a
soronkénti almappákban.

ÚJRAFUTTATHATÓ: a sorokat a Notion "Létrehozás időpontja" + a feladat/
megnevezés szövege alapján képzett kulccsal azonosítja, tehát egy második
futtatás nem duplázza a sorokat, csak frissíti őket. A csatolt fájlokat a
meglévő DocumentAttachment `notion_forras` mezője (az export-relatív
útvonal) tartja egyedinek - ugyanaz a fájl kétszeri futtatásnál nem töltődik
fel újra (lásd services/attachments.by_notion_source).

A "Felelős"/"Aki felvezette"/"Ellenőrzés felelős"/"Aki ellenőrizte" mezők
neveit ékezet-/kisbetű-türelmesen próbálja párosítani a meglévő
Employee.full_name mezőkkel - ami nem egyértelmű, azt a script a végén
kilistázza (nem hoz létre placeholder munkatársat)."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from datetime import date, datetime
from pathlib import Path
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.models.employee import Employee  # noqa: E402
from app.models.flora_feladat import FloraFeladat  # noqa: E402
from app.models.hype_todo import HypeTodoItem  # noqa: E402
from app.services import attachments  # noqa: E402
from app.services.hu_szoveg import ekezet_nelkul  # noqa: E402

HYPE_TODO_CSV_NEV = "HYPE TO-DO LIST"
FLORA_CSV_NEV = "Design adatbázis"

# A Notion export dátumformátumai - a Határidő néha csak dátum, néha
# dátum+idő(+időzóna-jelölés), a Létrehozás/Created time mindig dátum+idő.
_DATUM_FORMATUMOK = ("%B %d, %Y %I:%M %p", "%B %d, %Y")


def _datum(szoveg: str | None) -> date | None:
    dt = _datetime(szoveg)
    return dt.date() if dt else None


def _datetime(szoveg: str | None) -> datetime | None:
    if not szoveg:
        return None
    # "August 18, 2026 11:59 AM (GMT+2)" - az időzóna-jelölést levágjuk, a
    # helyi idő elég a beosztáshoz, egy időzóna-eltolódás miatt nem térne el
    # a nap, aminek a Notion oldal maga is csak a napi részét mutatja.
    szoveg = re.sub(r"\s*\(GMT[^)]*\)\s*$", "", szoveg.strip())
    for fmt in _DATUM_FORMATUMOK:
        try:
            return datetime.strptime(szoveg, fmt)
        except ValueError:
            continue
    return None


def _cimke_nev(labels: str | None) -> str | None:
    """"Krumpello (orange)" -> "Krumpello" - a Notion színjelölés levágása
    (a színt a felület a `selectColor()` hash-alapú kiosztásával pótolja,
    lásd frontend lib/selectColor.ts)."""
    if not labels:
        return None
    return re.sub(r"\s*\([a-z_]+\)\s*$", "", labels.strip()) or None


def _nevterkep(db: Session) -> tuple[dict[str, Employee], dict[str, list[Employee]]]:
    """(teljes név -> munkatárs, keresztnév -> munkatársak) - ékezet-/
    kisbetű-türelmesen, minta scripts/diszpo_tabla_import.py."""
    teljes: dict[str, Employee] = {}
    kereszt: dict[str, list[Employee]] = {}
    for emb in db.scalars(select(Employee)).all():
        nev = (emb.full_name or "").strip()
        if not nev:
            continue
        teljes[ekezet_nelkul(nev)] = emb
        for resz in nev.split():
            kereszt.setdefault(ekezet_nelkul(resz), []).append(emb)
    return teljes, kereszt


def _egy_ember(
    nev: str | None, teljes: dict[str, Employee], kereszt: dict[str, list[Employee]], uzenetek: list[str]
) -> Employee | None:
    if not nev or not nev.strip():
        return None
    nev = nev.strip()
    talalat = teljes.get(ekezet_nelkul(nev))
    if talalat:
        return talalat
    jeloltek = kereszt.get(ekezet_nelkul(nev), [])
    if len(jeloltek) == 1:
        return jeloltek[0]
    if not jeloltek:
        uzenetek.append(f"„{nev}” - nincs ilyen nevű munkatárs, a mező üresen marad")
    else:
        nevek = ", ".join(e.full_name for e in jeloltek[:4])
        uzenetek.append(f"„{nev}” - többen is illenek rá ({nevek}), kézzel kell megadni")
    return None


def _tobb_ember(
    nevek: str | None, teljes: dict[str, Employee], kereszt: dict[str, list[Employee]], uzenetek: list[str]
) -> list[Employee]:
    if not nevek:
        return []
    return [
        e
        for resz in nevek.split(",")
        if (e := _egy_ember(resz, teljes, kereszt, uzenetek)) is not None
    ]


def _fajl_ut(export_dir: Path, nyers_utvonal: str) -> Path | None:
    """A CSV-ben URL-encode-olt, relatív útvonalat keresi meg a ténylegesen
    kicsomagolt export alatt - ha közvetlenül nem található (pl. az export
    mappaszerkezete kicsit eltér), a fájlnév alapján is megpróbálja."""
    dekodolt = unquote(nyers_utvonal.strip())
    jelolt = export_dir / dekodolt
    if jelolt.is_file():
        return jelolt
    fajlnev = Path(dekodolt).name
    talalatok = list(export_dir.rglob(fajlnev))
    return talalatok[0] if talalatok else None


def _link_vagy_fajl(nyers_ertek: str | None) -> tuple[list[str], list[str]]:
    """Egy "Csatolni való"/"Készítéshez fájlok" mező szétválogatva: (linkek,
    export-relatív fájlútvonalak) - a Notion adatban EGYSZERRE fordul elő
    külső link (pl. Google Sheets, nincs mit feltölteni) és helyi, ténylegesen
    csatolt fájl is."""
    linkek: list[str] = []
    fajlok: list[str] = []
    for resz in (nyers_ertek or "").split(","):
        ertek = resz.strip()
        if not ertek:
            continue
        (linkek if ertek.startswith(("http://", "https://")) else fajlok).append(ertek)
    return linkek, fajlok


def _csatolmany_fel(
    db: Session,
    entity_type: str,
    entity_id: int | None,
    export_dir: Path,
    fajl_utvonalak: list[str],
    uzenetek: list[str],
    vegrehajt: bool,
) -> None:
    """PRÓBA módban (vegrehajt=False, entity_id=None) csak azt ellenőrzi, hogy
    a fájl megtalálható-e az export alatt - nem ír az adatbázisba/R2-re,
    hogy a hiányzó csatolmányok a felhasználó ELŐTT kiderüljenek, ne csak az
    éles futtatáskor."""
    for utvonal_szoveg in fajl_utvonalak:
        if vegrehajt and attachments.by_notion_source(db, utvonal_szoveg) is not None:
            continue  # már fel van töltve egy korábbi futtatásból
        fajl = _fajl_ut(export_dir, utvonal_szoveg)
        if fajl is None:
            uzenetek.append(f"Csatolmány nem található: {utvonal_szoveg}")
            continue
        if not vegrehajt:
            continue
        attachments.save(
            db,
            entity_type=entity_type,
            entity_id=entity_id,
            kategoria="egyeb",
            filename=fajl.name,
            data=fajl.read_bytes(),
            notion_forras=utvonal_szoveg,
        )


def _all_csv(export_dir: Path, oldal_nev: str) -> Path:
    talalatok = list(export_dir.glob(f"{oldal_nev} *_all.csv"))
    if not talalatok:
        raise SystemExit(f"Nem található „{oldal_nev} ..._all.csv” itt: {export_dir}")
    return talalatok[0]


def _sorok(csv_ut: Path) -> list[dict[str, str]]:
    with csv_ut.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def import_hype_todo(db: Session, export_dir: Path, vegrehajt: bool) -> dict:
    teljes, kereszt = _nevterkep(db)
    uzenetek: list[str] = []
    letrehozva = frissitve = 0
    for sor in _sorok(_all_csv(export_dir, HYPE_TODO_CSV_NEV)):
        feladat = (sor.get("Feladat") or "").strip()
        if not feladat:
            continue
        letrehozas = _datetime(sor.get("Létrehozás időpontja"))
        meglevo = db.scalar(
            select(HypeTodoItem).where(
                HypeTodoItem.feladat == feladat, HypeTodoItem.letrehozas_idopontja == letrehozas
            )
        )
        ujdonsag = meglevo is None
        # A munkatárs-egyeztetést és a csatolmány-keresést PRÓBA módban is
        # lefuttatjuk (csak nem írunk semmit) - így a hiányzó egyezések a
        # felhasználó ELŐTT kiderülnek, nem csak az éles futtatáskor.
        aki_felvezette = _egy_ember(sor.get("Aki felvezette"), teljes, kereszt, uzenetek)
        ellenorzes_felelos = _egy_ember(sor.get("Ellenőrzés felelős"), teljes, kereszt, uzenetek)
        aki_ellenorizte = _egy_ember(sor.get("Aki ellenőrizte/készbe rakta"), teljes, kereszt, uzenetek)
        felelosok = _tobb_ember(sor.get("Felelős"), teljes, kereszt, uzenetek)
        linkek, fajl_utvonalak = _link_vagy_fajl(sor.get("Csatolni való"))
        csatolando_link = linkek[0] if linkek else None
        _csatolmany_fel(db, "hypeTodo", meglevo.id if meglevo else None, export_dir, fajl_utvonalak, uzenetek, vegrehajt=False)

        if ujdonsag:
            letrehozva += 1
        else:
            frissitve += 1
        if not vegrehajt:
            continue

        obj = meglevo or HypeTodoItem(feladat=feladat)
        obj.feladat = feladat
        obj.allapot = (sor.get("Állapot") or None) or None
        obj.leiras = (sor.get("Leírás") or "").strip() or None
        obj.kategoria = (sor.get("Kategória") or "").strip() or None
        obj.hatarido = _datum(sor.get("Határidő"))
        obj.csatolando_link = csatolando_link
        obj.letrehozas_idopontja = letrehozas
        obj.aki_felvezette = aki_felvezette
        obj.ellenorzes_felelos = ellenorzes_felelos
        obj.aki_ellenorizte = aki_ellenorizte
        obj.felelosok = felelosok
        if ujdonsag:
            db.add(obj)
        db.flush()
        _csatolmany_fel(db, "hypeTodo", obj.id, export_dir, fajl_utvonalak, uzenetek, vegrehajt=True)
    if vegrehajt:
        db.commit()
    return {"letrehozva": letrehozva, "frissitve": frissitve, "uzenetek": uzenetek}


def import_flora(db: Session, export_dir: Path, vegrehajt: bool) -> dict:
    teljes, kereszt = _nevterkep(db)
    uzenetek: list[str] = []
    letrehozva = frissitve = 0
    for sor in _sorok(_all_csv(export_dir, FLORA_CSV_NEV)):
        megnevezes = (sor.get("Megnevezés") or "").strip()
        if not megnevezes:
            continue
        letrehozas = _datetime(sor.get("Created time"))
        cimke = _cimke_nev(sor.get("Labels"))
        # A cím+létrehozási-idő NEM garantáltan egyedi: a "Created time" a
        # Notion tábla tömeges felvitelekor gyakran ugyanaz több, valójában
        # KÜLÖNBÖZŐ soron (pl. két, azonos nevű "PROGRAMTERV (PRIO) ||
        # MŰUGRÓK" sor a valódi exportban) - a Labels (cimke) a legtöbb
        # ilyen esetben megkülönbözteti őket.
        meglevo = db.scalar(
            select(FloraFeladat).where(
                FloraFeladat.megnevezes == megnevezes,
                FloraFeladat.letrehozas_idopontja == letrehozas,
                FloraFeladat.cimke == cimke,
            )
        )
        ujdonsag = meglevo is None
        felelos = _egy_ember(sor.get("Felelős"), teljes, kereszt, uzenetek)
        felvezette = _egy_ember(sor.get("Felvezette"), teljes, kereszt, uzenetek)
        _, fajl_utvonalak = _link_vagy_fajl(sor.get("Készítéshez fájlok"))
        _csatolmany_fel(
            db, "floraFeladat", meglevo.id if meglevo else None, export_dir, fajl_utvonalak, uzenetek, vegrehajt=False
        )

        if ujdonsag:
            letrehozva += 1
        else:
            frissitve += 1
        if not vegrehajt:
            continue

        obj = meglevo or FloraFeladat(megnevezes=megnevezes)
        obj.megnevezes = megnevezes
        obj.allapot = (sor.get("Állapot") or None) or None
        obj.cimke = cimke
        obj.hatarido = _datetime(sor.get("Határidő"))
        obj.kesz_anyag_linkje = (sor.get("Kész anyag linkje") or "").strip() or None
        obj.leiras = (sor.get("Leírás") or "").strip() or None
        obj.letrehozas_idopontja = letrehozas
        obj.felelos = felelos
        obj.felvezette = felvezette
        if ujdonsag:
            db.add(obj)
        db.flush()
        _csatolmany_fel(db, "floraFeladat", obj.id, export_dir, fajl_utvonalak, uzenetek, vegrehajt=True)
    if vegrehajt:
        db.commit()
    return {"letrehozva": letrehozva, "frissitve": frissitve, "uzenetek": uzenetek}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--hype-todo-dir", type=Path, help="A HYPE TO-DO LIST export „Private & Shared” mappája.")
    parser.add_argument("--flora-dir", type=Path, help="A FLÓRA export „Private & Shared” mappája.")
    parser.add_argument("--vegrehajt", action="store_true", help="Ténylegesen írja az adatbázist.")
    args = parser.parse_args()

    if not args.hype_todo_dir and not args.flora_dir:
        parser.error("Legalább az egyik --hype-todo-dir / --flora-dir kötelező.")

    db = SessionLocal()
    try:
        print(f"\n{'PRÓBA (nem ír)' if not args.vegrehajt else 'VÉGREHAJTÁS'}\n")
        if args.hype_todo_dir:
            eredmeny = import_hype_todo(db, args.hype_todo_dir, args.vegrehajt)
            print(f"HYPE TO-DO LIST: {eredmeny['letrehozva']} új, {eredmeny['frissitve']} frissített sor")
            for u in dict.fromkeys(eredmeny["uzenetek"]):
                print("  -", u)
        if args.flora_dir:
            eredmeny = import_flora(db, args.flora_dir, args.vegrehajt)
            print(f"FLÓRA: {eredmeny['letrehozva']} új, {eredmeny['frissitve']} frissített sor")
            for u in dict.fromkeys(eredmeny["uzenetek"]):
                print("  -", u)
        if not args.vegrehajt:
            print("\nEz csak PRÓBA volt. Éles futtatás: --vegrehajt")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
