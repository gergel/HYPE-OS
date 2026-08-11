"""A Krumpello kassza és munkabér áthozatala a Google Sheets táblázatból.

Forrás: "HYPE PRODUCTIONS KFT. 2026 - PÉNZÜGY" munkafüzet
        "KRUMPELLO - KASSZA" és "KRUMPELLO - MUNKABÉR" lapjai.

Használat:

    # 1. a munkafüzet letöltése .xlsx-ként (Fájl -> Letöltés -> Excel)
    # 2. majd:
    python scripts/krumpello_import.py penzugy.xlsx
    python scripts/krumpello_import.py penzugy.xlsx --szarazon   # csak jelentés

IDEMPOTENS: kétszer lefuttatva sem duplikál.

- a napi kassza a DÁTUM alapján azonosít (naponta egy sor),
- a kiadás a (forrás, kedvezményezett, dátum, megnevezés, bruttó) négyeséből
  képzett kulccsal - ez azért elég, mert a táblázatban sem lehet két
  megkülönböztethetetlen sor ugyanarra a napra ugyanannyiról,
- a munkaóra a (dolgozó, dátum) párral.

Ami MÁR a rendszerben van, azt nem írja felül: az importálás után a felületen
javítanak, és egy újrafuttatás nem teheti tönkre azt a munkát. Aki mégis a
táblázatot tekinti igazságnak egy körre, a --felulir kapcsolóval kérheti.

Az oszlopokat NEM sorszám szerint olvassuk, hanem a fejlécsorból keressük ki:
a táblázatba idővel beszúrnak egy oszlopot, és egy elcsúszott indextől az
összeg némán rossz mezőbe kerülne.
"""

from __future__ import annotations

import argparse
import datetime
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal
from app.models.krumpello import KrumpelloDolgozo, KrumpelloKiadas, KrumpelloMunkaora, KrumpelloNap

KASSZA_LAP = "KRUMPELLO - KASSZA"
MUNKABER_LAP = "KRUMPELLO - MUNKABÉR"

#: A kiadás-blokkok a kassza-lapon: a "KIADÁS" alatti három szakasz. A
#: fejlécben szereplő nevük köti őket a modell `forras` értékeihez.
KIADAS_BLOKKOK = {
    "UTALÁS / BANKKÁRTYA": "utalas",
    "KÉSZPÉNZ": "keszpenz",
    "EXTRA": "extra",
}


def _datum(ertek) -> datetime.date | None:
    if isinstance(ertek, datetime.datetime):
        return ertek.date()
    if isinstance(ertek, datetime.date):
        return ertek
    return None


def _szam(ertek) -> float | None:
    return float(ertek) if isinstance(ertek, (int, float)) and not isinstance(ertek, bool) else None


def _szoveg(ertek) -> str | None:
    if ertek is None:
        return None
    szoveg = str(ertek).strip()
    return szoveg or None


def _blokk_oszlopai(ws, fejlec_sor: int, kezdet: int, veg: int) -> dict[str, int]:
    """Egy blokk oszlopnév -> oszlopindex térképe a fejlécsorból."""
    return {
        str(ws.cell(fejlec_sor, c).value).strip().upper(): c
        for c in range(kezdet, veg)
        if ws.cell(fejlec_sor, c).value
    }


def _kiadas_blokkok(ws, blokk_fejlec_sor: int, oszlop_fejlec_sor: int) -> list[tuple[str, dict[str, int]]]:
    """A három kiadás-blokk (forrás, oszloptérkép) párokként.

    A blokk KEZDETÉT a "UTALÁS / BANKKÁRTYA" / "KÉSZPÉNZ" / "EXTRA" felirat
    adja, a végét a következő blokk kezdete (az utolsóét a lap vége)."""
    kezdetek: list[tuple[int, str]] = []
    for c in range(1, ws.max_column + 1):
        cimke = _szoveg(ws.cell(blokk_fejlec_sor, c).value)
        if cimke and cimke.upper() in KIADAS_BLOKKOK:
            kezdetek.append((c, KIADAS_BLOKKOK[cimke.upper()]))
    blokkok = []
    for i, (c, forras) in enumerate(kezdetek):
        veg = kezdetek[i + 1][0] if i + 1 < len(kezdetek) else ws.max_column + 1
        blokkok.append((forras, _blokk_oszlopai(ws, oszlop_fejlec_sor, c, veg)))
    return blokkok


