"""Egy projektkód költségeinek TÉTELES bontása - mi mennyibe került.

A projektkód adatlapja eddig négy összeget mutatott (külsős, egyéb, vágás,
belsős), de nem lehetett megnézni, MI van bennük: melyik forgatás vitte a
pénzt, melyik anyagot meddig vágtuk, és milyen egyéb tételek terhelik. Ezekre
a kérdésekre válaszol ez a bontás.

Fontos: a számok UGYANONNAN jönnek, mint a fejlécben álló összegek (lásd
models/project_code.py) - a tételes lista összege ezért a fejléc-számot adja
ki, nem egy másik igazságot. Ahol becslés van (több projektre szóló TIG
felosztása), ott ugyanaz a szabály fut, mint az összesítésben
(services/kulsos_koltseg.py).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.employee import Employee, EmployeeType
from app.models.timesheet import Timesheet
from app.services import belsos_koltseg, deliverable_actions, kulsos_koltseg


def _osszeg(sor: Any) -> float:
    """A kiadás összege: a bruttó az irányadó, mert annyi megy ki a házból.

    Üres bruttónál a nettóra esünk vissza - a Kiadások űrlapja csak nettót
    kér, tehát a kézzel felvitt soroknál gyakran csak az van meg (ugyanaz a
    szabály, mint models/project_code._osszeg)."""
    if getattr(sor, "brutto", None):
        return float(sor.brutto)
    return float(getattr(sor, "netto", None) or 0)


def _kulsos_kiadas(e: Any) -> bool:
    """TIG-en kívüli KÜLSŐS kifizetés? Két jelről ismerjük fel: a sor
    `tipus="kulsos"` jelöléséről, vagy a hozzá kötött ember típusáról."""
    return (e.tipus or "").strip().lower() == "kulsos" or (
        e.employee is not None and e.employee.tipus == EmployeeType.KULSOS
    )


def projekt_kulsos(projekt: Any) -> float:
    """Egy FORGATÁSRA eső külsős TIG-összeg (bruttóban).

    Ugyanaz a felosztás, mint a projektkód szintjén: egy több napra szóló TIG
    összegéből csak az ide eső rész számít (lásd
    services/kulsos_koltseg._tig_resze)."""
    certek: dict[int, Any] = {}
    for cert in getattr(projekt, "performance_certificates", []) or []:
        certek[cert.id] = cert
    for tetel in getattr(projekt, "tig_tetelek", []) or []:
        if tetel.certificate is not None:
            certek[tetel.certificate.id] = tetel.certificate

    osszeg = 0.0
    for cert in certek.values():
        resz = kulsos_koltseg._tig_resze(cert, {projekt.id})
        if resz:
            osszeg += kulsos_koltseg._brutto(resz, cert.plusz_afa)
    return osszeg


def projekt_sorok(project_code: Any) -> list[dict]:
    """Forgatásonként: mibe került. Külsős stáb + belsős napidíj + vágás."""
    sorok = []
    for p in sorted(
        getattr(project_code, "projects", []) or [],
        key=lambda p: (p.forgatas_datuma or date.max, p.nev or ""),
    ):
        kulsos = projekt_kulsos(p)
        belsos = belsos_koltseg.projekt_koltsege(p)
        vagas = float(sum(d.koltseg or 0 for d in getattr(p, "deliverables", []) or []))
        sorok.append(
            {
                "id": p.id,
                "nev": p.nev,
                "forgatas_datuma": p.forgatas_datuma,
                "kulsos_koltseg": kulsos,
                "belsos_koltseg": belsos,
                "vagas_koltseg": vagas,
                "osszesen": kulsos + belsos + vagas,
            }
        )
    return sorok


def utomunka_sorok(db: Session, project_code: Any) -> list[dict]:
    """Anyagonként: mennyi ideig vágtuk és mennyibe került.

    A PERCEK a munkaidő-sorokból jönnek (Timesheet), az ÁR viszont a
    `Deliverable.koltseg`-ből: az összesítés is abból számol, tehát a két szám
    így ugyanazt mondja, mint a fejléc "Vágás" tétele."""
    anyagok = list(getattr(project_code, "deliverables", []) or [])
    # A projektkódhoz a saját anyagain FELÜL a forgatásain lógók is tartoznak.
    latott = {d.id for d in anyagok}
    for p in getattr(project_code, "projects", []) or []:
        for d in getattr(p, "deliverables", []) or []:
            if d.id not in latott:
                latott.add(d.id)
                anyagok.append(d)
    if not anyagok:
        return []

    # Egy lekérdezés az összes anyag perceire - anyagonként külön kérdezve ez
    # tucatnyi kör lenne egy nagyobb projektkódnál. A perceket ugyanaz a
    # szabály adja, mint az anyag saját oldalán (deliverable_actions.sor_percei):
    # elsődlegesen a rögzített perc, különben a két időpont különbsége - az
    # importált méréseknél sokszor csak az egyik van meg.
    percek: dict[int, float] = {}
    for sor in db.scalars(
        select(Timesheet).where(Timesheet.deliverable_id.in_([d.id for d in anyagok]))
    ):
        if sor.deliverable_id is None:
            continue
        percek[sor.deliverable_id] = percek.get(sor.deliverable_id, 0.0) + deliverable_actions.sor_percei(sor)

    vago_idk = {d.vago_employee_id for d in anyagok if d.vago_employee_id is not None}
    nevek = (
        {e.id: e.full_name for e in db.scalars(select(Employee).where(Employee.id.in_(vago_idk)))}
        if vago_idk
        else {}
    )

    return [
        {
            "id": d.id,
            "nev": d.projekt_neve,
            "project_id": d.project_id,
            "vago_nev": nevek.get(d.vago_employee_id) if d.vago_employee_id else None,
            "percek": percek.get(d.id, 0.0),
            "koltseg": float(d.koltseg or 0),
        }
        for d in sorted(anyagok, key=lambda d: (d.projekt_neve or "").lower())
    ]


def kiadas_sorok(project_code: Any) -> list[dict]:
    """A projektkód KIADÁS-SORAI tételesen, a besorolásukkal együtt.

    Kimarad belőle, ami már a TIG-eken keresztül számít: a TIG-ekből
    keletkezett Kiadás sorok ugyanazt a pénzt jelentenék még egyszer (lásd
    services/kulsos_koltseg.py).

    Ami marad, két helyre esik a fejléc bontásában, ezért mindegyik sor meg is
    mondja, melyikbe: a TIG-en kívüli külsős kifizetések a KÜLSŐS részbe, minden
    más (bérlés, utazás, kellék) az EGYÉB-be. Enélkül a lista összege nem
    stimmelne egyik fejléc-számmal sem, és az úgy nézne ki, mintha hiányozna
    valami."""
    _, tig_kiadas_idk = kulsos_koltseg.projektkod_kulsos(project_code)
    sorok = []
    for e in getattr(project_code, "expenses", []) or []:
        if e.id in tig_kiadas_idk:
            continue
        sorok.append(
            {
                "id": e.id,
                "megnevezes": e.megnevezes,
                "kinek": e.employee.full_name if e.employee is not None else None,
                "datum": e.fizetes_datuma or e.kiadas_datuma or e.fizetes_hatarideje,
                "netto": float(e.netto) if e.netto is not None else None,
                "osszeg": _osszeg(e),
                "kifizetve": bool(e.kesz),
                "resz": "kulsos" if _kulsos_kiadas(e) else "egyeb",
            }
        )
    return sorted(sorok, key=lambda s: (s["datum"] or date.max, s["megnevezes"] or ""))
