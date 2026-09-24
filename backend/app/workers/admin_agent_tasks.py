"""Lara háttérfeladatok (Celery Beat a megosztott celery_app-on).

* Éjszakai (02:00, szervezeti időzóna) háttér-tanuló (distill) — a korrekciókból
  szabály-/példa-JELÖLTEK; nem aktivál semmit.
* Heti értékelés (eval) — a biztonsági/pénzügyi invariánsok regressziós őre.
* Félóránkénti levelezés-olvasás — a szamla@ postafiók szálaiból tudás-jelölt
  (lásd admin_agent/levelezes.py).
* Félóránkénti AI-asszisztens-figyelés — a lezárt kérés-körökből tudás-jelölt
  (lásd admin_agent/asszisztens.py).
* Óránkénti tapasztalás — a teljes adattörténet ismétlődő tényei, és a Gemini
  állításai, amelyeket Lara az adaton ellenőriz (lásd admin_agent/tapasztalas.py).
* Kétóránkénti önellenőrzés — Lara a rögzített munkán ellenőrzi a tudását, és
  kérdez, ahol nem érti az eltérést (lásd admin_agent/onellenorzes.py).

VÉSZLEÁLLÍTÁS: leállított Laránál EGYIK feladat sem fut (lásd
settings_service.leallitva) - a tudás megmarad, visszakapcsolás után a
következő ütemezett időpontban folytatódik.

A beat itt regisztrálódik a meglévő workerre (lásd calendar_tasks.py), külön
Railway service nélkül (a worker "-B" flaggel embedded beatet is futtat). A
feladatok idempotensek: a distill csak az új korrekciókat dolgozza fel, a
kétszeres tudáskiadás ellen a jelölt→jóváhagyás→aktiválás lánc véd.
"""

from __future__ import annotations

import logging

from celery.schedules import crontab

from app.admin_agent.settings_service import leallitva
from app.core.database import SessionLocal
from app.workers.portal_tasks import celery_app

logger = logging.getLogger(__name__)


def _leallitva(feladat: str) -> bool:
    """VÉSZLEÁLLÍTÁS: leállított Laránál egyik ütemezett feladat sem fut (a
    tudás megmarad, a visszakapcsolás után a következő időpontban folytatja)."""
    if leallitva():
        logger.info("Lara le van állítva (vészleállítás) — %s kihagyva.", feladat)
        return True
    return False

# Europe/Budapest 02:00 — a Celery a beat időzónáját használja; ha a rendszer
# UTC-ben jár, ez UTC 02:00-nak felel meg. A pontos DST-kezelés a scheduler
# időzóna-beállításától függ (lásd docs/admin-agent/operations.md).
celery_app.conf.beat_schedule = {
    **(celery_app.conf.beat_schedule or {}),
    "admin-agent-nightly-distill": {
        "task": "admin_agent.nightly_distill",
        "schedule": crontab(hour=2, minute=0),
    },
    "admin-agent-weekly-eval": {
        "task": "admin_agent.weekly_eval",
        # Hétfő 03:00.
        "schedule": crontab(hour=3, minute=0, day_of_week=1),
    },
    "admin-agent-self-check": {
        "task": "admin_agent.self_check",
        # Kétóránként (:15-kor) — csak bekapcsolt „Tanulás és megfigyelés" forrással.
        "schedule": crontab(minute=15, hour="*/2"),
    },
    "admin-agent-levelezes": {
        "task": "admin_agent.levelezes",
        # Félóránként (:05 és :35) — csak bekapcsolt „Levelezés olvasása" forrással.
        "schedule": crontab(minute="5,35"),
    },
    "admin-agent-asszisztens": {
        "task": "admin_agent.asszisztens",
        # Félóránként (:20 és :50) — csak bekapcsolt „AI asszisztens figyelése" forrással.
        "schedule": crontab(minute="20,50"),
    },
    "admin-agent-observer": {
        "task": "admin_agent.observer",
        # Félóránként — csak ha a „Tanulás és megfigyelés" forrás be van kapcsolva.
        "schedule": crontab(minute="*/30"),
    },
    "admin-agent-beagyazas": {
        "task": "admin_agent.beagyazas",
        # Félóránként (:25 és :55) — a tudás-darabok jelentés szerinti kereséséhez.
        "schedule": crontab(minute="25,55"),
    },
    "admin-agent-rendszer": {
        "task": "admin_agent.rendszer",
        # Óránként (:40) — a teljes rendszer figyelése (csak olvas, csak tanul).
        "schedule": crontab(minute=40),
    },
    "admin-agent-tapasztalas": {
        "task": "admin_agent.tapasztalas",
        # Óránként (:10) — a teljes adattörténet tényei + Gemini-hipotézisek
        # adat-ellenőrzéssel (lásd admin_agent/tapasztalas.py). Csak olvas, csak tanul.
        "schedule": crontab(minute=10),
    },
    "admin-agent-napi-osszesito": {
        "task": "admin_agent.napi_osszesito",
        # Munkanapokon reggel (UTC 05:30 ≈ budapesti 07:30 nyáron, 06:30 télen).
        "schedule": crontab(hour=5, minute=30, day_of_week="1-5"),
    },
}


