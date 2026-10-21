"""Az ANYAGBEKÉRŐ közös logikája (modellek: models/anyagbekeres.py).

Itt él minden, ami a publikus és az admin végpontok közt közös: tokenek,
állapot-szabályok, útvonal-tisztítás, kvóta, mappa-fa építés, esemény-napló,
és a háttérben készülő ZIP-export (a portál-export Zip64 primitívjeivel, de
egyszerű háttérszállal - nem függ a Celery-től)."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import secrets
import threading
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.anyagbekeres import (
    Anyagbekeres,
    AnyagEsemeny,
    AnyagFajl,
    AnyagLeadas,
    AnyagLeadasExport,
    AnyagMappa,
)
from app.services import portal_storage as storage
from app.services.zip64 import PlannedEntry, Zip64Writer, sanitize_component

log = logging.getLogger(__name__)

#: Az export ZIP-ek helye az R2-ben (a portal-exports mintájára, külön
#: prefix). A media-portal/ előtaggal kezdődik, hogy a portal_storage
#: kulcs-képzése (presigned_download, delete_prefix) NE fűzzön elé még egyet -
#: az object_store viszont nyers kulcsot ír, így a kettő ugyanoda mutat.
EXPORT_PREFIX = "media-portal/anyag-exports/"

#: Egy multipart darab mérete - a kliens is ezt használja (R2 minimum 5 MB).
RESZ_MERET = 100 * 1024 * 1024

#: Fájlonkénti felső határ, ha a bekérésen nincs szűkebb keret (produkciós
#: nyersanyagra méretezve).
MAX_FAJL_BAJT = 100 * 1024 * 1024 * 1024  # 100 GB


def uj_token() -> str:
    return secrets.token_urlsafe(24)


def most() -> datetime:
    """UTC-naiv 'most' - a modellek DateTime oszlopaihoz."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def link_lejart(bekeres: Anyagbekeres) -> bool:
    return bekeres.link_lejarat is not None and bekeres.link_lejarat < most()


def fogadokepes(bekeres: Anyagbekeres) -> bool:
    """Indítható-e ÚJ feltöltés/leadás - lezárt vagy lejárt bekérésre nem.
    A már folyamatban lévő feltöltés darabjai és a véglegesítés viszont
    lejárat után is befejezhetők (a spec kérése: érvényes anyag nem veszhet
    el pusztán a link lejárta miatt)."""
    return bekeres.allapot == "nyitott" and not link_lejart(bekeres)


def esemeny(
    db: Session,
    bekeres_id: int,
    tipus: str,
    *,
    leadas_id: int | None = None,
    adat: dict | None = None,
    employee_id: int | None = None,
) -> None:
    db.add(
        AnyagEsemeny(
            anyagbekeres_id=bekeres_id,
            leadas_id=leadas_id,
            tipus=tipus,
            adat=adat,
            employee_id=employee_id,
            created_at=most(),
        )
    )


# ── Útvonalak és nevek ───────────────────────────────────────────────────────

_TILTOTT_SZEGMENS = re.compile(r'[<>:"\\|?*\x00-\x1f]')


def tiszta_szegmens(nev: str) -> str:
    """Egy mappa- vagy fájlnév-szegmens tisztítása: se "..", se elválasztó,
    se vezérlőkarakter - a letöltött ZIP és a tároló-kulcs is ebből épül."""
    nev = _TILTOTT_SZEGMENS.sub("_", (nev or "").strip())
    if not nev or nev in (".", ".."):
        raise ValueError("Érvénytelen mappa- vagy fájlnév.")
    return nev[:255]


def tiszta_utvonal(utvonal: str) -> str:
    """Relatív mappaútvonal tisztítása ("a/b/c"). Üres = gyökér."""
    reszek = [r for r in (utvonal or "").replace("\\", "/").split("/") if r.strip()]
    if len(reszek) > 12:
        raise ValueError("Túl mély mappastruktúra (legfeljebb 12 szint).")
    return "/".join(tiszta_szegmens(r) for r in reszek)


def mappa_utvonalra(db: Session, leadas: AnyagLeadas, utvonal: str) -> AnyagMappa | None:
    """A megadott relatív útvonal mappája - a hiányzó szinteket létrehozza.
    Üres útvonalra None (gyökér)."""
    utvonal = tiszta_utvonal(utvonal)
    if not utvonal:
        return None
    szulo: AnyagMappa | None = None
    eddig = ""
    for szegmens in utvonal.split("/"):
        eddig = f"{eddig}/{szegmens}" if eddig else szegmens
        mappa = db.scalar(
            select(AnyagMappa).where(AnyagMappa.leadas_id == leadas.id, AnyagMappa.utvonal == eddig)
        )
        if mappa is None:
            mappa = AnyagMappa(
                leadas_id=leadas.id, szulo_id=szulo.id if szulo else None, nev=szegmens, utvonal=eddig
            )
            db.add(mappa)
            db.flush()
        szulo = mappa
    return szulo


