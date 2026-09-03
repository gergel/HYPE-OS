"""KÉZZEL TÖRÖLT, naptárhoz kötött projektek nyilvántartása.

A felhasználó kérése: ha egy projektet kitöröl a rendszerből, de a Google
Naptárban az esemény még létezik, a percenkénti naptár-szinkron NE hozza
vissza. A törléskor ide kerül az esemény azonosítója (lásd
routes/projects._projekt_torles_elott), és a szinkron az itt szereplő
eseményekből nem hoz létre újra projektet (lásd services/google_calendar.py).

Ha a felhasználó mégis vissza akarja hozni: a naptárban az eseményt törölni
és újra felvenni (új esemény-azonosító), vagy a projektet kézzel felvenni."""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class ToroltNaptarEsemeny(TimestampMixin, Base):
    __tablename__ = "torolt_naptar_esemenyek"

    id: Mapped[int] = mapped_column(primary_key=True)
    #: A Google Naptár esemény-azonosítója, amihez a törölt projekt tartozott.
    event_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    #: A törölt projekt neve - csak tájékoztatásul, kereséshez.
    projekt_nev: Mapped[str | None] = mapped_column(String(255))
