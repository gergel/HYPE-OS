"""Teljesítési igazolás (TIG) - miután egy projekten mindenkinek megvan az
eseti szerződése (lásd subcontractor_contracts.py - "Kiküldve" vagy
"Kihagyva" mindenkinél, akinek egyáltalán kellett), a projekt "TIG-re kész"
állapotba kerül: ekkor minden nem belsős stábtagnak (a keretszerződéseseknek
IS - a TIG a konkrét munka elvégzését igazolja, nem azt, hogy van-e álló
keretszerződése) teljesítési igazolást kell generálni és kiküldeni, vagy
kihagyni.

Ugyanaz a kétlépéses (mentés majd generálás-és-küldés, vagy kihagyás)
életciklus, mint az eseti szerződéseknél, csak külön táblában
(PerformanceCertificate) és a csatolt 'TIG-alvalalkozo' program
mezőkészletével/sablon-placeholdereivel."""

from __future__ import annotations

import os
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import or_, select, tuple_
from sqlalchemy.orm import Session, selectinload

from app.api.routes.subcontractor_contracts import (
    csoport_szerzodes_kesz,
    csoport_szerzodes_kesz_projektkodon,
    eseti_szerzodesek_a_projekten,
    eseti_szerzodesek_a_projektkodon,
    load_szerzodes_kornyezet,
    load_szerzodes_kornyezet_projektkodon,
    szamlazo_csoportok_projektkodon,
    szerzodest_igenylo_emberek_projektkodon,
)
from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user, require_page_action
from app.models.contract import Contract
from app.models.employee import Employee, EmployeeType
from app.models.finance import Expense
from app.models.performance_certificate import (
    PerformanceCertificate,
    PerformanceCertificateInvoice,
    PerformanceCertificateTetel,
)
from app.models.project import Project
from app.models.project_code import ProjectCode
from app.models.project_szamlazo import ProjectSzamlazo
from app.schemas.finance import KifizetesIn
from app.schemas.performance_certificate import PerformanceCertificateRead
from app.services import (
    belsos_idoszak,
    document_storage,
    megbeszelt_dij,
    papir_fedettseg,
    papir_tetelek,
    papirozas_hatokor,
    szamlazo,
)
from app.services.gdoc_template import gdoc_fill_and_export_pdf
from app.services.google_email import send_message
from app.services.hu_number_words import szam_betukkel
from app.services.szamlazo import SzamlazoCsoport, SzamlazoFel

router = APIRouter(prefix="/teljesitesi-igazolasok", tags=["performance-certificates"])

# Lásd subcontractor_contracts.py: a TIG-műveletek az Utókövetés oldalhoz
# tartoznak, külön menüpont nincs hozzájuk.
PAGE = "/utokovetes"

TERMINAL_STATUSES = {"Kiküldve", "Kihagyva"}

_TIG_EMAIL_HTML = """\
<p>Kedves Címzett,</p>
<p>
  Alább a <b>{projektdatum}</b> dátumú, tárgyban említett projekt kódú esemény teljesítési igazolása.<br>
  Kérjük figyelj rá, hogy a számla teljesítési dátuma egyezzen a teljesítési igazolás teljesítési dátumával.
</p>
<p>Köszönettel,</p>
<br><br>
<table cellpadding="0" cellspacing="0" style="font-family: Arial, sans-serif; font-size: 12px; color: #000;">
  <tr>
    <td style="vertical-align: middle; width: 150px;">
      <img src="https://raw.githubusercontent.com/gergel/ADMIN_projektkod/main/hype_logo_BG_03%20(2).png" alt="Hype logo" width="110">
    </td>
    <td style="padding-left: 20px; vertical-align: middle;">
      <p style="margin: 0; font-size: 12px; font-weight: bold;">HYPE PRODUCTIONS - ADMINISZTRÁCIÓ</p>
      <p style="margin: 0; color: #888; font-size: 12px;">Hype Productions Kft.</p>
    </td>
    <td style="padding-left: 40px; vertical-align: top; color: #888; font-size: 12px;">
      <p style="margin: 0;">Rahman Martin – cégvezető</p>
      <p style="margin: 0;">
        <a href="mailto:martin.rahman@hypestab.hu" style="color: #888; text-decoration: underline;">martin.rahman@hypestab.hu</a><br>
        +36 30 898 7600
      </p>
      <p style="margin: 0;">Barna Blanka – Back office manager</p>
      <p style="margin: 0;">
        <a href="mailto:blanka.barna@hypestab.hu" style="color: #888; text-decoration: underline;">blanka.barna@hypestab.hu</a><br>
        +36 30 758 8751
      </p>
    </td>
  </tr>
</table>
"""


