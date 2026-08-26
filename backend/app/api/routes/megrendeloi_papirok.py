"""Megrendelői papírozás: eseti szerződés és TIG a MEGRENDELŐ felé.

Ugyanaz a folyamat, mint az alvállalkozói oldalon (lásd
routes/subcontractor_contracts.py és performance_certificates.py), csak a
másik irányba - ezért ugyanazok a műveletek is:

    piszkozat mentése -> generálás és kiküldés -> aláírt példány feltöltése
                      \\-> kihagyás (indokkal)  \\-> saját papír feltöltése

A sablonok a csatolt Notion-programokból jönnek (megrendelo-eseti,
megrendelo-keretszerzodes, TIG-megrendelo-email): a placeholder-nevek egy az
egyben azok, amiket azok a programok cserélnek - így ugyanaz a Google Docs
sablon használható tovább, nem kell újat gyártani.
"""

from __future__ import annotations

import os
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user, require_page_action
from app.models.contract import Contract
from app.models.employee import Employee
from app.models.megrendeloi_papir import ALLAPOTOK, LEZART_ALLAPOTOK, MegrendeloiSzerzodes, MegrendeloiTig
from app.models.project_code import ProjectCode
from app.services import document_storage, megrendeloi_papir, megrendeloi_szamla
from app.services.gdoc_template import gdoc_fill_export_and_store_pdf
from app.services.google_email import send_message
from app.services import penznem as penznem_szolg
from app.services.hu_number_words import szam_betukkel

router = APIRouter(prefix="/megrendeloi-papirok", tags=["megrendeloi-papirok"])

PAGE = "/projektek/project-kodok"

#: A két papírfajta. A `kulcs` megy az útvonalba, hogy egy komponens
#: szolgálhassa ki mindkettőt a felületen.
SZERZODES = "szerzodes"
TIG = "tig"


def _modell(fajta: str):
    if fajta == SZERZODES:
        return MegrendeloiSzerzodes
    if fajta == TIG:
        return MegrendeloiTig
    raise HTTPException(status_code=404, detail=f"Ismeretlen papírfajta: {fajta}")


def _sablon(fajta: str) -> tuple[str, str]:
    """(sablon-azonosító, beállítás neve) - a hibaüzenethez is kell a név."""
    if fajta == SZERZODES:
        return settings.gdoc_megrendeloi_eseti_template_id, "GDOC_MEGRENDELOI_ESETI_TEMPLATE_ID"
    return settings.gdoc_megrendeloi_tig_template_id, "GDOC_MEGRENDELOI_TIG_TEMPLATE_ID"


def _projektkod_vagy_404(db: Session, project_code_id: int) -> ProjectCode:
    pk = db.get(ProjectCode, project_code_id)
    if pk is None:
        raise HTTPException(status_code=404, detail="Ez a projektkód nem található.")
    return pk


# ─────────────────────────────────────────────────────────────────────────────
# Séma
# ─────────────────────────────────────────────────────────────────────────────


class PapirIn(BaseModel):
    """A papír adatai. MINDEN mező szerkeszthető, azok is, amiket az ügyfél
    adatlapjáról töltöttünk elő - a papírra a beküldött érték kerül."""

    client_id: int | None = None
    contact_id: int | None = None
    keretszerzodes_id: int | None = None

    ceg_neve: str | None = None
    szekhely: str | None = None
    adoszam: str | None = None
    kepviselo: str | None = None
    nyilvantartasi_szam: str | None = None
    email: str | None = None

    megbizas_targya: str | None = None
    projekt_nev: str | None = None
    teljesites_szoveg: str | None = None
    netto_osszeg: float | None = None
    plusz_afa: bool | None = None
    keltezes: date | None = None
    megjegyzes: str | None = None


class PapirRead(PapirIn):
    id: int
    project_code_id: int
    fajta: str
    allapot: str | None = None
    file_url: str | None = None
    alairt_file_url: str | None = None
    kihagyas_oka: str | None = None
    #: Kiment, de az aláírt példány még nem jött vissza.
    alairasra_var: bool = False
    projektkod: str | None = None
    #: A PROJEKTKÓD projektneve - a gyűjtőlista ezt mutatja, ha magára a
    #: papírra nem írtak külön projektnevet (lásd
    #: components/megrendeloi/MegrendeloiPapirokOldal.tsx).
    projektkod_projekt_nev: str | None = None
    #: MILYEN PÉNZNEMBEN vállaltuk (a projektkódról). A papíron az az összeg
    #: áll, amiben megállapodtunk - a bevétel ettől még forintban keletkezik
    #: (lásd services/penznem.py).
    penznem: str = "HUF"


