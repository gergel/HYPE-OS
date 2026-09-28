"""Lara — diszpó brief és technikai lista a korábbi forgatások tapasztalatából.

A felhasználó kérése (2026-09-28): Lara tanulja meg az egész rendszert, és a
múltbeli tapasztalatok alapján tudjon a diszpóhoz BRIEFET és TECHNIKAI LISTÁT
írni. A technikai listánál - ahogy a rendszerben máshol is - ne csak a
szöveget készítse el, hanem ténylegesen RENDELJE HOZZÁ a projekthez az összes
oda tartozó eszközt.

Hogyan:

1. **Tapasztalat** (`hasonlo_forgatasok`): a korábbi forgatások közül a
   leginkább hasonlók - ugyanaz az ügyfél / kampány / brief-típus, közös
   szavak a névben és a helyszínben, közös stáb. A hasonlóság súlyoz.
2. **Technikai csomag** (`technika_javaslat`): a hasonló forgatásokhoz
   ténylegesen hozzárendelt eszközök (Assignment) súlyozott gyakorisága. Ami a
   hasonló forgatások legalább felén ott volt, az bekerül; darabszámnál a
   szokásos (medián) mennyiség. Az éppen foglalt vagy nem használható eszköz
   helyett szabad, azonos kategóriájú (optikánál azonos zoom-tartományú)
   helyettesítőt keres; ha nincs, figyelmeztet. A projekten már meglévő
   eszközöket nem duplázza.
3. **Brief** (`brief_javaslat`): a projekt saját adataiból (név, időpont,
   helyszín, leírás, gyártási megjegyzés, kreatív doksi) + a hasonló
   forgatások briefjeiben VISSZATÉRŐ instrukciókból. Ha van modell (Gemini),
   az a hasonló briefek stílusában fogalmaz, de csak a bemenetben lévő tényekből;
   a technikát csak a valós eszköztörzsből választhatja (ismeretlen azonosító
   elutasítva). A diszpó alap-emlékeztetője (SD-kártyák) mindig a végén marad.
4. **Javaslat → jóváhagyás → végrehajtás** (R1, belső, visszafordítható írás):
   a végrehajtó a brief mezőt írja (csak ha közben nem módosult), az eszközöket
   a KÖZÖS foglalási úton rendeli hozzá (services/eszkoz_foglalas.py - ugyanaz,
   mint a felület „hozzáadás” gombja), majd lefuttatja a „Technika ready”
   ellenőrzést (services/technika.check_technika), ami a technikai lista
   szövegét és az ütközés-riportot a projektre írja. A diszpót NEM küldi ki.
5. **Visszavonás** (`visszavonas`): a Lara által létrehozott foglalások
   törlése, a megnövelt darabszámok visszaállítása és - ha azóta senki nem
   írta át - a korábbi brief visszaírása.

A tapasztalat tanulása (`tanul`) a teljes-rendszer figyelés része (lásd
admin_agent/rendszer.py): ügyfelenként és brief-típusonként a szokásos
technikai csomag és a visszatérő brief-instrukciók TÉNYKÉNT a Tudástárba
kerülnek (hatókör: "diszpo"), ahol látszanak és elvethetők."""

from __future__ import annotations

import json
import re
import statistics
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.equipment import Assignment, Equipment, TrackMode
from app.models.project import Project
from app.services.diszpo_sablon import BRIEF_SABLON

ESZKOZ = "diszpo.brief_technika_mentes"
#: Ennyi hasonló forgatást nézünk.
MAX_HASONLO = 12
#: Egy eszköz akkor kerül a javaslatba, ha a hasonló forgatások (súlyozott)
#: legalább ennyi részén ott volt ...
KUSZOB = 0.5
#: ... és legalább ennyi különböző forgatáson.
MIN_ELOFORDULAS = 2
#: Egy brief-sor akkor "visszatérő", ha legalább ennyi hasonló briefben szerepel.
MIN_BRIEF_ISMETLODES = 2
HASZNALHATO = "Használható"


class DiszpoHiba(ValueError):
    pass


def _most() -> datetime:
    return datetime.now(timezone.utc)


# ── Segédek ──────────────────────────────────────────────────────────────────

_SZO = re.compile(r"[a-záéíóöőúüű0-9]{4,}", re.I)
_TILTOTT_SOR = re.compile(r"(\d|@|https?://|www\.)", re.I)


def _szavak(szoveg: str | None) -> set[str]:
    return {w[:5] for w in _SZO.findall((szoveg or "").lower())}


def _norm_sor(sor: str) -> str:
    return " ".join(sor.strip(" -•*\t").split()).lower()