def kiterjesztes_engedett(bekeres: Anyagbekeres, fajlnev: str) -> bool:
    if not (bekeres.engedett_tipusok or "").strip():
        return True
    kit = fajlnev.rsplit(".", 1)[-1].lower() if "." in fajlnev else ""
    engedett = {t.strip().lower().lstrip(".") for t in bekeres.engedett_tipusok.split(",") if t.strip()}
    return kit in engedett


def felhasznalt_bajt(db: Session, leadas_id: int) -> int:
    """A leadás összes (kész + folyamatban lévő) fájljának névleges mérete -
    a kvóta ellenőrzéséhez."""
    return int(
        db.scalar(select(func.coalesce(func.sum(AnyagFajl.meret_bajt), 0)).where(AnyagFajl.leadas_id == leadas_id))
        or 0
    )


def fajl_kulcs(bekeres_id: int, leadas_id: int, fajl_id: int, fajlnev: str) -> str:
    """Tároló-kulcs VÉLETLEN taggal - a kulcs önmagában se legyen kitalálható
    (a tároló privát, letöltés csak aláírt URL-lel megy)."""
    alap = sanitize_component(fajlnev.rsplit("/", 1)[-1])[:120] or "fajl"
    return f"anyagbekeres/{bekeres_id}/{leadas_id}/{fajl_id}-{secrets.token_hex(8)}-{alap}"


# ── Takarítás ────────────────────────────────────────────────────────────────


def felbehagyott_feltoltesek_takaritasa(db: Session, leadas: AnyagLeadas, oras_kor: int = 48) -> int:
    """A rég félbehagyott (48 órája nem mozduló) feltöltés-alatti sorok
    kitakarítása: az R2 multipart megszakítása + a sor törlése. KÉSZ fájlt
    soha nem bánt. A beküldői oldal megnyitásakor fut, olcsó."""
    hatar = most() - timedelta(hours=oras_kor)
    regiek = [
        f
        for f in leadas.fajlok
        if f.allapot == "feltoltes_alatt" and (f.updated_at or f.created_at).replace(tzinfo=None) < hatar
    ]
    for f in regiek:
        if f.upload_id:
            try:
                storage.abort_multipart(f.storage_key, f.upload_id)
            except Exception:  # noqa: BLE001 - a takarítás nem törhet
                pass
        db.delete(f)
    return len(regiek)


# ── Háttérben készülő ZIP-export ─────────────────────────────────────────────


def _export_manifest(db: Session, leadas: AnyagLeadas, mappa: AnyagMappa | None) -> list[dict]:
    """A csomag tartalma: kész fájlok, EREDETI struktúrával. Mappa megadva =
    csak az az ág."""
    fajlok = [f for f in leadas.fajlok if f.allapot == "kesz"]
    if mappa is not None:
        mappa_utak = {m.id: m.utvonal for m in leadas.mappak}
        elotag = mappa.utvonal + "/"
        fajlok = [
            f
            for f in fajlok
            if f.mappa_id is not None
            and (mappa_utak.get(f.mappa_id, "") == mappa.utvonal or mappa_utak.get(f.mappa_id, "").startswith(elotag))
        ]
    if not fajlok:
        raise ValueError("Nincs letölthető (kész) fájl ebben a körben.")
    mappa_utak = {m.id: m.utvonal for m in leadas.mappak}
    manifest = []
    foglalt: set[str] = set()
    for f in fajlok:
        konyvtar = mappa_utak.get(f.mappa_id, "") if f.mappa_id else ""
        utvonal = f"{konyvtar}/{f.eredeti_nev}" if konyvtar else f.eredeti_nev
        # Azonos nevű fájlok ugyanabban a mappában: sorszámozott név a ZIP-ben.
        alap = utvonal
        i = 2
        while utvonal in foglalt:
            nev, pont, kit = alap.rpartition(".")
            utvonal = f"{nev} ({i}){pont}{kit}" if pont else f"{alap} ({i})"
            i += 1
        foglalt.add(utvonal)
        manifest.append({"fajl_id": f.id, "key": storage._key(f.storage_key), "path": utvonal, "size": int(f.meret_bajt)})
    return manifest


