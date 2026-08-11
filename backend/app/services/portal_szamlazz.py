"""Számla kiállítása a Számlázz.hu Számla Agenttel - a Média Portál fizetős
tárhely-hosszabbításához.

A Hype-repo-main (különálló client-portál projekt) szamlazz.py portja. A
folyamat: a vevő a portál fizetési űrlapján megadja a számlázási adatait, azok
a Payment sorba kerülnek, és a Barion sikeres visszahívása után ez a modul
állítja ki a számlát (lásd routes/portal_public.py barion_callback).

Agent kulcs nélkül nem hibázunk, csak visszajelezzük, hogy nem történt semmi:
a fizetés akkor is érvényes, ha a számlázás nincs beállítva - a pénz megjött,
a számlát legfeljebb kézzel kell kiállítani."""

from __future__ import annotations

import logging
from datetime import date
from xml.sax.saxutils import escape

import httpx

from app.core.config import settings

logger = logging.getLogger("hype_os")

SZAMLAZZ_URL = "https://www.szamlazz.hu/szamla/"

#: A számla tételének ÁFA kulcsa. A tárhely-hosszabbítás normál adókulcsos
#: szolgáltatás, ezért fix - ha valaha más kell, a hívó adja meg.
ALAP_AFA_KULCS = 27


def create_invoice(
    *,
    buyer_name: str,
    buyer_zip: str,
    buyer_city: str,
    buyer_address: str,
    buyer_tax_number: str = "",
    buyer_email: str = "",
    item_name: str,
    gross_amount: int,
    vat_rate: int = ALAP_AFA_KULCS,
) -> dict:
    """ÁFA-s e-számla kiállítása. A `gross_amount` BRUTTÓ forint.

    A nettót és az ÁFA-t visszaszámoljuk a bruttóból (forintra kerekítve), mert
    a portálon a vevő bruttó árat lát és bruttót fizet - a számlának pontosan
    annyiról kell szólnia, amennyit levontunk.

    Visszaad: {"ok": bool, "invoice_number": str, "error": str}"""
    if not settings.szamlazz_agent_key:
        return {"ok": False, "invoice_number": "", "error": "Nincs beállítva Számlázz.hu agent kulcs."}

    netto = round(gross_amount / (1 + vat_rate / 100))
    afa = gross_amount - netto
    ma = date.today().isoformat()

    # Adószám csak cégnél megy ki; magánszemélynél a mező hiánya a helyes.
    adoszam_sor = f"<adoszam>{escape(buyer_tax_number)}</adoszam>" if buyer_tax_number else ""
    email_sor = f"<email>{escape(buyer_email)}</email>" if buyer_email else ""

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<xmlszamla xmlns="http://www.szamlazz.hu/xmlszamla" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.szamlazz.hu/xmlszamla https://www.szamlazz.hu/szamla/docs/xsds/agent/xmlszamla.xsd">
  <beallitasok>
    <szamlaagentkulcs>{escape(settings.szamlazz_agent_key)}</szamlaagentkulcs>
    <eszamla>true</eszamla>
    <szamlaLetoltes>false</szamlaLetoltes>
    <valaszVerzio>2</valaszVerzio>
  </beallitasok>
  <fejlec>
    <keltDatum>{ma}</keltDatum>
    <teljesitesDatum>{ma}</teljesitesDatum>
    <fizetesiHataridoDatum>{ma}</fizetesiHataridoDatum>
    <fizmod>Bankkártya</fizmod>
    <penznem>HUF</penznem>
    <szamlaNyelve>hu</szamlaNyelve>
    <megjegyzes>Online tárhely-hosszabbítás</megjegyzes>
  </fejlec>
  <elado></elado>
  <vevo>
    <nev>{escape(buyer_name)}</nev>
    <irsz>{escape(buyer_zip)}</irsz>
    <telepules>{escape(buyer_city)}</telepules>
    <cim>{escape(buyer_address)}</cim>
    {email_sor}
    {adoszam_sor}
  </vevo>
  <tetelek>
    <tetel>
      <megnevezes>{escape(item_name)}</megnevezes>
      <mennyiseg>1</mennyiseg>
      <mennyisegiEgyseg>db</mennyisegiEgyseg>
      <nettoEgysegar>{netto}</nettoEgysegar>
      <afakulcs>{vat_rate}</afakulcs>
      <nettoErtek>{netto}</nettoErtek>
      <afaErtek>{afa}</afaErtek>
      <bruttoErtek>{gross_amount}</bruttoErtek>
    </tetel>
  </tetelek>
</xmlszamla>"""

    try:
        valasz = httpx.post(
            SZAMLAZZ_URL,
            files={"action-xmlagentxmlfile": ("invoice.xml", xml, "text/xml")},
            timeout=30,
        )
        szoveg = valasz.text or ""
    except Exception as exc:  # noqa: BLE001 - a hálózati hiba is válasz a hívónak
        logger.exception("Számlázz.hu hívás nem sikerült")
        return {"ok": False, "invoice_number": "", "error": str(exc)}

    if "<sikeres>true</sikeres>" in szoveg or "sikeres>true" in szoveg:
        szamlaszam = ""
        if "<szamlaszam>" in szoveg:
            szamlaszam = szoveg.split("<szamlaszam>")[1].split("</szamlaszam>")[0]
        return {"ok": True, "invoice_number": szamlaszam, "error": ""}

    # A hibaüzenetet megvágjuk: a Számlázz.hu néha egész XML-t küld vissza, az
    # egészet nem érdemes naplóba és adatbázisba vinni.
    return {"ok": False, "invoice_number": "", "error": szoveg[:300]}
