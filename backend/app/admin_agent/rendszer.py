"""Lara — a TELJES rendszer figyelése (csak tanulás, csak olvasás).

A felhasználó kérése: Lara lássa át az egész HYPE OS-t, figyelje és tanuljon
belőle — de a feladata a jövőben is KIZÁRÓLAG az adminisztráció marad (számla,
TIG, szerződés, e-mail, papírozás; lásd `enums.ADMIN_FELADATTIPUSOK` és a
végrehajtó hatáskör-őrét). Ez a modul ezért:

* csak OLVAS az üzleti táblákból, és csak Lara saját tábláiba ír
  (`aa_memory_chunks`, `aa_learning_runs`) — üzleti rekord nem változik;
* két fajta tudást készít, mindkettő TÉNY (a rendszer állapota, nem döntés),
  ezért ember-jóváhagyás nélkül használható, de a Tudástárban látszik és
  elvethető:
    1. **Rendszerismeret modulonként** — mi ez a modul (a modell leírásából),
       mennyi rekord van benne, mennyi mozgás volt az elmúlt 30 napban, milyen
       állapotokban állnak a tételek;
    2. **Projektkód-életút** — egy projektkódhoz a rendszer MINDEN részében
       kötődő tételek (diszpó, forgatás, utómunka, portál, anyagbekérés,
       szerződés, TIG, kiadás, bevétel…) darabszámmal és állapottal. Ebből tudja
       Lara pl. egy TIG-nél, hogy az utómunka már leadva, a portál kiküldve.
* a személyes / titkos adatokat NEM olvassa: kimaradnak a hitelesítési,
  értesítési, felület-beállítási, személyes (munkatárs-adatlap, dokumentum)
  táblák, és minden jelszó-, token-, kulcs-, bankszámla-, adóazonosító-,
  e-mail-, telefon-, lakcím-jellegű mező. Szabad szöveget nem másol ki, csak
  számlál és az állapot-jellegű (kevés értékű) mezőket összesíti.
* Engedélyhez kötött (`engedett_forrasok.rendszer`), vészleállításnál nem fut.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.admin_agent.observer import tanulas_kezdete
from app.admin_agent.settings_service import get_settings
from app.core.database import Base
from app.models.admin_agent import LearningRun, MemoryChunk

FORRAS = "rendszer"
HATOKOR = "rendszer"
#: A rendszer-tudás minősítése: tény (a rendszer állapota), nem döntés.
TENY = "rendszer_teny"
#: Egy futás legfeljebb ennyi projektkód életútját frissíti.
MAX_PROJEKTKOD = 300
#: Állapot-jellegű mező: legfeljebb ennyi különböző érték (különben szöveg).
MAX_ALLAPOT_ERTEK = 30

#: Soha nem olvasott táblák: Lara saját táblái, az AI asszisztens (külön
#: forrás), hitelesítés/értesítés/push, felület-beállítások, személyes adatlap.
KIZART_ELOTAGOK = ("aa_", "ai_")
KIZART_TABLAK = frozenset({
    "google_oauth_tokens", "push_devices", "push_deliveries", "notifications", "notification_preferences",
    "page_access_configs", "notion_import_map", "calendar_sync_state", "hatter_feladatok",
    "dashboard_configs", "deliverable_board_configs", "deliverable_status_configs", "detail_section_orders",
    "detail_tab_configs", "entity_field_configs", "field_visibility_configs", "custom_field_defs",
    "diszpo_nezetek", "employees", "employee_documents", "krumpello_dolgozok", "vallalkozas_tagok",
    "torolt_rekordok",
})
#: Érzékeny mezőnév-minták — ezekből semmit nem olvasunk.
ERZEKENY = re.compile(
    r"password|jelszo|token|secret|hash|api_key|_key$|iban|bankszamla|adoazonosito|\btaj|szemelyi|lakcim|"
    r"anyja|szulet|telefon|email|refresh|oauth|cookie|url$",
    re.IGNORECASE,
)
#: Állapot-jellegű mezők (ezeket összesítjük).
ALLAPOT_MINTA = re.compile(r"^(allapot|status|statusz|kesz|tipus|fazis)$|_(allapota|statusza|allapot|status)$")

#: Ismert táblák emberi neve (a többinél a modell leírásának eleje).
MODUL_NEV = {
    "project_codes": "Projektkódok", "projects": "Forgatások (projektek)", "callsheets": "Diszpó",
    "diszpo_munkalapok": "Diszpó-táblák", "diszpo_sorok": "Diszpó-tábla sorai", "diszpo_cellak": "Diszpó-cellák",
    "deliverables": "Utómunka anyagok", "deliverable_comments": "Utómunka kommentek",
    "portals": "Média Portál", "portal_videos": "Portál videók", "payments": "Portál fizetések",
    "anyagbekeresek": "Anyagbekérők", "anyag_leadasok": "Anyagleadások", "tasks": "Feladatok",
    "hype_todo_items": "HYPE teendők", "flora_feladatok": "Flóra-feladatok", "contracts": "Alvállalkozói szerződések",
    "performance_certificates": "Külsős TIG-ek", "internal_performance_certificates": "Belsős TIG-ek",
    "megrendeloi_szerzodesek": "Megrendelői szerződések", "megrendeloi_tigek": "Megrendelői TIG-ek",
    "expenses": "Kiadások", "revenues": "Bevételek", "kp_forgalmak": "Házipénztár", "bejovo_szamlak": "Beérkező számlák",
    "utalas_tetelek": "Utalások felvezetése", "kotelezettsegek": "Kötelezettségek", "autok": "Autók",
    "equipment": "Eszközök", "eszkoz_kivitelek": "Eszközkivitelek", "stocktake_sessions": "Leltárak",
    "clients": "Ügyfelek", "contacts": "Megrendelői kontaktok", "arajanlatok": "Árajánlatok",
    "munka_arajanlatok": "Munkafelajánlások", "ajanlatkeresek": "Ajánlatkérések", "campaigns": "Kampányok",
    "timesheets": "Munkaidő", "timeline_events": "Idővonal", "project_crew": "Stáb-beosztás",
    "keret_modositasok": "Keretszerződés-módosítások", "vallalkozasok": "Vállalkozások",
    "video_igenyek": "Videóigények", "post_shoot_feedbacks": "Forgatás utáni visszajelzések",
    "document_attachments": "Csatolt dokumentumok", "project_szamlazok": "Projekt-számlázók",
    "employee_monthly_items": "Havi munkatársi tételek", "assignments": "Kiosztások",
    "media_items": "Médiaelemek", "folders": "Mappák", "project_code_comments": "Projektkód-kommentek",
    "contract_tetelek": "Szerződés-tételek", "performance_certificate_tetelek": "TIG-tételek",
    "eszkoz_kivitel_tetelek": "Eszközkivitel-tételek", "krumpello_kiadasok": "Krumpelló-kiadások",
}


def _most() -> datetime:
    return datetime.now(timezone.utc)


def engedelyezve(db: Session) -> bool:
    return bool((get_settings(db).engedett_forrasok or {}).get(FORRAS))


def _figyelt_tablak(db: Session) -> dict[str, Any]:
    """tábla → Table objektum, a kizártak nélkül — csak ami az adatbázisban
    TÉNYLEGESEN létezik (egy még nem migrált modell nem állíthatja meg)."""
    from sqlalchemy import inspect

    import app.models  # noqa: F401 — minden modell regisztrálva legyen

    letezo = set(inspect(db.get_bind()).get_table_names())
    return {
        n: t for n, t in Base.metadata.tables.items()
        if n in letezo and not n.startswith(KIZART_ELOTAGOK) and n not in KIZART_TABLAK
    }


def _leiras(tabla: str) -> str:
    for m in Base.registry.mappers:
        if m.local_table is not None and m.local_table.name == tabla:
            doc = (m.class_.__doc__ or "").strip().split("\n")[0].strip()
            return re.split(r"(?<=[.!?])\s", doc)[0][:160] if doc else ""
    return ""


def modul_nev(tabla: str) -> str:
    return MODUL_NEV.get(tabla) or tabla.replace("_", " ")


def _allapot_oszlopok(t) -> list:
    return [c for c in t.c if ALLAPOT_MINTA.search(c.name) and not ERZEKENY.search(c.name)]


def _eloszlas(db: Session, t, oszlop, felt=None) -> list[tuple[str, int]] | None:
    """Egy állapot-jellegű oszlop értékeloszlása (None, ha túl sok az érték)."""
    q = select(oszlop, func.count()).group_by(oszlop).order_by(func.count().desc())
    if felt is not None:
        q = q.where(felt)
    sorok = db.execute(q.limit(MAX_ALLAPOT_ERTEK + 1)).all()
    if len(sorok) > MAX_ALLAPOT_ERTEK:
        return None
    ki = []
    for v, n in sorok:
        if v is None or (isinstance(v, str) and not v.strip()):
            continue
        cimke = ("igen" if v else "nem") if isinstance(v, bool) else str(v)[:40]
        ki.append((cimke, int(n)))
    return ki


def _ment(db: Session, forras: str, tartalom: str, verzio: str, *, regi: bool = False) -> str:
    m = db.scalar(select(MemoryChunk).where(MemoryChunk.forras == forras))
    if m is None:
        db.add(MemoryChunk(
            hatokor=HATOKOR, tartalom=tartalom, forras=forras, forras_verzio=verzio, minosites=TENY,
            tanulasi_halmaz="jovahagyott", ervenyes=True, regi_korszak=regi,
        ))
        return "uj"
    if m.visszavont:
        return "elvetve"  # ember elvetette — nem írjuk vissza
    if m.tartalom != tartalom:
        m.tartalom = tartalom  # a vektor ilyenkor magától érvénytelenül
        m.forras_verzio = verzio
        m.regi_korszak = regi
        return "frissitve"
    return "valtozatlan"


# ── 1) Rendszerismeret modulonként ───────────────────────────────────────────


def _modul_ismeret(db: Session, tablak: dict[str, Any], stat: Counter) -> list[dict]:
    most = _most()
    harminc = most - timedelta(days=30)
    aktivitas: list[dict] = []
    for nev, t in sorted(tablak.items()):
        if "id" not in t.c:
            continue
        try:
            with db.begin_nested():
                aktivitas.append(_modul(db, nev, t, harminc, most, stat))
        except Exception:  # noqa: BLE001 — egy hibás tábla ne állítsa meg a figyelést
            stat["hibas_tabla"] += 1
    return aktivitas


#: Mihez kötődhet egy modul tétele (oszlop → emberi szöveg).
_KOTESEK = (("project_code_id", "projektkódhoz"), ("project_id", "forgatáshoz"),
            ("employee_id", "munkatárshoz"), ("client_id", "ügyfélhez"))


def _modul(db: Session, nev: str, t, harminc: datetime, most: datetime, stat: Counter) -> dict:
    ossz = db.scalar(select(func.count()).select_from(t)) or 0
    uj = modositott = 0
    if "created_at" in t.c:
        uj = db.scalar(select(func.count()).select_from(t).where(t.c.created_at >= harminc)) or 0
    if "updated_at" in t.c:
        modositott = db.scalar(select(func.count()).select_from(t).where(t.c.updated_at >= harminc)) or 0
    adat = {"tabla": nev, "modul": modul_nev(nev), "osszes": ossz, "uj_30": uj, "modositott_30": modositott}
    if ossz == 0:
        return adat
    reszek = [f"Rendszerismeret — {modul_nev(nev)} (`{nev}`)"]
    leiras = _leiras(nev)
    if leiras:
        reszek[0] += f": {leiras}"
    reszek.append(f"Összesen {ossz} tétel; az elmúlt 30 napban {uj} új és {modositott} módosított.")
    kotes = [szoveg for oszlop, szoveg in _KOTESEK if oszlop in t.c]
    if kotes:
        reszek.append("Kötődik: " + ", ".join(kotes) + ".")
    for o in _allapot_oszlopok(t)[:3]:
        e = _eloszlas(db, t, o)
        if e:
            reszek.append(f"{o.name}: " + ", ".join(f"{v} ({n})" for v, n in e[:8]) + ".")
    stat[_ment(db, f"{FORRAS}:modul:{nev}", " ".join(reszek), most.date().isoformat())] += 1
    return adat


# ── 2) Projektkód-életút ─────────────────────────────────────────────────────


def _projektkod_eletut(db: Session, tablak: dict[str, Any], tol: datetime, stat: Counter) -> int:
    from app.models.project import Project
    from app.models.project_code import ProjectCode

    kod_tablak = {n: t for n, t in tablak.items() if "project_code_id" in t.c and n != "project_codes"}
    proj_tablak = {n: t for n, t in tablak.items() if "project_id" in t.c and "project_code_id" not in t.c}
    proj_kod = dict(db.execute(select(Project.id, Project.project_code_id)).all())

    # Mely projektkódoknál volt mozgás `tol` óta (a kód maga vagy bármelyik tétele)?
    utolso: dict[int, datetime] = {}

    def _jelol(pc_id, ido):
        if pc_id and ido and (pc_id not in utolso or ido > utolso[pc_id]):
            utolso[pc_id] = ido

    for pc_id, ido in db.execute(select(ProjectCode.id, ProjectCode.updated_at).where(ProjectCode.updated_at >= tol)).all():
        _jelol(pc_id, ido)
    for t in kod_tablak.values():
        if "updated_at" in t.c:
            for pc_id, ido in db.execute(
                select(t.c.project_code_id, func.max(t.c.updated_at)).where(t.c.updated_at >= tol)
                .group_by(t.c.project_code_id)
            ).all():
                _jelol(pc_id, ido)
    for t in proj_tablak.values():
        if "updated_at" in t.c:
            for p_id, ido in db.execute(
                select(t.c.project_id, func.max(t.c.updated_at)).where(t.c.updated_at >= tol).group_by(t.c.project_id)
            ).all():
                _jelol(proj_kod.get(p_id), ido)
    if not utolso:
        return 0
    idk = [pc for pc, _ in sorted(utolso.items(), key=lambda x: x[1], reverse=True)[:MAX_PROJEKTKOD]]

    # Tételszám + állapot-eloszlás táblánként, a kiválasztott kódokra.
    darab: dict[int, dict[str, int]] = defaultdict(dict)
    allapot: dict[int, dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
    for nev, t in kod_tablak.items():
        oszlop = next(iter(_allapot_oszlopok(t)), None)
        cols = [t.c.project_code_id] + ([oszlop] if oszlop is not None else [])
        for sor in db.execute(select(*cols, func.count()).where(t.c.project_code_id.in_(idk)).group_by(*cols)).all():
            pc_id, n = sor[0], int(sor[-1])
            darab[pc_id][nev] = darab[pc_id].get(nev, 0) + n
            if oszlop is not None and sor[1] not in (None, ""):
                allapot[pc_id][nev][str(sor[1])[:30]] += n
    kod_proj: dict[int, list[int]] = defaultdict(list)
    for p_id, pc_id in proj_kod.items():
        if pc_id in utolso:
            kod_proj[pc_id].append(p_id)
    osszes_proj = [p for pc in idk for p in kod_proj.get(pc, [])]
    if osszes_proj:
        for nev, t in proj_tablak.items():
            oszlop = next(iter(_allapot_oszlopok(t)), None)
            cols = [t.c.project_id] + ([oszlop] if oszlop is not None else [])
            for sor in db.execute(select(*cols, func.count()).where(t.c.project_id.in_(osszes_proj)).group_by(*cols)).all():
                pc_id, n = proj_kod.get(sor[0]), int(sor[-1])
                if pc_id is None:
                    continue
                darab[pc_id][nev] = darab[pc_id].get(nev, 0) + n
                if oszlop is not None and sor[1] not in (None, ""):
                    allapot[pc_id][nev][str(sor[1])[:30]] += n

    kezdet = tanulas_kezdete(db)
    for pc in db.scalars(select(ProjectCode).where(ProjectCode.id.in_(idk))).all():
        fej = f"Projektkód-életút — {pc.projektkod}"
        if (pc.project_nev or "").strip():
            fej += f" · {pc.project_nev.strip()}"
        if (pc.megrendelo_neve or "").strip():
            fej += f" (megrendelő: {pc.megrendelo_neve.strip()})"
        if (pc.esemeny_allapota or "").strip():
            fej += f", esemény állapota: {pc.esemeny_allapota.strip()}"
        tetelek = []
        for nev in sorted(darab.get(pc.id, {}), key=lambda n: modul_nev(n)):
            n = darab[pc.id][nev]
            a = allapot[pc.id].get(nev)
            reszlet = f" ({', '.join(f'{v}: {k}' for v, k in a.most_common(4))})" if a else ""
            tetelek.append(f"{modul_nev(nev)}: {n}{reszlet}")
        forgatas = len(kod_proj.get(pc.id, []))
        szoveg = (
            fej + ". A rendszerben: " + ("; ".join(tetelek) if tetelek else "még nincs hozzá kötött tétel")
            + (f". Forgatások száma: {forgatas}" if forgatas else "")
            + f". Utolsó mozgás: {utolso[pc.id].date().isoformat()}."
        )
        regi = pc.created_at is None or pc.created_at < kezdet
        stat[_ment(db, f"{FORRAS}:projektkod:{pc.id}", szoveg, utolso[pc.id].isoformat(), regi=regi)] += 1
    return len(idk)


# ── Futtatás + állapot ───────────────────────────────────────────────────────


def _utolso_futas(db: Session) -> datetime | None:
    r = db.scalar(
        select(LearningRun).where(LearningRun.trigger.like(f"{FORRAS}:%")).order_by(LearningRun.id.desc()).limit(1)
    )
    return r.kezdes_at if r is not None else None


def rendszer_figyeles(db: Session, *, trigger: str = "rendszer:kezi", kenyszeritett: bool = False) -> dict:
    """Egy rendszer-figyelő futás. A hívó commitál. Csak olvas az üzleti
    táblákból; csak `aa_memory_chunks` / `aa_learning_runs` írás."""
    if not kenyszeritett and not engedelyezve(db):
        return {"allapot": "kikapcsolva"}
    kezd = _most()
    tablak = _figyelt_tablak(db)
    stat: Counter = Counter()
    aktivitas = _modul_ismeret(db, tablak, stat)
    utolso = _utolso_futas(db)
    tol = max(tanulas_kezdete(db), (utolso - timedelta(hours=1)) if utolso else tanulas_kezdete(db))
    kodok = _projektkod_eletut(db, tablak, tol, stat)
    leg = sorted(aktivitas, key=lambda a: a["uj_30"] + a["modositott_30"], reverse=True)
    osszefoglalo = {
        "figyelt_tabla": len(tablak),
        "kizart_tabla": len(Base.metadata.tables) - len(tablak),
        "modul_tudas": sum(1 for a in aktivitas if a["osszes"]),
        "projektkod": kodok,
        "uj": stat["uj"],
        "frissitett": stat["frissitve"],
        "mozgas_30nap": sum(a["uj_30"] + a["modositott_30"] for a in aktivitas),
        "legaktivabb": [
            {"modul": a["modul"], "tabla": a["tabla"], "mozgas": a["uj_30"] + a["modositott_30"]}
            for a in leg[:8] if a["uj_30"] + a["modositott_30"]
        ],
    }
    db.add(LearningRun(trigger=trigger, allapot="kesz", kezdes_at=kezd, veg_at=_most(), osszefoglalo=osszefoglalo))
    db.flush()
    return osszefoglalo


def allapot(db: Session) -> dict:
    from app.admin_agent.settings_service import leallitva

    futasok = db.scalars(
        select(LearningRun).where(LearningRun.trigger.like(f"{FORRAS}:%")).order_by(LearningRun.id.desc()).limit(10)
    ).all()
    tudas = db.scalars(select(MemoryChunk).where(MemoryChunk.forras.like(f"{FORRAS}:%"))).all()
    return {
        "engedelyezve": engedelyezve(db),
        "leallitva": leallitva(db),
        "modul_tudas": sum(1 for m in tudas if m.forras.startswith(f"{FORRAS}:modul:") and not m.visszavont),
        "projektkod_tudas": sum(1 for m in tudas if m.forras.startswith(f"{FORRAS}:projektkod:") and not m.visszavont),
        "utolso": (futasok[0].osszefoglalo or {}) if futasok else None,
        "futasok": [
            {"id": f.id, "trigger": f.trigger, "veg_at": f.veg_at.isoformat() if f.veg_at else None,
             **{k: (f.osszefoglalo or {}).get(k) for k in ("figyelt_tabla", "projektkod", "uj", "frissitett", "mozgas_30nap")}}
            for f in futasok
        ],
    }
