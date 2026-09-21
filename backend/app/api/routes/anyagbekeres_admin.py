"""Az ANYAGBEKÉRŐ admin végpontjai - a Media Portal oldal jogosultságával
(page_permissions "/media-portal", a durva szerepkör-kapu nélkül, mint a
portal_admin). Itt jön létre a bekérés és a megosztható link, itt látszanak
a beérkezett leadások, innen megy a letöltés és a feldolgozás."""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.security import Role, hash_password, require_page_action
from app.models.anyagbekeres import (
    Anyagbekeres,
    AnyagEsemeny,
    AnyagFajl,
    AnyagLeadas,
    AnyagLeadasExport,
    AnyagMappa,
    VideoIgeny,
)
from app.models.client import Client
from app.models.employee import Employee
from app.models.project import Project
from app.services import anyagbekeres as szolg
from app.services import portal_storage as storage

router = APIRouter(prefix="/anyagbekeresek", tags=["anyagbekeres-admin"])
log = logging.getLogger(__name__)

PAGE = "/media-portal"
_MINDEN_SZEREPKOR = tuple(Role)

_LEADAS_ALLAPOTOK = ("piszkozat", "leadva", "feldolgozas", "kesz")


def _link(b: Anyagbekeres) -> str:
    alap = (settings.frontend_base_url or "").rstrip("/")
    return f"{alap}/anyagbekeres/{b.token}"


def _bekeres_sor(db: Session, b: Anyagbekeres) -> dict:
    leadasok = db.scalars(select(AnyagLeadas).where(AnyagLeadas.anyagbekeres_id == b.id)).all()
    leadott = [l for l in leadasok if l.allapot != "piszkozat"]
    ossz_meret = int(
        db.scalar(
            select(func.coalesce(func.sum(AnyagFajl.meret_bajt), 0))
            .join(AnyagLeadas, AnyagLeadas.id == AnyagFajl.leadas_id)
            .where(AnyagLeadas.anyagbekeres_id == b.id, AnyagFajl.allapot == "kesz")
        )
        or 0
    )
    utolso = db.scalar(
        select(func.max(AnyagEsemeny.created_at)).where(AnyagEsemeny.anyagbekeres_id == b.id)
    )
    return {
        "id": b.id,
        "nev": b.nev,
        "project_id": b.project_id,
        "client_id": b.client_id,
        "partner_nev": b.partner_nev,
        "hatarido": b.hatarido.isoformat() if b.hatarido else None,
        "felelos_id": b.felelos_id,
        "allapot": b.allapot,
        "lejart": szolg.link_lejart(b),
        "link_lejarat": b.link_lejarat.isoformat() if b.link_lejarat else None,
        "jelszos": bool(b.jelszo_hash),
        "kell_brief": b.kell_brief,
        "engedett_tipusok": b.engedett_tipusok,
        "meret_keret_bajt": b.meret_keret_bajt,
        "elore_mappak": b.elore_mappak or [],
        "udvozlo_szoveg": b.udvozlo_szoveg,
        "link": _link(b),
        "leadasok_szama": len(leadott),
        "piszkozatok_szama": len(leadasok) - len(leadott),
        "ossz_meret_bajt": ossz_meret,
        "utolso_aktivitas": utolso.isoformat() if utolso else (b.created_at.isoformat() if b.created_at else None),
    }


class BekeresIn(BaseModel):
    nev: str = Field(min_length=1, max_length=255)
    udvozlo_szoveg: str | None = None
    project_id: int | None = None
    client_id: int | None = None
    partner_nev: str | None = Field(default=None, max_length=255)
    hatarido: str | None = None
    felelos_id: int | None = None
    jelszo: str | None = None
    link_lejarat: str | None = None
    kell_brief: bool = True
    meret_keret_gb: float | None = Field(default=None, ge=0)
    engedett_tipusok: str | None = Field(default=None, max_length=500)
    elore_mappak: list[str] = Field(default_factory=list, max_length=50)


