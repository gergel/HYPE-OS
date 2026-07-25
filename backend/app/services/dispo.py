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
indítanának - ez felel meg az eredeti FULL_REPLY módnak.

FONTOS a válaszként (nem külön levélként) küldéshez: a Gmail API-nak küldött
`threadId` csak a KÜLDŐ saját Gmail-fiókjában garantálja a szálba fűzést - a
CÍMZETTEK levelezőjében (és más Gmail-fiókokban is) a tényleges RFC822
`In-Reply-To`/`References` fejléc dönt, aminek egy VALÓDI Message-ID-t kell
tartalmaznia (pl. `<abc123@mail.gmail.com>`), NEM a Gmail thread ID-t (ami
egy teljesen más formátumú, rövid hex azonosító). Ezért a `gmail_thread_id`
MELLETT a `gmail_last_message_id`-t (az előző email valódi Message-ID-je,
lásd Project modell) is eltároljuk, és EZT adjuk át `in_reply_to`-ként."""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, time, timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.employee import Employee
from app.models.project import Project
from app.services.gdoc_template import gdoc_fill_and_export_pdf
from app.services.google_email import send_message

logger = logging.getLogger("hype_os")

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

# A felhasználó által megadott, rögzített HYPE aláírás - minden diszpó emailhez
# (előzetes és teljes is) hozzáfűzzük. Külön konstansként, NEM a fenti .format()-olt
# sablonok részeként, hogy a benne szereplő HTML sose ütközzön a .format() placeholder
# szintaxisával (nincs benne {kulcs}, de így akkor sem lenne gond, ha később kapna).
_SIGNATURE_HTML = """\
<table cellpadding="0" cellspacing="0" style="font-family: Arial, sans-serif; font-size: 12px; color: #000;">
  <tr>
    <td style="vertical-align: middle; width: 150px;">
      <img src="https://raw.githubusercontent.com/gergel/ADMIN_projektkod/main/hype_logo_BG_03%20(2).png" alt="Hype logo" width="110">
    </td>
    <td style="padding-left: 20px; vertical-align: middle;">
      <p style="margin: 0; font-size: 12px; font-weight: bold;">
        HYPE PRODUCTIONS - GYÁRTÁS
      </p>
      <p style="margin: 0; color: #888; font-size: 12px;">
        Hype Productions Kft.
      </p>
    </td>
    <td style="padding-left: 40px; vertical-align: top; color: #888; font-size: 12px;">
      <p style="margin: 0;">Rahman Martin – cégvezető</p>
      <p style="margin: 0;">
        <a href="mailto:martin.rahman@hypestab.hu" style="color: #888; text-decoration: underline;">martin.rahman@hypestab.hu</a><br>
        +36 30 898 7600

      <br>
      <p style="margin: 0;">Barna Blanka – Back office manager</p>
      <p style="margin: 0;">
        <a href="mailto:blanka.barna@hypestab.hu" style="color: #888; text-decoration: underline;">blanka.barna@hypestab.hu</a><br>
        +36 30 758 8751
 <br>
      <p style="margin: 0;">Zseni Boglárka – Gyártásvezető</p>
      <p style="margin: 0;">
        <a href="mailto:boglarka.zseni@hypestab.hu" style="color: #888; text-decoration: underline;">boglarka.zseni@hypestab.hu</a><br>
        +36 30 241 9643
 <br>
      <p style="margin: 0;">Vidor Gergely – Operatív vezető</p>
      <p style="margin: 0;">
        <a href="mailto:gergely.vidor@hypestab.hu" style="color: #888; text-decoration: underline;">gergely.vidor@hypestab.hu</a><br>
        +36 20 560 9623
      </p>
    </td>
  </tr>