class ElotoltesOut(BaseModel):
    """Amivel egy ÚJ papír indul - a legjobb ismert forrásból előtöltve."""

    client_id: int | None = None
    contact_id: int | None = None
    keretszerzodes_id: int | None = None
    ceg_neve: str | None = None
    szekhely: str | None = None
    adoszam: str | None = None
    kepviselo: str | None = None
    nyilvantartasi_szam: str | None = None
    email: str | None = None
    megbizas_targya: str | None = None
    projekt_nev: str | None = None
    teljesites_szoveg: str | None = None
    netto_osszeg: float | None = None
    plusz_afa: bool | None = None
    #: Honnan jöttek az adatok: "keretszerzodes" | "ugyfel" | "kontakt" | "projektkod"
    forras: str = "ugyfel"
    #: Van-e élő keretszerződés a céggel - ilyenkor az eseti szerződés
    #: elhagyható (a TIG NEM, lásd services/megrendeloi_papir.py).
    van_elo_keretszerzodes: bool = False


def _f(ertek) -> float | None:
    return float(ertek) if ertek is not None else None


def _kimenet(papir, fajta: str) -> PapirRead:
    return PapirRead(
        id=papir.id,
        project_code_id=papir.project_code_id,
        fajta=fajta,
        client_id=papir.client_id,
        contact_id=papir.contact_id,
        keretszerzodes_id=papir.keretszerzodes_id,
        ceg_neve=papir.ceg_neve,
        szekhely=papir.szekhely,
        adoszam=papir.adoszam,
        kepviselo=papir.kepviselo,
        nyilvantartasi_szam=papir.nyilvantartasi_szam,
        email=papir.email,
        megbizas_targya=papir.megbizas_targya,
        projekt_nev=papir.projekt_nev,
        teljesites_szoveg=papir.teljesites_szoveg,
        netto_osszeg=_f(papir.netto_osszeg),
        plusz_afa=papir.plusz_afa,
        keltezes=papir.keltezes,
        megjegyzes=papir.megjegyzes,
        allapot=papir.allapot,
        file_url=papir.file_url,
        alairt_file_url=papir.alairt_file_url,
        kihagyas_oka=papir.kihagyas_oka,
        alairasra_var=papir.allapot == "Kiküldve" and not papir.alairt_file_url,
        projektkod=papir.project_code.projektkod if papir.project_code else None,
        projektkod_projekt_nev=papir.project_code.project_nev if papir.project_code else None,
        penznem=penznem_szolg.normalizald(getattr(papir.project_code, "penznem", None)),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Lekérdezés
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/{fajta}/elotoltes/{project_code_id}", response_model=ElotoltesOut)
def get_elotoltes(
    fajta: str,
    project_code_id: int,
    client_id: int | None = None,
    contact_id: int | None = None,
    keretszerzodes_id: int | None = None,
    db: Session = Depends(get_db),
    _user: Employee = Depends(get_current_user),
):
    """Egy új papír előtöltése.

    A szerződő fél a keretszerződésből VAGY a megrendelői kontaktokból jön, és
    az összes cégadatot hozza magával (lásd
    services/megrendeloi_papir.szerzodo_fel_adatai) - a felületen mind
    szerkeszthető."""
    _modell(fajta)
    pk = _projektkod_vagy_404(db, project_code_id)

    # A TIG UGYANARRÓL A MUNKÁRÓL szól, mint a szerződés: amit oda egyszer
    # beírtak, azt itt ne kelljen újra begépelni (ugyanaz a minta, mint az
    # alvállalkozói oldalon - lásd 06-papirozas.md "A TIG a szerződésből
    # indul"). Két forrás jöhet szóba, ebben a sorrendben:
    #
    # 1. a projektkódra készült megrendelői SZERZŐDÉS - azon már pontosított
    #    cégadatok és összeg állnak;
    # 2. a projektkódra kötött KERETSZERZŐDÉS - keret alatt eseti szerződés
    #    nincs, tehát a cégadat onnan a legjobb.
    korabbi = None
    if fajta == TIG:
        korabbi = db.scalars(
            select(MegrendeloiSzerzodes)
            .where(MegrendeloiSzerzodes.project_code_id == pk.id)
            .order_by(MegrendeloiSzerzodes.id.desc())
        ).first()
        if keretszerzodes_id is None and pk.contract_id is not None and pk.keret_fedi:
            keretszerzodes_id = pk.contract_id

    fel = megrendeloi_papir.szerzodo_fel_adatai(
        db, pk, client_id=client_id, contact_id=contact_id, keretszerzodes_id=keretszerzodes_id
    )
    if korabbi is not None:
        # A szerződésen lévő adat az ELSŐDLEGES: azt egyszer már ellenőrizték
        # és kiküldték. Csak a kitöltött mezők számítanak - egy üresen hagyott
        # mező ne törölje a máshonnan tudott értéket.
        fel.client_id = korabbi.client_id or fel.client_id
        fel.contact_id = korabbi.contact_id or fel.contact_id
        fel.keretszerzodes_id = korabbi.keretszerzodes_id or fel.keretszerzodes_id
        fel.ceg_neve = korabbi.ceg_neve or fel.ceg_neve
        fel.szekhely = korabbi.szekhely or fel.szekhely
        fel.adoszam = korabbi.adoszam or fel.adoszam
        fel.kepviselo = korabbi.kepviselo or fel.kepviselo
        fel.nyilvantartasi_szam = korabbi.nyilvantartasi_szam or fel.nyilvantartasi_szam
        fel.email = korabbi.email or fel.email
    keret = megrendeloi_papir.keretszerzodes_fedi(db, fel.client_id, pk.datum)
    return ElotoltesOut(
        client_id=fel.client_id,
        contact_id=fel.contact_id,
        keretszerzodes_id=fel.keretszerzodes_id,
        ceg_neve=fel.ceg_neve,
        szekhely=fel.szekhely,
        adoszam=fel.adoszam,
        kepviselo=fel.kepviselo,
        nyilvantartasi_szam=fel.nyilvantartasi_szam,
        email=fel.email,
        # A tárgy és az összeg a SZERZŐDÉSRŐL jön, ha van - azt ott már
        # megfogalmazták -, különben a projektkódról.
        megbizas_targya=(korabbi.megbizas_targya if korabbi else None)
        or pk.megbizas_targya
        or pk.szerzodes_targya,
        projekt_nev=(korabbi.projekt_nev if korabbi else None)
        or pk.szerzodes_projekt_nev
        or pk.project_nev
        or pk.tig_projektnev,
        teljesites_szoveg=(pk.tig_teljesitesi_ido or pk.teljesites)
        if fajta == TIG
        else (pk.teljesites or pk.tig_teljesitesi_ido),
        # A papírfajtájához tartozó összeg az elsődleges, de ha az üres, a
        # projektkód általános nettója is jobb, mint egy üresen induló mező -
        # ugyanez a visszaesés van a tárgynál és a projekt nevénél is. A két
        # oszlop külön Notion-örökség, és a régi sorokon jellemzően csak az
        # egyik van kitöltve.
        netto_osszeg=_f(korabbi.netto_osszeg if korabbi and korabbi.netto_osszeg is not None else None)
        or _f(
            (pk.szerzodes_netto_osszeg or pk.netto_osszeg)
            if fajta == SZERZODES
            else (pk.netto_osszeg or pk.szerzodes_netto_osszeg)
        ),
        plusz_afa=bool(korabbi.plusz_afa) if korabbi and korabbi.plusz_afa is not None
        else bool(pk.szerzodes_plusz_afa or pk.plusz_afa),
        forras=fel.forras,
        van_elo_keretszerzodes=keret is not None,
    )


@router.get("/megbizas-targya-lista", response_model=list[str])
def megbizas_targya_lista(
    db: Session = Depends(get_db),
    _user: Employee = Depends(get_current_user),
) -> list[str]:
    """A megrendelői papírokon eddig előfordult "megbízás tárgya" szövegek,
    ábécé szerint - az űrlapon ebből válogat a felhasználó, hogy ne kelljen
    mindig ugyanazt begépelnie. A lista NEM zárt (lásd
    services/entity_registry.NYITOTT_SELECT_MEZOK, ugyanaz a minta, csak a
    megrendelői oldalra, külön vokabuláriummal - az alvállalkozói "megbízás
    tárgya" mást jelent, nem ugyanarra a munkára mutat): egy új szöveg
    beírásával és a papír mentésével a következő betöltéskor magától
    megjelenik itt is, külön karbantartás nélkül.
    FONTOS: ez a route a `/{fajta}` elé regisztrálva - egy szó szerinti
    útvonal a `{fajta}` paraméteres útvonallal szemben csak akkor nyer, ha
    KORÁBBAN van bejegyezve (lásd routes/attachments.py hasonló esetét)."""
    ertekek: set[str] = set()
    for model in (MegrendeloiSzerzodes, MegrendeloiTig):
        for (ertek,) in db.execute(select(model.megbizas_targya).where(model.megbizas_targya.is_not(None)).distinct()):
            szoveg = (ertek or "").strip()
            if szoveg:
                ertekek.add(szoveg)
    return sorted(ertekek, key=lambda s: s.lower())


@router.get("/{fajta}", response_model=list[PapirRead])
def list_papirok(
    fajta: str,
    project_code_id: int | None = None,
    db: Session = Depends(get_db),
    _user: Employee = Depends(get_current_user),
):
    """Gyűjtőlista - projektkód nélkül az ÖSSZES papír, a kihagyottakkal együtt.

    A kihagyottak azért maradnak benne, mert a kihagyás indoka is információ:
    ha eltűnnének, csak az látszana, hogy "nincs papír", az pedig hiányosságnak
    néz ki, nem döntésnek (ugyanaz a szabály, mint a külsős TIG-eknél)."""
    modell = _modell(fajta)
    stmt = select(modell)
    if project_code_id is not None:
        stmt = stmt.where(modell.project_code_id == project_code_id)
    sorok = db.scalars(stmt.order_by(modell.id.desc())).all()
    return [_kimenet(p, fajta) for p in sorok]


# ─────────────────────────────────────────────────────────────────────────────
# Írás
# ─────────────────────────────────────────────────────────────────────────────


def _alkalmaz(papir, payload: PapirIn) -> None:
    for mezo, ertek in payload.model_dump(exclude_unset=True).items():
        setattr(papir, mezo, ertek)


# MIÉRT NINCS "keret visszakötése"?
#
# Egy eseti papír mentése korábban ráírta a papír keretszerződését a
# PROJEKTKÓDRA is (`contract_id`). Ez csendben átbillentette a projektkódot
# "keretszerződés alatt" állapotba - és onnantól a felület azt mondta, hogy
# eseti szerződés NEM KELL, pont abban a pillanatban, amikor a felhasználó
# éppen egy eseti szerződést készített.
#
# A papír `keretszerzodes_id` mezője csak azt mondja meg, HONNAN vettük a
# cégadatokat (az előtöltés akkor is felkínálja az ügyfél élő keretét, ha a
# felhasználó hozzá sem nyúlt). A projektkód `contract_id` mezője viszont egy
# ÁLLÍTÁS: ezt a munkát a keret fedi, tehát nem kérünk rá papírt. A kettő nem
# ugyanaz, és egy javaslatból nem lehet némán állítás - ez az a hiba, ami ellen
# a models/project_code.keret_fedi kommentje is szól: ez a jelölés TEENDŐT
# TÜNTET EL, tévesen állítva pont a hiányzó papírokat rejti el.
#
# A keret-kötés ezért kimondott döntés maradt, a projektkód saját
# "Keretszerződés alatt" kapcsolóján (lásd set_keret_kotes és a
# components/megrendeloi/KeretKotes.tsx).


def _uj_vagy_meglevo(db: Session, fajta: str, project_code_id: int, papir_id: int | None):
    modell = _modell(fajta)
    if papir_id is not None:
        papir = db.get(modell, papir_id)
        if papir is None:
            raise HTTPException(status_code=404, detail="Ez a papír nem található.")
        return papir
    papir = modell(project_code_id=project_code_id, allapot="Készítés alatt")
    db.add(papir)
    return papir


@router.post("/{fajta}/{project_code_id}/mentes", response_model=PapirRead)
def save_papir(
    fajta: str,
    project_code_id: int,
    payload: PapirIn,
    papir_id: int | None = None,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """Piszkozat mentése kiküldés nélkül."""
    _projektkod_vagy_404(db, project_code_id)
    papir = _uj_vagy_meglevo(db, fajta, project_code_id, papir_id)
    _alkalmaz(papir, payload)
    db.commit()
    db.refresh(papir)
    return _kimenet(papir, fajta)


def _sablon_mezok(papir, fajta: str) -> dict[str, str]:
    """A Google Docs sablon placeholder-ei.

    A nevek a csatolt Notion-programokból származnak (megrendelo-eseti/gdocs.py
    és TIG-megrendelo-email/gdocs.py) - egy az egyben, hogy a MEGLÉVŐ sablonok
    változtatás nélkül működjenek tovább."""
    netto = float(papir.netto_osszeg or 0)
    # MILYEN PÉNZNEMBEN vállaltuk. A papíron az az összeg áll, amiben
    # megállapodtunk: ha a megbízás euróban szól, a szerződésen és a TIG-en is
    # euró a helyes (a bevétel ettől még forintban keletkezik - lásd
    # services/penznem.py). A sablon a {{penznem}} és a {{penznem_szoveg}}
    # helyőrzővel tudja kiírni; a régi, "Ft"-et fixen tartalmazó sablonokat
    # ezekre kell átírni, hogy a devizás papír is helyes legyen.
    kod = penznem_szolg.normalizald(getattr(papir.project_code, "penznem", None))
    mezok = {
        "nev": papir.ceg_neve or "",
        "hely": papir.szekhely or "",
        "adoszam": papir.adoszam or "",
        "targy": papir.megbizas_targya or "",
        "tido": papir.teljesites_szoveg or "",
        # Ezres elválasztó szóközzel, ahogy az eredeti programok írják.
        "netto": f"{netto:,.0f}".replace(",", " "),
        "nettoki": szam_betukkel(netto),
        "penznem": "Ft" if kod == penznem_szolg.FORINT else kod,
        "penznem_szoveg": penznem_szolg.szoveggel(kod),
        "kelt": papir.keltezes.strftime("%Y.%m.%d.") if papir.keltezes else "",
        "afa": "+ ÁFA" if papir.plusz_afa else "",
        "nyilvszam": papir.nyilvantartasi_szam or "",
        "kepvis": papir.kepviselo or "",
    }
    if fajta == SZERZODES:
        mezok["projektnev"] = papir.projekt_nev or ""
        # Az eredeti program a teljesítés szövegét teszi a {{napok}} helyére is.
        mezok["napok"] = papir.teljesites_szoveg or ""
    else:
        mezok["projkod"] = papir.project_code.projektkod if papir.project_code else ""
    return mezok


_EMAIL_HTML = """\
<p>Kedves Partnerünk!</p>
<p>Mellékelten küldjük a(z) <b>{projekt}</b> projekthez tartozó {papir}.<br>
Kérjük, ellenőrizzék az adatokat, és aláírva szíveskedjenek visszaküldeni.</p>
<p>Köszönettel,<br>HYPE Productions Kft.</p>
"""


def _projekt_neve(papir, pk: ProjectCode) -> str:
    """A PROJEKT NEVE a levélhez - nem a projektkód.

    A levél a MEGRENDELŐNEK megy, ő pedig a projektet a nevén ismeri
    ("Tavaszi kampányfilm"); a HYPE26-014 a mi belső azonosítónk, neki semmit
    nem mond. A tárgysorban és a levél szövegében ezért a név áll.

    A sorrend azért ez: elöl az, ami a PAPÍRON is szerepel - a megrendelő a
    csatolmányon ugyanezt a nevet látja -, utána a projektkódon nyilvántartott
    nevek (ugyanaz a visszaesés, mint az űrlap előtöltésénél), és csak legvégső
    esetben maga a kód. Név nélküli tárgysor rosszabb volna, mint egy kód."""
    jeloltek = (
        getattr(papir, "projekt_nev", None),
        pk.szerzodes_projekt_nev,
        pk.project_nev,
        pk.tig_projektnev,
        pk.projektkod,
    )
    return next((str(j).strip() for j in jeloltek if j and str(j).strip()), "")


@router.post("/{fajta}/{project_code_id}/generalas-es-kuldes", response_model=PapirRead)
def generate_and_send(
    fajta: str,
    project_code_id: int,
    payload: PapirIn,
    papir_id: int | None = None,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "create")),
):
    """A papír generálása a sablonból és azonnali kiküldése e-mailben.

    Sablon nélkül nem küldünk: egy PDF nélküli levél nem ér semmit, ezért
    inkább beszédes hibát adunk a hiányzó beállítás nevével."""
    pk = _projektkod_vagy_404(db, project_code_id)
    papir = _uj_vagy_meglevo(db, fajta, project_code_id, papir_id)
    _alkalmaz(papir, payload)
    db.flush()

    if not papir.email:
        raise HTTPException(status_code=400, detail="Nincs e-mail cím, így nem lehet kiküldeni a papírt.")
    sablon_id, beallitas_nev = _sablon(fajta)
    if not sablon_id:
        db.commit()
        raise HTTPException(
            status_code=503,
            detail=(
                f"Nincs beállítva a dokumentum-sablon, így a PDF nem generálható. "
                f"Állítsd be a {beallitas_nev} környezeti változót a backendhez."
            ),
        )

    papir.keltezes = papir.keltezes or date.today()
    cimke = "megrendelői szerződés" if fajta == SZERZODES else "teljesítési igazolás"
    base_name = f"{pk.projektkod}_{papir.ceg_neve or 'megrendelo'}_{'szerzodes' if fajta == SZERZODES else 'TIG'}"
    try:
        pdf_bytes, pdf_link = gdoc_fill_export_and_store_pdf(
            template_file_id=sablon_id,
            base_name=base_name,
            fields=_sablon_mezok(papir, fajta),
            output_folder_id=settings.gdoc_output_folder_id or settings.drive_folder_id or None,
        )
        # A LEVÉLBEN a projekt NEVE megy, nem a kódja - a fájlnévben viszont
        # marad a kód: az iktatáshoz az a jó, mert egyedi.
        projekt_neve = _projekt_neve(papir, pk)
        send_message(
            [papir.email],
            f"{projekt_neve} – {cimke}" if projekt_neve else cimke.capitalize(),
            _EMAIL_HTML.format(projekt=projekt_neve, papir=cimke),
            pdf_bytes=pdf_bytes,
            pdf_filename=f"{base_name}.pdf",
        )
    except RuntimeError as exc:
        # A kitöltött adatokat akkor is mentsük, ha a küldés elhasal (pl.
        # hiányzó Google hitelesítő adat) - ne vesszen el az eddigi munka.
        db.commit()
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    papir.allapot = "Kiküldve"
    papir.file_url = pdf_link
    db.commit()
    db.refresh(papir)
    return _kimenet(papir, fajta)