def _get_project_or_404(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Projekt nem található")
    return project


def tig_kulcsa(cert: PerformanceCertificate) -> str | None:
    """Melyik SZÁMLÁZÓ FÉL nevére szól ez a TIG (lásd services/szamlazo.py)?"""
    if cert.vallalkozas_id is not None:
        return f"v{cert.vallalkozas_id}"
    if cert.employee_id is not None:
        return f"e{cert.employee_id}"
    return None


#: (projekt, ember) -> az őt lefedő TIG, és (projekt, számlázó kulcs) -> a fél
#: TIG-je azon a projekten. Az első azt válaszolja meg, hogy egy stábtag
#: munkájáról van-e már papír, a második azt, hogy melyik piszkozatot kell
#: szerkeszteni.
TigLookup = tuple[dict[tuple[int, int], PerformanceCertificate], dict[tuple[int, str], PerformanceCertificate]]


def _load_tig_lookup(db: Session, project_ids: set[int]) -> TigLookup:
    """A megadott projekteket ÉRINTŐ TIG-ek, a tételeiken keresztül.

    Nem a TIG saját project_id-je számít, hanem a tételei: egy TIG több projekt
    munkáját is igazolhatja (lásd models/performance_certificate.py
    PerformanceCertificateTetel), és attól még ugyanúgy "megvan a papír" az
    összes érintett projekten."""
    if not project_ids:
        return {}, {}
    tetelek = (
        db.query(PerformanceCertificateTetel)
        .options(selectinload(PerformanceCertificateTetel.certificate))
        .filter(PerformanceCertificateTetel.project_id.in_(project_ids))
        .all()
    )
    ember_fedettseg: dict[tuple[int, int], PerformanceCertificate] = {}
    fel_tig: dict[tuple[int, str], PerformanceCertificate] = {}
    for t in tetelek:
        cert = t.certificate
        if cert is None:
            continue
        ember_fedettseg[(t.project_id, t.employee_id)] = cert
        kulcs = tig_kulcsa(cert)
        if kulcs is not None:
            fel_tig[(t.project_id, kulcs)] = cert

    # Tétel nélküli TIG-ek (Notion-import, kézi javítás): a saját projektjükön
    # a saját emberüket fedik - lásd services/papir_fedettseg.py.
    for cert in (
        db.query(PerformanceCertificate)
        .filter(PerformanceCertificate.project_id.in_(project_ids), papir_fedettseg.tetel_nelkuli(PerformanceCertificate))
        .all()
    ):
        if cert.employee_id is not None:
            ember_fedettseg.setdefault((cert.project_id, cert.employee_id), cert)
        kulcs = tig_kulcsa(cert)
        if kulcs is not None:
            fel_tig.setdefault((cert.project_id, kulcs), cert)
    return ember_fedettseg, fel_tig


def _tig_candidates(
    project: Project, felulirasok: dict[tuple[int, int], ProjectSzamlazo] | None = None
) -> list[Employee]:
    """A TIG-et igénylő emberek egy projekten: minden nem belsős stábtag,
    FÜGGETLENÜL attól, hogy van-e keretszerződése (szemben az eseti
    szerződés-populációval, ahol a keretszerződésesek ki vannak zárva).

    Ide tartoznak a project.crew tagjai ÉS az alvállalkozói kiadásként ehhez
    a projekthez kötött emberek is (project.alvallalkozo_stab) - utóbbiak
    kaphatnak TIG-et anélkül, hogy a stábba (és így a diszpóba) bekerülnének
    (lásd models/project.py Project.alvallalkozo_stab).

    Kiesnek azok, akik PROJEKT KIADÁSKÉNT vannak elszámolva: az ő díjuk egy
    másik tételben szerepel, tehát nincs mit igazolni.

    "Belsős" itt A FORGATÁS NAPJÁRA értendő, nem a mai típusra (lásd
    services/belsos_idoszak.belsos_a_napon)."""
    crew_ids = {e.id for e in project.crew}
    alap_lista = list(project.crew) + [
        e for e in project.alvallalkozo_stab if e.id not in crew_ids
    ]
    emberek = [
        e for e in alap_lista if not belsos_idoszak.belsos_a_napon(e, project.forgatas_datuma)
    ]
    if felulirasok is None:
        return emberek
    return szamlazo.papirt_igenylo_emberek(project, emberek, felulirasok)


def tig_csoportok(
    project: Project, felulirasok: dict[tuple[int, int], ProjectSzamlazo]
) -> list[SzamlazoCsoport]:
    """A TIG-et igénylő stábtagok SZÁMLÁZÓ FELENKÉNT összefogva - egy fél
    munkájáról egy TIG szól, akkor is, ha több ember munkáját fedi."""
    return szamlazo.csoportok(project, _tig_candidates(project, felulirasok), felulirasok)


def tig_keszitheto_csoportok(
    project: Project,
    felulirasok: dict[tuple[int, int], ProjectSzamlazo],
    keretszerzodesek: dict[str, list[Contract]],
    project_contracts: dict[tuple[int, str], Contract],
) -> list[SzamlazoCsoport]:
    """Azok a számlázó felek, akikről MÁR most készíthető TIG ezen a projekten.

    A feltétel FELENKÉNT áll: akinek megvan az eseti szerződése (kiküldve vagy
    kihagyva), vagy akit keretszerződés mentesít, arról azonnal mehet a TIG.
    Korábban a teljes projekt szerződés-fázisának le kellett zárulnia ahhoz,
    hogy bárkiről készülhessen TIG - egyetlen késlekedő stábtag így az egész
    projekt papírozását megállította."""
    return [
        cs
        for cs in tig_csoportok(project, felulirasok)
        if csoport_szerzodes_kesz(project, cs, keretszerzodesek, project_contracts)
    ]


def _tig_keszitheto(db: Session, project: Project, csoport: SzamlazoCsoport) -> bool:
    """Egyetlen félre nézve: készíthető-e róla TIG ezen a projekten."""
    keretszerzodesek, project_contracts, _ = load_szerzodes_kornyezet(db, [project])
    return csoport_szerzodes_kesz(project, csoport, keretszerzodesek, project_contracts)


def _csoport_fedve(project: Project, csoport: SzamlazoCsoport, lookup: TigLookup) -> bool:
    """Le van-e zárva a TIG ennél a félnél ezen a projekten?

    EGY FÉLRE EGY PROJEKTEN EGY TIG JÁR. Ezért ha a félnek már van
    véglegesített (kiküldött vagy kihagyott) TIG-je erre a projektre, a fél
    kész - akkor is, ha közben újabb ember került alá.

    Ez a gyakorlatból jött: ha valaki egyben számlázott egy másik stábtaggal,
    de a "ki számláz kiért" beállítás csak KÉSŐBB, a TIG kiküldése után
    került rögzítésre, a rendszer korábban újra kérte a papírt - pedig a munka
    egyetlen, már kiküldött igazoláson szerepelt. A tétel-szintű ellenőrzés
    csak azoknál marad, akiknek még egyáltalán nincs TIG-jük.

    Az ára tudatos: ha az utólag alákerült ember munkája ÖSSZEGSZERŰEN nincs
    rajta a már kiküldött TIG-en, azt kézzel kell rendezni (a TIG állapotát
    vissza kell venni "Készítés alatt"-ra, és a tételt hozzáadni). A rendszer
    nem gyárt helyette egy második papírt ugyanarra a félre, mert abból a
    megbízott két igazolást kapna ugyanarról a projektről."""
    _, fel_tig = lookup
    fel_cert = fel_tig.get((project.id, csoport.kulcs))
    if fel_cert is not None and fel_cert.allapot in TERMINAL_STATUSES:
        return True

    ember_fedettseg, _ = lookup
    for tag in csoport.tagok:
        cert = ember_fedettseg.get((project.id, tag.id))
        if cert is None or cert.allapot not in TERMINAL_STATUSES:
            return False
    return True


def _tig_pending_csoportok(
    project: Project, csoportok: list[SzamlazoCsoport], lookup: TigLookup
) -> list[tuple[SzamlazoCsoport, PerformanceCertificate | None]]:
    _, fel_tig = lookup
    result: list[tuple[SzamlazoCsoport, PerformanceCertificate | None]] = []
    for csoport in csoportok:
        if _csoport_fedve(project, csoport, lookup):
            continue
        result.append((csoport, fel_tig.get((project.id, csoport.kulcs))))
    return result


class PendingProjectSummary(BaseModel):
    project_id: int
    project_nev: str | None
    forgatas_datuma: date | None
    pending_count: int


@router.get("", response_model=list[PendingProjectSummary])
def list_tig_ready_projects(db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
    # Lásd subcontractor_contracts.list_pending_projects: alvállalkozói
    # kiadásnál a diszpó állapotától függetlenül bekerül a projekt, mert maga
    # a kiadás a commitment, nem a stáb-behívás.
    projects = papirozas_hatokor.papirozando_projektek(
        db.query(Project)
        .filter(or_(papirozas_hatokor.diszpozott_projekt_feltetel(), Project.alvallalkozo_kiadasok.any()))
        .options(selectinload(Project.crew), selectinload(Project.project_code))
        .all()
    )
    keretszerzodesek, project_contracts, felulirasok = load_szerzodes_kornyezet(db, projects)
    # Projektenként AZOK a felek, akikről már mehet a TIG - nem az egész projekt
    # szerződés-fázisának lezárultát várjuk meg.
    keszitheto = {
        p.id: tig_keszitheto_csoportok(p, felulirasok, keretszerzodesek, project_contracts) for p in projects
    }
    eligible = [p for p in projects if keszitheto[p.id]]
    tig_lookup = _load_tig_lookup(db, {p.id for p in eligible})

    result: list[PendingProjectSummary] = []
    for p in eligible:
        pending = _tig_pending_csoportok(p, keszitheto[p.id], tig_lookup)
        if pending:
            result.append(
                PendingProjectSummary(
                    project_id=p.id, project_nev=p.nev, forgatas_datuma=p.forgatas_datuma, pending_count=len(pending)
                )
            )
    return result


class TetelInfo(BaseModel):
    """Egy TIG-tétel: kinek a munkája, melyik projekten."""

    project_id: int
    project_nev: str | None = None
    projektkod: str | None = None
    forgatas_datuma: date | None = None
    employee_id: int
    employee_nev: str | None = None
    netto_osszeg: float | None = None
    megnevezes: str | None = None


class DraftInfo(BaseModel):
    allapot: str | None
    ceg_neve: str | None
    szekhely: str | None
    adoszam: str | None
    megbizas_targya: str | None
    netto_osszeg: float | None
    teljesites_szoveg: str | None
    teljesites_kezdete: date | None
    teljesites_vege: date | None
    keltezes: date | None
    plusz_afa: bool | None
    #: Miért hagytuk ki - a kihagyásnál kötelező.
    kihagyas_oka: str | None = None
    tetelek: list[TetelInfo] = []


class SzerzodesElotoltes(BaseModel):
    """Amit a fél ESETI SZERZŐDÉSÉBŐL átveszünk a TIG-hez.

    Ugyanarról a munkáról szól a két papír, tehát a megbízás tárgya, az összeg
    és a teljesítés ideje ugyanaz - amit egyszer beírtak a szerződésbe, azt ne
    kelljen a TIG-nél még egyszer begépelni. ELŐTÖLTÉS, nem kényszer: az
    űrlapon minden mező marad szerkeszthető, és a mentés a TIG saját adatait
    írja, nem a szerződését."""

    allapot: str | None = None
    ceg_neve: str | None = None
    szekhely: str | None = None
    adoszam: str | None = None
    megbizas_targya: str | None = None
    netto_osszeg: float | None = None
    teljesites_szoveg: str | None = None
    plusz_afa: bool | None = None
    #: A szerződés tételeinek összegei - a TIG tételeire ugyanígy előtöltjük.
    tetelek: list[TetelInfo] = []


def _szerzodes_elotoltes(c: Contract | None) -> SzerzodesElotoltes | None:
    if c is None:
        return None
    return SzerzodesElotoltes(
        allapot=c.szerzodes_allapota,
        ceg_neve=c.ceg_neve,
        szekhely=c.szekhely,
        adoszam=c.adoszam,
        megbizas_targya=c.megbizas_targya,
        netto_osszeg=float(c.netto_osszeg) if c.netto_osszeg is not None else None,
        teljesites_szoveg=c.teljesites_szoveg,
        plusz_afa=c.plusz_afa,
        tetelek=[
            TetelInfo(
                project_id=t.project_id,
                project_nev=t.project.nev if t.project else None,
                projektkod=t.project.projektkod_szoveg if t.project else None,
                forgatas_datuma=t.project.forgatas_datuma if t.project else None,
                employee_id=t.employee_id,
                employee_nev=t.employee.full_name if t.employee else None,
                netto_osszeg=float(t.netto_osszeg) if t.netto_osszeg is not None else None,
                megnevezes=t.megnevezes,
            )
            for t in c.tetelek
        ],
    )


class PendingEmployeeInfo(BaseModel):
    """Egy SZÁMLÁZÓ FÉL, akitől még hátra van a TIG ezen a projekten.

    Az `id` a régi felület kedvéért az ember azonosítója (cégnél 0) - az új
    hívások a `szamlazo` kulccsal címeznek (lásd services/szamlazo.py)."""

    id: int
    szamlazo: str
    full_name: str
    cimke: str
    lefedettek: list[TetelInfo] = []
    vallalkozas_id: int | None = None
    email: str | None
    ceg_neve: str | None
    szekhely: str | None
    adoszam: str | None
    megbizas_targya: str | None
    plusz_afa: bool | None
    draft: DraftInfo | None
    #: A fél eseti szerződése ezen a projekten - ebből tölti elő az űrlap azt,
    #: amit ott már megadtak (lásd SzerzodesElotoltes).
    szerzodes: SzerzodesElotoltes | None = None


class PendingProjectDetail(BaseModel):
    project_id: int
    project_nev: str | None
    projektkod: str | None
    forgatas_datuma: date | None
    forgatas_datuma_vege: date | None
    # A teljesítés idejének alapértelmezett SZÖVEGE (a forgatás dátumából) -
    # az űrlap ezzel indul, amíg nincs mentett bejegyzés, amiből előtöltene.
    teljesites_szoveg_alap: str
    pending: list[PendingEmployeeInfo]
    tig_ready: bool
    #: Akikről még NEM készíthető TIG, mert nincs meg az eseti szerződésük -
    #: de KIHAGYNI már most is lehet őket (lásd skip_tig). Külön listában, hogy
    #: a teendő-számokat ne mozdítsa el: ők a szerződés-lépésnél várnak.
    szerzodesre_varo: list[PendingEmployeeInfo] = []


def _tetel_info(t: PerformanceCertificateTetel) -> TetelInfo:
    projekt = t.project
    return TetelInfo(
        project_id=t.project_id,
        project_nev=projekt.nev if projekt else None,
        projektkod=projekt.projektkod_szoveg if projekt else None,
        forgatas_datuma=projekt.forgatas_datuma if projekt else None,
        employee_id=t.employee_id,
        employee_nev=t.employee.full_name if t.employee else None,
        netto_osszeg=float(t.netto_osszeg) if t.netto_osszeg is not None else None,
        megnevezes=t.megnevezes,
    )


def _draft_info(c: PerformanceCertificate | None) -> DraftInfo | None:
    if c is None:
        return None
    return DraftInfo(
        allapot=c.allapot,
        ceg_neve=c.ceg_neve,
        szekhely=c.szekhely,
        adoszam=c.adoszam,
        megbizas_targya=c.megbizas_targya,
        netto_osszeg=c.netto_osszeg,
        teljesites_szoveg=c.teljesites_szoveg,
        teljesites_kezdete=c.teljesites_kezdete,
        teljesites_vege=c.teljesites_vege,
        keltezes=c.keltezes,
        plusz_afa=c.plusz_afa,
        kihagyas_oka=c.kihagyas_oka,
        tetelek=[_tetel_info(t) for t in c.tetelek],
    )


def _lefedettek_info(
    db: Session, project: Project, csoport: SzamlazoCsoport, szerzodes: Contract | None = None
) -> list[TetelInfo]:
    """A piszkozat alapértelmezett tétellistája: a fél által lefedett stábtagok
    ezen a projekten - és ha az eseti szerződése több forgatásra szól, azok is
    (lásd _szerzodes_szerinti_parok).

    A felület EBBŐL indul: ami itt benne van, az alapból ki van pipálva. Ezért
    kell ugyanannak lennie, mint amit a szerver a piszkozatra tesz - különben
    az első mentés levenné a többi napot a papírról."""
    return [_tetel_info_parbol(p, tag) for p, tag in _szerzodes_szerinti_parok(db, project, csoport, szerzodes)]


def _pending_info(
    db: Session,
    project: Project,
    csoport: SzamlazoCsoport,
    existing: PerformanceCertificate | None,
    szerzodes: Contract | None = None,
) -> PendingEmployeeInfo:
    fel = csoport.fel
    return PendingEmployeeInfo(
        id=fel.employee.id if fel.employee else 0,
        szamlazo=fel.kulcs,
        full_name=fel.nev,
        cimke=csoport.cimke(),
        lefedettek=_lefedettek_info(db, project, csoport, szerzodes),
        vallalkozas_id=fel.vallalkozas.id if fel.vallalkozas else None,
        email=fel.email,
        ceg_neve=fel.ceg_neve,
        szekhely=fel.szekhely,
        adoszam=fel.adoszam,
        megbizas_targya=fel.megbizas_targya,
        plusz_afa=fel.plusz_afa,
        draft=_draft_info(existing),
        szerzodes=_szerzodes_elotoltes(szerzodes),
    )


class PendingProjectCodeSummary(BaseModel):
    project_code_id: int
    projektkod: str
    project_nev: str | None
    pending_count: int


@router.get("/projektkodok", response_model=list[PendingProjectCodeSummary])
def list_tig_ready_project_codes(db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
    """Lásd list_tig_ready_projects (forgatás-alapú megfelelője) - a
    projektkód-szintű (forgatás nélküli) alvállalkozói kiadásokra."""
    project_codes = [pk for pk in projektkodok_alvallalkozoi_kiadassal(db) if szerzodest_igenylo_emberek_projektkodon(pk)]
    if not project_codes:
        return []

    result: list[PendingProjectCodeSummary] = []
    for pk in project_codes:
        keretszerzodesek, project_code_contracts = load_szerzodes_kornyezet_projektkodon(db, [pk])
        keszitheto = tig_keszitheto_csoportok_projektkodon(pk, keretszerzodesek, project_code_contracts)
        if not keszitheto:
            continue
        tig_lookup = _load_tig_lookup_projektkodon(db, {pk.id})
        pending = _tig_pending_csoportok_projektkodon(pk, keszitheto, tig_lookup)
        if pending:
            result.append(
                PendingProjectCodeSummary(
                    project_code_id=pk.id, projektkod=pk.projektkod, project_nev=pk.project_nev, pending_count=len(pending)
                )
            )
    return result


@router.get("/{project_id}", response_model=PendingProjectDetail)
def get_pending_for_project(project_id: int, db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
    project = _get_project_or_404(db, project_id)
    keretszerzodesek, project_contracts, felulirasok = load_szerzodes_kornyezet(db, [project])
    # Csak azok a felek jelennek meg, akikről MÁR készíthető TIG - a többi
    # addig a szerződés-fázisban vár (lásd tig_keszitheto_csoportok).
    keszitheto = tig_keszitheto_csoportok(project, felulirasok, keretszerzodesek, project_contracts)
    tig_ready = bool(keszitheto)
    lookup = _load_tig_lookup(db, {project.id})
    pending: list[tuple[SzamlazoCsoport, PerformanceCertificate | None]] = []
    if tig_ready:
        pending = _tig_pending_csoportok(project, keszitheto, lookup)
    # Akiknek a szerződése még hiányzik: TIG-et készíteni róluk nem lehet, de
    # KIHAGYNI igen - a három lépés kihagyása független egymástól.
    keszitheto_kulcsok = {cs.kulcs for cs in keszitheto}
    varakozok = _tig_pending_csoportok(
        project, [cs for cs in tig_csoportok(project, felulirasok) if cs.kulcs not in keszitheto_kulcsok], lookup
    )
    # A felek eseti szerződései EGY lekérdezésből - ebből tölt elő az űrlap.
    szerzodesek = eseti_szerzodesek_a_projekten(db, project.id) if pending else {}
    return PendingProjectDetail(
        project_id=project.id,
        project_nev=project.nev,
        projektkod=project.projektkod_szoveg,
        forgatas_datuma=project.forgatas_datuma,
        forgatas_datuma_vege=project.forgatas_datuma_vege,
        teljesites_szoveg_alap=_projekt_teljesites_szoveg(project),
        tig_ready=tig_ready,
        pending=[
            _pending_info(db, project, csoport, existing, szerzodesek.get(csoport.kulcs))
            for csoport, existing in pending
        ],
        szerzodesre_varo=[_pending_info(db, project, csoport, existing) for csoport, existing in varakozok],
    )


@router.get("/{project_id}/all", response_model=list[PerformanceCertificateRead])
def list_all_for_project(project_id: int, db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
    """Az adott projekt ÖSSZES TIG-bejegyzése (bármilyen állapotban) - a
    kiküldött (Kiküldve) tételekhez itt jelenik meg a számla-feltöltés és
    kifizetettként jelölés vezérlő a frontenden (lásd
    PerformanceCertificateManager), a still-pending (Készítés alatt) tételek
    a get_pending_for_project végpontból jönnek.

    A szűrés LEFEDETTSÉG szerint megy, nem a TIG saját `project_id`-ja szerint:
    egy TIG több projekt munkáját is igazolhatja, és ilyenkor a project_id csak
    azt mondja meg, melyik projektről indítva készült. A többi projekten a
    kiküldött TIG korábban egyáltalán nem látszott (lásd
    services/papir_fedettseg.py)."""
    rows = (
        db.query(PerformanceCertificate)
        .options(
            selectinload(PerformanceCertificate.invoices),
            # A tételek PROJEKTJE is kell: a felület ebből írja ki, hogy egy
            # összevont papír melyik forgatásokat fedi. Eager load nélkül ez
            # tételenként külön lekérdezés lenne.
            selectinload(PerformanceCertificate.tetelek)
            .selectinload(PerformanceCertificateTetel.project)
            .selectinload(Project.project_code),
        )
        .filter(
            papir_fedettseg.fedi_a_projektet(
                PerformanceCertificate, PerformanceCertificateTetel, project_id
            )
        )
        .all()
    )
    return [PerformanceCertificateRead.model_validate(r) for r in rows]


def _validate_szamlazo(
    db: Session, project: Project, szamlazo_kulcs: str, *, szerzodes_kell: bool = True
) -> SzamlazoCsoport:
    """A fél TIG-csoportja ezen a projekten.

    A `szerzodes_kell=False` a KIHAGYÁSHOZ való. TIG-et KÉSZÍTENI csak úgy van
    értelme, ha van mögötte szerződés - a papír éppen egy szerződés teljesítését
    igazolja. Azt viszont KIMONDANI, hogy innen nem lesz TIG, a szerződéstől
    függetlenül lehet: az a lépés nem a papírról szól, hanem arról, hogy nem
    lesz papír. Enélkül egy sosem elkészült szerződés örökre nyitva tartotta a
    TIG-lépést is - pedig épp azt akartuk lezárni."""
    fel = szamlazo.feloldas(db, szamlazo_kulcs)
    if fel is None:
        raise HTTPException(status_code=404, detail="A számlázó fél nem található")
    felulirasok = szamlazo.load_felulirasok(db, {project.id})
    csoport = next((cs for cs in tig_csoportok(project, felulirasok) if cs.kulcs == fel.kulcs), None)
    if csoport is None:
        if fel.employee is not None and fel.employee.tipus == EmployeeType.BELSOS:
            raise HTTPException(status_code=400, detail="Belsős munkatársnak nem kell teljesítési igazolás.")
        raise HTTPException(status_code=400, detail="Ezen a projekten senkinek a munkáját nem ez a fél számlázza.")
    # A feltétel csak ERRE a félre vonatkozik: a projekt többi szereplőjének
    # hiányzó szerződése nem akadálya annak, hogy erről a félről TIG készüljön.
    if szerzodes_kell and not _tig_keszitheto(db, project, csoport):
        raise HTTPException(
            status_code=400,
            detail=f"{csoport.cimke()} szerződése még nincs meg ezen a projekten - TIG csak azután készíthető róla.",
        )
    return csoport


def _szamlazo_szuro(fel: SzamlazoFel):
    if fel.vallalkozas is not None:
        return PerformanceCertificate.vallalkozas_id == fel.vallalkozas.id
    return (PerformanceCertificate.employee_id == fel.employee.id) & PerformanceCertificate.vallalkozas_id.is_(None)


def nyitott_munkak(db: Session, fel: SzamlazoFel, project_ids: set[int] | None = None) -> list[tuple[Project, Employee]]:
    """(projekt, ember) munkák, amiket EZ a fél számláz, és amikről még nincs
    TIG - vagyis amik ráTEHETŐK egy papírra.

    Három szűrő van rajta, és mindhárom kell:

    - csak DISZPÓZOTT projekt (a papírozás onnantól van napirenden);
    - a félnek a projekten már megvan a szerződéses háttere - és csak az ÖVÉ
      számít: a többi stábtag hiányzó szerződése nem tartja vissza az ő
      tételeit;
    - amiről már szól egy TIG, az kimarad: egy munkát csak egy papír igazolhat.

    A `project_ids` szűkítéssel ugyanez kérdezhető egy adott projekthalmazra -
    ezt használja a szerződés szerinti előtöltés (lásd
    _szerzodes_szerinti_parok)."""
    q = db.query(Project).filter(papirozas_hatokor.diszpozott_projekt_feltetel())
    if project_ids is not None:
        if not project_ids:
            return []
        q = q.filter(Project.id.in_(project_ids))
    projects = papirozas_hatokor.papirozando_projektek(
        q.options(selectinload(Project.crew), selectinload(Project.project_code)).all()
    )
    if not projects:
        return []
    keretszerzodesek, project_contracts, felulirasok = load_szerzodes_kornyezet(db, projects)
    ember_fedettseg, _ = _load_tig_lookup(db, {p.id for p in projects})

    parok: list[tuple[Project, Employee]] = []
    for p in projects:
        for csoport in tig_keszitheto_csoportok(p, felulirasok, keretszerzodesek, project_contracts):
            if csoport.kulcs != fel.kulcs:
                continue
            for tag in csoport.tagok:
                if (p.id, tag.id) in ember_fedettseg:
                    continue
                parok.append((p, tag))
    return parok


def _tetel_info_parbol(p: Project, tag: Employee) -> TetelInfo:
    return TetelInfo(
        project_id=p.id,
        project_nev=p.nev,
        projektkod=p.projektkod_szoveg,
        forgatas_datuma=p.forgatas_datuma,
        employee_id=tag.id,
        employee_nev=tag.full_name,
    )


@router.get("/{project_id}/{szamlazo_kulcs}/nyitott-tetelek", response_model=list[TetelInfo])
def list_nyitott_tetelek(
    project_id: int,
    szamlazo_kulcs: str,
    db: Session = Depends(get_db),
    _user: Employee = Depends(get_current_user),
):
    """Mi mindent tehetünk MÉG rá erre a TIG-re?

    Az "egy ember egyben küld be több projektet" eset felülete: felsorolja az
    összes olyan (projekt, ember) munkát az ÖSSZES diszpózott projektről, amit
    ez a fél számláz, amiről még nincs TIG, és aminek a projektjén a
    szerződés-fázis már lezárult. A felhasználó ebből pipálja ki, mi kerüljön
    erre az egy számlára.

    A most szerkesztett projekt saját tételei is benne vannak - így a lista
    egyben mutatja, mi az alap és mi a hozzáadható."""
    _get_project_or_404(db, project_id)
    fel = szamlazo.feloldas(db, szamlazo_kulcs)
    if fel is None:
        raise HTTPException(status_code=404, detail="A számlázó fél nem található")
    eredmeny = [_tetel_info_parbol(p, tag) for p, tag in nyitott_munkak(db, fel)]
    eredmeny.sort(key=lambda t: (t.forgatas_datuma or date.min, t.project_id, t.employee_id), reverse=True)
    return eredmeny


def _szerzodes_szerinti_parok(
    db: Session, project: Project, csoport: SzamlazoCsoport, szerzodes: Contract | None
) -> list[tuple[Project, Employee]]:
    """MIT fedjen ALAPBÓL a TIG: a projekt saját stábtagjait - és ha a fél
    ESETI SZERZŐDÉSE több forgatásra szól, akkor azokat is.

    Ha egyszer kimondtuk, hogy ez a néhány forgatás EGY szerződés, akkor a TIG
    is egy, és utána a SZÁMLA is egy: egy feltöltés, egy határidő, egy
    "kifizetve" - mindegyik érintett forgatás oldalán ugyanaz az egy sor (lásd
    services/papir_fedettseg.py). Enélkül a szerződés összevont volt, a TIG
    viszont projektenként külön indult, és a végén annyi számlát kellett
    feltölteni, ahány nap - pedig a megbízott egyet állított ki az egészről.

    Ami a szerződésen rajta van, de közben MÁS papírra került (vagy már nem ez
    a fél számlázza), az kimarad: az előtöltés javaslat, nem felülírás (lásd
    nyitott_munkak). A tételek a felületen ki-be pipálhatók."""
    parok: list[tuple[Project, Employee]] = [(project, tag) for tag in csoport.tagok]
    if szerzodes is None:
        return parok
    mas_projektek = {t.project_id for t in szerzodes.tetelek} - {project.id}
    parok.extend(nyitott_munkak(db, csoport.fel, mas_projektek))
    return parok


def _teljesites_datumokbol(cert: PerformanceCertificate) -> str:
    """A korábbi, tól-ig dátumos megadás szöveggé formázva - csak a régi
    bejegyzésekhez tartalék (lásd teljesites_szoveg)."""
    if cert.teljesites_vege and cert.teljesites_vege != cert.teljesites_kezdete:
        kezdet = cert.teljesites_kezdete.strftime("%Y.%m.%d.") if cert.teljesites_kezdete else ""
        return f"{kezdet} - {cert.teljesites_vege.strftime('%Y.%m.%d.')}"
    if cert.teljesites_kezdete:
        return cert.teljesites_kezdete.strftime("%Y.%m.%d.")
    return ""


def _projekt_teljesites_szoveg(project: Project) -> str:
    """Előtöltés a projekt forgatási dátumából - a teljesítés jellemzően a
    forgatás ideje, de a mező szabad szöveg, tehát bármire átírható."""
    start = project.forgatas_datuma
    if not start:
        return ""
    end = project.forgatas_datuma_vege
    if end and end != start:
        return f"{start.strftime('%Y.%m.%d.')} - {end.strftime('%Y.%m.%d.')}"
    return start.strftime("%Y.%m.%d.")


def _get_or_create_draft(db: Session, project: Project, csoport: SzamlazoCsoport) -> PerformanceCertificate:
    """A fél piszkozata ezen a projekten - vagy a meglévő, vagy egy új, a
    projekten hozzá tartozó stábtagok tételeivel feltöltve.

    A meglévőt a TÉTELEIN keresztül keressük: a fél TIG-je indulhatott egy
    másik projektről is, ha több forgatását egy számlán küldi be."""
    _, fel_tig = _load_tig_lookup(db, {project.id})
    existing = fel_tig.get((project.id, csoport.kulcs))
    if existing is None:
        # Piszkozat, aminek még nincs tétele: ilyenkor a saját projektjén és a
        # saját oldalán keressük.
        existing = (
            db.query(PerformanceCertificate)
            .filter(PerformanceCertificate.project_id == project.id, _szamlazo_szuro(csoport.fel))
            .first()
        )
    if existing is not None:
        if existing.allapot in TERMINAL_STATUSES:
            raise HTTPException(
                status_code=400,
                detail="Ehhez a projekthez és félhez már véglegesített TIG-bejegyzés tartozik (kiküldve vagy kihagyva).",
            )
        return existing
    fel = csoport.fel
    # A fél ESETI SZERZŐDÉSE ugyanerről a munkáról szól, tehát amit oda már
    # beírtak, azt innen vesszük át (lásd SzerzodesElotoltes). Ami a
    # szerződésen üres, arra marad a fél saját adata.
    szerzodes = eseti_szerzodesek_a_projekten(db, project.id).get(csoport.kulcs)

    def _szerzodesbol(mezo: str, tartalek):
        ertek = getattr(szerzodes, mezo, None) if szerzodes is not None else None
        return tartalek if ertek in (None, "") else ertek

    # Ha szerződés nincs (a felet keretszerződés fedi), az összeg a diszpó
    # írásakor LEBESZÉLT díjból jön - különben pont a keretszerződéseseknél
    # maradna üresen a mező, pedig ott is meg volt beszélve, mennyiért vállalja
    # (lásd services/megbeszelt_dij.py).
    dijak_projektenkent: dict[int, dict[int, float]] = {}

    def _dij(project_id: int, employee_id: int):
        if project_id not in dijak_projektenkent:
            dijak_projektenkent[project_id] = megbeszelt_dij.dijak_a_projekten(db, project_id)
        return dijak_projektenkent[project_id].get(employee_id)

    dijak = megbeszelt_dij.dijak_a_projekten(db, project.id)
    dijak_projektenkent[project.id] = dijak
    tag_idk = [t.id for t in csoport.tagok]

    draft = PerformanceCertificate(
        project_id=project.id,
        employee_id=fel.employee.id if fel.employee else None,
        vallalkozas_id=fel.vallalkozas.id if fel.vallalkozas else None,
        allapot="Készítés alatt",
        ceg_neve=_szerzodesbol("ceg_neve", fel.ceg_neve),
        szekhely=_szerzodesbol("szekhely", fel.szekhely),
        adoszam=_szerzodesbol("adoszam", fel.adoszam),
        megbizas_targya=_szerzodesbol("megbizas_targya", fel.megbizas_targya),
        netto_osszeg=_szerzodesbol("netto_osszeg", megbeszelt_dij.csoport_osszege(dijak, tag_idk)),
        plusz_afa=_szerzodesbol("plusz_afa", fel.plusz_afa),
        teljesites_szoveg=_szerzodesbol("teljesites_szoveg", _projekt_teljesites_szoveg(project)),
        email=fel.email,
    )
    db.add(draft)
    db.flush()
    # Alapból azt fedi, amiért ezen a projekten ő számláz - ÉS a szerződése
    # többi forgatását is, ha összevont papírról van szó (lásd
    # _szerzodes_szerinti_parok). A tételösszegek a szerződésről jönnek, ahol
    # ott már megadták őket.
    szerzodes_tetelei = (
        {(t.project_id, t.employee_id): t for t in szerzodes.tetelek} if szerzodes is not None else {}
    )
    for p, tag in _szerzodes_szerinti_parok(db, project, csoport, szerzodes):
        forras = szerzodes_tetelei.get((p.id, tag.id))
        db.add(
            PerformanceCertificateTetel(
                certificate_id=draft.id,
                project_id=p.id,
                employee_id=tag.id,
                netto_osszeg=(forras.netto_osszeg if forras is not None else None) or _dij(p.id, tag.id),
                megnevezes=forras.megnevezes if forras is not None else None,
            )
        )
    db.flush()
    return draft


class TetelIn(BaseModel):
    project_id: int
    employee_id: int
    #: Opcionális: "mikor más számláz vagy 4 projektet egybe számláz, akkor nem
    #: mindig lehet megmondani, hogy mi mennyibe került". A TIG fejösszege az
    #: igazság, ez csak akkor kell, ha a bontás ismert.
    netto_osszeg: float | None = None
    megnevezes: str | None = None


class TigDraftIn(BaseModel):
    ceg_neve: str | None = None
    szekhely: str | None = None
    adoszam: str | None = None
    megbizas_targya: str | None = None
    netto_osszeg: float | None = None
    teljesites_szoveg: str | None = None
    teljesites_kezdete: date | None = None
    teljesites_vege: date | None = None
    keltezes: date | None = None
    plusz_afa: bool | None = None
    #: Mit igazol ez a TIG. None = maradjon, ami van (a piszkozat létrehozásakor
    #: az adott projekten a félhez tartozó stábtagok).
    tetelek: list[TetelIn] | None = None


def _apply_tetelek(db: Session, draft: PerformanceCertificate, fel: SzamlazoFel, tetelek: list[TetelIn] | None) -> None:
    """A TIG tételeinek cseréje - ellenőrzésekkel.

    Két dolgot kell megvédeni:
    1. Egy (projekt, ember) munkájáról csak EGY TIG szólhat, különben kétszer
       igazolnánk (és kétszer fizetnénk) ugyanazt.
    2. Csak olyan tétel kerülhet rá, aminél tényleg ez a fél a számlázó azon a
       projekten - különben egy TIG-gel bárki munkáját le lehetne írni."""
    if tetelek is None:
        return
    if not tetelek:
        raise HTTPException(status_code=400, detail="A TIG-nek legalább egy tételt tartalmaznia kell.")

    parok = {(t.project_id, t.employee_id) for t in tetelek}
    if len(parok) != len(tetelek):
        raise HTTPException(status_code=400, detail="Ugyanaz az ember ugyanazon a projekten kétszer szerepel.")

    projektek = {p.id: p for p in db.query(Project).filter(Project.id.in_({t.project_id for t in tetelek})).all()}
    keretszerzodesek, project_contracts, felulirasok = load_szerzodes_kornyezet(db, list(projektek.values()))
    # Projektenként azok a felek, akikről már mehet a TIG - felenként dől el,
    # tehát a projekt többi szereplőjének hiányzó szerződése nem akadály.
    keszitheto_kulcsok = {
        pid: {cs.kulcs for cs in tig_keszitheto_csoportok(p, felulirasok, keretszerzodesek, project_contracts)}
        for pid, p in projektek.items()
    }
    for t in tetelek:
        projekt = projektek.get(t.project_id)
        if projekt is None:
            raise HTTPException(status_code=404, detail=f"A(z) #{t.project_id} projekt nem található.")
        ember = next((e for e in _tig_candidates(projekt, felulirasok) if e.id == t.employee_id), None)
        if ember is None:
            raise HTTPException(
                status_code=400,
                detail=f"A(z) #{t.employee_id} munkatárs nincs a(z) „{projekt.nev}” projekt (nem belsős) stábjában.",
            )
        if fel.kulcs not in keszitheto_kulcsok.get(projekt.id, set()):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"„{projekt.nev}” projekten ennek a félnek még nincs meg a szerződése - "
                    "TIG csak azután készíthető róla."
                ),
            )
        if szamlazo.szamlazo_fele(projekt, ember, felulirasok).kulcs != fel.kulcs:
            raise HTTPException(
                status_code=400,
                detail=f"„{projekt.nev}” projekten {ember.full_name} munkáját nem ez a fél számlázza.",
            )

    utkozes = (
        db.query(PerformanceCertificateTetel)
        .options(selectinload(PerformanceCertificateTetel.employee))
        .filter(
            PerformanceCertificateTetel.certificate_id != draft.id,
            tuple_(PerformanceCertificateTetel.project_id, PerformanceCertificateTetel.employee_id).in_(parok),
        )
        .first()
    )
    if utkozes is not None:
        nev = utkozes.employee.full_name if utkozes.employee else f"#{utkozes.employee_id}"
        raise HTTPException(
            status_code=400,
            detail=f"{nev} munkájáról ezen a projekten már szól egy másik TIG - egy munkát csak egy TIG igazolhat.",
        )
    # A tétel nélküli (import/kézi) TIG-eket a saját mezőik alapján nézzük -
    # lásd services/papir_fedettseg.py.
    regi = (
        db.query(PerformanceCertificate)
        .options(selectinload(PerformanceCertificate.employee))
        .filter(
            PerformanceCertificate.id != draft.id,
            papir_fedettseg.tetel_nelkuli(PerformanceCertificate),
            tuple_(PerformanceCertificate.project_id, PerformanceCertificate.employee_id).in_(parok),
        )
        .first()
    )
    if regi is not None:
        nev = regi.employee.full_name if regi.employee else f"#{regi.employee_id}"
        raise HTTPException(
            status_code=400,
            detail=f"{nev} munkájáról ezen a projekten már szól egy másik TIG - egy munkát csak egy TIG igazolhat.",
        )

    draft.tetelek.clear()
    db.flush()
    for t in tetelek:
        draft.tetelek.append(
            PerformanceCertificateTetel(
                project_id=t.project_id,
                employee_id=t.employee_id,
                netto_osszeg=t.netto_osszeg,
                megnevezes=t.megnevezes,
            )
        )
    db.flush()


_DRAFT_FIELDS = (
    "ceg_neve",
    "szekhely",
    "adoszam",
    "megbizas_targya",
    "netto_osszeg",
    "teljesites_szoveg",
    "teljesites_kezdete",
    "teljesites_vege",
    "keltezes",
    "plusz_afa",
)


def _apply_draft_fields(draft: PerformanceCertificate, payload: TigDraftIn) -> None:
    for field in _DRAFT_FIELDS:
        value = getattr(payload, field)
        if value is not None:
            setattr(draft, field, value)


@router.post("/{project_id}/{szamlazo_kulcs}/save", response_model=PerformanceCertificateRead)
def save_draft(
    project_id: int,
    szamlazo_kulcs: str,
    payload: TigDraftIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "create")),
):
    """A `szamlazo_kulcs` ember ("e12", vagy csak "12") vagy cég ("v3") is
    lehet - lásd services/szamlazo.py."""
    project = _get_project_or_404(db, project_id)
    csoport = _validate_szamlazo(db, project, szamlazo_kulcs)
    draft = _get_or_create_draft(db, project, csoport)
    _apply_draft_fields(draft, payload)
    _apply_tetelek(db, draft, csoport.fel, payload.tetelek)
    db.commit()
    db.refresh(draft)
    return PerformanceCertificateRead.model_validate(draft)


@router.post("/{project_id}/{szamlazo_kulcs}/generate-and-send", response_model=PerformanceCertificateRead)
def generate_and_send(
    project_id: int,
    szamlazo_kulcs: str,
    payload: TigDraftIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "create")),
):
    project = _get_project_or_404(db, project_id)
    csoport = _validate_szamlazo(db, project, szamlazo_kulcs)
    fel = csoport.fel
    draft = _get_or_create_draft(db, project, csoport)
    _apply_draft_fields(draft, payload)
    _apply_tetelek(db, draft, fel, payload.tetelek)

    if not draft.netto_osszeg or draft.netto_osszeg <= 0:
        raise HTTPException(status_code=400, detail="Add meg a nettó összeget.")
    cimzett = (draft.email or fel.email or "").strip()
    if not cimzett:
        raise HTTPException(status_code=400, detail="A számlázó félnek nincs email címe.")

    keltezes = draft.keltezes or date.today()
    draft.keltezes = keltezes

    # A teljesítés ideje szabad szöveg - a régi, dátum-alapú bejegyzésekhez
    # (amiknél ez még üres) a korábbi formázás a tartalék.
    # A papírra a TÉTELEK kerülnek: ha a TIG több munkát igazol (három forgatás
    # egy számlán, vagy két ember munkája egy fél nevében), a dokumentumból is
    # ki kell derülnie, mit fed - lásd services/papir_tetelek.py. Egytételes
    # TIG-nél minden pontosan úgy néz ki, mint eddig.
    tetelek = list(draft.tetelek)
    teljesites_str = papir_tetelek.teljesites_szovege(
        draft.teljesites_szoveg, tetelek, _teljesites_datumokbol(draft)
    )

    projektdatum = project.forgatas_datuma.strftime("%Y.%m.%d.") if project.forgatas_datuma else ""

    doc_link = None
    pdf_bytes = None
    base_name = f"{projektdatum}_{draft.ceg_neve or fel.nev}_{project.projektkod_szoveg or ''}_TIG"
    try:
        if settings.gdoc_kulsos_tig_template_id:
            fields = {
                "nev": draft.ceg_neve or fel.nev,
                "hely": draft.szekhely or "",
                "adoszam": draft.adoszam or "",
                "targy": papir_tetelek.targy_szovege(draft.megbizas_targya, tetelek),
                "tido": teljesites_str,
                "projkod": papir_tetelek.projektkodok_szovege(tetelek, project.projektkod_szoveg or ""),
                "netto": f"{draft.netto_osszeg:,.0f}".replace(",", " "),
                "kelt": keltezes.strftime("%Y.%m.%d."),
                "afa": "+ ÁFA" if draft.plusz_afa else "",
                "nettoki": szam_betukkel(draft.netto_osszeg),
            }
            pdf_bytes, new_doc_id = gdoc_fill_and_export_pdf(
                template_file_id=settings.gdoc_kulsos_tig_template_id,
                base_name=base_name,
                fields=fields,
                output_folder_id=settings.drive_kulsos_tig or settings.gdoc_output_folder_id or settings.drive_folder_id or None,
            )
            doc_link = f"https://docs.google.com/document/d/{new_doc_id}/edit"

        subject = f"{draft.ceg_neve or fel.nev}_{project.projektkod_szoveg or ''} - Projekt_TIG"
        # A levélben a teljesítés ideje: ha SZÖVEGGEL adták meg (pl. "2026
        # július"), az az igazság - az kerül ide is, ne egy "–" (a felhasználó
        # kérése). Szöveg híján a forgatás dátuma, végső tartalékként a
        # tételekből számolt teljesítés-szöveg.
        email_datum = (draft.teljesites_szoveg or "").strip() or projektdatum or teljesites_str
        html = _TIG_EMAIL_HTML.format(projektdatum=email_datum or "–")
        send_message([cimzett], subject, html, pdf_bytes=pdf_bytes, pdf_filename="teljesitesi_igazolas.pdf")
    except RuntimeError as exc:
        # A kitöltött adatokat akkor is mentsük el, ha a küldés elhasal (pl.
        # hiányzó Google hitelesítő adat) - ne vesszen el az eddigi munka.
        db.commit()
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    draft.allapot = "Kiküldve"
    draft.file_url = doc_link
    db.commit()
    db.refresh(draft)
    return PerformanceCertificateRead.model_validate(draft)


