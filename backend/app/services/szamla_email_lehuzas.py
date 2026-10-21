"""A szamla@hypestab.hu címre érkező számlák LEHÚZÁSA a Gmail-fiókból.

MIÉRT GMAIL-POLL? A rendszer levelezése a meglévő Gmail-integráción megy
(lásd services/google_email.py), és a hitelesítésben a `gmail.readonly` scope
MÁR benne van - tehát a bejövő leveleket ugyanazzal a hitelesítéssel tudjuk
olvasni, DNS/MX átállítás és új szolgáltató nélkül. A feltétel: a
szamla@hypestab.hu címre érkező levél a hitelesített fiókban landoljon
(alias vagy továbbítás - lásd az admin-teendőket a route docstringjében).

AUTOMATIKUSAN fut a háttérben (lásd main.py - a gyakoriság a
SZAMLA_AUTO_GYAKORISAG_PERC env-ből állítható, 0 = csak kézi), és a kézi
"Ellenőrzés most" gombról is ugyanez indul. AZ OLVASOTTSÁG NEM SZÁMÍT (a
felhasználó előírása): ha valaki megnyitotta a levelet, a számlát attól még
importálni kell.

IDEMPOTENCIA: a SAJÁT importnyilvántartás dönt - minden látott Gmail-üzenet a
`bejovo_emailek` táblába kerül a Gmail-azonosítójával; ami ott van, azt
másodszor nem dolgozzuk fel, így az ismételt ellenőrzés és az újraindítás sem
duplikál. EGY kivétel van (a felhasználó kérése): ha egy korábban látott levél
tétele MÁR NINCS a rendszerben (pl. az "Összes törlése" vitte el), és a levél
a postafiókban még OLVASATLAN, azt újra behozzuk - az elintézetlen számla ne
ragadjon kint. Az olvasott levelet kézzel elintézettnek tekintjük, az nem jön
vissza magától. Az eredeti levelet nem töröljük, nem mozgatjuk, az
olvasottságát nem változtatjuk (readonly scope) és nem is válaszolunk rá.

A csatolmányokból piszkozat készül (lásd services/szamla_erkeztetes.py):
- a nyilvánvalóan nem-számla mellékletek (kis képek: logó, aláírás) kimaradnak;
- a PDF+XML párok egy dokumentumként kapcsolódnak össze;
- a melléklet nélküli, csak linket tartalmazó levél is piszkozatot kap
  ("Pontosítás szükséges") - nem vész el, de automatikus letöltés nincs."""

from __future__ import annotations

import base64
import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.bejovo_szamla import BejovoEmail, BejovoSzamla
from app.models.employee import Employee, SystemRole, van_szerepkore
from app.services import excel_szoveg, notifications, szamla_erkeztetes
from app.services.google_email import _extract_header, _gmail_service

logger = logging.getLogger(__name__)

#: Ennél kisebb kép szinte biztosan logó/aláírás, nem számlafotó.
MIN_KEP_MERET = 30 * 1024

FELDOLGOZHATO_MIME = szamla_erkeztetes.ENGEDETT_MIME | szamla_erkeztetes.XML_MIME | excel_szoveg.EXCEL_MIME


def _cel_cim() -> str:
    return (settings.szamla_bejovo_cim or "szamla@hypestab.hu").strip()


def _legkorabbi_nap() -> date:
    """A lehúzás fix alsó dátumhatára (a felhasználó kérése: 2026. 09. 01.
    előtti levelet SOHA ne nézzünk) - env-ből (SZAMLA_EMAIL_KEZDET) írható át."""
    try:
        return date.fromisoformat((settings.szamla_email_kezdet or "").strip())
    except ValueError:
        return date(2026, 9, 1)


