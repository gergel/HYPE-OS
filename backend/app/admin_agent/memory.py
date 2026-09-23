"""Admin-Ágens — visszakeresés (retrieval).

Feladatonként legfeljebb néhány (5–10) RELEVÁNS, ÉRVÉNYES, JÓVÁHAGYOTT szabályt
és példát ad vissza. A pgvector OPCIONÁLIS: elérhetőségét futásidőben nézzük, és
mivel az embedding itt JSONB (nem natív vektor), a keresés determinista
pontos/szöveges fallbackre épül (master prompt 11.). A holdout SOHA nem kerül a
visszakeresésbe (csak `tanulasi_halmaz="jovahagyott"`). Egyszervezetes rendszer,
így nincs kereszt-szervezeti szivárgás; a hozzáférést a hívó RBAC-ja adja.
"""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.admin_agent.enums import RuleState
from app.models.admin_agent import MemoryChunk, PlaybookRule

MAX_TALALAT = 8
#: A régi (a tanulás kezdete előtti / Notion-korszakbeli) példák jelölése a
#: modell felé: kisebb súllyal veendő, az újabb gyakorlat felülírja.
REGI_ELOTAG = "[RÉGI, a HYPE OS előtti (Notion-korszakbeli) eset — kisebb súllyal] "


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


def kapcsolodo_tudas(db: Session, *, hatokor: str, partner: str | None = None) -> dict:
    """A javaslathoz csatolt, TÖMÖR tudás-hivatkozás: az adott feladattípus aktív
    szabályai + a UGYANAZON partnerhez tartozó jóváhagyott korábbi esetek.

    Hasonló eset csak akkor kerül mellé, ha a partner neve egyezik — kevés
    releváns találatnál NEM egészítjük ki irreleváns példákkal (master prompt 11.)."""
    r = retrieve(db, hatokor=hatokor, limit=5)
    peldak: list[dict] = []
    if partner and partner.strip():
        peldak = retrieve(db, hatokor=hatokor, query=partner.strip(), limit=5)["peldak"]
    return {
        "modszer": r["modszer"],
        "szabalyok": [{"id": s["id"], "cim": s["cim"], "tartalom": s["tartalom"]} for s in r["szabalyok"]],
        "hasonlo_esetek": [
            {
                "id": p["id"],
                # A régi korszak példáját a modell is kisebb súllyal kezelje.
                "tartalom": (REGI_ELOTAG if p.get("regi") else "") + p["tartalom"],
                "regi": bool(p.get("regi")),
            }
            for p in peldak
        ],
    }


def retrieve(
    db: Session,
    *,
    hatokor: str,
    query: str | None = None,
    limit: int = MAX_TALALAT,
) -> dict:
    """Aktív szabályok + jóváhagyott példák az adott hatókörhöz. A `query` a
    szöveges szűrésre szolgál (pontos/szöveges fallback). Kevés releváns találat
    esetén NEM egészítjük ki irreleváns elemekkel."""
    limit = max(1, min(limit, 10))

    szabalyok = db.scalars(
        select(PlaybookRule)
        .where(PlaybookRule.hatokor == hatokor, PlaybookRule.allapot == RuleState.ACTIVE.value)
        .order_by(PlaybookRule.prioritas.desc(), PlaybookRule.id.desc())
        .limit(limit)
    ).all()

    felt = [
        MemoryChunk.hatokor == hatokor,
        MemoryChunk.tanulasi_halmaz == "jovahagyott",
        MemoryChunk.ervenyes.is_(True),
        MemoryChunk.visszavont.is_(False),
    ]
    if query and query.strip():
        felt.append(MemoryChunk.tartalom.ilike(f"%{query.strip()}%"))
    # A tanulás kezdete óta (a HYPE OS felületén) keletkezett példák ELŐBB;
    # a régi (Notion-korszakbeli) jóváhagyott példa csak utánuk, ha van hely.
    peldak = db.scalars(
        select(MemoryChunk)
        .where(*felt)
        .order_by(MemoryChunk.regi_korszak.asc(), MemoryChunk.id.desc())
        .limit(limit)
    ).all()

    return {
        "modszer": "pgvector" if pgvector_elerheto_e() else "pontos_szoveges_fallback",
        "szabalyok": [
            {"id": r.id, "cim": r.cim, "tartalom": r.tartalom, "prioritas": r.prioritas, "verzio": r.verzio}
            for r in szabalyok
        ],
        "peldak": [
            {"id": m.id, "tartalom": m.tartalom, "forras": m.forras, "regi": bool(m.regi_korszak)} for m in peldak
        ],
    }