class TigKihagyasIn(BaseModel):
    kihagyas_oka: str | None = None
    #: Mire szóljon a kihagyás. Ugyanaz a lista, mint a mentésnél: egy TIG
    #: több projekt munkájáról is szólhat, tehát a kihagyása is - különben a
    #: többi projekten a fél újra TIG-re várna, pedig épp azt mondtuk ki, hogy
    #: tőle nem lesz papír. None = maradjon, ami a bejegyzésen van.
    tetelek: list[TetelIn] | None = None


@router.post("/{project_id}/{szamlazo_kulcs}/skip", response_model=PerformanceCertificateRead)
def skip_tig(
    project_id: int,
    szamlazo_kulcs: str,
    payload: TigKihagyasIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """A fél kihagyása a TIG-ből, KÖTELEZŐ indoklással.

    Egy hiányzó teljesítési igazolás önmagában gyanús: a puszta "Kihagyva"
    jelölésről fél év múlva senki nem tudja megmondani, hogy szándékos volt-e,
    vagy elfelejtődött. Az indok a bejegyzésen marad, és a listán is látszik.

    A SZERZŐDÉSTŐL FÜGGETLEN: kihagyni akkor is lehet, ha a fél eseti
    szerződése soha nem készült el (lásd _validate_szamlazo). A három lépés
    kihagyása egymástól független - egy elmaradt szerződés nem tarthatja nyitva
    a TIG-et is."""
    indok = (payload.kihagyas_oka or "").strip()
    if not indok:
        raise HTTPException(status_code=400, detail="A kihagyás okát meg kell adni.")
    project = _get_project_or_404(db, project_id)
    csoport = _validate_szamlazo(db, project, szamlazo_kulcs, szerzodes_kell=False)
    draft = _get_or_create_draft(db, project, csoport)
    _apply_tetelek(db, draft, csoport.fel, payload.tetelek)
    draft.allapot = "Kihagyva"
    draft.kihagyas_oka = indok
    db.commit()
    db.refresh(draft)
    return PerformanceCertificateRead.model_validate(draft)


class AllapotIn(BaseModel):
    allapot: str


ALLOWED_STATUSES = ["Készítés alatt", "Kiküldve", "Kihagyva"]


def _certificate_or_none(db: Session, project_id: int, szamlazo_kulcs: str) -> PerformanceCertificate | None:
    """A fél TIG-je ezen a projekten - akkor is, ha egy MÁSIK projektről indult,
    de van ezt a projektet érintő tétele."""
    fel = szamlazo.feloldas(db, szamlazo_kulcs)
    if fel is None:
        return None
    _, fel_tig = _load_tig_lookup(db, {project_id})
    cert = fel_tig.get((project_id, fel.kulcs))
    if cert is not None:
        return cert
    return (
        db.query(PerformanceCertificate)
        .filter(PerformanceCertificate.project_id == project_id, _szamlazo_szuro(fel))
        .first()
    )


@router.post("/{project_id}/{szamlazo_kulcs}/allapot", response_model=PerformanceCertificateRead)
def set_allapot(
    project_id: int,
    szamlazo_kulcs: str,
    payload: AllapotIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """A TIG állapotának KÉZI átállítása. Aki az oldalon szerkeszthet, itt is
    javíthat: pl. visszavehet egy tévesen kiküldöttre állított TIG-et, vagy
    kiküldöttnek jelölhet egyet, amit a rendszeren kívül küldtek el. A
    generálás/küldés folyamat változatlan - ez csak az állapot javítása."""
    if payload.allapot not in ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail=f"Ismeretlen állapot. Választható: {', '.join(ALLOWED_STATUSES)}")
    cert = _certificate_or_none(db, project_id, szamlazo_kulcs)
    if cert is None:
        raise HTTPException(status_code=404, detail="Ehhez a projekthez és félhez nincs TIG bejegyzés.")
    cert.allapot = payload.allapot
    db.commit()
    db.refresh(cert)
    return PerformanceCertificateRead.model_validate(cert)


@router.post("/{project_id}/{szamlazo_kulcs}/sajat-fajl", response_model=PerformanceCertificateRead)
async def upload_sajat_tig(
    project_id: int,
    szamlazo_kulcs: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "create")),
):
    """A KIKÜLDÉS KIHAGYÁSA: egy már meglévő TIG dokumentum feltöltése.

    Van, amikor a papír nem itt készül - kézzel írt, máshonnan kapott vagy már
    aláírt igazolás. Ilyenkor nincs mit generálni és nincs kinek kiküldeni,
    csak rögzíteni: a fájl a tárhelyünkre kerül, a bejegyzés `file_url`-je
    erre mutat, az állapot pedig "Kiküldve" lesz - ugyanoda jut a TIG, mint a
    generálás és küldés útján, tehát innentől számla is tölthető hozzá.

    Az összeget előtte menteni kell (POST /save): TIG-et összeg nélkül nem
    tekintünk késznek, ugyanúgy, ahogy a kiküldésnél sem.

    Rossz fájl esetén ugyanaz a javítás, mint tévesen KIKÜLDÖTT TIG-nél: a
    listán vissza kell venni az állapotot "Készítés alatt"-ra (lásd /allapot),
    utána újra feltölthető - a csere a régi objektumot a tárhelyről is
    eldobja. Egy TIG-nek ugyanis EGY dokumentuma van."""
    project = _get_project_or_404(db, project_id)
    csoport = _validate_szamlazo(db, project, szamlazo_kulcs)
    draft = _get_or_create_draft(db, project, csoport)
    if not draft.netto_osszeg or draft.netto_osszeg <= 0:
        raise HTTPException(status_code=400, detail="Add meg a nettó összeget.")

    filename = file.filename or "tig"
    content_type = file.content_type or "application/octet-stream"
    data = await file.read()

    regi_kulcs = draft.file_storage_key
    kulcs = f"tig-dokumentum/{project_id}/{szamlazo_kulcs}-{draft.id}{os.path.splitext(filename)[1]}"
    draft.file_url = document_storage.upload_bytes(data, kulcs, content_type)
    draft.file_storage_key = kulcs
    draft.allapot = "Kiküldve"
    db.commit()
    # A cserélt fájl törlése CSAK a mentés után, és csak ha tényleg másik
    # objektum volt - így egy elhasalt feltöltésnél nem marad se régi, se új.
    if regi_kulcs and regi_kulcs != kulcs:
        document_storage.delete_object(regi_kulcs)
    db.refresh(draft)
    return PerformanceCertificateRead.model_validate(draft)


