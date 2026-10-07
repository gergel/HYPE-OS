"""Alvállalkozói szerződés: "kérjük, küldd vissza aláírva" emlékeztető.

Ha egy kiküldött eseti szerződés VARAKOZAS (7 nap) alatt sem jött vissza
aláírva (nem töltöttük fel az aláírt példányt, és kézzel sem jelöltük
aláírtnak), a felület felajánlja, hogy ugyanarra a címre, ugyanabba a
levélszálba menjen egy válasz-levél. Magától SOHA nem megy ki semmi: a
küldés mindig egy ember gombnyomására történik (lásd
routes/subcontractor_contracts.py emlekezteto_kuldese). Kiküldés után a
következő emlékeztetőt megint csak VARAKOZAS elteltével ajánljuk fel.

A kiküldés nyomát (idő, cím, tárgy, Gmail-szál) a generálás és küldés
rögzíti (kikuldes_rogzitese). A régebben, ennek bevezetése előtt kiküldött
szerződéseknél ez hiányzik: ha a rendszer generálta őket (Google Docs link),
a keltezés napját vesszük a kiküldés napjának, és szál híján új levél megy,
ugyanazzal a tárggyal."""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

from app.models.contract import Contract
from app.services.google_email import ADMIN_ALAIRAS_HTML, elso_ervenyes_cim

UTC = timezone.utc
VARAKOZAS = timedelta(days=7)
KIKULDVE_ALLAPOT = "Kiküldve"

#: Az adminisztrációs aláírás (a szerződés-levéllel azonos - lásd
#: routes/subcontractor_contracts.py _CONTRACT_EMAIL_HTML, és a közös
#: google_email.ADMIN_ALAIRAS_HTML).
SZERZODES_ALAIRAS_HTML = ADMIN_ALAIRAS_HTML

#: Az emlékeztető ALAP szövege (sima szöveg - az üres sor új bekezdés). A
#: küldés előtt átírható (a felhasználó kérése) - lásd level_html.
ALAP_SZOVEG = (
    "Kedves Címzett,\n\n"
    "Néhány napja küldtük a tárgyban említett projektre vonatkozó szerződést, aláírt példány azonban még nem "
    "érkezett vissza hozzánk.\n"
    "Kérjük, a projekt további dokumentációjához (teljesítés igazolása, számlázás és kifizetés) aláírva és/vagy "
    "pecsételve küldd vissza számunkra a szerződést, erre az e-mailre válaszolva.\n\n"
    "Köszönettel,"
)


def level_html(szoveg: str | None = None) -> str:
    """Az emlékeztető levél HTML-je: a (megadott vagy alap) szöveg, alatta
    MINDIG a közös adminisztrációs aláírás. A beírt szöveg escape-elve megy
    (lásd admin_level.szoveg_html) - HTML-t nem lehet becsempészni."""
    from app.services.admin_level import szoveg_html

    return szoveg_html((szoveg or "").strip() or ALAP_SZOVEG) + "<br><br>\n" + SZERZODES_ALAIRAS_HTML


EMLEKEZTETO_HTML = level_html()


def _most() -> datetime:
    return datetime.now(UTC)


def _aware(ido: datetime) -> datetime:
    return ido if ido.tzinfo is not None else ido.replace(tzinfo=UTC)


def kikuldes_rogzitese(
    c: Contract,
    *,
    cimzett: str,
    targy: str,
    kuldes_eredmenye: tuple[str | None, str | None, str | None] | None,
) -> None:
    """A sikeres kiküldés után: mikor, kinek, milyen tárggyal, melyik szálban.
    Új kiküldésnél az emlékeztető-számláló is nulláról indul."""
    thread_id = rfc_id = None
    if isinstance(kuldes_eredmenye, tuple) and len(kuldes_eredmenye) == 3:
        thread_id, _gmail_id, rfc_id = kuldes_eredmenye
    c.kikuldve_at = _most()
    c.kikuldott_cim = cimzett
    c.kikuldott_targy = targy
    c.gmail_thread_id = thread_id
    c.gmail_rfc_message_id = rfc_id
    c.emlekezteto_kuldve_at = None
    c.emlekezteto_db = 0


def kikuldes_ideje(c: Contract) -> datetime | None:
    """Mikor ment ki a szerződés? A rögzített idő, régi szerződésnél a
    rendszer által generált (Google Docs) papír keltezése. A feltöltött saját
    szerződés (sajat-fajl) nem email-ben ment ki - arra nincs mit emlékeztetni."""
    if c.kikuldve_at is not None:
        return _aware(c.kikuldve_at)
    if c.keltezes is not None and (c.szerzodes_file_url or "").startswith("https://docs.google.com/"):
        return datetime.combine(c.keltezes, time(0), tzinfo=UTC)
    return None


