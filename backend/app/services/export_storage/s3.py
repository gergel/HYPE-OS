"""S3-kompatibilis (Cloudflare R2) privát objektumtár.

Az írás **multipart upload**-dal történik: a worker soha nem tartja a teljes
archívumot memóriában, csak egyetlen, konfigurálható méretű part-puffert
(``EXPORT_S3_MULTIPART_PART_BYTES``, alapból 64 MiB) szálanként.
"""

from __future__ import annotations

import hashlib
import logging
import urllib.parse
from collections.abc import Iterator
from contextlib import contextmanager

from app.services.export_storage.base import (
    ObjectNotFound,
    StorageError,
    StoredObject,
    WriteResult,
)

logger = logging.getLogger(__name__)

#: Az S3 API minimális part-mérete (az utolsó part kivételével).
MIN_PART_BYTES = 5 * 1024 * 1024
#: Az S3 multipart upload felső korlátja.
MAX_PARTS = 10_000


def content_disposition(filename: str) -> str:
    """RFC 6266 / RFC 5987 kompatibilis fejléc-érték Unicode fájlnévhez."""
    ascii_fallback = filename.encode("ascii", "replace").decode("ascii").replace('"', "_")
    quoted = urllib.parse.quote(filename, safe="")
    return f'attachment; filename="{ascii_fallback}"; filename*=UTF-8\'\'{quoted}'


class _MultipartWriter:
    """Csak-írható, nem kereshető kimenet S3 multipart upload fölött."""

    __slots__ = (
        "_bucket",
        "_buffer",
        "_buffer_len",
        "_client",
        "_hash",
        "_key",
        "_part_bytes",
        "_parts",
        "_size",
        "_upload_id",
    )

    def __init__(self, client, bucket: str, key: str, upload_id: str, part_bytes: int) -> None:
        self._client = client
        self._bucket = bucket
        self._key = key
        self._upload_id = upload_id
        self._part_bytes = max(part_bytes, MIN_PART_BYTES)
        self._buffer: list[bytes] = []
        self._buffer_len = 0
        self._parts: list[dict] = []
        self._hash = hashlib.sha256()
        self._size = 0

    def write(self, data: bytes, /) -> int:
        if not data:
            return 0
        self._hash.update(data)
        self._size += len(data)
        self._buffer.append(bytes(data))
        self._buffer_len += len(data)
        while self._buffer_len >= self._part_bytes:
            self._flush_part(self._part_bytes)
        return len(data)

    def _flush_part(self, upto: int) -> None:
        blob = b"".join(self._buffer)
        payload, rest = blob[:upto], blob[upto:]
        self._buffer = [rest] if rest else []
        self._buffer_len = len(rest)
        self._upload(payload)

    def _upload(self, payload: bytes) -> None:
        if not payload:
            return
        part_number = len(self._parts) + 1
        if part_number > MAX_PARTS:
            raise StorageError(
                f"A multipart upload elérte a {MAX_PARTS} part korlátot; "
                "növeld az EXPORT_S3_MULTIPART_PART_BYTES értékét."
            )
        response = self._client.upload_part(
            Bucket=self._bucket, Key=self._key, UploadId=self._upload_id,
            PartNumber=part_number, Body=payload,
        )
        self._parts.append({"ETag": response["ETag"], "PartNumber": part_number})

    def finish(self) -> tuple[list[dict], int, str]:
        if self._buffer_len:
            self._upload(b"".join(self._buffer))
            self._buffer, self._buffer_len = [], 0
        return self._parts, self._size, self._hash.hexdigest()


