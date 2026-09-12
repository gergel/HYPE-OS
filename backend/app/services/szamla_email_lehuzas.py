"""A szamla@hypestab.hu címre érkező számlák LEHÚZÁSA a Gmail-fiókból.

MIÉRT GMAIL-POLL? A rendszer levelezése a meglévő Gmail-integráción megy
(lásd services/google_email.py), és a hitelesítésben a `gmail.readonly` scope
MÁR benne van - tehát a bejövő leveleket ugyanazzal a hitelesítéssel tudjuk
olvasni, DNS/MX átállítás és új szolgáltató nélkül. A feltétel: a
szamla@hypestab.hu címre érkező levél a hitelesített fiókban landoljon
(alias vagy továbbítás - lásd az admin-teendőket a route docstringjében).

CSAK KÉZI INDÍTÁSRA fut (a felhasználó kérése: automatikusan ne hozzon át
semmit), és CSAK AZ OLVASATLAN leveleket nézi - amit a postafiókban már
elolvastak, azt nem bolygatja.

IDEMPOTENCIA: az olvasatlan-szűrő MELLETT minden látott Gmail-üzenet a
`bejovo_emailek` táblába is bekerül a Gmail-azonosítójával; ami ott van, azt
másodszor nem dolgozzuk fel - így az sem duplikál, ha egy behozott levél
olvasatlan marad a fiókban és a lehúzást újra megnyomják. Az eredeti levelet
nem töröljük, nem jelöljük olvasottnak és nem is válaszolunk rá.

A csatolmányokból piszkozat készül (lásd services/szamla_erkeztetes.py):
- a nyilvánvalóan nem-számla mellékletek (kis képek: logó, aláírás) kimaradnak;
- a PDF+XML párok egy dokumentumként kapcsolódnak össze;
- a melléklet nélküli, csak linket tartalmazó levél is piszkozatot kap
  ("Pontosítás szükséges") - nem vész el, de automatikus letöltés nincs."""

from __future__ import annotations

import base64
import logging
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.bejovo_szamla import BejovoEmail, BejovoSzamla
from app.models.employee import Employee, SystemRole, van_szerepkore
from app.services import notifications, szamla_erkeztetes
from app.services.google_email import _extract_header, _gmail_service

logger = logging.getLogger(__name__)

#: Ennél kisebb kép szinte biztosan logó/aláírás, nem számlafotó.
MIN_KEP_MERET = 30 * 1024

FELDOLGOZHATO_MIME = szamla_erkeztetes.ENGEDETT_MIME | szamla_erkeztetes.XML_MIME


def _cel_cim() -> str:
    return (settings.szamla_bejovo_cim or "szamla@hypestab.hu").strip()


def _legkorabbi_nap() -> date:
    """A lehúzás fix alsó dátumhatára (a felhasználó kérése: 2026. 09. 01.
    előtti levelet SOHA ne nézzünk) - env-ből (SZAMLA_EMAIL_KEZDET) írható át."""
    try:
        return date.fromisoformat((settings.szamla_email_kezdet or "").strip())
    except ValueError:
        return date(2026, 9, 1)


def _query(kezdo_datum: date | None) -> str:
    # CSAK AZ OLVASATLAN leveleket hozzuk be (a felhasználó kérése): amit a
    # postafiókban már elolvastak/lerendeztek, azt a lehúzás békén hagyja. A
    # kettős védelem megmarad: az olvasatlanok közül is csak az kerül be, ami
    # a bejovo_emailek naplóban még nem szerepel. A csatolmány-kérdést
    # üzenetenként döntjük el (a linkes levél is kapjon piszkozatot).
    #
    # DÁTUMHATÁR: mindig van alsó korlát (lásd _legkorabbi_nap) - a kért
    # kezdődátum csak SZŰKÍTHETI az időszakot, régebbre nem nyithatja ki.
    # A Gmail "after:" a megadott nap 0:00-jától értendő, tehát maga a
    # határnap még benne van.
    legkorabbi = _legkorabbi_nap()
    hatar = kezdo_datum if kezdo_datum and kezdo_datum > legkorabbi else legkorabbi
    return f"to:{_cel_cim()} is:unread after:{hatar.strftime('%Y/%m/%d')}"


