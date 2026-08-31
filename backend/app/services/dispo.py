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

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.dispo_responsible import DiszpoMasolatCimzett
from app.models.employee import Employee
from app.models.project import Project
from app.services import attachments, document_storage, projektkod_kotes
from app.services.gdoc_template import gdoc_fill_and_export_pdf, pdf_feltoltes
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
    """A forgatás ideje a levélben/PDF-ben: dátum(ok), és ha meg van adva, a
    napon belüli időpont is ("2026.07.06., 08:00 – 17:00")."""
    if not project.forgatas_datuma:
        return ""
    start = project.forgatas_datuma.strftime("%Y.%m.%d")
    if project.forgatas_datuma_vege and project.forgatas_datuma_vege != project.forgatas_datuma:
        datum = f"{start} – {project.forgatas_datuma_vege.strftime('%Y.%m.%d')}"
    else:
        datum = start
    ido = _format_ido(project)
    return f"{datum}, {ido}" if ido else datum


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


def _crew_without_email(project: Project) -> list[str]:
    """A projekt stábjából azok neve, akiknek nincs email címük - ábécé
    sorrendben, duplikátumok nélkül."""
    names = {e.full_name for e in project.crew if not (e.email or "").strip()}
    return sorted(names)


def _require_crew_emails(project: Project) -> None:
    """A diszpó (előzetes és teljes egyaránt) nem küldhető ki, amíg a projekt
    stábjában van olyan ember, akinek nincs email címe.

    Enélkül a hiányzó címűek NÉMÁN kimaradtak a címzettek közül (lásd
    _recipients: a None/üres emaileket egyszerűen kiszűri), tehát a diszpó
    kiment ugyan, de pont az érintett stábtag nem kapta meg - a felhasználó
    kifejezett kérése, hogy ilyenkor inkább álljon meg a küldés, és mondjuk
    meg, kinek hiányzik a címe."""
    missing = _crew_without_email(project)
    if not missing:
        return
    raise ValueError(
        "Nem küldhető ki a diszpó, mert a következő stábtagoknak nincs email címe:\n"
        + "\n".join(f"• {name}" for name in missing)
        + "\n\nAdd meg az email címüket (Csapat oldal), vagy vedd le őket a projekt stábjáról."
    )


def _require_projektkod(project: Project) -> None:
    """Projektkód nélkül nem megy ki diszpó.

    A projektkód a levél tárgyának és a csatolt PDF nevének a fele (lásd
    _subject), és ez alapján azonosítja a stáb a forgatást a levelezésben -
    enélkül "07.06._diszpo_" alakú, azonosíthatatlan tárgy menne ki. Az importok
    gyűjtő kódját ("NAPTAR-IMPORT", "ISMERETLEN-NOTION-IMPORT") sem fogadjuk el:
    azok csak technikai kezdőértékek, amíg valaki be nem sorolja a projektet
    (lásd services/projektkod_kotes.py).

    A FORMÁTUM viszont szabad: nem minden munka a megszokott kód-alakot viseli
    (más ügyfél rendszere, régi sorozat), és egy szigorú minta itt csak abban
    akadályozna meg, hogy kimenjen a diszpó."""
    kod = (project.projektkod_szoveg or "").strip()
    if projektkod_kotes.valodi(kod):
        return
    raise ValueError(
        "Nem küldhető ki a diszpó, mert a projektnek nincs projektkódja.\n\n"
        "A projektkód a levél tárgyába és a csatolt PDF nevébe is bekerül, ezért enélkül "
        "azonosíthatatlan lenne a forgatás. Add meg a projektkódot a projekt adatlapján - "
        "bármilyen formátum megadható, nem kell a megszokott alakot követnie."
    )


def _format_ido(project: Project) -> str:
    """A forgatás napon belüli időpontja ("08:00 – 17:00"), ha meg van adva -
    egyébként üres. Csak kezdés is elég ("08:00-tól")."""
    kezdes = project.forgatas_kezdes_ido
    veg = project.forgatas_veg_ido
    if kezdes and veg:
        return f"{kezdes.strftime('%H:%M')} – {veg.strftime('%H:%M')}"
    if kezdes:
        return f"{kezdes.strftime('%H:%M')}-tól"
    if veg:
        return f"{veg.strftime('%H:%M')}-ig"
    return ""


