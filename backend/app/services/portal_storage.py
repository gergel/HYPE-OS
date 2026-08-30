"""Cloudflare R2 (S3-kompatibilis) storage réteg a Média Portálhoz - a
Hype-repo-main (különálló client-portál projekt) storage.py 1:1 portolt
logikája, a meglévő HYPE OS R2 hitelesítő adatokkal (settings.r2_*) és
bucket-tel, de KEY_PREFIX alatt, hogy a portál fájljai (videók/képek/HLS)
elkülönüljenek a bucket egyéb (pl. diszpó PDF) tartalmától."""

from __future__ import annotations

import boto3
from botocore.config import Config

from app.core.config import settings

KEY_PREFIX = "media-portal/"

_session = boto3.session.Session()


class R2NotConfiguredError(Exception):
    """R2 hitelesítő adatok (settings.r2_*) hiányoznak - lásd a route-oldali
    kezelést (portal_admin.py), ami ezt egyértelmű 503 hibaüzenetté alakítja
    a nyers boto3/hálózati kivétel helyett."""


def is_configured() -> bool:
    return bool(
        settings.r2_account_id
        and settings.r2_access_key_id
        and settings.r2_secret_access_key
        and settings.r2_bucket_name
        and settings.r2_public_url
    )


def _client():
    if not is_configured():
        raise R2NotConfiguredError(
            "Az R2 tárhely nincs (teljesen) beállítva (hiányzó R2_ACCOUNT_ID / R2_ACCESS_KEY_ID / "
            "R2_SECRET_ACCESS_KEY / R2_BUCKET_NAME / R2_PUBLIC_URL környezeti változó) - videó/kép "
            "feltöltés emiatt nem működik."
        )
    return _session.client(
        "s3",
        endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def _key(key: str) -> str:
    return key if key.startswith(KEY_PREFIX) else f"{KEY_PREFIX}{key}"


def upload_file(local_path: str, key: str, content_type: str) -> str:
    client = _client()
    full_key = _key(key)
    client.upload_file(local_path, settings.r2_bucket_name, full_key, ExtraArgs={"ContentType": content_type})
    return public_url(key)


def upload_bytes(data: bytes, key: str, content_type: str) -> str:
    client = _client()
    client.put_object(Bucket=settings.r2_bucket_name, Key=_key(key), Body=data, ContentType=content_type)
    return public_url(key)


def delete_prefix(prefix: str) -> None:
    client = _client()
    full_prefix = _key(prefix)
    resp = client.list_objects_v2(Bucket=settings.r2_bucket_name, Prefix=full_prefix)
    objs = [{"Key": o["Key"]} for o in resp.get("Contents", [])]
    if objs:
        client.delete_objects(Bucket=settings.r2_bucket_name, Delete={"Objects": objs})


def create_multipart(key: str, content_type: str) -> str:
    client = _client()
    resp = client.create_multipart_upload(Bucket=settings.r2_bucket_name, Key=_key(key), ContentType=content_type)
    return resp["UploadId"]


def presigned_part(key: str, upload_id: str, part_number: int, expires: int = 3600) -> str:
    client = _client()
    return client.generate_presigned_url(
        "upload_part",
        Params={"Bucket": settings.r2_bucket_name, "Key": _key(key), "UploadId": upload_id, "PartNumber": part_number},
        ExpiresIn=expires,
    )


def complete_multipart(key: str, upload_id: str, parts: list) -> str:
    client = _client()
    ordered = sorted(parts, key=lambda p: p["PartNumber"])
    client.complete_multipart_upload(
        Bucket=settings.r2_bucket_name, Key=_key(key), UploadId=upload_id, MultipartUpload={"Parts": ordered}
    )
    return public_url(key)


def abort_multipart(key: str, upload_id: str) -> None:
    client = _client()
    try:
        client.abort_multipart_upload(Bucket=settings.r2_bucket_name, Key=_key(key), UploadId=upload_id)
    except Exception:
        pass


def presigned_download(key: str, filename: str, expires: int = 3600) -> str:
    """Aláírt GET URL, ami letöltésként szolgálja ki a fájlt (Content-Disposition)."""
    client = _client()
    return client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": settings.r2_bucket_name,
            "Key": _key(key),
            "ResponseContentDisposition": f'attachment; filename="{filename}"',
        },
        ExpiresIn=expires,
    )


def presigned_get(key: str, expires: int = 6 * 3600) -> str:
    """Aláírt GET URL - kell, hogy az ffmpeg (Celery worker) közvetlenül olvashassa a forrást."""
    client = _client()
    return client.generate_presigned_url(
        "get_object", Params={"Bucket": settings.r2_bucket_name, "Key": _key(key)}, ExpiresIn=expires
    )


def stream_object(key: str):
    """(chunk-iterátor, méret, content-type) - a fájl ÁTFOLYATÁSA a backenden.

    A tömeges (ZIP) letöltésnek erre van szüksége tartalékként: a böngésző a
    presigned R2 URL-eket fetch()-csel, CORS módban tölti le, ami CSAK akkor
    működik, ha a bucketen be van állítva CORS-szabály a portál originjére -
    enélkül minden fájl elbukik, és az ügyfél "a fájlok nem elérhetők" hibát
    kap. Ezen a végponton át viszont a fájl a backenden folyik keresztül
    (szerver-szerver R2 hívás, nincs CORS), amit a FastAPI CORSMiddleware-e
    ugyanúgy enged, mint bármely más API hívást - lásd
    routes/portal_public.py /file végpontjai és a frontend
    lib/portalUtils.ts fetchFileWithFallback."""
    client = _client()
    obj = client.get_object(Bucket=settings.r2_bucket_name, Key=_key(key))
    meret = int(obj.get("ContentLength") or 0)
    tipus = obj.get("ContentType") or "application/octet-stream"
    return obj["Body"].iter_chunks(1024 * 1024), meret, tipus


def head_size(key: str) -> int:
    client = _client()
    head = client.head_object(Bucket=settings.r2_bucket_name, Key=_key(key))
    return int(head.get("ContentLength") or 0)


def download_to(key: str, local_path: str) -> None:
    client = _client()
    client.download_file(settings.r2_bucket_name, _key(key), local_path)


def public_url(key: str) -> str:
    base = settings.r2_public_url.rstrip("/")
    return f"{base}/{_key(key)}"
