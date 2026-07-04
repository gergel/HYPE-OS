"""A Project oldal Notion-button automatizmusainak (Feldarabolás, Utómunka)
portolása - lásd a felhasználó által küldött screenshotokat a pontos mezőkről."""

from datetime import timedelta

from sqlalchemy.orm import Session

from app.models.deliverable import Deliverable
from app.models.employee import Employee
from app.models.project import Project


def create_feldarabolas(db: Session, project: Project) -> Project:
    """'Feldarabolás' gomb: új Project sort hoz létre ugyanahhoz a Project Code-hoz
    és kampányhoz, átmásolva a nevet/leírást/projektkódot/stábot - a dátum a
    'Darabolás dátuma' mező, ha ki van töltve, egyébként a forgatás záró napja
    utáni nap (a Notion automatizmus konfirmáció-üzenete pont ezt a két esetet
    ellenőrizte: van-e Darabolás dátuma, és nem lóg-e túl a projekt záró napján)."""
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
    )
    new_project.crew = list(project.crew)
    db.add(new_project)
    db.commit()
    db.refresh(new_project)
    return new_project


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
