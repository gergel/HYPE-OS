"""A Project oldal Notion-button automatizmusainak (Feldarabolás, Utómunka)
portolása - lásd a felhasználó által küldött screenshotokat a pontos mezőkről."""

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models.deliverable import Deliverable
from app.models.employee import Employee
from app.models.project import Project
from app.models.project_szamlazo import ProjectSzamlazo
from app.services import diszpo_sablon


def create_feldarabolas(
    db: Session, project: Project, datum: date | None = None, datum_vege: date | None = None
) -> Project:
    """'Feldarabolás' gomb: leválaszt egy NAPOT vagy DÁTUM-TARTOMÁNYT egy
    forgatásból - új Project sort hoz létre ugyanahhoz a Project Code-hoz és
    kampányhoz, átmásolva a nevet/leírást/projektkódot/stábot.

    A napot/tartományt a felugró ablak adja át (`datum` + opcionális
    `datum_vege` - a felhasználó kérése); ha nincs megadva, a régi
    alapértelmezés él: a 'Darabolás dátuma' mező, egyébként a forgatás záró
    napja utáni nap.

    A leválasztott nap MEGJEGYZI, melyik projektből származik
    (feldarabolas_szulo_id). Az EREDETI projekt dátumaihoz a darabolás NEM
    nyúl (a felhasználó 2026-09-03-i kérése): a fő esemény hossza változatlan
    marad, egyszerűen bekerül mellé egy plusz esemény - akár ugyanarra a
    napra/tartományra is (az esemény DUPLÁZÁSA is megengedett, a felhasználó
    kérése: pl. egy napon két stáb két diszpója)."""
    if datum is not None:
        new_date = datum
        # Egy napra mutató "tartomány" (vég <= kezdet) = egynapos leválasztás.
        if datum_vege is not None and datum_vege <= datum:
            datum_vege = None
    elif project.darabolas_datuma:
        new_date = project.darabolas_datuma
        datum_vege = None
    elif project.forgatas_datuma:
        base = project.forgatas_datuma_vege or project.forgatas_datuma
        new_date = base + timedelta(days=1)
        datum_vege = None
    else:
        new_date = None
        datum_vege = None

    new_project = Project(
        nev=project.nev,
        project_code_id=project.project_code_id,
        campaign_id=project.campaign_id,
        forgatas_datuma=new_date,
        forgatas_datuma_vege=datum_vege,
        description=project.description,
        projektkod_szoveg=project.projektkod_szoveg,
        helyszin=project.helyszin,
        feldarabolas_szulo_id=project.id,
        # A darabolás szándékos, kézi dátum-művelet: a leválasztott nap
        # dátumát a szinkronok nem írhatják felül (lásd models/project.py
        # forgatas_datum_kezzel_beallitva).
        forgatas_datum_kezzel_beallitva=True,
    )
    # Az üres kontakt/diszpó-szöveg/brief mezőkbe az alapértelmezett sablon
    # kerül (a felhasználó kérése) - ami az eredetiről átjött, az marad.
    diszpo_sablon.toltsd_ki_a_sablonokat_objektumon(new_project)
    new_project.crew = list(project.crew)
    # A számlázási felállás (ki számláz kiért) a leválasztott napra is
    # ugyanaz - lásd models/project_szamlazo.py. Enélkül a feldarabolt nap
    # minden emberénél újra a saját nevére kérné a papírt.
    new_project.szamlazok = [
        ProjectSzamlazo(
            employee_id=sz.employee_id,
            szamlazo_employee_id=sz.szamlazo_employee_id,
            szamlazo_vallalkozas_id=sz.szamlazo_vallalkozas_id,
            megjegyzes=sz.megjegyzes,
        )
        for sz in project.szamlazok
    ]
    db.add(new_project)

    db.commit()
    db.refresh(new_project)
    return new_project


class DarabolasHiba(ValueError):
    """A darabolás nem végezhető el - a felület ezt az üzenetet mutatja.

    Jelenleg semmi nem dobja (az esemény duplázása is megengedett, a
    felhasználó kérése) - a route hibakezelése miatt marad meg."""


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
