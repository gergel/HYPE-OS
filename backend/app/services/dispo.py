"""Diszpó küldés - a felhasználó által csatolt 'diszpo-kuldes' Railway program
portolása. Az eredeti Notion-oldali automatizmus egy checkbox+poll ciklus
(Előzetes tesztelés / Diszpó tesztelés checkbox -> a railway program 60mp-enként
lekérdezte a Notion-t és a checkbox-kombinációból számolt "stage" alapján küldött
emailt). Itt, mivel a felhasználó explicit gombokat akar ("Előzetes diszpó" /
"Diszpó küldése" gomb megnyomására fut le"), nincs szükség pollozásra és
stage-gépezetre: maga a gomb/endpoint hívása a trigger, a két függvény
egyenesen elvégzi a neki megfelelő lépést.

Az egyetlen state-alapú viselkedés, amit megtartunk: ha a projektnek már van
gmail_thread_id-je (mert korábban már küldtünk rajta emailt), a további
küldések ugyanabba a Gmail szálba válaszolnak ahelyett, hogy új levelet
indítanának - ez felel meg az eredeti FULL_REPLY módnak."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.employee import Employee
from app.models.project import Project
from app.services.gdoc_template import gdoc_fill_and_export_pdf
from app.services.google_email import send_message

_PRE_DISPO_HTML = """\
<p>Sziasztok,</p>
<p>Alább a tárgyban említett diszpó előzetes infói.</p>
<p>Helyszín:</p>
<p><pre style="font-family:Arial">{helyszin}</pre></p>
<p><pre style="font-family:Arial">{diszpo_szoveg}</pre></p>
<p><b>TOVÁBBI INFÓK HAMAROSAN!</b></p>
<p><b>Fontos: válasz esetén mindig a 'Válasz Mindenkinek' funkciót használd!</b></p>
<p>Köszönettel</p>
"""

_FULL_DISPO_HTML = """\
<p>Sziasztok,</p>
<p>Alább a tárgyban említett projekt diszpója.</p>
<p>Projekt: {name}<br/>
Projektkód: {projektkod}<br/>
Forgatás dátuma: {idopont}<br/>
Helyszín: {helyszin}</p>
<p>Köszönettel</p>
"""


def _format_hu_date_range(project: Project) -> str:
    if not project.forgatas_datuma:
        return ""
    start = project.forgatas_datuma.strftime("%Y.%m.%d")
    if project.forgatas_datuma_vege and project.forgatas_datuma_vege != project.forgatas_datuma:
        return f"{start} – {project.forgatas_datuma_vege.strftime('%Y.%m.%d')}"
    return start


def _recipients(project: Project) -> list[str]:
    raw = (project.resztvevok_email or "").replace(";", ",")
    return [e.strip() for e in raw.split(",") if e.strip()]


def _subject(project: Project) -> str:
    formula = project.diszpo_targya_notion
    if isinstance(formula, str) and formula.strip():
        return formula.strip()
    if isinstance(formula, list) and formula and isinstance(formula[0], str) and formula[0].strip():
        return formula[0].strip()
    return f"Diszpó – {project.nev}" if project.nev else "Diszpó"


def send_elozetes_diszpo(db: Session, project: Project, current_user: Employee) -> dict:
    """'Előzetes diszpó' gomb - rövid, technika-lista nélküli tájékoztató email
    (helyszín + diszpó szövege), nem generál PDF-et."""
    to_list = _recipients(project)
    if not to_list:
        raise ValueError("Nincs kitöltve 'Résztvevők email' - nincs kinek küldeni az előzetes diszpót.")

    html = _PRE_DISPO_HTML.format(helyszin=project.helyszin or "", diszpo_szoveg=project.diszpo_szovege or "")
    thread_id, _msg_id, rfc822 = send_message(
        to_list,
        _subject(project),
        html,
        thread_id=project.gmail_thread_id,
        in_reply_to=project.gmail_thread_id,
    )

    project.elozetes_diszpo_kuldes = "Küldésre állítva"
    project.gmail_thread_id = thread_id or project.gmail_thread_id
    project.aki_az_elozetest_kuldte_ki = [current_user.full_name]
    db.commit()
    db.refresh(project)
    return {"status": "OK", "message": "Előzetes diszpó elküldve.", "thread_id": project.gmail_thread_id}


def send_diszpo(db: Session, project: Project, current_user: Employee) -> dict:
    """'Diszpó küldése' gomb - teljes diszpó email a technika listával, brief-fel
    stb., és (ha GDOC_DISPO_TEMPLATE_ID be van állítva) egy Google Docs sablonból
    generált, csatolt PDF-fel. Ha a projektnek már van gmail_thread_id-je
    (előzetes diszpó már ment), ugyanabba a szálba válaszol."""
    to_list = _recipients(project)
    if not to_list:
        raise ValueError("Nincs kitöltve 'Résztvevők email' - nincs kinek küldeni a diszpót.")

    doc_link = None
    pdf_bytes = None
    if settings.gdoc_dispo_template_id:
        fields = {
            "Projekt": project.nev or "",
            "Projektkód": project.projektkod_szoveg or "",
            "Forgatás_dátuma": _format_hu_date_range(project),
            "Helyszín": project.helyszin or "",
            "Esemény": project.esemeny or "",
            "Diszpó_szövege": project.diszpo_szovege or "",
            "Technika": project.technika_lista or "",
            "Bérelt_technika": project.berelt_technika_logisztika or "",
            "Brief": project.brief or "",
            "Technikai_kérdés": project.technikai_kerdes or "",
            "Gyártási_kérdés": project.gyartassal_kapcsolatban or "",
            "Kontaktok": project.kontaktok or "",
        }
        pdf_bytes, new_doc_id = gdoc_fill_and_export_pdf(
            template_file_id=settings.gdoc_dispo_template_id,
            base_name=_subject(project),
            fields=fields,
            output_folder_id=settings.gdoc_output_folder_id or settings.drive_folder_id or None,
        )
        doc_link = f"https://docs.google.com/document/d/{new_doc_id}/edit"

    html = _FULL_DISPO_HTML.format(
        name=project.nev or "",
        projektkod=project.projektkod_szoveg or "",
        idopont=_format_hu_date_range(project),
        helyszin=project.helyszin or "",
    )
    thread_id, _msg_id, rfc822 = send_message(
        to_list,
        _subject(project),
        html,
        pdf_bytes=pdf_bytes,
        pdf_filename="diszpo.pdf",
        thread_id=project.gmail_thread_id,
        in_reply_to=project.gmail_thread_id,
    )

    project.diszpo = "Kiküldve"
    project.drive_diszpo_pdf_url = doc_link or project.drive_diszpo_pdf_url
    project.gmail_thread_id = thread_id or project.gmail_thread_id
    project.aki_kikuldte_a_diszpot = [current_user.full_name]
    db.commit()
    db.refresh(project)
    return {"status": "OK", "message": "Diszpó elküldve.", "thread_id": project.gmail_thread_id, "doc_link": doc_link}