def _get_sent_certificate_or_404(db: Session, project_id: int, szamlazo_kulcs: str) -> PerformanceCertificate:
    """A TIG-hez tartozó számla feltöltése/kifizetése csak azután lehetséges,
    hogy magát a TIG-et már kiküldtük (lásd generate_and_send) - eddig a
    pontig nincs mihez számlát kötni."""
    cert = _certificate_or_none(db, project_id, szamlazo_kulcs)
    if cert is None:
        raise HTTPException(status_code=404, detail="Ehhez a projekthez és félhez nem tartozik TIG-bejegyzés.")
    if cert.allapot != "Kiküldve":
        raise HTTPException(status_code=400, detail="Számla csak kiküldött TIG-hez tölthető fel.")
    return cert


@router.post("/{project_id}/{szamlazo_kulcs}/szamla", response_model=PerformanceCertificateRead)
async def upload_szamla(
    project_id: int,
    szamlazo_kulcs: str,
    file: UploadFile = File(...),
    fizetesi_hatarido: date | None = Form(default=None),
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """A kiküldött TIG-hez tartozó (külső számlázási rendszerben kiállított)
    számla feltöltése - ez még nem jelenti a kifizetést, csak a dokumentum
    rögzítését (lásd /szamla-kifizetve a tényleges Pénzügy-be kerüléshez).

    A FIZETÉSI HATÁRIDŐ megadása KÖTELEZŐ: a számlán ott áll, tehát abban a
    pillanatban a kezünkben van, amikor feltöltjük - utólag viszont senki nem
    nyitja ki újra a fájlt, és a tétel határidő nélkül csak "valamikor
    utalandó"-ként lóg a Pénzügyben. Utólag módosítható (lásd /hatarido), és a
    második, harmadik számlánál már nem kell újra megadni: ha a TIG-en már van
    határidő, az érvényes marad.

    Egy TIG-hez tetszőleges számú számla tölthető fel: minden hívás egy ÚJ
    számla-sort hoz létre (nem írja felül az előzőt) - a storage-kulcs ezért
    tartalmazza a számla id-jét is, különben a második feltöltés felülírná az
    első fájlját (lásd PerformanceCertificateInvoice modell-kommentje)."""
    cert = _get_sent_certificate_or_404(db, project_id, szamlazo_kulcs)
    if fizetesi_hatarido is None and cert.fizetesi_hatarido is None:
        raise HTTPException(
            status_code=400,
            detail="Add meg a számla fizetési határidejét - enélkül nem tudjuk, mikorra kell utalni.",
        )
    filename = file.filename or "szamla"
    content_type = file.content_type or "application/octet-stream"
    invoice = PerformanceCertificateInvoice(
        certificate_id=cert.id, filename=filename, content_type=content_type, storage_key="", url=""
    )
    db.add(invoice)
    db.flush()
    ext = os.path.splitext(filename)[1]
    key = f"tig-szamla/{project_id}/{szamlazo_kulcs}-{invoice.id}{ext}"
    data = await file.read()
    url = document_storage.upload_bytes(data, key, content_type)
    invoice.storage_key = key
    invoice.url = url
    if fizetesi_hatarido is not None:
        cert.fizetesi_hatarido = fizetesi_hatarido
    db.commit()
    db.refresh(cert)
    return PerformanceCertificateRead.model_validate(cert)


class HataridoIn(BaseModel):
    """A számla fizetési határideje. Üres értékkel törölhető, de csak addig,
    amíg nincs feltöltött számla: onnantól kötelező (lásd upload_szamla)."""

    fizetesi_hatarido: date | None = None


@router.post("/{project_id}/{szamlazo_kulcs}/hatarido", response_model=PerformanceCertificateRead)
def set_fizetesi_hatarido(
    project_id: int,
    szamlazo_kulcs: str,
    payload: HataridoIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """A fizetési határidő utólagos állítása.

    A feltöltéskor is megadható (ott kötelező is), de elírható - ilyenkor ne
    kelljen a számlát újra feltölteni azért, hogy a jó dátum kerüljön be.

    KIÜRÍTENI viszont csak addig lehet, amíg nincs feltöltött számla:
    különben a feltöltéskori kötelező megadást lehetne egy lépéssel
    megkerülni."""
    cert = _get_sent_certificate_or_404(db, project_id, szamlazo_kulcs)
    if payload.fizetesi_hatarido is None and cert.invoices:
        raise HTTPException(
            status_code=400,
            detail="A feltöltött számlához kell fizetési határidő - átírni lehet, kiüríteni nem.",
        )
    cert.fizetesi_hatarido = payload.fizetesi_hatarido
    db.commit()
    db.refresh(cert)
    return PerformanceCertificateRead.model_validate(cert)


@router.delete("/{project_id}/{szamlazo_kulcs}/szamla/{invoice_id}", response_model=PerformanceCertificateRead)
def delete_szamla(
    project_id: int,
    szamlazo_kulcs: str,
    invoice_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """Egy tévesen feltöltött számla törlése - a fájl a tárolóból is törlődik.
    A kifizetettség (szamla_kifizetve) és a hozzá tartozó Expense sor NEM
    változik: az már pénzügyi tény, nem a feltöltött dokumentum függvénye."""
    cert = _get_sent_certificate_or_404(db, project_id, szamlazo_kulcs)
    invoice = db.get(PerformanceCertificateInvoice, invoice_id)
    if invoice is None or invoice.certificate_id != cert.id:
        raise HTTPException(status_code=404, detail="A számla nem található.")
    document_storage.delete_object(invoice.storage_key)
    db.delete(invoice)
    db.commit()
    db.refresh(cert)
    return PerformanceCertificateRead.model_validate(cert)


class SzamlaKihagyasIn(BaseModel):
    """A számla-lépés kihagyása (vagy a kihagyás visszavonása).

    `kihagyva=True` esetén az indok KÖTELEZŐ - ugyanaz a szabály, mint a
    szerződés és a TIG kihagyásánál."""

    kihagyva: bool = True
    indok: str | None = None


@router.post("/{project_id}/{szamlazo_kulcs}/szamla-kihagyas", response_model=PerformanceCertificateRead)
def skip_szamla(
    project_id: int,
    szamlazo_kulcs: str,
    payload: SzamlaKihagyasIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """A SZÁMLA-LÉPÉS kihagyása: ehhez a TIG-hez nem várunk se számlát, se
    kifizetést.

    Van, amikor a papír elkészült, de a pénz útja itt nem folytatódik: máshol
    számolták el, elengedték, beszámították egy másik tételbe. Enélkül az ilyen
    munkák örökre "nincs kifizetve" állapotban lógtak az utókövetésben, és a
    projekt sosem lett kész - pedig nem volt rajta teendő.

    Az INDOK kötelező, ugyanazért, amiért a szerződés és a TIG kihagyásánál:
    fél év múlva a puszta "kihagyva" jelölésről nem derülne ki, szándékos
    volt-e vagy elfelejtődött.

    Amihez már tartozik KIADÁS SOR a Pénzügyben, azt nem lehet kihagyni: az
    pénzügyi tény, amit előbb ott kell rendezni (a Kiadás törlése ezt a TIG-et
    is visszadobja "nincs kifizetve" állapotba, lásd
    services/kiadas_kapcsolatok.py) - onnantól ez a kihagyás is megy.

    A TIG-TŐL FÜGGETLEN: kihagyni akkor is lehet, ha a félnek még nincs (vagy
    nem is lesz) TIG-je. Feltölteni számlát továbbra is csak kiküldött TIG-hez
    lehet - ott van mihez kötni -, de KIMONDANI, hogy ide nem jön számla, a
    TIG-től függetlenül szabad. Ha nincs még bejegyzés, itt jön létre: valahol
    tárolni kell a kihagyást és az indokát."""
    if not payload.kihagyva:
        # A visszavonáshoz kell egy bejegyzés - nincs mit visszavonni azon,
        # ami nincs.
        cert = _certificate_or_none(db, project_id, szamlazo_kulcs)
        if cert is None:
            raise HTTPException(status_code=404, detail="Ehhez a projekthez és félhez nem tartozik TIG-bejegyzés.")
        cert.szamla_kihagyva = False
        cert.szamla_kihagyas_oka = None
        db.commit()
        db.refresh(cert)
        return PerformanceCertificateRead.model_validate(cert)

    cert = _certificate_or_none(db, project_id, szamlazo_kulcs)
    if cert is None:
        project = _get_project_or_404(db, project_id)
        csoport = _validate_szamlazo(db, project, szamlazo_kulcs, szerzodes_kell=False)
        cert = _get_or_create_draft(db, project, csoport)

    indok = (payload.indok or "").strip()
    if not indok:
        raise HTTPException(
            status_code=400,
            detail="Írd le, miért marad el a számla és a kifizetés - enélkül később nem lehet mihez kötni.",
        )
    if cert.expense_id is not None:
        raise HTTPException(
            status_code=400,
            detail="Ehhez a TIG-hez már tartozik Kiadás sor a Pénzügyben - előbb azt kell rendezni.",
        )
    cert.szamla_kihagyva = True
    cert.szamla_kihagyas_oka = indok
    db.commit()
    db.refresh(cert)
    return PerformanceCertificateRead.model_validate(cert)


@router.post("/{project_id}/{szamlazo_kulcs}/szamla-kifizetve", response_model=PerformanceCertificateRead)
def mark_szamla_kifizetve(
    project_id: int,
    szamlazo_kulcs: str,
    payload: KifizetesIn | None = None,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """A feltöltött számla kifizetettként jelölése - ez hozza létre (vagy
    frissíti, ha már létezik) a Pénzügy -> Kiadások-ban megjelenő Expense
    sort, a projekt project_code_id-jához és az alvállalkozóhoz kötve, hogy a
    költség a helyes projekthez kapcsolódjon (lásd spec 2.1).

    `kiadasba_kerul=false` esetén CSAK a papír állapotát jelöljük: a kifizetés
    megtörtént, de máshol van elszámolva (lásd KifizetesIn).

    Az UTALÁS DÁTUMA a `kifizetes_datuma` mezőből jön - üresen a mai nap. A
    jelölés ugyanis gyakran csak napokkal a tényleges utalás után történik meg,
    és akkor a pénzügyi kimutatásban rossz napra kerülne a tétel."""
    cert = _get_sent_certificate_or_404(db, project_id, szamlazo_kulcs)
    if not cert.invoices:
        raise HTTPException(status_code=400, detail="Előbb töltsd fel a számlát.")

    utalas = (payload.kifizetes_datuma if payload is not None else None) or date.today()
    cert.utalas_datuma = utalas

    if payload is not None and not payload.kiadasba_kerul:
        cert.szamla_kifizetve = True
        db.commit()
        db.refresh(cert)
        return PerformanceCertificateRead.model_validate(cert)

    project = _get_project_or_404(db, project_id)

    # float(): a Numeric oszlop az adatbázisból Decimal-ként jön vissza, és a
    # Decimal * float TypeError-t dob (csak akkor működne, ha ugyanabban a
    # kérésben mi magunk írtunk bele float-ot).
    brutto = round(float(cert.netto_osszeg) * 1.27, 2) if (cert.plusz_afa and cert.netto_osszeg) else cert.netto_osszeg

    if cert.expense_id is not None:
        expense = db.get(Expense, cert.expense_id)
    else:
        expense = None

    # Egy TIG több projekt munkáját is igazolhatja - a Kiadás sor a TIG saját
    # ("otthon") projektjének kódjára kerül, de a megnevezés felsorolja az
    # összes érintett kódot, hogy a Pénzügyben látszódjon, mi van benne. A
    # fedezettség (Utalandók fül) az összes érintett kódot külön is nézi, lásd
    # routes/finance.py.
    erintett_kodok = [
        t.project.projektkod_szoveg
        for t in cert.tetelek
        if t.project is not None and t.project.projektkod_szoveg
    ]
    kodok_szoveg = ", ".join(dict.fromkeys(erintett_kodok)) or project.projektkod_szoveg or project.nev or ""

    if expense is None:
        expense = Expense(
            megnevezes=f"TIG - {cert.ceg_neve or ''} - {kodok_szoveg}".strip(" -"),
            project_code_id=project.project_code_id,
            employee_id=cert.employee_id,
            tipus="kulsos",
            netto=cert.netto_osszeg,
            brutto=brutto,
            hozzaadas_a_kiadasokhoz=True,
        )
        db.add(expense)
        db.flush()
        cert.expense_id = expense.id
    else:
        expense.netto = cert.netto_osszeg
        expense.brutto = brutto

    expense.kesz = True
    expense.fizetes_datuma = utalas
    # A számláról ismert határidő a Kiadás sorra is átmegy, ha ott még nincs -
    # a Pénzügy "Utalandók" nézete ebből tudja, mi jár le hamarosan. Egy már
    # ott kézzel beírt határidőt nem írunk felül.
    if expense.fizetes_hatarideje is None and cert.fizetesi_hatarido is not None:
        expense.fizetes_hatarideje = cert.fizetesi_hatarido
    cert.szamla_kifizetve = True
    db.commit()
    db.refresh(cert)
    return PerformanceCertificateRead.model_validate(cert)


@router.delete("/{project_id}/{szamlazo_kulcs}", status_code=204)
def delete_certificate(
    project_id: int,
    szamlazo_kulcs: str,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "delete")),
):
    """A TIG-bejegyzés teljes törlése - a munkatárs ezután újra "hiányzik"
    ezen a projekten, és készíthető neki új TIG.

    Erre azért van szükség, mert a TIG egy elrontott adattal (rossz összeg,
    rossz teljesítés) is kiküldhető: az állapot visszaállítása nem elég, ha
    tiszta lappal akarjuk újrakezdeni. A feltöltött számlák a TIG-gel együtt
    törlődnek (cascade), a fájlok a tárolóból is.

    Amihez KIADÁS SOR tartozik a Pénzügyben, azt nem töröljük: az pénzügyi
    tény, amit előbb ott kell rendezni (a Kiadás törlése ezt a TIG-et is
    visszadobja "nincs kifizetve" állapotba, lásd
    services/kiadas_kapcsolatok.py - onnantól ez a törlés is megy).

    A pusztán "kifizetve" jelölés viszont NEM akadály, ha nem tartozik hozzá
    Kiadás sor (lásd schemas/finance.KifizetesIn kiadasba_kerul=False): ott
    csak egy jelölés áll a papíron, nincs mit előbb rendezni - ha az is téves
    volt, a TIG-gel együtt szűnik meg."""
    cert = _certificate_or_none(db, project_id, szamlazo_kulcs)
    if cert is None:
        raise HTTPException(status_code=404, detail="Ehhez a projekthez és félhez nincs TIG bejegyzés.")
    if cert.expense_id is not None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Ehhez a TIG-hez Kiadás sor tartozik a Pénzügyben - előbb azt töröld ott. "
                "A Kiadás törlése ezt a TIG-et is visszaállítja „nincs kifizetve” állapotba."
            ),
        )
    for invoice in cert.invoices:
        document_storage.delete_object(invoice.storage_key)
    db.delete(cert)
    db.commit()


# ═══════════════════════════════════════════════════════════════════════════
# PROJEKTKÓD-SZINTŰ ÁG: TIG forgatás nélküli alvállalkozói kiadáshoz
# ═══════════════════════════════════════════════════════════════════════════
#
# Lásd subcontractor_contracts.py azonos című szakaszát - ugyanaz a döntés: ha
# egy projektkódon nincs forgatás (tisztán ügynökségi feladat), a TIG a
# PROJEKTKÓDHOZ kötődik (lásd models/performance_certificate.py
# PerformanceCertificate.project_code_id), és a szerződés-oldali "csoport"
# fogalmakat (szamlazo_csoportok_projektkodon stb.) újrahasználja - nincs
# tétel-rendszer és nincs "ki számláz kiért" felülírás ezen az ágon sem.
#
# A számla-lépés (feltöltött számla, fizetési határidő, kifizetés-jelölés) ezen
# az ágon NEM érhető el: egy forgatás nélküli alvállalkozói kiadásnál maga az
# Expense (a kiadás sora) hordozza a kifizetés állapotát - ott jelölhető
# kifizetettnek, nincs szükség egy második, TIG-hez kötött számla-lépésre.


def _get_project_code_or_404(db: Session, project_code_id: int) -> ProjectCode:
    projektkod = db.get(ProjectCode, project_code_id)
    if projektkod is None:
        raise HTTPException(status_code=404, detail="Projektkód nem található")
    return projektkod


#: (projektkód id, ember) -> az őt lefedő TIG, és (projektkód id, számlázó
#: kulcs) -> a fél TIG-je azon a projektkódon - lásd TigLookup (forgatás-alapú
#: megfelelője).
TigLookupProjektkod = tuple[
    dict[tuple[int, int], PerformanceCertificate], dict[tuple[int, str], PerformanceCertificate]
]


def _load_tig_lookup_projektkodon(db: Session, project_code_ids: set[int]) -> TigLookupProjektkod:
    """Lásd _load_tig_lookup (forgatás-alapú megfelelője) - itt nincs
    tétel-rendszer, ezért egyenesen a `project_code_id` oszlopra szűrünk."""
    if not project_code_ids:
        return {}, {}
    ember_fedettseg: dict[tuple[int, int], PerformanceCertificate] = {}
    fel_tig: dict[tuple[int, str], PerformanceCertificate] = {}
    for cert in (
        db.query(PerformanceCertificate).filter(PerformanceCertificate.project_code_id.in_(project_code_ids)).all()
    ):
        if cert.employee_id is not None:
            ember_fedettseg[(cert.project_code_id, cert.employee_id)] = cert
        kulcs = tig_kulcsa(cert)
        if kulcs is not None:
            fel_tig[(cert.project_code_id, kulcs)] = cert
    return ember_fedettseg, fel_tig


def tig_keszitheto_csoportok_projektkodon(
    projektkod: ProjectCode,
    keretszerzodesek: dict[str, list[Contract]],
    project_code_contracts: dict[tuple[int, str], Contract],
) -> list[SzamlazoCsoport]:
    """Lásd tig_keszitheto_csoportok (forgatás-alapú megfelelője)."""
    return [
        cs
        for cs in szamlazo_csoportok_projektkodon(projektkod)
        if csoport_szerzodes_kesz_projektkodon(projektkod, cs, keretszerzodesek, project_code_contracts)
    ]


def _tig_keszitheto_projektkodon(db: Session, projektkod: ProjectCode, csoport: SzamlazoCsoport) -> bool:
    keretszerzodesek, project_code_contracts = load_szerzodes_kornyezet_projektkodon(db, [projektkod])
    return csoport_szerzodes_kesz_projektkodon(projektkod, csoport, keretszerzodesek, project_code_contracts)


def _csoport_fedve_projektkodon(
    projektkod: ProjectCode, csoport: SzamlazoCsoport, lookup: TigLookupProjektkod
) -> bool:
    """Lásd _csoport_fedve (forgatás-alapú megfelelője)."""
    _, fel_tig = lookup
    fel_cert = fel_tig.get((projektkod.id, csoport.kulcs))
    if fel_cert is not None and fel_cert.allapot in TERMINAL_STATUSES:
        return True
    ember_fedettseg, _ = lookup
    for tag in csoport.tagok:
        cert = ember_fedettseg.get((projektkod.id, tag.id))
        if cert is None or cert.allapot not in TERMINAL_STATUSES:
            return False
    return True


def _tig_pending_csoportok_projektkodon(
    projektkod: ProjectCode, csoportok: list[SzamlazoCsoport], lookup: TigLookupProjektkod
) -> list[tuple[SzamlazoCsoport, PerformanceCertificate | None]]:
    _, fel_tig = lookup
    result: list[tuple[SzamlazoCsoport, PerformanceCertificate | None]] = []
    for csoport in csoportok:
        if _csoport_fedve_projektkodon(projektkod, csoport, lookup):
            continue
        result.append((csoport, fel_tig.get((projektkod.id, csoport.kulcs))))
    return result


def projektkodok_alvallalkozoi_kiadassal(db: Session) -> list[ProjectCode]:
    """Azok a projektkódok, amiken FORGATÁS NÉLKÜL van legalább egy
    alvállalkozói kiadás - lásd models/finance.py Expense.alvallalkozo_project_id
    és models/project_code.py ProjectCode.alvallalkozo_stab_forgatas_nelkul."""
    projekt_kod_idk = set(
        db.scalars(
            select(Expense.project_code_id).where(
                Expense.employee_id.is_not(None),
                Expense.alvallalkozo_project_id.is_(None),
                Expense.project_code_id.is_not(None),
            )
        ).all()
    )
    if not projekt_kod_idk:
        return []
    return [
        pk
        for pk in db.query(ProjectCode).filter(ProjectCode.id.in_(projekt_kod_idk)).all()
        if not pk.elmaradt and not papirozas_hatokor.projektkod_kivett(pk.projektkod)
    ]


class PendingProjectCodeEmployeeInfo(BaseModel):
    """Lásd PendingEmployeeInfo (forgatás-alapú megfelelője) - egyszerűbb,
    nincs "lefedettek" tétellista (lásd fájl fejléce)."""

    id: int
    szamlazo: str
    full_name: str
    email: str | None
    ceg_neve: str | None
    szekhely: str | None
    adoszam: str | None
    megbizas_targya: str | None
    plusz_afa: bool | None
    draft: DraftInfo | None
    #: A fél eseti szerződése ezen a projektkódon - ebből tölti elő az űrlap
    #: azt, amit ott már megadtak (lásd SzerzodesElotoltes).
    szerzodes: SzerzodesElotoltes | None = None


class PendingProjectCodeDetail(BaseModel):
    project_code_id: int
    projektkod: str
    project_nev: str | None
    pending: list[PendingProjectCodeEmployeeInfo]
    tig_ready: bool
    szerzodesre_varo: list[PendingProjectCodeEmployeeInfo] = []


def _pending_info_projektkodon(
    csoport: SzamlazoCsoport, existing: PerformanceCertificate | None, szerzodes: Contract | None = None
) -> PendingProjectCodeEmployeeInfo:
    fel = csoport.fel
    return PendingProjectCodeEmployeeInfo(
        id=fel.employee.id if fel.employee else 0,
        szamlazo=fel.kulcs,
        full_name=fel.nev,
        email=fel.email,
        ceg_neve=fel.ceg_neve,
        szekhely=fel.szekhely,
        adoszam=fel.adoszam,
        megbizas_targya=fel.megbizas_targya,
        plusz_afa=fel.plusz_afa,
        draft=_draft_info(existing),
        szerzodes=_szerzodes_elotoltes(szerzodes),
    )


@router.get("/projektkodok/{project_code_id}", response_model=PendingProjectCodeDetail)
def get_pending_for_project_code(
    project_code_id: int, db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)
):
    projektkod = _get_project_code_or_404(db, project_code_id)
    keretszerzodesek, project_code_contracts = load_szerzodes_kornyezet_projektkodon(db, [projektkod])
    osszes_csoport = szamlazo_csoportok_projektkodon(projektkod)
    keszitheto = [
        cs
        for cs in osszes_csoport
        if csoport_szerzodes_kesz_projektkodon(projektkod, cs, keretszerzodesek, project_code_contracts)
    ]
    szerzodesre_varo_csoportok = [cs for cs in osszes_csoport if cs not in keszitheto]
    tig_lookup = _load_tig_lookup_projektkodon(db, {projektkod.id})
    pending = _tig_pending_csoportok_projektkodon(projektkod, keszitheto, tig_lookup)
    szerzodesek = eseti_szerzodesek_a_projektkodon(db, projektkod.id)

    return PendingProjectCodeDetail(
        project_code_id=projektkod.id,
        projektkod=projektkod.projektkod,
        project_nev=projektkod.project_nev,
        pending=[
            _pending_info_projektkodon(csoport, existing, szerzodesek.get(csoport.kulcs))
            for csoport, existing in pending
        ],
        tig_ready=bool(pending),
        szerzodesre_varo=[_pending_info_projektkodon(cs, None, szerzodesek.get(cs.kulcs)) for cs in szerzodesre_varo_csoportok],
    )


