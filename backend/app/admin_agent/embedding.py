"""Lara — jelentés szerinti (szemantikus) keresés a tudásban.

Eddig egy korábbi eset CSAK akkor került elő, ha a partner neve (normalizálva)
egyezett. Egy hasonló eset egy másik partnernél — vagy ugyanaz a cég kicsit más
néven („Kovács Kft." / „Kovács és Társa Kft.") — nem jött elő. Ez a modul
minden tudás-darabhoz beágyazó vektort (embedding) számol, és a lekérdezéshez
a JELENTÉSBEN legközelebbi, jóváhagyott darabokat adja vissza.

* A vektort a már beállított Gemini-kulccsal számoljuk (`GEMINI_EMBEDDING_MODEL`,
  alap „gemini-embedding-001", 768 dimenzió) — külön szolgáltatás nem kell.
* pgvector NEM kell: a vektor a meglévő `aa_memory_chunks.embedding` (JSONB)
  oszlopba kerül, a hasonlóságot Pythonban számoljuk (koszinusz, normalizált
  vektorokon). Néhány ezer darabig ez gyors; ha egyszer több lesz, a pgvector
  bekapcsolása csak a keresés helyét cseréli.
* Fail-closed: kulcs nélkül vagy modellhibánál a keresés csendben a régi,
  partnernév-alapú útra marad — soha nem talál ki egyezést.
* Csak JÓVÁHAGYOTT, érvényes, nem visszavont darab jöhet elő (mint eddig).
* Kikapcsolható: `aa_settings.limitek.szemantikus_kereses` (alap: be).
"""

from __future__ import annotations

import math
import time
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin_agent.settings_service import get_settings
from app.core.config import settings
from app.models.admin_agent import MemoryChunk

DIM = 768
#: Egy hívásban ennyi szöveget ágyazunk be.
KOTEG = 50
#: Egy darab beágyazott szövegének felső határa (karakter).
MAX_HOSSZ = 6000
#: Ennél kisebb hasonlóságú találat nem jön elő (0..1, koszinusz).
MIN_HASONLOSAG = 0.62
#: Ennyi legfrissebb jóváhagyott darabon keresünk.
KERESESI_ABLAK = 4000

#: Tesztben beállítható hamis beágyazó: (szövegek, feladat) -> vektorok.
_TESZT: Callable[[list[str], str], list[list[float]]] | None = None


class BeagyazasHiba(Exception):
    pass


def teszt_beagyazo(fn: Callable[[list[str], str], list[list[float]]] | None) -> None:
    global _TESZT
    _TESZT = fn


def modell() -> str:
    return getattr(settings, "gemini_embedding_model", None) or "gemini-embedding-001"


def elerheto() -> bool:
    return _TESZT is not None or bool(getattr(settings, "gemini_api_key", None))


def bekapcsolva(db: Session) -> bool:
    return (get_settings(db).limitek or {}).get("szemantikus_kereses") is not False


def _normal(v: list[float]) -> list[float]:
    h = math.sqrt(sum(x * x for x in v)) or 1.0
    return [round(x / h, 5) for x in v]


def beagyaz(szovegek: list[str], feladat: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
    """Normalizált vektorok. Hiba esetén `BeagyazasHiba` (a hívó fail-closed)."""
    if not szovegek:
        return []
    tiszta = [(s or " ")[:MAX_HOSSZ] for s in szovegek]
    if _TESZT is None and not getattr(settings, "gemini_api_key", None):
        raise BeagyazasHiba("Nincs beállítva a Gemini-kulcs.")
    try:
        if _TESZT is not None:
            vektorok = [list(v) for v in _TESZT(tiszta, feladat)]
            return _ellenoriz(vektorok, len(tiszta))
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.gemini_api_key)
        resp = client.models.embed_content(
            model=modell(),
            contents=tiszta,
            config=types.EmbedContentConfig(task_type=feladat, output_dimensionality=DIM),
        )
        vektorok = [list(e.values or []) for e in (resp.embeddings or [])]
    except BeagyazasHiba:
        raise
    except Exception as e:  # noqa: BLE001 — bármilyen modellhiba: fail-closed
        raise BeagyazasHiba(str(e)[:300]) from e
    return _ellenoriz(vektorok, len(tiszta))


