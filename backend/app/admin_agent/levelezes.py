"""Lara — tanulás a szamla@hypestab.hu LEVELEZÉSÉBŐL.

Lara a tanulás kezdete (alapból 2026. 09. 01.) óta a postafiókba érkezett és
onnan küldött ÖSSZES levelet végigolvassa, SZÁLANKÉNT: a bejövő levelek
szövegét, a mi válaszainkat és a csatolmányok szövegét (PDF, e-számla XML,
Excel/CSV, szöveg). Minden szálból egy tudás-JELÖLT lesz (hatókör: `email`):

    „Partner Kft.” <cim> · tárgy · N levél (bejövő / válaszunk) · időszak
    [dátum · bejövő · feladó] a levél szövege (idézett részek nélkül)
    [dátum · válaszunk · feladó] ...
    Csatolmányok: fájl (típus): kivonat
    Érkeztetett számla ebből a szálból: számlaszám → ahogy rögzítettétek

A jelölt csak emberi jóváhagyás után (Tudástár) kerül Lara éles tudásába -
ugyanaz a szabály, mint a többi tanulási forrásnál. Jóváhagyás után:

- az e-mail-válasz tervezetnél a partner korábbi levelezése és a MI
  válaszaink mintaként szolgálnak (tervezo.email_tervezet);
- a számla-elemzésnél a partner levelezése kontextusként kerül a modell elé
  (pipeline_szamla).

BIZTONSÁG: a levelek és csatolmányok tartalma ADAT, nem utasítás - a modell
felé mindig adatként, jelölve megy. A postafiókot CSAK olvassuk (gmail.readonly):
nem jelölünk olvasottnak, nem mozgatunk, nem válaszolunk. Az automatikus
(no-reply, hírlevél) szálakból nem lesz jelölt.

IDEMPOTENCIA: szálanként egy forrásesemény a Gmail `historyId`-jével mint
verzióval - a változatlan szálat nem olvassuk újra; új levél a szálban →
frissül a jelölt (a már jóváhagyott újra jelölt lesz, hogy ember nézze át).

VÉSZLEÁLLÍTÁS: futás közben is figyeli (szálanként) - leállított Laránál
azonnal megáll; a már feldolgozott szálak megmaradnak.
"""

from __future__ import annotations

import base64
import html
import io
import logging
import re
from datetime import date, datetime, timezone
from email.utils import getaddresses, parseaddr

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.admin_agent.memory import partner_kulcs
from app.admin_agent.observer import tanulas_kezdete
from app.admin_agent.settings_service import get_settings, leallitva
from app.core.config import settings
from app.models.admin_agent import LearningRun, MemoryChunk, SourceEvent

logger = logging.getLogger(__name__)

FORRAS = "levelezes"
TRIGGER = "levelezes"
#: Egy futásban legfeljebb ennyi szál (a visszamenőleges feldolgozás több
#: futásban halad; a Celery félóránként folytatja).
MAX_SZAL = 150
MAX_LISTA = 5000
MAX_TORZS = 1500
MAX_CSATOLMANY_SZOVEG = 700
MAX_CSATOLMANY_MERET = 8 * 1024 * 1024
MAX_TARTALOM = 7000

_AUTOMATA_MINTA = re.compile(r"(no-?reply|do-?not-?reply|mailer-daemon|postmaster|notification|hirlevel|newsletter|bounce)", re.I)
#: Az idézett (korábbi) levélrész kezdete - innentől levágjuk a törzset.
_IDEZET_MINTA = re.compile(
    r"^(On .{5,200} wrote:|.{3,200} (írta|ezt írta)\s*(\(.{1,80}\))?:?\s*$|-{2,}\s*(Original Message|Eredeti üzenet|"
    r"Forwarded message|Továbbított üzenet)\s*-{0,}|From: .+|Feladó: .+)",
    re.M | re.I,
)
_SZOVEGES_MIME = {"text/plain", "text/csv", "application/xml", "text/xml"}


def engedelyezve(db: Session) -> bool:
    return bool((get_settings(db).engedett_forrasok or {}).get(FORRAS))


def postafiok() -> str:
    return (settings.szamla_bejovo_cim or "szamla@hypestab.hu").strip().lower()


def _sajat_domain() -> str:
    return postafiok().split("@")[-1]


def query(kezdet: date) -> str:
    """Minden levél, ami a postafiókba jött VAGY onnan ment (Gmail: {a b} = VAGY)."""
    c = postafiok()
    return f"{{to:{c} from:{c} cc:{c} deliveredto:{c}}} after:{kezdet.strftime('%Y/%m/%d')}"