def _subject_date(project: Project) -> str:
    """A tárgyban szereplő dátum, ÉVSZÁM NÉLKÜL - a felhasználó által megadott
    pontos alak (időpont ide NEM kerül, csak a dátum):

    - egy nap:      "07.30"          (pont nélkül a végén)
    - több nap:     "07.28-07.31."   (mindkét hónap kiírva, ponttal a végén)
    """
    start = project.forgatas_datuma
    if not start:
        return ""
    end = project.forgatas_datuma_vege
    if not end or end == start:
        return start.strftime("%m.%d")
    return f"{start.strftime('%m.%d')}-{end.strftime('%m.%d')}."


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


# A Gmail üzenetméret-korlátja 25 MB, de az base64 kódolás ~33%-kal növeli a
# méretet, és a levél többi része (HTML, diszpó PDF) is elfér benne - ezért a
# nyers csatolmányokra ennél alacsonyabb határt szabunk. Enélkül a Gmail egy
# nehezen értelmezhető hibával utasítaná vissza a küldést, a felhasználó pedig
# nem tudná, mit rontott el.
#
# Ugyanez a határ él már a FELTÖLTÉSNÉL is (services/attachments.py) - egy
# forrásból, hogy ne lehessen feltölteni olyat, ami itt aztán elakad. Ez a
# vizsgálat így csak a régi, a korlát előtt feltöltött fájlok hálója.
MAX_CSATOLMANY_BAJT = attachments.DISZPO_MAX_BAJT


def _diszpo_csatolmanyok(db: Session, project: Project) -> list[tuple[str, str, bytes]]:
    """A projekthez "csatolni való"-ként feltöltött fájlok a diszpó-levélhez,
    (fájlnév, MIME típus, tartalom) hármasokként. A fájlok az R2-en vannak
    (lásd services/attachments.py), innen töltjük le őket küldéskor - így a
    levélbe mindig az AKTUÁLIS változat kerül.

    Ha egy fájl nem tölthető le, inkább hibát dobunk, mint hogy a diszpó
    csendben, a melléklet nélkül menjen ki: a stáb nem tudná, hogy hiányzik
    valami."""
    rekordok = attachments.list_by_kategoria(db, "project", project.id, "diszpo")
    if not rekordok:
        return []

    osszes = sum(r.meret_bajt or 0 for r in rekordok)
    if osszes > MAX_CSATOLMANY_BAJT:
        raise ValueError(
            f"A csatolni való fájlok együtt túl nagyok ({osszes / 1024 / 1024:.1f} MB) - "
            f"a levélhez legfeljebb {MAX_CSATOLMANY_BAJT // 1024 // 1024} MB csatolható. "
            "Törölj néhányat - " + attachments.DISZPO_TULLEPES_TANACS
        )

    csatolmanyok: list[tuple[str, str, bytes]] = []
    for rekord in rekordok:
        try:
            adat = document_storage.download_bytes(rekord.storage_key)
        except Exception as exc:  # noqa: BLE001 - a konkrét okot a felhasználónak mutatjuk
            raise ValueError(
                f"A csatolni való fájl nem tölthető le a tárhelyről: {rekord.filename} ({exc}). "
                "A diszpó nem ment ki - próbáld újra, vagy töltsd fel újra a fájlt."
            ) from exc
        csatolmanyok.append((rekord.filename, rekord.content_type or "application/octet-stream", adat))
    return csatolmanyok


def masolat_cimzettek(db: Session) -> list[str]:
    """A Beállításokban megadott emberek email címei - MINDEN kimenő diszpó
    (előzetes és teljes) másolatot (CC) kap rájuk, a HYPE_CC env fix címei
    mellé (lásd models/dispo_responsible.DiszpoMasolatCimzett és
    google_email.send_message extra_cc). Akinek nincs email címe, azt
    csendben kihagyjuk - nincs hova küldeni."""
    sorok = db.scalars(
        select(Employee).join(DiszpoMasolatCimzett, DiszpoMasolatCimzett.employee_id == Employee.id)
    ).all()
    return [e.email.strip() for e in sorok if e.email and e.email.strip()]