class S3ObjectStorage:
    """``ObjectStorage`` implementáció S3/R2 fölött (boto3)."""

    supports_presigned_urls = True

    def __init__(
        self, *, bucket: str, endpoint_url: str, access_key: str, secret_key: str,
        region: str = "auto", part_bytes: int = 64 * 1024 * 1024,
    ) -> None:
        import boto3
        from botocore.config import Config

        if not bucket:
            raise StorageError("Hiányzó R2_BUCKET_NAME.")
        self.bucket = bucket
        self.part_bytes = part_bytes
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url or None,
            aws_access_key_id=access_key or None,
            aws_secret_access_key=secret_key or None,
            region_name=region,
            config=Config(signature_version="s3v4", retries={"max_attempts": 5, "mode": "standard"}),
        )

    # --- olvasás ---------------------------------------------------------

    def stat(self, key: str) -> StoredObject:
        try:
            head = self._client.head_object(Bucket=self.bucket, Key=key)
        except Exception as exc:  # botocore ClientError / 404
            if _is_not_found(exc):
                raise ObjectNotFound(key) from exc
            raise
        return StoredObject(key=key, size=int(head["ContentLength"]),
                            etag=str(head.get("ETag", "")).strip('"'))

    def exists(self, key: str) -> bool:
        try:
            self.stat(key)
        except ObjectNotFound:
            return False
        return True

    def read_stream(
        self, key: str, *, offset: int = 0, length: int | None = None,
        chunk_size: int = 8 * 1024 * 1024,
    ) -> Iterator[bytes]:
        kwargs = {"Bucket": self.bucket, "Key": key}
        if offset or length is not None:
            end = "" if length is None else str(offset + length - 1)
            kwargs["Range"] = f"bytes={offset}-{end}"
        try:
            body = self._client.get_object(**kwargs)["Body"]
        except Exception as exc:
            if _is_not_found(exc):
                raise ObjectNotFound(key) from exc
            raise
        try:
            while True:
                data = body.read(chunk_size)
                if not data:
                    return
                yield data
        finally:
            body.close()

    # --- írás ------------------------------------------------------------

    @contextmanager
    def open_write(self, key: str, *, content_type: str = "application/octet-stream"):
        upload = self._client.create_multipart_upload(
            Bucket=self.bucket, Key=key, ContentType=content_type
        )
        upload_id = upload["UploadId"]
        writer = _MultipartWriter(self._client, self.bucket, key, upload_id, self.part_bytes)
        holder = _S3WriteHolder(writer)
        try:
            yield holder
            parts, size, sha256 = writer.finish()
            if not parts:  # üres objektum: a multipart nem enged 0 partot
                self._client.abort_multipart_upload(Bucket=self.bucket, Key=key, UploadId=upload_id)
                self._client.put_object(Bucket=self.bucket, Key=key, Body=b"", ContentType=content_type)
            else:
                self._client.complete_multipart_upload(
                    Bucket=self.bucket, Key=key, UploadId=upload_id,
                    MultipartUpload={"Parts": parts},
                )
        except BaseException:
            try:
                self._client.abort_multipart_upload(Bucket=self.bucket, Key=key, UploadId=upload_id)
            except Exception:
                logger.warning("Multipart upload megszakítása sikertelen: %s", key, exc_info=True)
            raise
        stored = self.stat(key)
        holder.result = WriteResult(key=key, size=size, etag=stored.etag, sha256=sha256)

    # --- törlés ----------------------------------------------------------

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self.bucket, Key=key)

    def presigned_download_url(
        self, key: str, *, expires_in: int, filename: str | None = None,
        content_type: str = "application/zip",
    ) -> str | None:
        params = {"Bucket": self.bucket, "Key": key, "ResponseContentType": content_type}
        if filename:
            params["ResponseContentDisposition"] = content_disposition(filename)
        return self._client.generate_presigned_url(
            "get_object", Params=params, ExpiresIn=expires_in
        )


class _S3WriteHolder:
    __slots__ = ("result", "stream")

    def __init__(self, writer: _MultipartWriter) -> None:
        self.stream = writer
        self.result: WriteResult | None = None

    def write(self, data: bytes, /) -> int:
        return self.stream.write(data)


def _is_not_found(exc: Exception) -> bool:
    response = getattr(exc, "response", None)
    if not isinstance(response, dict):
        return False
    code = str(response.get("Error", {}).get("Code", ""))
    status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
    return code in {"404", "NoSuchKey", "NotFound"} or status == 404