def _ellenoriz(vektorok: list[list[float]], n: int) -> list[list[float]]:
    if len(vektorok) != n or any(not v for v in vektorok):
        raise BeagyazasHiba("A beágyazó hiányos választ adott.")
    return [_normal(v) for v in vektorok]


def feltolt(db: Session, *, max_db: int = 400, max_mp: float = 60.0) -> dict:
    """A még vektor nélküli (vagy régebbi modellel számolt) darabok beágyazása.
    Idempotens; a hívó commitál. A jelölteket is beágyazzuk (a jóváhagyás után
    azonnal kereshetők legyenek), a visszavontakat nem."""
    if not elerheto():
        return {"elerheto": False, "beagyazva": 0, "hiba": None}
    m_nev = modell()
    hianyzo = db.scalars(
        select(MemoryChunk)
        .where(
            MemoryChunk.visszavont.is_(False),
            (MemoryChunk.embedding.is_(None)) | (MemoryChunk.embedding_modell.is_distinct_from(m_nev)),
        )
        .order_by(MemoryChunk.ervenyes.desc(), MemoryChunk.id.desc())
        .limit(max_db)
    ).all()
    kezd = time.monotonic()
    kesz = 0
    hiba = None
    for i in range(0, len(hianyzo), KOTEG):
        if time.monotonic() - kezd > max_mp:
            break
        resz = hianyzo[i : i + KOTEG]
        try:
            vektorok = beagyaz([m.tartalom for m in resz])
        except BeagyazasHiba as e:
            hiba = str(e)
            break
        for m, v in zip(resz, vektorok):
            m.embedding = v
            m.embedding_modell = m_nev
            m.embedding_dim = len(v)
            kesz += 1
    db.flush()
    return {"elerheto": True, "beagyazva": kesz, "hiba": hiba}


def lefedettseg(db: Session) -> dict:
    ossz = db.scalars(select(MemoryChunk.id).where(MemoryChunk.visszavont.is_(False))).all()
    kesz = db.scalars(
        select(MemoryChunk.id).where(
            MemoryChunk.visszavont.is_(False),
            MemoryChunk.embedding.is_not(None),
            MemoryChunk.embedding_modell == modell(),
        )
    ).all()
    return {"osszes": len(ossz), "beagyazva": len(kesz), "modell": modell(), "elerheto": elerheto()}


def _koszinusz(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def hasonlo(
    db: Session,
    szoveg: str,
    *,
    hatokorok: tuple[str, ...] | None = None,
    limit: int = 3,
    kiveve: set[int] | None = None,
    min_hasonlosag: float | None = None,
) -> list[dict]:
    """A jelentésben legközelebbi JÓVÁHAGYOTT tudás-darabok. Hiba / kikapcsolt
    állapot esetén üres lista (a hívó a régi úton marad)."""
    if not szoveg.strip() or not elerheto() or not bekapcsolva(db):
        return []
    kuszob = MIN_HASONLOSAG if min_hasonlosag is None else min_hasonlosag
    felt = [
        MemoryChunk.tanulasi_halmaz == "jovahagyott",
        MemoryChunk.ervenyes.is_(True),
        MemoryChunk.visszavont.is_(False),
        MemoryChunk.embedding.is_not(None),
        MemoryChunk.embedding_modell == modell(),
    ]
    if hatokorok:
        felt.append(MemoryChunk.hatokor.in_(hatokorok))
    jeloltek = db.scalars(select(MemoryChunk).where(*felt).order_by(MemoryChunk.id.desc()).limit(KERESESI_ABLAK)).all()
    if not jeloltek:
        return []
    try:
        q = beagyaz([szoveg], "RETRIEVAL_QUERY")[0]
    except BeagyazasHiba:
        return []
    kiveve = kiveve or set()
    pontok = []
    for m in jeloltek:
        if m.id in kiveve or not isinstance(m.embedding, list) or len(m.embedding) != len(q):
            continue
        s = _koszinusz(q, m.embedding)
        if s >= kuszob:
            # A régi (Notion-korszakbeli) darab kisebb súllyal.
            pontok.append((s * (0.85 if m.regi_korszak else 1.0), s, m))
    pontok.sort(key=lambda x: x[0], reverse=True)
    return [
        {
            "id": m.id,
            "hatokor": m.hatokor,
            "tartalom": m.tartalom,
            "hasonlosag": round(s, 3),
            "regi": bool(m.regi_korszak),
        }
        for _, s, m in pontok[:limit]
    ]