def _datum(ertek: str | None) -> datetime | None:
    if not ertek:
        return None
    try:
        return datetime.fromisoformat(ertek.replace("Z", ""))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Érvénytelen dátum: {ertek}") from exc


def _mezok_beallitasa(db: Session, b: Anyagbekeres, p: BekeresIn) -> None:
    if p.project_id is not None and db.get(Project, p.project_id) is None:
        raise HTTPException(status_code=404, detail="A projekt nem található.")
    if p.client_id is not None and db.get(Client, p.client_id) is None:
        raise HTTPException(status_code=404, detail="Az ügyfél nem található.")
    if p.felelos_id is not None and db.get(Employee, p.felelos_id) is None:
        raise HTTPException(status_code=404, detail="A felelős munkatárs nem található.")
    b.nev = p.nev.strip()
    b.udvozlo_szoveg = p.udvozlo_szoveg
    b.project_id = p.project_id
    b.client_id = p.client_id
    b.partner_nev = (p.partner_nev or "").strip() or None
    b.hatarido = _datum(p.hatarido)
    b.felelos_id = p.felelos_id
    b.link_lejarat = _datum(p.link_lejarat)
    b.kell_brief = p.kell_brief
    b.meret_keret_bajt = int(p.meret_keret_gb * 1024**3) if p.meret_keret_gb else None
    b.engedett_tipusok = (p.engedett_tipusok or "").strip() or None
    b.elore_mappak = [m.strip() for m in p.elore_mappak if m.strip()] or None
    # Jelszó: None = marad; "" = törlés; egyéb = csere.
    if p.jelszo is not None:
        b.jelszo_hash = hash_password(p.jelszo) if p.jelszo else None


@router.get("")
def lista(
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
):
    sorok = db.scalars(select(Anyagbekeres).order_by(Anyagbekeres.id.desc())).all()
    return [_bekeres_sor(db, b) for b in sorok]


@router.post("")
def letrehozas(
    payload: BekeresIn,
    db: Session = Depends(get_db),
    user: Employee = Depends(require_page_action(PAGE, "create", *_MINDEN_SZEREPKOR)),
):
    b = Anyagbekeres(nev=payload.nev.strip(), token=szolg.uj_token(), letrehozta_id=user.id)
    _mezok_beallitasa(db, b, payload)
    db.add(b)
    db.flush()
    szolg.esemeny(db, b.id, "letrehozva", employee_id=user.id)
    db.commit()
    return _bekeres_sor(db, b)


