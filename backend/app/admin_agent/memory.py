"""Lara — visszakeresés (retrieval).

Feladatonként legfeljebb néhány (5–10) RELEVÁNS, ÉRVÉNYES, JÓVÁHAGYOTT szabályt
és példát ad vissza. A pgvector OPCIONÁLIS: elérhetőségét futásidőben nézzük, és
mivel az embedding itt JSONB (nem natív vektor), a keresés determinista
pontos/szöveges fallbackre épül (master prompt 11.). A holdout SOHA nem kerül a
visszakeresésbe (csak `tanulasi_halmaz="jovahagyott"`). Egyszervezetes rendszer,
így nincs kereszt-szervezeti szivárgás; a hozzáférést a hívó RBAC-ja adja.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from functools import lru_cache

from sqlalchemy import and_, func, or_, select, text, update
from sqlalchemy.orm import Session

from app.admin_agent.enums import RuleState
from app.models.admin_agent import MemoryChunk, PlaybookRule

MAX_TALALAT = 8
#: A partner-szűrésnél ennyi legutóbbi jóváhagyott példát nézünk végig.
_PELDA_ABLAK = 2000
#: Cégforma-/vállalkozói utótagok: a „Zseni Boglárka EV" és a „Zseni Boglárka"
#: ugyanaz a partner.
_CEGFORMA = re.compile(r"\b(kft|bt|zrt|nyrt|kkt|ev|e v|egyeni vallalkozo|egyeni vallalkozas|ltd|gmbh|inc)\b")


def partner_kulcs(nev: str | None) -> str:
    """Összevetésre normalizált partnernév: kisbetű, ékezet nélkül, cégforma és
    írásjelek nélkül (pl. „Turcsik Márk EV" → "turcsik mark")."""
    if not nev:
        return ""
    s = unicodedata.normalize("NFKD", nev.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = _CEGFORMA.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def _partner_egyezik(kulcs: str, szoveg: str | None) -> bool:
    return len(kulcs) >= 3 and kulcs in partner_kulcs(szoveg)
#: A régi (a tanulás kezdete előtti / Notion-korszakbeli) példák jelölése a
#: modell felé: kisebb súllyal veendő, az újabb gyakorlat felülírja.
REGI_ELOTAG = "[RÉGI, a HYPE OS előtti (Notion-korszakbeli) eset — kisebb súllyal] "
#: A HIPOTÉZIS (pl. a modell feltételezett indoka) sosem kerül tényként a
#: modell elé - ezzel a jelöléssel látja (lásd `bizonyitek_szint`).
HIPOTEZIS_ELOTAG = "[HIPOTÉZIS — forrással nem igazolt feltételezés, nem tény] "


def ervenyes_most():
    """SQL-feltétel: a tudás érvényességi ablaka (`ervenyes_tol`/`ervenyes_ig`)
    most nyitva van. A NULL mindkét oldalon nyitott végű."""
    most = datetime.now(timezone.utc)
    return and_(
        or_(MemoryChunk.ervenyes_tol.is_(None), MemoryChunk.ervenyes_tol <= most),
        or_(MemoryChunk.ervenyes_ig.is_(None), MemoryChunk.ervenyes_ig > most),
    )


def hasznalhato():
    """SQL-feltételek: a DÖNTÉSBEN használható tudás - jóváhagyott tanító
    halmaz (a vizsgakészlet `holdout`, soha), érvényes, nem visszavont, és az
    érvényességi ablaka nyitva."""
    return (
        MemoryChunk.tanulasi_halmaz == "jovahagyott",
        MemoryChunk.ervenyes.is_(True),
        MemoryChunk.visszavont.is_(False),
        ervenyes_most(),
    )


def jelolt_szoveg(m: MemoryChunk) -> str:
    """A tudás szövege a modell felé, a súlyát jelző előtagokkal."""
    elotag = ""
    if m.bizonyitek_szint == "hipotezis":
        elotag += HIPOTEZIS_ELOTAG
    if m.regi_korszak:
        elotag += REGI_ELOTAG
    return elotag + m.tartalom


def felhasznalas_rogzit(db: Session, ids) -> None:
    """A modell / beszélgetés elé került tudás felhasználásának rögzítése (a
    Tanulási folyamat nézet és a minőségmérés látja). Egy UPDATE-tel."""
    idk = sorted({int(i) for i in ids if i})
    if not idk:
        return
    db.execute(
        update(MemoryChunk)
        .where(MemoryChunk.id.in_(idk))
        .values(felhasznalva_db=MemoryChunk.felhasznalva_db + 1, utolso_felhasznalas_at=func.now())
        .execution_options(synchronize_session=False)
    )


@lru_cache(maxsize=1)
def pgvector_elerheto_e(_cache_key: int = 0) -> bool:
    """A pgvector extension telepítve van-e. Cache-elve; a fallback dokumentált."""
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        return bool(db.execute(text("SELECT 1 FROM pg_extension WHERE extname='vector'")).first())
    except Exception:
        return False
    finally:
        db.close()


#: A jelentés szerinti keresésnél a feladattípushoz ezek a tudás-körök is
#: számítanak (pl. egy számlánál a projektkód-kommentek és a fizetési szokás).
ROKON_HATOKOROK: dict[str, tuple[str, ...]] = {
    "szamla": ("szamla", "projektkod", "kintlevoseg", "email", "rendszer"),
    "tig": ("tig", "szerzodes", "projektkod", "rendszer"),
    "szerzodes": ("szerzodes", "tig", "projektkod", "arajanlat", "rendszer"),
    "email": ("email", "szamla", "kintlevoseg", "projektkod", "rendszer"),
}
_HATOKOR_SZO = {"szamla": "számla", "tig": "teljesítésigazolás (TIG)", "szerzodes": "szerződés", "email": "e-mail"}


def projekt_eletut(db: Session, project_code_id: int | None) -> str | None:
    """A projektkód életútja a TELJES rendszerben (diszpó, forgatás, utómunka,
    portál, papírok, pénzügy…) — a rendszer-figyelés ténye (lásd
    admin_agent/rendszer.py). Csak olvasott tudás; None, ha még nincs."""
    if not project_code_id:
        return None
    m = db.scalar(
        select(MemoryChunk).where(
            MemoryChunk.forras == f"rendszer:projektkod:{project_code_id}",
            MemoryChunk.ervenyes.is_(True),
            MemoryChunk.visszavont.is_(False),
        )
    )
    return m.tartalom if m is not None else None


def kivetelek(db: Session, *, partner: str | None = None, szoveg: str | None = None, limit: int = 4) -> list[dict]:
    """Érvényes KIVÉTEL-tudás (a tanításból): a partnerhez kötött előbb, majd a
    szövegben szóba kerülők. A kivétel külön rovat, hogy a modell ne
    általános szabályként olvassa."""
    sorok = db.scalars(
        select(MemoryChunk)
        .where(MemoryChunk.tudas_fajta == "kivetel", *hasznalhato())
        .order_by(MemoryChunk.id.desc())
        .limit(500)
    ).all()
    p_kulcs = partner_kulcs(partner)
    tokenek = _tokenek(szoveg)
    jell = _jellegzetes(szoveg)
    pont: list[tuple[int, MemoryChunk]] = []
    for m in sorok:
        hp = partner_kulcs(((m.hatokor_reszletek or {}).get("partner")) or "")
        if p_kulcs and hp and (hp == p_kulcs or _partner_egyezik(p_kulcs, hp)):
            pont.append((100, m))
        elif tokenek:
            t = egyezes(tokenek, jell, _tokenek(m.tartalom) | _tokenek(hp))
            if t:
                pont.append((t, m))
    pont.sort(key=lambda x: (-x[0], -x[1].id))
    return [{"id": m.id, "tartalom": jelolt_szoveg(m), "hatokor": m.hatokor} for _, m in pont[:limit]]


def rendszerismeret(db: Session, *, szoveg: str | None = None, project_code_id: int | None = None,
                    limit: int = 4, engedelyezett=None) -> list[dict]:
    """RENDSZERISMERET külön rovatban: a jóváhagyott kézikönyv-szakaszok (lásd
    admin_agent/kezikonyv.py) és - ha van - a projektkód életútja. A
    technikai leírás és a jóváhagyott üzleti eljárás jelölve különül el."""
    ki: list[dict] = []
    eletut = projekt_eletut(db, project_code_id)
    if eletut:
        ki.append({"id": None, "fajta": "projektkod_eletut", "tartalom": eletut})
    if szoveg and szoveg.strip():
        from app.admin_agent.kezikonyv import kereses

        ki += kereses(db, szoveg, limit=limit, engedelyezett=engedelyezett)
    return ki


def kapcsolodo_tudas(
    db: Session, *, hatokor: str, partner: str | None = None, szoveg: str | None = None,
    project_code_id: int | None = None,
) -> dict:
    """A javaslathoz csatolt, TÖMÖR tudás-hivatkozás, KÜLÖN rovatokban:

    - `szabalyok`: az adott feladattípus ÉLES szabályai;
    - `kivetelek`: a tanított kivételek (nem általános szabályok!);
    - `rendszerismeret`: jóváhagyott kézikönyv-szakasz + projektkód-életút;
    - `hasonlo_esetek` / `hasonlo_jelentes`: jóváhagyott korábbi esetek
      (partner-egyezés, ill. jelentés szerinti hasonlóság).

    A partner-egyezéses eset csak akkor kerül mellé, ha a partner neve egyezik;
    a jelentés szerinti találat csak egy küszöb fölött — kevés releváns
    találatnál NEM egészítjük ki irreleváns példákkal (master prompt 11.).
    A hipotézis jelölve kerül a modell elé; a felhasználás rögzül."""
    r = retrieve(db, hatokor=hatokor, partner=partner, limit=5)
    peldak: list[dict] = []
    if partner and partner.strip():
        peldak = retrieve(db, hatokor=hatokor, query=partner.strip(), limit=5)["peldak"]
    kerdes = (szoveg or "").strip() or (
        f"{_HATOKOR_SZO.get(hatokor, hatokor)} — partner: {partner.strip()}" if partner and partner.strip() else ""
    )
    jelentes: list[dict] = []
    if kerdes:
        from app.admin_agent.embedding import hasonlo

        jelentes = hasonlo(
            db, kerdes, hatokorok=ROKON_HATOKOROK.get(hatokor, (hatokor,)), limit=3,
            kiveve={p["id"] for p in peldak},
        )
    kiv = kivetelek(db, partner=partner, szoveg=szoveg)
    rendszer = rendszerismeret(db, szoveg=kerdes if hatokor else szoveg, project_code_id=project_code_id)

    def _elotag(d: dict) -> str:
        return (HIPOTEZIS_ELOTAG if d.get("hipotezis") else "") + (REGI_ELOTAG if d.get("regi") else "")

    felhasznalas_rogzit(
        db,
        [p["id"] for p in peldak] + [j["id"] for j in jelentes] + [k["id"] for k in kiv]
        + [x["id"] for x in rendszer if x.get("id")],
    )
    return {
        # A projektkód életútja a teljes rendszerben (ha ismert) — pl. TIG-nél
        # látszik, hogy az utómunka leadva, a portál kiküldve.
        "projekt_eletut": projekt_eletut(db, project_code_id),
        "modszer": "jelentes_szerinti" if jelentes else r["modszer"],
        "hasonlo_jelentes": [
            {
                "id": j["id"],
                "hatokor": j["hatokor"],
                "hasonlosag": j["hasonlosag"],
                "tartalom": _elotag(j) + j["tartalom"],
                "regi": j["regi"],
            }
            for j in jelentes
        ],
        "szabalyok": [{"id": s["id"], "cim": s["cim"], "tartalom": s["tartalom"]} for s in r["szabalyok"]],
        "kivetelek": kiv,
        "rendszerismeret": [x for x in rendszer if x.get("fajta") != "projektkod_eletut"],
        "hasonlo_esetek": [
            {
                "id": p["id"],
                # A régi korszak példáját a modell is kisebb súllyal kezelje.
                "tartalom": _elotag(p) + p["tartalom"],
                "regi": bool(p.get("regi")),
            }
            for p in peldak
        ],
    }


# ── Szabad szöveges kérdés (beszélgetés) ─────────────────────────────────────

_STOP = frozenset(
    "a az egy es is hogy nem van volt lesz mi mit mint meg mar csak de ha akkor ez azt ezt kell lehet "
    "vagy mert igen nincs kinek kit hol mikor miert hogyan melyik mennyi nala neki velem veled tole "
    "rola ra re ban ben bol bol nak nek val vel ert".split()
)


#: Egyszerű tövesítés: a magyar toldalékok miatt („számlája” / „számlái”)
#: a szavak első TO_HOSSZ betűje számít.
TO_HOSSZ = 5
#: Ennyi betűtől jellegzetes egy szó (pl. partnernév): egyetlen egyezése is elég.
JELLEGZETES = 8


def _szavak(szoveg: str | None) -> list[str]:
    if not szoveg:
        return []
    return [t for t in partner_kulcs(szoveg).split() if len(t) >= 4 and t not in _STOP]


def _tokenek(szoveg: str | None) -> set[str]:
    """A szöveg szó-tövei (a keresés egysége)."""
    return {t[:TO_HOSSZ] for t in _szavak(szoveg)}


def _jellegzetes(szoveg: str | None) -> set[str]:
    return {t[:TO_HOSSZ] for t in _szavak(szoveg) if len(t) >= JELLEGZETES}


def egyezes(kerdes: set[str], jell: set[str], doku: set[str]) -> int:
    """Szó-egyezés pontszáma (0 = nem releváns): legalább két közös tő, vagy
    egy JELLEGZETES (hosszú, pl. partnernév) tő, vagy rövid kérdésnél egy tő."""
    t = len(kerdes & doku)
    if t >= 2 or (t >= 1 and (len(kerdes) <= 2 or kerdes & jell & doku)):
        return t
    return 0


def tudas_csomag(
    db: Session, *, szoveg: str, hatokor: str | None = None, partner: str | None = None,
    project_code_id: int | None = None, limit: int = 6, kizart_ugyek: set[str] | None = None,
    engedelyezett=None,
) -> dict:
    """A beszélgetés / tudáspróba KATEGORIZÁLT tudása egy szabad szöveges
    kérdéshez: szabályok, kivételek, rendszerismeret és hasonló esetek
    KÜLÖN. Csak használható (jóváhagyott, érvényes) tudás; a `kizart_ugyek`
    (vizsgaeset) ügyeiből származó darab SOHA nem kerül bele.

    Az aktuális üzleti adat NEM innen jön: azt a beszélgetés a hiteles
    rendszerrekordokból olvassa (csak olvasó eszközökkel)."""
    tokenek = _tokenek(szoveg)
    jell = _jellegzetes(szoveg)
    p_kulcs = partner_kulcs(partner)
    kizart_ugyek = kizart_ugyek or set()
    # `engedelyezett`: oldal-kulcs -> bool (a kérdező jogosultsága); az
    # oldalhoz kötött kézikönyv-szakasz csak annak megy, aki látja az oldalt.

    # Szabályok: az összes ÉLES szabály közül a partnerhez kötött, majd a
    # szövegben szóba kerülők, végül (ha hatókör adott) az általánosak.
    aktiv = db.scalars(
        select(PlaybookRule).where(PlaybookRule.allapot == RuleState.ACTIVE.value)
        .order_by(PlaybookRule.prioritas.desc(), PlaybookRule.id.desc())
    ).all()
    szab_pont: list[tuple[int, PlaybookRule]] = []
    for r in aktiv:
        rp = (r.feltetelek or {}).get("partner")
        if rp and p_kulcs and (rp == p_kulcs or _partner_egyezik(rp, p_kulcs) or _partner_egyezik(p_kulcs, rp)):
            szab_pont.append((100, r))
            continue
        t = egyezes(tokenek, jell, _tokenek(r.cim) | _tokenek(r.tartalom) | _tokenek(rp))
        if t:
            szab_pont.append((t, r))
        elif hatokor and r.hatokor == hatokor and not rp:
            szab_pont.append((0, r))
    szab_pont.sort(key=lambda x: (-x[0], -x[1].prioritas, -x[1].id))
    szabalyok = [
        {"id": r.id, "cim": r.cim, "tartalom": r.tartalom, "hatokor": r.hatokor, "verzio": r.verzio}
        for _, r in szab_pont[:limit]
    ]

    # Hasonló esetek: szó-egyezés a jóváhagyott tudásban (+ jelentés szerinti).
    felt = [*hasznalhato(), MemoryChunk.hatokor != "kezikonyv"]
    felt.append(or_(MemoryChunk.tudas_fajta.is_(None), MemoryChunk.tudas_fajta.notin_(("kivetel",))))
    if hatokor:
        felt.append(MemoryChunk.hatokor.in_(ROKON_HATOKOROK.get(hatokor, (hatokor,))))
    ablak = db.scalars(select(MemoryChunk).where(*felt).order_by(MemoryChunk.id.desc()).limit(_PELDA_ABLAK)).all()
    pont: list[tuple[float, MemoryChunk]] = []
    for m in ablak:
        if m.ugy_kulcs and m.ugy_kulcs in kizart_ugyek:
            continue
        t = egyezes(tokenek, jell, _tokenek(m.tartalom))
        if p_kulcs and _partner_egyezik(p_kulcs, m.tartalom):
            t += 5
        if t:
            pont.append((t * (0.85 if m.regi_korszak else 1.0), m))
    pont.sort(key=lambda x: (-x[0], -x[1].id))
    esetek = [
        {"id": m.id, "hatokor": m.hatokor, "fajta": m.tudas_fajta or "eset", "tartalom": jelolt_szoveg(m),
         "forras": m.forras}
        for _, m in pont[:limit]
    ]
    try:
        from app.admin_agent.embedding import hasonlo

        jelentes = hasonlo(db, szoveg, hatokorok=ROKON_HATOKOROK.get(hatokor) if hatokor else None, limit=3,
                           kiveve={e["id"] for e in esetek})
    except Exception:  # noqa: BLE001 — a jelentés szerinti keresés hibája nem állítja meg
        jelentes = []
    kizart_jel = {
        m.id for m in db.scalars(select(MemoryChunk).where(MemoryChunk.id.in_([j["id"] for j in jelentes]))).all()
        if m.ugy_kulcs and m.ugy_kulcs in kizart_ugyek
    } if jelentes and kizart_ugyek else set()
    for j in jelentes:
        if j["id"] in kizart_jel or j["hatokor"] == "kezikonyv":
            continue
        esetek.append({
            "id": j["id"], "hatokor": j["hatokor"], "fajta": j.get("fajta") or "eset",
            "tartalom": (HIPOTEZIS_ELOTAG if j.get("hipotezis") else "") + (REGI_ELOTAG if j["regi"] else "")
            + j["tartalom"], "hasonlosag": j["hasonlosag"],
        })

    kiv = kivetelek(db, partner=partner, szoveg=szoveg)
    rendszer = rendszerismeret(db, szoveg=szoveg, project_code_id=project_code_id, engedelyezett=engedelyezett)
    felhasznalas_rogzit(
        db, [e["id"] for e in esetek] + [k["id"] for k in kiv] + [x["id"] for x in rendszer if x.get("id")]
    )
    return {"szabalyok": szabalyok, "kivetelek": kiv, "rendszerismeret": rendszer, "hasonlo_esetek": esetek}


def retrieve(
    db: Session,
    *,
    hatokor: str,
    query: str | None = None,
    limit: int = MAX_TALALAT,
    partner: str | None = None,
) -> dict:
    """Aktív szabályok + jóváhagyott példák az adott hatókörhöz. A `query` a
    partnerre szűr (normalizált névvel: cégforma, ékezet, kisbetű nem számít).
    A PARTNERHEZ KÖTÖTT szabály (`feltetelek.partner`) csak az adott partnernél
    jön elő, az általános szabály mindig. Kevés releváns találat esetén NEM
    egészítjük ki irreleváns elemekkel."""
    limit = max(1, min(limit, 10))

    aktiv = db.scalars(
        select(PlaybookRule)
        .where(PlaybookRule.hatokor == hatokor, PlaybookRule.allapot == RuleState.ACTIVE.value)
        .order_by(PlaybookRule.prioritas.desc(), PlaybookRule.id.desc())
    ).all()
    p_kulcs = partner_kulcs(partner)
    sajat = [
        r for r in aktiv
        if (r.feltetelek or {}).get("partner") and p_kulcs
        and ((r.feltetelek or {})["partner"] == p_kulcs or _partner_egyezik((r.feltetelek or {})["partner"], p_kulcs))
    ]
    altalanos = [r for r in aktiv if not (r.feltetelek or {}).get("partner")]
    szabalyok = (sajat + altalanos)[:limit]

    felt = [MemoryChunk.hatokor == hatokor, *hasznalhato()]
    # A tanulás kezdete óta (a HYPE OS felületén) keletkezett példák ELŐBB;
    # a régi (Notion-korszakbeli) jóváhagyott példa csak utánuk, ha van hely.
    rendezes = (MemoryChunk.regi_korszak.asc(), MemoryChunk.id.desc())
    if query and query.strip():
        q_kulcs = partner_kulcs(query)
        if len(q_kulcs) >= 3:
            jeloltek = db.scalars(select(MemoryChunk).where(*felt).order_by(*rendezes).limit(_PELDA_ABLAK)).all()
            peldak = [m for m in jeloltek if _partner_egyezik(q_kulcs, m.tartalom)][:limit]
        else:
            felt.append(MemoryChunk.tartalom.ilike(f"%{query.strip()}%"))
            peldak = db.scalars(select(MemoryChunk).where(*felt).order_by(*rendezes).limit(limit)).all()
    else:
        peldak = db.scalars(select(MemoryChunk).where(*felt).order_by(*rendezes).limit(limit)).all()

    return {
        "modszer": "pgvector" if pgvector_elerheto_e() else "pontos_szoveges_fallback",
        "szabalyok": [
            {"id": r.id, "cim": r.cim, "tartalom": r.tartalom, "prioritas": r.prioritas, "verzio": r.verzio}
            for r in szabalyok
        ],
        "peldak": [
            {
                "id": m.id, "tartalom": m.tartalom, "forras": m.forras, "regi": bool(m.regi_korszak),
                "hipotezis": m.bizonyitek_szint == "hipotezis", "fajta": m.tudas_fajta,
            }
            for m in peldak
        ],
    }