def _sablon_sorok() -> set[str]:
    return {_norm_sor(s) for s in BRIEF_SABLON.splitlines() if s.strip()}


def brief_ures(brief: str | None) -> bool:
    """Üres-e a brief (vagy csak az alap-sablon van benne)?"""
    maradek = [s for s in (brief or "").splitlines() if s.strip() and _norm_sor(s) not in _sablon_sorok()]
    return not maradek


def _client_id(p: Project) -> int | None:
    return p.project_code.client_id if p.project_code is not None else None


def _tartomany(p: Project) -> tuple[date, date] | None:
    if p.forgatas_datuma is None:
        return None
    return p.forgatas_datuma, (p.forgatas_datuma_vege or p.forgatas_datuma)


def hasznalhato(e: Equipment) -> bool:
    if e.hasznalhato and e.hasznalhato != HASZNALHATO:
        return False
    if e.archive_statusz and "archiv" in e.archive_statusz.lower():
        return False
    return True


def forgatas_kereses(
    db: Session, *, project_id: Any = None, project_code_id: int | None = None, szoveg: str | None = None
) -> int | None:
    """Melyik forgatásra (Project) szól a diszpó-feladat? Kifejezett azonosító >
    a projektkód egyetlen / legközelebbi jövőbeli forgatása. None: nem egyértelmű."""
    if project_id not in (None, ""):
        try:
            p = db.get(Project, int(project_id))
        except (TypeError, ValueError):
            p = None
        if p is not None:
            return p.id
    if project_code_id is None:
        return None
    projektek = list(db.scalars(select(Project).where(Project.project_code_id == project_code_id)).all())
    if len(projektek) == 1:
        return projektek[0].id
    ma = date.today()
    jovo = sorted((p for p in projektek if p.forgatas_datuma and p.forgatas_datuma >= ma), key=lambda p: p.forgatas_datuma)
    return jovo[0].id if jovo else None


# ── 1) Tapasztalat: hasonló korábbi forgatások ───────────────────────────────


def hasonlosag(p: Project, masik: Project) -> tuple[float, list[str]]:
    """Hasonlósági pontszám + az okai (emberi szöveg)."""
    pont = 0.0
    ok: list[str] = []
    if _client_id(p) and _client_id(p) == _client_id(masik):
        pont += 3
        ok.append("ugyanaz az ügyfél")
    if p.campaign_id and p.campaign_id == masik.campaign_id:
        pont += 2
        ok.append("ugyanaz a kampány")
    if p.brief_tipus and p.brief_tipus == masik.brief_tipus:
        pont += 2
        ok.append(f"brief-típus: {p.brief_tipus}")
    if p.fotos_diszpo and masik.fotos_diszpo:
        pont += 1
        ok.append("fotós diszpó")
    kozos = _szavak(p.nev) & _szavak(masik.nev)
    if kozos:
        pont += min(3.0, 1.0 * len(kozos))
        ok.append("hasonló név")
    if _szavak(p.helyszin) & _szavak(masik.helyszin):
        pont += 1
        ok.append("hasonló helyszín")
    stab = {e.id for e in p.crew} & {e.id for e in masik.crew}
    if stab:
        pont += min(2.0, 0.5 * len(stab))
        ok.append(f"{len(stab)} közös stábtag")
    return pont, ok


def hasonlo_forgatasok(db: Session, project: Project, *, limit: int = MAX_HASONLO) -> list[dict]:
    """A leginkább hasonló KORÁBBI forgatások (a projekt előttiek), amelyeknek
    van briefje vagy hozzárendelt technikája."""
    q = (
        select(Project)
        .options(selectinload(Project.crew), selectinload(Project.project_code))
        .where(
            Project.id != project.id,
            Project.forgatas_datuma.is_not(None),
            or_(Project.brief.is_not(None), Project.id.in_(select(Assignment.project_id))),
        )
    )
    if project.forgatas_datuma is not None:
        q = q.where(Project.forgatas_datuma < project.forgatas_datuma)
    eredmeny = []
    for m in db.scalars(q.order_by(Project.forgatas_datuma.desc()).limit(600)).all():
        pont, ok = hasonlosag(project, m)
        if pont <= 0:
            continue
        eredmeny.append({"project": m, "pont": pont, "okok": ok})
    eredmeny.sort(key=lambda x: (-x["pont"], -(x["project"].forgatas_datuma.toordinal())))
    return eredmeny[:limit]


# ── 2) Technikai csomag ──────────────────────────────────────────────────────


