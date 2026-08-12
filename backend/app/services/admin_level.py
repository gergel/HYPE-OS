"""Az ADMIN FIÓKBÓL kimenő levelek közös burka.

A megrendelői papírok egy része nem a gyártás nevében megy, hanem az admin
fiókból (MODOSITAS_SENDER, alapból admin@hypest.hu), és a levél aláírása az
abban a fiókban BEÁLLÍTOTT Gmail-aláírás - nem egy külön, itt karbantartott
szöveg. Így ha valaki a Gmailben átírja az aláírást, a HYPE OS-ből kimenő
levél is azzal megy, anélkül hogy ehhez a kódhoz bárki hozzányúlna.

Miért külön modul? Mert ugyanez kell a keretszerződéshez és a
szerződésmódosításhoz is. Két másolatból előbb-utóbb két különböző aláírás
lenne ugyanattól a feladótól."""

from __future__ import annotations

from html import escape

from app.core.config import settings
from app.services.google_email import sendas_adatok

#: Ha a fiókban nincs beállított aláírás (vagy nem tudjuk kiolvasni), ez megy
#: a levél aljára. Nem véletlenül semleges: a valódi aláírás helye a Gmail.
TARTALEK_ALAIRAS = "<p>Üdvözlettel,<br>HYPE Productions Kft.</p>"


def szoveg_html(szoveg: str) -> str:
    """Sima szöveg -> a levél HTML törzse.

    A felhasználó egy sima szövegdobozba ír, a levél viszont HTML - a kettő
    között valakinek fordítania kell. Az üres sorok bekezdést, az egyszerű
    sortörések `<br>`-t adnak.

    A tartalmat ESCAPE-eljük: egy `<` a szövegben (pl. "díj < 100e") elrontaná
    a levél szerkezetét, egy beillesztett HTML-részlet pedig olyat is
    megjeleníthetne, amire a küldő nem számít."""
    bekezdesek = [b.strip() for b in szoveg.replace("\r\n", "\n").split("\n\n") if b.strip()]
    return "".join(f"<p>{escape(b).replace(chr(10), '<br>')}</p>" for b in bekezdesek)


def felado_es_torzs(torzs_html: str) -> tuple[str | None, str]:
    """(feladónév, kész levéltörzs) - mindkettő a küldő fiók beállításából.

    Egy lekérdezés adja a megjelenő nevet és az aláírást is; ezért jönnek
    együtt. Ha a fiók beállításai nem olvashatók, a név marad a globális
    alapérték, az aláírás pedig a beépített tartalék - egy hiányzó aláírás nem
    ér annyit, hogy egy kiküldés elhasaljon rajta.

    A törzset HTML-ként várja: van, ahol a felhasználó gépeli (lásd
    `szoveg_html`), és van, ahol kész sablonszöveg megy ki."""
    nev, alairas = sendas_adatok(settings.modositas_sender)
    return nev, torzs_html + (alairas or TARTALEK_ALAIRAS)