@celery_app.task(name="admin_agent.observer")
def observer_task() -> dict | None:
    """A projektkód/utókövetés megfigyelő ütemezett futása. Csak bekapcsolt
    forrással dolgozik (a megfigyeles modul maga ellenőrzi)."""
    if _leallitva("observer"):
        return {"leallitva": True}
    from app.admin_agent.observer import megfigyeles

    db = SessionLocal()
    try:
        eredmeny = megfigyeles(db)
        db.commit()
        return eredmeny
    except Exception:
        db.rollback()
        logger.exception("Lara megfigyelő futás sikertelen.")
        raise
    finally:
        db.close()


@celery_app.task(name="admin_agent.nightly_distill")
def nightly_distill_task() -> dict | None:
    """A háttér-tanuló futtatása. Akkor dolgozik, ha a tanulás engedélyezett: a
    modul be van kapcsolva VAGY a „Tanulás és megfigyelés" forrás aktív (L0-ban
    is tanulhat — a tanulás csak jelölteket készít, mellékhatás nélkül)."""
    if _leallitva("nightly_distill"):
        return {"leallitva": True}
    from app.admin_agent.learning import distill
    from app.admin_agent.observer import engedelyezve
    from app.admin_agent.settings_service import get_settings

    db = SessionLocal()
    try:
        if not (get_settings(db).module_enabled or engedelyezve(db)):
            logger.debug("Lara distill kihagyva: sem a modul, sem a tanulási forrás nincs bekapcsolva.")
            return None
        lr = distill(db, trigger="nightly")
        db.commit()
        from app.admin_agent.megerosites import futtat

        m = futtat(db, trigger="megerosites:ejszakai")
        db.commit()
        # Gyorsított tanulás a Geminivel (ugyanaz a kulcs, mint az AI
        # asszisztensé): partner-profilok + önreflexió — jelöltek, emberi
        # jóváhagyásra (lásd admin_agent/gemini_tanulas.py).
        from app.admin_agent import gemini_tanulas

        try:
            g = gemini_tanulas.futtat(db, trigger="ejszakai")
            db.commit()
        except Exception:  # noqa: BLE001 — a Gemini-tanulás hibája ne vigye el az éjszakai tanulást
            db.rollback()
            logger.exception("Lara Gemini-tanulása sikertelen.")
            g = {"allapot": "hiba"}
        return {
            "learning_run_id": lr.id,
            "feldolgozott": lr.feldolgozott_korrekciok,
            "auto_jovahagyott": m["auto_jovahagyott"],
            "uj_szabalyjavaslat": m["uj_szabalyjavaslat"],
            "gemini_tanulas": g.get("allapot"),
        }
    except Exception:
        db.rollback()
        logger.exception("Lara éjszakai distill sikertelen.")
        raise
    finally:
        db.close()


