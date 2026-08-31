"""Hosszan futó admin-műveletek (Notion import, sheet-szinkron) állapota.

Miért adatbázisban és nem a processz memóriájában: a backend TÖBB uvicorn
worker-processzel fut (lásd Dockerfile), és a "fut-e már?" zár meg a napló
memóriában workerenként KÜLÖN példány lenne - az egyik worker elindítaná az
importot, a másik a státusz-lekérdezésre azt mondaná, semmi nem fut, és egy
második indítást is átengedne. Az adatbázis-sor az egyetlen közös igazság.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class HatterFeladat(TimestampMixin, Base):
    """Egy megnevezett háttérfeladat ("notion-import", "diszpo-sheet-sync")
    aktuális/utolsó futása - fajtánként EGY sor van, az újraindítás ezt írja
    felül."""

    __tablename__ = "hatter_feladatok"

    id: Mapped[int] = mapped_column(primary_key=True)
    nev: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    running: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    #: A futás naplója, soronként \n-nel elválasztva (a felület listaként
    #: mutatja). Korlátozott hossz - lásd services/hatter_feladat.py.
    log: Mapped[str] = mapped_column(Text, nullable=False, default="")
    #: Fajtánként változó kiegészítés: az importnál a kiválasztott adatbázisok,
    #: a sheet-szinkronnál a záró összegzés.
    reszletek: Mapped[dict | None] = mapped_column(JSONB)
