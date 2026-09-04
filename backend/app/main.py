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


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "environment": settings.environment}
