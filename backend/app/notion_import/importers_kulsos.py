"""A Notion "Külsős" tábla importja: projektenkénti ESETI SZERZŐDÉS + KÜLSŐS TIG.

Ez a tábla a HYPE Notionban a külsősök projektenkénti papírjait tartja nyilván:
soronként egy (ember, forgatás) pár, rajta a szerződés és a TIG állapota,
összege, dátumai és a feltöltött fájlok.

Eddig NEM importáltuk - a 2026-07-02-i felmérés csak annyit állapított meg
róla, hogy nem munkatárs-nyilvántartó tábla, ezért kimaradt a listából (lásd
importers.import_employees docstringje). Emiatt a rendszer nem tudott arról a
több mint ezer papírról, ami a Notionban már elkészült, és az Utókövetés úgy
mutatta ezeket a projekteket, mintha még minden hátra lenne.

Két entitást tölt:

- Contract (eseti, projekthez kötött) - ha a "Szerződés Állapot" szerint
  készült szerződés. A "Keretszerződése van" sorokhoz szándékosan NEM
  készítünk szerződést: ott a keretszerződés váltja ki, eseti papír nem
  létezik (lásd models/contract.py keretszerzodes_ervenyes).
- PerformanceCertificate (külsős TIG) - ha az "Állapot" szerint a TIG
  elkészült. A "Készíthető a TIG" sorok kimaradnak: ott tényleg nincs még TIG,
  és jogos, hogy az Utókövetés kérje.

Idempotens: minden sor a saját Notion page ID-jén keresztül azonosítja a nála
készült rekordokat, tehát az újrafuttatás frissít, nem duplikál. A kézzel
beírt adatot nem írja felül - csak az üres mezőket egészíti ki -, ugyanaz az
elv, mint a keretszerződéseknél.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.contract import Contract, ContractType
from app.models.notion_import import NotionImportMap
from app.models.performance_certificate import PerformanceCertificate, PerformanceCertificateTetel
from app.notion_import import database_ids as db_ids, files
from app.notion_import.client import NotionClient, as_date, extract_properties
from app.notion_import.engine import ImportResult, resolve_relation_id
from app.notion_import.importers import _first_url, _szoveg_mezo, _text

#: A "Szerződés Állapot" értékei, amiknél MÁR VAN eseti szerződés.
SZERZODES_KESZ = {"Elkészült és kiküldve", "Kész feltöltve"}
#: Ennél az értéknél nincs (és nem is kell) eseti szerződés.
SZERZODES_KERETTEL = "Keretszerződése van"

#: Az "Állapot" (TIG) értékei, amiknél MÁR ELKÉSZÜLT a TIG.
TIG_KESZ = {"Elkészült és kiküldve", "Kész feltöltve"}

#: A mi állapot-szótárunk: ami a Notionban kész, az nálunk "Kiküldve" - ez a
#: lezárt állapot mind a szerződésnél, mind a TIG-nél (lásd
#: routes/subcontractor_contracts.py és performance_certificates.py
#: TERMINAL_STATUSES).
LEZART = "Kiküldve"

#: Ember- és projekt-relációk. A Notionban több írásmóddal is előfordulhatnak.
EMBER_MEZOK = ("Külsős", "Külsős ", "Vállalkozó", "Személy")
FORGATAS_MEZOK = ("Forgatás", "Forgatás ", "Main Database")


def _mezo_lista(props: dict, *nevek: str) -> list[str]:
    for nev in nevek:
        ertek = props.get(nev)
        if isinstance(ertek, list) and ertek:
            return [v for v in ertek if isinstance(v, str) and v]
    return []


#: A PROJEKTKÓD relation és szöveges mezője - a forgatás másodlagos azonosítói.
PROJEKTKOD_MEZOK = ("HYPE ADMIN projektkódok", "HYPE ADMIN projektkódok ")


def _projekt_azonositasa(db: Session, props: dict) -> int | None:
    """Melyik forgatásra szól ez a papír?

    Elsősorban a "Forgatás" relation mondja meg. Ha az üres (vagy a
    hivatkozott sor nem jött át), a PROJEKTKÓDBÓL is ki lehet találni: a
    papíron ott a kód relationként és szövegként is, a kód alatt pedig ott
    vannak a forgatások.

    Ez azért kell, mert a sor kihagyása nem semleges: attól a rendszer úgy
    mutatja, mintha a TIG még hátra lenne - pedig a Notionban ott van, kész.
    Ha a kód alatt TÖBB forgatás fut, a "Forgatás dátuma" dönt; ha az sem
    választja szét őket, inkább nem tippelünk (a rossz projektre könyvelt
    papír rosszabb, mint a hiányzó)."""
    from app.models.project import Project
    from app.services import projektkod_kotes

    project_id = resolve_relation_id(db, "Project", _mezo_lista(props, *FORGATAS_MEZOK))
    if project_id is not None:
        return project_id

    kod_id = resolve_relation_id(db, "ProjectCode", _mezo_lista(props, *PROJEKTKOD_MEZOK))
    if kod_id is None:
        kod = projektkod_kotes.keresd(db, _szoveg_mezo(props, "Projektkód"))
        kod_id = kod.id if kod else None
    if kod_id is None:
        return None

    projektek = list(db.scalars(select(Project).where(Project.project_code_id == kod_id)))
    if not projektek:
        return None
    if len(projektek) == 1:
        return projektek[0].id

    nap = as_date(_szoveg_mezo(props, "Forgatás dátuma"))
    egyezo = [p for p in projektek if nap is not None and p.forgatas_datuma == nap]
    if len(egyezo) == 1:
        return egyezo[0].id
    # Több forgatás, nincs eldöntő dátum: nem tippelünk.
    return None


def _plusz_afa(ertek) -> bool | None:
    """A Notionban select mező ("+ ÁFA" / "+ÁFA"), nálunk boolean."""
    if ertek in (None, "", []):
        return None
    szoveg = " ".join(ertek) if isinstance(ertek, list) else str(ertek)
    return "áfa" in szoveg.lower()


def _kiegeszit(rekord, mezok: dict) -> None:
    """Csak az ÜRES mezőket tölti ki - amit kézzel beírtak, azt nem írjuk felül."""
    for mezo, ertek in mezok.items():
        if ertek is not None and getattr(rekord, mezo, None) in (None, ""):
            setattr(rekord, mezo, ertek)


def _mar_letezik(db: Session, kulcs: str, model: type):
    mapping = db.scalar(select(NotionImportMap).where(NotionImportMap.notion_page_id == kulcs))
    return db.get(model, mapping.entity_id) if mapping else None


def _jegyezd_fel(db: Session, kulcs: str, entity_type: str, entity_id: int) -> None:
    db.add(NotionImportMap(notion_page_id=kulcs, entity_type=entity_type, entity_id=entity_id))
    db.flush()


def _cegadat(props: dict) -> dict:
    return {
        "ceg_neve": _szoveg_mezo(props, "Vállalkozás név", "Vállalkozás neve", "Név"),
        "szekhely": _szoveg_mezo(props, "Székhely"),
        "adoszam": _szoveg_mezo(props, "Adószám"),
        "vallalkozas_kepviseloje": _szoveg_mezo(props, "Vállalkozás képviselő"),
        "vallalkozas_nyilvantartasi_szam": _szoveg_mezo(props, "Nyilvántartási szám:", "Nyilvántartási szám"),
        "email": _szoveg_mezo(props, "email", "Email"),
    }


def _szerzodes_importalasa(
    db: Session, result: ImportResult, page: dict, props: dict, project_id: int, employee_id: int
) -> None:
    allapot = _text(props.get("Szerződés Állapot"))
    if allapot not in SZERZODES_KESZ:
        # "Keretszerződése van" -> nincs eseti papír; "Nincs elkezdve" -> még
        # tényleg hiányzik, jogos, hogy az Utókövetés kérje.
        return

    kulcs = f"kulsos-szerzodes:{page['id']}"
    szerzodes = _mar_letezik(db, kulcs, Contract)
    if szerzodes is None:
        # Lehet, hogy nálunk MÁR készült szerződés erre a párosra (a
        # rendszerben, nem a Notionban) - azt frissítjük, nem duplikálunk.
        szerzodes = db.scalar(
            select(Contract).where(
                Contract.project_id == project_id,
                Contract.employee_id == employee_id,
                Contract.tipus == ContractType.ALVALLALKOZOI,
            )
        )
        uj = szerzodes is None
        if uj:
            szerzodes = Contract(
                tipus=ContractType.ALVALLALKOZOI,
                project_id=project_id,
                employee_id=employee_id,
                keretszerzodes=False,
            )
            db.add(szerzodes)
        db.flush()
        _jegyezd_fel(db, kulcs, "Contract", szerzodes.id)
        result.created += 1 if uj else 0
        result.updated += 0 if uj else 1
    else:
        result.updated += 1

    _kiegeszit(
        szerzodes,
        {
            **_cegadat(props),
            "megbizas_targya": _szoveg_mezo(props, "Megbízás Tárgya szerződés", "Megbízás Tárgya"),
            "netto_osszeg": props.get("Nettó összeg"),
            "keltezes": as_date(props.get("Keltezés szerződés")),
            "teljesites_szoveg": _teljesites_szoveg(props.get("Teljesítési idő szerződés")),
            "plusz_afa": _plusz_afa(props.get("Plusz ÁFA")),
        },
    )
    # Az ÁLLAPOT a Notion szerint: ami ott elkészült, az nálunk lezárt - épp
    # ezért nem kéri többé az Utókövetés.
    szerzodes.szerzodes_allapota = LEZART
    ujak = files.atemel_mindent(db, props, entity_type="contract", entity_id=szerzodes.id, result=result)
    uj_url = files.elso(ujak, "Szerződés aláírva") or _first_url(props.get("Szerződés aláírva"))
    if uj_url and not szerzodes.szerzodes_file_url:
        szerzodes.szerzodes_file_url = uj_url[:500]
    if uj_url:
        szerzodes.alairva = True


def _teljesites_szoveg(ertek) -> str | None:
    """A Notion dátum(tartomány) a mi szabad szöveges teljesítés-mezőnkre.

    A rendszerben ez szándékosan szöveg (nem mindig naptári intervallum), az
    importált soroknál viszont dátum áll rendelkezésre - ugyanabban a
    formában írjuk le, ahogy a generált szerződésre kerülne. Tartományt az
    extract_properties már lelapított "kezdő – záró" alakban ad (lásd
    client.py), ezt bontjuk vissza."""
    if not ertek:
        return None
    szoveg = str(ertek)
    kezdet_s, _, veg_s = szoveg.partition(" – ")
    kezdet_d, veg_d = as_date(kezdet_s), as_date(veg_s) if veg_s else None
    if kezdet_d is None:
        return None
    if veg_d and veg_d != kezdet_d:
        return f"{kezdet_d.strftime('%Y.%m.%d.')} - {veg_d.strftime('%Y.%m.%d.')}"
    return kezdet_d.strftime("%Y.%m.%d.")


def _tig_importalasa(
    db: Session, result: ImportResult, page: dict, props: dict, project_id: int, employee_id: int
) -> None:
    if _text(props.get("Állapot")) not in TIG_KESZ:
        return

    kulcs = f"kulsos-tig:{page['id']}"
    tig = _mar_letezik(db, kulcs, PerformanceCertificate)
    if tig is None:
        tig = db.scalar(
            select(PerformanceCertificate).where(
                PerformanceCertificate.project_id == project_id,
                PerformanceCertificate.employee_id == employee_id,
            )
        )
        uj = tig is None
        if uj:
            tig = PerformanceCertificate(project_id=project_id, employee_id=employee_id)
            db.add(tig)
        db.flush()
        _jegyezd_fel(db, kulcs, "PerformanceCertificate", tig.id)
        result.created += 1 if uj else 0
        result.updated += 0 if uj else 1
    else:
        result.updated += 1

    # A TIG a TÉTELEIN keresztül mondja meg, KINEK a munkáját igazolja (lásd
    # models/performance_certificate.py), és a "hiányzik-e még TIG" kérdésre is
    # ezek válaszolnak, ha az illetőt MÁS számlázza (lásd
    # routes/performance_certificates._csoport_fedve). Tétel nélkül tehát a
    # rendszer akkor is kérné a papírt, amikor az már megvan - ezért minden
    # futásnál ellenőrizzük, nem csak a most létrehozott TIG-eknél.
    if not any(t.project_id == project_id and t.employee_id == employee_id for t in tig.tetelek):
        tig.tetelek.append(PerformanceCertificateTetel(project_id=project_id, employee_id=employee_id))
        db.flush()

    _kiegeszit(
        tig,
        {
            "ceg_neve": _szoveg_mezo(props, "Vállalkozás név", "Vállalkozás neve", "Név"),
            "szekhely": _szoveg_mezo(props, "Székhely"),
            "adoszam": _szoveg_mezo(props, "Adószám"),
            "email": _szoveg_mezo(props, "email", "Email"),
            "megbizas_targya": _szoveg_mezo(props, "Megbízás Tárgya"),
            "netto_osszeg": props.get("Nettó TIG"),
            "plusz_afa": _plusz_afa(props.get("TIG plusz ÁFA")),
            "teljesites_szoveg": _teljesites_szoveg(props.get("Teljesítési idő")),
            "keltezes": as_date(props.get("Keltezési idő")),
        },
    )
    tig.allapot = LEZART
    ujak = files.atemel_mindent(db, props, entity_type="performance_certificate", entity_id=tig.id, result=result)
    uj_url = files.elso(ujak, "TIG csatolás") or _text(props.get("TIG aláírva"))
    if uj_url and not tig.file_url:
        tig.file_url = uj_url[:500]
    # A "Kifizettük és számla feltöltve" a Notionban a lezárt pénzügyi állapot.
    if _text(props.get("Számla állapot")) == "Kifizettük és számla feltöltve":
        tig.szamla_kifizetve = True


def import_kulsos_papirok(client: NotionClient, db: Session) -> ImportResult:
    """Eseti szerződés + külsős TIG <- a Notion 'Külsős' tábla.

    Csak a Project és az Employee import UTÁN futtatható: soronként mindkét
    relationt fel kell oldani, enélkül nincs mihez kötni a papírt."""
    result = ImportResult(entity_type="Contract+PerformanceCertificate (Külsős)")

    for page in client.query_database(db_ids.KULSOS):
        props = extract_properties(page, client)
        employee_id = resolve_relation_id(db, "Employee", _mezo_lista(props, *EMBER_MEZOK))
        project_id = _projekt_azonositasa(db, props)
        if employee_id is None or project_id is None:
            result.skipped += 1
            # A KÉSZ papírok kimaradása a fájdalmas: azoknál a rendszer úgy
            # mutatja, mintha a teendő még hátra lenne. Ezért a napló külön
            # kiírja, MI hiányzott - abból látszik, mit kell előbb importálni.
            if _text(props.get("Állapot")) in TIG_KESZ:
                result.hianyzo_kesz_tig += 1
            hiany = "munkatárs" if employee_id is None else "forgatás"
            result.errors.append(
                f"Külsős papír '{_text(props.get('Név')) or page['id']}': nem azonosítható a {hiany} - "
                "a sor kimarad, mert nincs mihez kötni."
            )
            continue
        if _text(props.get("Állapot")) in TIG_KESZ:
            result.notion_kesz_tig += 1
        try:
            with db.begin_nested():
                _szerzodes_importalasa(db, result, page, props, project_id, employee_id)
                _tig_importalasa(db, result, page, props, project_id, employee_id)
                db.flush()
        except Exception as exc:  # noqa: BLE001 - soronkénti izoláció
            result.errors.append(
                f"Külsős papír '{_text(props.get('Név')) or page['id']}': {type(exc).__name__}: {exc}"
            )

    return result