def cimzett(c: Contract) -> str | None:
    """Ugyanaz a cím, ahova a szerződés ment; régi szerződésnél a bejegyzés
    címe, végső esetben a számlázó félé."""
    return elso_ervenyes_cim(
        c.kikuldott_cim,
        c.email,
        c.employee.email if c.employee is not None else None,
        c.vallalkozas.email if c.vallalkozas is not None else None,
    )


def varakozik(c: Contract) -> bool:
    """Kiküldve, és még nem jött vissza aláírva."""
    return c.szerzodes_allapota == KIKULDVE_ALLAPOT and not c.alairva and not c.alairt_file_url


def napja(c: Contract, most: datetime | None = None) -> int | None:
    """Hány napja ment ki (és azóta nincs meg aláírva)? None, ha nem vár."""
    ido = kikuldes_ideje(c)
    if ido is None or not varakozik(c):
        return None
    return max(0, ((most or _most()) - ido).days)


def esedekes(c: Contract, most: datetime | None = None) -> bool:
    """Felajánljuk-e most az emlékeztetőt?"""
    most = most or _most()
    ido = kikuldes_ideje(c)
    if ido is None or not varakozik(c) or cimzett(c) is None:
        return False
    if most - ido < VARAKOZAS:
        return False
    if c.emlekezteto_kuldve_at is not None and most - _aware(c.emlekezteto_kuldve_at) < VARAKOZAS:
        return False
    return True


def kovetkezo_felajanlas(c: Contract) -> datetime | None:
    """Mikortól ajánljuk fel (újra) az emlékeztetőt: a kiküldés, ill. az
    előző emlékeztető után VARAKOZAS-sal. None, ha a szerződés nem vár
    aláírásra (vagy nem tudni, mikor ment ki)."""
    ido = kikuldes_ideje(c)
    if ido is None or not varakozik(c):
        return None
    alap = ido
    if c.emlekezteto_kuldve_at is not None:
        alap = max(alap, _aware(c.emlekezteto_kuldve_at))
    return alap + VARAKOZAS


def hatra_napok(c: Contract, most: datetime | None = None) -> int | None:
    """Hány nap múlva ajánljuk fel az emlékeztetőt (0 = már most). A felület
    ezt mutatja a kiküldéstől kezdve (a felhasználó kérése), nem csak a 7.
    nap után."""
    kovetkezo = kovetkezo_felajanlas(c)
    if kovetkezo is None:
        return None
    hatra = kovetkezo - (most or _most())
    if hatra <= timedelta(0):
        return 0
    return hatra.days + (1 if hatra.seconds or hatra.microseconds else 0)


def targya(c: Contract, alap_targy: str | None = None) -> str:
    """Az emlékeztető tárgya: válasz az eredeti szerződés-levélre ("Re: …").
    Az `alap_targy` a régi (rögzített tárgy nélküli) szerződés eredeti tárgya,
    ahogy a kiküldés összerakta."""
    targy = c.kikuldott_targy or alap_targy or "Szerződés"
    if not targy.lower().startswith("re:"):
        targy = f"Re: {targy}"
    return targy


def kuldes(c: Contract, *, send_message, alap_targy: str | None = None, szoveg: str | None = None) -> str:
    """Kiküldi az emlékeztetőt (ugyanarra a címre; ha ismert a szál, abba
    válaszolva), és rögzíti. Visszaadja a címzettet. RuntimeError, ha a
    küldés nem sikerült - ilyenkor semmi nem változik. Az `alap_targy` a
    régi (rögzített tárgy nélküli) szerződés eredeti tárgya, ahogy a
    kiküldés összerakta. A `szoveg` a küldés előtt átírt levélszöveg (üresen
    az ALAP_SZOVEG)."""
    cim = cimzett(c)
    if cim is None:
        raise ValueError("Nincs címzett e-mail cím ehhez a szerződéshez.")
    send_message(
        [cim],
        targya(c, alap_targy),
        level_html(szoveg),
        thread_id=c.gmail_thread_id,
        in_reply_to=c.gmail_rfc_message_id,
    )
    c.emlekezteto_kuldve_at = _most()
    c.emlekezteto_db = (c.emlekezteto_db or 0) + 1
    return cim