def _uzenet_lista(svc, kezdo_datum: date | None, limit: int) -> list[str]:
    idk: list[str] = []
    token = None
    while len(idk) < limit:
        valasz = (
            svc.users()
            .messages()
            .list(userId="me", q=_query(kezdo_datum), maxResults=min(100, limit - len(idk)), pageToken=token)
            .execute()
        )
        idk.extend(m["id"] for m in valasz.get("messages", []))
        token = valasz.get("nextPageToken")
        if not token:
            break
    return idk


def _resz_szoveg(payload: dict) -> str:
    """A levél szöveg-törzse (text/plain előnyben) - a besoroláshoz kell."""
    darabok: list[str] = []

    def jar(p: dict) -> None:
        mime = p.get("mimeType", "")
        if mime == "text/plain" and p.get("body", {}).get("data"):
            try:
                darabok.append(base64.urlsafe_b64decode(p["body"]["data"]).decode("utf-8", "replace"))
            except Exception:  # noqa: BLE001
                pass
        for gyerek in p.get("parts") or []:
            jar(gyerek)

    jar(payload)
    return "\n".join(darabok)[:4000]


def _csatolmanyok(svc, uzenet_id: str, payload: dict) -> list[tuple[str, str, bytes]]:
    """(fájlnév, mime, tartalom) hármasok - csak a feldolgozható típusok."""
    eredmeny: list[tuple[str, str, bytes]] = []

    def jar(p: dict) -> None:
        fajlnev = p.get("filename") or ""
        mime = (p.get("mimeType") or "").split(";")[0].lower()
        body = p.get("body") or {}
        if fajlnev and mime in FELDOLGOZHATO_MIME:
            adat = None
            if body.get("attachmentId"):
                letoltott = (
                    svc.users()
                    .messages()
                    .attachments()
                    .get(userId="me", messageId=uzenet_id, id=body["attachmentId"])
                    .execute()
                )
                adat = base64.urlsafe_b64decode(letoltott.get("data", ""))
            elif body.get("data"):
                adat = base64.urlsafe_b64decode(body["data"])
            if adat:
                # Logó/aláírás-szűrő: a pár kilobájtos kép nem számla.
                if mime.startswith("image/") and len(adat) < MIN_KEP_MERET:
                    return
                eredmeny.append((fajlnev, mime, adat))
        for gyerek in p.get("parts") or []:
            jar(gyerek)

    jar(payload)
    return eredmeny


def _ertesites(db: Session, targy: str, darab: int) -> None:
    """Egy ÉRTESÍTÉS levelenként a számla-ellenőrzésre jogosultaknak (admin +
    adminisztráció) - nem minden technikai lépésről, csak arról, hogy van új
    ellenőrizendő tétel."""
    try:
        cimzettek = [
            e
            for e in db.scalars(select(Employee).where(Employee.is_active.is_(True))).all()
            if van_szerepkore(e, SystemRole.ADMIN) or van_szerepkore(e, SystemRole.ADMINISZTRACIO)
        ]
        for e in cimzettek:
            notifications.create_notification(
                db,
                employee_id=e.id,
                kind="bejovo_szamla",
                message=f"Új beérkező számla ellenőrzésre: {targy[:80] or '(tárgy nélkül)'} ({darab} dokumentum)",
                link="/penzugyek/bejovo-szamlak",
            )
        db.commit()
    except Exception:  # noqa: BLE001 - az értesítés nem állíthatja meg a lehúzást
        db.rollback()
        logger.exception("Beérkező számla értesítés nem ment ki")


