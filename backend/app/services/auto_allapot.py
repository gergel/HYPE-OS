"""AUTÓ ÁLLAPOTFOTÓK - képfeldolgozás, mentés, napokra bontott nézet (lásd
models/auto_allapot.py).

A képek a dokumentum-tárhelyre kerülnek (services/document_storage.py),
kitalálhatatlan névvel. Feltöltéskor a kép a helyes irányba fordul (a
telefonok EXIF-forgatása), legfeljebb 2560 px-re kicsinyül, és bélyegkép is
készül a listákhoz."""

from __future__ import annotations

import io
import logging
import secrets
from collections import defaultdict
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auto_allapot import OLDAL_KULCSOK, OLDALAK, AutoAllapotBekeres, AutoAllapotFoto
from app.services import document_storage
from app.services.hu_datum import BUDAPEST_IDOZONA

logger = logging.getLogger(__name__)

MAX_MERET = 25 * 1024 * 1024
MAX_OLDAL_PX = 2560
BELYEG_PX = 640


class FotoHiba(ValueError):
    pass


def uj_token() -> str:
    return secrets.token_urlsafe(24)


def nap(ido: datetime) -> date:
    """A fotó napja magyar idő szerint."""
    if ido.tzinfo is None:
        ido = ido.replace(tzinfo=timezone.utc)
    return ido.astimezone(BUDAPEST_IDOZONA).date()


def kep_feldolgozas(data: bytes) -> tuple[bytes, str, bytes | None]:
    """(eredeti JPEG-ben, content-type, bélyegkép vagy None). Ha a képet nem
    tudjuk megnyitni (pl. ritka formátum), változatlanul tároljuk, bélyeg
    nélkül - a fotó attól még megmarad."""
    try:
        from PIL import Image, ImageOps

        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img).convert("RGB")
        img.thumbnail((MAX_OLDAL_PX, MAX_OLDAL_PX))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85, optimize=True)
        belyeg = img.copy()
        belyeg.thumbnail((BELYEG_PX, BELYEG_PX))
        bbuf = io.BytesIO()
        belyeg.save(bbuf, format="JPEG", quality=75, optimize=True)
        return buf.getvalue(), "image/jpeg", bbuf.getvalue()
    except Exception:  # noqa: BLE001 - feldolgozás nélkül is megtartjuk a képet
        logger.warning("Autó állapotfotó: a kép nem dolgozható fel, változatlanul mentjük.")
        return data, "application/octet-stream", None


def tarolas(auto_id: int, oldal: str, data: bytes) -> dict:
    """A kép (és bélyegképe) a tárhelyre - a blokkoló rész, szálon fut."""
    eredeti, tipus, belyeg = kep_feldolgozas(data)
    azon = secrets.token_hex(12)
    kulcs = f"auto-allapot/{auto_id}/{oldal}-{azon}.jpg"
    url = document_storage.upload_bytes(eredeti, kulcs, tipus if tipus != "application/octet-stream" else "image/jpeg")
    belyeg_kulcs = belyeg_url = None
    if belyeg is not None:
        belyeg_kulcs = f"auto-allapot/{auto_id}/{oldal}-{azon}-kicsi.jpg"
        belyeg_url = document_storage.upload_bytes(belyeg, belyeg_kulcs, "image/jpeg")
    return {"kulcs": kulcs, "url": url, "belyeg_kulcs": belyeg_kulcs, "belyeg_url": belyeg_url, "meret": len(eredeti)}


def ellenoriz(oldal: str, data: bytes, content_type: str | None) -> None:
    if oldal not in OLDAL_KULCSOK:
        raise FotoHiba("Ismeretlen nézet.")
    if not data:
        raise FotoHiba("Üres fájl.")
    if len(data) > MAX_MERET:
        raise FotoHiba("A kép túl nagy (legfeljebb 25 MB).")
    if content_type and not content_type.startswith("image/"):
        raise FotoHiba("Csak képet lehet feltölteni.")


def rogzites(
    db: Session, bekeres: AutoAllapotBekeres, oldal: str, tarolt: dict, keszito: str | None, most: datetime | None = None
) -> tuple[AutoAllapotFoto, list[str]]:
    """Az új fotó sora. Ugyanarról az autóról, ugyanabból a nézetből az AZNAPI
    korábbi fotót lecseréli (az újrafotózás felülírja); a régi napokét nem.
    Visszaadja az eldobott tárhely-kulcsokat is (a hívó törli őket)."""
    most = most or datetime.now(timezone.utc)
    eldobott: list[str] = []
    for regi in db.scalars(
        select(AutoAllapotFoto).where(AutoAllapotFoto.auto_id == bekeres.auto_id, AutoAllapotFoto.oldal == oldal)
    ):
        if nap(regi.keszult_at) == nap(most):
            eldobott += [k for k in (regi.kulcs, regi.belyeg_kulcs) if k]
            db.delete(regi)
    foto = AutoAllapotFoto(
        auto_id=bekeres.auto_id, bekeres_id=bekeres.id, oldal=oldal, keszult_at=most,
        keszito=(keszito or "").strip()[:120] or None, **tarolt,
    )
    db.add(foto)
    db.flush()
    return foto, eldobott


def tarhely_takaritas(kulcsok: list[str]) -> None:
    for k in kulcsok:
        try:
            document_storage.delete_object(k)
        except Exception:  # noqa: BLE001 - árva fájl marad, a felületen már nem látszik
            logger.exception("Autó állapotfotó: a régi kép törlése sikertelen: %s", k)


def foto_kimenet(f: AutoAllapotFoto) -> dict:
    return {
        "id": f.id,
        "oldal": f.oldal,
        "keszult_at": f.keszult_at,
        "keszito": f.keszito,
        "url": f.url,
        "belyeg_url": f.belyeg_url or f.url,
    }


def oldalak() -> list[dict]:
    return [{"kulcs": k, "cimke": c} for k, c in OLDALAK]


def mai_fotok(db: Session, auto_id: int, ma: date) -> dict[str, dict]:
    eredmeny: dict[str, dict] = {}
    for f in db.scalars(
        select(AutoAllapotFoto).where(AutoAllapotFoto.auto_id == auto_id).order_by(AutoAllapotFoto.keszult_at)
    ):
        if nap(f.keszult_at) == ma:
            eredmeny[f.oldal] = foto_kimenet(f)
    return eredmeny


def napok(db: Session, auto_id: int) -> list[dict]:
    """Az autó állapota NAPRÓL NAPRA (legfrissebb elöl): melyik nap melyik
    nézetről készült kép, és mennyi van meg a hétből."""
    szerint: dict[date, dict[str, dict]] = defaultdict(dict)
    for f in db.scalars(
        select(AutoAllapotFoto).where(AutoAllapotFoto.auto_id == auto_id).order_by(AutoAllapotFoto.keszult_at)
    ):
        szerint[nap(f.keszult_at)][f.oldal] = foto_kimenet(f)
    return [
        {"datum": d.isoformat(), "fotok": fotok, "db": len(fotok), "osszes": len(OLDALAK)}
        for d, fotok in sorted(szerint.items(), reverse=True)
    ]
