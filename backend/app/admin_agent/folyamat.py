"""A tanulási folyamat ELLENŐRIZHETŐSÉGE (2026-09, A fázis).

Két kérdésre ad választ, a tényleges állapotból (nem becslés):

1. Forrásonként (megfigyelés, levelezés, AI asszisztens, rendszer-figyelés,
   tapasztalás, önellenőrzés, háttér-tanuló, beágyazás, gyors visszacsatolás,
   automatikus számla-elemzés): mikor futott utoljára sikeresen, mi vár
   feldolgozásra, volt-e hiba, és ha nem fut, MIÉRT. Az állapotok külön:
   - `nincs_adat`: még nem futott, és nincs mit feldolgozni;
   - `kikapcsolva`: a forrás / kapcsoló ki van kapcsolva, vagy Lara le van
     állítva;
   - `nincs_jogosultsag`: a futáshoz szükséges hozzáférés (pl. modell-kulcs,
     Gmail-hitelesítés) nincs beállítva;
   - `feldolgozasi_hiba`: az utolsó futás hibára futott (az utolsó siker
     után);
   - `jovahagyasra_var`: van feldolgozott, de emberi jóváhagyásra váró
     eredmény;
   - `rendben`.
2. Egy tudás-darab ÚTJA (`nyomvonal`): honnan jött (forrás, forrásesemény),
   ki és mikor hagyta jóvá, mikor vált használhatóvá, hányszor és mikor került
   Lara elé, és mely szabály hivatkozik rá.

A futásnapló (`LearningRun`, trigger = `folyamat:<forrás>`) forrásonként EGY
sor: az utolsó siker, az utolsó hiba (rövid, titok nélkül), az utolsó
kihagyás oka és a számlálók. Így korlátos marad, és nem kell törölni.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.admin_agent import LearningRun, MemoryChunk

ELOTAG = "folyamat:"
MAX_HIBA_NAPLO = 10

#: forrás-kulcs -> (cím, a Celery-feladat neve)
FORRASOK: dict[str, str] = {
    "observer": "Megfigyelés (lezárt emberi munka)",
    "levelezes": "Levelezés olvasása (szamla@)",
    "asszisztens": "AI asszisztens figyelése",
    "rendszer": "Rendszer-figyelés",
    "tapasztalas": "Tapasztalás",
    "self_check": "Önellenőrzés",
    "nightly_distill": "Háttér-tanuló (javításokból)",
    "beagyazas": "Jelentés szerinti kereshetőség (beágyazás)",
    "visszacsatolas": "Gyors visszacsatolás + automatikus számla-elemzés",
    "weekly_eval": "Heti értékelés",
    "napi_osszesito": "Napi összesítő",
}


def _most() -> datetime:
    return datetime.now(timezone.utc)


def _kivonat(eredmeny) -> dict:
    """A futás eredményéből csak a rövid, számszerű mezők (titok / személyes
    adat nem kerül a naplóba)."""
    if not isinstance(eredmeny, dict):
        return {}
    ki = {}
    for k, v in eredmeny.items():
        if isinstance(v, bool) or isinstance(v, (int, float)):
            ki[str(k)[:40]] = v
        if len(ki) >= 20:
            break
    return ki


def naplo(db: Session, forras: str, allapot: str, *, kezdes: datetime | None = None, eredmeny=None,
          hiba: str | None = None) -> None:
    """Egy futás rögzítése a forrás EGY naplósorába. `allapot`: kesz | hiba |
    kihagyva. A hívó commitál."""
    sor = db.scalar(select(LearningRun).where(LearningRun.trigger == ELOTAG + forras))
    if sor is None:
        sor = LearningRun(trigger=ELOTAG + forras, allapot=allapot, osszefoglalo={})
        db.add(sor)
    o = dict(sor.osszefoglalo or {})
    most = _most()
    o["futas_db"] = int(o.get("futas_db") or 0) + 1
    if allapot == "kesz":
        o["utolso_siker"] = most.isoformat()
        o["utolso_eredmeny"] = _kivonat(eredmeny)
    elif allapot == "hiba":
        o["hiba_db"] = int(o.get("hiba_db") or 0) + 1
        o["utolso_hiba"] = {"ido": most.isoformat(), "hiba": (hiba or "")[:300]}
        o["hibak"] = ([o["utolso_hiba"]] + list(o.get("hibak") or []))[:MAX_HIBA_NAPLO]
    else:
        o["utolso_kihagyas"] = {"ido": most.isoformat(), "ok": (hiba or "")[:200]}
    sor.osszefoglalo = o
    sor.allapot = allapot
    sor.kezdes_at = kezdes or most
    sor.veg_at = most


def _naplo_sorok(db: Session) -> dict[str, dict]:
    return {
        r.trigger[len(ELOTAG):]: (r.osszefoglalo or {})
        for r in db.scalars(select(LearningRun).where(LearningRun.trigger.like(ELOTAG + "%"))).all()
    }


def _kapcsolok(db: Session) -> dict[str, tuple[bool, str | None]]:
    """forrás -> (fut-e, ha nem: miért)."""
    from app.admin_agent import asszisztens, embedding, levelezes, observer, rendszer, tapasztalas, visszacsatolas
    from app.admin_agent.settings_service import get_settings

    s = get_settings(db)
    ki: dict[str, tuple[bool, str | None]] = {
        "observer": (observer.engedelyezve(db), "A „Tanulás és megfigyelés” forrás ki van kapcsolva."),
        "levelezes": (levelezes.engedelyezve(db), "A „Levelezés olvasása” forrás ki van kapcsolva."),
        "asszisztens": (asszisztens.engedelyezve(db), "Az „AI asszisztens figyelése” forrás ki van kapcsolva."),
        "rendszer": (rendszer.engedelyezve(db), "A rendszer-figyelés forrás ki van kapcsolva."),
        "tapasztalas": (tapasztalas.bekapcsolva(db), "A tapasztalás ki van kapcsolva (vagy a megfigyelés forrás)."),
        "self_check": (observer.engedelyezve(db), "A „Tanulás és megfigyelés” forrás ki van kapcsolva."),
        "nightly_distill": (bool(s.module_enabled or observer.engedelyezve(db)),
                            "Sem a modul, sem a tanulási forrás nincs bekapcsolva."),
        "beagyazas": (embedding.bekapcsolva(db), "A jelentés szerinti keresés ki van kapcsolva."),
        "visszacsatolas": (visszacsatolas.bekapcsolva(db) or visszacsatolas.auto_elemzes_be(db),
                           "A gyors visszacsatolás és az automatikus számla-elemzés ki van kapcsolva (alapállás)."),
        "weekly_eval": (True, None),
        "napi_osszesito": (True, None),
    }
    return {k: (be, None if be else ok) for k, (be, ok) in ki.items()}


def _jogosultsag_hiany(forras: str) -> str | None:
    from app.admin_agent.integrations import BEALLITAS_SZUKSEGES, integracio_allapotok

    igeny = {"levelezes": "gmail", "beagyazas": "modell", "tapasztalas": None}.get(forras)
    if not igeny:
        return None
    for i in integracio_allapotok():
        if i["kulcs"] == igeny and i["allapot"] == BEALLITAS_SZUKSEGES:
            return i["uzenet"] or f"{i['nev']}: beállítás szükséges."
    return None


def varakozo_munka(db: Session) -> dict:
    """Ami feldolgozásra / emberi döntésre vár (összesítve)."""
    from app.models.admin_agent import Correction, LaraKerdes, Outbox, PlaybookRule

    jelolt = db.scalar(select(func.count(MemoryChunk.id)).where(
        MemoryChunk.ervenyes.is_(False), MemoryChunk.visszavont.is_(False),
        MemoryChunk.minosites.in_(("jelolt", "kezi_jelolt")), MemoryChunk.hatokor != "kezikonyv",
    )) or 0
    kezikonyv = db.scalar(select(func.count(MemoryChunk.id)).where(
        MemoryChunk.hatokor == "kezikonyv", MemoryChunk.ervenyes.is_(False), MemoryChunk.visszavont.is_(False),
    )) or 0
    return {
        "tudas_jelolt": jelolt,
        "kezikonyv_tervezet": kezikonyv,
        "nyitott_kerdes": db.scalar(select(func.count(LaraKerdes.id)).where(LaraKerdes.allapot == "nyitott")) or 0,
        "feldolgozatlan_javitas": db.scalar(
            select(func.count(Correction.id)).where(Correction.feldolgozas_allapot == "uj")) or 0,
        "szabalyjavaslat": db.scalar(
            select(func.count(PlaybookRule.id)).where(PlaybookRule.allapot.in_(("pending", "draft")))) or 0,
        "visszacsatolas_fuggo": db.scalar(select(func.count(Outbox.id)).where(
            Outbox.esemeny_tipus.like("lara_visszacsatolas:%"), Outbox.allapot == "pending")) or 0,
    }


def allapot(db: Session) -> dict:
    """Forrásonkénti állapot + a várakozó munka."""
    from app.admin_agent.settings_service import leallitva

    naplok = _naplo_sorok(db)
    kapcs = _kapcsolok(db)
    var = varakozo_munka(db)
    le = leallitva(db)
    jovahagyasra = {"observer": var["tudas_jelolt"], "self_check": var["nyitott_kerdes"],
                    "nightly_distill": var["szabalyjavaslat"]}
    sorok = []
    for kulcs, cim in FORRASOK.items():
        n = naplok.get(kulcs, {})
        be, ok = kapcs.get(kulcs, (True, None))
        hiany = _jogosultsag_hiany(kulcs)
        siker = n.get("utolso_siker")
        hiba = n.get("utolso_hiba") or {}
        if le:
            st, indok = "kikapcsolva", "Lara le van állítva (vészleállítás)."
        elif not be:
            st, indok = "kikapcsolva", ok
        elif hiany:
            st, indok = "nincs_jogosultsag", hiany
        elif hiba and (not siker or hiba.get("ido", "") > siker):
            st, indok = "feldolgozasi_hiba", hiba.get("hiba")
        elif jovahagyasra.get(kulcs):
            st, indok = "jovahagyasra_var", f"{jovahagyasra[kulcs]} tétel emberi döntésre vár."
        elif not siker and not n:
            st, indok = "nincs_adat", "Még nem futott (vagy a futásnapló a 2026-09-es bővítés óta üres)."
        else:
            st, indok = "rendben", None
        sorok.append({
            "kulcs": kulcs, "cim": cim, "allapot": st, "indok": indok,
            "utolso_siker": siker, "utolso_hiba": hiba or None,
            "utolso_kihagyas": n.get("utolso_kihagyas"), "futas_db": n.get("futas_db", 0),
            "hiba_db": n.get("hiba_db", 0), "utolso_eredmeny": n.get("utolso_eredmeny") or {},
        })
    return {"leallitva": le, "forrasok": sorok, "varakozo": var}


def nyomvonal(db: Session, memory_id: int) -> dict | None:
    """Egy tudás-darab teljes útja a beérkezéstől a felhasználásig."""
    from app.models.admin_agent import ActionTrace, PlaybookRule, SourceEvent
    from app.models.employee import Employee

    m = db.get(MemoryChunk, memory_id)
    if m is None:
        return None
    forras = m.forras or ""
    fejek = forras.split(":", 1)
    se = None
    if len(fejek) == 2 and fejek[0] in ("megfigyeles", "visszajatszas", "levelezes", "asszisztens"):
        se = db.scalar(
            select(SourceEvent).where(SourceEvent.forras == fejek[0], SourceEvent.forras_azonosito == fejek[1])
            .order_by(SourceEvent.id.desc())
        )
    jovahagyo = db.get(Employee, m.jovahagyta_id) if m.jovahagyta_id else None
    nyomok = db.scalars(
        select(ActionTrace).where(ActionTrace.eroforras == f"memory:{m.id}").order_by(ActionTrace.id)
    ).all()
    szabalyok = [
        {"id": r.id, "cim": r.cim, "allapot": r.allapot}
        for r in db.scalars(select(PlaybookRule)).all()
        if m.forras in ((r.forras_esetek or {}).get("peldak") or [])
        or m.id in ((r.forras_esetek or {}).get("tanitas") or [])
        or (r.feltetelek or {}).get("tudas_id") == m.id
    ][:20]
    lepesek = [{"lepes": "beérkezés", "ido": m.created_at.isoformat() if m.created_at else None,
                "leiras": f"forrás: {forras or '—'}"}]
    if se is not None:
        lepesek.append({"lepes": "forrásesemény", "ido": se.created_at.isoformat() if se.created_at else None,
                        "leiras": f"{se.forras} #{se.forras_azonosito} ({se.allapot})"})
    for t in nyomok:
        lepesek.append({"lepes": t.muvelet, "ido": t.tortent_at.isoformat() if t.tortent_at else None,
                        "leiras": t.eredmeny})
    if m.jovahagyva_at:
        lepesek.append({"lepes": "jóváhagyás", "ido": m.jovahagyva_at.isoformat(),
                        "leiras": jovahagyo.full_name if jovahagyo else "—"})
    if m.felhasznalhato_at:
        lepesek.append({"lepes": "használhatóvá vált", "ido": m.felhasznalhato_at.isoformat(), "leiras": None})
    if m.utolso_felhasznalas_at:
        lepesek.append({"lepes": "legutóbbi felhasználás", "ido": m.utolso_felhasznalas_at.isoformat(),
                        "leiras": f"összesen {m.felhasznalva_db}×"})
    lepesek.sort(key=lambda x: x["ido"] or "")
    kesleltetes = None
    if m.felhasznalhato_at and m.created_at:
        kesleltetes = round((m.felhasznalhato_at - m.created_at).total_seconds() / 60, 1)
    return {
        "id": m.id, "hatokor": m.hatokor, "fajta": m.tudas_fajta, "bizonyitek_szint": m.bizonyitek_szint,
        "minosites": m.minosites, "ervenyes": m.ervenyes, "visszavont": m.visszavont, "verzio": m.verzio,
        "ugy_kulcs": m.ugy_kulcs, "felhasznalva_db": m.felhasznalva_db,
        "hasznalhato_lett_perc": kesleltetes, "szabalyok": szabalyok, "lepesek": lepesek,
    }
