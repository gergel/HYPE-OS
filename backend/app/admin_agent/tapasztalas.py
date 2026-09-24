"""Lara — TAPASZTALÁS: önálló, háttérben futó tanulás a teljes adattörténetből,
a Gemini segítségével, a valóságon ellenőrizve.

A felhasználó kérése: Lara a Gemini segítségével a háttérben önállóan tanuljon
és tapasztaljon, hogy a benne lévő adat és kapcsolat mennyisége drasztikusan
nőjön, és vele együtt a bizonyosság százaléka is.

A bizonyosság (Tudásháló) a kapcsolatok mögötti BIZONYÍTÉKBÓL jön — ezt nem
lehet „felhangolni", csak valódi bizonyítékkal növelni. Ezért a tapasztalás két
lépés, és egyikben sem a modell mondja meg, mennyire biztos valami:

1. **Tények a teljes történetből** (determinista, modell nélkül): Lara végigjárja
   az ÖSSZES lezárt emberi munkát (szerződés, TIG, belsős TIG, kiadás,
   megrendelői papír, bevétel, utalás-felvezetés — a megfigyelő kinyerőivel),
   és partnerenként összesíti, mi ISMÉTLŐDIK: milyen formában dolgozunk vele,
   milyen projektkódokon, milyen típussal, melyik megrendelőnek. Tapasztalat az,
   ami legalább kétszer egybehangzóan megtörtént. A régi (Notion / a tanulás
   kezdete előtti) rekord kisebb súllyal számít (lásd tudashalo.REGI_SZORZO).
2. **Hipotézis → ellenőrzés a Geminivel**: a Gemini egy partner rekordjaiból
   ELLENŐRIZHETŐ általánosításokat javasol (zárt állítás-típusokkal: pl. „a
   számlái X projektkódra mennek", „mindig van mellette TIG", „nettó A–B Ft
   között számláz", „legfeljebb N nap késéssel fizet"). Lara MINDEN állítást
   maga ellenőriz a teljes adaton: csak az marad meg, amit legalább
   `IGAZOLT_MIN` eset és `IGAZOLT_ARANY` arány igazol. A cáfolt állítás nem
   lesz tudás, csak a Gemini találati arányába számít. Új adatnál Lara a már
   igazolt állításokat újraellenőrzi — ami már nem áll, azt visszavonja.

BIZTONSÁG:
* Csak olvas az üzleti táblákból; csak Lara saját tábláiba ír (tudás-darab,
  forrásesemény, futásnapló). SZABÁLYT nem élesít és nem is javasol — a
  tapasztalat tény és igazolt állítás, nem utasítás.
* A tények és az igazolt állítások a Tudástárban „tapasztalat" / „adat
  igazolta" címkével látszanak, és egy kattintással visszavonhatók.
* Fail-closed: nincs Gemini-kulcs / modellhiba → a tény-gyűjtés akkor is fut, a
  hipotézis-kör kimarad.
* Vészleállításnál és kikapcsolt „Tanulás és megfigyelés" forrásnál nem fut;
  külön is kikapcsolható: `aa_settings.limitek.tapasztalas`.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin_agent import llm
from app.admin_agent.memory import partner_kulcs
from app.models.admin_agent import LearningRun, MemoryChunk, SourceEvent

logger = logging.getLogger(__name__)

FORRAS = "tapasztalas"
TRIGGER = "tapasztalas"
#: A megfigyelő forrásai, amelyekből tény lesz (lezárt emberi munka). A szabad
#: szöveg (komment, árajánlat) és a negatív jel (törlés) nem tény.
TENY_FORRASOK = (
    "szerzodes", "tig", "belsos_tig", "kiadas", "megrendeloi_szerzodes", "megrendeloi_tig", "bevetel", "utalas",
)
#: Ennyi egybehangzó rekordtól tapasztalat egy tény.
MIN_TAPASZTALAT = 2
#: Ennyi rekordtól kérdezi Lara a Geminit a partnerről.
HIPOTEZIS_MIN_REKORD = 4
ALAP_GEMINI_MAX = 6
#: Egy állítás akkor igazolt, ha legalább ennyi eset és ekkora arány igazolja.
IGAZOLT_MIN = 3
IGAZOLT_ARANY = 0.8
MAX_REKORD_A_PROMPTBAN = 80
MAX_CAFOLT_NAPLO = 10

ALLITAS_TIPUSOK = ("forras", "projektkod", "megrendelo", "tipus", "osszeg_sav", "papir_parban", "fizetes_kesedelem")
FORRAS_CIMKE = {
    "szerzodes": "szerződés", "tig": "TIG", "belsos_tig": "belsős TIG", "kiadas": "kiadás/számla",
    "megrendeloi_szerzodes": "megrendelői szerződés", "megrendeloi_tig": "megrendelői TIG",
    "bevetel": "bevétel (fizetés)", "utalas": "utalás-felvezetés",
}
#: A forrás → tudásháló-témakör (lásd tudashalo._TABLA_TEMA).
FORRAS_TEMA = {
    "szerzodes": "szerzodes", "megrendeloi_szerzodes": "szerzodes", "tig": "tig", "belsos_tig": "tig",
    "megrendeloi_tig": "tig", "kiadas": "szamla", "bevetel": "szamla", "utalas": "szamla",
}
#: A forrás → Lara tudás-hatóköre (a Tudástárban és a keresésben).
FORRAS_HATOKOR = {
    "szerzodes": "szerzodes", "megrendeloi_szerzodes": "szerzodes", "tig": "tig", "belsos_tig": "tig",
    "megrendeloi_tig": "tig", "kiadas": "szamla", "bevetel": "kintlevoseg", "utalas": "szamla",
}
#: A Tudástár címkéi (minosites).
TENY = "tapasztalat"
IGAZOLT = "adat_igazolta"
CAFOLT = "adat_cafolta"

RENDSZER = llm.RENDSZER_ALAP + (
    " Most TAPASZTALATOT gyűjtesz: egy partnerrel kapcsolatos, ember által rögzített, lezárt rekordok listáját "
    "kapod. Írj ELLENŐRIZHETŐ állításokat arról, mi ismétlődik — csak a megadott állítás-típusokkal. Az "
    "állításaidat a szerver a teljes adaton ellenőrzi; ami nem áll meg, azt elveti és a te hibádként számolja. "
    "Ezért csak azt állítsd, amit a rekordok tényleg mutatnak, és inkább kevesebbet, de igazat."
)

HIPOTEZIS_SEMA = {
    "type": "object",
    "properties": {
        "allitasok": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "tipus": {"type": "string", "enum": list(ALLITAS_TIPUSOK)},
                    "ertek": {"type": "string"},
                    "also": {"type": ["number", "null"]},
                    "felso": {"type": ["number", "null"]},
                    "szoveg": {"type": "string"},
                },
                "required": ["tipus", "ertek", "szoveg"],
            },
        },
    },
    "required": ["allitasok"],
}


def _most() -> datetime:
    return datetime.now(timezone.utc)


def _lenyomat(adat: object) -> str:
    return hashlib.sha256(json.dumps(adat, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()[:24]


def _norm(v: Any) -> str:
    return " ".join(str(v).strip().lower().split()) if v not in (None, "") else ""


def bekapcsolva(db: Session) -> bool:
    from app.admin_agent.observer import engedelyezve
    from app.admin_agent.settings_service import get_settings

    return engedelyezve(db) and (get_settings(db).limitek or {}).get("tapasztalas", True) is not False


def _gemini_max(db: Session) -> int:
    from app.admin_agent.settings_service import get_settings

    try:
        n = int((get_settings(db).limitek or {}).get("tapasztalas_gemini_max") or ALAP_GEMINI_MAX)
    except (TypeError, ValueError):
        n = ALAP_GEMINI_MAX
    return max(0, min(n, 40))


# ── 1) Rekordok a teljes történetből ─────────────────────────────────────────


def rekordok(db: Session) -> dict[str, dict]:
    """Partnerkulcs → {"nev", "rekordok": [...]} az ÖSSZES lezárt emberi
    munkából (a megfigyelő kinyerőivel). Csak olvas."""
    from app.admin_agent.observer import FIGYELT, _Kontextus, _notion_rekordok, _regi, tanulas_kezdete

    kezdet = tanulas_kezdete(db)
    k = _Kontextus(db)
    ki: dict[str, dict] = defaultdict(lambda: {"nev": None, "rekordok": []})
    for f in FIGYELT:
        if f.kulcs not in TENY_FORRASOK:
            continue
        extra = [f.szuro] if f.szuro is not None else []
        sorok = [r for r in db.scalars(select(f.model).where(*extra).order_by(f.model.id)).all() if f.lezart(r)]
        notion = _notion_rekordok(db, f, [r.id for r in sorok])
        for r in sorok:
            meta = f.leiro(k, r)
            pk = partner_kulcs(meta.get("partner"))
            if len(pk) < 3:
                continue
            pc_id = meta.get("project_code_id")
            ido = r.updated_at or r.created_at
            osszeg = meta.get("osszeg")
            g = ki[pk]
            g["nev"] = g["nev"] or str(meta.get("partner")).strip()
            g["rekordok"].append({
                "forras": f.kulcs,
                "id": r.id,
                "pc_id": pc_id,
                "kod": meta.get("projektkod"),
                "megrendelo": k.projektkod_megrendelo(pc_id) if pc_id else None,
                "tipus": meta.get("kiadas_tipus") or meta.get("cel_tipus"),
                "osszeg": float(osszeg) if osszeg is not None else None,
                "kules_nap": meta.get("kules_nap"),
                "datum": ido.date().isoformat() if ido else None,
                "regi": _regi(r.created_at, r.id in notion, kezdet),
            })
    return ki


# ── 2) Tények (determinista) ─────────────────────────────────────────────────


def _teny(fajta: str, ertek: str, cimke: str, sorok: list[dict], ossz: int) -> dict:
    return {
        "fajta": fajta, "ertek": ertek, "cimke": cimke, "n": len(sorok), "ossz": ossz,
        "n_uj": sum(1 for s in sorok if not s["regi"]), "n_regi": sum(1 for s in sorok if s["regi"]),
    }


def tenyek(rek: list[dict]) -> list[dict]:
    """Egy partner ismétlődő tényei (legalább MIN_TAPASZTALAT egybehangzó rekord)."""
    ki: list[dict] = []
    ossz = len(rek)
    for fajta, kulcs, cimke_fn in (
        ("forras", lambda s: s["forras"], lambda v: FORRAS_CIMKE.get(v, v)),
        ("projektkod", lambda s: str(s["pc_id"]) if s["pc_id"] else None, None),
        ("megrendelo", lambda s: partner_kulcs(s["megrendelo"]) if s["megrendelo"] else None, None),
        ("tipus", lambda s: _norm(s["tipus"]) or None, None),
    ):
        csoport: dict[str, list[dict]] = defaultdict(list)
        for s in rek:
            v = kulcs(s)
            if v:
                csoport[v].append(s)
        alap = sum(len(v) for v in csoport.values())
        for v, sorok in csoport.items():
            if len(sorok) < MIN_TAPASZTALAT:
                continue
            if cimke_fn is not None:
                cimke = cimke_fn(v)
            elif fajta == "projektkod":
                cimke = sorok[0]["kod"] or f"#{v}"
            elif fajta == "megrendelo":
                cimke = str(sorok[0]["megrendelo"]).strip()
            else:
                cimke = str(sorok[0]["tipus"]).strip()
            ki.append(_teny(fajta, v, cimke, sorok, ossz if fajta == "forras" else alap))
    return sorted(ki, key=lambda t: (-t["n"], t["fajta"], t["cimke"]))


def _teny_szoveg(nev: str, rek: list[dict], tk: list[dict]) -> str:
    datumok = sorted(s["datum"] for s in rek if s["datum"])
    ido = f" ({datumok[0]} – {datumok[-1]})" if datumok else ""
    reszek = []
    for fajta, elotag in (("forras", "formában"), ("projektkod", "projektkódon"), ("megrendelo", "megrendelőnek"),
                          ("tipus", "típussal")):
        t = [x for x in tk if x["fajta"] == fajta][:6]
        if t:
            reszek.append(f"{elotag}: " + ", ".join(f"{x['cimke']} {x['n']}/{x['ossz']}" for x in t))
    return (f"Tapasztalat — {nev}: {len(rek)} lezárt, ember által rögzített rekord{ido}. "
            + "; ".join(reszek) + ". (Lara a teljes adattörténetből számolta, nem becslés.)")


def teny_gyujtes(db: Session, minden: dict[str, dict] | None = None) -> dict:
    """A tények frissítése minden partnerre. Idempotens (lenyomat): változatlan
    adatnál nem ír. A hívó commitál."""
    stat: Counter = Counter()
    minden = rekordok(db) if minden is None else minden
    for pk, g in minden.items():
        rek = g["rekordok"]
        if len(rek) < MIN_TAPASZTALAT:
            stat["kevés_adat"] += 1
            continue
        tk = tenyek(rek)
        if not tk:
            stat["nincs_ismetlodes"] += 1
            continue
        lenyomat = _lenyomat([(s["forras"], s["id"], s["pc_id"], s["tipus"], s["osszeg"], s["regi"]) for s in rek])
        azon = f"partner:{pk}"[:255]
        se = db.scalar(select(SourceEvent).where(SourceEvent.forras == FORRAS, SourceEvent.forras_azonosito == azon))
        if se is not None and se.forras_verzio == lenyomat:
            stat["valtozatlan"] += 1
            continue
        uj_regi = all(s["regi"] for s in rek)
        forras_hatokor = Counter(FORRAS_HATOKOR.get(s["forras"], "szamla") for s in rek).most_common(1)[0][0]
        meta = dict(se.metaadat or {}) if se is not None else {}
        meta.update({
            "partner": pk, "nev": g["nev"], "ossz": len(rek),
            "n_uj": sum(1 for s in rek if not s["regi"]), "tenyek": tk,
            "rekord_lenyomat": lenyomat, "hatokor": forras_hatokor,
        })
        if se is None:
            db.add(SourceEvent(forras=FORRAS, forras_azonosito=azon, forras_verzio=lenyomat, allapot="feldolgozva",
                               metaadat=meta, feldolgozva_at=_most()))
            stat["uj_partner"] += 1
        else:
            se.forras_verzio, se.metaadat, se.feldolgozva_at = lenyomat, meta, _most()
            stat["frissult_partner"] += 1
        forras = f"{FORRAS}:partner:{pk}"[:120]
        tartalom = _teny_szoveg(g["nev"], rek, tk)
        m = db.scalar(select(MemoryChunk).where(MemoryChunk.forras == forras))
        if m is None:
            db.add(MemoryChunk(hatokor=forras_hatokor, tartalom=tartalom, forras=forras, forras_verzio=lenyomat,
                               minosites=TENY, tanulasi_halmaz="jovahagyott", ervenyes=True, regi_korszak=uj_regi))
        elif not m.visszavont:
            m.tartalom, m.forras_verzio, m.hatokor, m.regi_korszak = tartalom, lenyomat, forras_hatokor, uj_regi
        stat["teny"] += len(tk)
        # Új adat → a már igazolt állításokat újraellenőrzi (modell nélkül).
        stat.update(ujraellenoriz(db, pk, g["nev"], rek, meta))
        if se is not None:
            se.metaadat = dict(meta)
    db.flush()
    stat["partner_ossz"] = len(minden)
    return dict(stat)


# ── 3) Állítások ellenőrzése (determinista) ───────────────────────────────────


def ellenoriz(allitas: dict, rek: list[dict]) -> tuple[int, int]:
    """(egyező, alapsokaság) — az állítás a partner összes rekordján."""
    t = allitas.get("tipus")
    ertek = _norm(allitas.get("ertek"))
    also, felso = allitas.get("also"), allitas.get("felso")
    if t == "forras":
        sok = rek
        jo = [s for s in sok if _norm(s["forras"]) == ertek or _norm(FORRAS_CIMKE.get(s["forras"])) == ertek]
    elif t == "projektkod":
        sok = [s for s in rek if s["pc_id"]]
        jo = [s for s in sok if _norm(s["kod"]) == ertek or str(s["pc_id"]) == ertek]
    elif t == "megrendelo":
        sok = [s for s in rek if s["megrendelo"]]
        jo = [s for s in sok if partner_kulcs(s["megrendelo"]) == partner_kulcs(allitas.get("ertek"))]
    elif t == "tipus":
        sok = [s for s in rek if s["tipus"]]
        jo = [s for s in sok if _norm(s["tipus"]) == ertek]
    elif t == "osszeg_sav":
        if also is None and felso is None:
            return 0, 0
        sok = [s for s in rek if s["osszeg"] is not None]
        jo = [s for s in sok if (also is None or s["osszeg"] >= also) and (felso is None or s["osszeg"] <= felso)]
    elif t == "papir_parban":
        papir = {s["pc_id"] for s in rek if s["pc_id"] and s["forras"] in ("szerzodes", "tig", "megrendeloi_szerzodes",
                                                                        "megrendeloi_tig")}
        sok = [s for s in rek if s["forras"] == "kiadas" and s["pc_id"]]
        jo = [s for s in sok if s["pc_id"] in papir]
    elif t == "fizetes_kesedelem":
        if felso is None:
            return 0, 0
        sok = [s for s in rek if s["forras"] == "bevetel" and s["kules_nap"] is not None]
        jo = [s for s in sok if s["kules_nap"] <= felso]
    else:
        return 0, 0
    return len(jo), len(sok)


def igazolt(jo: int, sok: int) -> bool:
    return sok > 0 and jo >= IGAZOLT_MIN and jo / sok >= IGAZOLT_ARANY


def _allitas_kulcs(a: dict) -> str:
    return _lenyomat([a.get("tipus"), _norm(a.get("ertek")), a.get("also"), a.get("felso")])[:12]


def _allitas_szoveg(nev: str, a: dict, jo: int, sok: int) -> str:
    return (f"{nev}: {a['szoveg'].strip()} — Lara tapasztalata: {jo}/{sok} rögzített eset igazolja "
            f"({round(100 * jo / sok)}%). (A Gemini javasolta, Lara a teljes adaton ellenőrizte.)")


def ujraellenoriz(db: Session, pk: str, nev: str, rek: list[dict], meta: dict) -> Counter:
    """A partner már igazolt állításai az ÚJ adaton: ami már nem áll, visszavonja."""
    stat: Counter = Counter()
    maradt = []
    for a in meta.get("igazolt") or []:
        jo, sok = ellenoriz(a, rek)
        m = db.scalar(select(MemoryChunk).where(MemoryChunk.forras == a.get("forras")))
        if igazolt(jo, sok):
            a.update({"n": jo, "ossz": sok, "n_uj": sum(1 for s in rek if not s["regi"])})
            if m is not None and not m.visszavont and m.minosites == IGAZOLT:
                m.tartalom = _allitas_szoveg(nev, a, jo, sok)
            maradt.append(a)
            stat["ujraigazolt"] += 1
        else:
            if m is not None and not m.visszavont:
                m.ervenyes, m.minosites = False, CAFOLT
            meta.setdefault("cafolt", []).append({**a, "n": jo, "ossz": sok, "ok": "az új adat már nem igazolja"})
            meta["cafolt"] = meta["cafolt"][-MAX_CAFOLT_NAPLO:]
            stat["visszavont"] += 1
    meta["igazolt"] = maradt
    return stat


# ── 4) Hipotézis-kör a Geminivel ─────────────────────────────────────────────


def _prompt(nev: str, rek: list[dict]) -> str:
    sorok = sorted(rek, key=lambda s: s["datum"] or "", reverse=True)[:MAX_REKORD_A_PROMPTBAN]
    return (
        f"PARTNER: {nev}\nÖsszesen {len(rek)} lezárt rekord; itt a legutóbbi {len(sorok)}.\n"
        "Állítás-típusok (a 'tipus' mező):\n"
        "- forras: milyen formában dolgozunk vele (ertek: szerzodes / tig / belsos_tig / kiadas / megrendeloi_szerzodes / "
        "megrendeloi_tig / bevetel / utalas)\n"
        "- projektkod: melyik projektkódon (ertek: a projektkód pontosan)\n"
        "- megrendelo: melyik megrendelő projektjein (ertek: a megrendelő neve)\n"
        "- tipus: a kiadás típusa / az utalás célja (ertek: pontosan, ahogy a rekordban áll)\n"
        "- osszeg_sav: a nettó összeg sávja (also / felso Ft-ban; ertek: \"\")\n"
        "- papir_parban: a kiadásai mellett ugyanazon a projektkódon van szerződés/TIG is (ertek: \"\")\n"
        "- fizetes_kesedelem: a határidőhöz képest legfeljebb 'felso' nap késéssel fizet (ertek: \"\")\n"
        "Legfeljebb 6 állítást írj; a 'szoveg' egy rövid, emberi mondat (pl. „A számláit a HYP-2641 kódra rögzítjük.”).\n\n"
        "REKORDOK (forrás | projektkód | megrendelő | típus | nettó | késés nap | dátum):\n"
        + "\n".join(
            f"- {s['forras']} | {s['kod'] or '—'} | {s['megrendelo'] or '—'} | {s['tipus'] or '—'} | "
            f"{'—' if s['osszeg'] is None else round(s['osszeg'])} | {'—' if s['kules_nap'] is None else s['kules_nap']} | "
            f"{s['datum'] or '—'}"
            for s in sorok
        )
    )


def hipotezis_kor(db: Session, max_partner: int, minden: dict[str, dict] | None = None) -> dict:
    """A Gemini állításokat javasol a legtöbb adattal rendelkező, még nem (vagy
    új adat óta nem) vizsgált partnerekre; Lara mindet ellenőrzi. A hívó commitál."""
    stat: Counter = Counter()
    if max_partner <= 0 or not llm.elerheto():
        return {"allapot": "kihagyva"}
    minden = rekordok(db) if minden is None else minden
    esemenyek = db.scalars(select(SourceEvent).where(SourceEvent.forras == FORRAS)).all()
    jeloltek = sorted(
        (se for se in esemenyek
         if (se.metaadat or {}).get("ossz", 0) >= HIPOTEZIS_MIN_REKORD
         and (se.metaadat or {}).get("hipotezis_lenyomat") != se.forras_verzio),
        key=lambda se: (se.metaadat or {}).get("ossz", 0), reverse=True,
    )
    stat["varakozo"] = max(0, len(jeloltek) - max_partner)
    for se in jeloltek[:max_partner]:
        meta = dict(se.metaadat or {})
        pk = meta.get("partner")
        g = minden.get(pk)
        if not g:
            continue
        try:
            v = llm.strukturalt_hivas(_prompt(g["nev"], g["rekordok"]), HIPOTEZIS_SEMA, rendszer=RENDSZER)
        except (llm.ModellHiba, llm.ModellNincsBeallitva) as exc:
            logger.info("Lara tapasztalás (%s) — a Gemini-kör kimaradt: %s", pk, exc)
            stat["hiba"] += 1
            break  # kvóta / kulcs gond: a többi partnert se most kérdezze
        meglevo = {a.get("kulcs") for a in meta.get("igazolt") or []}
        for a in (v.adat.get("allitasok") or [])[:6]:
            if a.get("tipus") not in ALLITAS_TIPUSOK or not str(a.get("szoveg") or "").strip():
                stat["ervenytelen"] += 1
                continue
            kulcs = _allitas_kulcs(a)
            jo, sok = ellenoriz(a, g["rekordok"])
            stat["javasolt"] += 1
            if not igazolt(jo, sok):
                stat["cafolt"] += 1
                meta.setdefault("cafolt", []).append({**a, "kulcs": kulcs, "n": jo, "ossz": sok, "ok": "az adat nem igazolja"})
                meta["cafolt"] = meta["cafolt"][-MAX_CAFOLT_NAPLO:]
                continue
            stat["igazolt"] += 1
            if kulcs in meglevo:
                stat["mar_ismert"] += 1
                continue
            forras = f"{FORRAS}:allitas:{pk}:{kulcs}"[:120]
            tartalom = _allitas_szoveg(g["nev"], a, jo, sok)
            hatokor = FORRAS_HATOKOR.get(a.get("ertek") if a.get("tipus") == "forras" else "", None) or meta.get("hatokor") or "szamla"
            m = db.scalar(select(MemoryChunk).where(MemoryChunk.forras == forras))
            if m is None:
                db.add(MemoryChunk(hatokor=hatokor, tartalom=tartalom, forras=forras, forras_verzio=se.forras_verzio,
                                   minosites=IGAZOLT, tanulasi_halmaz="jovahagyott", ervenyes=True,
                                   regi_korszak=not any(not s["regi"] for s in g["rekordok"])))
            elif m.visszavont:
                continue  # ember már elvetette — nem hozzuk vissza
            else:
                m.tartalom, m.ervenyes, m.minosites = tartalom, True, IGAZOLT
            meta.setdefault("igazolt", []).append({
                "kulcs": kulcs, "forras": forras, "tipus": a["tipus"], "ertek": a.get("ertek"),
                "also": a.get("also"), "felso": a.get("felso"), "szoveg": a["szoveg"].strip(), "n": jo, "ossz": sok,
                "n_uj": sum(1 for s in g["rekordok"] if not s["regi"]),
            })
            meglevo.add(kulcs)
        meta["hipotezis_lenyomat"] = se.forras_verzio
        meta["hipotezis_ido"] = _most().isoformat()
        se.metaadat = meta
        stat["partner"] += 1
    db.flush()
    return {"allapot": "kesz", **stat}


# ── Futtatás, állapot ────────────────────────────────────────────────────────


def futtat(db: Session, trigger: str = "utemezett", gemini_max: int | None = None, *, kenyszeritett: bool = False) -> dict:
    """Egy tapasztalás-kör: tények a teljes történetből, majd Gemini-hipotézisek
    ellenőrzéssel. A hívó commitál."""
    from app.admin_agent.gemini_tanulas import bekapcsolva as gemini_be
    from app.admin_agent.settings_service import leallitva

    if leallitva():
        return {"allapot": "leallitva"}
    if not kenyszeritett and not bekapcsolva(db):
        return {"allapot": "kikapcsolva"}
    kezd = _most()
    minden = rekordok(db)
    tenyek_stat = teny_gyujtes(db, minden)
    if gemini_be(db):
        hip = hipotezis_kor(db, _gemini_max(db) if gemini_max is None else gemini_max, minden)
    else:
        hip = {"allapot": "gemini_kikapcsolva"}
    eredmeny = {"allapot": "kesz", "tenyek": tenyek_stat, "hipotezisek": hip}
    db.add(LearningRun(trigger=f"{TRIGGER}:{trigger}", allapot="kesz", kezdes_at=kezd, veg_at=_most(),
                       osszefoglalo=eredmeny))
    db.flush()
    return eredmeny


def allapot(db: Session) -> dict:
    """A tapasztalás összesítése a felületnek."""
    esemenyek = db.scalars(select(SourceEvent).where(SourceEvent.forras == FORRAS)).all()
    igazolt_db = sum(len((se.metaadat or {}).get("igazolt") or []) for se in esemenyek)
    tenyek_db = sum(len((se.metaadat or {}).get("tenyek") or []) for se in esemenyek)
    vizsgalt = [se for se in esemenyek if (se.metaadat or {}).get("hipotezis_lenyomat")]
    varakozo = [se for se in esemenyek if (se.metaadat or {}).get("ossz", 0) >= HIPOTEZIS_MIN_REKORD
                and (se.metaadat or {}).get("hipotezis_lenyomat") != se.forras_verzio]
    futasok = db.scalars(
        select(LearningRun).where(LearningRun.trigger.like(f"{TRIGGER}:%")).order_by(LearningRun.id.desc()).limit(200)
    ).all()
    javasolt = sum(((f.osszefoglalo or {}).get("hipotezisek") or {}).get("javasolt", 0) for f in futasok)
    jo = sum(((f.osszefoglalo or {}).get("hipotezisek") or {}).get("igazolt", 0) for f in futasok)
    legjobb = sorted(
        ({"nev": (se.metaadat or {}).get("nev"), "szoveg": a.get("szoveg"), "n": a.get("n"), "ossz": a.get("ossz")}
         for se in esemenyek for a in (se.metaadat or {}).get("igazolt") or []),
        key=lambda x: -(x["n"] or 0),
    )[:8]
    utolso = futasok[0] if futasok else None
    return {
        "bekapcsolva": bekapcsolva(db),
        "partnerek": len(esemenyek),
        "tenyek": tenyek_db,
        "igazolt_allitasok": igazolt_db,
        "gemini_vizsgalt_partner": len(vizsgalt),
        "gemini_varakozo_partner": len(varakozo),
        "gemini_talalati_arany": round(jo / javasolt, 3) if javasolt else None,
        "gemini_javasolt": javasolt,
        "legjobb_allitasok": legjobb,
        "utolso_futas": {"ido": utolso.veg_at.isoformat() if utolso and utolso.veg_at else None,
                         "osszefoglalo": utolso.osszefoglalo if utolso else None},
    }