def lehuzas(
    db: Session,
    *,
    kezdo_datum: date | None = None,
    limit: int = 50,
    csak_elonezet: bool = False,
    naplo=lambda s: None,
) -> dict:
    """A célcímre érkezett levelek feldolgozása. `csak_elonezet`: nem hoz létre
    semmit, csak megmutatja, MI TÖRTÉNNE (a régi levelek visszamenőleges
    feldolgozása előtt ezt érdemes megnézni)."""
    svc = _gmail_service()
    uzenet_idk = _uzenet_lista(svc, kezdo_datum, limit)
    naplo(f"{len(uzenet_idk)} levél a keresésben ({_query(kezdo_datum)})")

    mar_lattuk = {
        e.gmail_uzenet_id
        for e in db.scalars(select(BejovoEmail).where(BejovoEmail.gmail_uzenet_id.in_(uzenet_idk)))
    }
    elonezet: list[dict] = []
    uj_szamlak = 0
    feldolgozott_level = 0
    kihagyott_korabbi = 0
    hibas_level = 0

    for uzenet_id in uzenet_idk:
        if uzenet_id in mar_lattuk:
            # Korábban már átvett vagy a resetnél kizárt üzenet - akkor sem
            # jön át újra, ha a postafiókban olvasatlan maradt.
            kihagyott_korabbi += 1
            continue
        uzenet = svc.users().messages().get(userId="me", id=uzenet_id, format="full").execute()
        payload = uzenet.get("payload") or {}
        fejlecek = payload.get("headers") or []
        felado = _extract_header(fejlecek, "From") or ""
        targy = _extract_header(fejlecek, "Subject") or ""
        beerkezes = datetime.fromtimestamp(int(uzenet.get("internalDate", 0)) / 1000, tz=timezone.utc)
        if beerkezes.date() < _legkorabbi_nap():
            # Kettős védelem a Gmail-szűrő mellett: a dátumhatár előtti levél
            # akkor sem jön be, ha a keresés valamiért visszaadta.
            kihagyott_korabbi += 1
            continue
        szoveg = _resz_szoveg(payload)
        csatolmanyok = _csatolmanyok(svc, uzenet_id, payload)

        if csak_elonezet:
            elonezet.append(
                {
                    "felado": felado,
                    "targy": targy,
                    "beerkezes": beerkezes.isoformat(),
                    "csatolmanyok": [f"{nev} ({mime}, {len(adat) // 1024} kB)" for nev, mime, adat in csatolmanyok],
                }
            )
            continue

        email_meta = {
            "uzenet_id": uzenet_id,
            # A TOVÁBBÍTÓ feladó nem azonos a számla kibocsátójával - ezért
            # csak metaadatként őrizzük, a kibocsátót a dokumentum adja.
            "felado": felado[:300],
            "targy": targy[:500],
            "beerkezes": beerkezes,
            "szoveg": szoveg,
        }
        letrejott = 0
        try:
            for nev, mime, adat in csatolmanyok:
                bejovo = szamla_erkeztetes.letrehozas(
                    db,
                    forras="email",
                    adat=adat,
                    fajl_nev=nev,
                    content_type=mime,
                    email_meta=email_meta,
                )
                szamla_erkeztetes.feldolgoz(db, bejovo, adat=adat)
                letrejott += 1
            if not csatolmanyok:
                # Melléklet nélküli levél (pl. csak számlaletöltő link): ne
                # vesszen el - fájl nélküli, pontosítandó piszkozat készül.
                bejovo = szamla_erkeztetes.letrehozas(
                    db, forras="email", adat=None, fajl_nev=None, content_type=None, email_meta=email_meta
                )
                szamla_erkeztetes.feldolgoz(db, bejovo)
                letrejott += 1
            db.add(
                BejovoEmail(
                    gmail_uzenet_id=uzenet_id,
                    felado=felado[:300],
                    targy=targy[:500],
                    beerkezes=beerkezes,
                    allapot="feldolgozva" if csatolmanyok else "nincs_csatolmany",
                    letrehozott_szamla_db=letrejott,
                )
            )
            db.commit()
            uj_szamlak += letrejott
            feldolgozott_level += 1
            naplo(f"Feldolgozva: {targy[:60]} ({letrejott} dokumentum)")
            _ertesites(db, targy, letrejott)
        except Exception as exc:  # noqa: BLE001 - egy rossz levél ne állítsa meg a többit
            db.rollback()
            logger.exception("Számla-email feldolgozási hiba (%s)", uzenet_id)
            db.add(
                BejovoEmail(
                    gmail_uzenet_id=uzenet_id,
                    felado=felado[:300],
                    targy=targy[:500],
                    beerkezes=beerkezes,
                    allapot="hiba",
                    megjegyzes=str(exc)[:1000],
                )
            )
            db.commit()
            hibas_level += 1
            naplo(f"HIBA: {targy[:60]} - {exc}")

    return {
        # KÜLÖN számoljuk a leveleket és a belőlük készült számlákat (a
        # felhasználó kérése): hány olvasatlan levelet vizsgáltunk, hányból
        # lett új számla, hány korábbi/kizárt maradt ki, és mi hibázott.
        "talalt_level": len(uzenet_idk),
        "uj_level": feldolgozott_level,
        "uj_szamla": uj_szamlak,
        "kihagyott_korabbi": kihagyott_korabbi,
        "hibas_level": hibas_level,
        "elonezet": elonezet if csak_elonezet else None,
    }