class AllapotIn(BaseModel):
    allapot: str


@router.post("/{fajta}/{papir_id}/allapot", response_model=PapirRead)
def set_allapot(
    fajta: str,
    papir_id: int,
    payload: AllapotIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """Az állapot kézi átállítása - egy tévesen kiküldöttre állított papír
    visszavehető, és újra elkészíthető."""
    if payload.allapot not in ALLAPOTOK:
        raise HTTPException(status_code=400, detail=f"Ismeretlen állapot. Választható: {', '.join(ALLAPOTOK)}")
    papir = db.get(_modell(fajta), papir_id)
    if papir is None:
        raise HTTPException(status_code=404, detail="Ez a papír nem található.")
    papir.allapot = payload.allapot
    db.commit()
    db.refresh(papir)
    return _kimenet(papir, fajta)


class KihagyasIn(BaseModel):
    kihagyas_oka: str | None = None


class KeretKotesIn(BaseModel):
    """A projektkód keretszerződés alá helyezése (vagy a kötés oldása).

    Kétféleképp lehet megadni: konkrét keretszerződéssel, vagy csak az
    ÜGYFÉLLEL - utóbbinál mi keressük meg az élő keretét. Üres `client_id` és
    üres `keretszerzodes_id` = a kötés oldása."""

    client_id: int | None = None
    keretszerzodes_id: int | None = None


class KeretKotesOut(BaseModel):
    keret_fedi: bool
    keretszerzodes_id: int | None = None
    keretszerzodes_neve: str | None = None
    client_id: int | None = None


@router.post("/keret-kotes/{project_code_id}", response_model=KeretKotesOut)
def set_keret_kotes(
    project_code_id: int,
    payload: KeretKotesIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """"Ez a munka keretszerződés alatt van" - a projektkód rákötése a
    megrendelői keretszerződésre.

    Ettől a kódtól nem kérünk eseti szerződést: a szerződés-lépés kész, és már
    csak a TIG van hátra. A kötés a PROJEKTKÓDON él (`contract_id`), nem az
    ügyfélen - egy megrendelővel köthetünk keretet úgy is, hogy nem minden
    munkája tartozik alá (lásd models/project_code.keret_fedi).

    Ügyfelet megadva magunk keressük meg az élő keretét: a felületen így elég
    kiválasztani, kiről van szó."""
    pk = _projektkod_vagy_404(db, project_code_id)

    if payload.keretszerzodes_id is None and payload.client_id is None:
        pk.contract_id = None
        db.commit()
        return KeretKotesOut(keret_fedi=False, client_id=pk.client_id)

    keret: Contract | None = None
    if payload.keretszerzodes_id is not None:
        keret = db.get(Contract, payload.keretszerzodes_id)
        if keret is None or not megrendeloi_papir.megrendeloi_keret_ervenyes(keret, pk.datum):
            raise HTTPException(
                status_code=400,
                detail="Ez a keretszerződés nem érvényes erre a munkára (nem aktív, vagy nem fedi a dátumát).",
            )
    else:
        keret = megrendeloi_papir.keretszerzodes_fedi(db, payload.client_id, pk.datum)
        if keret is None:
            raise HTTPException(
                status_code=400,
                detail="Ennek az ügyfélnek nincs élő keretszerződése - eseti szerződést kell készíteni.",
            )

    pk.contract_id = keret.id
    # Az ügyfél is a helyére kerül, ha eddig üres volt: a keret megmondja,
    # kiről van szó, és így a többi előtöltés is jó irányba indul.
    if pk.client_id is None and keret.client_id is not None:
        pk.client_id = keret.client_id
    db.commit()
    return KeretKotesOut(
        keret_fedi=True,
        keretszerzodes_id=keret.id,
        keretszerzodes_neve=keret.ceg_neve or (keret.client.nev if keret.client else None),
        client_id=pk.client_id,
    )


@router.post("/{fajta}/{project_code_id}/kihagyas", response_model=PapirRead)
def skip_papir(
    fajta: str,
    project_code_id: int,
    payload: KihagyasIn,
    papir_id: int | None = None,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """Kihagyás - INDOKKAL.

    Az indok kötelező: enélkül fél év múlva csak annyi látszana, hogy nincs
    papír, és nem lehetne megkülönböztetni a döntést a mulasztástól."""
    if not (payload.kihagyas_oka or "").strip():
        raise HTTPException(status_code=400, detail="A kihagyáshoz meg kell adni az okát.")
    _projektkod_vagy_404(db, project_code_id)
    papir = _uj_vagy_meglevo(db, fajta, project_code_id, papir_id)
    papir.allapot = "Kihagyva"
    papir.kihagyas_oka = payload.kihagyas_oka.strip()
    db.commit()
    db.refresh(papir)
    return _kimenet(papir, fajta)


@router.post("/{fajta}/{project_code_id}/sajat-papir", response_model=PapirRead)
async def upload_sajat_papir(
    fajta: str,
    project_code_id: int,
    papir_id: int | None = None,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """SAJÁT papír feltöltése a generálás helyett.

    Nem minden papír itt készül: van, amit a megrendelő ad (a saját
    sablonjával), és van, ami régebbi, még a rendszer előtti.

    Az így feltöltött papír KÉSZ, ALÁÍRT papírnak számít. Ez nem kényelmi
    egyszerűsítés: amit ide feltöltenek, az a megvan-és-kész dokumentum, nem
    egy általunk generált piszkozat - nincs kinek kiküldeni, és nincs kitől
    visszavárni az aláírást. Korábban "Kiküldve, aláírásra vár"-ként állt itt,
    vagyis a felület örökre teendőt mutatott olyasmire, ami már le volt zárva.
    Ugyanez a szabály, mint a Notionból átvett papíroknál (lásd
    services/megrendeloi_papir_atvetel.ATVETT_ALLAPOT)."""
    _projektkod_vagy_404(db, project_code_id)
    papir = _uj_vagy_meglevo(db, fajta, project_code_id, papir_id)
    db.flush()
    data = await file.read()
    regi_kulcs = papir.file_storage_key
    kulcs = f"megrendelo-{fajta}/{project_code_id}/{papir.id}{os.path.splitext(file.filename or '')[1] or '.pdf'}"
    papir.file_url = document_storage.upload_bytes(
        data, kulcs, file.content_type or "application/octet-stream"
    )
    papir.file_storage_key = kulcs
    # Ugyanaz a fájl az aláírt példány is. A tárhely-kulcsot SZÁNDÉKOSAN nem
    # másoljuk át: egy fájl van, egy kulccsal - különben a törlés kétszer
    # próbálná eldobni ugyanazt az objektumot.
    if not papir.alairt_file_url:
        papir.alairt_file_url = papir.file_url
    if papir.allapot not in LEZART_ALLAPOTOK:
        papir.allapot = "Van már papír"
    db.commit()
    if regi_kulcs and regi_kulcs != kulcs:
        document_storage.delete_object(regi_kulcs)
    db.refresh(papir)
    return _kimenet(papir, fajta)


@router.post("/{fajta}/{papir_id}/alairt-fajl", response_model=PapirRead)
async def upload_alairt(
    fajta: str,
    papir_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """Az ALÁÍRVA visszakapott példány. Amíg ez nincs meg, a papír
    "aláírásra vár" - a kiküldés önmagában még nem lezárt ügy.

    Az aláírt példány a LEGERŐSEBB bizonyíték: ha megvan, a papír kész, akkor
    is, ha a nyilvántartásban még piszkozatként állt. Enélkül egy piszkozatba
    feltöltött aláírt szerződés "Készítés alatt" maradt - a felület teendőt
    mutatott arra, ami már alá volt írva."""
    papir = db.get(_modell(fajta), papir_id)
    if papir is None:
        raise HTTPException(status_code=404, detail="Ez a papír nem található.")
    data = await file.read()
    regi_kulcs = papir.alairt_file_storage_key
    kulcs = f"megrendelo-{fajta}-alairt/{papir.project_code_id}/{papir.id}{os.path.splitext(file.filename or '')[1] or '.pdf'}"
    papir.alairt_file_url = document_storage.upload_bytes(
        data, kulcs, file.content_type or "application/octet-stream"
    )
    papir.alairt_file_storage_key = kulcs
    if papir.allapot not in LEZART_ALLAPOTOK:
        # Nem "Kiküldve": innen nem ment ki semmi. A papír megvan és alá van
        # írva - a fázis-nézetek ezt látják lezártnak (LEZART_ALLAPOTOK).
        papir.allapot = "Van már papír"
    db.commit()
    if regi_kulcs and regi_kulcs != kulcs:
        document_storage.delete_object(regi_kulcs)
    db.refresh(papir)
    return _kimenet(papir, fajta)


@router.delete("/{fajta}/{papir_id}", status_code=204)
def delete_papir(
    fajta: str,
    papir_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "delete")),
):
    """A papír törlése - utána tiszta lappal újrakezdhető.

    A tárhelyre feltöltött fájlokat is eldobjuk; a Drive-on lévő generált
    PDF-hez nem nyúlunk, mert az nem a mi tárhelyünk."""
    papir = db.get(_modell(fajta), papir_id)
    if papir is None:
        raise HTTPException(status_code=404, detail="Ez a papír nem található.")
    kulcsok = [k for k in (papir.file_storage_key, papir.alairt_file_storage_key) if k]
    db.delete(papir)
    db.commit()
    for k in kulcsok:
        document_storage.delete_object(k)


# ── A SZÁMLA lépése (a papírozás harmadik, utolsó szakasza) ──────────────────
# A szerződés és a TIG után jön a pénz: mikorra szól a számla, mikor fizették
# ki, és bekerül-e a Pénzügyek bevételei közé. A logika a szolgáltatásban van
# (lásd services/megrendeloi_szamla.py), itt csak a HTTP-felület.


class SzamlaAllasOut(BaseModel):
    fizetesi_hatarido: date | None = None
    kifizetes_datuma: date | None = None
    kifizetve: bool
    bevetelbe_ne_keruljon: bool
    bevetel_kihagyas_oka: str | None = None
    netto: float | None = None
    brutto: float | None = None
    van_szamla_fajl: bool
    szamla_url: str | None = None
    bevetel_sorok: int
    szamla_kihagyva: bool = False
    szamla_kihagyas_oka: str | None = None
    #: Kötelező-e a kifizetés dátuma. Ahol számlát sem várunk, ott nem: a
    #: legtöbbször nincs is tranzakció (lásd
    #: services/megrendeloi_szamla._kifizetes_datum_kell).
    kifizetes_datum_kell: bool = True
    #: Tranzakció NÉLKÜL lett lezárva - nincs kifizetési dátuma, és ez nem
    #: hiány, hanem maga a válasz.
    tranzakcio_nelkul_lezarva: bool = False
    hatarido_kell: bool = True
    #: Milyen pénznemben vállaltuk a munkát. A `netto`/`brutto` EBBEN a
    #: pénznemben van (a szerződésen és a TIG-en is ez áll), a `*_forintban`
    #: pedig az, ami ténylegesen a Pénzügyekbe kerül - lásd
    #: services/penznem.py. Enélkül a kártya egy euró összeget írt ki
    #: forintként, mert a mezők nem jutottak ki a válaszból.
    penznem: str = "HUF"
    arfolyam: float | None = None
    netto_forintban: float | None = None
    brutto_forintban: float | None = None
    #: MENNYI IDŐ van a kifizetésig, vagy mennyivel csúszott - a fizetési
    #: határidőhöz mérve (lásd models/project_code.hatarido_allas).
    hatarido_allas: dict | None = None
    #: HOGYAN érkezett a pénz (Átutalás / Készpénz). Készpénznél a bevétel a
    #: kasszába is bekerül - a KP forgalom oldalon ugyanez a sor látszik.
    fizetes_modja: str | None = None
    keszpenzes: bool = False
    #: Készpénzes bevételnél ettől függ, hogy sima legális bevétel-e, vagy
    #: FEDEZET a számla nélküli kiadásokhoz (lásd services/bizonylat.py).
    van_szamla_a_bevetelen: bool = False


class KifizetesIn(BaseModel):
    #: Mikor érkezett meg a pénz. Ahol SZÁMLA van, ott kötelező (lásd
    #: services/megrendeloi_szamla._kifizetes_datum_kell); ahol nincs számla,
    #: ott üresen hagyva "tranzakció nélküli lezárás" lesz belőle.
    #: A jelölés ritkán esik egybe a
    #: beérkezéssel (a pénz megjön, és napokkal később kattint rá valaki),
    #: ezért nem tippelünk a mai nappal: ebből lesz a bevétel-sor dátuma.
    #: Lásd services/megrendeloi_szamla.jelold_kifizetettnek.
    kifizetes_datuma: date | None = None
    #: "Kifizetve, de ne kerüljön a bevételek közé" - ilyenkor INDOK kell.
    bevetelbe_ne_keruljon: bool = False
    kihagyas_oka: str | None = None
    #: HOGYAN érkezett a pénz: "Átutalás" vagy "Készpénz". Készpénznél a
    #: bevétel-sor a KASSZÁBA is bekerül (lásd services/kassza.py) - ezért nem
    #: tippelünk, hanem a jelöléskor megkérdezzük.
    fizetes_modja: str | None = None


def _projektkod_vagy_404(db: Session, project_code_id: int) -> ProjectCode:
    pk = db.get(ProjectCode, project_code_id)
    if pk is None:
        raise HTTPException(status_code=404, detail="Ez a projektkód nem található.")
    return pk


@router.get("/szamla/{project_code_id}", response_model=SzamlaAllasOut)
def get_szamla_allas(
    project_code_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(get_current_user),
):
    """Hol tart a számla-lépés ezen a projektkódon."""
    return megrendeloi_szamla.allas(db, _projektkod_vagy_404(db, project_code_id))


class SzamlaKihagyasIn(BaseModel):
    """"Erről a munkáról nincs számla" - be/ki, indokkal."""

    kihagyva: bool
    oka: str | None = None


# FIGYELEM: az útvonal NEM lehet ".../kihagyas" - azt a fentebb bejegyzett
# általános "/{fajta}/{project_code_id}/kihagyas" (papír kihagyása) nyelné el,
# és a hívás egy másik végponton kötne ki, érthetetlen hibaüzenettel.
@router.post("/szamla/{project_code_id}/nincs-szamla", response_model=SzamlaAllasOut)
def set_szamla_kihagyas(
    project_code_id: int,
    payload: SzamlaKihagyasIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """Nincs számla erről a munkáról - ilyenkor fizetési határidő sem kell a
    kifizetés jelöléséhez."""
    pk = _projektkod_vagy_404(db, project_code_id)
    try:
        allas = megrendeloi_szamla.allitsd_a_szamla_kihagyast(db, pk, kihagyva=payload.kihagyva, oka=payload.oka)
    except megrendeloi_szamla.SzamlaHiba as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return allas


@router.post("/szamla/{project_code_id}/kifizetve", response_model=SzamlaAllasOut)
def set_szamla_kifizetve(
    project_code_id: int,
    payload: KifizetesIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """"Kifizetve" - a pénz megérkezett. Alapból bevétel-sort is nyit."""
    pk = _projektkod_vagy_404(db, project_code_id)
    try:
        allas = megrendeloi_szamla.jelold_kifizetettnek(
            db,
            pk,
            kifizetes_datuma=payload.kifizetes_datuma,
            bevetelbe_ne_keruljon=payload.bevetelbe_ne_keruljon,
            kihagyas_oka=payload.kihagyas_oka,
            fizetes_modja=payload.fizetes_modja,
        )
    except megrendeloi_szamla.SzamlaHiba as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return allas


@router.post("/szamla/{project_code_id}/visszavonas", response_model=SzamlaAllasOut)
def szamla_kifizetes_visszavonasa(
    project_code_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """Mégsincs kifizetve - téves gombnyomás javítása."""
    pk = _projektkod_vagy_404(db, project_code_id)
    allas = megrendeloi_szamla.vond_vissza(db, pk)
    db.commit()
    return allas
