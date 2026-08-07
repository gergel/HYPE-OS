"""Álló (alvállalkozói) keretszerződés generálása és kiküldése.

A csatolt "alvallalkozo-keret" Railway program (main.py + notion.py + gdocs.py
+ gmail.py) portolása: Google Docs sablon másolása, a {{...}} helyőrzők
kitöltése a megbízott cégadataiból, PDF export, majd kiküldés e-mailben.

Két dolog szándékosan tér el az eredetitől:

- Az eredeti program a Notiont pásztázta ("Keretszerződés küld" pipa +
  "Nincs feltöltve" állapot), és 5 percenként futott. Itt nincs mit
  pásztázni: a felhasználó a Keretszerződések oldalon kattint, tehát a
  kiküldés KÉZI, egy szerződésre szól - ez fedi le a kérést is ("legyen opció
  … új kiküldésére", pl. mert a régi lejárt).
- A PDF nem megy ki a lemezre: a Railway fájlrendszere efemer, ezért a
  meglévő gdoc_template.py memóriában adja vissza (ugyanaz a minta, mint az
  eseti szerződésnél és a TIG-eknél).

Az állapot az eredeti program szerint "Kiküldve/aláírásra vár" lesz.
"""
from __future__ import annotations

from datetime import date

from app.core.config import settings
from app.models.contract import Contract
from app.models.employee import Employee
from app.services.gdoc_template import gdoc_fill_and_export_pdf
from app.services.google_email import send_message

#: A kiküldés utáni állapot - a csatolt program mark_item_sent()-je ezt írta a
#: Notion "Állapot" mezőjébe.
KIKULDVE_ALLAPOT = "Kiküldve/aláírásra vár"

#: A feladó neve a levélben (a csatolt gmail.py from_name-je).
FELADO_NEV = "HYPE Productions - ADMINISZTRÁCIÓ"

#: A levél törzse - a csatolt gmail.py html_content-je, változatlan szöveggel
#: és aláírás-blokkal (ugyanaz, mint az eseti szerződésnél: lásd
#: api/routes/subcontractor_contracts.py _CONTRACT_EMAIL_HTML).
EMAIL_HTML = """\
<body style="font-family: Arial, sans-serif; font-size: 14px; color: #000;">
  <p>Kedves Címzett,</p>
  <p>
    Levelemhez csatoltan küldöm a tárgyban említett dokumentumot.<br>
    Kérjük a szükséges dokumentációhoz (teljesítés igazolása, számlázás és kifizetés), aláírva és/vagy
    pecsételve küldd vissza számunkra a csatolt dokumentumot, válasz e-mailben.
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
</body>
"""


class KeretszerzodesHiba(Exception):
    """Amit a felhasználónak kell megjavítania (hiányzó cégadat, e-mail cím)."""


def cimzettek(szerzodes: Contract, employee: Employee | None) -> list[str]:
    """Kinek megy a levél: a szerződésen tárolt e-mail, egyébként a munkatársé.

    A csatolt program a Notion "Vállalkozó" relationjén ült e-mailt használta;
    nálunk ugyanez a cégadat a szerződés-soron, illetve a munkatárs lapján van."""
    jeloltek = [szerzodes.email, employee.email if employee else None]
    return [c.strip() for c in jeloltek if c and c.strip()]


def _mezok(szerzodes: Contract, employee: Employee | None, keltezes: date) -> dict[str, str]:
    """A sablon {{...}} helyőrzői - a csatolt gdocs.py mezőkészlete."""
    return {
        "nev": szerzodes.ceg_neve or (employee.vallakozas_neve if employee else None) or "",
        "hely": szerzodes.szekhely or (employee.vallakozas_szekhely if employee else None) or "",
        "adoszam": szerzodes.adoszam or (employee.vallalkozas_adoszama if employee else None) or "",
        "targy": szerzodes.megbizas_targya or (employee.megbizas_targya if employee else None) or "",
        "kelt": keltezes.strftime("%Y.%m.%d."),
        "nyilvszam": szerzodes.vallalkozas_nyilvantartasi_szam
        or (employee.nyilvantartasi_szam if employee else None)
        or "",
        "kepvis": szerzodes.vallalkozas_kepviseloje or (employee.vallalkozas_kepviselo if employee else None) or "",
    }


def generalas_es_kuldes(
    szerzodes: Contract, employee: Employee | None, *, keltezes: date | None = None
) -> tuple[str, list[str]]:
    """Legenerálja és kiküldi a keretszerződést. (doc_link, címzettek) párt ad.

    A hívó dolga a szerződés-sor frissítése (állapot, fájl-link) és a commit -
    így a végpont dönti el, mit tegyen, ha a küldés elhasal."""
    if not settings.keretszerzodes_template_id:
        raise KeretszerzodesHiba(
            "Nincs beállítva a keretszerződés Google Docs sablonja "
            "(GDOC_KERETSZERZODES_TEMPLATE_ID)."
        )
    cim = cimzettek(szerzodes, employee)
    if not cim:
        raise KeretszerzodesHiba(
            "Nincs e-mail cím sem a szerződésen, sem a munkatárs adatlapján - "
            "előbb töltsd ki, hova menjen a szerződés."
        )
    mezok = _mezok(szerzodes, employee, keltezes or szerzodes.keltezes or date.today())
    if not mezok["nev"]:
        raise KeretszerzodesHiba("Hiányzik a cég neve - enélkül nem lehet szerződést kiállítani.")

    base_name = f"{mezok['nev']}_megbizasi_keretszerzodes"
    pdf_bytes, new_doc_id = gdoc_fill_and_export_pdf(
        template_file_id=settings.keretszerzodes_template_id,
        base_name=base_name,
        fields=mezok,
        output_folder_id=settings.keretszerzodes_folder_id or None,
    )
    send_message(
        cim,
        f"{mezok['nev']}_megbízási keretszerződés",
        EMAIL_HTML,
        pdf_bytes=pdf_bytes,
        pdf_filename=f"{base_name}.pdf",
        sender_name=FELADO_NEV,
    )
    return f"https://docs.google.com/document/d/{new_doc_id}/edit", cim
