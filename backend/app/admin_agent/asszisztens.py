"""Lara — tanulás az AI ASSZISZTENS munkájából.

Lara figyeli, mit kérnek az AI asszisztenstől, és mit csinált meg az
asszisztens: minden KÉRÉS-KÖR (egy felhasználói kérdés + az asszisztens
válasza + a közben indított írási műveletek) egy megfigyelés, és ha a kör
lezárult, egy tudás-JELÖLT:

    AI asszisztens — kérés (ki, mikor, melyik oldalon): „…a kérdés…”
    Válasz: …az asszisztens válasza (röviden)…
    Műveletek: ✓ végrehajtva: POST /api/v1/expenses — összefoglaló (kulcs adatok)
               ✗ elutasítva a felhasználó által: …   ! hiba: …

A témát (számla / TIG / szerződés / e-mail / egyéb asszisztens-kérés) a
műveletek útvonala adja. A jelölt - mint minden más forrásnál - emberi
jóváhagyás után (Tudástár) kerül Lara éles tudásába; onnan a partner szerint
előkerül (a műveletek kulcsadataiban szerepel a partner neve), így a
számla-elemzés és a tervezetek is használják. Az ELUTASÍTOTT művelet erős
negatív jel: a jelöltben külön szerepel, hogy az embernek mi NEM tetszett.

Csak olvas (az asszisztens táblái nem változnak). A tanulás kezdete előtti
kérésekből nem lesz jelölt; a még futó kört nem dolgozza fel (a következő
futás lezárva látja). Idempotens: kérés-körönként egy forrásesemény, a kör
tartalmának ujjlenyomatával mint verzióval. Vészleállításnál nem fut.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.admin_agent.observer import tanulas_kezdete
from app.admin_agent.settings_service import get_settings, leallitva
from app.models.admin_agent import LearningRun, MemoryChunk, SourceEvent
from app.models.ai_beszelgetes import AiBeszelgetes, AiMuvelet, AiUzenet
from app.models.employee import Employee

logger = logging.getLogger(__name__)

FORRAS = "asszisztens"
TRIGGER = "asszisztens"
MAX_KOR = 300
MAX_KERDES = 800
MAX_VALASZ = 700
MAX_TARTALOM = 6000

#: Az írási művelet útvonala → Lara témája (az első találat dönt).
_TEMA_UTVONAL: tuple[tuple[str, str], ...] = (
    ("/bejovo-szamlak", "szamla"),
    ("/expenses", "szamla"),
    ("/revenues", "szamla"),
    ("/kp-forgalom", "szamla"),
    ("/finance", "szamla"),
    ("performance-certificates", "tig"),
    ("/tig", "tig"),
    ("contract", "szerzodes"),
    ("szerzodes", "szerzodes"),
    ("email", "email"),
)
TEMA_CIMKE = {
    "szamla": "számla",
    "tig": "TIG",
    "szerzodes": "szerződés",
    "email": "e-mail",
    "asszisztens": "általános kérés",
}
_ALLAPOT_JEL = {"vegrehajtva": "✓ végrehajtva", "elutasitva": "✗ a felhasználó ELUTASÍTOTTA", "hiba": "! hibára futott",
                "fuggo": "… jóváhagyásra vár"}
_VEZERLO = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _tiszta(s: str | None) -> str:
    return _VEZERLO.sub("", s or "")


def _most() -> datetime:
    return datetime.now(timezone.utc)


def engedelyezve(db: Session) -> bool:
    return bool((get_settings(db).engedett_forrasok or {}).get(FORRAS))


def tema(muveletek: list[AiMuvelet]) -> str:
    for m in muveletek:
        ut = (m.path or "").lower()
        for minta, t in _TEMA_UTVONAL:
            if minta in ut:
                return t
    return "asszisztens"


def _kulcsadatok(keres, max_hossz: int = 260) -> str:
    """A kérés törzsének egyszerű mezői röviden (itt szerepel pl. a partner neve)."""
    if not isinstance(keres, dict):
        return ""
    reszek = [
        f"{k}: {v}"
        for k, v in keres.items()
        if isinstance(v, (str, int, float, bool)) and v not in ("", None) and not str(k).startswith("_")
    ]
    s = "; ".join(reszek)
    return s[:max_hossz] + ("…" if len(s) > max_hossz else "")


def korok(uzenetek: list[AiUzenet], muveletek: list[AiMuvelet]) -> list[dict]:
    """A beszélgetés kérés-körökre bontása: minden felhasználói üzenettől a
    következőig tartó üzenetek és az ezalatt indított műveletek."""
    kerdesek = [u for u in uzenetek if u.szerep == "felhasznalo"]
    ki: list[dict] = []
    for i, u in enumerate(kerdesek):
        kov = kerdesek[i + 1] if i + 1 < len(kerdesek) else None
        valaszok = [x for x in uzenetek if x.id > u.id and (kov is None or x.id < kov.id) and x.szerep == "asszisztens"]
        muv = [
            m for m in muveletek
            if m.created_at and u.created_at and m.created_at >= u.created_at
            and (kov is None or (kov.created_at and m.created_at < kov.created_at))
        ]
        ki.append({"kerdes": u, "valasz": valaszok[-1] if valaszok else None, "muveletek": muv, "utolso": kov is None})
    return ki


def _verzio(kor: dict) -> str:
    alap = [kor["kerdes"].id, kor["valasz"].id if kor["valasz"] else None,
            [(m.id, m.allapot, m.valasz_status) for m in kor["muveletek"]]]
    return hashlib.sha1(json.dumps(alap, default=str).encode()).hexdigest()[:20]


def tartalom(kor: dict, ki: str | None, oldal: str | None) -> str:
    u = kor["kerdes"]
    nap = u.created_at.date().isoformat() if u.created_at else "?"
    t = tema(kor["muveletek"])
    fej = f"AI asszisztens — {TEMA_CIMKE[t]} ({ki or 'ismeretlen'}, {nap}" + (f", oldal: {oldal}" if oldal else "") + ")"
    reszek = [fej, f"Kérés: „{_tiszta(u.szoveg).strip()[:MAX_KERDES]}”"]
    if kor["valasz"] is not None and kor["valasz"].szoveg:
        v = re.sub(r"\s+", " ", _tiszta(kor["valasz"].szoveg)).strip()
        reszek.append(f"Válasz: {v[:MAX_VALASZ]}" + ("…" if len(v) > MAX_VALASZ else ""))
    for m in kor["muveletek"]:
        sor = f"{_ALLAPOT_JEL.get(m.allapot, m.allapot)}: {m.method} {m.path}"
        if m.osszefoglalo:
            sor += f" — {_tiszta(m.osszefoglalo)[:300]}"
        adat = _kulcsadatok(m.keres)
        if adat:
            sor += f" ({_tiszta(adat)})"
        if m.allapot == "hiba" and m.valasz_status:
            sor += f" [HTTP {m.valasz_status}]"
        reszek.append(sor)
    if not kor["muveletek"]:
        reszek.append("Művelet nem történt (kérdés / keresés).")
    return "\n".join(reszek)[:MAX_TARTALOM]


def _oldal(u: AiUzenet) -> str | None:
    adat = u.adat if isinstance(u.adat, dict) else {}
    ktx = adat.get("kontextus") if isinstance(adat.get("kontextus"), dict) else adat
    return (ktx.get("cim") or ktx.get("utvonal")) if isinstance(ktx, dict) else None


def asszisztens_tanulas(db: Session, *, trigger: str = TRIGGER, max_kor: int = MAX_KOR) -> dict:
    """Egy megfigyelő futás az AI asszisztens beszélgetésein. A hívó commitál."""
    if leallitva(db):
        return {"allapot": "leallitva"}
    if not engedelyezve(db):
        return {"allapot": "kikapcsolva"}
    kezdet = tanulas_kezdete(db)
    ismert = {
        azon: verzio
        for azon, verzio in db.execute(
            select(SourceEvent.forras_azonosito, SourceEvent.forras_verzio)
            .where(SourceEvent.forras == FORRAS)
            .order_by(SourceEvent.id)
        ).all()
    }
    nevek = dict(db.execute(select(Employee.id, Employee.full_name)).all())
    stat = Counter()
    temak = Counter()
    feldolgozott = 0
    for b in db.scalars(
        select(AiBeszelgetes).where(AiBeszelgetes.updated_at >= kezdet).order_by(AiBeszelgetes.id)
    ).all():
        uz = db.scalars(select(AiUzenet).where(AiUzenet.beszelgetes_id == b.id).order_by(AiUzenet.id)).all()
        mv = db.scalars(select(AiMuvelet).where(AiMuvelet.beszelgetes_id == b.id).order_by(AiMuvelet.id)).all()
        for kor in korok(list(uz), list(mv)):
            u = kor["kerdes"]
            if u.created_at is None or u.created_at < kezdet:
                continue
            # A még futó utolsó kört nem dolgozzuk fel; a függő művelet is
            # megvárja a felhasználó döntését.
            if (kor["utolso"] and b.fut) or any(m.allapot == "fuggo" for m in kor["muveletek"]):
                stat["folyamatban"] += 1
                continue
            azon = f"kor:{u.id}"
            verzio = _verzio(kor)
            if ismert.get(azon) == verzio:
                continue
            if feldolgozott >= max_kor:
                stat["hatravan"] += 1
                continue
            feldolgozott += 1
            t = tema(kor["muveletek"])
            temak[t] += 1
            allapotok = Counter(m.allapot for m in kor["muveletek"])
            meta = {
                "beszelgetes_id": b.id,
                "employee_id": b.employee_id,
                "tema": t,
                "kerdes": _tiszta(u.szoveg)[:300],
                "muveletek": len(kor["muveletek"]),
                "vegrehajtva": allapotok["vegrehajtva"],
                "elutasitva": allapotok["elutasitva"],
                "hiba": allapotok["hiba"],
            }
            try:
                with db.begin_nested():
                    db.add(SourceEvent(forras=FORRAS, forras_azonosito=azon, forras_verzio=verzio,
                                       allapot="feldolgozva", metaadat=meta, feldolgozva_at=_most()))
                    szoveg = tartalom(kor, nevek.get(b.employee_id), _oldal(u))
                    ref = f"{FORRAS}:{u.id}"
                    pelda = db.scalar(select(MemoryChunk).where(MemoryChunk.forras == ref))
                    if pelda is None:
                        db.add(MemoryChunk(
                            hatokor=t, tartalom=szoveg, forras=ref, forras_verzio=verzio, minosites="jelolt",
                            tanulasi_halmaz="jovahagyott", ervenyes=False, forras_keletkezes=u.created_at,
                            regi_korszak=False,
                        ))
                        stat["uj"] += 1
                    elif not pelda.visszavont and pelda.tartalom != szoveg:
                        if pelda.ervenyes:  # új fejlemény → ember újra nézze át
                            pelda.ervenyes = False
                            pelda.minosites = "jelolt"
                        pelda.tartalom = szoveg
                        pelda.hatokor = t
                        pelda.forras_verzio = verzio
                        stat["frissitett"] += 1
                    db.flush()
                stat["elutasitott_muvelet"] += allapotok["elutasitva"]
                stat["vegrehajtott_muvelet"] += allapotok["vegrehajtva"]
            except IntegrityError:
                continue
            except Exception:  # noqa: BLE001 - egy hibás kör nem állítja meg a többit
                logger.exception("Asszisztens-kör feldolgozása sikertelen: %s", azon)
                stat["hiba"] += 1
    db.flush()
    osszefoglalo = {
        "allapot": "kesz",
        "feldolgozott_kor": feldolgozott,
        "uj": stat["uj"],
        "frissitett": stat["frissitett"],
        "vegrehajtott_muvelet": stat["vegrehajtott_muvelet"],
        "elutasitott_muvelet": stat["elutasitott_muvelet"],
        "folyamatban": stat["folyamatban"],
        "hatravan": stat["hatravan"],
        "hiba": stat["hiba"],
        "temak": dict(temak),
    }
    most = _most()
    db.add(LearningRun(trigger=trigger, allapot="kesz", kezdes_at=most, veg_at=most, osszefoglalo=osszefoglalo))
    db.flush()
    return osszefoglalo


def allapot(db: Session) -> dict:
    """A Tanulás oldal kártyájához: mit figyelt meg Lara az asszisztens munkájából."""
    esemenyek = db.scalars(select(SourceEvent).where(SourceEvent.forras == FORRAS).order_by(SourceEvent.id)).all()
    utolso: dict[str, dict] = {}
    for se in esemenyek:
        utolso[se.forras_azonosito] = se.metaadat or {}
    temak = Counter(m.get("tema") or "asszisztens" for m in utolso.values())
    jelolt = db.execute(
        select(MemoryChunk.ervenyes, func.count(MemoryChunk.id))
        .where(MemoryChunk.forras.like(f"{FORRAS}:%"), MemoryChunk.visszavont.is_(False))
        .group_by(MemoryChunk.ervenyes)
    ).all()
    futasok = db.scalars(
        select(LearningRun).where(LearningRun.trigger.like(f"{TRIGGER}%")).order_by(LearningRun.id.desc()).limit(10)
    ).all()
    return {
        "engedelyezve": engedelyezve(db),
        "leallitva": leallitva(db),
        "kerdesek": len(utolso),
        "vegrehajtott_muvelet": sum(int(m.get("vegrehajtva") or 0) for m in utolso.values()),
        "elutasitott_muvelet": sum(int(m.get("elutasitva") or 0) for m in utolso.values()),
        "hibas_muvelet": sum(int(m.get("hiba") or 0) for m in utolso.values()),
        "temak": {TEMA_CIMKE.get(k, k): v for k, v in temak.most_common()},
        "jelolt": sum(n for e, n in jelolt if not e),
        "jovahagyott": sum(n for e, n in jelolt if e),
        "futasok": [
            {"id": r.id, "trigger": r.trigger, "veg_at": r.veg_at.isoformat() if r.veg_at else None, **(r.osszefoglalo or {})}
            for r in futasok
        ],
    }
