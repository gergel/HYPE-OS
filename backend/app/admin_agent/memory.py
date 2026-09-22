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
    peldak = db.scalars(
        select(MemoryChunk).where(*felt).order_by(MemoryChunk.id.desc()).limit(limit)
    ).all()

    return {
        "modszer": "pgvector" if pgvector_elerheto_e() else "pontos_szoveges_fallback",
        "szabalyok": [
            {"id": r.id, "cim": r.cim, "tartalom": r.tartalom, "prioritas": r.prioritas, "verzio": r.verzio}
            for r in szabalyok
        ],
        "peldak": [{"id": m.id, "tartalom": m.tartalom, "forras": m.forras} for m in peldak],
    }
