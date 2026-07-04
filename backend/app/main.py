from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import api_router
from app.core.config import settings

app = FastAPI(title="HYPE OS API", version="0.1.0")

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

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "environment": settings.environment}
