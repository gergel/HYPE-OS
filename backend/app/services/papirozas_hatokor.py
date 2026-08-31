"""Mely projektek tartoznak egyáltalán a papírozás hatókörébe.

Van olyan projektkód, aminek a szerződéseit és teljesítési igazolásait NEM itt
vezettük - a HYPE24-es sorozat papírjai máshol készültek el, tehát a HYPE OS-nek
nincs velük teendője. Ezeket ki kell hagyni mindenhonnan, ahol a rendszer
"hiányzó papírt" számol vagy teendőt gyárt: az alvállalkozói szerződésből, a
külsős TIG-ből, az utókövetésből, a megrendelői szerződésből és TIG-ből, és az
automatikusan generált papírozás-feladatokból egyaránt.

Ha nem így lenne, minden ilyen projekt örökre "függőben" maradna: senki nem
fogja utólag felvinni a máshol elintézett papírokat, viszont a teendőlista és az
utókövetés folyamatosan hiányosnak mutatná őket - és a valódi hiányok is
elvesznének a zajban.

Ugyanide tartozik az ELMARADT esemény is: ami meg sem történt, arról nincs
mit igazolni - se a megrendelő, se a stáb felé (lásd
models/project_code.esemeny_elmaradt).

A kivett SOROZATOK szabálya ELŐTAG-alapú, mert egy sorozat minden tagját érinti (HYPE24-001,
HYPE24-002, ...), és környezeti változóval bővíthető anélkül, hogy a kódhoz
hozzá kellene nyúlni:

    PAPIROZAS_KIVETT_PROJEKTKODOK=HYPE24,HYPE23
"""

from __future__ import annotations

import os
from datetime import date
from typing import Any

#: Alapértelmezetten kivett projektkód-előtagok. A HYPE24-es sorozat papírjai a
#: HYPE OS bevezetése ELŐTT, egy másik rendszerben készültek el.
ALAP_KIVETT_ELOTAGOK: tuple[str, ...] = ("HYPE24",)


def kivett_elotagok() -> tuple[str, ...]:
    """A kivett projektkód-előtagok, nagybetűsítve az összehasonlításhoz.

    A környezeti változó TELJESEN felülírja az alapértelmezést (nem bővíti),
    hogy üres értékkel ki is lehessen kapcsolni a kizárást."""
    nyers = os.environ.get("PAPIROZAS_KIVETT_PROJEKTKODOK")
    if nyers is None:
        return ALAP_KIVETT_ELOTAGOK
    return tuple(darab.strip().upper() for darab in nyers.split(",") if darab.strip())


def projektkod_kivett(projektkod: str | None) -> bool:
    """Ki van-e véve ez a projektkód a papírozásból?"""
    if not projektkod:
        return False
    kod = projektkod.strip().upper()
    return any(kod.startswith(elotag) for elotag in kivett_elotagok())


def projekt_kivett(project: Any) -> bool:
    """Ki van-e véve ez a PROJEKT a papírozásból?

    Két helyen lehet a kód, és MINDKETTŐ elég a kizáráshoz. A kapcsolt Project
    Code a megbízható forrás, de a Notion-import azoknak a soroknak, amiknek
    nem találta meg a párját, egy gyűjtő ("ISMERETLEN-NOTION-IMPORT")
    projektkódot adott - ott egyedül a `projektkod_szoveg` szabad szöveges
    mezőben maradt meg az eredeti kód.

    Ennek az az ára, hogy egy ellentmondásos sor (HYPE25-ös Project Code-hoz
    kapcsolva, de HYPE24-es szöveges kóddal) is kimarad. Ez tudatos csere: a
    téves kizárás egy sort rejt el, amit a szöveges kód javításával azonnal
    vissza lehet hozni, a téves BENNTARTÁS viszont örökre "hiányzó papírt"
    mutatna egy olyan projekten, amivel nincs teendő."""
    project_code = getattr(project, "project_code", None)
    if project_code is not None:
        if projektkod_kivett(getattr(project_code, "projektkod", None)):
            return True
        # ELMARADT esemény: a forgatás meg sem történt, tehát a stábbal sincs
        # mit szerződni és mit igazolni (lásd
        # models/project_code.esemeny_elmaradt). Enélkül egy lemondott, de
        # diszpózott forgatás örökre hiányzó papírokat mutatna.
        if getattr(project_code, "elmaradt", False):
            return True
    return projektkod_kivett(getattr(project, "projektkod_szoveg", None))


def papirozando_projektek(projektek: list[Any]) -> list[Any]:
    """A lista a kivett projektek nélkül - ezt hívja minden olyan végpont, ami
    hiányzó papírt keres."""
    return [p for p in projektek if not projekt_kivett(p)]


#: 2026. szeptember 1-től megy a diszpó a HYPE OS-ből. Az EZELŐTTI forgatások
#: "Kiküldve" jelölése visszamenőleges adatpótlás (lásd az
#: a9e4c72d5b18/f4b6d28a9c53 migrációkat), nem valós papírozási jel - az
#: utókövetés diszpó-ága ezért csak a rendszer-éra forgatásait nézi. A régi
#: projektek továbbra is bekerülnek, ha valódi alvállalkozói kiadás köti őket
#: (az a commitment maga). Enélkül a visszamenőleges jelölés után minden régi,
#: stábos projekt "hiányzó szerződést" mutatott (300+ sor a valós 20-30
#: helyett)."""
RENDSZER_DISZPO_KEZDETE = date(2026, 9, 1)


def diszpozott_projekt_feltetel():
    """SQLAlchemy-feltétel: a papírozásba a DISZPÓ jogán csak a rendszer-éra
    (szept. 1-től) forgatásai kerülnek be."""
    from sqlalchemy import and_

    from app.models.project import Project

    return and_(Project.diszpo == "Kiküldve", Project.forgatas_datuma >= RENDSZER_DISZPO_KEZDETE)
