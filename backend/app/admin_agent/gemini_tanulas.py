"""Lara — GYORSÍTOTT TANULÁS és ÖNFEJLESZTÉS a Geminivel.

A felhasználó kérése: a rendszerbe már be van kötve a Gemini (az AI asszisztens
azt használja) — kössük be innen Larába is, hogy gyorsabban tanuljon, nagyobb
tudásra tegyen szert, és gyorsan fejlessze önmagát.

Lara UGYANAZT a Gemini-kapcsolatot használja, mint az AI asszisztens
(`GEMINI_API_KEY`, `GEMINI_MODEL` — lásd core/config.py): külön kulcs nem kell.
Eddig a modellt a számla-elemzéshez, a tervezetekhez, a jelentés szerinti
kereséshez és az utánanézéshez használta; ez a modul a TANULÁSBA is bekötni:

1. **Partner-profilok** — ahol egy partnerről már legalább 3 jóváhagyott eset
   van, a Gemini összegzi, hogyan dolgozunk vele (papír, ÁFA, projektkód,
   számla, fizetés), és szabályt javasol. Egy profil sok példa helyett egyetlen
   tömör, azonnal használható tudás.
2. **Önreflexió** — Lara a Geminivel átnézi a saját hibáit (a kérdéseire adott
   válaszokat, az emberi javításokat, az önellenőrzés eltéréseit), és
   tanulságokat ír: mit csinál ezentúl másképp, hol gyenge.

BIZTONSÁG / önfejlesztés határai:
* Minden eredmény JELÖLT (a Tudástárban), a szabály FÜGGŐBEN — élesíteni csak
  ember tud. Lara a saját kódját, promptjait, jogosultságait, küszöbeit NEM
  írja át; „önfejlesztés" = a tudása bővül, emberi jóváhagyással.
* Szabályt csak adminisztrációs területre javasolhat (számla, TIG, szerződés,
  e-mail).
* Fail-closed: nincs kulcs / modellhiba → nem történik semmi, a régi út marad.
* Idempotens: ugyanabból az anyagból nem kérdez újra (ujjlenyomat).
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin_agent import llm
from app.admin_agent.memory import partner_kulcs
from app.core.config import settings
from app.models.admin_agent import Correction, LaraKerdes, LearningRun, MemoryChunk, PlaybookRule, SourceEvent

logger = logging.getLogger(__name__)

TRIGGER = "gemini_tanulas"
PROFIL_MIN = 3
ALAP_PROFIL_MAX = 5
PROFIL_PELDA_MAX = 25
REFLEXIO_NAPOK = 14
ADMIN_HATOKOROK = ("szamla", "tig", "szerzodes", "email")
_FORRAS_HATOKOR = {"visszajatszas": "szamla", "levelezes": "email"}

RENDSZER = llm.RENDSZER_ALAP + (
    " Most a SAJÁT TANULÁSODON dolgozol: a megadott, ember által jóváhagyott esetekből és visszajelzésekből "
    "általánosítasz. Csak azt írd le, amit az esetek alátámasztanak; ha ellentmondásosak, mondd ki. "
    "A kimenet jelölt tudás, amit ember hagy jóvá."
)

PROFIL_SEMA = {
    "type": "object",
    "properties": {
        "profil": {"type": "string"},
        "szabalyok": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "hatokor": {"type": "string", "enum": list(ADMIN_HATOKOROK)},
                    "cim": {"type": "string"},
                    "tartalom": {"type": "string"},
                    "eset_db": {"type": "integer"},
                },
                "required": ["hatokor", "cim", "tartalom"],
            },
        },
        "bizonytalansag": {"type": "number"},
    },
    "required": ["profil", "szabalyok", "bizonytalansag"],
}

REFLEXIO_SEMA = {
    "type": "object",
    "properties": {
        "osszefoglalo": {"type": "string"},
        "tanulsagok": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "hatokor": {"type": "string", "enum": [*ADMIN_HATOKOROK, "rendszer"]},
                    "tanulsag": {"type": "string"},
                    "mit_csinalok_maskepp": {"type": "string"},
                },
                "required": ["hatokor", "tanulsag", "mit_csinalok_maskepp"],
            },
        },
        "gyenge_pontok": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["osszefoglalo", "tanulsagok", "gyenge_pontok"],
}


def _most() -> datetime:
    return datetime.now(timezone.utc)


def _ujjlenyomat(adat: object) -> str:
    return hashlib.sha256(json.dumps(adat, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()[:24]


def bekapcsolva(db: Session) -> bool:
    from app.admin_agent.settings_service import get_settings

    return (get_settings(db).limitek or {}).get("gemini_tanulas", True) is not False


# ── 1) Partner-profilok ──────────────────────────────────────────────────────


def _partner_peldak(db: Session) -> dict[str, dict]:
    """Jóváhagyott példák partnerenként (a forrásesemény partneréből)."""
    peldak = {
        m.forras: m
        for m in db.scalars(
            select(MemoryChunk).where(
                MemoryChunk.ervenyes.is_(True), MemoryChunk.visszavont.is_(False),
                MemoryChunk.forras.like("megfigyeles:%") | MemoryChunk.forras.like("visszajatszas:%")
                | MemoryChunk.forras.like("levelezes:%") | MemoryChunk.forras.like("kerdes:%"),
            )
        ).all()
    }
    csoport: dict[str, dict] = defaultdict(lambda: {"nev": None, "peldak": [], "hatokor": Counter()})

    def _add(partner: str | None, m: MemoryChunk | None, hatokor: str) -> None:
        pk = partner_kulcs(partner)
        if m is None or len(pk) < 3:
            return
        g = csoport[pk]
        g["nev"] = g["nev"] or (partner or "").strip()
        g["peldak"].append(m)
        g["hatokor"][hatokor] += 1

    for se in db.scalars(select(SourceEvent).where(SourceEvent.forras.in_(("megfigyeles", "visszajatszas", "levelezes")))).all():
        meta = se.metaadat or {}
        azon = se.forras_azonosito if se.forras != "levelezes" else se.forras_azonosito.split(":", 1)[-1]
        m = peldak.pop(f"{se.forras}:{azon}", None)
        _add(meta.get("partner"), m, _FORRAS_HATOKOR.get(se.forras) or (m.hatokor if m else "szamla"))
    for forras, m in list(peldak.items()):
        if forras.startswith("kerdes:") and forras.split(":", 1)[1].isdigit():
            k = db.get(LaraKerdes, int(forras.split(":", 1)[1]))
            if k is not None:
                _add(k.partner_nev, m, m.hatokor)
    return csoport


def partner_profilok(db: Session, max_db: int = ALAP_PROFIL_MAX) -> dict:
    """Partner-profil jelöltek (és függő szabályjavaslatok) a Geminivel.
    A hívó commitál."""
    stat = Counter()
    jeloltek = sorted(
        ((pk, g) for pk, g in _partner_peldak(db).items() if len(g["peldak"]) >= PROFIL_MIN),
        key=lambda x: len(x[1]["peldak"]), reverse=True,
    )
    for pk, g in jeloltek:
        if stat["uj"] + stat["frissult"] >= max_db:
            stat["varolistan"] += 1
            continue
        peldak = sorted(g["peldak"], key=lambda m: m.id)[-PROFIL_PELDA_MAX:]
        lenyomat = _ujjlenyomat([(m.id, m.tartalom) for m in peldak])
        forras = f"gemini:profil:{pk}"[:120]
        meglevo = db.scalar(select(MemoryChunk).where(MemoryChunk.forras == forras))
        if meglevo is not None and (meglevo.forras_verzio == lenyomat or meglevo.visszavont):
            stat["valtozatlan"] += 1
            continue
        szoveg = (
            f"PARTNER: {g['nev']}\nAz alábbi {len(peldak)} JÓVÁHAGYOTT eset alapján írd le tömören (3-6 mondat), "
            "hogyan dolgozunk ezzel a partnerrel az adminisztrációban (papír kell-e, +ÁFA, milyen projektkódra/célra "
            "megy a számla, fizetési szokás, bármi visszatérő). Ha egyértelmű, visszatérő gyakorlat van, javasolj rá "
            "szabályt (csak számla / tig / szerzodes / email területre). A 'bizonytalansag' 0 = biztos, 1 = nagyon bizonytalan.\n\n"
            + "\n".join(f"- [{m.hatokor}] {m.tartalom[:600]}" for m in peldak)
        )
        try:
            v = llm.strukturalt_hivas(szoveg, PROFIL_SEMA, rendszer=RENDSZER)
        except (llm.ModellHiba, llm.ModellNincsBeallitva) as exc:
            logger.info("Lara partner-profil (%s) kihagyva: %s", pk, exc)
            stat["hiba"] += 1
            continue
        hatokor = g["hatokor"].most_common(1)[0][0] if g["hatokor"] else "szamla"
        tartalom = (
            f"Partner-profil — {g['nev']} (Lara összegzése a Geminivel, {len(peldak)} jóváhagyott eset alapján): "
            f"{v.adat['profil'].strip()}"
        )
        if meglevo is None:
            db.add(MemoryChunk(
                hatokor=hatokor, tartalom=tartalom, forras=forras, forras_verzio=lenyomat, minosites="jelolt",
                tanulasi_halmaz="jovahagyott", ervenyes=False, regi_korszak=False,
            ))
            stat["uj"] += 1
        else:
            # Új anyag → új szöveg, és újra ember hagyja jóvá.
            meglevo.tartalom, meglevo.forras_verzio = tartalom, lenyomat
            meglevo.hatokor, meglevo.ervenyes, meglevo.minosites = hatokor, False, "jelolt"
            stat["frissult"] += 1
        for sz in v.adat.get("szabalyok") or []:
            if sz.get("hatokor") not in ADMIN_HATOKOROK:
                continue
            cim = f"{g['nev']}: {sz['cim']}"[:200]
            if db.scalar(select(PlaybookRule.id).where(PlaybookRule.cim == cim, PlaybookRule.allapot != "retired")):
                continue
            db.add(PlaybookRule(
                hatokor=sz["hatokor"], cim=cim,
                tartalom=f"{sz['tartalom'].strip()} (Lara javaslata a Geminivel, {len(peldak)} jóváhagyott eset alapján.)",
                feltetelek={"forras": "gemini", "partner": pk, "partner_nev": g["nev"]},
                prioritas=5, verzio=1, allapot="pending",
                forras_esetek={"memoria_idk": [m.id for m in peldak]},
            ))
            stat["szabalyjavaslat"] += 1
    db.flush()
    return dict(stat)


# ── 2) Önreflexió ────────────────────────────────────────────────────────────


def _reflexio_anyag(db: Session) -> dict:
    tol = _most() - timedelta(days=REFLEXIO_NAPOK)
    kerdesek = [
        {"kerdes": (k.kerdes or "")[:500], "valasz": k.valasz_tipus, "magyarazat": (k.valasz_szoveg or "")[:400],
         "lara_utananezett": ((k.kontextus or {}).get("lara_nyomozas") or {}).get("javaslat"),
         "elfogadva": ((k.kontextus or {}).get("lara_nyomozas") or {}).get("elfogadva")}
        for k in db.scalars(
            select(LaraKerdes).where(LaraKerdes.allapot != "nyitott", LaraKerdes.megvalaszolva_at >= tol)
            .order_by(LaraKerdes.id.desc()).limit(40)
        ).all()
    ]
    javitasok = [
        {"mezok": sorted((c.mezo_diff or {}).keys())[:10], "tipus": c.tipus, "magyarazat": (c.magyarazat or "")[:400]}
        for c in db.scalars(select(Correction).where(Correction.created_at >= tol).order_by(Correction.id.desc()).limit(30)).all()
    ]
    futas = db.scalar(
        select(LearningRun).where(LearningRun.trigger.like("onellenorzes%")).order_by(LearningRun.id.desc())
    )
    teruletek = {
        t: {"arany": d.get("talalati_arany"), "elter": d.get("elter")}
        for t, d in ((futas.osszefoglalo or {}).get("teruletek") or {}).items()
    } if futas else {}
    return {"kerdesek": kerdesek, "javitasok": javitasok, "onellenorzes": teruletek}


def onreflexio(db: Session) -> dict:
    """Lara átnézi a saját hibáit a Geminivel, és tanulság-jelölteket ír.
    A hívó commitál."""
    anyag = _reflexio_anyag(db)
    if not anyag["kerdesek"] and not anyag["javitasok"]:
        return {"allapot": "nincs_uj_anyag"}
    lenyomat = _ujjlenyomat(anyag)
    elozo = db.scalar(select(LearningRun).where(LearningRun.trigger == f"{TRIGGER}:reflexio").order_by(LearningRun.id.desc()))
    if elozo is not None and (elozo.osszefoglalo or {}).get("lenyomat") == lenyomat:
        return {"allapot": "valtozatlan"}
    szoveg = (
        "Az elmúlt két hét visszajelzései a munkádról (a kérdéseidre adott emberi válaszok, a javaslataidon végzett "
        "emberi javítások, az önellenőrzésed találati aránya területenként). Nézd át őket: hol tévedtél, mi a "
        "visszatérő minta, mit csinálsz ezentúl másképp? Írj legfeljebb 8 konkrét, általánosítható tanulságot, és "
        "sorold fel a gyenge pontjaidat.\n\n" + json.dumps(anyag, ensure_ascii=False, default=str)[:24000]
    )
    try:
        v = llm.strukturalt_hivas(szoveg, REFLEXIO_SEMA, rendszer=RENDSZER)
    except (llm.ModellHiba, llm.ModellNincsBeallitva) as exc:
        logger.info("Lara önreflexiója kihagyva: %s", exc)
        return {"allapot": "hiba", "hiba": str(exc)[:300]}
    uj = 0
    for i, t in enumerate((v.adat.get("tanulsagok") or [])[:8]):
        forras = f"gemini:tanulsag:{lenyomat[:12]}:{i}"
        if db.scalar(select(MemoryChunk.id).where(MemoryChunk.forras == forras)):
            continue
        db.add(MemoryChunk(
            hatokor=t["hatokor"],
            tartalom=f"Tanulság (Lara önreflexiója a Geminivel): {t['tanulsag'].strip()} Ezentúl: {t['mit_csinalok_maskepp'].strip()}",
            forras=forras, forras_verzio=lenyomat, minosites="jelolt", tanulasi_halmaz="jovahagyott",
            ervenyes=False, regi_korszak=False,
        ))
        uj += 1
    most = _most()
    db.add(LearningRun(
        trigger=f"{TRIGGER}:reflexio", allapot="kesz", kezdes_at=most, veg_at=most,
        osszefoglalo={"lenyomat": lenyomat, "osszefoglalo": v.adat.get("osszefoglalo", "")[:2000],
                      "gyenge_pontok": [str(x)[:300] for x in (v.adat.get("gyenge_pontok") or [])[:8]],
                      "uj_tanulsag": uj, "modell": v.modell},
    ))
    db.flush()
    return {"allapot": "kesz", "uj_tanulsag": uj}


# ── Futtatás, állapot ────────────────────────────────────────────────────────


def futtat(db: Session, trigger: str = "ejszakai", profil_max: int | None = None) -> dict:
    """Mindkét Gemini-tanulás. A hívó commitál."""
    from app.admin_agent.settings_service import leallitva

    if leallitva():
        return {"allapot": "leallitva"}
    if not bekapcsolva(db):
        return {"allapot": "kikapcsolva"}
    if not llm.elerheto():
        return {"allapot": "beallitas_szukseges"}
    profil = partner_profilok(db, ALAP_PROFIL_MAX if profil_max is None else profil_max)
    reflexio = onreflexio(db)
    most = _most()
    eredmeny = {"allapot": "kesz", "profil": profil, "reflexio": reflexio}
    db.add(LearningRun(trigger=f"{TRIGGER}:{trigger}", allapot="kesz", kezdes_at=most, veg_at=most,
                       osszefoglalo=eredmeny))
    db.flush()
    return eredmeny


FUNKCIOK = (
    ("szamla_elemzes", "Beérkező számlák elemzése a megtanult tudással", None),
    ("tervezetek", "TIG-, szerződés- és e-mail-tervezetek", None),
    ("szemantikus_kereses", "Jelentés szerinti keresés a tudásban", "szemantikus_kereses"),
    ("nyomozas", "Utánanézés kérdés előtt (az AI asszisztens eszközeivel)", "nyomozas"),
    ("megoldas", "Megoldási javaslat a feladatokhoz", "megoldas"),
    ("gemini_tanulas", "Gyorsított tanulás: partner-profilok és önreflexió", "gemini_tanulas"),
    ("tapasztalas", "Tapasztalás: állítások a teljes adatból, adaton ellenőrizve", "tapasztalas"),
)


def allapot(db: Session) -> dict:
    from app.admin_agent.settings_service import get_settings

    lim = get_settings(db).limitek or {}
    utolso = db.scalar(select(LearningRun).where(LearningRun.trigger.like(f"{TRIGGER}:%"),
                                                 LearningRun.trigger != f"{TRIGGER}:reflexio")
                       .order_by(LearningRun.id.desc()))
    reflexio = db.scalar(select(LearningRun).where(LearningRun.trigger == f"{TRIGGER}:reflexio")
                         .order_by(LearningRun.id.desc()))
    from app.admin_agent import tapasztalas

    profilok = db.scalars(select(MemoryChunk).where(MemoryChunk.forras.like("gemini:profil:%"))).all()
    tanulsagok = db.scalars(select(MemoryChunk).where(MemoryChunk.forras.like("gemini:tanulsag:%"))).all()
    return {
        "kulcs_beallitva": bool(getattr(settings, "gemini_api_key", None)),
        "kozos_az_asszisztenssel": True,
        "modell": settings.gemini_model,
        "embedding_modell": getattr(settings, "gemini_embedding_model", None),
        "funkciok": [{"kulcs": k, "nev": n, "be": (lim.get(kap, True) is not False) if kap else True} for k, n, kap in FUNKCIOK],
        "profilok": {"osszes": len(profilok), "jovahagyott": sum(m.ervenyes for m in profilok)},
        "tanulsagok": {"osszes": len(tanulsagok), "jovahagyott": sum(m.ervenyes for m in tanulsagok)},
        "utolso_futas": {"ido": utolso.veg_at.isoformat() if utolso and utolso.veg_at else None,
                         "osszefoglalo": utolso.osszefoglalo if utolso else None},
        "tapasztalas": tapasztalas.allapot(db),
        "utolso_reflexio": {
            "ido": reflexio.veg_at.isoformat() if reflexio and reflexio.veg_at else None,
            "osszefoglalo": (reflexio.osszefoglalo or {}).get("osszefoglalo") if reflexio else None,
            "gyenge_pontok": (reflexio.osszefoglalo or {}).get("gyenge_pontok") if reflexio else [],
        },
    }


KAPCSOLAT_SEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}


def kapcsolat_teszt() -> dict:
    """Egy apró, valódi modellhívás: él-e a Gemini-kapcsolat."""
    kezdet = time.monotonic()
    try:
        v = llm.strukturalt_hivas('Válaszolj pontosan így: {"ok": true}', KAPCSOLAT_SEMA, max_proba=1)
    except llm.ModellNincsBeallitva:
        return {"ok": False, "uzenet": "Nincs Gemini-kulcs a szerveren (GEMINI_API_KEY) — ugyanaz kell, mint az AI asszisztensnek."}
    except llm.ModellHiba as exc:
        return {"ok": False, "uzenet": f"A Gemini nem válaszolt rendben: {str(exc)[:300]}"}
    return {"ok": bool(v.adat.get("ok")), "modell": v.modell, "ms": int((time.monotonic() - kezdet) * 1000),
            "uzenet": "A Gemini-kapcsolat él."}