def _foglalas_utkozes(db: Session, e: Equipment, project: Project, qty: int) -> str | None:
    """Foglalt-e az eszköz a projekt napjain (más projekt miatt)? Vissza: ok vagy None."""
    rng = _tartomany(project)
    if rng is None:
        return None
    start, end = rng
    tobbi = db.scalars(
        select(Assignment).where(Assignment.equipment_id == e.id, Assignment.project_id != project.id)
    ).all()
    if e.track_mode in (TrackMode.ASSET, "asset"):
        for a in tobbi:
            o = db.get(Project, a.project_id)
            r = _tartomany(o) if o else None
            if r and start <= r[1] and r[0] <= end:
                return f"foglalt: {o.nev} ({r[0].isoformat()})"
        return None
    if e.osszes_mennyiseg is None:
        return None
    napi: dict[date, int] = defaultdict(int)
    for a in tobbi:
        o = db.get(Project, a.project_id)
        r = _tartomany(o) if o else None
        if not r:
            continue
        for n in range((min(end, r[1]) - max(start, r[0])).days + 1):
            napi[date.fromordinal(max(start, r[0]).toordinal() + n)] += a.qty or 0
    csucs = max(napi.values(), default=0)
    if csucs + qty > e.osszes_mennyiseg:
        return f"készlet: {csucs} db már foglalt a {e.osszes_mennyiseg} db-ból"
    return None


def _helyettesito(db: Session, e: Equipment, project: Project, kizart: set[int]) -> Equipment | None:
    """Szabad, azonos kategóriájú (optikánál azonos zoom-tartományú, egyébként
    lehetőleg azonos márkájú) egyedi eszköz."""
    if e.track_mode not in (TrackMode.ASSET, "asset"):
        return None
    jeloltek = db.scalars(
        select(Equipment).where(
            Equipment.kategoria == e.kategoria, Equipment.id != e.id, Equipment.track_mode == TrackMode.ASSET
        )
    ).all()
    marka = (e.nev or "").split()[0].lower() if e.nev else ""
    if e.zoom_atfogas:
        jeloltek = [c for c in jeloltek if c.zoom_atfogas == e.zoom_atfogas]
    else:
        jeloltek = sorted(jeloltek, key=lambda c: (not (c.nev or "").lower().startswith(marka), c.nev or ""))
    for c in jeloltek:
        if c.id in kizart or not hasznalhato(c):
            continue
        if _foglalas_utkozes(db, c, project, 1) is None:
            return c
    return None


def technika_javaslat(db: Session, project: Project, hasonlok: list[dict]) -> dict:
    """A hasonló forgatások tényleges eszközeiből súlyozott gyakoriság szerint
    összeállított csomag - elérhetőség-ellenőrzéssel és helyettesítővel."""
    meglevo = {
        a.equipment_id: a
        for a in db.scalars(select(Assignment).where(Assignment.project_id == project.id)).all()
    }
    tech_hasonlok = []
    for h in hasonlok:
        foglalasok = db.scalars(select(Assignment).where(Assignment.project_id == h["project"].id)).all()
        if foglalasok:
            tech_hasonlok.append((h, foglalasok))
    ossz_suly = sum(h["pont"] for h, _ in tech_hasonlok)
    suly: dict[int, float] = defaultdict(float)
    darab: dict[int, list[int]] = defaultdict(list)
    projektek: dict[int, set[int]] = defaultdict(set)
    for h, foglalasok in tech_hasonlok:
        latott: set[int] = set()
        for a in foglalasok:
            darab[a.equipment_id].append(a.qty or 1)
            if a.equipment_id not in latott:
                suly[a.equipment_id] += h["pont"]
                projektek[a.equipment_id].add(h["project"].id)
                latott.add(a.equipment_id)
    egyetlen_eros = len(tech_hasonlok) == 1 and tech_hasonlok[0][0]["pont"] >= 4

    tetelek: list[dict] = []
    figyelmeztetesek: list[str] = []
    felhasznalt: set[int] = set(meglevo)
    for eid, s in sorted(suly.items(), key=lambda x: -x[1]):
        arany = s / ossz_suly if ossz_suly else 0
        n = len(projektek[eid])
        if arany < KUSZOB or (n < MIN_ELOFORDULAS and not egyetlen_eros):
            continue
        e = db.get(Equipment, eid)
        if e is None or eid in meglevo:
            continue
        stock = e.track_mode in (TrackMode.STOCK, "stock")
        qty = int(statistics.median(darab[eid])) if stock else 1
        gyakorisag = f"{n}/{len(tech_hasonlok)} hasonló forgatáson"
        ok = None if hasznalhato(e) else f"nem használható ({e.hasznalhato or e.archive_statusz})"
        ok = ok or _foglalas_utkozes(db, e, project, qty)
        if ok is None:
            tetelek.append(_tetel(e, qty, "tapasztalat", f"A hasonló forgatások {round(arany * 100)}%-án ott volt.", gyakorisag))
            felhasznalt.add(e.id)
            continue
        alt = _helyettesito(db, e, project, felhasznalt)
        if alt is not None:
            t = _tetel(alt, 1, "helyettesito", f"{e.nev} helyett ({ok}).", gyakorisag)
            t["helyettesiti"] = {"equipment_id": e.id, "nev": e.nev}
            tetelek.append(t)
            felhasznalt.add(alt.id)
        else:
            figyelmeztetesek.append(f"{e.nev} kellene ({gyakorisag}), de {ok} - nincs szabad helyettesítő.")
    return {
        "tetelek": tetelek,
        "meglevo": [
            {"equipment_id": a.equipment_id, "nev": (db.get(Equipment, a.equipment_id).nev if db.get(Equipment, a.equipment_id) else "?"), "qty": a.qty}
            for a in meglevo.values()
        ],
        "tapasztalat_forgatasok": len(tech_hasonlok),
        "figyelmeztetesek": figyelmeztetesek,
    }