def importal(xlsx: Path, *, szarazon: bool, felulir: bool) -> None:
    try:
        import openpyxl
    except ImportError:
        raise SystemExit("Ehhez az openpyxl csomag kell: pip install openpyxl")

    wb = openpyxl.load_workbook(xlsx, data_only=True)
    for lap in (KASSZA_LAP, MUNKABER_LAP):
        if lap not in wb.sheetnames:
            raise SystemExit(f"Hiányzik a(z) {lap!r} lap a munkafüzetből. Talált lapok: {wb.sheetnames}")

    db = SessionLocal()
    uj_nap = uj_kiadas = uj_ora = uj_dolgozo = 0
    frissitett = 0
    try:
        # ── Napi kassza ────────────────────────────────────────────────────
        ws = wb[KASSZA_LAP]
        bev = _blokk_oszlopai(ws, 3, 1, 13)
        # A "BRUTTÓ/NETTÓ/BORRAVALÓ" hármas mindegyikének van KP és KÁRTYA
        # oszlopa, tehát a puszta név nem egyedi - a sorrendjük viszont fix,
        # ezért a 2. fejlécsor csoportjaiból olvassuk ki őket.
        csoportok: list[tuple[str, int]] = []
        for c in range(1, 13):
            cimke = _szoveg(ws.cell(2, c).value)
            if cimke:
                csoportok.append((cimke.upper(), c))
        kp_kartya = {}
        for cimke, c in csoportok:
            if cimke in ("BRUTTÓ", "NETTÓ", "BORRAVALÓ"):
                kp_kartya[cimke] = (c, c + 1)
        extra_oszlop = bev.get("EXTRA")

        letezo_napok = {n.datum: n for n in db.query(KrumpelloNap).all()}
        for r in range(4, ws.max_row + 1):
            d = _datum(ws.cell(r, 1).value)
            if d is None:
                continue
            ertekek = {}
            for cimke, kulcs in (("BRUTTÓ", "brutto"), ("NETTÓ", "netto"), ("BORRAVALÓ", "borravalo")):
                if cimke in kp_kartya:
                    kp, kartya = kp_kartya[cimke]
                    ertekek[f"{kulcs}_kp"] = _szam(ws.cell(r, kp).value)
                    ertekek[f"{kulcs}_kartya"] = _szam(ws.cell(r, kartya).value)
            ertekek["extra"] = _szam(ws.cell(r, extra_oszlop).value) if extra_oszlop else None
            if not any(v for v in ertekek.values()):
                continue  # üres nap - nem hozunk létre sort, csak zajt adna
            meglevo = letezo_napok.get(d)
            if meglevo is None:
                db.add(KrumpelloNap(datum=d, **ertekek))
                uj_nap += 1
            elif felulir:
                for k, v in ertekek.items():
                    setattr(meglevo, k, v)
                frissitett += 1

        # ── Kiadások ───────────────────────────────────────────────────────
        letezo_kiadas = {
            (k.forras, k.kedvezmenyezett, k.datum, k.megnevezes, float(k.brutto) if k.brutto is not None else None)
            for k in db.query(KrumpelloKiadas).all()
        }
        for forras, oszlopok in _kiadas_blokkok(ws, 2, 3):
            kedv = oszlopok.get("KEDVEZMÉNYEZETT")
            if kedv is None:
                continue
            for r in range(4, ws.max_row + 1):
                nev = _szoveg(ws.cell(r, kedv).value)
                if not nev:
                    continue
                sor = {
                    "forras": forras,
                    "kedvezmenyezett": nev,
                    "datum": _datum(ws.cell(r, oszlopok["DÁTUM"]).value) if "DÁTUM" in oszlopok else None,
                    "megnevezes": _szoveg(ws.cell(r, oszlopok["TÉTEL NEVE"]).value) if "TÉTEL NEVE" in oszlopok else None,
                    "netto": _szam(ws.cell(r, oszlopok["NETTÓ"]).value) if "NETTÓ" in oszlopok else None,
                    "afa": _szam(ws.cell(r, oszlopok["ÁFA"]).value) if "ÁFA" in oszlopok else None,
                }
                # Az "extra" blokknak nincs nettó/áfa oszlopa, csak ÖSSZEG-e.
                brutto_oszlop = oszlopok.get("BRUTTÓ") or oszlopok.get("ÖSSZEG")
                sor["brutto"] = _szam(ws.cell(r, brutto_oszlop).value) if brutto_oszlop else None
                kulcs = (sor["forras"], sor["kedvezmenyezett"], sor["datum"], sor["megnevezes"], sor["brutto"])
                if kulcs in letezo_kiadas:
                    continue
                letezo_kiadas.add(kulcs)
                db.add(KrumpelloKiadas(**sor))
                uj_kiadas += 1

        # ── Dolgozók és munkaóra ───────────────────────────────────────────
        ws2 = wb[MUNKABER_LAP]
        # Emberenként egy oszlopcsoport, a nevük az 1. sorban áll.
        emberek = [(str(ws2.cell(1, c).value).strip(), c) for c in range(1, ws2.max_column + 1) if ws2.cell(1, c).value]
        dolgozok = {d.nev.casefold(): d for d in db.query(KrumpelloDolgozo).all()}
        letezo_ora = {(o.dolgozo_id, o.datum) for o in db.query(KrumpelloMunkaora).all()}

        for nyers_nev, kezdo in emberek:
            # A táblázatban van, aki csupa nagybetűvel szerepel, van, aki nem -
            # a rendszerben egységesen olvasható alakban tároljuk.
            nev = nyers_nev.title() if nyers_nev.isupper() else nyers_nev
            dolgozo = dolgozok.get(nev.casefold())
            if dolgozo is None:
                dolgozo = KrumpelloDolgozo(nev=nev)
                db.add(dolgozo)
                db.flush()
                dolgozok[nev.casefold()] = dolgozo
                uj_dolgozo += 1
            oszlopok = _blokk_oszlopai(ws2, 2, kezdo, kezdo + 6)
            for r in range(3, ws2.max_row + 1):
                d = _datum(ws2.cell(r, oszlopok["DÁTUM"]).value) if "DÁTUM" in oszlopok else None
                if d is None:
                    continue
                ora = _szam(ws2.cell(r, oszlopok["ÓRA"]).value) if "ÓRA" in oszlopok else None
                borravalo = _szam(ws2.cell(r, oszlopok["BORRAVALÓ"]).value) if "BORRAVALÓ" in oszlopok else None
                # A táblázatban minden embernek minden nap van sora, a nem
                # dolgozott napok 0/üres értékkel - azokból nem csinálunk
                # bejegyzést, mert csak felhígítanák az elszámolást.
                if not ora and not borravalo:
                    continue
                if (dolgozo.id, d) in letezo_ora:
                    continue
                letezo_ora.add((dolgozo.id, d))
                orabar = _szam(ws2.cell(r, oszlopok["ÓRABÉR"]).value) if "ÓRABÉR" in oszlopok else None
                fizetes = _szam(ws2.cell(r, oszlopok["FIZETÉS"]).value) if "FIZETÉS" in oszlopok else None
                if fizetes is None and ora is not None and orabar is not None:
                    fizetes = round(ora * orabar, 2)
                db.add(
                    KrumpelloMunkaora(
                        dolgozo_id=dolgozo.id, datum=d, ora=ora, orabar=orabar,
                        fizetes=fizetes, borravalo=borravalo,
                    )
                )
                uj_ora += 1
                if orabar:
                    dolgozo.alap_orabar = orabar

        print(f"Új nap:      {uj_nap}" + (f" (frissítve: {frissitett})" if felulir else ""))
        print(f"Új kiadás:   {uj_kiadas}")
        print(f"Új dolgozó:  {uj_dolgozo}")
        print(f"Új munkaóra: {uj_ora}")
        if szarazon:
            db.rollback()
            print("\nSZÁRAZ FUTÁS - semmi nem került mentésre.")
        else:
            db.commit()
            print("\nMentve.")
    finally:
        db.close()


def main() -> None:
    p = argparse.ArgumentParser(description="Krumpello kassza + munkabér importálása .xlsx-ből")
    p.add_argument("xlsx", type=Path, help="A letöltött munkafüzet")
    p.add_argument("--szarazon", action="store_true", help="Csak jelentés, mentés nélkül")
    p.add_argument(
        "--felulir",
        action="store_true",
        help="A már meglévő NAPI sorokat is felülírja a táblázat értékeivel",
    )
    args = p.parse_args()
    if not args.xlsx.exists():
        raise SystemExit(f"Nincs ilyen fájl: {args.xlsx}")
    importal(args.xlsx, szarazon=args.szarazon, felulir=args.felulir)


if __name__ == "__main__":
    main()