def send_elozetes_diszpo(db: Session, project: Project, current_user: Employee) -> dict:
    """'Előzetes diszpó' gomb - rövid, technika-lista nélküli tájékoztató email
    (helyszín + diszpó szövege), nem generál PDF-et."""
    _require_projektkod(project)
    _require_crew_emails(project)
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
        extra_cc=masolat_cimzettek(db),
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


def _pdf_a_drive_ra(project: Project, pdf_bytes: bytes | None) -> str | None:
    """A kiküldött diszpó kész PDF-jét felteszi a Drive célmappájába, és a
    linkjével tér vissza.

    Csak a KIKÜLDÉS UTÁN hívjuk: így egy sikertelen küldés nem hagy maga után
    fájlt a mappában, és ami ott van, az tényleg kiment. Ha a feltöltés
    elhasal (nincs Drive hitelesítés, rossz mappa-azonosító), azt csak
    naplózzuk - a levél már kiment, azt visszacsinálni úgysem tudnánk, a
    hiányzó archív példány miatt pedig nem érdemes hibát mutatni a küldőnek."""
    if not pdf_bytes:
        return None
    try:
        return pdf_feltoltes(
            filename=_pdf_filename(project),
            pdf_bytes=pdf_bytes,
            folder_id=settings.diszpo_folder_id or None,
        )
    except Exception:  # noqa: BLE001 - a kiküldést ez nem buktathatja meg
        logger.exception("Nem sikerült feltölteni a diszpó PDF-et a Drive-ra project_id=%s", project.id)
        return None


def send_diszpo(db: Session, project: Project, current_user: Employee) -> dict:
    """'Diszpó küldése' gomb - teljes diszpó email a technika listával, stábbal,
    brief-fel stb., és (ha GDOC_DISPO_TEMPLATE_ID be van állítva) egy Google Docs
    sablonból generált, csatolt PDF-fel. Ha a projektnek már van
    gmail_thread_id-je (előzetes diszpó már ment), ugyanabba a szálba válaszol -
    valódi email-válaszként (lásd gmail_last_message_id), nem külön levélként.

    A kiküldés UTÁN a kész PDF felkerül a diszpók Drive mappájába is (lásd
    _pdf_a_drive_ra), és a projekt "Drive diszpó pdf" mezője erre a kész
    fájlra mutat - nem a szerkeszthető Docs példányra."""
    _require_projektkod(project)
    _require_crew_emails(project)
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
        csatolmanyok=_diszpo_csatolmanyok(db, project),
        thread_id=project.gmail_thread_id,
        in_reply_to=project.gmail_last_message_id,
        sender_name=settings.dispo_sender_name,
        extra_cc=masolat_cimzettek(db),
    )

    # A levél kiment - ezt AZONNAL elkönyveljük és commitoljuk, mielőtt a
    # küldés utáni kényelmi lépések (Drive archiválás, utókövetés ütemezése)
    # bármelyike elhasalhatna: a "Kiküldve" állapotnak egy ténylegesen kiment
    # levél után akkor is meg kell maradnia, ha a ráadás-lépések hibáznak.
    project.diszpo = "Kiküldve"
    project.gmail_thread_id = thread_id or project.gmail_thread_id
    project.gmail_last_message_id = rfc822 or project.gmail_last_message_id
    project.aki_kikuldte_a_diszpot = [current_user.full_name]
    db.commit()

    pdf_link = _pdf_a_drive_ra(project, pdf_bytes)
    project.drive_diszpo_pdf_url = pdf_link or doc_link or project.drive_diszpo_pdf_url
    _schedule_utokovetes_email(project)
    db.commit()
    db.refresh(project)
    return {
        "status": "OK",
        "message": "Diszpó elküldve.",
        "thread_id": project.gmail_thread_id,
        "doc_link": doc_link,
        "pdf_link": pdf_link,
    }