def _tetel(e: Equipment, qty: int, forras: str, indoklas: str, gyakorisag: str | None = None) -> dict:
    return {
        "equipment_id": e.id,
        "nev": e.nev,
        "kategoria": e.kategoria,
        "track_mode": e.track_mode.value if hasattr(e.track_mode, "value") else str(e.track_mode),
        "qty": max(1, int(qty or 1)),
        "forras": forras,
        "indoklas": indoklas,
        "gyakorisag": gyakorisag,
    }


# ── 3) Brief ─────────────────────────────────────────────────────────────────


def visszatero_instrukciok(hasonlok: list[dict]) -> list[str]:
    """A hasonló forgatások briefjeiben legalább kétszer előforduló sorok -
    szám, dátum, e-mail, link nélküliek (azok projektfüggők), a sablon nélkül."""
    sablon = _sablon_sorok()
    szamlalo: dict[str, int] = defaultdict(int)
    eredeti: dict[str, str] = {}
    for h in hasonlok:
        latott: set[str] = set()
        for sor in (h["project"].brief or "").splitlines():
            n = _norm_sor(sor)
            if len(n) < 15 or len(n) > 220 or n in sablon or _TILTOTT_SOR.search(sor) or n in latott:
                continue
            latott.add(n)
            szamlalo[n] += 1
            eredeti.setdefault(n, sor.strip(" -•*\t"))
    return [eredeti[n] for n, c in sorted(szamlalo.items(), key=lambda x: -x[1]) if c >= MIN_BRIEF_ISMETLODES][:12]


def _idopont(p: Project) -> str:
    if p.forgatas_datuma is None:
        return "időpont egyeztetés alatt"
    s = p.forgatas_datuma.isoformat()
    if p.forgatas_datuma_vege and p.forgatas_datuma_vege != p.forgatas_datuma:
        s += f" – {p.forgatas_datuma_vege.isoformat()}"
    if p.forgatas_kezdes_ido:
        s += f", {p.forgatas_kezdes_ido.strftime('%H:%M')}"
        if p.forgatas_veg_ido:
            s += f"–{p.forgatas_veg_ido.strftime('%H:%M')}"
    return s


def _vegere_sablon(szoveg: str) -> str:
    szoveg = szoveg.rstrip()
    if _norm_sor(BRIEF_SABLON.splitlines()[0]) not in {_norm_sor(s) for s in szoveg.splitlines()}:
        szoveg = f"{szoveg}\n\n{BRIEF_SABLON}"
    return szoveg


def brief_szabaly_alapon(project: Project, instrukciok: list[str]) -> str:
    """Modell nélküli brief: CSAK a projekt saját adataiból és a visszatérő
    instrukciókból - semmit nem talál ki."""
    reszek = [f"{project.nev} – {_idopont(project)}"]
    if project.helyszin:
        reszek.append(f"Helyszín: {project.helyszin.strip()}")
    if project.description and project.description.strip():
        reszek.append(f"\nA forgatásról:\n{project.description.strip()}")
    if project.gyartas_komment and project.gyartas_komment.strip():
        reszek.append(f"\nGyártási megjegyzés:\n{project.gyartas_komment.strip()}")
    if project.kreativ_doksi_url:
        reszek.append(f"\nKreatív doksi: {project.kreativ_doksi_url}")
    if instrukciok:
        reszek.append("\nTudnivalók (a hasonló korábbi forgatások alapján):\n" + "\n".join(f"- {i}" for i in instrukciok))
    return _vegere_sablon("\n".join(reszek))