@celery_app.task(name="admin_agent.weekly_eval")
def weekly_eval_task() -> dict | None:
    """Heti teljes értékelés. A beépített biztonsági eseteket mindig ellenőrzi
    (a modul állapotától függetlenül — ez regressziós védelem)."""
    if _leallitva("weekly_eval"):
        return {"leallitva": True}
    from app.admin_agent.evals import run_eval, safety_esetek_magveto

    db = SessionLocal()
    try:
        safety_esetek_magveto(db)
        run = run_eval(db)
        db.commit()
        return {"eval_run_id": run.id, "atment": run.atment, "kritikus_hiba": run.kritikus_hiba}
    except Exception:
        db.rollback()
        logger.exception("Lara heti eval sikertelen.")
        raise
    finally:
        db.close()


@celery_app.task(name="admin_agent.self_check")
def self_check_task() -> dict | None:
    """Lara folyamatos önellenőrzése: a friss rögzítések visszajátszása, majd a
    jelenlegi tudással „vak" jóslat a rögzített számlákra, összevetés a
    valósággal, és kérdés ott, ahol nem érti az eltérést. Csak bekapcsolt
    „Tanulás és megfigyelés" forrással fut; üzleti rekordot nem módosít."""
    if _leallitva("self_check"):
        return {"leallitva": True}
    from app.admin_agent.observer import engedelyezve
    from app.admin_agent.onellenorzes import onellenorzes
    from app.admin_agent.visszajatszas import visszajatszas

    db = SessionLocal()
    try:
        if not engedelyezve(db):
            return None
        visszajatszas(db)
        eredmeny = onellenorzes(db, trigger="onellenorzes:utemezett")
        db.commit()
        # A valóság által igazolt példák automatikus jóváhagyása + szabályjavaslat
        # (lásd admin_agent/megerosites.py) — a friss visszajátszás után.
        from app.admin_agent.megerosites import futtat

        eredmeny["megerosites"] = {
            k: v for k, v in futtat(db, trigger="megerosites:utemezett").items() if k != "reszletek"
        }
        db.commit()
        # Mielőtt az ember válaszolna: Lara maga is utánanéz a friss kérdéseinek
        # az AI asszisztens csak-olvasó eszközeivel (lásd admin_agent/nyomozas.py).
        from app.admin_agent import nyomozas

        try:
            eredmeny["nyomozas"] = nyomozas.futtat(db)
            db.commit()
        except Exception:  # noqa: BLE001 — az utánanézés hibája ne vigye el az önellenőrzést
            db.rollback()
            logger.exception("Lara utánanézése sikertelen.")
        # A javítási (és más „egyéb") feladatokhoz megoldási javaslat
        # (lásd admin_agent/megoldas.py) — korlátozott számban.
        from app.admin_agent import megoldas

        try:
            eredmeny["megoldas"] = megoldas.futtat(db)
            db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
            logger.exception("Lara megoldási javaslatai sikertelenek.")
        return eredmeny
    except Exception:
        db.rollback()
        logger.exception("Lara önellenőrzése sikertelen.")
        raise
    finally:
        db.close()


@celery_app.task(name="admin_agent.levelezes")
def levelezes_task() -> dict | None:
    """A szamla@ postafiók levelezésének olvasása (szálanként tudás-jelölt).
    Csak bekapcsolt „Levelezés olvasása" forrással fut; futás közben is
    figyeli a vészleállítást (lásd admin_agent/levelezes.py)."""
    if _leallitva("levelezes"):
        return {"leallitva": True}
    from app.admin_agent.levelezes import levelezes_tanulas

    db = SessionLocal()
    try:
        eredmeny = levelezes_tanulas(db, trigger="levelezes:utemezett")
        db.commit()
        return eredmeny
    except Exception:
        db.rollback()
        logger.exception("Lara levelezés-olvasása sikertelen.")
        raise
    finally:
        db.close()


