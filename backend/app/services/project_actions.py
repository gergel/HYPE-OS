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
    (feldarabolas_szulo_id), és az eredeti projektből KIVESSZÜK a leválasztott
    napot. Enélkül az "egész" (több napos) projekt is ugyanúgy diszponálandóként
    jelent meg, mint a leválasztott nap - pedig darabolás után már a napokat
    kell diszponálni, nem az egészet.

    Egynapos forgatásból nincs mit leválasztani a SAJÁT napjára: abból nem két
    forgatás lenne, hanem ugyanaz kétszer. (A záró nap UTÁNI napra darabolás
    viszont továbbra is megengedett - az a "vegyünk fel még egy napot" eset.)"""
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
    _ellenorizd_a_darabolast(project, new_date, datum_vege)

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

    _vagd_le_a_leszakitott_napot(project, new_date, datum_vege)

    db.commit()
    db.refresh(new_project)
    return new_project


class DarabolasHiba(ValueError):
    """A darabolás nem végezhető el - a felület ezt az üzenetet mutatja."""


def _ellenorizd_a_darabolast(project: Project, new_date: date | None, new_end: date | None) -> None:
    """A leválasztott nap/tartomány nem fedheti le az EGÉSZ forgatást: abból
    nem két forgatás lenne, hanem ugyanaz kétszer. (A záró nap UTÁNI napra
    darabolás továbbra is megengedett - az a "vegyünk fel még egy napot"
    eset.)"""
    if new_date is None or project.forgatas_datuma is None:
        return
    utolso_nap = project.forgatas_datuma_vege or project.forgatas_datuma
    if new_date <= project.forgatas_datuma and (new_end or new_date) >= utolso_nap:
        raise DarabolasHiba(
            "A leválasztott nap/tartomány a teljes forgatást lefedné - a darabolással "
            "ugyanaz a forgatás jelenne meg kétszer. Válaszd ki, MELYIK napot (vagy "
            "rövidebb tartományt) emeljük ki, vagy a záró nap utáni dátummal vegyél fel "
            "egy új napot."
        )


def _vagd_le_a_leszakitott_napot(project: Project, new_date: date | None, new_end: date | None = None) -> None:
    """Az eredeti projektből KIVESSZÜK a leválasztott napot/tartományt.

    Három eset van (a tartomány egy napnál a [nap, nap] tartomány):

    - a leválasztás az ELSŐ napon kezdődik: az eredeti a tartomány utáni
      naptól él tovább. Enélkül az eredeti érintetlen maradt, tehát ugyanarra
      a napra az "egész" forgatás is ott állt a diszponálandók közt a
      leválasztott nap mellett - pont az, amit a darabolásnak meg kellene
      szüntetnie;
    - a leválasztás a tartományon BELÜL kezdődik: az eredeti a kezdőnap
      előtti napig tart;
    - a leválasztás a tartományon KÍVÜL esik (pl. a záró nap UTÁNI napra
      daraboltak, ami a régi, Notionből hozott alapértelmezés): az eredetihez
      nem nyúlunk, ott nincs mit levágni.

    Ha az eredeti egyetlen naposra zsugorodik, a záró dátumot töröljük - a
    `forgatas_datuma_vege` csak több napos forgatásnál értelmes."""
    if new_date is None or project.forgatas_datuma is None:
        return
    utolso_nap = project.forgatas_datuma_vege or project.forgatas_datuma
    veg = new_end or new_date
    if new_date > utolso_nap or veg < project.forgatas_datuma:
        return
    if new_date <= project.forgatas_datuma:
        uj_kezdet = veg + timedelta(days=1)
        project.forgatas_datuma = uj_kezdet
        project.forgatas_datuma_vege = None if uj_kezdet >= utolso_nap else utolso_nap
        # A megkurtított eredeti dátumait se írhassa vissza a szinkron a
        # darabolás előtti (teljes) tartományra - lásd models/project.py
        # forgatas_datum_kezzel_beallitva.
        project.forgatas_datum_kezzel_beallitva = True
        return
    uj_veg = new_date - timedelta(days=1)
    project.forgatas_datuma_vege = None if uj_veg == project.forgatas_datuma else uj_veg
    project.forgatas_datum_kezzel_beallitva = True


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