def _validate_szamlazo_projektkodon(
    db: Session, projektkod: ProjectCode, szamlazo_kulcs: str, *, szerzodes_kell: bool = True
) -> SzamlazoCsoport:
    """Lásd _validate_szamlazo (forgatás-alapú megfelelője)."""
    fel = szamlazo.feloldas(db, szamlazo_kulcs)
    if fel is None:
        raise HTTPException(status_code=404, detail="A számlázó fél nem található")
    csoport = next((cs for cs in szamlazo_csoportok_projektkodon(projektkod) if cs.kulcs == fel.kulcs), None)
    if csoport is None:
        if fel.employee is not None and fel.employee.tipus == EmployeeType.BELSOS:
            raise HTTPException(status_code=400, detail="Belsős munkatársnak nem kell teljesítési igazolás.")
        raise HTTPException(
            status_code=400, detail="Ezen a projektkódon senkinek a munkáját nem ez a fél számlázza."
        )
    if szerzodes_kell and not _tig_keszitheto_projektkodon(db, projektkod, csoport):
        raise HTTPException(
            status_code=400,
            detail=f"{csoport.cimke()} szerződése még nincs meg ezen a projektkódon - TIG csak azután készíthető róla.",
        )
    return csoport


def _szamlazo_szuro_projektkodon(fel: SzamlazoFel):
    if fel.vallalkozas is not None:
        return PerformanceCertificate.vallalkozas_id == fel.vallalkozas.id
    return (PerformanceCertificate.employee_id == fel.employee.id) & PerformanceCertificate.vallalkozas_id.is_(None)


