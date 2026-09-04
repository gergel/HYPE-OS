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
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

from app.core.config import settings

DOCS_SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
]

#: A Google Drive/Docs időnként átmeneti 500 "Internal Error"-t ad (élesben
#: is előfordult a TIG-sablon másolásánál úgy, hogy a következő próbálkozás
#: már sikerült). A googleapiclient num_retries paramétere ilyenkor
#: véletlenített exponenciális backoffal (~1-2-4-8-16 mp) automatikusan
#: újrapróbálja az 5xx-es és rate-limites válaszokat.
UJRAPROBALKOZASOK = 4


def _google_hiba_szoveg(muvelet: str, exc: HttpError) -> str:
    allapot = exc.resp.status if exc.resp is not None else None
    if allapot in (403,):
        return (
            f"A Google-fiók nem fér hozzá a fájlhoz ennél a lépésnél: {muvelet}. "
            "Ellenőrizd a sablon/mappa megosztását a beállított Google-fiókkal."
        )
    if allapot in (404,):
        return (
            f"A Google Drive nem találja a fájlt ennél a lépésnél: {muvelet}. "
            "Ellenőrizd a beállított sablon/mappa azonosítót."
        )
    return (
        f"A Google Drive/Docs hibát adott ({allapot or 'ismeretlen'}) ennél a lépésnél: "
        f"{muvelet}. Többszöri újrapróbálkozás után sem sikerült - ez jellemzően átmeneti "
        "Google-oldali hiba, próbáld újra pár perc múlva."
    )


def _futtat(request, muvelet: str):
    """Google API kérés végrehajtása újrapróbálkozással és magyar hibával.

    Ha minden próbálkozás elfogy, RuntimeError megy tovább - a küldő
    végpontok azt egységesen 503-as, olvasható hibaként adják vissza a
    beírt adatok elmentése mellett (lásd pl.
    routes/performance_certificates.py generate_and_send)."""
    try:
        return request.execute(num_retries=UJRAPROBALKOZASOK)
    except HttpError as exc:
        raise RuntimeError(_google_hiba_szoveg(muvelet, exc)) from exc


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
    # supportsAllDrives: megosztott meghajtón lévő sablon/mappa esetén is működjön.
    new_file = _futtat(
        drive.files().copy(fileId=template_file_id, body=body, supportsAllDrives=True),
        "a sablon másolása",
    )
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
        _futtat(
            docs.documents().batchUpdate(documentId=doc_id, body={"requests": requests}),
            "a sablon kitöltése",
        )


def _export_pdf_bytes(doc_id: str) -> bytes:
    drive = _google_service("drive", "v3")
    req = drive.files().export_media(fileId=doc_id, mimeType="application/pdf")
    fh = BytesIO()
    downloader = MediaIoBaseDownload(fh, req)
    done = False
    try:
        while not done:
            _status, done = downloader.next_chunk(num_retries=UJRAPROBALKOZASOK)
    except HttpError as exc:
        raise RuntimeError(_google_hiba_szoveg("a PDF exportálása", exc)) from exc
    return fh.getvalue()


def drive_fajl_letoltes(file_id: str) -> bytes:
    """Egy Drive-on tárolt fájl (pl. régebbi diszpó PDF) letöltése bájtokként
    - az R2-re költöztetéshez (lásd routes/dashboard.sajat_diszpo_pdf_url:
    a régi, csak Drive-linkes diszpók első megnyitáskor kerülnek át R2-re)."""
    drive = _google_service("drive", "v3")
    req = drive.files().get_media(fileId=file_id, supportsAllDrives=True)
    fh = BytesIO()
    downloader = MediaIoBaseDownload(fh, req)
    done = False
    try:
        while not done:
            _status, done = downloader.next_chunk(num_retries=UJRAPROBALKOZASOK)
    except HttpError as exc:
        raise RuntimeError(_google_hiba_szoveg("a PDF letöltése a Drive-ról", exc)) from exc
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
    uploaded = _futtat(
        drive.files().create(body=body, media_body=media, fields="id, webViewLink", supportsAllDrives=True),
        "a kész PDF feltöltése a Drive-ra",
    )
    return uploaded.get("webViewLink")


def pdf_feltoltes(*, filename: str, pdf_bytes: bytes, folder_id: str | None) -> str | None:
    """Egy MÁR MEGLÉVŐ PDF feltöltése a Drive-ra, a webViewLink-jével visszatérve.

    A fenti gdoc_* függvények egy menetben generálnak és töltenek fel; ez az
    azoktól független belépő azoknak a folyamatoknak, ahol a feltöltésnek
    később kell megtörténnie, mint a generálásnak - a diszpónál például csak
    AZUTÁN kerül fel a PDF, hogy a levél tényleg kiment (lásd
    services/dispo.py send_diszpo), hogy egy sikertelen küldés ne hagyjon
    maga után fájlt a mappában."""
    return _upload_pdf(filename, pdf_bytes, folder_id)


def szulo_mappa(file_id: str) -> str | None:
    """Melyik Drive mappában van ez a fájl? (az első szülő azonosítója)

    A sablon MELLÉ generálunk: a kész dokumentum és a PDF is oda kerül, ahol a
    sablon van - így nem kell külön mappát beállítani és karbantartani, és a
    kettő sosem csúszhat szét. A supportsAllDrives azért kell, hogy megosztott
    meghajtón lévő sablon esetén is működjön."""
    drive = _google_service("drive", "v3")
    adat = _futtat(
        drive.files().get(fileId=file_id, fields="parents", supportsAllDrives=True),
        "a sablon mappájának lekérdezése",
    )
    szulok = adat.get("parents") or []
    return szulok[0] if szulok else None


def _delete_file(file_id: str) -> None:
    drive = _google_service("drive", "v3")
    _futtat(drive.files().delete(fileId=file_id), "az ideiglenes dokumentum törlése")


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


def gdoc_fill_export_and_store_both(
    *,
    template_file_id: str,
    base_name: str,
    fields: dict[str, str],
    output_folder_id: str | None = None,
) -> tuple[bytes, str, str | None]:
    """Sablon kitöltése úgy, hogy MINDKÉT végeredmény a Drive-on maradjon: a
    szerkeszthető Google Docs példány ÉS a belőle exportált PDF is.

    Alapértelmezésben a SABLON SAJÁT MAPPÁJÁBA kerül mindkettő (lásd
    szulo_mappa) - az output_folder_id csak akkor írja ezt felül, ha a hívó
    kifejezetten megad egy másikat.

    A másik két változattól ez abban tér el, hogy semmit nem dob el: a
    gdoc_fill_and_export_pdf csak a Docs példányt hagyja meg (PDF-et nem tölt
    fel), a gdoc_fill_export_and_store_pdf pedig fordítva, a Doc-ot törli.

    Visszatér: (pdf_bytes, doc_id, a feltöltött PDF webViewLink-je)."""
    doc_name = (base_name or "Dokumentum").strip() or "Dokumentum"
    cel_mappa = output_folder_id or szulo_mappa(template_file_id)
    doc_id = _copy_template(template_file_id, doc_name, cel_mappa)
    _replace_placeholders(doc_id, fields)
    pdf_bytes = _export_pdf_bytes(doc_id)
    pdf_link = _upload_pdf(f"{doc_name}.pdf", pdf_bytes, cel_mappa)
    return pdf_bytes, doc_id, pdf_link


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
