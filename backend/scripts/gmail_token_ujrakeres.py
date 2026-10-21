"""ÚJ GMAIL-TOKEN kérése, ha a régi lejárt / visszavonták (a felhasználó
kérése: a diszpó és a többi levél nem ment ki, mert lejárt a token).

A SAJÁT GÉPEDEN futtasd (böngésző kell hozzá), ne a szerveren:

    pip install google-auth-oauthlib
    python gmail_token_ujrakeres.py kliens.json

ahol a `kliens.json` a Google Cloud Console-ból letöltött OAuth-kliens
(APIs & Services -> Credentials -> az OAuth 2.0 Client ID mellett a letöltés
ikon; "Desktop app" típusú kliens kell - ha nincs ilyen, ugyanabban a
projektben hozz létre egyet).

Megnyílik a böngésző: lépj be AZZAL a Gmail-fiókkal, amelyikről a levelek
mennek (GMAIL_SENDER), és engedélyezd a hozzáférést. A szkript az új tokent az
`uj_gmail_token.json` fájlba írja - ennek a TELJES tartalmát kell a Railway-en
a backend `GMAIL_OAUTH_TOKEN_JSON` változójába másolni (ha ott a régi
`TIGTOKEN_JSON` név van használatban, akkor abba). A token TITOK: ne küldd el
senkinek, és beillesztés után töröld a fájlt.

A token egyszerre kéri a levélküldés (Gmail) és a dokumentum-generálás
(Docs/Drive) jogát, mert a rendszer a Gmail-tokent tartalékként a
dokumentumokhoz is használja - így egy tokennel mindkettő működik."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCOPES = [
    # Levélküldés + a szál/Message-Id kiolvasása (services/google_email.py).
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    # A fiókban beállított aláírás kiolvasása (szerződésmódosítás levele).
    "https://www.googleapis.com/auth/gmail.settings.basic",
    # Dokumentum-generálás: sablon másolása, kitöltése, PDF (services/gdoc_template.py).
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
]

KIMENET = Path("uj_gmail_token.json")


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("Hiányzik a csomag - telepítsd: pip install google-auth-oauthlib")
        return 1

    flow = InstalledAppFlow.from_client_secrets_file(sys.argv[1], SCOPES)
    # access_type=offline + prompt=consent: így a Google biztosan ad
    # refresh tokent (enélkül egy korábban már engedélyezett fióknál
    # kihagyhatja, és a token egy óra múlva használhatatlan lenne).
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    if not creds.refresh_token:
        print("A Google nem adott refresh tokent - futtasd újra, és a böngészőben engedélyezd a hozzáférést.")
        return 1
    KIMENET.write_text(creds.to_json())
    adat = json.loads(KIMENET.read_text())
    print(f"Kész: az új token a(z) {KIMENET.resolve()} fájlban van.")
    print(f"Engedélyezett jogok: {len(adat.get('scopes') or [])} db.")
    print("Teendő: a fájl TELJES tartalmát másold a Railway-en a backend GMAIL_OAUTH_TOKEN_JSON")
    print("(vagy ha az van használatban: TIGTOKEN_JSON) változójába, majd töröld a fájlt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
