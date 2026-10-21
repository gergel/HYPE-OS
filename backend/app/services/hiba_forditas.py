"""A le nem kezelt hibák ÉRTHETŐ válasza (a felhasználó jelezte: a diszpó nem
ment ki, és a projekt mezői sem mentődtek - a felületen csak annyi látszott,
hogy "Váratlan szerverhiba történt.", amiből semmi nem derült ki).

A main.py hiba-middleware-je hívja: ami itt felismerhető, az a semmitmondó
500-as helyett megmondja, MI a baj és MIT kell tenni. Csak a hiba
FAJTÁJÁT fordítjuk le - titok (token, jelszó) sosem kerül a válaszba."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

#: PostgreSQL hibakódok (SQLSTATE).
LOCK_NEM_ELERHETO = "55P03"  # lock_timeout: a sort / táblát más tartja zárolva
LEKERDEZES_MEGSZAKITVA = "57014"  # statement_timeout


@dataclass(frozen=True)
class Forditas:
    status_code: int
    detail: str


def _sqlstate(exc: BaseException) -> str | None:
    """A SQLAlchemy-be csomagolt psycopg hiba SQLSTATE kódja (ha van)."""
    orig = getattr(exc, "orig", None)
    return getattr(orig, "sqlstate", None) or getattr(exc, "sqlstate", None)


def _google_auth_hiba(exc: BaseException) -> bool:
    try:
        from google.auth.exceptions import RefreshError
    except ImportError:  # pragma: no cover - a google-auth a függőségek része
        return False
    return isinstance(exc, RefreshError)


def _google_http_hiba(exc: BaseException) -> int | None:
    try:
        from googleapiclient.errors import HttpError
    except ImportError:  # pragma: no cover
        return None
    if isinstance(exc, HttpError):
        return getattr(getattr(exc, "resp", None), "status", None) or 0
    return None


def lanc(exc: BaseException):
    """A hiba és az okai (__cause__ / __context__) - egy RuntimeError mögött
    is megtaláljuk a Google- vagy adatbázis-hibát."""
    latott: set[int] = set()
    while exc is not None and id(exc) not in latott:
        latott.add(id(exc))
        yield exc
        exc = exc.__cause__ or exc.__context__


def fordit(exc: BaseException) -> Forditas | None:
    """A felismert hibafajták érthető válasza; ismeretlen hibára None."""
    for e in lanc(exc):
        kod = _sqlstate(e)
        if kod == LOCK_NEM_ELERHETO:
            return Forditas(
                409,
                "Ezt az adatot épp egy másik, még futó művelet fogja, ezért most nem lehetett menteni. "
                "Próbáld újra fél perc múlva. Ha továbbra sem megy, szólj - a szerver naplójában "
                "látszik, mi tartja (\"Zárolt sor\" bejegyzés).",
            )
        if kod == LEKERDEZES_MEGSZAKITVA:
            return Forditas(503, "A művelet túl sokáig tartott, ezért a szerver megszakította. Próbáld újra.")
        if _google_auth_hiba(e):
            return Forditas(
                503,
                "A Google-fiók hozzáférése lejárt vagy visszavonták (ezen keresztül megy ki a levél / "
                "készül a dokumentum). A levél NEM ment ki. A Google-hozzáférést újra kell engedélyezni "
                "(a backend Gmail-tokenje) - utána a küldés újra működik.",
            )
        statusz = _google_http_hiba(e)
        if statusz is not None:
            return Forditas(
                502,
                f"A Google hibával utasította el a kérést (HTTP {statusz}), ezért a művelet nem ment végbe. "
                "Próbáld újra pár perc múlva; ha továbbra is hibázik, szólj.",
            )
    return None


def ismeretlen_uzenet(exc: BaseException) -> str:
    """A nem felismert hiba üzenete - a hiba TÍPUSÁVAL, hogy a bejelentésből
    is látszódjon, merre kell keresni (a típusnév nem tartalmaz titkot)."""
    return f"Váratlan szerverhiba történt ({type(exc).__name__})."


def zarolok_naplozasa() -> None:
    """Zárolási időtúllépéskor a naplóba írjuk, kik tartanak nyitva régóta
    tranzakciót - enélkül utólag nem derülne ki, mi fogta a sort."""
    try:
        from sqlalchemy import text

        from app.core.database import engine

        with engine.connect() as conn:
            sorok = conn.execute(
                text(
                    "SELECT pid, state, now() - xact_start AS kor, left(query, 200) AS lekerdezes "
                    "FROM pg_stat_activity "
                    "WHERE datname = current_database() AND pid <> pg_backend_pid() "
                    "AND xact_start IS NOT NULL AND now() - xact_start > interval '10 seconds' "
                    "ORDER BY xact_start LIMIT 5"
                )
            ).fetchall()
        for s in sorok:
            # A szöveges értékeket kitakarjuk: a naplóba csak a lekérdezés
            # FORMÁJA kerül (melyik tábla, melyik művelet), adat/titok nem.
            forma = re.sub(r"'[^']*'", "'…'", s.lekerdezes or "")
            logger.warning("Zárolt sor - régóta nyitott tranzakció: pid=%s állapot=%s kor=%s lekérdezés=%r",
                           s.pid, s.state, s.kor, forma)
        if not sorok:
            logger.warning("Zárolt sor - a naplózáskor már nincs régóta nyitott tranzakció.")
    except Exception:  # noqa: BLE001 - a diagnosztika nem okozhat újabb hibát
        logger.exception("Zárolt sor - a zárolók listázása nem sikerült.")