def _query(kezdo_datum: date | None, veg_datum: date | None = None) -> str:
    """A Gmail-keresés. AZ OLVASOTTSÁG NEM SZÁMÍT (a felhasználó előírása):
    ha valaki megnyitotta a levelet, a számlát attól még importálni kell. A
    duplikáció ellen a SAJÁT importnyilvántartás (bejovo_emailek) véd - az
    egyszer már látott üzenet-azonosító nem jön be újra. A leveleket nem
    töröljük, nem mozgatjuk, és az olvasottságukat sem változtatjuk
    (readonly scope).

    DÁTUMHATÁR: mindig van alsó korlát (lásd _legkorabbi_nap) - a kért
    kezdődátum csak SZŰKÍTHETI az időszakot, régebbre nem nyithatja ki.
    A Gmail "after:" a megadott nap 0:00-jától értendő, tehát maga a
    határnap még benne van. A `veg_datum` a visszamenőleges, dátumtartományos
    visszatöltéshez van (before: kizáró, ezért +1 nap)."""
    legkorabbi = _legkorabbi_nap()
    hatar = kezdo_datum if kezdo_datum and kezdo_datum > legkorabbi else legkorabbi
    q = f"to:{_cel_cim()} after:{hatar.strftime('%Y/%m/%d')}"
    if veg_datum is not None:
        q += f" before:{(veg_datum + timedelta(days=1)).strftime('%Y/%m/%d')}"
    return q


def _okos_kezdo_datum(db: Session, kezdo_datum: date | None) -> date | None:
    """Az AUTOMATIKUS futásnak nem kell minden alkalommal a teljes időszakot
    végignéznie: az importnyilvántartás legutóbbi beérkezése előtt pár nappal
    kezdünk (átfedéssel, hogy a késve szinkronizálódó levél se maradjon ki) -
    kifejezett kezdődátum ezt felülírja.

    KIVÉTEL: ha van ÁRVA nyilvántartás-sor (a levélből valaha készült tétel,
    de már egy sincs a rendszerben - pl. az "Összes törlése" vitte el), a
    keresés a legrégebbi ilyen levélig nyúlik vissza, hogy az olvasatlan
    maradtakat újra be tudja hozni (lásd a fejlécet)."""
    if kezdo_datum is not None:
        return kezdo_datum
    utolso = db.scalar(select(func.max(BejovoEmail.beerkezes)))
    if utolso is None:
        return None
    kezdet = (utolso.date() if hasattr(utolso, "date") else utolso) - timedelta(days=3)
    legregebbi_arva = db.scalar(
        select(func.min(BejovoEmail.beerkezes)).where(
            BejovoEmail.letrehozott_szamla_db > 0,
            ~select(BejovoSzamla.id)
            .where(BejovoSzamla.email_uzenet_id == BejovoEmail.gmail_uzenet_id)
            .exists(),
        )
    )
    if legregebbi_arva is not None:
        arva_nap = legregebbi_arva.date() if hasattr(legregebbi_arva, "date") else legregebbi_arva
        kezdet = min(kezdet, arva_nap)
    return kezdet