def export_kerese(db: Session, leadas: AnyagLeadas, mappa: AnyagMappa | None, filename: str) -> AnyagLeadasExport:
    """Export-job létrehozása (vagy a meglévő visszaadása) + a háttérszál
    indítása - a portal_exports mintája, Celery-függés nélkül."""
    manifest = _export_manifest(db, leadas, mappa)
    fingerprint = hashlib.sha256(json.dumps([leadas.id, manifest], sort_keys=True).encode()).hexdigest()
    job = db.scalar(select(AnyagLeadasExport).where(AnyagLeadasExport.fingerprint == fingerprint))
    if job and job.state == "ready" and job.expires_at and job.expires_at <= most():
        _biztonsagos_torles(job.object_key)
        job.state = "expired"
    if job and job.state in ("failed", "expired"):
        job.state = "queued"
        job.error = None
        job.object_key = None
        job.bytes_done = 0
        job.expires_at = None
        job.touched_at = most()
        db.commit()
    if job is None:
        job = AnyagLeadasExport(
            id=str(uuid.uuid4()),
            leadas_id=leadas.id,
            fingerprint=fingerprint,
            manifest=manifest,
            filename=sanitize_component(filename or "anyagok")[:200] + ".zip",
            state="queued",
            total_bytes=sum(e["size"] for e in manifest),
            touched_at=most(),
        )
        db.add(job)
        db.commit()
    if job.state == "queued":
        inditsd_a_hattereben(job.id)
    return job


def inditsd_a_hattereben(job_id: str) -> None:
    threading.Thread(target=export_futtatasa, args=(job_id,), daemon=True).start()


def _biztonsagos_torles(key: str | None) -> None:
    if key and key.startswith(EXPORT_PREFIX):
        try:
            storage.delete_prefix(key)
        except Exception:  # noqa: BLE001
            log.exception("Anyag-export takarítás sikertelen: %s", key)


def export_futtatasa(job_id: str) -> None:
    """A ZIP megépítése háttérszálban: a forrásfájlok az R2-ből folynak át a
    Zip64Writer-en az R2-be - se böngésző-, se szerver-memóriában nem gyűlik
    össze a csomag (lásd services/zip64.py és export_storage/s3.py)."""
    from app.services.portal_exports import object_store

    key = f"{EXPORT_PREFIX}{job_id}.zip"
    with SessionLocal() as db:
        nyert = db.execute(
            update(AnyagLeadasExport)
            .where(AnyagLeadasExport.id == job_id, AnyagLeadasExport.state == "queued")
            .values(state="running", touched_at=most(), bytes_done=0)
        )
        db.commit()
        if nyert.rowcount != 1:
            return
        job = db.get(AnyagLeadasExport, job_id)
        try:
            client = storage._client()
            kesz = 0

            def darabok(entry):
                nonlocal kesz
                body = client.get_object(Bucket=settings.r2_bucket_name, Key=entry["key"])["Body"]
                try:
                    while adat := body.read(4 * 1024 * 1024):
                        kesz += len(adat)
                        yield adat
                finally:
                    body.close()

            store = object_store()
            with store.open_write(key, content_type="application/zip") as sink:
                writer = Zip64Writer(sink)
                for entry in job.manifest:
                    meret = client.head_object(Bucket=settings.r2_bucket_name, Key=entry["key"])["ContentLength"]
                    writer.add_stream(PlannedEntry(entry["path"], meret, datetime(2026, 1, 1)), darabok(entry))
                    db.execute(
                        update(AnyagLeadasExport)
                        .where(AnyagLeadasExport.id == job_id)
                        .values(bytes_done=kesz, touched_at=most())
                    )
                    db.commit()
                writer.close()
            db.execute(
                update(AnyagLeadasExport)
                .where(AnyagLeadasExport.id == job_id)
                .values(
                    state="ready",
                    object_key=key,
                    object_size=sink.result.size,
                    bytes_done=job.total_bytes,
                    touched_at=most(),
                    expires_at=most() + timedelta(hours=48),
                    error=None,
                )
            )
            db.commit()
        except Exception:  # noqa: BLE001 - a job hibája nem törheti a folyamatot
            db.rollback()
            log.exception("Anyag-export sikertelen: %s", job_id)
            _biztonsagos_torles(key)
            db.execute(
                update(AnyagLeadasExport)
                .where(AnyagLeadasExport.id == job_id)
                .values(state="failed", error="A csomag nem készült el - próbáld újra.", touched_at=most())
            )
            db.commit()


def export_allapot(job: AnyagLeadasExport) -> dict:
    return {
        "id": job.id,
        "state": job.state,
        "filename": job.filename,
        "total_bytes": job.total_bytes,
        "bytes_done": job.bytes_done,
        "file_count": len(job.manifest or []),
        "error": job.error,
        "expires_at": job.expires_at.isoformat() if job.expires_at else None,
        "url": storage.presigned_download(job.object_key, job.filename, expires=3600)
        if job.state == "ready" and job.object_key
        else None,
    }