def _most() -> datetime:
    return datetime.now(timezone.utc)


# ── Szöveg-kinyerés ──────────────────────────────────────────────────────────


def _b64(adat: str) -> bytes:
    return base64.urlsafe_b64decode(adat + "=" * (-len(adat) % 4))


def _html_szoveg(h: str) -> str:
    h = re.sub(r"(?is)<(script|style).*?</\1>", " ", h)
    h = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>", "\n", h)
    return html.unescape(re.sub(r"<[^>]+>", " ", h))


def torzs(payload: dict) -> str:
    """A levél SAJÁT szövege: text/plain (különben a HTML szövege), az idézett
    korábbi levelek nélkül."""
    sima: list[str] = []
    htmlek: list[str] = []

    def jar(p: dict) -> None:
        mime = (p.get("mimeType") or "").lower()
        data = (p.get("body") or {}).get("data")
        if data and not p.get("filename"):
            try:
                szoveg = _b64(data).decode("utf-8", "replace")
            except Exception:  # noqa: BLE001
                szoveg = ""
            if mime == "text/plain":
                sima.append(szoveg)
            elif mime == "text/html":
                htmlek.append(_html_szoveg(szoveg))
        for gy in p.get("parts") or []:
            jar(gy)

    jar(payload)
    szoveg = "\n".join(sima) if sima else "\n".join(htmlek)
    return tisztit(szoveg)


def tisztit(szoveg: str) -> str:
    m = _IDEZET_MINTA.search(szoveg)
    if m and m.start() > 0:
        szoveg = szoveg[: m.start()]
    sorok = [s.rstrip() for s in szoveg.splitlines() if not s.lstrip().startswith(">")]
    szoveg = re.sub(r"\n{3,}", "\n\n", "\n".join(sorok)).strip()
    szoveg = re.sub(r"[ \t]{2,}", " ", szoveg)
    return szoveg[:MAX_TORZS]


def csatolmany_szoveg(fajlnev: str, mime: str, adat: bytes) -> str | None:
    """Kivonat egy csatolmányból - None, ha nem olvasható (pl. kép)."""
    nev = (fajlnev or "").lower()
    try:
        if mime == "application/pdf" or nev.endswith(".pdf"):
            try:
                from pypdf import PdfReader
            except ImportError:  # pragma: no cover - a requirements tartalmazza
                return None
            olvaso = PdfReader(io.BytesIO(adat))
            szoveg = "\n".join((oldal.extract_text() or "") for oldal in olvaso.pages[:3])
        elif mime in ("application/xml", "text/xml") or nev.endswith(".xml"):
            szoveg = re.sub(r"<[^>]+>", " ", adat.decode("utf-8", "replace"))
        elif mime in _SZOVEGES_MIME or nev.endswith((".txt", ".csv")):
            szoveg = adat.decode("utf-8", "replace")
        else:
            from app.services import excel_szoveg

            if not excel_szoveg.excelnek_tunik(mime, fajlnev):
                return None
            szoveg = excel_szoveg.szovegge(adat, fajlnev)
    except Exception:  # noqa: BLE001 - egy sérült melléklet nem állíthatja meg a futást
        logger.info("Csatolmány nem olvasható: %s", fajlnev)
        return None
    szoveg = re.sub(r"\s+", " ", html.unescape(szoveg or "")).strip()
    return szoveg[:MAX_CSATOLMANY_SZOVEG] or None


def _csatolmanyok(svc, uzenet_id: str, payload: dict) -> list[dict]:
    ki: list[dict] = []

    def jar(p: dict) -> None:
        fajlnev = p.get("filename") or ""
        body = p.get("body") or {}
        if fajlnev:
            mime = (p.get("mimeType") or "").split(";")[0].lower()
            meret = int(body.get("size") or 0)
            kivonat = None
            if meret <= MAX_CSATOLMANY_MERET and not mime.startswith(("image/", "video/", "audio/")):
                adat = None
                try:
                    if body.get("attachmentId"):
                        adat = _b64(
                            svc.users().messages().attachments()
                            .get(userId="me", messageId=uzenet_id, id=body["attachmentId"]).execute().get("data", "")
                        )
                    elif body.get("data"):
                        adat = _b64(body["data"])
                except Exception:  # noqa: BLE001
                    adat = None
                if adat:
                    kivonat = csatolmany_szoveg(fajlnev, mime, adat)
            ki.append({"nev": fajlnev, "mime": mime, "meret": meret, "kivonat": kivonat})
        for gy in p.get("parts") or []:
            jar(gy)

    jar(payload)
    return ki


