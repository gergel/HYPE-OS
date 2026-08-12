"""Szerződésmódosítás a megrendelői keretszerződéshez: generálás + kiküldés.

Ugyanaz a menet, mint a keretszerződésnél (Google Docs sablon kitöltése ->
PDF -> Drive mappa -> e-mail), három eltéréssel:

1. **Más címről megy.** A módosítás az admin fiókból megy ki (MODOSITAS_SENDER,
   alapból admin@hypest.hu), és a levél aláírása az abban a fiókban BEÁLLÍTOTT
   Gmail-aláírás - nem egy külön, itt karbantartott szöveg. Így ha valaki a
   Gmailben átírja az aláírást, a HYPE OS-ből kimenő levél is azzal megy,
   anélkül hogy ehhez a kódhoz bárki hozzányúlna.
2. **Nem a kiküldés a végállomás.** A módosítás akkor ér valamit, ha aláírva
   visszajön - a kiküldés utáni állapot ezért "Aláírásra vár", és a folyamatot
   az aláírt példány feltöltése zárja le (lásd models/keret_modositas.py).
3. **Több is lehet belőle.** Minden kiküldés új sort nyit, mert egy
   keretszerződést az évek alatt többször is módosítanak.
4. **A kísérőlevelet a felhasználó írja.** A többi papír fix szöveggel megy; itt
   a levél maga is része az ügynek (mit módosítunk, mire hivatkozva), ezért a
   kiküldés előtt szerkeszthető, és amit kiküldtünk, azt el is tesszük.

A sablon placeholder-nevei megegyeznek a keretszerződésével ({{nev}} {{hely}}
{{nyilvszam}} {{adoszam}} {{kepvis}}), tehát a meglévő dokumentum változtatás
nélkül használható."""

from __future__ import annotations

from datetime import date, datetime, timezone
from html import escape

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.contract import Contract
from app.models.employee import Employee
from app.models.keret_modositas import KeretModositas
from app.services import gdoc_template
from app.services.google_email import sendas_adatok, send_message

#: Ha a fiókban nincs beállított aláírás (vagy nem tudjuk kiolvasni), ez megy
#: a levél aljára. Nem véletlenül semleges: a valódi aláírás helye a Gmail.
TARTALEK_ALAIRAS = "<p>Üdvözlettel,<br>HYPE Productions Kft.</p>"

#: A kísérőlevél alapszövege. A felületen ez töltődik be a szerkeszthető
#: mezőbe, tehát a felhasználó minden kiküldésnél átírhatja - ez csak a
#: kiindulás, és az API-ból érkező, szöveg nélküli hívás tartaléka.
#: Ha itt változik, változtasd a frontend ALAP_LEVEL_SZOVEG-ét is
#: (components/megrendeloi/KeretModositasok.tsx).
ALAP_LEVEL_SZOVEG = """\
Kedves Partnerünk!

Mellékelten küldjük a köztünk fennálló megbízási szerződés módosítását.
Kérjük, ellenőrizzék az adatokat, és aláírva szíveskedjenek visszaküldeni."""


def szoveg_html(szoveg: str) -> str:
    """Sima szöveg -> a levél HTML törzse.

    A felhasználó egy sima szövegdobozba ír, a levél viszont HTML - a
    kettő között valakinek fordítania kell. Az üres sorok bekezdést, az
    egyszerű sortörések `<br>`-t adnak.

    A tartalmat ESCAPE-eljük: egy `<` a szövegben (pl. "díj < 100e") elrontaná
    a levél szerkezetét, egy beillesztett HTML-részlet pedig olyat is
    megjeleníthetne, amire a küldő nem számít."""
    bekezdesek = [b.strip() for b in szoveg.replace("\r\n", "\n").split("\n\n") if b.strip()]
    return "".join(f"<p>{escape(b).replace(chr(10), '<br>')}</p>" for b in bekezdesek)


def sablon_mezok(c: Contract) -> dict[str, str]:
    """A dokumentumba behelyettesített értékek - a MEGBÍZÓ (a megrendelő) adatai."""
    return {
        "nev": c.ceg_neve or (c.client.nev if c.client else "") or "",
        "hely": c.szekhely or "",
        "nyilvszam": c.vallalkozas_nyilvantartasi_szam or "",
        "adoszam": c.adoszam or "",
        "kepvis": c.vallalkozas_kepviseloje or "",
    }


