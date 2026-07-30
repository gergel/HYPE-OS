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
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

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
    # A TIGTOKEN_JSON a különálló belsős-TIG program (csatolt belsos-TIG-main)
    # token-neve - azért fogadjuk el, hogy a HYPE OS ugyanazzal a Railway
    # beállítással működjön, amivel az a program eddig futott.
    for token_json in (
        settings.google_docs_oauth_token_json,
        settings.tigtoken_json,
        settings.gmail_oauth_token_json,
    ):
        if token_json:
            creds = _load_user_creds_from_json(token_json)
            return build(api, version, credentials=creds, cache_discovery=False)
    raise RuntimeError(
        "Nincs Google OAuth token beállítva a Docs/Drive sablon-generáláshoz. Állítsd be a "
        f"GOOGLE_DOCS_OAUTH_TOKEN_JSON (vagy TIGTOKEN_JSON) környezeti változót az alábbi "
        f"scope-okkal: {', '.join(DOCS_SCOPES)}"
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


def _upload_pdf(filename: str, pdf_bytes: bytes, folder_id: str | None) -> str | None:
    """A kész PDF-et FÁJLKÉNT tölti fel a Drive-ra, és a webViewLink-jével tér
    vissza. Az eredeti program lemezre írt (/tmp), majd onnan töltött fel -
    Railway-en a fájlrendszer efemer, ezért itt memóriából megy."""
    drive = _google_service("drive", "v3")
    body: dict = {"name": filename}
    if folder_id:
        body["parents"] = [folder_id]
    media = MediaIoBaseUpload(BytesIO(pdf_bytes), mimetype="application/pdf", resumable=False)
    uploaded = drive.files().create(body=body, media_body=media, fields="id, webViewLink").execute()
    return uploaded.get("webViewLink")


def _delete_file(file_id: str) -> None:
    drive = _google_service("drive", "v3")
    drive.files().delete(fileId=file_id).execute()


def gdoc_fill_export_and_store_pdf(
    *,
    template_file_id: str,
    base_name: str,
    fields: dict[str, str],
    output_folder_id: str | None = None,
) -> tuple[bytes, str | None]:
    """Ugyanaz, mint a gdoc_fill_and_export_pdf, de a VÉGEREDMÉNY a Drive-ra
    feltöltött PDF, és az ideiglenes Google Docs példány törlődik - a csatolt
    belsős-TIG program (belsos-TIG-main/gdocs.py) menete:

    sablon másolása -> placeholderek cseréje -> PDF export -> a PDF feltöltése
    a célmappába -> az ideiglenes Doc törlése.

    Visszatér: (pdf_bytes, a feltöltött PDF webViewLink-je). Így a rendszerben
    tárolt link egy KÉSZ PDF-re mutat, nem egy szerkeszthető dokumentumra -
    ez kerül vissza a munkatárshoz a TIG-listájába.

    A másolat szándékosan NEM a célmappába jön létre (mint az eredetiben sem):
    úgyis törlődik, a mappába a kész PDF kerül."""
    doc_name = (base_name or "Dokumentum").strip() or "Dokumentum"
    doc_id = _copy_template(template_file_id, doc_name, None)
    try:
        _replace_placeholders(doc_id, fields)
        pdf_bytes = _export_pdf_bytes(doc_id)
        link = _upload_pdf(f"{doc_name}.pdf", pdf_bytes, output_folder_id)
    finally:
        # Az ideiglenes példány akkor se maradjon a Drive-on, ha közben hiba
        # történt - a törlés hibáját elnyeljük, mert a lényeg (a PDF) már
        # megvan, és egy takarítási hiba ne bukja meg a kiküldést.
        try:
            _delete_file(doc_id)
        except Exception:  # noqa: BLE001
            pass
    return pdf_bytes, link


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