# ── Egy szál feldolgozása ────────────────────────────────────────────────────


def _fejlec(uzenet: dict, nev: str) -> str:
    for h in (uzenet.get("payload") or {}).get("headers") or []:
        if (h.get("name") or "").lower() == nev.lower():
            return h.get("value") or ""
    return ""


def _kimeno(uzenet: dict, felado_cim: str) -> bool:
    return "SENT" in (uzenet.get("labelIds") or []) or felado_cim.endswith("@" + _sajat_domain())


def uzenetek(svc, szal: dict) -> list[dict]:
    """A szál leveleinek egységes leírása (időrendben)."""
    ki: list[dict] = []
    for u in szal.get("messages") or []:
        felado_nev, felado_cim = parseaddr(_fejlec(u, "From"))
        felado_cim = felado_cim.lower()
        try:
            ido = datetime.fromtimestamp(int(u.get("internalDate") or 0) / 1000, tz=timezone.utc)
        except (TypeError, ValueError):
            ido = None
        ki.append(
            {
                "id": u.get("id"),
                "ido": ido,
                "felado_nev": felado_nev or None,
                "felado_cim": felado_cim,
                "cimzettek": [c.lower() for _, c in getaddresses([_fejlec(u, "To"), _fejlec(u, "Cc")]) if c],
                "targy": _fejlec(u, "Subject"),
                "kimeno": _kimeno(u, felado_cim),
                "torzs": torzs(u.get("payload") or {}),
                "csatolmanyok": _csatolmanyok(svc, u.get("id"), u.get("payload") or {}) if svc is not None else [],
            }
        )
    ki.sort(key=lambda x: x["ido"] or datetime.min.replace(tzinfo=timezone.utc))
    return ki


def partner_a_szalban(levelek: list[dict]) -> tuple[str | None, str | None]:
    """(partner neve, címe): az első KÜLSŐ feladó; ha csak mi írtunk, a címzett."""
    for lv in levelek:
        if not lv["kimeno"] and lv["felado_cim"]:
            return lv["felado_nev"] or lv["felado_cim"], lv["felado_cim"]
    for lv in levelek:
        for c in lv["cimzettek"]:
            if not c.endswith("@" + _sajat_domain()):
                return c, c
    return None, None


def automatikus(levelek: list[dict]) -> bool:
    """Csak gépi (no-reply, hírlevél) levelek, és nem válaszoltunk rájuk."""
    bejovok = [lv for lv in levelek if not lv["kimeno"]]
    return bool(bejovok) and not any(lv["kimeno"] for lv in levelek) and all(
        _AUTOMATA_MINTA.search(lv["felado_cim"] or "") for lv in bejovok
    )


def _kapcsolodo_szamlak(db: Session, levelek: list[dict]) -> list[str]:
    from app.admin_agent.onellenorzes import _cel_szoveg
    from app.admin_agent.visszajatszas import vegso_dontes
    from app.models.bejovo_szamla import ALLAPOT_JOVAHAGYVA, BejovoSzamla

    idk = [lv["id"] for lv in levelek if lv["id"]]
    if not idk:
        return []
    ki: list[str] = []
    for b in db.scalars(select(BejovoSzamla).where(BejovoSzamla.email_uzenet_id.in_(idk))).all():
        sor = f"{b.szamlaszam or 'számlaszám nélkül'} ({b.kibocsato_nev or '?'}"
        if b.netto is not None:
            sor += f", nettó {float(b.netto):,.0f} Ft".replace(",", " ")
        sor += ")"
        if b.allapot == ALLAPOT_JOVAHAGYVA:
            v = vegso_dontes(db, b)
            sor += f" → így rögzítettétek: {_cel_szoveg(db, v.tipus, v.projektkod_idk)}"
        else:
            sor += " → még nincs rögzítve"
        ki.append(sor)
    return ki