def celmappa() -> str | None:
    """Hova kerüljön a kész PDF a Drive-on.

    Saját mappa -> keretszerződések mappája -> generikus kimeneti mappa -> a
    SABLON saját mappája. Az utolsó lépcső azért van, hogy beállítás nélkül se
    a Drive gyökerébe szóródjanak a módosítások: ahol a sablon van, oda való a
    belőle készült papír is."""
    beallitott = (
        settings.gdoc_keret_modositas_folder_id
        or settings.gdoc_keretszerzodes_folder_id
        or settings.gdoc_output_folder_id
    )
    if beallitott:
        return beallitott
    try:
        return gdoc_template.szulo_mappa(settings.gdoc_keret_modositas_template_id)
    except Exception:  # noqa: BLE001 - a mappa kiderítése ne bukjon meg a kiküldésen
        return None


def level_adatok(szoveg: str | None = None) -> tuple[str | None, str]:
    """(feladónév, kész levéltörzs) a megírt szövegből.

    A feladónév és az aláírás is a küldő fiók Gmail-beállításából jön - egy
    lekérdezés adja mindkettőt, ezért jönnek együtt. Ha a beállítás nem
    olvasható, a név marad a globális alapérték, az aláírás a beépített
    tartalék. Az ALÁÍRÁST mindig mi tesszük a végére: azt nem a felhasználó
    gépeli be minden alkalommal."""
    nev, alairas = sendas_adatok(settings.modositas_sender)
    torzs = szoveg_html((szoveg or "").strip() or ALAP_LEVEL_SZOVEG)
    return nev, torzs + (alairas or TARTALEK_ALAIRAS)


def uj_modositas(c: Contract, *, keltezes: date | None = None) -> KeretModositas:
    """Üres módosítás-sor a keret ADATAINAK PILLANATKÉPÉVEL.

    A cégadatokat itt másoljuk át, nem kiküldéskor olvassuk ki élőben: a papír
    azt kell hogy őrizze, ami rajta van (lásd models/keret_modositas.py)."""
    return KeretModositas(
        contract_id=c.id,
        ceg_neve=c.ceg_neve or (c.client.nev if c.client else None),
        szekhely=c.szekhely,
        adoszam=c.adoszam,
        kepviselo=c.vallalkozas_kepviseloje,
        nyilvantartasi_szam=c.vallalkozas_nyilvantartasi_szam,
        email=c.email,
        keltezes=keltezes or date.today(),
        allapot="Készítés alatt",
    )


def fajlnev(c: Contract) -> str:
    nev = c.ceg_neve or (c.client.nev if c.client else None) or f"keret-{c.id}"
    return f"{nev}_szerzodesmodositas"


def generalj_es_kuldj(
    db: Session, c: Contract, user: Employee | None, *, level_szoveg: str | None = None
) -> KeretModositas:
    """A módosítás legyártása és kiküldése. Hibánál RuntimeError-t dob.

    A sorrend szándékos: a sort ELŐBB felvesszük, de csak a sikeres kiküldés
    után jelöljük kiküldöttnek. Ha a generálás vagy a levél elhasal, a
    módosítás "Készítés alatt" marad, és látszik, hogy hol akadt el - nem
    tűnik el nyomtalanul, de nem is állítja azt magáról, hogy kiment."""
    if not (c.email or "").strip():
        raise RuntimeError("Nincs e-mail cím a keretszerződésen, így nem lehet kiküldeni a módosítást.")
    if not settings.gdoc_keret_modositas_template_id:
        raise RuntimeError(
            "Nincs beállítva a szerződésmódosítás sablonja. Állítsd be a "
            "GDOC_KERET_MODOSITAS_TEMPLATE_ID környezeti változót a backendhez."
        )

    m = uj_modositas(c)
    db.add(m)
    db.flush()

    alap_nev = fajlnev(c)
    pdf_bytes, pdf_link = gdoc_template.gdoc_fill_export_and_store_pdf(
        template_file_id=settings.gdoc_keret_modositas_template_id,
        base_name=alap_nev,
        fields=sablon_mezok(c),
        output_folder_id=celmappa(),
    )
    m.file_url = pdf_link

    nev = c.ceg_neve or (c.client.nev if c.client else "") or "Partnerünk"
    felado_nev, torzs = level_adatok(level_szoveg)
    send_message(
        [c.email],
        f"{nev} – szerződésmódosítás",
        torzs,
        pdf_bytes=pdf_bytes,
        pdf_filename=f"{alap_nev}.pdf",
        sender_name=felado_nev,
        sender_email=settings.modositas_sender,
    )

    # A kiküldött szöveget úgy tesszük el, ahogy ténylegesen kiment - beleértve
    # azt is, ha a felhasználó nem írt semmit, és az alapszöveg ment.
    m.level_szoveg = (level_szoveg or "").strip() or ALAP_LEVEL_SZOVEG
    m.allapot = "Aláírásra vár"
    m.kikuldve = datetime.now(timezone.utc)
    m.kikuldte_id = user.id if user else None
    return m