def _get_or_create_draft_projektkodon(
    db: Session, projektkod: ProjectCode, csoport: SzamlazoCsoport
) -> PerformanceCertificate:
    """Lásd _get_or_create_draft (forgatás-alapú megfelelője)."""
    _, fel_tig = _load_tig_lookup_projektkodon(db, {projektkod.id})
    existing = fel_tig.get((projektkod.id, csoport.kulcs))
    if existing is None:
        existing = (
            db.query(PerformanceCertificate)
            .filter(
                PerformanceCertificate.project_code_id == projektkod.id, _szamlazo_szuro_projektkodon(csoport.fel)
            )
            .first()
        )
    if existing is not None:
        if existing.allapot in TERMINAL_STATUSES:
            raise HTTPException(
                status_code=400,
                detail="Ehhez a projektkódhoz és félhez már véglegesített TIG-bejegyzés tartozik (kiküldve vagy kihagyva).",
            )
        return existing
    fel = csoport.fel
    # A fél ESETI SZERZŐDÉSE ugyanerről a munkáról szól - amit oda már
    # beírtak, azt innen vesszük át (lásd SzerzodesElotoltes).
    szerzodes = eseti_szerzodesek_a_projektkodon(db, projektkod.id).get(csoport.kulcs)

    def _szerzodesbol(mezo: str, tartalek):
        ertek = getattr(szerzodes, mezo, None) if szerzodes is not None else None
        return tartalek if ertek in (None, "") else ertek

    draft = PerformanceCertificate(
        project_code_id=projektkod.id,
        employee_id=fel.employee.id if fel.employee else None,
        vallalkozas_id=fel.vallalkozas.id if fel.vallalkozas else None,
        allapot="Készítés alatt",
        ceg_neve=_szerzodesbol("ceg_neve", fel.ceg_neve),
        szekhely=_szerzodesbol("szekhely", fel.szekhely),
        adoszam=_szerzodesbol("adoszam", fel.adoszam),
        megbizas_targya=_szerzodesbol("megbizas_targya", fel.megbizas_targya),
        netto_osszeg=_szerzodesbol("netto_osszeg", None),
        plusz_afa=_szerzodesbol("plusz_afa", fel.plusz_afa),
        teljesites_szoveg=_szerzodesbol("teljesites_szoveg", ""),
        email=fel.email,
    )
    db.add(draft)
    db.flush()
    return draft