def tartalom(partner: str | None, cim: str | None, levelek: list[dict], szamlak: list[str]) -> str:
    targy = next((lv["targy"] for lv in levelek if lv["targy"]), "") or "(tárgy nélkül)"
    bejovo = sum(1 for lv in levelek if not lv["kimeno"])
    valasz = len(levelek) - bejovo
    napok = [lv["ido"].date().isoformat() for lv in levelek if lv["ido"]]
    idoszak = f"{napok[0]} – {napok[-1]}" if napok and napok[0] != napok[-1] else (napok[0] if napok else "?")
    fej = (
        f"Levelezés — „{partner or '?'}”" + (f" <{cim}>" if cim and cim != partner else "")
        + f" · tárgy: „{targy}” · {len(levelek)} levél ({bejovo} bejövő, {valasz} válaszunk) · {idoszak}."
    )
    reszek = [fej]
    for lv in levelek:
        irany = "válaszunk" if lv["kimeno"] else "bejövő"
        ki = lv["felado_nev"] or lv["felado_cim"] or "?"
        nap = lv["ido"].date().isoformat() if lv["ido"] else "?"
        reszek.append(f"[{nap} · {irany} · {ki}] {lv['torzs'] or '(üres törzs)'}")
    csat = [c for lv in levelek for c in lv["csatolmanyok"]]
    if csat:
        reszek.append(
            "Csatolmányok: "
            + "; ".join(f"{c['nev']}" + (f": {c['kivonat']}" if c.get("kivonat") else "") for c in csat[:8])
        )
    if szamlak:
        reszek.append("Érkeztetett számla ebből a szálból: " + "; ".join(szamlak))
    szoveg = "\n".join(reszek)
    return szoveg[:MAX_TARTALOM]


def szal_feldolgozasa(db: Session, szal: dict, levelek: list[dict], *, verzio: str) -> str:
    """Egy (már letöltött) szál → forrásesemény + tudás-jelölt. Vissza:
    uj | frissitett | valtozatlan | automatikus | ures."""
    szal_id = szal.get("id")
    azonosito = f"szal:{szal_id}"
    if not levelek:
        return "ures"
    partner, cim = partner_a_szalban(levelek)
    auto = automatikus(levelek)
    meta = {
        "partner": partner,
        "cim": cim,
        "targy": next((lv["targy"] for lv in levelek if lv["targy"]), None),
        "levelek": len(levelek),
        "bejovo": sum(1 for lv in levelek if not lv["kimeno"]),
        "valasz": sum(1 for lv in levelek if lv["kimeno"]),
        "csatolmanyok": sum(len(lv["csatolmanyok"]) for lv in levelek),
        "elso": levelek[0]["ido"].isoformat() if levelek[0]["ido"] else None,
        "utolso": levelek[-1]["ido"].isoformat() if levelek[-1]["ido"] else None,
        "automatikus": auto,
        "uzenet_idk": [lv["id"] for lv in levelek],
    }
    try:
        with db.begin_nested():
            db.add(
                SourceEvent(
                    forras=FORRAS,
                    forras_azonosito=azonosito,
                    forras_verzio=verzio,
                    allapot="feldolgozva",
                    metaadat=meta,
                    feldolgozva_at=_most(),
                )
            )
    except IntegrityError:
        return "valtozatlan"
    if auto:
        return "automatikus"

    szoveg = tartalom(partner, cim, levelek, _kapcsolodo_szamlak(db, levelek))
    forras_ref = f"{FORRAS}:{szal_id}"
    pelda = db.scalar(select(MemoryChunk).where(MemoryChunk.forras == forras_ref))
    if pelda is None:
        db.add(
            MemoryChunk(
                hatokor="email",
                tartalom=szoveg,
                forras=forras_ref,
                forras_verzio=verzio,
                minosites="jelolt",
                tanulasi_halmaz="jovahagyott",
                ervenyes=False,  # emberi jóváhagyásig NEM használható
                forras_keletkezes=levelek[0]["ido"],
                regi_korszak=False,
            )
        )
        return "uj"
    if pelda.visszavont or pelda.tartalom == szoveg:
        pelda.forras_verzio = verzio
        return "valtozatlan"
    # Új levél a szálban: a jelölt frissül; a már jóváhagyott újra jelölt lesz.
    if pelda.ervenyes:
        pelda.ervenyes = False
        pelda.minosites = "jelolt"
    pelda.tartalom = szoveg
    pelda.forras_verzio = verzio
    return "frissitett"


# ── Futás ─────────────────────────────────────────────────────────────────────


def _feldolgozott_verziok(db: Session) -> dict[str, str]:
    ki: dict[str, str] = {}
    for azon, verzio in db.execute(
        select(SourceEvent.forras_azonosito, SourceEvent.forras_verzio)
        .where(SourceEvent.forras == FORRAS)
        .order_by(SourceEvent.id)
    ).all():
        ki[azon] = verzio or ""
    return ki


