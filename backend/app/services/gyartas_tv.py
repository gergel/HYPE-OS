"""GYÁRTÁS-TV — a gyártási szobában kirakott, élő áttekintő adatai.

A felhasználó kérése: egy Larától független „Gyártás" oldal, amit a gyártási
szobában egy TV-re kirakunk: a héten milyen forgatások vannak, kik dolgoznak,
ki mit vág épp, mely vágások küldhetők már ki, és hol várnak a gyártásra, hogy
válaszoljon valamire. Folyamatosan élő, a háttérben frissül.

Csak olvas. Az utómunka-állapotok szabad szövegek (az admin szerkeszti őket),
ezért — a meglévő felismerők mintájára (lásd services/vagoi_jatek.py) — a
NEVÜK dönt arról, melyik oszlopba kerül egy anyag; az admin állapotonként
felülírhatja (Utómunka → Nézet beállítása → „Gyártás-TV oszlop", lásd
models/deliverable_status.tv_csoport).
"""

from __future__ import annotations

import unicodedata
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.deliverable import Deliverable
from app.models.deliverable_status import DeliverableStatusConfig
from app.models.employee import Employee
from app.models.project import Project
from app.models.timesheet import Timesheet

IDOZONA = ZoneInfo("Europe/Budapest")
#: Az admin állapotonkénti felülírásának értékei (a „vagas" csak a régi
#: beállításokért maradt: az „Épp vágják" oszlopot a futó mérő adja).
TV_CSOPORTOK = ("vagas", "ellenorzes", "kikuldheto", "gyartasra_var", "rejtett")
LATHATO_CSOPORTOK = ("vagas", "ellenorzes", "kikuldheto", "gyartasra_var")
#: Az ennél régebben nem mozdult, határidő nélküli / régi határidejű anyag
#: nem kerül ki (a Notion-korszakból itt ragadt tételek ne töltsék meg a TV-t).
ELAVULT_NAP = 120
NAPNEVEK = ("Hétfő", "Kedd", "Szerda", "Csütörtök", "Péntek", "Szombat", "Vasárnap")


def _egyszeru(s: str | None) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", (s or "").lower()) if unicodedata.category(c) != "Mn")


#: A „Gyártásra vár" oszlop állapota (a felhasználó meghatározása).
GYARTASTOL_KERDES = "gyartastol kerdes"


def auto_csoport(allapot: str | None) -> str | None:
    """Az állapot NEVE alapján: melyik TV-oszlop (None = nem jelenik meg).

    Az „Épp vágják" oszlopot NEM az állapot adja: oda az kerül, amin épp fut
    valakinek az időmérője (lásd aktiv_vagasok)."""
    e = " ".join(_egyszeru(allapot).split())
    if not e:
        return None
    if ("kesz" in e and "kikuld" in e) or "archiv" in e or "torol" in e or "lezar" in e:
        return "rejtett"
    if e == GYARTASTOL_KERDES:
        return "gyartasra_var"
    if "kikuld" in e:
        return "kikuldheto"
    if "ellenorz" in e or "beerkez" in e:
        return "ellenorzes"
    return None


def _ember(e: Employee | None) -> dict | None:
    if e is None:
        return None
    return {"id": e.id, "nev": e.full_name, "szin": e.szin}


def _ma() -> date:
    return datetime.now(IDOZONA).date()


def _forgatas(p: Project) -> dict:
    pc = p.project_code
    return {
        "id": p.id,
        "nev": p.nev,
        "datum": p.forgatas_datuma.isoformat() if p.forgatas_datuma else None,
        "datum_vege": p.forgatas_datuma_vege.isoformat() if p.forgatas_datuma_vege else None,
        "kezdes": p.forgatas_kezdes_ido.strftime("%H:%M") if p.forgatas_kezdes_ido else None,
        "veg": p.forgatas_veg_ido.strftime("%H:%M") if p.forgatas_veg_ido else None,
        "helyszin": (p.helyszin or "").strip()[:120] or None,
        "projektkod": pc.projektkod if pc else None,
        "megrendelo": (pc.megrendelo_neve if pc else None) or None,
        "allapot": p.allapot,
        "meeting": bool(p.nem_diszponalando),
        "stab": sorted((_ember(e) for e in p.crew if e is not None), key=lambda x: x["nev"] or ""),
    }


def heti_forgatasok(db: Session, ma: date) -> tuple[date, date, list[dict]]:
    hetfo = ma - timedelta(days=ma.weekday())
    vasarnap = hetfo + timedelta(days=6)
    sorok = db.scalars(
        select(Project)
        .options(selectinload(Project.crew), selectinload(Project.project_code))
        .where(
            Project.forgatas_datuma.is_not(None),
            Project.forgatas_datuma <= vasarnap,
            or_(
                Project.forgatas_datuma >= hetfo,
                Project.forgatas_datuma_vege >= hetfo,
            ),
        )
        .order_by(Project.forgatas_datuma, Project.forgatas_kezdes_ido, Project.nev)
    ).all()
    # A több napos forgatásból leválasztott napok mellett a szülő nem kell.
    szulok = {p.feldarabolas_szulo_id for p in sorok if p.feldarabolas_szulo_id}
    napok = []
    for i in range(7):
        nap = hetfo + timedelta(days=i)
        lista = [
            _forgatas(p) for p in sorok
            if p.id not in szulok and p.forgatas_datuma <= nap <= (p.forgatas_datuma_vege or p.forgatas_datuma)
        ]
        napok.append({"datum": nap.isoformat(), "nev": NAPNEVEK[i], "ma": nap == ma, "multbeli": nap < ma,
                      "forgatasok": lista})
    return hetfo, vasarnap, napok


