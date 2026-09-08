"""Közös oszloptípusok."""

from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.types import TypeDecorator


class TZDateTime(TypeDecorator):
    """Mindig UTC-aware ``datetime``-et ad vissza.

    PostgreSQL-en a ``timestamptz`` eleve aware; SQLite (tesztek) naiv értéket ad,
    ezt itt UTC-nek jelöljük, hogy a lejárat/bérlet összehasonlítások mindenhol
    ugyanúgy működjenek.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


def ensure_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
