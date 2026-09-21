import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError

from app.api.routes import api_router
from app.core.config import settings
from app.services.portal_storage import R2NotConfiguredError

logger = logging.getLogger("hype_os")

app = FastAPI(title="HYPE OS API", version="0.1.0")


@app.exception_handler(R2NotConfiguredError)
async def r2_not_configured_handler(request: Request, exc: R2NotConfiguredError) -> JSONResponse:
    """Videó/kép feltöltésnél az R2 hitelesítő adatok hiánya egyértelmű 503-at
    adjon vissza (nem egy nyers boto3/hálózati kivétel 500-at) - lásd
    services/portal_storage.py is_configured()."""
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.middleware("http")
async def catch_unhandled_exceptions(request: Request, call_next):
    """Bármilyen le nem kezelt kivétel itt fusson át. FONTOS: ez a middleware
    a forráskódban a CORSMiddleware ELŐTT van regisztrálva, ezért az ő
    "belsejében" fut (a Starlette middleware-verem a hozzáadás sorrendjének
    fordítottja - a később hozzáadott lesz a külső réteg) - egy sima
    @app.exception_handler(Exception) NEM lenne elég, mert a Starlette azt
    külön a legkülső ServerErrorMiddleware-hez köti (lásd
    starlette.applications.Starlette.build_middleware_stack: `if key in (500,
    Exception): error_handler = value`), ami a CORSMiddleware-en KÍVÜL van -
    így egy ott elkapott 500-as válaszra sosem kerülne CORS fejléc, és a
    böngésző tévesen CORS-hibaként mutatná azt, ami valójában egy 500-as
    szerverhiba (a tényleges hiba a Railway logban látszik, itt csak a
    felhasználó felé megy egyértelmű üzenet)."""
    try:
        return await call_next(request)
    except SQLAlchemyTimeoutError:
        # Kapcsolat-kimerülés (pool timeout): EGY sor a logba, nem teljes
        # traceback - túlterheléskor kérésenként egy ~100 soros traceback
        # percenként több ezer log-sort jelentett, amit a Railway el is
        # kezdett eldobni (500 log/mp korlát), és pont a hasznos sorok
        # vesztek el. A válasz 503: a kliens tudja, hogy átmeneti.
        logger.warning("Adatbázis-kapcsolat várakozás timeout: %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=503,
            content={"detail": "A rendszer pillanatnyilag túlterhelt - próbáld újra pár másodperc múlva."},
        )
    except Exception:
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Váratlan szerverhiba történt."})


_cors_origins = settings.cors_origin_list
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    # A "*" origin és allow_credentials=True kombináció tiltott a böngészőkben -
    # de mivel az auth Bearer token-nel megy (Authorization header), nem
    # cookie-val, nincs is szükség allow_credentials-re wildcard esetén.
    allow_credentials=_cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# A nagy listák (projektkódok, utómunka, kiadások) több száz kilobájtos
# JSON-ok - tömörítve a töredékük megy át a hálózaton, ami 30 párhuzamos
# felhasználónál érezhetően gyorsabb oldalbetöltést ad. A kis válaszokat
# (minimum_size alatt) nem éri meg tömöríteni.
app.add_middleware(GZipMiddleware, minimum_size=1024)

app.include_router(api_router, prefix="/api/v1")


@app.on_event("startup")
def _regi_diszpo_pdfek_athozasa() -> None:
    """A RÉGI diszpó PDF-ek átköltöztetése a saját tárhelyre (R2) - a
    felhasználó kérése: a diszpók ne a Drive-ról nyíljanak. Induláskor
    háttérszálon fut (az app azonnal kiszolgál), idempotens: csak addig
    csinál bármit, amíg van még át nem hozott régi diszpó - utána minden
    indulásnál üresen tér vissza. Több worker esetén a hatter_feladatok
    tábla zárja, hogy csak egy példány fusson."""
    try:
        from app.services import diszpo_pdf_koltoztetes

        if diszpo_pdf_koltoztetes.inditsd_a_teljes_koltoztetest():
            logger.info("Régi diszpó PDF-ek R2-re költöztetése elindult a háttérben.")
    except Exception:  # noqa: BLE001 - az app indulását ez nem akaszthatja meg
        logger.exception("A régi diszpó PDF-ek költöztetését nem sikerült elindítani.")


@app.on_event("startup")
def _szamla_auto_erkeztetes() -> None:
    """AUTOMATIKUS számla-érkeztetés: a bejövő címre érkezett levelek
    feldolgozása a háttérben, akkor is, ha senki nem nyitja meg az oldalt
    (a felhasználó kérése). A gyakoriság env-ből állítható
    (SZAMLA_AUTO_GYAKORISAG_PERC, 0 = kikapcsolva, csak kézi ellenőrzés).

    Több uvicorn worker esetén a hatter_feladatok tábla zárja, hogy egy
    ellenőrzés egyszerre csak egy példányban fusson - ugyanaz a zár, amit a
    kézi "Ellenőrzés most" gomb is használ, tehát ütközés ott sincs. Egy
    hibás futás nem állítja le az időzítőt: a következő kör újrapróbálja."""
    gyakorisag = int(settings.szamla_auto_gyakorisag_perc or 0)
    if gyakorisag <= 0:
        logger.info("Automatikus számla-érkeztetés kikapcsolva (SZAMLA_AUTO_GYAKORISAG_PERC=0).")
        return

    import threading
    import time as _time

    def _kor() -> None:
        from app.api.routes.bejovo_szamlak import EMAIL_LEHUZAS_FELADAT
        from app.services import hatter_feladat, szamla_email_lehuzas

        while True:
            _time.sleep(gyakorisag * 60)
            try:

                def _munka(naplo):
                    from app.core.database import SessionLocal

                    db = SessionLocal()
                    try:
                        return szamla_email_lehuzas.lehuzas(db, limit=100, naplo=naplo)
                    finally:
                        db.close()

                hatter_feladat.inditas(EMAIL_LEHUZAS_FELADAT, _munka)
            except Exception:  # noqa: BLE001 - a következő kör újrapróbálja
                logger.exception("Automatikus számla-érkeztetés: az ellenőrzés nem indult el.")

    threading.Thread(target=_kor, daemon=True, name="szamla-auto-erkeztetes").start()
    logger.info("Automatikus számla-érkeztetés bekapcsolva: %s percenként.", gyakorisag)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "environment": settings.environment}


# Durable outbox consumption; SKIP LOCKED coordinates multiple API workers.
import threading
_push_stop = threading.Event()
_push_thread = None

@app.on_event("startup")
def _start_apple_push():
    global _push_thread
    from app.services.push_delivery import start_worker
    _push_stop.clear()
    _push_thread = threading.Thread(target=start_worker, args=(_push_stop,), daemon=True, name="apple-push")
    _push_thread.start()

@app.on_event("shutdown")
def _stop_apple_push():
    _push_stop.set()
    if _push_thread is not None:
        _push_thread.join(timeout=12)


# Capability negotiation prevents old servers from silently ignoring offline guards.
from fastapi import Depends
from app.core.security import get_current_user
from app.models.employee import Employee

@app.get("/api/v1/offline/capabilities")
def offline_capabilities(user: Employee = Depends(get_current_user)):
    from app.services.offline_sync import PATCH_PREFIXES
    from fastapi import HTTPException
    if user.is_active is False and not getattr(user, "vedett_admin", False):
        raise HTTPException(status_code=403, detail="Inaktív fiók")
    return {"version": 1, "grid": True, "patch_prefixes": sorted(PATCH_PREFIXES)}