@router.patch("/{bekeres_id}")
def modositas(
    bekeres_id: int,
    payload: BekeresIn,
    db: Session = Depends(get_db),
    user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    b = db.get(Anyagbekeres, bekeres_id)
    if b is None:
        raise HTTPException(status_code=404, detail="Az anyagbekérés nem található.")
    _mezok_beallitasa(db, b, payload)
    szolg.esemeny(db, b.id, "modositva", employee_id=user.id)
    db.commit()
    return _bekeres_sor(db, b)


class AllapotIn(BaseModel):
    allapot: str


@router.post("/{bekeres_id}/allapot")
def bekeres_allapot(
    bekeres_id: int,
    payload: AllapotIn,
    db: Session = Depends(get_db),
    user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """Lezárás / újranyitás. A lezárt bekérés admin-oldali elérése megmarad."""
    b = db.get(Anyagbekeres, bekeres_id)
    if b is None:
        raise HTTPException(status_code=404, detail="Az anyagbekérés nem található.")
    if payload.allapot not in ("nyitott", "lezart"):
        raise HTTPException(status_code=400, detail="Az állapot 'nyitott' vagy 'lezart' lehet.")
    b.allapot = payload.allapot
    szolg.esemeny(db, b.id, "lezarva" if payload.allapot == "lezart" else "ujranyitva", employee_id=user.id)
    db.commit()
    return _bekeres_sor(db, b)


@router.post("/{bekeres_id}/token-ujra")
def token_ujragereralas(
    bekeres_id: int,
    db: Session = Depends(get_db),
    user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """A megosztási link visszavonása + újragenerálása: a régi link azonnal
    érvénytelen, a meglévő leadások (saját tokenjeikkel) megmaradnak."""
    b = db.get(Anyagbekeres, bekeres_id)
    if b is None:
        raise HTTPException(status_code=404, detail="Az anyagbekérés nem található.")
    b.token = szolg.uj_token()
    szolg.esemeny(db, b.id, "link_ujragereralva", employee_id=user.id)
    db.commit()
    return {"link": _link(b), "token": b.token}


@router.delete("/{bekeres_id}")
def bekeres_torles(
    bekeres_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "delete", *_MINDEN_SZEREPKOR)),
):
    """A teljes anyagbekérés VÉGLEGES törlése: minden leadás, mappa, fájl,
    videóigény, esemény és export is törlődik (adatbázis-cascade), és a
    feltöltött tartalom is kikerül a tárhelyről (R2). Visszavonhatatlan."""
    b = db.get(Anyagbekeres, bekeres_id)
    if b is None:
        raise HTTPException(status_code=404, detail="Az anyagbekérés nem található.")
    # A tárhely-takarítást a DB-törlés ELŐTT végezzük, amíg a kulcsok elérhetők.
    # Az összes fájl az anyagbekeres/{id}/ prefix alatt van (lásd szolg.fajl_kulcs),
    # az elkészült export-ZIP-ek pedig külön, egyedi kulcson - azokat egyenként.
    export_keyek = db.scalars(
        select(AnyagLeadasExport.object_key)
        .join(AnyagLeadas, AnyagLeadas.id == AnyagLeadasExport.leadas_id)
        .where(AnyagLeadas.anyagbekeres_id == bekeres_id, AnyagLeadasExport.object_key.is_not(None))
    ).all()
    try:
        storage.delete_prefix(f"anyagbekeres/{bekeres_id}/")
    except Exception:  # noqa: BLE001 - a tárhely-hiba ne akadályozza a törlést
        log.exception("Anyagbekérés törlése: a tárhely-takarítás megbukott (bekeres_id=%s)", bekeres_id)
    for key in export_keyek:
        szolg._biztonsagos_torles(key)
    db.delete(b)
    db.commit()
    return {"ok": True}


def _leadas_sor(l: AnyagLeadas) -> dict:
    kesz = [f for f in l.fajlok if f.allapot == "kesz"]
    return {
        "id": l.id,
        "bekuldo_nev": l.bekuldo_nev,
        "bekuldo_email": l.bekuldo_email,
        "bekuldo_ceg": l.bekuldo_ceg,
        "allapot": l.allapot,
        "leadva_at": l.leadva_at.isoformat() if l.leadva_at else None,
        "letrehozva": l.created_at.isoformat() if l.created_at else None,
        "fajlok_szama": len(kesz),
        "ossz_meret_bajt": sum(int(f.meret_bajt) for f in kesz),
        "igenyek_szama": len(l.igenyek),
        "felelos_id": l.felelos_id,
    }


@router.get("/{bekeres_id}")
def reszletek(
    bekeres_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
):
    b = db.get(Anyagbekeres, bekeres_id)
    if b is None:
        raise HTTPException(status_code=404, detail="Az anyagbekérés nem található.")
    leadasok = db.scalars(
        select(AnyagLeadas)
        .where(AnyagLeadas.anyagbekeres_id == b.id)
        .options(selectinload(AnyagLeadas.fajlok), selectinload(AnyagLeadas.igenyek))
        .order_by(AnyagLeadas.id.desc())
    ).all()
    esemenyek = db.scalars(
        select(AnyagEsemeny)
        .where(AnyagEsemeny.anyagbekeres_id == b.id)
        .order_by(AnyagEsemeny.created_at.desc())
        .limit(50)
    ).all()
    return {
        **_bekeres_sor(db, b),
        "leadasok": [_leadas_sor(l) for l in leadasok],
        "esemenyek": [
            {
                "tipus": e.tipus,
                "leadas_id": e.leadas_id,
                "adat": e.adat,
                "created_at": e.created_at.isoformat(),
            }
            for e in esemenyek
        ],
    }


@router.get("/{bekeres_id}/leadas/{leadas_id}")
def leadas_reszletek(
    bekeres_id: int,
    leadas_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
):
    l = db.scalar(
        select(AnyagLeadas)
        .where(AnyagLeadas.id == leadas_id, AnyagLeadas.anyagbekeres_id == bekeres_id)
        .options(
            selectinload(AnyagLeadas.mappak),
            selectinload(AnyagLeadas.fajlok),
            selectinload(AnyagLeadas.igenyek).selectinload(VideoIgeny.forrasok),
        )
    )
    if l is None:
        raise HTTPException(status_code=404, detail="A leadás nem található.")
    return {
        **_leadas_sor(l),
        "belso_megjegyzes": l.belso_megjegyzes,
        "mappak": [
            {"id": m.id, "szulo_id": m.szulo_id, "nev": m.nev, "utvonal": m.utvonal, "leiras": m.leiras}
            for m in sorted(l.mappak, key=lambda m: m.utvonal.lower())
        ],
        "fajlok": [
            {
                "id": f.id,
                "mappa_id": f.mappa_id,
                "nev": f.eredeti_nev,
                "relativ_utvonal": f.relativ_utvonal,
                "meret_bajt": f.meret_bajt,
                "content_type": f.content_type,
                "allapot": f.allapot,
                "kesz_at": f.kesz_at.isoformat() if f.kesz_at else None,
            }
            for f in sorted(l.fajlok, key=lambda f: (f.relativ_utvonal or f.eredeti_nev).lower())
        ],
        "igenyek": [
            {
                "id": i.id,
                "nev": i.nev,
                "leiras": i.leiras,
                "hossz": i.hossz,
                "felulet": i.felulet,
                "keparany": i.keparany,
                "hatarido": i.hatarido.isoformat() if i.hatarido else None,
                "teljes_anyagbol": i.teljes_anyagbol,
                "reszletek": i.reszletek or {},
                "idokodok": i.idokodok or [],
                "mappa_idk": [x.mappa_id for x in i.forrasok if x.mappa_id],
                "fajl_idk": [x.fajl_id for x in i.forrasok if x.fajl_id],
            }
            for i in l.igenyek
        ],
    }


class LeadasModositasIn(BaseModel):
    allapot: str | None = None
    felelos_id: int | None = Field(default=None)
    belso_megjegyzes: str | None = None


@router.patch("/{bekeres_id}/leadas/{leadas_id}")
def leadas_modositas(
    bekeres_id: int,
    leadas_id: int,
    payload: LeadasModositasIn,
    db: Session = Depends(get_db),
    user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    l = db.scalar(select(AnyagLeadas).where(AnyagLeadas.id == leadas_id, AnyagLeadas.anyagbekeres_id == bekeres_id))
    if l is None:
        raise HTTPException(status_code=404, detail="A leadás nem található.")
    adatok = payload.model_dump(exclude_unset=True)
    if "allapot" in adatok:
        if adatok["allapot"] not in _LEADAS_ALLAPOTOK:
            raise HTTPException(status_code=400, detail=f"Ismeretlen állapot: {adatok['allapot']}")
        if l.allapot != adatok["allapot"]:
            szolg.esemeny(
                db, bekeres_id, "leadas_allapot", leadas_id=l.id, adat={"uj": adatok["allapot"]}, employee_id=user.id
            )
        l.allapot = adatok["allapot"]
    if "felelos_id" in adatok:
        l.felelos_id = adatok["felelos_id"]
    if "belso_megjegyzes" in adatok:
        l.belso_megjegyzes = adatok["belso_megjegyzes"]
    db.commit()
    return _leadas_sor(l)


@router.get("/{bekeres_id}/leadas/{leadas_id}/fajl/{fajl_id}/letoltes")
def fajl_letoltes(
    bekeres_id: int,
    leadas_id: int,
    fajl_id: int,
    # Megosztható link: a beküldött fájlra mutató, aláírt letöltő URL. Sima
    # letöltésnél 1 óra elég; a "Link kimásolása" gomb hosszabb (max 7 napos)
    # linket kér, amit a kolléga később is meg tud nyitni.
    megosztas: bool = Query(default=False),
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
):
    f = db.get(AnyagFajl, fajl_id)
    if f is None or f.leadas_id != leadas_id:
        raise HTTPException(status_code=404, detail="A fájl nem található.")
    l = db.get(AnyagLeadas, leadas_id)
    if l is None or l.anyagbekeres_id != bekeres_id:
        raise HTTPException(status_code=404, detail="A leadás nem található.")
    if f.allapot != "kesz":
        raise HTTPException(status_code=400, detail="Ez a fájl még nincs (sikeresen) feltöltve.")
    # 7 nap = az aláírt (SigV4) URL maximuma.
    expires = 7 * 24 * 3600 if megosztas else 3600
    return {"url": storage.presigned_download(f.storage_key, f.eredeti_nev, expires=expires)}


class ExportIn(BaseModel):
    mappa_id: int | None = None


@router.post("/{bekeres_id}/leadas/{leadas_id}/export")
def export_inditas(
    bekeres_id: int,
    leadas_id: int,
    payload: ExportIn,
    db: Session = Depends(get_db),
    user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
):
    """Háttérben készülő ZIP a teljes leadásról vagy egy mappájáról, EREDETI
    struktúrával - a kész csomag időkorlátos letöltési linket kap."""
    l = db.scalar(
        select(AnyagLeadas)
        .where(AnyagLeadas.id == leadas_id, AnyagLeadas.anyagbekeres_id == bekeres_id)
        .options(selectinload(AnyagLeadas.mappak), selectinload(AnyagLeadas.fajlok))
    )
    if l is None:
        raise HTTPException(status_code=404, detail="A leadás nem található.")
    mappa = None
    if payload.mappa_id is not None:
        mappa = db.get(AnyagMappa, payload.mappa_id)
        if mappa is None or mappa.leadas_id != l.id:
            raise HTTPException(status_code=404, detail="A mappa nem található.")
    nev = f"{l.bekuldo_nev}-{mappa.nev}" if mappa else l.bekuldo_nev
    try:
        job = szolg.export_kerese(db, l, mappa, nev)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    szolg.esemeny(db, bekeres_id, "export", leadas_id=l.id, adat={"job": job.id}, employee_id=user.id)
    db.commit()
    return szolg.export_allapot(job)


@router.delete("/{bekeres_id}/leadas/{leadas_id}/igeny/{igeny_id}")
def igeny_torles(
    bekeres_id: int,
    leadas_id: int,
    igeny_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "delete", *_MINDEN_SZEREPKOR)),
):
    """Egy kért videó (videóigény) törlése a leadásból - a hozzá kötött
    forrás-hivatkozások (mappa/fájl) is törlődnek, a fájlok maguk nem."""
    l = db.scalar(
        select(AnyagLeadas).where(AnyagLeadas.id == leadas_id, AnyagLeadas.anyagbekeres_id == bekeres_id)
    )
    if l is None:
        raise HTTPException(status_code=404, detail="A leadás nem található.")
    ig = db.get(VideoIgeny, igeny_id)
    if ig is None or ig.leadas_id != leadas_id:
        raise HTTPException(status_code=404, detail="A kért videó nem található.")
    db.delete(ig)
    db.commit()
    return {"ok": True}


@router.get("/export/{job_id}")
def export_allapot(
    job_id: str,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
):
    job = db.get(AnyagLeadasExport, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="A csomag nem található.")
    # Ha a folyamat újraindult és a job beragadt, innen újraindítható.
    if job.state == "queued" and job.touched_at < szolg.most().replace(microsecond=0):
        szolg.inditsd_a_hattereben(job.id)
    return szolg.export_allapot(job)