def aktiv_vagasok(db: Session, ma: date) -> dict[str, list[dict]]:
    konfig = {c.allapot: c for c in db.scalars(select(DeliverableStatusConfig)).all()}
    futok: dict[int, list[dict]] = {}
    fut_ota: dict[int, datetime] = {}
    for did, emp, kezdet in db.execute(
        select(Timesheet.deliverable_id, Employee, Timesheet.start_date)
        .join(Employee, Employee.id == Timesheet.employee_id)
        .where(Timesheet.deliverable_id.is_not(None), Timesheet.end_date.is_(None), Timesheet.start_date.is_not(None))
    ).all():
        futok.setdefault(did, []).append(_ember(emp))
        if did not in fut_ota or kezdet < fut_ota[did]:
            fut_ota[did] = kezdet

    hatar = datetime.now(timezone.utc) - timedelta(days=ELAVULT_NAP)
    sorok = db.scalars(
        select(Deliverable)
        .options(selectinload(Deliverable.kiosztottak), selectinload(Deliverable.vago),
                 selectinload(Deliverable.project_code))
        .where(Deliverable.allapot.is_not(None))
    ).all()
    csoportok: dict[str, list[dict]] = {c: [] for c in LATHATO_CSOPORTOK}
    for d in sorok:
        k = konfig.get(d.allapot or "")
        if d.id in futok:
            # ÉPP VÁGJÁK = amin most fut valakinek az időmérője (bármi az állapota).
            cs = "vagas"
        else:
            cs = (k.tv_csoport if k is not None and k.tv_csoport in TV_CSOPORTOK else None) or auto_csoport(d.allapot)
            if cs == "vagas":
                cs = None  # a régi „Épp vágják" beállítás: mérő nélkül nem vágják épp
        if cs not in csoportok:
            continue
        if "archivalva" in _egyszeru(d.archivalas):
            continue
        frissult = d.updated_at if d.updated_at and d.updated_at.tzinfo else (
            d.updated_at.replace(tzinfo=timezone.utc) if d.updated_at else None)
        if d.id not in futok and (frissult is None or frissult < hatar) and not (d.hatarido and d.hatarido >= ma):
            continue
        emberek = [_ember(e) for e in d.kiosztottak] or [x for x in (_ember(d.vago),) if x]
        if d.vago is not None and all(e["id"] != d.vago.id for e in emberek):
            emberek.insert(0, _ember(d.vago))
        csoportok[cs].append({
            "id": d.id,
            "projekt": d.projekt_neve,
            "projektkod": (d.project_code.projektkod if d.project_code else None) or d.projektkod_szoveg,
            "allapot": d.allapot,
            "szin": k.szin if k is not None else None,
            "emberek": emberek,
            "fut": futok.get(d.id, []),
            "fut_ota": fut_ota[d.id].isoformat() if d.id in fut_ota else None,
            "hatarido": d.hatarido.isoformat() if d.hatarido else None,
            "kesik": bool(d.hatarido and d.hatarido < ma),
            "prioritas": bool(d.prioritas),
            "leiras": (d.vagas_leiras or "").strip().replace("\n", " ")[:140] or None,
            "ota": frissult.isoformat() if frissult else None,
        })

    def _hatarido(x: dict) -> str:
        return x["hatarido"] or "9999-12-31"

    # Aki a legrégebben vágja (legkorábban indított mérő), az elöl.
    csoportok["vagas"].sort(key=lambda x: x["fut_ota"] or "")
    csoportok["ellenorzes"].sort(key=lambda x: (not x["prioritas"], _hatarido(x)))
    csoportok["kikuldheto"].sort(key=lambda x: (not x["prioritas"], _hatarido(x)))
    # Aki a legrégebben vár a gyártásra, az elöl.
    csoportok["gyartasra_var"].sort(key=lambda x: (not x["prioritas"], x["ota"] or ""))
    return csoportok


def tv_adatok(db: Session, ma: date | None = None) -> dict:
    ma = ma or _ma()
    hetfo, vasarnap, napok = heti_forgatasok(db, ma)
    vagasok = aktiv_vagasok(db, ma)
    ma_nap = next((n for n in napok if n["ma"]), None)
    ma_dolgozik: dict[int, dict] = {}
    for f in (ma_nap or {}).get("forgatasok", []):
        if f["meeting"]:
            continue
        for e in f["stab"]:
            ma_dolgozik.setdefault(e["id"], e)
    most_vag: dict[int, dict] = {}
    for v in vagasok["vagas"]:
        for e in v["fut"]:
            most_vag.setdefault(e["id"], {**e, "projekt": v["projekt"]})
    return {
        "most": datetime.now(IDOZONA).isoformat(),
        "het": {"tol": hetfo.isoformat(), "ig": vasarnap.isoformat()},
        "napok": napok,
        "ma_forgat": sorted(ma_dolgozik.values(), key=lambda e: e["nev"] or ""),
        "most_vag": sorted(most_vag.values(), key=lambda e: e["nev"] or ""),
        "vagasok": vagasok,
        "osszesito": {
            "forgatas_a_heten": len({f["id"] for n in napok for f in n["forgatasok"] if not f["meeting"]}),
            **{k: len(v) for k, v in vagasok.items()},
        },
    }
