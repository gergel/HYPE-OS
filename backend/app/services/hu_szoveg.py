"""Magyar szöveg-összehasonlítás segédei.

Egyetlen helyen, mert több import is ugyanazt csinálta külön-külön: a Notionban
(és a Google-táblázatokban) ugyanaz a szó hol ékezettel, hol anélkül, hol
más kis/nagybetűvel szerepel - összehasonlítani csak normalizálva érdemes."""

from __future__ import annotations

import unicodedata


def ekezet_nelkul(szoveg: str) -> str:
    """Kisbetűs, ékezet nélküli, körbevágott alak: "Belsős " -> "belsos"."""
    return "".join(
        c for c in unicodedata.normalize("NFKD", (szoveg or "").lower()) if not unicodedata.combining(c)
    ).strip()