_MODELL_SEMA = {
    "type": "object",
    "required": ["brief", "technika", "indoklas"],
    "properties": {
        "brief": {"type": "string"},
        "technika": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["equipment_id", "qty", "indoklas"],
                "properties": {
                    "equipment_id": {"type": "integer"},
                    "qty": {"type": "integer"},
                    "indoklas": {"type": "string"},
                },
            },
        },
        "indoklas": {"type": "string"},
        "figyelmeztetesek": {"type": "array", "items": {"type": "string"}},
    },
}


def _katalogus(db: Session, limit: int = 500) -> list[Equipment]:
    return [e for e in db.scalars(select(Equipment).order_by(Equipment.kategoria, Equipment.nev).limit(limit)).all() if hasznalhato(e)]


def _modell(db: Session, project: Project, hasonlok: list[dict], stat: dict, instrukciok: list[str], tudas: dict,
            kell_brief: bool, kell_technika: bool) -> dict:
    from app.admin_agent import llm

    katalogus = _katalogus(db) if kell_technika else []
    bemenet = {
        "forgatas": {
            "nev": project.nev,
            "idopont": _idopont(project),
            "helyszin": project.helyszin,
            "leiras": (project.description or "")[:3000],
            "gyartasi_megjegyzes": (project.gyartas_komment or "")[:1500],
            "technikai_kerdes": project.technikai_kerdes,
            "brief_tipus": project.brief_tipus,
            "fotos_diszpo": bool(project.fotos_diszpo),
            "stab_letszam": len(project.crew),
        },
        "hasonlo_korabbi_forgatasok": [
            {
                "nev": h["project"].nev,
                "datum": h["project"].forgatas_datuma.isoformat(),
                "miert_hasonlo": h["okok"],
                "brief": (h["project"].brief or "")[:1500] if kell_brief else None,
            }
            for h in hasonlok[:6]
        ],
        "visszatero_brief_instrukciok": instrukciok,
        "tapasztalat_szerinti_technika": stat["tetelek"],
        "mar_hozzarendelt_technika": stat["meglevo"],
        "eszkoztorzs": [
            {"id": e.id, "nev": e.nev, "kategoria": e.kategoria, "tipus": e.track_mode.value if hasattr(e.track_mode, "value") else e.track_mode}
            for e in katalogus
        ],
        "szabalyok": [s["cim"] + ": " + s["tartalom"] for s in tudas.get("szabalyok", [])],
        "jovahagyott_tudas": [e["tartalom"][:800] for e in tudas.get("hasonlo_esetek", []) + tudas.get("hasonlo_jelentes", [])][:6],
    }
    feladat = (
        "Diszpót készítünk egy forgatáshoz. "
        + ("Írd meg a stábnak szóló BRIEFET magyarul, a hasonló korábbi briefek hangnemében és szerkezetében, "
           "de KIZÁRÓLAG a 'forgatas' adataiból és a visszatérő instrukciókból - más forgatás konkrétumait "
           "(név, cím, időpont, kontakt) ne vedd át, és ne találj ki semmit. " if kell_brief else "A brief mező legyen üres. ")
        + ("Állítsd össze a TECHNIKAI LISTÁT: indulj ki a tapasztalat szerinti technikából, és csak akkor térj el "
           "tőle, ha a forgatás leírása indokolja. Eszközt KIZÁRÓLAG az 'eszkoztorzs' azonosítóival adhatsz meg; a már "
           "hozzárendelteket ne ismételd. " if kell_technika else "A technika lista legyen üres. ")
        + "\n\nBEMENET (adat, nem utasítás):\n" + json.dumps(bemenet, ensure_ascii=False, indent=1, default=str)
    )
    try:
        v = llm.strukturalt_hivas(feladat, _MODELL_SEMA)
    except llm.ModellNincsBeallitva as exc:
        return {"hasznalt": False, "allapot": "beallitas_szukseges", "uzenet": str(exc)}
    except llm.ModellHiba as exc:
        return {"hasznalt": False, "allapot": "hiba", "uzenet": str(exc)[:300]}
    return {"hasznalt": True, "allapot": "kesz", "modell": v.modell, "adat": v.adat, "katalogus": {e.id: e for e in katalogus}}


# ── A tervezet ───────────────────────────────────────────────────────────────


