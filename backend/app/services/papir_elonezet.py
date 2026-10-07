"""Alvállalkozói szerződés és külsős TIG: a KIMENŐ papír és az ELŐNÉZETE.

A felhasználó kérése: kiküldés előtt lehessen látni, hogyan néz ki a kimenő
papír. A kiküldés és az előnézet ugyanabból a `KimenoPapir`-ból dolgozik
(lásd routes/subcontractor_contracts._kimeno_szerzodes és
routes/performance_certificates._kimeno_tig), így az előnézet pontosan azt
mutatja, ami kimenne: a levél címzettjét, tárgyát, szövegét, és a kitöltött
dokumentumot PDF-ben."""

from __future__ import annotations

import base64

from pydantic import BaseModel

from app.services.gdoc_template import gdoc_elonezet_pdf


class KimenoPapir(BaseModel):
    """Ami egy papír kiküldésekor ténylegesen kimegy."""

    cimzett: str
    targy: str
    level_html: str
    #: A sablon mezői - None, ha nincs beállítva sablon (akkor PDF sem megy).
    mezok: dict[str, str] | None = None


class ElonezetOut(BaseModel):
    """A kiküldés ELŐNÉZETE: a levél és (kérésre) a kitöltött dokumentum."""

    cimzett: str | None = None
    targy: str
    level_html: str
    #: A kitöltött dokumentum PDF-ben, base64-ben - ha kérték és sikerült.
    pdf_base64: str | None = None
    #: Ha a PDF nem készülhetett el (nincs sablon, Google-hiba) - a levél
    #: előnézete attól még használható.
    pdf_hiba: str | None = None


def elonezet_valasz(kimeno: KimenoPapir, sablon_id: str | None, *, pdf: bool) -> ElonezetOut:
    """Az előnézet válasza; a PDF-et csak kérésre készíti el (Google-hívás)."""
    valasz = ElonezetOut(cimzett=kimeno.cimzett or None, targy=kimeno.targy, level_html=kimeno.level_html)
    if not pdf:
        return valasz
    if kimeno.mezok is None or not sablon_id:
        valasz.pdf_hiba = "Nincs beállítva dokumentum-sablon - a levél PDF melléklet nélkül menne ki."
        return valasz
    try:
        adat = gdoc_elonezet_pdf(template_file_id=sablon_id, base_name=kimeno.targy, fields=kimeno.mezok)
    except Exception as exc:  # noqa: BLE001 - az előnézet ne bukjon el a PDF miatt
        valasz.pdf_hiba = f"A PDF-előnézet most nem készült el: {exc}"
        return valasz
    valasz.pdf_base64 = base64.b64encode(adat).decode("ascii")
    return valasz