class TigDraftInProjektkod(BaseModel):
    ceg_neve: str | None = None
    szekhely: str | None = None
    adoszam: str | None = None
    megbizas_targya: str | None = None
    netto_osszeg: float | None = None
    teljesites_szoveg: str | None = None
    keltezes: date | None = None
    plusz_afa: bool | None = None


def _apply_draft_fields_projektkodon(draft: PerformanceCertificate, payload: TigDraftInProjektkod) -> None:
    for field in (
        "ceg_neve",
        "szekhely",
        "adoszam",
        "megbizas_targya",
        "netto_osszeg",
        "teljesites_szoveg",
        "keltezes",
        "plusz_afa",
    ):
        value = getattr(payload, field)
        if value is not None:
            setattr(draft, field, value)


@router.post("/projektkodok/{project_code_id}/{szamlazo_kulcs}/save", response_model=PerformanceCertificateRead)
def save_draft_projektkodon(
    project_code_id: int,
    szamlazo_kulcs: str,
    payload: TigDraftInProjektkod,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "create")),
):
    projektkod = _get_project_code_or_404(db, project_code_id)
    csoport = _validate_szamlazo_projektkodon(db, projektkod, szamlazo_kulcs)
    draft = _get_or_create_draft_projektkodon(db, projektkod, csoport)
    _apply_draft_fields_projektkodon(draft, payload)
    db.commit()
    db.refresh(draft)
    return PerformanceCertificateRead.model_validate(draft)


@router.post(
    "/projektkodok/{project_code_id}/{szamlazo_kulcs}/generate-and-send", response_model=PerformanceCertificateRead
)
def generate_and_send_projektkodon(
    project_code_id: int,
    szamlazo_kulcs: str,
    payload: TigDraftInProjektkod,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "create")),
):
    projektkod = _get_project_code_or_404(db, project_code_id)
    csoport = _validate_szamlazo_projektkodon(db, projektkod, szamlazo_kulcs)
    fel = csoport.fel
    draft = _get_or_create_draft_projektkodon(db, projektkod, csoport)
    _apply_draft_fields_projektkodon(draft, payload)

    if not draft.netto_osszeg or draft.netto_osszeg <= 0:
        raise HTTPException(status_code=400, detail="Add meg a nettó összeget.")
    cimzett = (draft.email or fel.email or "").strip()
    if not cimzett:
        raise HTTPException(status_code=400, detail="A számlázó félnek nincs email címe.")

    keltezes = draft.keltezes or date.today()
    draft.keltezes = keltezes
    teljesites_str = papir_tetelek.teljesites_szovege(draft.teljesites_szoveg, [], "")

    doc_link = None
    pdf_bytes = None
    base_name = f"{projektkod.projektkod}_{draft.ceg_neve or fel.nev}_TIG"
    try:
        if settings.gdoc_kulsos_tig_template_id:
            fields = {
                "nev": draft.ceg_neve or fel.nev,
                "hely": draft.szekhely or "",
                "adoszam": draft.adoszam or "",
                "targy": papir_tetelek.targy_szovege(draft.megbizas_targya, []),
                "tido": teljesites_str,
                "projkod": projektkod.projektkod,
                "netto": f"{draft.netto_osszeg:,.0f}".replace(",", " "),
                "kelt": keltezes.strftime("%Y.%m.%d."),
                "afa": "+ ÁFA" if draft.plusz_afa else "",
                "nettoki": szam_betukkel(draft.netto_osszeg),
            }
            pdf_bytes, new_doc_id = gdoc_fill_and_export_pdf(
                template_file_id=settings.gdoc_kulsos_tig_template_id,
                base_name=base_name,
                fields=fields,
                output_folder_id=settings.drive_kulsos_tig or settings.gdoc_output_folder_id or settings.drive_folder_id or None,
            )
            doc_link = f"https://docs.google.com/document/d/{new_doc_id}/edit"

        subject = f"{draft.ceg_neve or fel.nev}_{projektkod.projektkod} - Projekt_TIG"
        # A projektkód-alapú TIG-nél nincs forgatás-dátum - a szöveggel megadott
        # teljesítés (pl. "2026 július") kerül a levélbe is, ne egy "–"
        # (a felhasználó kérése).
        html = _TIG_EMAIL_HTML.format(projektdatum=teljesites_str or "–")
        send_message([cimzett], subject, html, pdf_bytes=pdf_bytes, pdf_filename="teljesitesi_igazolas.pdf")
    except RuntimeError as exc:
        db.commit()
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    draft.allapot = "Kiküldve"
    draft.file_url = doc_link
    db.commit()
    db.refresh(draft)
    return PerformanceCertificateRead.model_validate(draft)


class TigKihagyasInProjektkod(BaseModel):
    kihagyas_oka: str | None = None