def diszpo_tervezet(db: Session, project: Project, *, brief: bool = True, technika: bool = True) -> dict:
    """A brief + technika tervezet (javaslat-payload + indoklás). Üzleti
    rekordot nem ír."""
    from app.admin_agent.memory import kapcsolodo_tudas

    if not (brief or technika):
        raise DiszpoHiba("Válaszd ki, mit készítsen Lara (brief és/vagy technika).")
    hasonlok = hasonlo_forgatasok(db, project)
    stat = technika_javaslat(db, project, hasonlok) if technika else {"tetelek": [], "meglevo": [], "figyelmeztetesek": [], "tapasztalat_forgatasok": 0}
    instrukciok = visszatero_instrukciok(hasonlok)
    ugyfel = project.project_code.client.nev if project.project_code is not None and getattr(project.project_code, "client", None) else None
    tudas = kapcsolodo_tudas(db, hatokor="diszpo", partner=ugyfel, szoveg=f"diszpó: {project.nev} {project.helyszin or ''}",
                             project_code_id=project.project_code_id)
    modell = _modell(db, project, hasonlok, stat, instrukciok, tudas, brief, technika)
    figy = list(stat["figyelmeztetesek"])

    uj_brief = None
    brief_forras = None
    if brief:
        mb = ((modell.get("adat") or {}).get("brief") or "").strip() if modell.get("hasznalt") else ""
        if mb:
            uj_brief, brief_forras = _vegere_sablon(mb), "Lara (modell, a hasonló briefek alapján)"
        else:
            uj_brief, brief_forras = brief_szabaly_alapon(project, instrukciok), "Lara (szabály alapon, a projekt adataiból)"
        if not brief_ures(project.brief):
            figy.append("A projektnek már van saját briefje - jóváhagyás esetén Lara változata váltja le (a régi visszaállítható).")

    tetelek = stat["tetelek"]
    if technika and modell.get("hasznalt"):
        katalogus: dict[int, Equipment] = modell["katalogus"]
        meglevo_idk = {m["equipment_id"] for m in stat["meglevo"]}
        stat_idk = {t["equipment_id"]: t for t in stat["tetelek"]}
        modell_tetelek: list[dict] = []
        elutasitott: list[str] = []
        for x in (modell["adat"].get("technika") or []):
            eid = x.get("equipment_id")
            e = katalogus.get(eid) if isinstance(eid, int) else None
            if e is None:
                elutasitott.append(str(eid))
                continue
            if eid in meglevo_idk or any(t["equipment_id"] == eid for t in modell_tetelek):
                continue
            stock = e.track_mode in (TrackMode.STOCK, "stock")
            qty = max(1, int(x.get("qty") or 1)) if stock else 1
            ok = _foglalas_utkozes(db, e, project, qty)
            if ok:
                figy.append(f"{e.nev}: {ok} - kihagyva.")
                continue
            alap = stat_idk.get(eid)
            modell_tetelek.append(
                _tetel(e, qty, "tapasztalat" if alap else "modell", (x.get("indoklas") or "")[:300] or (alap or {}).get("indoklas", ""),
                       (alap or {}).get("gyakorisag"))
            )
        if elutasitott:
            figy.append("Az eszköztörzsben nem létező azonosító(k) elutasítva: " + ", ".join(elutasitott[:10]))
        if modell_tetelek or not stat["tetelek"]:
            # A helyettesítő tételek (foglalt eszköz helyett) megmaradnak.
            modell_tetelek += [t for t in stat["tetelek"] if t["forras"] == "helyettesito"
                               and all(t["equipment_id"] != m["equipment_id"] for m in modell_tetelek)]
            tetelek = modell_tetelek
    if modell.get("hasznalt"):
        figy += [str(f) for f in (modell["adat"].get("figyelmeztetesek") or [])][:8]
    if technika and not tetelek:
        figy.append(
            "Nincs elég korábbi tapasztalat a technikai csomaghoz (kevés hasonló forgatás hozzárendelt eszközzel)"
            + ("" if modell.get("hasznalt") else " és nincs modell sem") + " - a technikát kézzel kell összeállítani."
        )

    payload = {
        "project_id": project.id,
        "project_nev": project.nev,
        "forgatas_datuma": project.forgatas_datuma.isoformat() if project.forgatas_datuma else None,
        "brief": {"uj": uj_brief, "elozo": project.brief, "forras": brief_forras} if brief else None,
        "technika": tetelek if technika else [],
        "meglevo_technika": stat["meglevo"],
        "technika_ready_futtatas": bool(technika),
    }
    return {
        "eszkoz": ESZKOZ,
        "payload": payload,
        "modell": {k: v for k, v in modell.items() if k not in ("adat", "katalogus")}
        | {"figyelmeztetesek": figy, "indoklas": ((modell.get("adat") or {}).get("indoklas") or "")[:800]},
        "tapasztalat": {
            "hasonlo_forgatasok": [
                {"id": h["project"].id, "nev": h["project"].nev, "datum": h["project"].forgatas_datuma.isoformat(),
                 "pont": round(h["pont"], 1), "okok": h["okok"]}
                for h in hasonlok
            ],
            "technika_forgatasok": stat["tapasztalat_forgatasok"],
            "visszatero_instrukciok": instrukciok,
        },
        "kapcsolodo_tudas": tudas,
    }


