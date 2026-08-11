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
import re
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


#: Szövegben álló összeg: "6535FT", "BÓNUSZ: 5000 FT", "1700 Ft - Tüdőszűrés",
#: "borravaló összesen : 35 585Ft". A táblázatban a borravaló oszlopba
#: rendszeresen kerül jegyzet is, nem csak szám - ha ezeket egyszerűen
#: eldobnánk (a _szam None-t ad rájuk), némán tűnne el egy bónusz vagy egy
#: üzemorvosi térítés.
_OSSZEG_MINTA = re.compile(r"-?\s*\d[\d\s .]*", re.UNICODE)

#: Ha ez szerepel a szövegben, az összeg egy IDŐSZAKI VÉGÖSSZEG, nem az adott
#: napé - napi értékként felvéve megduplázná az elszámolást.
_VEGOSSZEG_SZAVAK = ("összesen", "osszesen", "kiegészítés", "kiegeszites")


def _szam_szovegbol(ertek) -> tuple[float | None, str | None]:
    """(összeg, eredeti szöveg) egy cellából.

    Szám cellánál az összeg maga, jegyzet nélkül. Szöveges cellánál kiolvassuk
    belőle az első számot, ÉS megtartjuk a teljes szöveget megjegyzésnek - a
    "8400 - Üzemorvos" esetében a 8400 az összeg, de az, hogy MIÉRT, legalább
    ilyen fontos.

    Végösszeget jelölő szövegnél (lásd _VEGOSSZEG_SZAVAK) az összeget NEM
    adjuk vissza, csak a szöveget: az egy időszak összesítése, nem az adott
    napé."""
    szam = _szam(ertek)
    if szam is not None:
        return szam, None
    szoveg = _szoveg(ertek)
    if szoveg is None:
        return None, None
    egysoros = " ".join(szoveg.split())
    if any(sz in egysoros.casefold() for sz in _VEGOSSZEG_SZAVAK):
        return None, egysoros
    talalat = _OSSZEG_MINTA.search(egysoros)
    if talalat is None:
        return None, egysoros
    nyers = talalat.group(0).replace(" ", "").replace(" ", "").replace(".", "")
    try:
        return float(nyers), egysoros
    except ValueError:
        return None, egysoros


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
            # A csupa NULLÁS nap is bejön (`is not None`, nem `if v`): a "aznap
            # nyitva voltunk és nem volt bevétel" állítás információ, a hiányzó
            # zárástól különbözik. A táblázatban viszont az egész év előre ki
            # van rajzolva üres sorokkal - azokból nem csinálunk bejegyzést,
            # mert csak zajt adnának.
            if all(v is None for v in ertekek.values()):
                continue
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

        # A munkabér-lap SORAI DÁTUM SZERINT IGAZODNAK: ugyanabban a sorban
        # minden embernél ugyanaz a nap áll (ellenőrizve: egyetlen sorban sincs
        # két különböző dátum). Ezért ha valakinél üresen maradt a dátum-cella,
        # a sor dátuma a többiek oszlopából pótolható - enélkül az a munkanap
        # némán kimaradna az elszámolásból.
        sor_datumok: dict[int, datetime.date] = {}
        #: A "ZÁRÁS" sorokat SORSZINTEN ismerjük fel, nem oszloponként: a
        #: feliratot ("2026.05.06.-2026.05.31. ZÁRÁS") jellemzően csak az első
        #: ember oszlopába írják be, a többieknél üresen marad a dátum-cella,
        #: pedig ugyanaz a sor az ő időszaki elszámolásuk is. Oszloponként
        #: nézve ezek "dátum nélküli" soroknak látszanának, és vagy kimaradnának
        #: figyelmeztetéssel, vagy - ha a sor dátumát rájuk húznánk - az
        #: időszak teljes bérét egyetlen napra könyvelnénk.
        zaras_sorok: dict[int, str] = {}
        for _, kezdo in emberek:
            for r in range(3, ws2.max_row + 1):
                nyers = ws2.cell(r, kezdo).value
                d = _datum(nyers)
                if d is not None:
                    sor_datumok.setdefault(r, d)
                    continue
                szoveg = _szoveg(nyers)
                if szoveg and "ZÁRÁS" in szoveg.upper():
                    zaras_sorok.setdefault(r, " ".join(szoveg.split()))
        # Ahol egyetlen oszlopban sincs se dátum, se felirat, de van kifizetés,
        # az is időszaki zárás (a táblázat nem mindig írja ki a feliratot).
        for r in range(3, ws2.max_row + 1):
            if r in sor_datumok or r in zaras_sorok:
                continue
            if any(_szam(ws2.cell(r, kezdo + 4).value) for _, kezdo in emberek):
                zaras_sorok[r] = f"{r}. sor (felirat nélküli időszaki zárás)"

        zarasok: list[str] = []
        datum_nelkul: list[str] = []

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
                nyers_datum = ws2.cell(r, oszlopok["DÁTUM"]).value if "DÁTUM" in oszlopok else None
                ora = _szam(ws2.cell(r, oszlopok["ÓRA"]).value) if "ÓRA" in oszlopok else None
                orabar = _szam(ws2.cell(r, oszlopok["ÓRABÉR"]).value) if "ÓRABÉR" in oszlopok else None
                fizetes = _szam(ws2.cell(r, oszlopok["FIZETÉS"]).value) if "FIZETÉS" in oszlopok else None
                # A borravaló oszlopba rendszeresen jegyzet is kerül ("BÓNUSZ:
                # 5000 FT", "8400 - Üzemorvos") - az összeget kiolvassuk, a
                # szöveget megtartjuk. Az időszaki VÉGÖSSZEGEK csak jegyzetként
                # jönnek át, összegként nem (megdupláznák az elszámolást).
                borravalo, jegyzet = (
                    _szam_szovegbol(ws2.cell(r, oszlopok["BORRAVALÓ"]).value)
                    if "BORRAVALÓ" in oszlopok
                    else (None, None)
                )

                # A "ZÁRÁS" sorok egy IDŐSZAK kifizetését összegzik (dátum
                # helyett intervallum áll bennük). Nem munkanapok: napként
                # felvéve a napi sorokkal együtt duplán számítanának. Csak
                # jelentjük őket, hogy a futás után látszódjon, mi maradt ki.
                if r in zaras_sorok:
                    if fizetes or borravalo or jegyzet:
                        zarasok.append(f"{nev}: {zaras_sorok[r]} → {fizetes or 0:,.0f} Ft")
                    continue

                d = _datum(nyers_datum) or sor_datumok.get(r)
                if d is None:
                    if ora or fizetes or borravalo:
                        datum_nelkul.append(f"{nev} ({ws2.title} {r}. sor)")
                    continue

                # Van olyan nap, amikor nem dolgozott, de kapott valamit
                # (üzemorvos, tüdőszűrés térítése) - ezeknek nincs órájuk, de
                # attól még kifizetés. A régi feltétel ("csak ha van óra vagy
                # borravaló") ezeket eldobta.
                if not ora and not borravalo and not fizetes and not jegyzet:
                    continue
                if (dolgozo.id, d) in letezo_ora:
                    continue
                letezo_ora.add((dolgozo.id, d))
                if fizetes is None and ora is not None and orabar is not None:
                    fizetes = round(ora * orabar, 2)
                db.add(
                    KrumpelloMunkaora(
                        dolgozo_id=dolgozo.id, datum=d, ora=ora, orabar=orabar,
                        fizetes=fizetes, borravalo=borravalo, megjegyzes=jegyzet,
                    )
                )
                uj_ora += 1
                if orabar:
                    dolgozo.alap_orabar = orabar

        if zarasok:
            print("\nIDŐSZAKI ZÁRÁS-sorok (nem munkanapok, ezért NEM jönnek át -")
            print("a napi soraik összege adja ki ugyanezt):")
            for z in zarasok:
                print(f"  {z}")
        if datum_nelkul:
            print("\nFIGYELEM - ezekhez nem volt dátum, és a sorból sem volt pótolható:")
            for x in datum_nelkul:
                print(f"  {x}")
        print()
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