@celery_app.task(name="admin_agent.asszisztens")
def asszisztens_task() -> dict | None:
    """Az AI asszisztens lezárt kérés-köreinek figyelése (körönként tudás-jelölt).
    Csak bekapcsolt „AI asszisztens figyelése" forrással fut."""
    if _leallitva("asszisztens"):
        return {"leallitva": True}
    from app.admin_agent.asszisztens import asszisztens_tanulas

    db = SessionLocal()
    try:
        eredmeny = asszisztens_tanulas(db, trigger="asszisztens:utemezett")
        db.commit()
        return eredmeny
    except Exception:
        db.rollback()
        logger.exception("Lara AI-asszisztens-figyelése sikertelen.")
        raise
    finally:
        db.close()


@celery_app.task(name="admin_agent.beagyazas")
def beagyazas_task() -> dict | None:
    """A tudás-darabok beágyazása a jelentés szerinti kereséshez (lásd
    admin_agent/embedding.py). Kikapcsolt keresésnél / kulcs nélkül nem fut."""
    if _leallitva("beagyazas"):
        return {"leallitva": True}
    from app.admin_agent.embedding import bekapcsolva, elerheto, feltolt

    db = SessionLocal()
    try:
        if not elerheto() or not bekapcsolva(db):
            return None
        eredmeny = feltolt(db, max_db=400, max_mp=100)
        db.commit()
        return eredmeny
    except Exception:
        db.rollback()
        logger.exception("Lara beágyazása sikertelen.")
        raise
    finally:
        db.close()


@celery_app.task(name="admin_agent.napi_osszesito")
def napi_osszesito_task() -> dict | None:
    """Reggeli értesítés: hány tudás-jelölt vár jóváhagyásra, és melyik a
    legértékesebb (lásd admin_agent/osszesito.py)."""
    if _leallitva("napi_osszesito"):
        return {"leallitva": True}
    from app.admin_agent.osszesito import napi_osszesito

    db = SessionLocal()
    try:
        eredmeny = napi_osszesito(db)
        db.commit()
        return eredmeny
    except Exception:
        db.rollback()
        logger.exception("Lara napi összesítője sikertelen.")
        raise
    finally:
        db.close()


@celery_app.task(name="admin_agent.rendszer")
def rendszer_task() -> dict | None:
    """A teljes rendszer figyelése: modulonkénti rendszerismeret és projektkód-
    életút (lásd admin_agent/rendszer.py). Csak olvas; csak bekapcsolt „Teljes
    rendszer figyelése" forrással fut."""
    if _leallitva("rendszer"):
        return {"leallitva": True}
    from app.admin_agent.rendszer import engedelyezve, rendszer_figyeles

    db = SessionLocal()
    try:
        if not engedelyezve(db):
            return None
        eredmeny = rendszer_figyeles(db, trigger="rendszer:utemezett")
        db.commit()
        return eredmeny
    except Exception:
        db.rollback()
        logger.exception("Lara rendszer-figyelése sikertelen.")
        raise
    finally:
        db.close()


@celery_app.task(name="admin_agent.tapasztalas")
def tapasztalas_task() -> dict | None:
    """Lara önálló tapasztalás-köre: tények a teljes történetből, majd a Gemini
    ellenőrizhető állításai, amelyeket Lara a teljes adaton igazol vagy elvet.
    Csak bekapcsolt „Tanulás és megfigyelés" forrással fut (a modul maga
    ellenőrzi); üzleti rekordot nem módosít."""
    if _leallitva("tapasztalas"):
        return {"leallitva": True}
    from app.admin_agent.tapasztalas import futtat

    db = SessionLocal()
    try:
        eredmeny = futtat(db, trigger="utemezett")
        db.commit()
        return eredmeny
    except Exception:
        db.rollback()
        logger.exception("Lara tapasztalás-köre sikertelen.")
        raise
    finally:
        db.close()