</table>
"""


def _format_hu_date_range(project: Project) -> str:
    if not project.forgatas_datuma:
        return ""
    start = project.forgatas_datuma.strftime("%Y.%m.%d")
    if project.forgatas_datuma_vege and project.forgatas_datuma_vege != project.forgatas_datuma:
        return f"{start} – {project.forgatas_datuma_vege.strftime('%Y.%m.%d')}"
    return start


def _recipients(project: Project) -> list[str]:
    """A diszpó (és az utókövető email) címzettjei - a 'Résztvevők email'
    Notion-mezőben kézzel felsoroltak MELLÉ automatikusan hozzávesszük a
    projekt stábjaként (project.crew) felvett emberek email címét is, hogy ne
    kelljen minden hozzáadott stábtagot manuálisan is beírni a szöveges
    mezőbe. Kis- és nagybetű szerint dedupolva, a megjelenési sorrend
    megtartásával."""
    raw = (project.resztvevok_email or "").replace(";", ",")
    manual = [e.strip() for e in raw.split(",") if e.strip()]
    crew_emails = [e.email.strip() for e in project.crew if e.email and e.email.strip()]

    seen: set[str] = set()
    result: list[str] = []
    for email in manual + crew_emails:
        key = email.lower()
        if key not in seen:
            seen.add(key)
            result.append(email)
    return result


def _subject_date(project: Project) -> str:
    """A tárgyban szereplő dátum, ÉVSZÁM NÉLKÜL:

    - egy nap:                 "07.06."
    - több nap egy hónapban:   "07.08.-10."   (a hónapot nem ismételjük)
    - hónaphatáron át:         "07.30.-08.02."
    """
    start = project.forgatas_datuma
    if not start:
        return ""
    end = project.forgatas_datuma_vege
    if not end or end == start:
        return start.strftime("%m.%d.")
    if end.month == start.month:
        return f"{start.strftime('%m.%d.')}-{end.strftime('%d.')}"
    return f"{start.strftime('%m.%d.')}-{end.strftime('%m.%d.')}"


def _subject(project: Project) -> str:
    """A diszpó-levél tárgya: "<dátum>_diszpo_<projektkód>", pl.
    "07.06._diszpo_HYPE26-0001" vagy "07.08.-10._diszpo_HYPE26-0002".

    Mindig ebből a két adatból áll össze - a Notion 'Diszpó tárgya' képletét
    szándékosan NEM használjuk, mert a felhasználó egységes formátumot kért.
    A Notion-képlet (majd a projekt neve) csak akkor jön elő, ha se dátum, se
    projektkód nincs, hogy tárgy nélküli levél semmiképp ne menjen ki.

    Ugyanez a szöveg lesz a csatolt PDF neve is (lásd _pdf_filename)."""
    datum = _subject_date(project)
    projektkod = (project.projektkod_szoveg or "").strip()
    if datum or projektkod:
        return f"{datum}_diszpo_{projektkod}"

    formula = project.diszpo_targya_notion
    if isinstance(formula, str) and formula.strip():
        return formula.strip()
    if isinstance(formula, list) and formula and isinstance(formula[0], str) and formula[0].strip():
        return formula[0].strip()
    return f"Diszpó – {project.nev}" if project.nev else "Diszpó"


def _pdf_filename(project: Project) -> str:
    """A csatolt PDF neve = a levél tárgya (felhasználói kérés). A fájlnévbe
    nem való karaktereket cseréljük, mert a tárgy tartalmazhat ilyet (pl. a
    fallback ágon "Diszpó – Név"), és a név idézőjelek közt megy ki a
    Content-Disposition fejlécben."""
    name = _subject(project)
    for bad in ('/', '\\', '"', "\r", "\n", "\t"):
        name = name.replace(bad, "-")
    return f"{name.strip() or 'diszpo'}.pdf"


def send_elozetes_diszpo(db: Session, project: Project, current_user: Employee) -> dict:
    """'Előzetes diszpó' gomb - rövid, technika-lista nélküli tájékoztató email
    (helyszín + diszpó szövege), nem generál PDF-et."""
    to_list = _recipients(project)
    if not to_list:
        raise ValueError("Nincs kitöltve 'Résztvevők email' - nincs kinek küldeni az előzetes diszpót.")

    html = _PRE_DISPO_HTML.format(helyszin=project.helyszin or "", diszpo_szoveg=project.diszpo_szovege or "") + _SIGNATURE_HTML
    thread_id, _msg_id, rfc822 = send_message(
        to_list,
        _subject(project),
        html,
        thread_id=project.gmail_thread_id,
        in_reply_to=project.gmail_last_message_id,
        sender_name=settings.dispo_sender_name,
    )

    # A levél ekkor már ténylegesen kiment (a send_message fentebb hibát dobna,
    # ha nem), ezért "Kiküldve" - ugyanaz a szöveg, mint a teljes diszpónál, hogy
    # a két állapot egységes legyen a Naptár/Projekt nézetekben.
    project.elozetes_diszpo_kuldes = "Kiküldve"
    project.gmail_thread_id = thread_id or project.gmail_thread_id
    project.gmail_last_message_id = rfc822 or project.gmail_last_message_id
    project.aki_az_elozetest_kuldte_ki = [current_user.full_name]
    db.commit()
    db.refresh(project)
    return {"status": "OK", "message": "Előzetes diszpó elküldve.", "thread_id": project.gmail_thread_id}


def _schedule_utokovetes_email(project: Project) -> None:
    """A diszpó kiküldése után beütemezi az utókövető kérdőív-emailt a
    forgatás vége utáni napra, 12 órára (egy napos forgatásnál a forgatási
    nap utáni nap 12:00, több naposnál az utolsó forgatási nap utáni nap
    12:00 - mindkettő ugyanaz a képlet: utolsó nap + 1 nap, 12:00). Az eta-t
    naiv (nem UTC-re konvertált) időpontként adjuk át - egy nagyjából 12 órás
    utókövető emailnél ez az egyszerűsítés (max. 1-2 órás csúszás időzóna
    miatt) nem számít. Ha az ütemezés (pl. Redis nem elérhető) elhasal, ez
    NEM hiúsítja meg magát a diszpó-küldést - csak naplózzuk."""
    last_day = project.forgatas_datuma_vege or project.forgatas_datuma
    if not last_day:
        return
    if not project.utokoveto_token:
        project.utokoveto_token = secrets.token_urlsafe(16)
    eta = datetime.combine(last_day, time(0)) + timedelta(days=1, hours=12)
    try:
        from app.workers.dispo_tasks import send_utokovetes_email_task

        send_utokovetes_email_task.apply_async(args=[project.id], eta=eta)
    except Exception:
        logger.exception("Nem sikerült beütemezni az utókövető emailt project_id=%s", project.id)


def send_diszpo(db: Session, project: Project, current_user: Employee) -> dict:
    """'Diszpó küldése' gomb - teljes diszpó email a technika listával, stábbal,
    brief-fel stb., és (ha GDOC_DISPO_TEMPLATE_ID be van állítva) egy Google Docs
    sablonból generált, csatolt PDF-fel. Ha a projektnek már van
    gmail_thread_id-je (előzetes diszpó már ment), ugyanabba a szálba válaszol -
    valódi email-válaszként (lásd gmail_last_message_id), nem külön levélként."""
    to_list = _recipients(project)
    if not to_list:
        raise ValueError("Nincs kitöltve 'Résztvevők email' - nincs kinek küldeni a diszpót.")

    doc_link = None
    pdf_bytes = None
    if settings.gdoc_dispo_template_id:
        stab = ", ".join(e.full_name for e in project.crew) if project.crew else ""
        fields = {
            "Projekt": project.nev or "",
            "Projektkód": project.projektkod_szoveg or "",
            "Forgatás_dátuma": _format_hu_date_range(project),
            "Helyszín": project.helyszin or "",
            "Esemény": project.esemeny or "",
            "Diszpó_szövege": project.diszpo_szovege or "",
            "Stáb": stab,
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
    ) + _SIGNATURE_HTML
    thread_id, _msg_id, rfc822 = send_message(
        to_list,
        _subject(project),
        html,
        pdf_bytes=pdf_bytes,
        pdf_filename=_pdf_filename(project),
        thread_id=project.gmail_thread_id,
        in_reply_to=project.gmail_last_message_id,
        sender_name=settings.dispo_sender_name,
    )

    project.diszpo = "Kiküldve"
    project.drive_diszpo_pdf_url = doc_link or project.drive_diszpo_pdf_url
    project.gmail_thread_id = thread_id or project.gmail_thread_id
    project.gmail_last_message_id = rfc822 or project.gmail_last_message_id
    project.aki_kikuldte_a_diszpot = [current_user.full_name]
    _schedule_utokovetes_email(project)
    db.commit()
    db.refresh(project)
    return {"status": "OK", "message": "Diszpó elküldve.", "thread_id": project.gmail_thread_id, "doc_link": doc_link}
