"""Hosszan futó admin-műveletek (Notion import, sheet-szinkron) indítása és
követése - adatbázis-alapú zárral és naplóval.

Miért nem processz-memória (ahogy régen volt): több uvicorn worker fut, és a
memóriabeli zár/napló workerenként külön példány - az egyik elindítja a
feladatot, a másik viszont "nem fut semmi"-t mondana, és egy második indítást
is átengedne. Itt minden a `hatter_feladatok` táblán megy át (lásd
models/hatter_feladat.py), amit minden worker ugyanúgy lát.

A tényleges munka egy daemon-háttérszálon fut a SAJÁT adatbázis-kapcsolatával:
a HTTP-válasz azonnal visszamegy, az oldal nem várakozik rá. A szál a napló
sorait is ide, az adatbázisba írja - a státusz-végpont bármelyik workerből
ki tudja szolgálni."""

from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.hatter_feladat import HatterFeladat

#: Ennél hosszabb naplót nem tartunk meg (a legrégebbi sorok esnek ki) - a
#: felületnek a vége kell, és egy több órás import naplója enélkül megabájtokra
#: hízna az adatbázisban.
MAX_LOG_KARAKTER = 400_000


def allapot(db: Session, nev: str) -> HatterFeladat | None:
    return db.scalar(select(HatterFeladat).where(HatterFeladat.nev == nev))


def _lejart_futas(sor: HatterFeladat, elavulas: timedelta) -> bool:
    """Beragadt "running" jelző felismerése: ha a workert futás közben
    újraindították (deploy), a szál meghalt, de a sor running maradt volna
    örökre - az elavulási időn túl ezért újra lehet indítani."""
    if not sor.running or sor.started_at is None:
        return False
    kezdet = sor.started_at
    if kezdet.tzinfo is None:
        kezdet = kezdet.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - kezdet > elavulas


def inditas(
    nev: str,
    munka: Callable[[Callable[[str], None]], dict | None],
    *,
    reszletek: dict | None = None,
    elavulas: timedelta = timedelta(hours=6),
) -> bool:
    """Elindítja a megnevezett feladatot háttérszálon, ha épp nem fut.

    A `munka` egy naplózó függvényt kap (soronként hívható), és opcionálisan
    egy dict-et adhat vissza, ami a sor `reszletek` mezőjébe kerül (pl. a
    szinkron záró összegzése). Visszatérés: True = elindult, False = már fut.

    A zár-igénylés atomi: a sort FOR UPDATE-tel olvassuk, így két egyszerre
    érkező indítás közül csak az egyik jut át."""
    db = SessionLocal()
    try:
        sor = db.execute(
            select(HatterFeladat).where(HatterFeladat.nev == nev).with_for_update()
        ).scalar_one_or_none()
        if sor is None:
            sor = HatterFeladat(nev=nev)
            db.add(sor)
        elif sor.running and not _lejart_futas(sor, elavulas):
            db.rollback()
            return False
        sor.running = True
        sor.started_at = datetime.now(timezone.utc)
        sor.finished_at = None
        sor.error = None
        sor.log = ""
        sor.reszletek = reszletek
        db.commit()
    finally:
        db.close()

    def _naplo(line: str) -> None:
        # Saját, rövid életű kapcsolat naplósoronként: a munkát végző szál
        # hosszú tranzakciója ne tartsa fogva a napló-írást (és fordítva).
        ndb = SessionLocal()
        try:
            nsor = ndb.execute(
                select(HatterFeladat).where(HatterFeladat.nev == nev).with_for_update()
            ).scalar_one()
            uj = (nsor.log + line + "\n")[-MAX_LOG_KARAKTER:]
            nsor.log = uj
            ndb.commit()
        finally:
            ndb.close()

    def _futtat() -> None:
        eredmeny: dict | None = None
        hiba: str | None = None
        try:
            eredmeny = munka(_naplo)
        except Exception as exc:  # noqa: BLE001 - a felületen akarjuk látni a pontos hibát
            hiba = f"{type(exc).__name__}: {exc}"
        zdb = SessionLocal()
        try:
            zsor = zdb.execute(
                select(HatterFeladat).where(HatterFeladat.nev == nev).with_for_update()
            ).scalar_one()
            zsor.running = False
            zsor.finished_at = datetime.now(timezone.utc)
            zsor.error = hiba
            if hiba:
                zsor.log = (zsor.log + f"\nHIBA: {hiba}\n")[-MAX_LOG_KARAKTER:]
            if eredmeny is not None:
                zsor.reszletek = {**(zsor.reszletek or {}), **eredmeny}
            zdb.commit()
        finally:
            zdb.close()

    threading.Thread(target=_futtat, daemon=True).start()
    return True