def _uzenet_lista(svc, kezdo_datum: date | None, limit: int, veg_datum: date | None = None) -> list[str]:
    idk: list[str] = []
    token = None
    while len(idk) < limit:
        valasz = (
            svc.users()
            .messages()
            .list(
                userId="me",
                q=_query(kezdo_datum, veg_datum),
                maxResults=min(100, limit - len(idk)),
                pageToken=token,
            )
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
        # A levelezők az Excel-mellékletet néha általános MIME-mal küldik
        # (application/octet-stream) - ilyenkor a kiterjesztés dönt.
        if fajlnev and (mime in FELDOLGOZHATO_MIME or excel_szoveg.excelnek_tunik(mime, fajlnev)):
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
    veg_datum: date | None = None,
    limit: int = 50,
    csak_elonezet: bool = False,
    naplo=lambda s: None,
) -> dict:
    """A célcímre érkezett levelek feldolgozása - kézi gombról ÉS az
    automatikus háttérfolyamatból is ez fut (lásd main.py). `csak_elonezet`:
    nem hoz létre semmit, csak megmutatja, MI TÖRTÉNNE. A `kezdo_datum` +
    `veg_datum` a régi levelek visszamenőleges, dátumtartományos
    visszatöltéséhez van."""
    svc = _gmail_service()
    okos_kezdet = _okos_kezdo_datum(db, kezdo_datum) if veg_datum is None else kezdo_datum
    uzenet_idk = _uzenet_lista(svc, okos_kezdet, limit, veg_datum)
    naplo(f"{len(uzenet_idk)} levél a keresésben ({_query(okos_kezdet, veg_datum)})")

    mar_lattuk = {
        e.gmail_uzenet_id
        for e in db.scalars(select(BejovoEmail).where(BejovoEmail.gmail_uzenet_id.in_(uzenet_idk)))
    }
    # Melyik korábban látott levélnek van MÉG tétele a rendszerben - aminek
    # nincs (törölték), az olvasatlanul újra behozható (lásd a fejlécet).
    rendszerben = set(
        db.scalars(
            select(BejovoSzamla.email_uzenet_id).where(BejovoSzamla.email_uzenet_id.in_(uzenet_idk))
        )
    )
    elonezet: list[dict] = []
    uj_szamlak = 0
    feldolgozott_level = 0
    kihagyott_korabbi = 0
    ujra_behozott = 0
    hibas_level = 0

    for uzenet_id in uzenet_idk:
        ujra_behozas = False
        if uzenet_id in mar_lattuk:
            if uzenet_id in rendszerben:
                # Korábban átvett üzenet, aminek a tétele MEGVAN a rendszerben
                # - nem jön át újra, az olvasottságtól függetlenül.
                kihagyott_korabbi += 1
                continue
            # Korábban látott, de a tétele már nincs a rendszerben (pl. az
            # "Összes törlése" vitte el) - csak akkor hozzuk be ÚJRA, ha a
            # postafiókban még olvasatlan (az olvasott levelet kézzel
            # elintézettnek tekintjük). Az olvasottságot lentebb, a letöltött
            # üzenet címkéiből döntjük el.
            ujra_behozas = True
        uzenet = svc.users().messages().get(userId="me", id=uzenet_id, format="full").execute()
        if ujra_behozas and "UNREAD" not in (uzenet.get("labelIds") or []):
            kihagyott_korabbi += 1
            continue
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
                    "targy": targy + (" [újra behozható: törölt tétel, még olvasatlan]" if ujra_behozas else ""),
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
            _nyilvantartas_mentes(
                db,
                uzenet_id,
                felado=felado,
                targy=targy,
                beerkezes=beerkezes,
                allapot="feldolgozva" if csatolmanyok else "nincs_csatolmany",
                letrejott=letrejott,
                megjegyzes="Újra behozva: a korábbi tétele törölve volt, a levél olvasatlan maradt." if ujra_behozas else None,
            )
            db.commit()
            uj_szamlak += letrejott
            feldolgozott_level += 1
            if ujra_behozas:
                ujra_behozott += 1
                naplo(f"Újra behozva (törölt tétel, olvasatlan): {targy[:60]} ({letrejott} dokumentum)")
            else:
                naplo(f"Feldolgozva: {targy[:60]} ({letrejott} dokumentum)")
            _ertesites(db, targy, letrejott)
        except Exception as exc:  # noqa: BLE001 - egy rossz levél ne állítsa meg a többit
            db.rollback()
            logger.exception("Számla-email feldolgozási hiba (%s)", uzenet_id)
            _nyilvantartas_mentes(
                db,
                uzenet_id,
                felado=felado,
                targy=targy,
                beerkezes=beerkezes,
                allapot="hiba",
                letrejott=0,
                megjegyzes=str(exc)[:1000],
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
        #: Ebből hány volt ÚJRA behozott: korábban látott, de törölt tételű,
        #: a postafiókban még olvasatlan levél (benne van az uj_level-ben is).
        "ujra_behozott": ujra_behozott,
        "hibas_level": hibas_level,
        "elonezet": elonezet if csak_elonezet else None,
    }


def _nyilvantartas_mentes(
    db: Session,
    uzenet_id: str,
    *,
    felado: str,
    targy: str,
    beerkezes: datetime,
    allapot: str,
    letrejott: int,
    megjegyzes: str | None,
) -> None:
    """Az importnyilvántartás-sor felvétele VAGY frissítése. Az újra behozott
    levélnek már van sora (uq_bejovo_email_uzenet) - azt írjuk át, nem
    duplikálunk; a történet a megjegyzésben marad meg."""
    meglevo = db.scalar(select(BejovoEmail).where(BejovoEmail.gmail_uzenet_id == uzenet_id))
    if meglevo is not None:
        meglevo.felado = felado[:300]
        meglevo.targy = targy[:500]
        meglevo.beerkezes = beerkezes
        meglevo.allapot = allapot
        meglevo.letrehozott_szamla_db = letrejott
        if megjegyzes:
            meglevo.megjegyzes = megjegyzes[:1000]
        return
    db.add(
        BejovoEmail(
            gmail_uzenet_id=uzenet_id,
            felado=felado[:300],
            targy=targy[:500],
            beerkezes=beerkezes,
            allapot=allapot,
            letrehozott_szamla_db=letrejott,
            megjegyzes=megjegyzes[:1000] if megjegyzes else None,
        )
    )
