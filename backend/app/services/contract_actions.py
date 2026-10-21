"""'Szerződés készítés' és 'szerződés készítése és küldése' - a Main oldal
Notion automatizmusainak portolása.

A felhasználó leírása szerint a 'Szerződés készítés' relation (Külsős és
belsős adatbázis) egy embert enged kiválasztani, és az illető minden adatát
átmásolja a Project megfelelő mezőibe. A Project modellben ezekhez a Notion
oldalon már léteznek saját, névvel ellátott "megbízott_*" tükör-mezők (lásd
app/models/project.py "szerződés / TIG" blokk) - ide másolunk.

A relation technikailag Notion-oldalon multi-select típusú, de a leírás
("a kiválasztott embernek MINDEN adatát") és a cél mezők egyes számú jellege
(nem lista) alapján itt pragmatikusan egyetlen kiválasztott Employee-ként
kezeljük (hasonlóan a Feldarabolás dátum-mezőjéhez - lásd project_actions.py)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.employee import Employee
from app.models.project import Project
from app.services.gdoc_template import gdoc_fill_and_export_pdf
from app.services.google_email import send_message

_CONTRACT_EMAIL_HTML = """\
<p>Kedves {nev},</p>
<p>Csatoltan küldjük a(z) {projekt} projekthez tartozó megbízási szerződést.</p>
<p>Kérjük, aláírás után küldd vissza.</p>
<p>Köszönettel</p>
"""


def apply_szerzodes_keszites(db: Session, project: Project, employee_id: int) -> Project:
    """'Szerződés készítés' relation kiválasztása: az Employee adatai bemásolódnak
    a Project szerződés-mezőibe."""
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise ValueError("A kiválasztott személy nem található.")

    project.szerzodes_keszites_employee_id = employee.id
    project.megbizott_neve = employee.vallakozas_neve or employee.full_name
    project.megbizott_szekhely = employee.vallakozas_szekhely
    project.megbizott_adoszam = employee.vallalkozas_adoszama
    project.kepviselo = employee.vallalkozas_kepviselo
    project.keltezes_datuma = employee.keltezes_datuma
    project.megbizas_targya = employee.megbizas_targya
    project.nyilvantartasi_szam = employee.nyilvantartasi_szam
    project.szerzodes_allapot = "Készítés alatt"

    db.commit()
    db.refresh(project)
    return project


def send_szerzodes(db: Session, project: Project) -> dict:
    """'szerződés készítése és küldése' gomb - a Project szerződés-mezőiből (lásd
    apply_szerzodes_keszites) Google Docs sablonból PDF-et generál (ha
    GDOC_CONTRACT_TEMPLATE_ID be van állítva) és elküldi a megbízott email
    címére, ugyanúgy ahogy a diszpó küldés teszi a diszpó PDF-fel."""
    if not project.szerzodes_keszites_employee_id:
        raise ValueError("Nincs kiválasztva megbízott ('Szerződés készítés' mező) - előbb azt kell beállítani.")
    employee = db.get(Employee, project.szerzodes_keszites_employee_id)
    if employee is None or not employee.email:
        raise ValueError("A kiválasztott megbízottnak nincs email címe.")

    doc_link = None
    pdf_bytes = None
    if settings.gdoc_contract_template_id:
        fields = {
            "Megbízott_neve": project.megbizott_neve or "",
            "Megbízott_székhely": project.megbizott_szekhely or "",
            "Megbízott_adószám": project.megbizott_adoszam or "",
            "Képviselő": project.kepviselo or "",
            "Keltezés_dátuma": project.keltezes_datuma.strftime("%Y.%m.%d") if project.keltezes_datuma else "",
            "Megbízás_tárgya": project.megbizas_targya or "",
            "Nyilvántartási_szám": project.nyilvantartasi_szam or "",
            "Projektkód": project.projektkod_szoveg or "",
            "Projekt": project.nev or "",
        }
        pdf_bytes, new_doc_id = gdoc_fill_and_export_pdf(
            template_file_id=settings.gdoc_contract_template_id,
            base_name=f"Szerződés – {project.megbizott_neve or project.nev}",
            fields=fields,
            output_folder_id=settings.gdoc_output_folder_id or settings.drive_folder_id or None,
        )
        doc_link = f"https://docs.google.com/document/d/{new_doc_id}/edit"

    subject = f"Megbízási szerződés – {project.megbizott_neve or project.nev}"
    html = _CONTRACT_EMAIL_HTML.format(nev=project.megbizott_neve or employee.full_name, projekt=project.nev or "")
    send_message([employee.email], subject, html, pdf_bytes=pdf_bytes, pdf_filename="szerzodes.pdf")

    project.szerzodes_allapot = "Kiküldve"
    project.szerzodes_pdf_url = doc_link or project.szerzodes_pdf_url
    db.commit()
    db.refresh(project)
    return {"status": "OK", "message": "Szerződés elküldve.", "doc_link": doc_link}
