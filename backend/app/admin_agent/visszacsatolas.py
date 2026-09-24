"""Gyors visszacsatolás (2026-09, E fázis) — TARTÓS, idempotens sor.

Eddig egy emberi javítás vagy jóváhagyott magyarázat csak a következő
ütemezett futásnál (félóra–éjszaka) vált a döntésben használható tudássá.
Ez a modul a meglévő (eddig használatlan) `aa_outbox` táblára épít:

1. az esemény (javítás, jóváhagyott tudás, tanítás, kérdésre adott válasz)
   UGYANABBAN a tranzakcióban kerül a sorba, mint maga a változás;
2. a feldolgozó (Celery, percenként) idempotensen dolgozza fel:
   - javításnál a háttér-tanulót (distill) futtatja;
   - tudásnál a beágyazást (jelentés szerinti kereshetőség) és a
     megerősítést;
3. hibánál visszalépő (backoff) újrapróba jön; `MAX_PROBA` után karantén.
   Minden sor megmarad naplónak (állapot, hiba, feldolgozás ideje).

KAPCSOLÓK (mindkettő alapból KI — `aa_settings.limitek`):

- `gyors_visszacsatolas`: a sor. Kikapcsolva semmi sem kerül bele, és a
  meglévő ütemezett folyamatok változatlanul viszik a tanulást (ezek maradnak
  a helyreállítási út bekapcsolva is).
- `auto_szamla_elemzes`: az új beérkező számlák automatikus L0 elemzése. CSAK
  JAVASLAT: nem hoz létre jóváhagyást, nem kerül végrehajtási sorba, nem küld
  értesítést, nem ír üzleti rekordot, és nem emel bizalmi szintet
  (`pipeline_szamla.arnyek_elemzes(csak_javaslat=True)`). Csak a bekapcsolás
  UTÁN érkezett számlákat nézi; futásonként legfeljebb `AUTO_ELEMZES_MAX`-ot.

Vészleállításnál semmi sem fut. A sor nem változtat jogosultságot, policyt,
bizalmi szintet vagy üzleti kapcsolót.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import String, cast, select
from sqlalchemy.orm import Session

from app.models.admin_agent import Outbox

logger = logging.getLogger(__name__)

TIPUSOK = ("korrekcio", "tudas", "tanitas", "kerdes_valasz")
ELOTAG = "lara_visszacsatolas:"
MAX_PROBA = 5
KARANTEN = "karanten"
AUTO_ELEMZES_MAX = 5


def _most() -> datetime:
    return datetime.now(timezone.utc)


def _limitek(db: Session) -> dict:
    from app.admin_agent.settings_service import get_settings

    return get_settings(db).limitek or {}


def bekapcsolva(db: Session) -> bool:
    return _limitek(db).get("gyors_visszacsatolas") is True


def auto_elemzes_be(db: Session) -> bool:
    return _limitek(db).get("auto_szamla_elemzes") is True


def sorba(db: Session, tipus: str, azonosito: int | str) -> Outbox | None:
    """Esemény a sorba — a hívó tranzakciójában (a hívó commitál). Idempotens:
    ugyanarra a (típus, azonosító) párra egyszerre egy függő sor van."""
    if tipus not in TIPUSOK or not bekapcsolva(db):
        return None
    kulcs = f"{tipus}:{azonosito}"
    meglevo = db.scalar(
        select(Outbox).where(
            Outbox.esemeny_tipus == ELOTAG + tipus, Outbox.kulso_azonosito == kulcs, Outbox.allapot == "pending",
        )
    )
    if meglevo is not None:
        return meglevo
    o = Outbox(esemeny_tipus=ELOTAG + tipus, payload={"tipus": tipus, "azonosito": azonosito}, allapot="pending",
               probalkozasok=0, kulso_azonosito=kulcs)
    db.add(o)
    db.flush()
    return o


def _vissza(probalkozas: int) -> timedelta:
    """Visszalépő várakozás: 1, 2, 4, 8… perc (legfeljebb 60)."""
    return timedelta(minutes=min(60, 2 ** max(0, probalkozas - 1)))


def _kezel(db: Session, sorok: list[Outbox]) -> dict:
    """A kötegben szereplő események tényleges hatása — egyszer futtatva a
    kötegre (a distill és a megerősítés maga is idempotens)."""
    tipusok = {(o.payload or {}).get("tipus") for o in sorok}
    ki: dict = {}
    if "korrekcio" in tipusok:
        from app.admin_agent.learning import distill

        r = distill(db, trigger="visszacsatolas")
        ki["distill"] = {"korrekciok": r.feldolgozott_korrekciok, "uj_pelda": r.uj_pelda_jeloltek}
    if tipusok & {"tudas", "tanitas", "kerdes_valasz"}:
        from app.admin_agent import embedding

        if embedding.bekapcsolva(db):
            ki["beagyazas"] = embedding.feltolt(db, max_db=50, max_mp=20.0)
        from app.admin_agent.megerosites import futtat as megerosites

        m = megerosites(db, trigger="megerosites:visszacsatolas")
        ki["megerosites"] = {"auto_jovahagyott": m.get("auto_jovahagyott")}
    return ki


def feldolgoz(db: Session, *, max_db: int = 50) -> dict:
    """A függő események feldolgozása. Hibánál a köteg sorai visszalépő
    újrapróbát kapnak; a sor maga a napló. A hívó commitál."""
    from app.admin_agent.settings_service import leallitva

    if leallitva(db):
        return {"leallitva": True}
    most = _most()
    sorok = db.scalars(
        select(Outbox).where(
            Outbox.esemeny_tipus.like(ELOTAG + "%"),
            Outbox.allapot == "pending",
            (Outbox.kovetkezo_probalkozas_at.is_(None)) | (Outbox.kovetkezo_probalkozas_at <= most),
        ).order_by(Outbox.id).limit(max_db).with_for_update(skip_locked=True)
    ).all()
    if not sorok:
        return {"feldolgozva": 0}
    try:
        with db.begin_nested():
            hatas = _kezel(db, sorok)
    except Exception as exc:  # noqa: BLE001 — újrapróba / karantén, a hiba a sorban
        logger.warning("Lara gyors visszacsatolás hibára futott: %s", exc)
        for o in sorok:
            o.probalkozasok += 1
            o.hiba = f"{type(exc).__name__}: {str(exc)[:500]}"
            if o.probalkozasok >= MAX_PROBA:
                o.allapot = KARANTEN
            else:
                o.kovetkezo_probalkozas_at = most + _vissza(o.probalkozasok)
        db.flush()
        return {"feldolgozva": 0, "hiba": len(sorok)}
    for o in sorok:
        o.probalkozasok += 1
        o.allapot = "done"
        o.hiba = None
        o.feldolgozva_at = _most()
    db.flush()
    return {"feldolgozva": len(sorok), **hatas}


def allapot(db: Session) -> dict:
    """A Tanulási folyamat nézethez: a sor állapota."""
    from sqlalchemy import func

    szam = dict(
        db.execute(
            select(Outbox.allapot, func.count(Outbox.id))
            .where(Outbox.esemeny_tipus.like(ELOTAG + "%")).group_by(Outbox.allapot)
        ).all()
    )
    utolso = db.scalar(
        select(Outbox).where(Outbox.esemeny_tipus.like(ELOTAG + "%"), Outbox.allapot == "done")
        .order_by(Outbox.feldolgozva_at.desc().nulls_last())
    )
    hibas = db.scalar(
        select(Outbox).where(Outbox.esemeny_tipus.like(ELOTAG + "%"), Outbox.hiba.is_not(None))
        .order_by(Outbox.updated_at.desc())
    )
    return {
        "bekapcsolva": bekapcsolva(db),
        "auto_szamla_elemzes": auto_elemzes_be(db),
        "fuggo": szam.get("pending", 0),
        "kesz": szam.get("done", 0),
        "karanten": szam.get(KARANTEN, 0),
        "utolso_feldolgozas": utolso.feldolgozva_at.isoformat() if utolso and utolso.feldolgozva_at else None,
        "utolso_hiba": ({"hiba": hibas.hiba, "ido": hibas.updated_at.isoformat() if hibas.updated_at else None,
                         "allapot": hibas.allapot} if hibas else None),
    }


# ── Automatikus L0 számla-elemzés (csak javaslat) ────────────────────────────


def auto_szamla_elemzes(db: Session, *, max_db: int = AUTO_ELEMZES_MAX) -> dict:
    """A bekapcsolás UTÁN érkezett, kiolvasott, még nem elemzett számlák
    CSAK JAVASLATOS elemzése. A hívó commitál."""
    from app.admin_agent.pipeline_szamla import FORRAS, arnyek_elemzes
    from app.admin_agent.settings_service import leallitva
    from app.models.admin_agent import SourceEvent
    from app.models.bejovo_szamla import ALLAPOT_ELLENORZENDO, ALLAPOT_PONTOSITAS, BejovoSzamla

    if leallitva(db) or not auto_elemzes_be(db):
        return {"fut": False}
    tol_s = _limitek(db).get("auto_szamla_elemzes_tol")
    try:
        tol = datetime.fromisoformat(str(tol_s)) if tol_s else None
    except ValueError:
        tol = None
    if tol is None:
        return {"fut": False, "ok": "nincs bekapcsolási időpont"}
    elemzett = select(SourceEvent.forras_azonosito).where(SourceEvent.forras == FORRAS)
    jeloltek = db.scalars(
        select(BejovoSzamla).where(
            BejovoSzamla.allapot.in_((ALLAPOT_ELLENORZENDO, ALLAPOT_PONTOSITAS)),
            BejovoSzamla.created_at >= tol,
            cast(BejovoSzamla.id, String).notin_(elemzett),
        ).order_by(BejovoSzamla.id).limit(max_db)
    ).all()
    kesz = hiba = 0
    for b in jeloltek:
        try:
            with db.begin_nested():
                arnyek_elemzes(db, b, trigger="auto_elemzes", csak_javaslat=True)
            kesz += 1
        except Exception:  # noqa: BLE001 — egy számla hibája nem állítja meg a többit
            logger.exception("Lara auto számla-elemzés hiba (bejövő #%s).", b.id)
            hiba += 1
    db.flush()
    return {"fut": True, "elemzett": kesz, "hiba": hiba}
