"""Cloudflare R2 (S3-kompatibilis) storage réteg általános dokumentum-
feltöltésekhez (pl. egy munkatárs munkaszerződése) - ugyanazokat az R2
hitelesítő adatokat és bucket-et használja, mint portal_storage.py, de saját
KEY_PREFIX alatt, hogy elkülönüljön a Média Portál tartalmától."""

from __future__ import annotations

import boto3
from botocore.config import Config

from app.core.config import settings
from app.services.portal_storage import R2NotConfiguredError

KEY_PREFIX = "documents/"

_session = boto3.session.Session()


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
            "R2_SECRET_ACCESS_KEY / R2_BUCKET_NAME / R2_PUBLIC_URL környezeti változó) - fájlfeltöltés "
            "emiatt nem működik."
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


def upload_bytes(data: bytes, key: str, content_type: str) -> str:
    client = _client()
    client.put_object(Bucket=settings.r2_bucket_name, Key=_key(key), Body=data, ContentType=content_type)
    return public_url(key)


def public_url(key: str) -> str:
    base = settings.r2_public_url.rstrip("/")
    return f"{base}/{_key(key)}"
