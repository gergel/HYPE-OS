"""Az ANYAGBEKÉRŐ publikus (tokenes) végpontjai - a beküldői oldal API-ja.

Kétféle token van:
- a BEKÉRÉS tokenje (a megosztott link): csak a bekérés adatait mutatja, és
  új leadást lehet vele nyitni - korábbi leadásokhoz NEM ad hozzáférést;
- a LEADÁS tokenje (a beküldő saját folytatási linkje): ezzel éri el és
  szerkeszti a beküldő a SAJÁT piszkozatát. Más leadás azonosítójának
  ismerete nem ér semmit - minden művelet ehhez a tokenhez kötött.

A fájlok KÖZVETLENÜL az R2-be mennek darabolt (multipart) feltöltéssel,
rövid élettartamú aláírt URL-ekkel - az alkalmazásszerveren csak a pár
bájtos vezérlő-hívások (init/sign/complete) mennek át, a médiatartalom nem."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.security import hash_password, verify_password
from app.models.anyagbekeres import Anyagbekeres, AnyagFajl, AnyagLeadas, AnyagMappa, VideoIgeny, VideoIgenyForras
from app.services import anyagbekeres as szolg
from app.services import notifications
from app.services import portal_storage as storage
from app.services.portal_storage import R2NotConfiguredError

router = APIRouter(prefix="/public/anyagbekeres", tags=["anyagbekeres-public"])


def _bekeres_token_alapjan(db: Session, token: str) -> Anyagbekeres:
    b = db.scalar(select(Anyagbekeres).where(Anyagbekeres.token == token))
    if b is None:
        raise HTTPException(status_code=404, detail="Az anyagbekérés nem található - a link érvénytelen vagy visszavonták.")
    return b


def _leadas_token_alapjan(db: Session, token: str) -> AnyagLeadas:
    l = db.scalar(
        select(AnyagLeadas)
        .where(AnyagLeadas.token == token)
        .options(
            selectinload(AnyagLeadas.mappak),
            selectinload(AnyagLeadas.fajlok),
            selectinload(AnyagLeadas.igenyek).selectinload(VideoIgeny.forrasok),
            selectinload(AnyagLeadas.anyagbekeres),
        )
    )
    if l is None:
        raise HTTPException(status_code=404, detail="A leadás nem található - a folytatási link érvénytelen.")
    return l


def _szerkesztheto(leadas: AnyagLeadas) -> None:
    if leadas.allapot != "piszkozat":
        raise HTTPException(status_code=409, detail="Ez a leadás már véglegesítve lett - nem módosítható.")


def _bekeres_info(b: Anyagbekeres) -> dict:
    return {
        "nev": b.nev,
        "udvozlo_szoveg": b.udvozlo_szoveg,
        "hatarido": b.hatarido.isoformat() if b.hatarido else None,
        "kell_brief": b.kell_brief,
        "engedett_tipusok": b.engedett_tipusok,
        "meret_keret_bajt": b.meret_keret_bajt,
        "jelszo_kell": bool(b.jelszo_hash),
        "lezart": b.allapot != "nyitott",
        "lejart": szolg.link_lejart(b),
        "fogadokepes": szolg.fogadokepes(b),
    }


def _leadas_valasz(leadas: AnyagLeadas) -> dict:
    """A beküldő SAJÁT teljes állapota - ebből áll vissza minden frissítés
    után (brief, mappák, fájl-állapotok). Belső megjegyzés SOSEM megy ki."""
    return {
        "bekeres": _bekeres_info(leadas.anyagbekeres),
        "leadas": {
            "id": leadas.id,
            "allapot": leadas.allapot,
            "leadva_at": leadas.leadva_at.isoformat() if leadas.leadva_at else None,
            "bekuldo_nev": leadas.bekuldo_nev,
            "bekuldo_email": leadas.bekuldo_email,
            "bekuldo_ceg": leadas.bekuldo_ceg,
        },
        "mappak": [
            {"id": m.id, "szulo_id": m.szulo_id, "nev": m.nev, "utvonal": m.utvonal, "leiras": m.leiras}
            for m in sorted(leadas.mappak, key=lambda m: m.utvonal.lower())
        ],
        "fajlok": [
            {
                "id": f.id,
                "mappa_id": f.mappa_id,
                "nev": f.eredeti_nev,
                "relativ_utvonal": f.relativ_utvonal,
                "meret_bajt": f.meret_bajt,
                "allapot": f.allapot,
                # A már IGAZOLTAN feltöltött darabok sorszámai - oldalfrissítés
                # utáni folytatáshoz (a fájlt újra ki kell választani, de a
                # kész darabokat nem töltjük fel újra).
                "kesz_reszek": sorted(int(k) for k in (f.kesz_reszek or {}).keys()),
            }
            for f in sorted(leadas.fajlok, key=lambda f: f.id)
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
            for i in leadas.igenyek
        ],
        "resz_meret": szolg.RESZ_MERET,
    }


# ── A bekérő link ────────────────────────────────────────────────────────────


@router.get("/{token}")
def bekeres_adatok(token: str, db: Session = Depends(get_db)):
    """A bekérés publikus adatai - leadások és személyes adatok NÉLKÜL."""
    return _bekeres_info(_bekeres_token_alapjan(db, token))


class UjLeadasIn(BaseModel):
    bekuldo_nev: str = Field(min_length=1, max_length=255)
    bekuldo_email: str = Field(min_length=3, max_length=255)
    bekuldo_ceg: str | None = Field(default=None, max_length=255)
    jelszo: str | None = None


@router.post("/{token}/leadas")
def uj_leadas(token: str, payload: UjLeadasIn, db: Session = Depends(get_db)):
    """Új SAJÁT leadás nyitása - a válaszban a beküldő titkos folytatási
    tokenje. Az előre beállított mappák ekkor jönnek létre."""
    b = _bekeres_token_alapjan(db, token)
    if not szolg.fogadokepes(b):
        raise HTTPException(status_code=410, detail="Ez az anyagbekérés már lezárult vagy a link lejárt - új leadás nem indítható.")
    if b.jelszo_hash and not (payload.jelszo and verify_password(payload.jelszo, b.jelszo_hash)):
        raise HTTPException(status_code=401, detail="Hibás vagy hiányzó jelszó.")
    if "@" not in payload.bekuldo_email:
        raise HTTPException(status_code=400, detail="Érvényes e-mail címet adj meg.")
    leadas = AnyagLeadas(
        anyagbekeres_id=b.id,
        token=szolg.uj_token(),
        bekuldo_nev=payload.bekuldo_nev.strip(),
        bekuldo_email=payload.bekuldo_email.strip(),
        bekuldo_ceg=(payload.bekuldo_ceg or "").strip() or None,
    )
    db.add(leadas)
    db.flush()
    for nev in b.elore_mappak or []:
        try:
            szolg.mappa_utvonalra(db, leadas, str(nev))
        except ValueError:
            continue
    szolg.esemeny(db, b.id, "leadas_nyitva", leadas_id=leadas.id, adat={"bekuldo": leadas.bekuldo_nev})
    db.commit()
    return {"leadas_token": leadas.token}


# ── A beküldő saját leadása ──────────────────────────────────────────────────


@router.get("/leadas/{token}")
def leadas_adatok(token: str, db: Session = Depends(get_db)):
    leadas = _leadas_token_alapjan(db, token)
    # Olcsó takarítás: a rég félbehagyott feltöltés-alatti sorok kiesnek.
    if szolg.felbehagyott_feltoltesek_takaritasa(db, leadas):
        db.commit()
        db.refresh(leadas)
    return _leadas_valasz(leadas)


class BekuldoIn(BaseModel):
    bekuldo_nev: str | None = Field(default=None, max_length=255)
    bekuldo_email: str | None = Field(default=None, max_length=255)
    bekuldo_ceg: str | None = Field(default=None, max_length=255)


@router.patch("/leadas/{token}")
def bekuldo_adatok(token: str, payload: BekuldoIn, db: Session = Depends(get_db)):
    leadas = _leadas_token_alapjan(db, token)
    _szerkesztheto(leadas)
    if payload.bekuldo_nev is not None and payload.bekuldo_nev.strip():
        leadas.bekuldo_nev = payload.bekuldo_nev.strip()
    if payload.bekuldo_email is not None and "@" in payload.bekuldo_email:
        leadas.bekuldo_email = payload.bekuldo_email.strip()
    if payload.bekuldo_ceg is not None:
        leadas.bekuldo_ceg = payload.bekuldo_ceg.strip() or None
    db.commit()
    return {"ok": True}


class MappaIn(BaseModel):
    nev: str = Field(min_length=1, max_length=255)
    szulo_id: int | None = None
    leiras: str | None = None


@router.post("/leadas/{token}/mappa")
def mappa_letrehozas(token: str, payload: MappaIn, db: Session = Depends(get_db)):
    leadas = _leadas_token_alapjan(db, token)
    _szerkesztheto(leadas)
    if not szolg.fogadokepes(leadas.anyagbekeres):
        raise HTTPException(status_code=410, detail="A bekérés lezárult - új mappa nem hozható létre.")
    try:
        nev = szolg.tiszta_szegmens(payload.nev)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    szulo = None
    if payload.szulo_id is not None:
        szulo = db.get(AnyagMappa, payload.szulo_id)
        if szulo is None or szulo.leadas_id != leadas.id:
            raise HTTPException(status_code=404, detail="A szülőmappa nem található.")
    utvonal = f"{szulo.utvonal}/{nev}" if szulo else nev
    letezo = db.scalar(select(AnyagMappa).where(AnyagMappa.leadas_id == leadas.id, AnyagMappa.utvonal == utvonal))
    if letezo is not None:
        return {"id": letezo.id, "utvonal": letezo.utvonal}
    mappa = AnyagMappa(leadas_id=leadas.id, szulo_id=szulo.id if szulo else None, nev=nev, utvonal=utvonal, leiras=payload.leiras)
    db.add(mappa)
    db.commit()
    return {"id": mappa.id, "utvonal": mappa.utvonal}


class MappaModositasIn(BaseModel):
    leiras: str | None = None


@router.patch("/leadas/{token}/mappa/{mappa_id}")
def mappa_leiras(token: str, mappa_id: int, payload: MappaModositasIn, db: Session = Depends(get_db)):
    leadas = _leadas_token_alapjan(db, token)
    _szerkesztheto(leadas)
    mappa = db.get(AnyagMappa, mappa_id)
    if mappa is None or mappa.leadas_id != leadas.id:
        raise HTTPException(status_code=404, detail="A mappa nem található.")
    mappa.leiras = payload.leiras
    db.commit()
    return {"ok": True}


# ── Fájlfeltöltés (R2 multipart, aláírt URL-ekkel) ───────────────────────────


class FajlInitIn(BaseModel):
    nev: str = Field(min_length=1, max_length=500)
    #: A beküldő gépén volt relatív MAPPA-útvonal ("Nyersek/A kamera") - mappa-
    #: feltöltésnél ebből épül a fa; kézi feltöltésnél a mappa_id az irányadó.
    relativ_mappa: str | None = None
    mappa_id: int | None = None
    meret_bajt: int = Field(ge=1)
    content_type: str | None = None


@router.post("/leadas/{token}/fajl/init")
def fajl_init(token: str, payload: FajlInitIn, db: Session = Depends(get_db)):
    """Feltöltés indítása: szerveroldali típus-/kvóta-/útvonal-ellenőrzés,
    aztán R2 multipart nyitás. A válaszból tölt a kliens (sign-part)."""
    leadas = _leadas_token_alapjan(db, token)
    _szerkesztheto(leadas)
    b = leadas.anyagbekeres
    if not szolg.fogadokepes(b):
        raise HTTPException(status_code=410, detail="A bekérés lezárult vagy a link lejárt - új feltöltés nem indítható.")
    try:
        nev = szolg.tiszta_szegmens(payload.nev.replace("\\", "/").rsplit("/", 1)[-1])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not szolg.kiterjesztes_engedett(b, nev):
        raise HTTPException(status_code=400, detail=f"Ez a fájltípus itt nem engedett ({b.engedett_tipusok}).")
    if payload.meret_bajt > szolg.MAX_FAJL_BAJT:
        raise HTTPException(status_code=400, detail="A fájl túl nagy.")
    if b.meret_keret_bajt and szolg.felhasznalt_bajt(db, leadas.id) + payload.meret_bajt > b.meret_keret_bajt:
        raise HTTPException(status_code=400, detail="A feltöltési keret betelt ehhez a leadáshoz.")

    if payload.mappa_id is not None:
        mappa = db.get(AnyagMappa, payload.mappa_id)
        if mappa is None or mappa.leadas_id != leadas.id:
            raise HTTPException(status_code=404, detail="A mappa nem található.")
    else:
        try:
            mappa = szolg.mappa_utvonalra(db, leadas, payload.relativ_mappa or "")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    fajl = AnyagFajl(
        leadas_id=leadas.id,
        mappa_id=mappa.id if mappa else None,
        eredeti_nev=nev,
        relativ_utvonal=(f"{mappa.utvonal}/{nev}" if mappa else nev),
        storage_key="",
        meret_bajt=payload.meret_bajt,
        content_type=payload.content_type,
    )
    db.add(fajl)
    db.flush()
    fajl.storage_key = szolg.fajl_kulcs(b.id, leadas.id, fajl.id, nev)
    try:
        fajl.upload_id = storage.create_multipart(fajl.storage_key, payload.content_type or "application/octet-stream")
    except R2NotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    db.commit()
    return {"fajl_id": fajl.id, "mappa_id": fajl.mappa_id, "resz_meret": szolg.RESZ_MERET}


def _sajat_folyamatban_levo_fajl(db: Session, leadas: AnyagLeadas, fajl_id: int) -> AnyagFajl:
    fajl = db.get(AnyagFajl, fajl_id)
    if fajl is None or fajl.leadas_id != leadas.id:
        raise HTTPException(status_code=404, detail="A fájl nem található.")
    return fajl


class ReszIn(BaseModel):
    part_number: int = Field(ge=1, le=10000)


@router.post("/leadas/{token}/fajl/{fajl_id}/sign")
def fajl_sign(token: str, fajl_id: int, payload: ReszIn, db: Session = Depends(get_db)):
    leadas = _leadas_token_alapjan(db, token)
    fajl = _sajat_folyamatban_levo_fajl(db, leadas, fajl_id)
    if fajl.allapot == "kesz" or not fajl.upload_id:
        raise HTTPException(status_code=409, detail="Ez a fájl már fel van töltve.")
    return {"url": storage.presigned_part(fajl.storage_key, fajl.upload_id, payload.part_number, expires=3600)}


class ReszKeszIn(BaseModel):
    part_number: int = Field(ge=1, le=10000)
    etag: str = Field(min_length=1, max_length=200)


@router.post("/leadas/{token}/fajl/{fajl_id}/resz-kesz")
def fajl_resz_kesz(token: str, fajl_id: int, payload: ReszKeszIn, db: Session = Depends(get_db)):
    """Egy darab sikeres feltöltésének KÖNYVELÉSE - oldalfrissítés utáni
    folytatáshoz a szerver is tudja, mely darabok vannak fent."""
    leadas = _leadas_token_alapjan(db, token)
    fajl = _sajat_folyamatban_levo_fajl(db, leadas, fajl_id)
    reszek = dict(fajl.kesz_reszek or {})
    reszek[str(payload.part_number)] = payload.etag
    fajl.kesz_reszek = reszek
    fajl.allapot = "feltoltes_alatt"
    db.commit()
    return {"ok": True}


@router.post("/leadas/{token}/fajl/{fajl_id}/befejez")
def fajl_befejez(token: str, fajl_id: int, db: Session = Depends(get_db)):
    """A multipart lezárása a KÖNYVELT darabokból + szerveroldali méret-
    ellenőrzés: a fájl csak akkor lesz "kesz", ha az R2-ben tényleg a várt
    méretű objektum áll."""
    leadas = _leadas_token_alapjan(db, token)
    fajl = _sajat_folyamatban_levo_fajl(db, leadas, fajl_id)
    if fajl.allapot == "kesz":
        return {"allapot": "kesz"}
    if not fajl.upload_id or not fajl.kesz_reszek:
        raise HTTPException(status_code=400, detail="Ehhez a fájlhoz nincs könyvelt feltöltött darab.")
    parts = [{"PartNumber": int(k), "ETag": v} for k, v in fajl.kesz_reszek.items()]
    try:
        storage.complete_multipart(fajl.storage_key, fajl.upload_id, parts)
        tenyleges = storage.head_size(fajl.storage_key)
    except Exception as exc:  # noqa: BLE001 - a hívó emberi hibát vár
        fajl.allapot = "hibas"
        db.commit()
        raise HTTPException(status_code=400, detail="A feltöltés lezárása nem sikerült - próbáld újra a fájlt.") from exc
    if tenyleges != fajl.meret_bajt:
        fajl.allapot = "hibas"
        db.commit()
        raise HTTPException(status_code=400, detail="A feltöltött méret nem egyezik - töltsd fel újra a fájlt.")
    fajl.allapot = "kesz"
    fajl.upload_id = None
    fajl.kesz_at = szolg.most()
    db.commit()
    return {"allapot": "kesz"}


@router.delete("/leadas/{token}/fajl/{fajl_id}")
def fajl_torles(token: str, fajl_id: int, db: Session = Depends(get_db)):
    """Hibás/felesleges fájl eltávolítása a leadásból (a beküldő sajátja)."""
    leadas = _leadas_token_alapjan(db, token)
    _szerkesztheto(leadas)
    fajl = _sajat_folyamatban_levo_fajl(db, leadas, fajl_id)
    if fajl.upload_id:
        storage.abort_multipart(fajl.storage_key, fajl.upload_id)
    elif fajl.allapot == "kesz" and fajl.storage_key:
        try:
            storage.delete_prefix(fajl.storage_key)
        except Exception:  # noqa: BLE001 - az árva objektumot a takarítás szedi fel
            pass
    db.delete(fajl)
    db.commit()
    return {"ok": True}


# ── Videóigények (brief) - automatikus mentés teljes cserével ────────────────


class IgenyIn(BaseModel):
    nev: str = Field(min_length=1, max_length=255)
    leiras: str | None = None
    hossz: str | None = Field(default=None, max_length=120)
    felulet: str | None = Field(default=None, max_length=255)
    keparany: str | None = Field(default=None, max_length=30)
    hatarido: str | None = None
    teljes_anyagbol: bool = False
    reszletek: dict = Field(default_factory=dict)
    idokodok: list = Field(default_factory=list)
    mappa_idk: list[int] = Field(default_factory=list)
    fajl_idk: list[int] = Field(default_factory=list)


class IgenyekIn(BaseModel):
    igenyek: list[IgenyIn] = Field(max_length=100)


@router.put("/leadas/{token}/igenyek")
def igenyek_mentese(token: str, payload: IgenyekIn, db: Session = Depends(get_db)):
    """A brief mentése (a felület automatikusan hívja): a teljes lista
    cseréje - így a visszaállítás is mindig egyértelmű."""
    leadas = _leadas_token_alapjan(db, token)
    _szerkesztheto(leadas)
    sajat_mappak = {m.id for m in leadas.mappak}
    sajat_fajlok = {f.id for f in leadas.fajlok}
    for i in leadas.igenyek:
        db.delete(i)
    db.flush()
    for sorrend, be in enumerate(payload.igenyek):
        hatarido = None
        if be.hatarido:
            try:
                hatarido = datetime.fromisoformat(be.hatarido.replace("Z", ""))
            except ValueError:
                hatarido = None
        igeny = VideoIgeny(
            leadas_id=leadas.id,
            sorrend=sorrend,
            nev=be.nev.strip()[:255],
            leiras=be.leiras,
            hossz=be.hossz,
            felulet=be.felulet,
            keparany=be.keparany,
            hatarido=hatarido,
            teljes_anyagbol=be.teljes_anyagbol,
            reszletek=be.reszletek or None,
            idokodok=be.idokodok or None,
        )
        db.add(igeny)
        db.flush()
        # Csak a SAJÁT leadás mappái/fájljai köthetők forrásként.
        for mid in dict.fromkeys(be.mappa_idk):
            if mid in sajat_mappak:
                db.add(VideoIgenyForras(igeny_id=igeny.id, mappa_id=mid))
        for fid in dict.fromkeys(be.fajl_idk):
            if fid in sajat_fajlok:
                db.add(VideoIgenyForras(igeny_id=igeny.id, fajl_id=fid))
    db.commit()
    return {"ok": True, "mentve": len(payload.igenyek)}


# ── Véglegesítés ─────────────────────────────────────────────────────────────


@router.post("/leadas/{token}/veglegesit")
def veglegesites(token: str, db: Session = Depends(get_db)):
    """A leadás véglegesítése. IDEMPOTENS: az ismételt hívás (dupla kattintás)
    nem hoz létre új leadást és nem küld új értesítést."""
    leadas = _leadas_token_alapjan(db, token)
    if leadas.allapot != "piszkozat":
        return {"allapot": leadas.allapot, "leadas_id": leadas.id, "mar_leadva": True}
    fuggoben = [f for f in leadas.fajlok if f.allapot != "kesz"]
    if fuggoben:
        raise HTTPException(
            status_code=400,
            detail=f"{len(fuggoben)} fájl feltöltése még nem fejeződött be - várd meg, próbáld újra, vagy távolítsd el őket.",
        )
    kesz_fajlok = [f for f in leadas.fajlok if f.allapot == "kesz"]
    if not kesz_fajlok:
        raise HTTPException(status_code=400, detail="A leadáshoz legalább egy sikeresen feltöltött fájl kell.")
    b = leadas.anyagbekeres
    leadas.allapot = "leadva"
    leadas.leadva_at = szolg.most()
    szolg.esemeny(
        db,
        b.id,
        "leadas_veglegesitve",
        leadas_id=leadas.id,
        adat={"fajlok": len(kesz_fajlok), "igenyek": len(leadas.igenyek)},
    )
    # Értesítés a belső felelősnek (vagy a létrehozónak) - EGYSZER.
    cimzett = b.felelos_id or b.letrehozta_id
    if cimzett:
        notifications.create_notification(
            db,
            employee_id=cimzett,
            kind="anyagbekeres_leadas",
            message=f"Új anyagleadás érkezett: {leadas.bekuldo_nev} - {b.nev} ({len(kesz_fajlok)} fájl)",
            link=f"/media-portal/anyagbekeres/{b.id}",
        )
    db.commit()
    return {"allapot": "leadva", "leadas_id": leadas.id, "mar_leadva": False}
