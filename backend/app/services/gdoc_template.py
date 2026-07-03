"""Google Docs sablon-másolás + placeholder csere + PDF export - a csatolt
'diszpo-kuldes' Railway program (app/gdoc_template.py) portolása. A diszpó és a
szerződés küldés is ezt használja, csak más sablon file ID-val és mezőkészlettel.

A HYPE OS backend Railway-en fut, ahol a helyi fájlrendszer efemer - ezért az
eredeti verzióval ellentétben (ami /mnt/data alá írta a PDF-et) itt memóriában
(bytes) adjuk vissza a PDF-et, amit közvetlenül a Gmail csatolmányba lehet tenni
lemezre írás nélkül.

Hitelesítő adat (GOOGLE_DOCS_OAUTH_TOKEN_JSON, vagy hiányában GMAIL_OAUTH_TOKEN_JSON
'drive'+'documents' scope-okkal) nélkül RuntimeError-t dob - Railway-en, valódi
env varokkal tesztelendő."""

from __future__ import annotations

import json
from io import BytesIO

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as UserCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from app.core.config import settings

DOCS_SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
]


def _load_user_creds_from_json(token_json: str) -> UserCredentials:
    data = json.loads(token_json)
    data.setdefault("token_uri", "https://oauth2.googleapis.com/token")
    creds = UserCredentials.from_authorized_user_info(data, scopes=DOCS_SCOPES)
    if not creds.valid:
        try:
            creds.refresh(Request())
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "A Google Drive/Docs scope-ok hiányoznak a tokenből. Adj meg "
                f"GOOGLE_DOCS_OAUTH_TOKEN_JSON-t az alábbi scope-okkal: {', '.join(DOCS_SCOPES)}"
            ) from exc
    return creds


def _google_service(api: str, version: str):
    if settings.google_docs_oauth_token_json:
        creds = _load_user_creds_from_json(settings.google_docs_oauth_token_json)
        return build(api, version, credentials=creds, cache_discovery=False)
    if settings.gmail_oauth_token_json:
        creds = _load_user_creds_from_json(settings.gmail_oauth_token_json)
        return build(api, version, credentials=creds, cache_discovery=False)
    raise RuntimeError(
        "Nincs Google OAuth token beállítva a Docs/Drive sablon-generáláshoz. Állítsd be a "
        f"GOOGLE_DOCS_OAUTH_TOKEN_JSON környezeti változót az alábbi scope-okkal: {', '.join(DOCS_SCOPES)}"
    )


def _copy_template(template_file_id: str, name: str, parent_folder_id: str | None) -> str:
    drive = _google_service("drive", "v3")
    body: dict = {"name": name}
    if parent_folder_id:
        body["parents"] = [parent_folder_id]
    new_file = drive.files().copy(fileId=template_file_id, body=body).execute()
    return new_file["id"]


def _replace_placeholders(doc_id: str, fields: dict[str, str]) -> None:
    docs = _google_service("docs", "v1")
    requests = []
    for key, value in (fields or {}).items():
        text_value = value or ""
        for needle in (f"{{{{{key}}}}}", f"{{{{ {key} }}}}"):
            requests.append(
                {
                    "replaceAllText": {
                        "containsText": {"text": needle, "matchCase": True},
                        "replaceText": text_value,
                    }
                }
            )
    if requests:
        docs.documents().batchUpdate(documentId=doc_id, body={"requests": requests}).execute()


def _export_pdf_bytes(doc_id: str) -> bytes:
    drive = _google_service("drive", "v3")
    req = drive.files().export_media(fileId=doc_id, mimeType="application/pdf")
    fh = BytesIO()
    downloader = MediaIoBaseDownload(fh, req)
    done = False
    while not done:
        _status, done = downloader.next_chunk()
    return fh.getvalue()


def gdoc_fill_and_export_pdf(
    *,
    template_file_id: str,
    base_name: str,
    fields: dict[str, str],
    output_folder_id: str | None = None,
) -> tuple[bytes, str]:
    """1) Sablon másolása a megadott Drive mappába, 2) {{Kulcs}} placeholderek
    cseréje, 3) PDF export. Visszatér: (pdf_bytes, new_doc_id)."""
    doc_name = (base_name or "Dokumentum").strip() or "Dokumentum"
    new_doc_id = _copy_template(template_file_id, doc_name, output_folder_id)
    _replace_placeholders(new_doc_id, fields)
    pdf_bytes = _export_pdf_bytes(new_doc_id)
    return pdf_bytes, new_doc_id