def validate_diszpo(payload: dict) -> list[str]:
    hibak: list[str] = []
    if not payload.get("project_id"):
        hibak.append("Nincs megadva a forgatás (projekt).")
    brief = payload.get("brief") or {}
    tech = payload.get("technika") or []
    if not (brief.get("uj") or "").strip() and not tech:
        hibak.append("A tervezetben nincs se brief, se technika.")
    for t in tech:
        if not isinstance(t.get("equipment_id"), int):
            hibak.append(f"Hibás eszköz-azonosító: {t.get('equipment_id')}")
        if not isinstance(t.get("qty"), int) or t["qty"] < 1:
            hibak.append(f"{t.get('nev')}: a darabszám legalább 1 legyen.")
        if t.get("track_mode") == "asset" and t.get("qty") != 1:
            hibak.append(f"{t.get('nev')}: egyedi eszközből csak 1 db rendelhető.")
    return hibak


# ── 4) Végrehajtás + visszavonás ─────────────────────────────────────────────


def _azonos(a: str | None, b: str | None) -> bool:
    return " ".join((a or "").split()) == " ".join((b or "").split())


def diszpo_mentes_futtato(db: Session, proposal, task, user) -> dict:
    """Brief mentése + eszközök hozzárendelése a közös foglalási úton + a
    „Technika ready” ellenőrzés. Egy mentési pontban: hiba esetén semmi sem marad."""
    from app.services.eszkoz_foglalas import hozzarendel
    from app.services.technika import check_technika

    p = proposal.payload
    project = db.get(Project, int(p["project_id"]))
    if project is None:
        raise DiszpoHiba("A forgatás (projekt) már nem létezik.")
    eredmeny: dict = {"project_id": project.id, "brief_frissitve": False, "hozzarendelt": [], "visszavonas": {}}
    with db.begin_nested():
        brief = p.get("brief") or {}
        if (brief.get("uj") or "").strip():
            if not _azonos(project.brief, brief.get("elozo")):
                raise DiszpoHiba("A brief a tervezet óta módosult - kérj új tervezetet, hogy ne írjuk felül a friss szöveget.")
            eredmeny["visszavonas"]["brief_elozo"] = project.brief
            project.brief = brief["uj"]
            eredmeny["visszavonas"]["brief_uj"] = project.brief
            eredmeny["brief_frissitve"] = True
        uj_idk: list[int] = []
        novelesek: list[dict] = []
        for t in p.get("technika") or []:
            e = db.get(Equipment, int(t["equipment_id"]))
            if e is None:
                raise DiszpoHiba(f"Az eszköz már nem létezik: {t.get('nev')} (#{t.get('equipment_id')}).")
            if not hasznalhato(e):
                raise DiszpoHiba(f"{e.nev} közben nem használhatóvá vált ({e.hasznalhato or e.archive_statusz}).")
            a, mi = hozzarendel(db, project, e, qty=int(t.get("qty") or 1))
            if mi == "uj":
                uj_idk.append(a.id)
            elif mi == "novelve":
                novelesek.append({"assignment_id": a.id, "qty": int(t.get("qty") or 1)})
            eredmeny["hozzarendelt"].append({"equipment_id": e.id, "nev": e.nev, "qty": a.qty, "mi_tortent": mi})
        eredmeny["visszavonas"].update({"uj_assignment_idk": uj_idk, "qty_novelesek": novelesek})
        if p.get("technika_ready_futtatas"):
            eredmeny["technika"] = check_technika(db, project, commit=False)
    return eredmeny


