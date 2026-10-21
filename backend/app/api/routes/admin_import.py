"""Admin-only végpont a Notion import elindításához a böngészőből, `railway
ssh` nélkül - lásd app/notion_import/run_all.py docstringjét arról, miért kellett
ez: a `railway ssh` kapcsolat rendszeresen megszakad, mielőtt a (Notion API
rate-limitje miatt akár órákig tartó) import lefutna, és a megszakadt SSH-val
együtt a benne futó Python-processz is leáll. Ez a végpont ehelyett egy
háttérszálon indítja el az importot a futó backend service processzében.

Az állapot (fut-e, napló, hiba) az ADATBÁZISBAN van (lásd
services/hatter_feladat.py): a backend több workerrel fut, és a memóriabeli
állapotot csak az a worker látná, amelyik az importot ténylegesen futtatja -
a státusz-lekérdezés fele "nem fut semmi"-t mondott volna, a dupla indítás
elleni zár pedig nem is védett volna."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, get_db
from app.core.security import Role, require_roles
from app.models.employee import Employee
from app.notion_import import katalogus
from app.notion_import.run_all import run_import
from app.services import hatter_feladat

router = APIRouter(prefix="/admin/notion-import", tags=["admin"])

FELADAT_NEV = "notion-import"


def _import_munka(nevek: list[str] | None):
    def munka(naplo) -> None:
        db = SessionLocal()
        try:
            run_import(db, nevek, log=naplo)
        finally:
            db.close()

    return munka


class ImporterInfoOut(BaseModel):
    """Egy választható adatbázis a felületnek (lásd notion_import/katalogus.py)."""

    nev: str
    cimke: str
    kor: int
    forrasok: list[str]
    leiras: str
    fuggosegek: list[str]


@router.get("/importerek", response_model=list[ImporterInfoOut])
def list_importerek(_user: Employee = Depends(require_roles(Role.ADMIN))) -> list[ImporterInfoOut]:
    """Mit lehet importálni: Notion-táblánként egy sor, körrel és függőségekkel.

    A felület ebből építi a választót - így ha új importer kerül a katalógusba,
    magától megjelenik, nem kell a frontendet is módosítani."""
    return [
        ImporterInfoOut(
            nev=info.nev,
            cimke=info.cimke,
            kor=info.kor,
            forrasok=list(info.forrasok),
            leiras=info.leiras,
            fuggosegek=list(info.fuggosegek),
        )
        for info in katalogus.KATALOGUS
    ]


class ImportIndito(BaseModel):
    #: Mely adatbázisokat importáljuk. Üres/hiányzó = MINDET (a korábbi
    #: viselkedés, hogy a régi hívások változatlanul működjenek).
    importerek: list[str] | None = None


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def start_import(
    payload: ImportIndito | None = None,
    _user: Employee = Depends(require_roles(Role.ADMIN)),
) -> dict:
    """Import indítása. Megadható, mely adatbázisok fussanak; üres kéréssel
    minden fut.

    Az elgépelt nevet ITT utasítjuk vissza, nem a háttérszálban: különben a
    felhasználó csak a naplóból (vagy sehonnan) tudná meg, hogy elírta."""
    nevek = (payload.importerek if payload else None) or None
    if nevek:
        ismeretlen = katalogus.ismeretlen_nevek(nevek)
        if ismeretlen:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Ismeretlen adatbázis: {', '.join(ismeretlen)}.",
            )

    kivalasztott = [info.nev for info in katalogus.valogat(nevek)]
    elindult = hatter_feladat.inditas(
        FELADAT_NEV,
        _import_munka(nevek),
        reszletek={"kivalasztott": kivalasztott},
    )
    if not elindult:
        raise HTTPException(status.HTTP_409_CONFLICT, "Már fut egy Notion import.")
    return {"started": True, "importerek": kivalasztott}


@router.get("/status")
def get_status(
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_roles(Role.ADMIN)),
) -> dict:
    sor = hatter_feladat.allapot(db, FELADAT_NEV)
    if sor is None:
        return {
            "running": False,
            "started_at": None,
            "finished_at": None,
            "error": None,
            "kivalasztott": [],
            "log": [],
        }
    return {
        "running": sor.running,
        "started_at": sor.started_at.isoformat() if sor.started_at else None,
        "finished_at": sor.finished_at.isoformat() if sor.finished_at else None,
        "error": sor.error,
        "kivalasztott": (sor.reszletek or {}).get("kivalasztott", []),
        "log": sor.log.splitlines(),
    }