@router.post("/projektkodok/{project_code_id}/{szamlazo_kulcs}/skip", response_model=PerformanceCertificateRead)
def skip_tig_projektkodon(
    project_code_id: int,
    szamlazo_kulcs: str,
    payload: TigKihagyasInProjektkod,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """Lásd skip_tig (forgatás-alapú megfelelője) - a szerződéstől függetlenül
    kihagyható."""
    indok = (payload.kihagyas_oka or "").strip()
    if not indok:
        raise HTTPException(status_code=400, detail="A kihagyás okát meg kell adni.")
    projektkod = _get_project_code_or_404(db, project_code_id)
    csoport = _validate_szamlazo_projektkodon(db, projektkod, szamlazo_kulcs, szerzodes_kell=False)
    draft = _get_or_create_draft_projektkodon(db, projektkod, csoport)
    draft.allapot = "Kihagyva"
    draft.kihagyas_oka = indok
    db.commit()
    db.refresh(draft)
    return PerformanceCertificateRead.model_validate(draft)


def _certificate_or_none_projektkodon(
    db: Session, project_code_id: int, szamlazo_kulcs: str
) -> PerformanceCertificate | None:
    fel = szamlazo.feloldas(db, szamlazo_kulcs)
    if fel is None:
        return None
    _, fel_tig = _load_tig_lookup_projektkodon(db, {project_code_id})
    cert = fel_tig.get((project_code_id, fel.kulcs))
    if cert is not None:
        return cert
    return (
        db.query(PerformanceCertificate)
        .filter(PerformanceCertificate.project_code_id == project_code_id, _szamlazo_szuro_projektkodon(fel))
        .first()
    )


@router.post("/projektkodok/{project_code_id}/{szamlazo_kulcs}/allapot", response_model=PerformanceCertificateRead)
def set_allapot_projektkodon(
    project_code_id: int,
    szamlazo_kulcs: str,
    payload: AllapotIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """Lásd set_allapot (forgatás-alapú megfelelője)."""
    if payload.allapot not in ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail=f"Ismeretlen állapot. Választható: {', '.join(ALLOWED_STATUSES)}")
    cert = _certificate_or_none_projektkodon(db, project_code_id, szamlazo_kulcs)
    if cert is None:
        raise HTTPException(status_code=404, detail="Ehhez a projektkódhoz és félhez nincs TIG bejegyzés.")
    cert.allapot = payload.allapot
    db.commit()
    db.refresh(cert)
    return PerformanceCertificateRead.model_validate(cert)


@router.post("/projektkodok/{project_code_id}/{szamlazo_kulcs}/sajat-fajl", response_model=PerformanceCertificateRead)
async def upload_sajat_tig_projektkodon(
    project_code_id: int,
    szamlazo_kulcs: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "create")),
):
    """Lásd upload_sajat_tig (forgatás-alapú megfelelője)."""
    projektkod = _get_project_code_or_404(db, project_code_id)
    csoport = _validate_szamlazo_projektkodon(db, projektkod, szamlazo_kulcs)
    draft = _get_or_create_draft_projektkodon(db, projektkod, csoport)
    if not draft.netto_osszeg or draft.netto_osszeg <= 0:
        raise HTTPException(status_code=400, detail="Add meg a nettó összeget.")

    filename = file.filename or "tig"
    content_type = file.content_type or "application/octet-stream"
    data = await file.read()

    regi_kulcs = draft.file_storage_key
    kulcs = f"tig-dokumentum/projektkod-{project_code_id}/{szamlazo_kulcs}-{draft.id}{os.path.splitext(filename)[1]}"
    draft.file_url = document_storage.upload_bytes(data, kulcs, content_type)
    draft.file_storage_key = kulcs
    draft.allapot = "Kiküldve"
    db.commit()
    if regi_kulcs and regi_kulcs != kulcs:
        document_storage.delete_object(regi_kulcs)
    db.refresh(draft)
    return PerformanceCertificateRead.model_validate(draft)


@router.get("/projektkodok/{project_code_id}/all", response_model=list[PerformanceCertificateRead])
def list_all_for_project_code(
    project_code_id: int, db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)
):
    """Lásd list_all_for_project (forgatás-alapú megfelelője) - itt nincs
    tétel-alapú lefedettség, a szűrés a TIG saját project_code_id-ja szerint
    megy (lásd fájl fejléce: ezen az ágon egy TIG csak EGY projektkódhoz
    tartozhat)."""
    rows = db.query(PerformanceCertificate).filter(PerformanceCertificate.project_code_id == project_code_id).all()
    return [PerformanceCertificateRead.model_validate(c) for c in rows]


@router.delete("/projektkodok/{project_code_id}/{szamlazo_kulcs}", status_code=204)
def delete_certificate_projektkodon(
    project_code_id: int,
    szamlazo_kulcs: str,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "delete")),
):
    """Lásd delete_certificate (forgatás-alapú megfelelője)."""
    cert = _certificate_or_none_projektkodon(db, project_code_id, szamlazo_kulcs)
    if cert is None:
        raise HTTPException(status_code=404, detail="Ehhez a projektkódhoz és félhez nincs TIG bejegyzés.")
    if cert.expense_id is not None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Ehhez a TIG-hez Kiadás sor tartozik a Pénzügyben - előbb azt töröld ott. "
                "A Kiadás törlése ezt a TIG-et is visszaállítja „nincs kifizetve” állapotba."
            ),
        )
    for invoice in cert.invoices:
        document_storage.delete_object(invoice.storage_key)
    db.delete(cert)
    db.commit()


def _get_sent_certificate_or_404_projektkodon(
    db: Session, project_code_id: int, szamlazo_kulcs: str
) -> PerformanceCertificate:
    """Lásd _get_sent_certificate_or_404 (forgatás-alapú megfelelője)."""
    cert = _certificate_or_none_projektkodon(db, project_code_id, szamlazo_kulcs)
    if cert is None:
        raise HTTPException(status_code=404, detail="Ehhez a projektkódhoz és félhez nem tartozik TIG-bejegyzés.")
    if cert.allapot != "Kiküldve":
        raise HTTPException(status_code=400, detail="Számla csak kiküldött TIG-hez tölthető fel.")
    return cert


@router.post("/projektkodok/{project_code_id}/{szamlazo_kulcs}/szamla", response_model=PerformanceCertificateRead)
async def upload_szamla_projektkodon(
    project_code_id: int,
    szamlazo_kulcs: str,
    file: UploadFile = File(...),
    fizetesi_hatarido: date | None = Form(default=None),
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """Lásd upload_szamla (forgatás-alapú megfelelője)."""
    cert = _get_sent_certificate_or_404_projektkodon(db, project_code_id, szamlazo_kulcs)
    if fizetesi_hatarido is None and cert.fizetesi_hatarido is None:
        raise HTTPException(
            status_code=400,
            detail="Add meg a számla fizetési határidejét - enélkül nem tudjuk, mikorra kell utalni.",
        )
    filename = file.filename or "szamla"
    content_type = file.content_type or "application/octet-stream"
    invoice = PerformanceCertificateInvoice(
        certificate_id=cert.id, filename=filename, content_type=content_type, storage_key="", url=""
    )
    db.add(invoice)
    db.flush()
    ext = os.path.splitext(filename)[1]
    key = f"tig-szamla/projektkod-{project_code_id}/{szamlazo_kulcs}-{invoice.id}{ext}"
    data = await file.read()
    url = document_storage.upload_bytes(data, key, content_type)
    invoice.storage_key = key
    invoice.url = url
    if fizetesi_hatarido is not None:
        cert.fizetesi_hatarido = fizetesi_hatarido
    db.commit()
    db.refresh(cert)
    return PerformanceCertificateRead.model_validate(cert)


@router.post("/projektkodok/{project_code_id}/{szamlazo_kulcs}/hatarido", response_model=PerformanceCertificateRead)
def set_fizetesi_hatarido_projektkodon(
    project_code_id: int,
    szamlazo_kulcs: str,
    payload: HataridoIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """Lásd set_fizetesi_hatarido (forgatás-alapú megfelelője)."""
    cert = _get_sent_certificate_or_404_projektkodon(db, project_code_id, szamlazo_kulcs)
    if payload.fizetesi_hatarido is None and cert.invoices:
        raise HTTPException(
            status_code=400,
            detail="A feltöltött számlához kell fizetési határidő - átírni lehet, kiüríteni nem.",
        )
    cert.fizetesi_hatarido = payload.fizetesi_hatarido
    db.commit()
    db.refresh(cert)
    return PerformanceCertificateRead.model_validate(cert)


@router.delete(
    "/projektkodok/{project_code_id}/{szamlazo_kulcs}/szamla/{invoice_id}", response_model=PerformanceCertificateRead
)
def delete_szamla_projektkodon(
    project_code_id: int,
    szamlazo_kulcs: str,
    invoice_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """Lásd delete_szamla (forgatás-alapú megfelelője)."""
    cert = _get_sent_certificate_or_404_projektkodon(db, project_code_id, szamlazo_kulcs)
    invoice = db.get(PerformanceCertificateInvoice, invoice_id)
    if invoice is None or invoice.certificate_id != cert.id:
        raise HTTPException(status_code=404, detail="A számla nem található.")
    document_storage.delete_object(invoice.storage_key)
    db.delete(invoice)
    db.commit()
    db.refresh(cert)
    return PerformanceCertificateRead.model_validate(cert)


@router.post(
    "/projektkodok/{project_code_id}/{szamlazo_kulcs}/szamla-kihagyas", response_model=PerformanceCertificateRead
)
def skip_szamla_projektkodon(
    project_code_id: int,
    szamlazo_kulcs: str,
    payload: SzamlaKihagyasIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """Lásd skip_szamla (forgatás-alapú megfelelője)."""
    if not payload.kihagyva:
        cert = _certificate_or_none_projektkodon(db, project_code_id, szamlazo_kulcs)
        if cert is None:
            raise HTTPException(status_code=404, detail="Ehhez a projektkódhoz és félhez nem tartozik TIG-bejegyzés.")
        cert.szamla_kihagyva = False
        cert.szamla_kihagyas_oka = None
        db.commit()
        db.refresh(cert)
        return PerformanceCertificateRead.model_validate(cert)

    cert = _certificate_or_none_projektkodon(db, project_code_id, szamlazo_kulcs)
    if cert is None:
        projektkod = _get_project_code_or_404(db, project_code_id)
        csoport = _validate_szamlazo_projektkodon(db, projektkod, szamlazo_kulcs, szerzodes_kell=False)
        cert = _get_or_create_draft_projektkodon(db, projektkod, csoport)

    indok = (payload.indok or "").strip()
    if not indok:
        raise HTTPException(
            status_code=400,
            detail="Írd le, miért marad el a számla és a kifizetés - enélkül később nem lehet mihez kötni.",
        )
    if cert.expense_id is not None:
        raise HTTPException(
            status_code=400,
            detail="Ehhez a TIG-hez már tartozik Kiadás sor a Pénzügyben - előbb azt kell rendezni.",
        )
    cert.szamla_kihagyva = True
    cert.szamla_kihagyas_oka = indok
    db.commit()
    db.refresh(cert)
    return PerformanceCertificateRead.model_validate(cert)


@router.post(
    "/projektkodok/{project_code_id}/{szamlazo_kulcs}/szamla-kifizetve", response_model=PerformanceCertificateRead
)
def mark_szamla_kifizetve_projektkodon(
    project_code_id: int,
    szamlazo_kulcs: str,
    payload: KifizetesIn | None = None,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """Lásd mark_szamla_kifizetve (forgatás-alapú megfelelője) - a Kiadás sor
    itt egyenesen a TIG saját project_code_id-jára kerül, tétel-lista híján."""
    cert = _get_sent_certificate_or_404_projektkodon(db, project_code_id, szamlazo_kulcs)
    if not cert.invoices:
        raise HTTPException(status_code=400, detail="Előbb töltsd fel a számlát.")

    utalas = (payload.kifizetes_datuma if payload is not None else None) or date.today()
    cert.utalas_datuma = utalas

    if payload is not None and not payload.kiadasba_kerul:
        cert.szamla_kifizetve = True
        db.commit()
        db.refresh(cert)
        return PerformanceCertificateRead.model_validate(cert)

    projektkod = _get_project_code_or_404(db, project_code_id)

    brutto = round(float(cert.netto_osszeg) * 1.27, 2) if (cert.plusz_afa and cert.netto_osszeg) else cert.netto_osszeg

    if cert.expense_id is not None:
        expense = db.get(Expense, cert.expense_id)
    else:
        expense = None

    kodok_szoveg = projektkod.projektkod or projektkod.project_nev or ""

    if expense is None:
        expense = Expense(
            megnevezes=f"TIG - {cert.ceg_neve or ''} - {kodok_szoveg}".strip(" -"),
            project_code_id=projektkod.id,
            employee_id=cert.employee_id,
            tipus="kulsos",
            netto=cert.netto_osszeg,
            brutto=brutto,
            hozzaadas_a_kiadasokhoz=True,
        )
        db.add(expense)
        db.flush()
        cert.expense_id = expense.id
    else:
        expense.netto = cert.netto_osszeg
        expense.brutto = brutto

    expense.kesz = True
    expense.fizetes_datuma = utalas
    if expense.fizetes_hatarideje is None and cert.fizetesi_hatarido is not None:
        expense.fizetes_hatarideje = cert.fizetesi_hatarido
    cert.szamla_kifizetve = True
    db.commit()
    db.refresh(cert)
    return PerformanceCertificateRead.model_validate(cert)