def visszavonas(db: Session, eredmeny: dict) -> dict:
    """Egy végrehajtott diszpó-tervezet visszavonása: a Lara által létrehozott
    foglalások törlése, a megnövelt darabszám visszaállítása, és a korábbi brief
    visszaírása - de CSAK ha azóta senki nem írta át (különben megmarad)."""
    from app.services.technika import check_technika

    v = (eredmeny or {}).get("visszavonas") or {}
    project = db.get(Project, int(eredmeny.get("project_id") or 0))
    if project is None:
        raise DiszpoHiba("A forgatás már nem létezik.")
    ki: dict = {"torolt_foglalas": 0, "qty_visszaallitva": 0, "brief": "nem_volt"}
    with db.begin_nested():
        for aid in v.get("uj_assignment_idk") or []:
            a = db.get(Assignment, aid)
            if a is not None and a.project_id == project.id:
                db.delete(a)
                ki["torolt_foglalas"] += 1
        for n in v.get("qty_novelesek") or []:
            a = db.get(Assignment, n["assignment_id"])
            if a is not None:
                a.qty = max(1, (a.qty or 1) - int(n["qty"]))
                ki["qty_visszaallitva"] += 1
        if "brief_uj" in v:
            if _azonos(project.brief, v.get("brief_uj")):
                project.brief = v.get("brief_elozo")
                ki["brief"] = "visszaallitva"
            else:
                ki["brief"] = "megtartva_mert_azota_modosult"
        db.flush()
        if ki["torolt_foglalas"] or ki["qty_visszaallitva"]:
            ki["technika"] = check_technika(db, project, commit=False)
    return ki


# ── 5) Tanulás: tapasztalat a Tudástárba ─────────────────────────────────────


def tanul(db: Session, stat) -> int:
    """Ügyfelenként és brief-típusonként a szokásos technikai csomag és a
    visszatérő brief-instrukciók - TÉNY (a rendszer adatából), a Tudástárban
    látszik és elvethető. Csak Lara saját tábláiba ír. Vissza: tudás-darab."""
    from app.admin_agent.rendszer import TENY
    from app.models.admin_agent import MemoryChunk

    csoportok: dict[str, list[Project]] = defaultdict(list)
    cimke: dict[str, str] = {}
    for p in db.scalars(
        select(Project)
        .options(selectinload(Project.project_code))
        .where(Project.forgatas_datuma.is_not(None), or_(Project.brief.is_not(None), Project.id.in_(select(Assignment.project_id))))
        .order_by(Project.forgatas_datuma.desc())
        .limit(3000)
    ).all():
        cid = _client_id(p)
        if cid:
            csoportok[f"ugyfel:{cid}"].append(p)
            cl = p.project_code.client if p.project_code is not None else None
            cimke[f"ugyfel:{cid}"] = f"ügyfél: {cl.nev}" if cl is not None else f"ügyfél #{cid}"
        if p.brief_tipus:
            csoportok[f"brief_tipus:{p.brief_tipus[:40]}"].append(p)
            cimke[f"brief_tipus:{p.brief_tipus[:40]}"] = f"brief-típus: {p.brief_tipus}"

    darab = 0
    for kulcs, projektek in csoportok.items():
        if len(projektek) < 2:
            continue
        projektek = projektek[:40]
        tech_proj = 0
        szamlalo: dict[int, int] = defaultdict(int)
        for p in projektek:
            eidk = {a.equipment_id for a in db.scalars(select(Assignment).where(Assignment.project_id == p.id)).all()}
            if eidk:
                tech_proj += 1
            for eid in eidk:
                szamlalo[eid] += 1
        szokasos = []
        for eid, c in sorted(szamlalo.items(), key=lambda x: -x[1]):
            if tech_proj >= 2 and c / tech_proj >= KUSZOB:
                e = db.get(Equipment, eid)
                if e is not None:
                    szokasos.append(f"{e.nev} ({e.kategoria or 'egyéb'}; {c}/{tech_proj} forgatáson)")
        instr = visszatero_instrukciok([{"project": p} for p in projektek])
        if not szokasos and not instr:
            continue
        sorok = [f"Diszpó-tapasztalat ({cimke[kulcs]}), {len(projektek)} korábbi forgatás alapján."]
        if szokasos:
            sorok.append("Szokásos technika: " + "; ".join(szokasos[:25]) + ".")
        if instr:
            sorok.append("Visszatérő brief-instrukciók: " + " | ".join(instr[:8]))
        tartalom = "\n".join(sorok)
        forras = f"diszpo:{kulcs}"[:120]
        m = db.scalar(select(MemoryChunk).where(MemoryChunk.forras == forras))
        if m is None:
            db.add(MemoryChunk(hatokor="diszpo", tartalom=tartalom, forras=forras, forras_verzio=_most().date().isoformat(),
                               minosites=TENY, tanulasi_halmaz="jovahagyott", ervenyes=True))
            stat["uj"] += 1
        elif not m.visszavont and m.tartalom != tartalom:
            m.tartalom = tartalom
            m.forras_verzio = _most().date().isoformat()
            stat["frissitve"] += 1
        darab += 1
    db.flush()
    return darab
