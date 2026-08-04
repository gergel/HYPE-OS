"""A Project oldal Notion-button automatizmusainak (Feldarabolás, Utómunka)
portolása - lásd a felhasználó által küldött screenshotokat a pontos mezőkről."""

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models.deliverable import Deliverable
from app.models.employee import Employee
from app.models.project import Project


def create_feldarabolas(db: Session, project: Project) -> Project:
    """'Feldarabolás' gomb: leválaszt EGY NAPOT egy több napos forgatásból - új
    Project sort hoz létre ugyanahhoz a Project Code-hoz és kampányhoz,
    átmásolva a nevet/leírást/projektkódot/stábot. A dátum a 'Darabolás
    dátuma' mező, ha ki van töltve, egyébként a forgatás záró napja utáni nap.

    A leválasztott nap MEGJEGYZI, melyik projektből származik
    (feldarabolas_szulo_id), és az eredeti projekt záró napját visszavágjuk a
    leválasztott nap ELŐTTI napra. Enélkül az "egész" (több napos) projekt is
    ugyanúgy diszponálandóként jelent meg, mint a leválasztott nap - pedig
    darabolás után már a napokat kell diszponálni, nem az egészet."""
    if project.darabolas_datuma:
        new_date = project.darabolas_datuma
    elif project.forgatas_datuma:
        base = project.forgatas_datuma_vege or project.forgatas_datuma
        new_date = base + timedelta(days=1)
    else:
        new_date = None

    new_project = Project(
        nev=project.nev,
        project_code_id=project.project_code_id,
        campaign_id=project.campaign_id,
        forgatas_datuma=new_date,
        description=project.description,
        projektkod_szoveg=project.projektkod_szoveg,
        helyszin=project.helyszin,
        feldarabolas_szulo_id=project.id,
    )
    new_project.crew = list(project.crew)
    db.add(new_project)

    _vagd_le_a_leszakitott_napot(project, new_date)

    db.commit()
    db.refresh(new_project)
    return new_project


def _vagd_le_a_leszakitott_napot(project: Project, new_date: date | None) -> None:
    """Az eredeti projekt már csak a leválasztott nap ELŐTTI napokat fedi le.

    Ha ezzel egyetlen naposra zsugorodik, a záró dátumot töröljük (a
    forgatas_datuma_vege csak több napos forgatásnál értelmes). Ha a
    leválasztott nap nem a projekt tartományán belülre esik (pl. a záró nap
    UTÁNI napra daraboltak, ami a régi, Notionből hozott alapértelmezés), az
    eredetihez nem nyúlunk - ott nincs mit levágni."""
    if new_date is None or project.forgatas_datuma is None:
        return
    utolso_nap = project.forgatas_datuma_vege or project.forgatas_datuma
    if new_date > utolso_nap or new_date <= project.forgatas_datuma:
        return
    uj_veg = new_date - timedelta(days=1)
    project.forgatas_datuma_vege = None if uj_veg == project.forgatas_datuma else uj_veg


def create_utomunka(db: Session, project: Project, current_user: Employee) -> Deliverable:
    """'Utómunka' gomb: új Deliverable-t hoz létre ehhez a projekthez, a Notion
    automatizmus PROJEK NEVE formulájával megegyező névvel:
    <Name>_<Forgatás időpontja YYYY.MM.DD>_<Projektkód első 4 karaktere>."""
    date_part = project.forgatas_datuma.strftime("%Y.%m.%d") if project.forgatas_datuma else ""
    kod_part = (project.projektkod_szoveg or "")[:4]
    projekt_neve = "_".join(part for part in (project.nev, date_part, kod_part) if part)

    deliverable = Deliverable(
        projekt_neve=projekt_neve or f"Utómunka – {project.nev}",
        project_id=project.id,
        project_code_id=project.project_code_id,
        campaign_id=project.campaign_id,
        allapot="Beérkező",
        projektkod_szoveg=project.projektkod_szoveg,
        aki_felvezette_employee_id=current_user.id,
        aki_felvezette_az_utomunkat_notion_ids=[current_user.full_name],
    )
    db.add(deliverable)
    db.commit()
    db.refresh(deliverable)
    return deliverable
