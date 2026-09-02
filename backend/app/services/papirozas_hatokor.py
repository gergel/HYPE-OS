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


#: A papírozás (alvállalkozói szerződés, külsős TIG, utókövetés) 2026. JÚLIUS
#: elejétől megy a HYPE OS-ben (a modulok 2026-07-03..09 közt élesedtek) - az
#: ez utáni forgatások papírjait már itt intézik, tehát a kiküldött diszpójuk
#: valós papírozási jel akkor is, ha még egyetlen papírjuk sincs a rendszerben.
#:
#: Az EZELŐTTI forgatások "Kiküldve" jelölése viszont visszamenőleges
#: adatpótlás (az a9e4c72d5b18/f4b6d28a9c53 migrációk minden szept. 1. előtti
#: forgatást megjelöltek), nem papírozási jel - és utólag nem is állapítható
#: meg róluk, hogy a rendszerből mentek-e: a jelöltjeink (diszpo_kikuldve_at,
#: aki_kikuldte_a_diszpot, gmail_thread_id) mindegyikét vagy a visszamenőleges
#: időbélyeg-pótlás (f7b2d84e9a53), vagy a régi Notion-import is írta. Ezért
#: dátumhatár kell: a régi projektek csak akkor kerülnek be, ha valódi papír
#: vagy alvállalkozói kiadás köti őket. Enélkül minden régi, stábos projekt
#: "hiányzó szerződést" mutatott (300+ sor a valós 20-30 helyett).
#:
#: A határ env-változóval igazítható újratelepítés nélkül:
#:
#:     PAPIROZAS_RENDSZER_KEZDETE=2026-07-01
ALAP_RENDSZER_KEZDETE = date(2026, 7, 1)


def rendszer_kezdete() -> date:
    """Mettől számít egy forgatás a rendszer-érába (papírozás a HYPE OS-ben)."""
    nyers = os.environ.get("PAPIROZAS_RENDSZER_KEZDETE")
    if nyers:
        try:
            return date.fromisoformat(nyers.strip())
        except ValueError:
            pass
    return ALAP_RENDSZER_KEZDETE


def rendszer_diszpozott(project: Any) -> bool:
    """Python-oldali párja a diszpozott_projekt_feltetel diszpó-ágának - ott
    használjuk, ahol a projektek már be vannak töltve (lásd dashboard.py)."""
    if not (getattr(project, "diszpo", None) == "Kiküldve" or getattr(project, "diszpo_kikuldve_at", None)):
        return False
    forgatas = getattr(project, "forgatas_datuma", None)
    return forgatas is not None and forgatas >= rendszer_kezdete()


def diszpozott_projekt_feltetel():
    """SQLAlchemy-feltétel: mely projektek tartoznak a papírozási nézetekbe.

    Három jogcím, bármelyik elég:
    1. RENDSZER-ÉRA forgatás (lásd rendszer_kezdete), amin már van élet:
       kiküldött diszpó VAGY kiküldött előzetes VAGY beosztott stáb. A stáb
       azért elég önmagában, mert a szerződések a forgatás ELŐTT mennek ki -
       ha a listába csak a diszpó kiküldése után kerülne be a projekt, a
       szerződés-teendő pont akkor nem látszana, amikor esedékes (a
       felhasználó ezt hiányolta: a projekt felől megvan a teendő, a listában
       nincs). A csak-belsős stábú projekt így is "kész"-ként jelenik meg,
       mert nincs rajta papírozandó fél;
    2. MÁR VAN hozzá szerződés vagy TIG (közvetlenül vagy tételként) - a
       visszamenőleg lepapírozott munkáknak is látszaniuk kell, különben épp a
       kész áttekintés tűnne el (a felhasználó kérése);
    3. (a hívók a maguk or_-jában) valós alvállalkozói kiadás.

    Amit ez KISZŰR: a rendszer-éra előtti, papír és kiadás nélküli projektek -
    ezek csak a visszamenőleges "Kiküldve"-jelölés miatt tűntek teendőnek
    (300+ hamis "hiányzó szerződés" sor a valós 20-30 helyett).

    FONTOS: az utókövetés RÉSZLETNÉZETE (utokovetes_admin.get_utokovetes_detail)
    szándékosan szűretlen - egy projekt adatlapjáról odalépve bármelyik projekt
    papírozható. Ez a feltétel csak a LISTÁKAT és a teendő-számlálókat szűri,
    tehát a kettőnek együtt kell mozognia: ami itt kiesik, azt a listában nem
    lehet megtalálni, hiába van vele teendő."""
    from sqlalchemy import and_, exists, or_

    from app.models.contract import Contract, ContractTetel
    from app.models.performance_certificate import PerformanceCertificate, PerformanceCertificateTetel
    from app.models.project import Project

    return or_(
        and_(
            Project.forgatas_datuma >= rendszer_kezdete(),
            or_(
                # A szöveges mező VAGY a küldés kitörölhetetlen nyoma (lásd
                # models/project.diszpo_kikuldve_at) - a kiürített mező ne
                # ejtse ki a ténylegesen diszpózott projektet a papírozásból.
                Project.diszpo == "Kiküldve",
                Project.diszpo_kikuldve_at.is_not(None),
                Project.elozetes_diszpo_kuldes == "Kiküldve",
                Project.elozetes_kikuldve_at.is_not(None),
                # Beosztott stáb: a szerződés a forgatás ELŐTT esedékes, a
                # diszpónál nem várhat (lásd a docstring 1. pontját).
                Project.crew.any(),
            ),
        ),
        exists().where(Contract.project_id == Project.id),
        exists().where(ContractTetel.project_id == Project.id),
        exists().where(PerformanceCertificate.project_id == Project.id),
        exists().where(PerformanceCertificateTetel.project_id == Project.id),
    )
