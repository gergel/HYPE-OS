"""TEVÉKENYSÉGNAPLÓ - ki, mikor, mit csinált a papírozásban (lásd
models/admin_ellenorzes.py AdminTevekenyseg).

A felhasználó kérése: a tulajdonos ellenőrizhesse az adminisztrációs kolléga
munkáját. A rekordokon csak létrehozás/módosítás ideje van, felhasználó nincs
- ezért a papírozási routerek MINDEN író kérése (POST/PATCH/PUT/DELETE)
naplózódik, ha sikeres volt. Nem kell hozzá egyenként átírni a végpontokat:
egy router-szintű függőség (lásd `naplo_fuggoseg`) a végpont lefutása UTÁN,
ugyanabban az adatbázis-munkamenetben ír egy sort. Ha a végpont hibát dobott,
nem naplózunk (nem történt meg). A naplózás hibája soha nem buktatja meg a
kérést.

A leírás az ÚTVONAL-SABLONBÓL jön (pl. ".../{project_id}/{szamlazo_kulcs}/skip"
-> "Szerződés: KIHAGYVA"), a beküldött adatból csak a lényeg kerül el (a
kihagyás oka, "nincs számla" stb. - lásd ADAT_MEZOK). Az előnézetek (semmit
nem módosítanak) nem kerülnek a naplóba."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.admin_ellenorzes import AdminTevekenyseg
from app.models.employee import Employee

logger = logging.getLogger(__name__)

IRO_METODUSOK = frozenset({"POST", "PATCH", "PUT", "DELETE"})

#: Útvonal-előtag -> (tárgy kulcs, emberi név). A hosszabb előtag előbb.
TARGYAK: list[tuple[str, str, str]] = [
    ("/alvallalkozoi-szerzodesek", "szerzodes", "Alvállalkozói szerződés"),
    ("/teljesitesi-igazolasok", "tig", "Külsős TIG"),
    ("/belsos-tig", "belsos_tig", "Belsős TIG"),
    ("/kulsos-tigek", "tig", "Külsős TIG"),
    ("/expenses", "kiadas", "Kiadás"),
    ("/kp-forgalom", "kassza", "Házipénztár"),
    ("/revenues", "bevetel", "Bevétel"),
    ("/bejovo-szamlak", "bejovo_szamla", "Bejövő számla"),
    ("/megrendeloi-papirok", "megrendeloi_papir", "Megrendelői papír"),
    ("/megrendeloi-keretszerzodesek", "megrendeloi_keret", "Megrendelői keretszerződés"),
    ("/eseti-szerzodesek", "eseti_szerzodes", "Eseti szerződés"),
    ("/utalasok", "utalas", "Utalás-felvezetés"),
    ("/utokovetes", "utokovetes", "Utókövetés"),
    ("/contracts", "keretszerzodes", "Szerződés"),
]

#: (metódus vagy None, minta az útvonal VÉGÉRE, művelet kulcs, címke) -
#: sorrendben az első egyező nyer. None kulcs = nem naplózzuk.
MUVELETEK: list[tuple[str | None, str, str | None, str]] = [
    (None, r"/elonezet$", None, ""),
    ("POST", r"/(generate-and-send|generalas-es-kuldes)$", "kikuldes", "generálva és kiküldve"),
    ("POST", r"/(save|mentes)$", "mentes", "piszkozat mentve"),
    ("POST", r"/(skip|kihagyas)$", "kihagyas", "KIHAGYVA"),
    ("POST", r"/mar-van$", "mar_van", "„van már” jelölés (nem itt készült)"),
    ("POST", r"/(sajat-fajl|sajat-papir|tig-fajl)$", "sajat_fajl", "saját papír feltöltve"),
    ("POST", r"/alairt-fajl$", "alairt_feltoltes", "aláírt példány feltöltve"),
    ("DELETE", r"/(alairt-fajl|tig-fajl)$", "fajl_eldobas", "feltöltött papír ELDOBVA"),
    ("POST", r"/allapot$", "allapot", "állapot kézzel átállítva"),
    ("POST", r"/(szamla-kihagyas|nincs-szamla)$", "szamla_kihagyas", "számla KIHAGYVA"),
    ("POST", r"/(szamla-kifizetve|kifizetve|fizetes)$", "kifizetes", "kifizetettnek jelölve"),
    ("POST", r"/(szamla|fajl|feltoltes)$", "szamla_feltoltes", "számla/fájl feltöltve"),
    ("POST", r"/emlekezteto$", "emlekezteto", "emlékeztető kiküldve"),
    ("POST", r"/hatarido$", "hatarido", "határidő módosítva"),
    ("POST", r"/(jovahagyas|rogzites)$", "jovahagyas", "jóváhagyva/rögzítve"),
    ("POST", r"/visszavonas$", "visszavonas", "visszavonva"),
    ("DELETE", r".*", "torles", "TÖRÖLVE"),
    ("PATCH", r".*", "modositas", "módosítva"),
    ("PUT", r".*", "modositas", "módosítva"),
    ("POST", r"^$", "letrehozas", "felvéve"),
    ("POST", r".*", "egyeb", "művelet"),
]

#: A beküldött adatból ennyi kerül a naplóba - a lényeg, nem az egész.
ADAT_MEZOK = (
    "kihagyas_oka",
    "szamla_kihagyas_oka",
    "allapot",
    "kesz",
    "nincs_szamla",
    "kp_fedezet",
    "netto",
    "netto_osszeg",
    "brutto",
    "megnevezes",
    "fizetes_datuma",
    "kifizetes_modja",
    "tipus",
    "project_code_id",
    "employee_id",
)

#: Ezek a műveletek számítanak KIVÉTELNEK (ezeket nézi meg a tulajdonos).
KIVETEL_MUVELETEK = frozenset({"kihagyas", "mar_van", "szamla_kihagyas", "torles", "fajl_eldobas", "allapot"})


def besorolas(metodus: str, sablon: str) -> tuple[str, str, str] | None:
    """(tárgy kulcs, művelet kulcs, leírás) egy kérésre - None, ha nem
    naplózzuk (nem papírozási útvonal, vagy csak előnézet)."""
    targy = next(((k, n, p) for p, k, n in TARGYAK if sablon == p or sablon.startswith(p + "/")), None)
    if targy is None:
        return None
    targy_kulcs, targy_nev, elotag = targy
    farok = sablon[len(elotag):]
    for m, minta, kulcs, cimke in MUVELETEK:
        if m is not None and m != metodus:
            continue
        if re.search(minta, farok):
            if kulcs is None:
                return None
            if kulcs == "egyeb":
                cimke = f"művelet ({farok.strip('/') or 'új'})"
            return targy_kulcs, kulcs, f"{targy_nev}: {cimke}"
    return None


def _adat_kivonat(nyers: bytes | None) -> dict | None:
    if not nyers:
        return None
    try:
        adat = json.loads(nyers)
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(adat, dict):
        return None
    kivonat = {k: adat[k] for k in ADAT_MEZOK if k in adat}
    if isinstance(adat.get("tetelek"), list):
        kivonat["tetelek_db"] = len(adat["tetelek"])
        kivonat["projektek_db"] = len({t.get("project_id") for t in adat["tetelek"] if isinstance(t, dict)})
    return kivonat or None


def rogzit(db: Session, *, felhasznalo: Employee | None, metodus: str, sablon: str, parameterek: dict,
           nyers_adat: bytes | None = None, most: datetime | None = None) -> AdminTevekenyseg | None:
    """Egy sikeres író kérés naplózása (ha papírozási útvonal)."""
    besorolt = besorolas(metodus, sablon)
    if besorolt is None:
        return None
    targy, muvelet, leiras = besorolt
    project_id = parameterek.get("project_id")
    try:
        project_id = int(project_id) if project_id is not None else None
    except (TypeError, ValueError):
        project_id = None
    sor = AdminTevekenyseg(
        letrejott_at=most or datetime.now(timezone.utc),
        employee_id=felhasznalo.id if felhasznalo is not None else None,
        muvelet=muvelet,
        targy=targy,
        leiras=leiras[:300],
        metodus=metodus,
        utvonal=sablon[:300],
        parameterek={k: str(v) for k, v in parameterek.items()} or None,
        project_id=project_id,
        adat=_adat_kivonat(nyers_adat),
    )
    db.add(sor)
    db.commit()
    return sor


async def naplo_fuggoseg(
    request: Request,
    db: Session = Depends(get_db),
    felhasznalo: Employee = Depends(get_current_user),
):
    """Router-szintű függőség: a végpont SIKERES lefutása után naplóz.

    A végpont hibája a `yield`-nél jön vissza ide - ilyenkor nem naplózunk,
    és a hibát változatlanul továbbengedjük."""
    if request.method not in IRO_METODUSOK:
        yield
        return
    yield
    try:
        route = request.scope.get("route")
        sablon = getattr(route, "path", None) or request.url.path
        if sablon.startswith("/api/v1"):
            sablon = sablon[len("/api/v1"):]
        nyers = None
        if (request.headers.get("content-type") or "").startswith("application/json"):
            nyers = await request.body()
        rogzit(
            db,
            felhasznalo=felhasznalo,
            metodus=request.method,
            sablon=sablon,
            parameterek=dict(request.path_params),
            nyers_adat=nyers,
        )
    except Exception:  # noqa: BLE001 - a naplózás hibája nem buktathatja meg a kérést
        logger.exception("A tevékenységnapló sora nem íródott be: %s %s", request.method, request.url.path)
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
