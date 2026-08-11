"""Alvállalkozók szerződése - projektenként összegyűjti, hogy a diszpó kiküldése
után kik vettek részt a projekten, akik SEM nem belsősök (Employee.tipus ==
"belsos"), SEM nincs már keretszerződésük (Contract, tipus="alvallalkozoi",
project_id=NULL, employee_id=ő) - nekik kell egyedi (eseti, projekthez kötött)
megbízási szerződést generálni és kiküldeni, vagy kihagyni (ha nem lesz
szerződés az adott projekttel).

Az eseti szerződés két lépésben készül, mint az eredeti (Notion-alapú) rendszer
"Adatok átemelése" -> "Szerződés készítése és küldése" gombpárosa: a "Mentés"
(save) csak elmenti a kitöltött adatokat egy "Készítés alatt" állapotú Contract
sorba (nincs PDF-generálás/email-küldés), hogy a felhasználó bármikor bezárhassa
és később visszatérhessen hozzá; a "Generálás és küldés" ugyanezt menti el, majd
rögtön le is generálja és ki is küldi. A "Kihagyás" bármikor lezárja az adott
embert erre a projektre nézve szerződés nélkül.

A generálás+küldés a meglévő diszpó/szerződés-küldő motort (gdoc_template.py +
google_email.py) használja, a csatolt 'kulsos-eseti-szerzodes' Railway program
mezőkészletével (lásd hu_number_words.py a nettó összeg szöveges kiírásához)."""

from __future__ import annotations

import os
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import or_, tuple_
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user, require_page_action
from app.models.contract import (
    Contract,
    ContractTetel,
    ContractType,
    keretszerzodes_ervenyes,
    megkotott_keretszerzodes,
)
from app.models.employee import Employee, EmployeeType
from app.models.performance_certificate import PerformanceCertificate, PerformanceCertificateTetel
from app.models.project import Project
from app.models.project_szamlazo import ProjectSzamlazo
from app.schemas.contract import ContractRead
from app.services import document_storage, papir_fedettseg, papir_tetelek, szamlazo
from app.services.gdoc_template import gdoc_fill_and_export_pdf
from app.services.google_email import send_message
from app.services.hu_number_words import szam_betukkel
from app.services.szamlazo import SzamlazoCsoport, SzamlazoFel

router = APIRouter(prefix="/alvallalkozoi-szerzodesek", tags=["subcontractor-contracts"])

# A művelet a Utókövetés oldalon (és a projekt adatlapján) érhető el - külön
# menüpontja nincs, ezért a jogosultsága is az Utókövetés oldalé.
PAGE = "/utokovetes"

TERMINAL_STATUSES = {"Kiküldve", "Kihagyva"}