def levelezes_tanulas(db: Session, *, trigger: str = TRIGGER, max_szal: int = MAX_SZAL, svc=None) -> dict:
    """Egy levelezés-olvasó futás. A hívó commitál. Csak bekapcsolt forrással és
    nem leállított Larával dolgozik."""
    if leallitva(db):
        return {"allapot": "leallitva"}
    if not engedelyezve(db):
        return {"allapot": "kikapcsolva"}
    if svc is None:
        try:
            from app.services.google_email import _gmail_service

            svc = _gmail_service()
        except Exception as exc:  # noqa: BLE001 - hiányzó hitelesítés: érthető üzenet
            return {"allapot": "beallitas_szukseges", "uzenet": str(exc)[:300]}

    kezdet = tanulas_kezdete(db).date()
    q = query(kezdet)
    szalak: list[dict] = []
    token = None
    while len(szalak) < MAX_LISTA:
        v = svc.users().threads().list(userId="me", q=q, maxResults=100, pageToken=token).execute()
        szalak.extend(v.get("threads") or [])
        token = v.get("nextPageToken")
        if not token:
            break

    ismert = _feldolgozott_verziok(db)
    teendo = [s for s in szalak if ismert.get(f"szal:{s['id']}") != str(s.get("historyId") or "")]
    stat = {"uj": 0, "frissitett": 0, "valtozatlan": 0, "automatikus": 0, "ures": 0, "hiba": 0}
    allapot = "kesz"
    for i, s in enumerate(teendo[:max_szal]):
        # Vészleállítás futás közben is: FRISS munkamenetből olvasva.
        if i % 10 == 0 and i and leallitva():
            allapot = "leallitva"
            break
        try:
            teljes = svc.users().threads().get(userId="me", id=s["id"], format="full").execute()
            levelek = uzenetek(svc, teljes)
            eredmeny = szal_feldolgozasa(db, teljes, levelek, verzio=str(teljes.get("historyId") or s.get("historyId") or ""))
        except Exception:  # noqa: BLE001 - egy hibás szál nem állítja meg a többit
            logger.exception("Levelezés-szál feldolgozása sikertelen: %s", s.get("id"))
            eredmeny = "hiba"
        stat[eredmeny] = stat.get(eredmeny, 0) + 1
    db.flush()
    osszefoglalo = {
        "allapot": allapot,
        "postafiok": postafiok(),
        "kezdet": kezdet.isoformat(),
        "talalt_szal": len(szalak),
        "feldolgozando": len(teendo),
        "hatravan": max(0, len(teendo) - max_szal) if allapot == "kesz" else None,
        **stat,
    }
    most = _most()
    db.add(LearningRun(trigger=trigger, allapot="kesz" if allapot == "kesz" else "megszakitva",
                       kezdes_at=most, veg_at=most, osszefoglalo=osszefoglalo))
    db.flush()
    return osszefoglalo


def allapot(db: Session) -> dict:
    """A Tanulás oldal kártyájához: kapcsoló, hitelesítés, számok, futások."""
    from app.admin_agent.integrations import _gmail_konfiguralt

    szalak = db.scalar(
        select(func.count(func.distinct(SourceEvent.forras_azonosito))).where(SourceEvent.forras == FORRAS)
    ) or 0
    jeloltek = db.execute(
        select(MemoryChunk.ervenyes, MemoryChunk.visszavont, func.count(MemoryChunk.id))
        .where(MemoryChunk.forras.like(f"{FORRAS}:%"))
        .group_by(MemoryChunk.ervenyes, MemoryChunk.visszavont)
    ).all()
    jovahagyott = sum(n for e, v, n in jeloltek if e and not v)
    jelolt = sum(n for e, v, n in jeloltek if not e and not v)
    futasok = db.scalars(
        select(LearningRun).where(LearningRun.trigger.like(f"{TRIGGER}%")).order_by(LearningRun.id.desc()).limit(10)
    ).all()
    return {
        "engedelyezve": engedelyezve(db),
        "leallitva": leallitva(db),
        "gmail_konfiguralt": _gmail_konfiguralt(),
        "postafiok": postafiok(),
        "kezdet": tanulas_kezdete(db).date().isoformat(),
        "feldolgozott_szalak": szalak,
        "jelolt": jelolt,
        "jovahagyott": jovahagyott,
        "futasok": [
            {"id": r.id, "trigger": r.trigger, "veg_at": r.veg_at.isoformat() if r.veg_at else None, **(r.osszefoglalo or {})}
            for r in futasok
        ],
    }
