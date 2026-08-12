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

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import tuple_
from sqlalchemy.orm import Session, selectinload

from app.api.routes.subcontractor_contracts import (
    csoport_szerzodes_kesz,
    eseti_szerzodesek_a_projekten,
    load_szerzodes_kornyezet,
    szerzodest_igenylo_emberek,
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
from app.models.project_szamlazo import ProjectSzamlazo
from app.schemas.finance import KifizetesIn
from app.schemas.performance_certificate import PerformanceCertificateRead
from app.services import document_storage, papir_fedettseg, papir_tetelek, papirozas_hatokor, szamlazo
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

    Kiesnek azok, akik PROJEKT KIADÁSKÉNT vannak elszámolva: az ő díjuk egy
    másik tételben szerepel, tehát nincs mit igazolni."""
    emberek = [e for e in project.crew if e.tipus != EmployeeType.BELSOS]
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
    projects = papirozas_hatokor.papirozando_projektek(
        db.query(Project)
        .filter(Project.diszpo == "Kiküldve")
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


def _lefedettek_info(project: Project, csoport: SzamlazoCsoport) -> list[TetelInfo]:
    """A fél által lefedett stábtagok ezen a projekten, TIG-tétel alakban - ez
    a piszkozat alapértelmezett tétellistája."""
    return [
        TetelInfo(
            project_id=project.id,
            project_nev=project.nev,
            projektkod=project.projektkod_szoveg,
            forgatas_datuma=project.forgatas_datuma,
            employee_id=tag.id,
            employee_nev=tag.full_name,
        )
        for tag in csoport.tagok
    ]


def _pending_info(
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
        lefedettek=_lefedettek_info(project, csoport),
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


@router.get("/{project_id}", response_model=PendingProjectDetail)
def get_pending_for_project(project_id: int, db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
    project = _get_project_or_404(db, project_id)
    keretszerzodesek, project_contracts, felulirasok = load_szerzodes_kornyezet(db, [project])
    # Csak azok a felek jelennek meg, akikről MÁR készíthető TIG - a többi
    # addig a szerződés-fázisban vár (lásd tig_keszitheto_csoportok).
    keszitheto = tig_keszitheto_csoportok(project, felulirasok, keretszerzodesek, project_contracts)
    tig_ready = bool(keszitheto)
    pending: list[tuple[SzamlazoCsoport, PerformanceCertificate | None]] = []
    if tig_ready:
        pending = _tig_pending_csoportok(project, keszitheto, _load_tig_lookup(db, {project.id}))
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
            _pending_info(project, csoport, existing, szerzodesek.get(csoport.kulcs))
            for csoport, existing in pending
        ],
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
        .filter(
            papir_fedettseg.fedi_a_projektet(
                PerformanceCertificate, PerformanceCertificateTetel, project_id
            )
        )
        .all()
    )
    return [PerformanceCertificateRead.model_validate(r) for r in rows]


def _validate_szamlazo(db: Session, project: Project, szamlazo_kulcs: str) -> SzamlazoCsoport:
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
    if not _tig_keszitheto(db, project, csoport):
        raise HTTPException(
            status_code=400,
            detail=f"{csoport.cimke()} szerződése még nincs meg ezen a projekten - TIG csak azután készíthető róla.",
        )
    return csoport


def _szamlazo_szuro(fel: SzamlazoFel):
    if fel.vallalkozas is not None:
        return PerformanceCertificate.vallalkozas_id == fel.vallalkozas.id
    return (PerformanceCertificate.employee_id == fel.employee.id) & PerformanceCertificate.vallalkozas_id.is_(None)


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

    projects = papirozas_hatokor.papirozando_projektek(
        db.query(Project)
        .filter(Project.diszpo == "Kiküldve")
        .options(selectinload(Project.crew), selectinload(Project.project_code))
        .all()
    )
    keretszerzodesek, project_contracts, felulirasok = load_szerzodes_kornyezet(db, projects)
    ember_fedettseg, _ = _load_tig_lookup(db, {p.id for p in projects})

    eredmeny: list[TetelInfo] = []
    for p in projects:
        # Csak az a kérdés, hogy EZ a fél rendben van-e a projekten - a többiek
        # hiányzó szerződése nem tartja vissza az ő tételeit.
        for csoport in tig_keszitheto_csoportok(p, felulirasok, keretszerzodesek, project_contracts):
            if csoport.kulcs != fel.kulcs:
                continue
            for tag in csoport.tagok:
                if (p.id, tag.id) in ember_fedettseg:
                    continue
                eredmeny.append(
                    TetelInfo(
                        project_id=p.id,
                        project_nev=p.nev,
                        projektkod=p.projektkod_szoveg,
                        forgatas_datuma=p.forgatas_datuma,
                        employee_id=tag.id,
                        employee_nev=tag.full_name,
                    )
                )
    eredmeny.sort(key=lambda t: (t.forgatas_datuma or date.min, t.project_id, t.employee_id), reverse=True)
    return eredmeny


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

    draft = PerformanceCertificate(
        project_id=project.id,
        employee_id=fel.employee.id if fel.employee else None,
        vallalkozas_id=fel.vallalkozas.id if fel.vallalkozas else None,
        allapot="Készítés alatt",
        ceg_neve=_szerzodesbol("ceg_neve", fel.ceg_neve),
        szekhely=_szerzodesbol("szekhely", fel.szekhely),
        adoszam=_szerzodesbol("adoszam", fel.adoszam),
        megbizas_targya=_szerzodesbol("megbizas_targya", fel.megbizas_targya),
        netto_osszeg=_szerzodesbol("netto_osszeg", None),
        plusz_afa=_szerzodesbol("plusz_afa", fel.plusz_afa),
        teljesites_szoveg=_szerzodesbol("teljesites_szoveg", _projekt_teljesites_szoveg(project)),
        email=fel.email,
    )
    db.add(draft)
    db.flush()
    # Alapból pontosan azt fedi, amiért ezen a projekten ő számláz - a
    # tételösszegeket is a szerződésről hozva, ahol ott már megadták.
    szerzodes_tetelei = (
        {(t.project_id, t.employee_id): t for t in szerzodes.tetelek} if szerzodes is not None else {}
    )
    for tag in csoport.tagok:
        forras = szerzodes_tetelei.get((project.id, tag.id))
        db.add(
            PerformanceCertificateTetel(
                certificate_id=draft.id,
                project_id=project.id,
                employee_id=tag.id,
                netto_osszeg=forras.netto_osszeg if forras is not None else None,
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
        html = _TIG_EMAIL_HTML.format(projektdatum=projektdatum or "–")
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
    vagy elfelejtődött. Az indok a bejegyzésen marad, és a listán is látszik."""
    indok = (payload.kihagyas_oka or "").strip()
    if not indok:
        raise HTTPException(status_code=400, detail="A kihagyás okát meg kell adni.")
    project = _get_project_or_404(db, project_id)
    csoport = _validate_szamlazo(db, project, szamlazo_kulcs)
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
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """A kiküldött TIG-hez tartozó (külső számlázási rendszerben kiállított)
    számla feltöltése - ez még nem jelenti a kifizetést, csak a dokumentum
    rögzítését (lásd /szamla-kifizetve a tényleges Pénzügy-be kerüléshez).

    Egy TIG-hez tetszőleges számú számla tölthető fel: minden hívás egy ÚJ
    számla-sort hoz létre (nem írja felül az előzőt) - a storage-kulcs ezért
    tartalmazza a számla id-jét is, különben a második feltöltés felülírná az
    első fájlját (lásd PerformanceCertificateInvoice modell-kommentje)."""
    cert = _get_sent_certificate_or_404(db, project_id, szamlazo_kulcs)
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
    megtörtént, de máshol van elszámolva (lásd KifizetesIn)."""
    cert = _get_sent_certificate_or_404(db, project_id, szamlazo_kulcs)
    if not cert.invoices:
        raise HTTPException(status_code=400, detail="Előbb töltsd fel a számlát.")

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
    expense.fizetes_datuma = date.today()
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