# A csatolt program email-sablonjának 1:1 portja (aláírás: "ADMINISZTRÁCIÓ",
# nem "GYÁRTÁS" - lásd services/dispo.py _SIGNATURE_HTML, ami a diszpóhoz
# tartozik, ide ezt a külön, adminisztrációs változatot használjuk).
_CONTRACT_EMAIL_HTML = """\
<p>Kedves Címzett,</p>
<p>
  Levelemhez csatoltan küldöm a tárgyban említett projektre vonatkozó szerződést.<br>
  Kérjük a projekt további dokumentációjához (teljesítés igazolása, számlázás és kifizetés)
  aláírva és/vagy pecsételve küldd vissza számunkra a csatolt dokumentumot, válasz e-mailben.
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


def szerzodes_kulcsa(c: Contract) -> str | None:
    """Melyik SZÁMLÁZÓ FÉLHEZ tartozik ez a szerződés (lásd
    services/szamlazo.py kulcs)? None, ha egyikhez sem (pl. ügyfél-szerződés)."""
    if c.vallalkozas_id is not None:
        return f"v{c.vallalkozas_id}"
    if c.employee_id is not None:
        return f"e{c.employee_id}"
    return None


def _load_contract_lookup(
    db: Session, employee_ids: set[int], vallalkozas_ids: set[int] | None = None
) -> tuple[dict[str, list[Contract]], dict[tuple[int, str], Contract]]:
    """Számlázó felenként a KERETSZERZŐDÉSEI, és (projekt, számlázó fél)
    szerint az eseti szerződések.

    A kulcs azért szöveg ("e12" / "v3"), mert a szerződés másik oldala lehet
    ember és cég is: az embereket küldő vállalkozással kötött keretszerződés az
    összes tőle jövő embert fedi (lásd services/szamlazo.py).

    Keretszerződésből több is lehet egy félnél (idővel újat kötünk vele), ezért
    nem egy azonosító-halmazt adunk vissza, hanem a szerződéseket magukat: a
    mentesség a projekt NAPJÁTÓL függ, azt pedig csak a hívó tudja (lásd
    models/contract.py keretszerzodes_ervenyes)."""
    vallalkozas_ids = vallalkozas_ids or set()
    if not employee_ids and not vallalkozas_ids:
        return {}, {}
    feltetelek = []
    if employee_ids:
        feltetelek.append(Contract.employee_id.in_(employee_ids))
    if vallalkozas_ids:
        feltetelek.append(Contract.vallalkozas_id.in_(vallalkozas_ids))
    contracts = (
        db.query(Contract)
        .options(selectinload(Contract.idoszakok), selectinload(Contract.tetelek))
        .filter(Contract.tipus == ContractType.ALVALLALKOZOI, or_(*feltetelek))
        .all()
    )
    # CSAK a valódi keretszerződés mentesít az eseti szerződés alól: a
    # Notion-importból származó, puszta cégadat-sorok nem (lásd
    # models/contract.py megkotott_keretszerzodes) - különben a rendszer
    # mindenkiről azt hinné, hogy már van szerződése.
    keretszerzodesek: dict[str, list[Contract]] = {}
    project_contracts: dict[tuple[int, str], Contract] = {}
    for c in contracts:
        kulcs = szerzodes_kulcsa(c)
        if kulcs is None:
            continue
        if megkotott_keretszerzodes(c):
            keretszerzodesek.setdefault(kulcs, []).append(c)
            continue
        # Egy eseti szerződés TÖBB projektet is fedhet (három nap forgatás egy
        # szerződéssel) - a lefedettséget a tételei hordozzák, nem a saját
        # project_id-je. Tétel nélküli (import/régi) sornál az utóbbi marad,
        # lásd services/papir_fedettseg.py.
        erintett = {t.project_id for t in c.tetelek} or (
            {c.project_id} if c.project_id is not None else set()
        )
        for project_id in erintett:
            project_contracts[(project_id, kulcs)] = c
    return keretszerzodesek, project_contracts


def _mentesul_keretszerzodessel(keretszerzodesek: list[Contract], nap: date | None) -> bool:
    """Fedi-e valamelyik keretszerződése a projekt napját?

    Dátum nélküli projektnél a MAI napot nézzük: ilyenkor az a kérdés, hogy
    él-e most keretszerződése - ennél többet a projektről nem tudunk."""
    return any(keretszerzodes_ervenyes(c, nap or date.today()) for c in keretszerzodesek)


def szerzodest_igenylo_emberek(project: Project) -> list[Employee]:
    """Akiknek a munkájáról egyáltalán szerződés kell: a nem belsős stáb.

    Hogy kinek a NEVÉRE megy a papír, azt ebből a listából a számlázó felek
    csoportosítása dönti el (lásd _szamlazo_csoportok)."""
    return [e for e in project.crew if e.tipus != EmployeeType.BELSOS]


def _szamlazo_csoportok(
    project: Project, felulirasok: dict[tuple[int, int], ProjectSzamlazo]
) -> list[SzamlazoCsoport]:
    return szamlazo.csoportok(project, szerzodest_igenylo_emberek(project), felulirasok)


def csoport_szerzodes_kesz(
    project: Project,
    csoport: SzamlazoCsoport,
    keretszerzodesek: dict[str, list[Contract]],
    project_contracts: dict[tuple[int, str], Contract],
) -> bool:
    """Megvan-e MÁR ENNEK a félnek a szerződéses háttere ezen a projekten?

    Kétféleképpen lehet meg: vagy keretszerződés mentesíti a forgatás napján
    (akkor eseti szerződés sem kell tőle), vagy az eseti szerződése lezárult
    (kiküldve vagy kihagyva).

    Szándékosan FELENKÉNT dől el, nem projektszinten: aki már aláírt - vagy
    akinek álló keretszerződése van -, arról azonnal készülhet a teljesítési
    igazolás, nem kell megvárnia a projekt összes többi szereplőjét. Egy
    lassan válaszoló stábtag korábban az egész projekt TIG-fázisát blokkolta
    (lásd performance_certificates.py)."""
    # A keretszerződés csak akkor mentesít, ha a FORGATÁS NAPJÁN élt: aki két
    # időszak közé eső projekten dolgozott, attól eseti szerződés kell.
    if _mentesul_keretszerzodessel(keretszerzodesek.get(csoport.kulcs, []), project.forgatas_datuma):
        return True
    existing = project_contracts.get((project.id, csoport.kulcs))
    return existing is not None and existing.szerzodes_allapota in TERMINAL_STATUSES


def _pending_csoportok(
    project: Project,
    keretszerzodesek: dict[str, list[Contract]],
    project_contracts: dict[tuple[int, str], Contract],
    felulirasok: dict[tuple[int, int], ProjectSzamlazo],
) -> list[tuple[SzamlazoCsoport, Contract | None]]:
    """Kiktől van még hátra eseti szerződés ezen a projekten?

    A lista SZÁMLÁZÓ FELENKÉNT egy sor, nem emberenként: ha egy projekten két
    stábtag munkáját ugyanaz a fél számlázza, egyetlen szerződés kell, nem
    kettő (lásd services/szamlazo.py)."""
    return [
        (csoport, project_contracts.get((project.id, csoport.kulcs)))
        for csoport in _szamlazo_csoportok(project, felulirasok)
        if not csoport_szerzodes_kesz(project, csoport, keretszerzodesek, project_contracts)
    ]


class PendingProjectSummary(BaseModel):
    project_id: int
    project_nev: str | None
    forgatas_datuma: date | None
    pending_count: int


def load_szerzodes_kornyezet(
    db: Session, projects: list[Project]
) -> tuple[
    dict[str, list[Contract]],
    dict[tuple[int, str], Contract],
    dict[tuple[int, int], ProjectSzamlazo],
]:
    """A szerződés-fázis eldöntéséhez kellő HÁROM index, egyszerre az összes
    megadott projektre.

    Enélkül projektenként külön lekérdezés futna (számlázó felülírások,
    keretszerződések, eseti szerződések) - száz projektnél ez már érezhető
    lassulás minden listaoldal-betöltésnél."""
    felulirasok = szamlazo.load_felulirasok(db, {p.id for p in projects})
    employee_ids: set[int] = set()
    vallalkozas_ids: set[int] = set()
    for p in projects:
        for csoport in _szamlazo_csoportok(p, felulirasok):
            if csoport.fel.vallalkozas is not None:
                vallalkozas_ids.add(csoport.fel.vallalkozas.id)
            elif csoport.fel.employee is not None:
                employee_ids.add(csoport.fel.employee.id)
    keretszerzodesek, project_contracts = _load_contract_lookup(db, employee_ids, vallalkozas_ids)
    return keretszerzodesek, project_contracts, felulirasok


@router.get("", response_model=list[PendingProjectSummary])
def list_pending_projects(db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
    projects = (
        db.query(Project)
        .filter(Project.diszpo == "Kiküldve")
        .options(selectinload(Project.crew))
        .all()
    )
    keretszerzodesek, project_contracts, felulirasok = load_szerzodes_kornyezet(db, projects)

    result: list[PendingProjectSummary] = []
    for p in projects:
        pending = _pending_csoportok(p, keretszerzodesek, project_contracts, felulirasok)
        if pending:
            result.append(
                PendingProjectSummary(
                    project_id=p.id, project_nev=p.nev, forgatas_datuma=p.forgatas_datuma, pending_count=len(pending)
                )
            )
    return result


class TetelInfo(BaseModel):
    """Egy szerződés-tétel: kinek a munkájára, melyik projekten."""

    project_id: int
    project_nev: str | None = None
    projektkod: str | None = None
    forgatas_datuma: date | None = None
    employee_id: int
    employee_nev: str | None = None
    netto_osszeg: float | None = None
    megnevezes: str | None = None


class DraftInfo(BaseModel):
    szerzodes_allapota: str | None
    ceg_neve: str | None
    szekhely: str | None
    adoszam: str | None
    vallalkozas_kepviseloje: str | None
    vallalkozas_nyilvantartasi_szam: str | None
    megbizas_targya: str | None
    netto_osszeg: float | None
    #: A teljesítés ideje SZABAD SZÖVEG (a régi, dátumpáros bejegyzéseknél a
    #: két dátumból képzett szöveg - lásd _teljesites_szovege).
    teljesites_szoveg: str | None
    keltezes: date | None
    plusz_afa: bool | None
    tetelek: list[TetelInfo] = []


class PendingEmployeeInfo(BaseModel):
    """Egy SZÁMLÁZÓ FÉL, akitől még hátra van a szerződés ezen a projekten.

    Az `id` a régi felület kedvéért maradt az ember azonosítója (cégnél 0) - az
    új hívások a `szamlazo` kulcsot használják (lásd services/szamlazo.py)."""

    id: int
    szamlazo: str
    full_name: str
    #: "Ladányi Máté (Balla Berci helyett is)" - ez megy a felületre.
    cimke: str
    #: Kiknek a munkáját fedi ez az egy szerződés EZEN a projekten - egyben a
    #: piszkozat alapértelmezett tétellistája.
    lefedettek: list[TetelInfo] = []
    vallalkozas_id: int | None = None
    email: str | None
    ceg_neve: str | None
    szekhely: str | None
    adoszam: str | None
    kepviselo: str | None
    nyilvantartasi_szam: str | None
    megbizas_targya: str | None
    plusz_afa: bool | None
    draft: DraftInfo | None


class PendingProjectDetail(BaseModel):
    project_id: int
    project_nev: str | None
    forgatas_datuma: date | None
    forgatas_datuma_vege: date | None
    #: A teljesítés idejének ELŐTÖLTÉSE a forgatás dátumából - a mező szabad
    #: szöveg, tehát bármire átírható (lásd _projekt_teljesites_szoveg).
    teljesites_szoveg_alap: str = ""
    pending: list[PendingEmployeeInfo]


def _projekt_teljesites_szoveg(project: Project) -> str:
    """Előtöltés a projekt forgatási dátumából - a teljesítés jellemzően a
    forgatás ideje. Ugyanaz a szabály, mint a TIG-nél (lásd
    routes/performance_certificates.py)."""
    start = project.forgatas_datuma
    if not start:
        return ""
    end = project.forgatas_datuma_vege
    if end and end != start:
        return f"{start.strftime('%Y.%m.%d.')} - {end.strftime('%Y.%m.%d.')}"
    return start.strftime("%Y.%m.%d.")


def _get_project_or_404(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Projekt nem található")
    return project


def _teljesites_szovege(c: Contract) -> str | None:
    """A teljesítés ideje, ahogy a szerződésre kerül.

    Elsődlegesen a szabad szöveges mező (ezt írja be a felhasználó), és csak
    ha az üres - a régi, dátumpárral rögzített szerződéseknél -, akkor
    képezzük a két dátumból, ugyanabban a formában, ahogy eddig."""
    szoveg = (c.teljesites_szoveg or "").strip()
    if szoveg:
        return szoveg
    if c.teljesites_vege and c.teljesites_vege != c.teljesites_kezdete:
        kezdet = c.teljesites_kezdete.strftime("%Y.%m.%d.") if c.teljesites_kezdete else ""
        return f"{kezdet} - {c.teljesites_vege.strftime('%Y.%m.%d.')}"
    if c.teljesites_kezdete:
        return c.teljesites_kezdete.strftime("%Y.%m.%d.")
    return None


def _tetel_info(t: ContractTetel) -> TetelInfo:
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


def _draft_info(c: Contract | None) -> DraftInfo | None:
    if c is None:
        return None
    return DraftInfo(
        szerzodes_allapota=c.szerzodes_allapota,
        ceg_neve=c.ceg_neve,
        szekhely=c.szekhely,
        adoszam=c.adoszam,
        vallalkozas_kepviseloje=c.vallalkozas_kepviseloje,
        vallalkozas_nyilvantartasi_szam=c.vallalkozas_nyilvantartasi_szam,
        megbizas_targya=c.megbizas_targya,
        netto_osszeg=c.netto_osszeg,
        teljesites_szoveg=_teljesites_szovege(c),
        keltezes=c.keltezes,
        plusz_afa=c.plusz_afa,
        tetelek=[_tetel_info(t) for t in c.tetelek],
    )


@router.get("/{project_id}", response_model=PendingProjectDetail)
def get_pending_for_project(
    project_id: int, db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)
):
    project = _get_project_or_404(db, project_id)
    keretszerzodesek, project_contracts, felulirasok = load_szerzodes_kornyezet(db, [project])
    pending = _pending_csoportok(project, keretszerzodesek, project_contracts, felulirasok)
    return PendingProjectDetail(
        project_id=project.id,
        project_nev=project.nev,
        forgatas_datuma=project.forgatas_datuma,
        forgatas_datuma_vege=project.forgatas_datuma_vege,
        teljesites_szoveg_alap=_projekt_teljesites_szoveg(project),
        pending=[pending_info(project, csoport, existing) for csoport, existing in pending],
    )


def _lefedettek_info(project: Project, csoport: SzamlazoCsoport) -> list[TetelInfo]:
    """A fél által lefedett stábtagok ezen a projekten, tétel alakban."""
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


def pending_info(project: Project, csoport: SzamlazoCsoport, existing: Contract | None) -> PendingEmployeeInfo:
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
        kepviselo=fel.kepviselo,
        nyilvantartasi_szam=fel.nyilvantartasi_szam,
        megbizas_targya=fel.megbizas_targya,
        plusz_afa=fel.plusz_afa,
        draft=_draft_info(existing),
    )


class ElkeszultSzerzodes(BaseModel):
    """Egy projekthez már elkészült (vagy kihagyott) eseti szerződés - a
    felületen ez mutatja meg, hogy kinek van kész papírja, és hol van."""

    contract_id: int
    #: Cég nevére szóló szerződésnél nincs ember - ilyenkor 0.
    employee_id: int
    szamlazo: str
    full_name: str
    szerzodes_allapota: str | None = None
    netto_osszeg: float | None = None
    keltezes: date | None = None
    #: A generált dokumentum linkje (Google Docs), ha a küldés lefutott.
    szerzodes_file_url: str | None = None


@router.get("/{project_id}/{szamlazo_kulcs}/nyitott-tetelek", response_model=list[TetelInfo])
def list_nyitott_tetelek(
    project_id: int,
    szamlazo_kulcs: str,
    db: Session = Depends(get_db),
    _user: Employee = Depends(get_current_user),
):
    """Mi mindent tehetünk MÉG rá erre a szerződésre?

    A "három nap forgatás egy szerződéssel" eset felülete: felsorolja az összes
    olyan (projekt, ember) munkát az ÖSSZES diszpózott projektről, amit ez a fél
    számláz, és amiről még nincs eseti szerződés. A felhasználó ebből pipálja
    ki, mi kerüljön erre az egy papírra - ugyanaz a logika, mint a TIG-nél
    (lásd routes/performance_certificates.py list_nyitott_tetelek), hogy az
    összevont TIG mellé összevont szerződés is tartozhasson."""
    _get_project_or_404(db, project_id)
    fel = szamlazo.feloldas(db, szamlazo_kulcs)
    if fel is None:
        raise HTTPException(status_code=404, detail="A számlázó fél nem található")

    projects = (
        db.query(Project)
        .filter(Project.diszpo == "Kiküldve")
        .options(selectinload(Project.crew), selectinload(Project.project_code))
        .all()
    )
    keretszerzodesek, project_contracts, felulirasok = load_szerzodes_kornyezet(db, projects)

    eredmeny: list[TetelInfo] = []
    for p in projects:
        # Ahol keretszerződés fedi, ott nincs mit szerződni.
        if _mentesul_keretszerzodessel(keretszerzodesek.get(fel.kulcs, []), p.forgatas_datuma):
            continue
        meglevo = project_contracts.get((p.id, fel.kulcs))
        # A már véglegesített (kiküldött/kihagyott) szerződést nem bontjuk meg.
        if meglevo is not None and meglevo.szerzodes_allapota in TERMINAL_STATUSES:
            continue
        for csoport in _szamlazo_csoportok(p, felulirasok):
            if csoport.kulcs != fel.kulcs:
                continue
            eredmeny.extend(_lefedettek_info(p, csoport))
    eredmeny.sort(key=lambda t: (t.forgatas_datuma or date.min, t.project_id, t.employee_id), reverse=True)
    return eredmeny


@router.get("/{project_id}/all", response_model=list[ElkeszultSzerzodes])
def list_all_for_project(
    project_id: int, db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)
):
    """Az adott projekt ÖSSZES eseti szerződés-bejegyzése, bármilyen
    állapotban.

    A függő lista (get_pending_for_project) szándékosan csak azokat adja
    vissza, akikkel még van teendő - a kiküldött szerződés onnan eltűnik.
    Ezért kell ez a végpont: az Utókövetésen az elkészült szerződésnek is
    látszania kell, a generált dokumentumra mutató linkkel együtt."""
    _get_project_or_404(db, project_id)
    rows = (
        db.query(Contract)
        .options(selectinload(Contract.employee), selectinload(Contract.vallalkozas))
        .filter(Contract.project_id == project_id, Contract.tipus == ContractType.ALVALLALKOZOI)
        .all()
    )
    eredmeny: list[ElkeszultSzerzodes] = []
    for c in rows:
        kulcs = szerzodes_kulcsa(c)
        if kulcs is None:
            continue
        if c.vallalkozas is not None:
            nev = c.vallalkozas.nev
        elif c.employee is not None:
            nev = c.employee.full_name
        else:
            nev = c.ceg_neve or kulcs
        eredmeny.append(
            ElkeszultSzerzodes(
                contract_id=c.id,
                employee_id=c.employee_id or 0,
                szamlazo=kulcs,
                full_name=nev,
                szerzodes_allapota=c.szerzodes_allapota,
                netto_osszeg=float(c.netto_osszeg) if c.netto_osszeg is not None else None,
                keltezes=c.keltezes,
                szerzodes_file_url=c.szerzodes_file_url,
            )
        )
    return eredmeny


def _validate_szamlazo(db: Session, project: Project, szamlazo_kulcs: str) -> SzamlazoCsoport:
    """Feloldja a számlázó felet, és ellenőrzi, hogy tőle egyáltalán kell-e
    eseti szerződés ezen a projekten.

    A fél NEM feltétlenül stábtag: aki más munkáját számlázza, maga lehet, hogy
    ott sem volt a forgatáson. A követelmény az, hogy legalább egy stábtag
    munkája hozzá tartozzon."""
    fel = szamlazo.feloldas(db, szamlazo_kulcs)
    if fel is None:
        raise HTTPException(status_code=404, detail="A számlázó fél nem található")
    felulirasok = szamlazo.load_felulirasok(db, {project.id})
    csoport = next((cs for cs in _szamlazo_csoportok(project, felulirasok) if cs.kulcs == fel.kulcs), None)
    if csoport is None:
        if fel.employee is not None and fel.employee.tipus == EmployeeType.BELSOS:
            raise HTTPException(status_code=400, detail="Belsős munkatársnak nem kell eseti szerződés.")
        raise HTTPException(
            status_code=400,
            detail="Ezen a projekten senkinek a munkáját nem ez a fél számlázza.",
        )
    # A keretszerződés csak akkor váltja ki az esetit, ha a FORGATÁS NAPJÁN
    # élt - egy lejárt (vagy még meg sem kötött) keretszerződés nem mentesít.
    keretszerzodesek, _ = _load_contract_lookup(
        db,
        {fel.employee.id} if fel.employee else set(),
        {fel.vallalkozas.id} if fel.vallalkozas else set(),
    )
    if _mentesul_keretszerzodessel(keretszerzodesek.get(fel.kulcs, []), project.forgatas_datuma):
        raise HTTPException(
            status_code=400, detail="Ennek a félnek már van keretszerződése, nincs szükség eseti szerződésre."
        )
    return csoport


def _szamlazo_szuro(fel: SzamlazoFel):
    """A szerződés a fél OLDALÁRA szűr: cégnél a vallalkozas_id-ra, embernél az
    employee_id-ra ÉS arra, hogy ne céghez tartozzon (különben egy céges sor
    összekeveredne a cég képviselőjének saját szerződésével)."""
    if fel.vallalkozas is not None:
        return Contract.vallalkozas_id == fel.vallalkozas.id
    return (Contract.employee_id == fel.employee.id) & Contract.vallalkozas_id.is_(None)


def _get_or_create_draft(db: Session, project: Project, csoport: SzamlazoCsoport) -> Contract:
    """A fél szerződés-piszkozata ezen a projekten - vagy a meglévő, vagy egy
    új, a projekten hozzá tartozó stábtagok tételeivel feltöltve.

    A meglévőt a TÉTELEIN keresztül is keressük: a szerződés indulhatott egy
    másik projektről is, ha három nap forgatás egy szerződéssel megy."""
    fel = csoport.fel
    existing = (
        db.query(Contract)
        .filter(
            Contract.tipus == ContractType.ALVALLALKOZOI,
            Contract.keretszerzodes.is_(False),
            _szamlazo_szuro(fel),
            papir_fedettseg.fedi_a_projektet(Contract, ContractTetel, project.id),
        )
        .first()
    )
    if existing is not None:
        if existing.szerzodes_allapota in TERMINAL_STATUSES:
            raise HTTPException(
                status_code=400,
                detail="Ehhez a projekthez és félhez már véglegesített szerződés-bejegyzés tartozik (kiküldve vagy kihagyva).",
            )
        return existing
    draft = Contract(
        tipus=ContractType.ALVALLALKOZOI,
        project_id=project.id,
        employee_id=fel.employee.id if fel.employee else None,
        vallalkozas_id=fel.vallalkozas.id if fel.vallalkozas else None,
        szerzodes_allapota="Készítés alatt",
        ceg_neve=fel.ceg_neve,
        szekhely=fel.szekhely,
        adoszam=fel.adoszam,
        vallalkozas_kepviseloje=fel.kepviselo,
        vallalkozas_nyilvantartasi_szam=fel.nyilvantartasi_szam,
        megbizas_targya=fel.megbizas_targya,
        plusz_afa=fel.plusz_afa,
        email=fel.email,
    )
    db.add(draft)
    db.flush()
    # Alapból pontosan azt fedi, amiért ezen a projekten ő számláz.
    for tag in csoport.tagok:
        db.add(ContractTetel(contract_id=draft.id, project_id=project.id, employee_id=tag.id))
    db.flush()
    return draft


class TetelIn(BaseModel):
    project_id: int
    employee_id: int
    #: Opcionális: összevont szerződésnél nem mindig tudható, melyik nap
    #: mennyibe került. A szerződés fejösszege az igazság.
    netto_osszeg: float | None = None
    megnevezes: str | None = None


def _apply_tetelek(db: Session, draft: Contract, fel: SzamlazoFel, tetelek: list[TetelIn] | None) -> None:
    """A szerződés tételeinek cseréje - ugyanazokkal az ellenőrzésekkel, mint a
    TIG-nél (lásd routes/performance_certificates.py _apply_tetelek):

    1. egy (projekt, ember) munkájáról csak EGY eseti szerződés szólhat;
    2. csak olyan tétel kerülhet rá, aminél tényleg ez a fél a számlázó azon a
       projekten;
    3. és csak olyan projekt, ahol a félnek egyáltalán kell szerződés (nem
       fedi keretszerződés)."""
    if tetelek is None:
        return
    if not tetelek:
        raise HTTPException(status_code=400, detail="A szerződésnek legalább egy tételt tartalmaznia kell.")

    parok = {(t.project_id, t.employee_id) for t in tetelek}
    if len(parok) != len(tetelek):
        raise HTTPException(status_code=400, detail="Ugyanaz az ember ugyanazon a projekten kétszer szerepel.")

    projektek = {p.id: p for p in db.query(Project).filter(Project.id.in_({t.project_id for t in tetelek})).all()}
    felulirasok = szamlazo.load_felulirasok(db, set(projektek))
    keretszerzodesek, _ = _load_contract_lookup(
        db,
        {fel.employee.id} if fel.employee else set(),
        {fel.vallalkozas.id} if fel.vallalkozas else set(),
    )
    for t in tetelek:
        projekt = projektek.get(t.project_id)
        if projekt is None:
            raise HTTPException(status_code=404, detail=f"A(z) #{t.project_id} projekt nem található.")
        ember = next((e for e in szerzodest_igenylo_emberek(projekt) if e.id == t.employee_id), None)
        if ember is None:
            raise HTTPException(
                status_code=400,
                detail=f"A(z) #{t.employee_id} munkatárs nincs a(z) „{projekt.nev}” projekt (nem belsős) stábjában.",
            )
        if szamlazo.szamlazo_fele(projekt, ember, felulirasok).kulcs != fel.kulcs:
            raise HTTPException(
                status_code=400,
                detail=f"„{projekt.nev}” projekten {ember.full_name} munkáját nem ez a fél számlázza.",
            )
        if _mentesul_keretszerzodessel(keretszerzodesek.get(fel.kulcs, []), projekt.forgatas_datuma):
            raise HTTPException(
                status_code=400,
                detail=f"„{projekt.nev}” projekten keretszerződés fedi ezt a felet - oda nem kell eseti szerződés.",
            )

    utkozes = (
        db.query(ContractTetel)
        .options(selectinload(ContractTetel.employee))
        .filter(
            ContractTetel.contract_id != draft.id,
            tuple_(ContractTetel.project_id, ContractTetel.employee_id).in_(parok),
        )
        .first()
    )
    if utkozes is not None:
        nev = utkozes.employee.full_name if utkozes.employee else f"#{utkozes.employee_id}"
        raise HTTPException(
            status_code=400,
            detail=f"{nev} munkájáról ezen a projekten már szól egy másik szerződés - egy munkára csak egy szerződés köthető.",
        )
    # A tétel nélküli (import/régi) szerződéseket a saját mezőik alapján
    # nézzük - lásd services/papir_fedettseg.py.
    regi = (
        db.query(Contract)
        .options(selectinload(Contract.employee))
        .filter(
            Contract.id != draft.id,
            Contract.tipus == ContractType.ALVALLALKOZOI,
            Contract.keretszerzodes.is_(False),
            papir_fedettseg.tetel_nelkuli(Contract),
            tuple_(Contract.project_id, Contract.employee_id).in_(parok),
        )
        .first()
    )
    if regi is not None:
        nev = regi.employee.full_name if regi.employee else f"#{regi.employee_id}"
        raise HTTPException(
            status_code=400,
            detail=f"{nev} munkájáról ezen a projekten már szól egy másik szerződés - egy munkára csak egy szerződés köthető.",
        )

    draft.tetelek.clear()
    db.flush()
    for t in tetelek:
        draft.tetelek.append(
            ContractTetel(
                project_id=t.project_id,
                employee_id=t.employee_id,
                netto_osszeg=t.netto_osszeg,
                megnevezes=t.megnevezes,
            )
        )
    db.flush()


class ContractDraftIn(BaseModel):
    #: Mire szól a szerződés. None = maradjon, ami van (a piszkozat
    #: létrehozásakor az adott projekten a félhez tartozó stábtagok).
    tetelek: list[TetelIn] | None = None
    ceg_neve: str | None = None
    szekhely: str | None = None
    adoszam: str | None = None
    vallalkozas_kepviseloje: str | None = None
    vallalkozas_nyilvantartasi_szam: str | None = None
    megbizas_targya: str | None = None
    netto_osszeg: float | None = None
    teljesites_szoveg: str | None = None
    keltezes: date | None = None
    plusz_afa: bool | None = None


_DRAFT_FIELDS = (
    "ceg_neve",
    "szekhely",
    "adoszam",
    "vallalkozas_kepviseloje",
    "vallalkozas_nyilvantartasi_szam",
    "megbizas_targya",
    "netto_osszeg",
    "teljesites_szoveg",
    "keltezes",
    "plusz_afa",
)


def _apply_draft_fields(draft: Contract, payload: ContractDraftIn) -> None:
    for field in _DRAFT_FIELDS:
        value = getattr(payload, field)
        if value is not None:
            setattr(draft, field, value)


@router.post("/{project_id}/{szamlazo_kulcs}/save", response_model=ContractRead)
def save_draft(
    project_id: int,
    szamlazo_kulcs: str,
    payload: ContractDraftIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "create")),
):
    """Elmenti a kitöltött adatokat 'Készítés alatt' állapotban, PDF-generálás
    és email-küldés nélkül - így be lehet zárni a projektet, dolgozni valaki
    máson, és később visszatérni ehhez a félhez a mentett adatokkal.

    A `szamlazo_kulcs` ember ("e12", vagy csak "12") vagy cég ("v3") is lehet -
    lásd services/szamlazo.py."""
    project = _get_project_or_404(db, project_id)
    csoport = _validate_szamlazo(db, project, szamlazo_kulcs)
    draft = _get_or_create_draft(db, project, csoport)
    _apply_draft_fields(draft, payload)
    _apply_tetelek(db, draft, csoport.fel, payload.tetelek)
    db.commit()
    db.refresh(draft)
    return ContractRead.model_validate(draft)


@router.post("/{project_id}/{szamlazo_kulcs}/generate-and-send", response_model=ContractRead)
def generate_and_send(
    project_id: int,
    szamlazo_kulcs: str,
    payload: ContractDraftIn,
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

    # A papírra a TÉTELEK kerülnek: ha a szerződés több munkát fed (három nap
    # forgatás egy szerződéssel, vagy két ember munkája egy fél nevében), a
    # dokumentumból is ki kell derülnie, mit fed - lásd services/papir_tetelek.py.
    # Egytételes szerződésnél minden pontosan úgy néz ki, mint eddig.
    tetelek = list(draft.tetelek)
    teljesites_str = papir_tetelek.teljesites_szovege(_teljesites_szovege(draft), tetelek)

    # float(): a Numeric oszlop az adatbázisból Decimal-ként jön vissza (csak a
    # most beírt érték float), a Decimal * float pedig TypeError.
    brutto_osszeg = round(float(draft.netto_osszeg) * 1.27, 2) if draft.plusz_afa else draft.netto_osszeg

    doc_link = None
    pdf_bytes = None
    base_name = f"{project.forgatas_datuma or ''}_{project.nev or ''}_{fel.nev}_szerződés"
    try:
        if settings.gdoc_alvallalkozoi_szerzodes_template_id:
            fields = {
                "nev": draft.ceg_neve or fel.nev,
                "hely": draft.szekhely or "",
                "adoszam": draft.adoszam or "",
                "targy": papir_tetelek.targy_szovege(draft.megbizas_targya, tetelek),
                "tido": teljesites_str,
                "netto": f"{draft.netto_osszeg:,.0f}".replace(",", " "),
                "kelt": keltezes.strftime("%Y.%m.%d."),
                "afa": "+ ÁFA" if draft.plusz_afa else "",
                "brutto": f"{brutto_osszeg:,.0f}".replace(",", " "),
                "nettoki": szam_betukkel(draft.netto_osszeg),
                "nyilvszam": draft.vallalkozas_nyilvantartasi_szam or "",
                "kepvis": draft.vallalkozas_kepviseloje or "",
                "projektnev": papir_tetelek.projektnevek_szovege(tetelek, project.nev or ""),
            }
            pdf_bytes, new_doc_id = gdoc_fill_and_export_pdf(
                template_file_id=settings.gdoc_alvallalkozoi_szerzodes_template_id,
                base_name=base_name,
                fields=fields,
                output_folder_id=settings.gdoc_output_folder_id or settings.drive_folder_id or None,
            )
            doc_link = f"https://docs.google.com/document/d/{new_doc_id}/edit"

        send_message([cimzett], base_name, _CONTRACT_EMAIL_HTML, pdf_bytes=pdf_bytes, pdf_filename="szerzodes.pdf")
    except RuntimeError as exc:
        # A kitöltött adatokat akkor is mentsük el, ha a küldés elhasal (pl.
        # hiányzó Google hitelesítő adat) - ne vesszen el az eddigi munka.
        db.commit()
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    draft.szerzodes_allapota = "Kiküldve"
    draft.szerzodes_file_url = doc_link
    db.commit()
    db.refresh(draft)
    return ContractRead.model_validate(draft)


@router.post("/{project_id}/{szamlazo_kulcs}/sajat-fajl", response_model=ContractRead)
async def upload_sajat_szerzodes(
    project_id: int,
    szamlazo_kulcs: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "create")),
):
    """A KIKÜLDÉS KIHAGYÁSA: egy már meglévő szerződés feltöltése.

    Van, amikor a papír nem itt készül - máshol megírt, vagy már aláírva
    visszakapott szerződés. Ilyenkor nincs mit generálni és nincs kinek
    kiküldeni, csak rögzíteni: a fájl a tárhelyünkre kerül, a bejegyzés
    `szerzodes_file_url`-je erre mutat, az állapot pedig "Kiküldve" lesz -
    ugyanoda jut a szerződés, mint a generálás és küldés útján, tehát a
    projekt továbbléphet a TIG-fázisba.

    Az összeget előtte menteni kell (POST /save): szerződést összeg nélkül nem
    tekintünk késznek, ugyanúgy, ahogy a kiküldésnél sem.

    Rossz fájl esetén ugyanaz a javítás, mint tévesen KIKÜLDÖTT szerződésnél:
    a bejegyzést törölni kell (DELETE), és tiszta lappal újrakezdeni - egy
    véglegesített szerződés-bejegyzést nem írunk felül. Egy szerződésnek
    ugyanis EGY dokumentuma van; ha a bejegyzés még nincs véglegesítve, egy
    újabb feltöltés lecseréli az előzőt (a régi objektumot a tárhelyről is
    eldobva)."""
    project = _get_project_or_404(db, project_id)
    csoport = _validate_szamlazo(db, project, szamlazo_kulcs)
    draft = _get_or_create_draft(db, project, csoport)
    if not draft.netto_osszeg or draft.netto_osszeg <= 0:
        raise HTTPException(status_code=400, detail="Add meg a nettó összeget.")

    filename = file.filename or "szerzodes"
    content_type = file.content_type or "application/octet-stream"
    data = await file.read()

    regi_kulcs = draft.szerzodes_file_storage_key
    kulcs = f"szerzodes-dokumentum/{project_id}/{szamlazo_kulcs}-{draft.id}{os.path.splitext(filename)[1]}"
    draft.szerzodes_file_url = document_storage.upload_bytes(data, kulcs, content_type)
    draft.szerzodes_file_storage_key = kulcs
    draft.szerzodes_allapota = "Kiküldve"
    db.commit()
    # A cserélt fájl törlése CSAK a mentés után, és csak ha tényleg másik
    # objektum volt - így egy elhasalt feltöltésnél nem marad se régi, se új.
    if regi_kulcs and regi_kulcs != kulcs:
        document_storage.delete_object(regi_kulcs)
    db.refresh(draft)
    return ContractRead.model_validate(draft)


@router.post("/{project_id}/{szamlazo_kulcs}/skip", response_model=ContractRead)
def skip_contract(
    project_id: int,
    szamlazo_kulcs: str,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """A megbízott kihagyása - a projekt lezárható vele szerződés nélkül is,
    ő ezután nem jelenik meg többé a függő listán ennél a projektnél."""
    project = _get_project_or_404(db, project_id)
    csoport = _validate_szamlazo(db, project, szamlazo_kulcs)
    draft = _get_or_create_draft(db, project, csoport)
    draft.szerzodes_allapota = "Kihagyva"
    db.commit()
    db.refresh(draft)
    return ContractRead.model_validate(draft)


@router.delete("/{project_id}/{szamlazo_kulcs}", status_code=204)
def delete_contract(
    project_id: int,
    szamlazo_kulcs: str,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "delete")),
):
    """Az eseti szerződés-bejegyzés teljes törlése - a munkatárs ezután újra
    "hiányzik" ezen a projekten, és készíthető neki új szerződés.

    Az állapot visszaállítása nem mindig elég: ha rossz adattal ment ki a
    szerződés (vagy tévesen lett kihagyva), tiszta lappal kell újrakezdeni.

    Ha a projekten már készült TIG ehhez az emberhez, azt előbb törölni kell:
    a TIG a szerződés lezárása UTÁN következő lépés, és a szerződés törlésével
    a projekt visszalép a szerződés-fázisba - a fázisok ne csúszhassanak
    egymásba."""
    fel = szamlazo.feloldas(db, szamlazo_kulcs)
    if fel is None:
        raise HTTPException(status_code=404, detail="A számlázó fél nem található")
    contract = (
        db.query(Contract)
        .filter(
            Contract.project_id == project_id,
            Contract.tipus == ContractType.ALVALLALKOZOI,
            _szamlazo_szuro(fel),
        )
        .first()
    )
    if contract is None:
        raise HTTPException(status_code=404, detail="Ehhez a projekthez és félhez nincs szerződés-bejegyzés.")
    if _van_tig_a_projekten(db, project_id, fel):
        raise HTTPException(
            status_code=400,
            detail="Ehhez a félhez már készült TIG ezen a projekten - előbb a TIG-et kell törölni.",
        )
    db.delete(contract)
    db.commit()


def _van_tig_a_projekten(db: Session, project_id: int, fel: SzamlazoFel) -> bool:
    """Készült-e már TIG ehhez a félhez ezen a projekten?

    A TIG akkor is ide tartozik, ha egy MÁSIK projektről indult, de van ezt a
    projektet érintő tétele (egy fél több projektjét egy TIG-en igazolhatja) -
    ezért a tételeken keresztül keresünk, nem a TIG saját project_id-jén."""
    lekerdezes = db.query(PerformanceCertificate.id).filter(
        papir_fedettseg.fedi_a_projektet(PerformanceCertificate, PerformanceCertificateTetel, project_id)
    )
    if fel.vallalkozas is not None:
        lekerdezes = lekerdezes.filter(PerformanceCertificate.vallalkozas_id == fel.vallalkozas.id)
    else:
        lekerdezes = lekerdezes.filter(
            PerformanceCertificate.employee_id == fel.employee.id,
            PerformanceCertificate.vallalkozas_id.is_(None),
        )
    return lekerdezes.first() is not None
