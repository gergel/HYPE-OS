"""ADMINISZTRÁCIÓ ELLENŐRZÉSE - a tulajdonos ellenőrző oldalának adatai.

A felhasználó kérése (2026-10): követhesse, mikor mi készült el, mindenhez
rendesen van-e papír, és nincs-e csendben kihagyva semmi - az előző
kollégánál így elcsúsztak dolgok. Négy nézet:

1. NAPLÓ: ki, mikor, mit (services/tevekenyseg_naplo.py tölti).
2. KIVÉTELEK: minden kihagyás, "van már szerződés", számla-kihagyás, "sosem
   lesz számlája" jelölés, törlés és kézi állapot-átállítás egy helyen - az
   indokkal, ki/mikor adattal; a tulajdonos "rendben"-re teheti vagy
   visszadobhatja (visszadobásnál feladat megy a figyelt kollégának).
3. LEJÁRT HIÁNYOK: a beállított határidőknél régebben hiányzó papírok.
4. HETI ÖSSZESÍTŐ: mennyi készült el / maradt nyitva hétről hétre.

KEZDŐNAP (a felhasználó kérése): az egész ellenőrzés csak a beállított
naptól (alapból 2026.10.05. - a figyelt kolléga ekkor kezdett) nézi a
dolgokat: a napló, a kivételek, a heti összesítő és Lara is csak az azóta
történteket, a lejárt hiányok csak az azóta lezajlott forgatásokat.

Minden csak OLVAS, kivéve a tulajdonos saját jelölését (és az abból
keletkező feladatot)."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.admin_ellenorzes import (
    ALAP_HATARIDOK,
    ALAP_KEZDET,
    AdminEllenorzesBeallitas,
    AdminKivetelJeloles,
    AdminTevekenyseg,
    LaraFigyelesJelzes,
)
from app.models.contract import Contract, ContractType
from app.models.employee import Employee
from app.models.finance import Expense
from app.models.internal_performance_certificate import KIHAGYVA as BELSOS_KIHAGYVA
from app.models.internal_performance_certificate import InternalPerformanceCertificate
from app.models.megrendeloi_papir import MegrendeloiSzerzodes, MegrendeloiTig
from app.models.performance_certificate import PerformanceCertificate
from app.models.task import Task
from app.services import szerzodes_emlekezteto
from app.services.hu_datum import BUDAPEST_IDOZONA

PAGE = "/admin-ellenorzes"
KIHAGYVA = "Kihagyva"
MAR_VAN = "Van már szerződés"

#: A naplóból a heti összesítő csoportjai.
HETI_CSOPORTOK = {
    "kikuldes": "Kiküldött papír",
    "sajat_fajl": "Feltöltött saját papír",
    "alairt_feltoltes": "Aláírt példány megjött",
    "szamla_feltoltes": "Számla feltöltve",
    "kifizetes": "Kifizetve jelölés",
    "kivetel": "Kihagyás / kivétel",
    "torles": "Törlés",
}


def _most() -> datetime:
    return datetime.now(timezone.utc)


# ── Beállítások ─────────────────────────────────────────────────────────────


def beallitas(db: Session) -> AdminEllenorzesBeallitas:
    """Az egyetlen beállítás-sor (id=1); ha még nincs, alapértékekkel jön létre."""
    b = db.get(AdminEllenorzesBeallitas, 1)
    if b is None:
        b = AdminEllenorzesBeallitas(id=1, lara_figyeles=False, hataridok=dict(ALAP_HATARIDOK))
        db.add(b)
        db.flush()
    return b


def hataridok(b: AdminEllenorzesBeallitas) -> dict[str, int]:
    meglevo = b.hataridok or {}
    return {k: int(meglevo.get(k, v)) for k, v in ALAP_HATARIDOK.items()}


def kezdet(b: AdminEllenorzesBeallitas | None) -> date:
    """Ettől a naptól nézi az ellenőrzés a dolgokat (a figyelt kolléga kezdete)."""
    return (b.figyeles_kezdete if b is not None else None) or ALAP_KEZDET


def kezdet_idopont(nap: date) -> datetime:
    """A kezdőnap 0:00 budapesti idő szerint (az időbélyegek szűréséhez)."""
    return datetime.combine(nap, datetime.min.time(), tzinfo=BUDAPEST_IDOZONA)


def _hatar(napok: int | None, tol: date | None) -> datetime | None:
    """Az "utolsó N nap" és a kezdőnap közül a későbbi."""
    jeloltek = []
    if napok:
        jeloltek.append(_most() - timedelta(days=napok))
    if tol is not None:
        jeloltek.append(kezdet_idopont(tol))
    return max(jeloltek) if jeloltek else None


# ── Napló ───────────────────────────────────────────────────────────────────


def _nevek(db: Session, idk: set[int]) -> dict[int, str]:
    idk = {i for i in idk if i is not None}
    if not idk:
        return {}
    return {e.id: e.full_name for e in db.scalars(select(Employee).where(Employee.id.in_(idk)))}


def naplo(
    db: Session, *, napok: int | None = 14, employee_id: int | None = None, csak_kivetel: bool = False,
    limit: int = 500, tol: date | None = None,
) -> list[dict]:
    from app.services.tevekenyseg_naplo import KIVETEL_MUVELETEK

    q = select(AdminTevekenyseg)
    hatar = _hatar(napok, tol)
    if hatar is not None:
        q = q.where(AdminTevekenyseg.letrejott_at >= hatar)
    if employee_id is not None:
        q = q.where(AdminTevekenyseg.employee_id == employee_id)
    if csak_kivetel:
        q = q.where(AdminTevekenyseg.muvelet.in_(KIVETEL_MUVELETEK))
    sorok = db.scalars(q.order_by(AdminTevekenyseg.letrejott_at.desc()).limit(limit)).all()
    nevek = _nevek(db, {s.employee_id for s in sorok})
    return [
        {
            "id": s.id,
            "letrejott_at": s.letrejott_at,
            "employee_id": s.employee_id,
            "ki": nevek.get(s.employee_id, "–"),
            "muvelet": s.muvelet,
            "targy": s.targy,
            "leiras": s.leiras,
            "kivetel": s.muvelet in KIVETEL_MUVELETEK,
            "project_id": s.project_id,
            "parameterek": s.parameterek or {},
            "adat": s.adat or {},
            "link": _naplo_link(s),
        }
        for s in sorok
    ]


def _naplo_link(s: AdminTevekenyseg) -> str | None:
    p = s.parameterek or {}
    if s.targy in ("szerzodes", "tig", "utokovetes") and p.get("project_id"):
        return f"/utokovetes/{p['project_id']}"
    if s.targy in ("szerzodes", "tig") and p.get("project_code_id"):
        return f"/utokovetes/projektkodok/{p['project_code_id']}"
    if s.targy == "kiadas" and p.get("item_id"):
        return f"/penzugyek/kiadas/{p['item_id']}"
    if s.targy == "belsos_tig":
        return "/belsos-tig"
    return None


# ── Kivételek ───────────────────────────────────────────────────────────────


def _ki_mikor(db: Session, targy: str, muveletek: tuple[str, ...], project_ids: set[int], kulcs: str | None) -> dict:
    """Ki és mikor tette - a naplóból (a napló bevezetése előttieknél üres)."""
    q = select(AdminTevekenyseg).where(AdminTevekenyseg.targy == targy, AdminTevekenyseg.muvelet.in_(muveletek))
    if project_ids:
        q = q.where(AdminTevekenyseg.project_id.in_(project_ids))
    for s in db.scalars(q.order_by(AdminTevekenyseg.letrejott_at.desc()).limit(20)):
        if kulcs and (s.parameterek or {}).get("szamlazo_kulcs") not in (kulcs, kulcs.lstrip("e")):
            continue
        return {"ki_id": s.employee_id, "mikor": s.letrejott_at}
    return {"ki_id": None, "mikor": None}


def _szerzodes_projektek(c: Contract) -> set[int]:
    return {t.project_id for t in c.tetelek} or ({c.project_id} if c.project_id else set())


def _szerzodes_link(c: Contract) -> str | None:
    pids = sorted(_szerzodes_projektek(c))
    if pids:
        return f"/utokovetes/{pids[0]}"
    if c.project_code_id:
        return f"/utokovetes/projektkodok/{c.project_code_id}"
    return None


def _fel_neve(papir) -> str:
    if getattr(papir, "vallalkozas", None) is not None:
        return papir.vallalkozas.nev
    if getattr(papir, "employee", None) is not None:
        return papir.employee.full_name
    return getattr(papir, "ceg_neve", None) or "–"


def _projekt_cimke(papir) -> str:
    p = getattr(papir, "project", None)
    if p is not None:
        return " · ".join(x for x in (p.projektkod_szoveg, p.nev, p.forgatas_datuma.isoformat() if p.forgatas_datuma else None) if x)
    pk = getattr(papir, "project_code", None)
    return pk.projektkod if pk is not None else "–"


def kivetelek(
    db: Session, *, napok: int | None = 90, csak_nyitott: bool = False, tol: date | None = None
) -> list[dict]:
    """Minden kivétel (kihagyás és társai) a tulajdonos döntésével együtt -
    a `tol` kezdőnap előtt módosítottak nélkül."""
    hatar = _hatar(napok, tol)
    sorok: list[dict] = []

    def frissebb(oszlop):
        return oszlop >= hatar if hatar is not None else True

    # 1-2. Alvállalkozói (eseti) szerződés: kihagyva / "van már szerződés".
    for c in db.scalars(
        select(Contract)
        .options(selectinload(Contract.tetelek), selectinload(Contract.employee), selectinload(Contract.vallalkozas),
                 selectinload(Contract.project), selectinload(Contract.project_code))
        .where(
            Contract.tipus == ContractType.ALVALLALKOZOI,
            Contract.keretszerzodes.is_(False),
            Contract.szerzodes_allapota.in_([KIHAGYVA, MAR_VAN]),
            frissebb(Contract.updated_at),
        )
    ):
        kihagyva = c.szerzodes_allapota == KIHAGYVA
        kulcs = f"v{c.vallalkozas_id}" if c.vallalkozas_id else f"e{c.employee_id}"
        figyelmeztetes = None
        if not kihagyva and not (c.szerzodes_file_url or c.alairt_file_url):
            figyelmeztetes = "Nincs hozzá feltöltött papír."
        sorok.append({
            "kulcs": f"szerzodes_{'kihagyva' if kihagyva else 'mar_van'}:{c.id}",
            "tipus": "Szerződés kihagyva" if kihagyva else "„Van már szerződése” (nem itt készült)",
            "fel": _fel_neve(c),
            "projekt": _projekt_cimke(c),
            "projektek_db": len(_szerzodes_projektek(c)),
            "indok": c.kihagyas_oka,
            "figyelmeztetes": figyelmeztetes,
            "osszeg": float(c.netto_osszeg) if c.netto_osszeg is not None else None,
            "link": _szerzodes_link(c),
            "modositva_at": c.updated_at,
            **_ki_mikor(db, "szerzodes", ("kihagyas",) if kihagyva else ("mar_van",), _szerzodes_projektek(c), kulcs),
        })

    # 3-4. Külsős TIG: kihagyva / számla kihagyva.
    for t in db.scalars(
        select(PerformanceCertificate)
        .options(selectinload(PerformanceCertificate.employee), selectinload(PerformanceCertificate.vallalkozas),
                 selectinload(PerformanceCertificate.project), selectinload(PerformanceCertificate.project_code))
        .where(
            or_(PerformanceCertificate.allapot == KIHAGYVA, PerformanceCertificate.szamla_kihagyva.is_(True)),
            frissebb(PerformanceCertificate.updated_at),
        )
    ):
        kulcs = f"v{t.vallalkozas_id}" if t.vallalkozas_id else f"e{t.employee_id}"
        link = f"/utokovetes/{t.project_id}" if t.project_id else (
            f"/utokovetes/projektkodok/{t.project_code_id}" if t.project_code_id else None)
        alap = {"fel": _fel_neve(t), "projekt": _projekt_cimke(t), "projektek_db": 1, "link": link,
                "modositva_at": t.updated_at,
                "osszeg": float(t.netto_osszeg) if t.netto_osszeg is not None else None, "figyelmeztetes": None}
        pids = {t.project_id} if t.project_id else set()
        if t.allapot == KIHAGYVA:
            sorok.append({**alap, "kulcs": f"tig_kihagyva:{t.id}", "tipus": "Külsős TIG kihagyva",
                          "indok": t.kihagyas_oka, **_ki_mikor(db, "tig", ("kihagyas",), pids, kulcs)})
        if t.szamla_kihagyva:
            sorok.append({**alap, "kulcs": f"tig_szamla_kihagyva:{t.id}", "tipus": "Számla kihagyva (külsős TIG)",
                          "indok": t.szamla_kihagyas_oka, **_ki_mikor(db, "tig", ("szamla_kihagyas",), pids, kulcs)})

    # 5. Belsős TIG kihagyva.
    for b in db.scalars(
        select(InternalPerformanceCertificate)
        .options(selectinload(InternalPerformanceCertificate.employee))
        .where(InternalPerformanceCertificate.allapot == BELSOS_KIHAGYVA, frissebb(InternalPerformanceCertificate.updated_at))
    ):
        sorok.append({
            "kulcs": f"belsos_tig_kihagyva:{b.id}", "tipus": "Belsős TIG kihagyva",
            "fel": b.employee.full_name if b.employee else "–", "projekt": f"{b.ev}. {b.honap:02d}. hónap",
            "projektek_db": 0, "indok": b.megjegyzes, "figyelmeztetes": None,
            "osszeg": float(b.netto_osszeg) if b.netto_osszeg is not None else None,
            "link": "/belsos-tig", "modositva_at": b.updated_at, **_ki_mikor(db, "belsos_tig", ("kihagyas",), set(), None),
        })

    # 6. Kiadás: "sosem lesz számlája".
    for e in db.scalars(
        select(Expense).where(Expense.nincs_szamla.is_(True), frissebb(Expense.updated_at))
    ):
        sorok.append({
            "kulcs": f"kiadas_nincs_szamla:{e.id}", "tipus": "Kiadás – sosem lesz számlája",
            "fel": e.megnevezes or "–", "projekt": e.kiadas_leiras or "–", "projektek_db": 0, "indok": None,
            "figyelmeztetes": None, "osszeg": float(e.brutto or e.netto or 0) or None,
            "link": f"/penzugyek/kiadas/{e.id}", "modositva_at": e.updated_at,
            **_kiadas_ki_mikor(db, e.id),
        })

    # 7. Megrendelői szerződés / TIG kihagyva.
    for modell, nev in ((MegrendeloiSzerzodes, "Megrendelői szerződés kihagyva"), (MegrendeloiTig, "Megrendelői TIG kihagyva")):
        for m in db.scalars(select(modell).where(modell.allapot == KIHAGYVA, frissebb(modell.updated_at))):
            sorok.append({
                "kulcs": f"{modell.__tablename__}_kihagyva:{m.id}", "tipus": nev, "fel": "Megrendelő",
                "projekt": m.project_code.projektkod if getattr(m, "project_code", None) else "–", "projektek_db": 0,
                "indok": m.kihagyas_oka, "figyelmeztetes": None, "osszeg": None,
                "link": f"/projektek/project-kodok/{m.project_code_id}", "modositva_at": m.updated_at,
                **_ki_mikor(db, "megrendeloi_papir", ("kihagyas",), set(), None),
            })

    # 8-9. Ami már nincs meg (törlés, eldobott papír) vagy kézzel lett átállítva - a naplóból.
    for s in naplo(db, napok=napok, csak_kivetel=True, limit=1000, tol=tol):
        if s["muvelet"] not in ("torles", "fajl_eldobas", "allapot"):
            continue
        sorok.append({
            "kulcs": f"naplo:{s['id']}", "tipus": s["leiras"], "fel": "–",
            "projekt": f"#{s['project_id']}" if s["project_id"] else "–", "projektek_db": 0,
            "indok": (s["adat"] or {}).get("allapot") and f"Új állapot: {s['adat']['allapot']}",
            "figyelmeztetes": None, "osszeg": None, "link": s["link"], "modositva_at": s["letrejott_at"],
            "ki_id": s["employee_id"], "mikor": s["letrejott_at"],
        })

    # A tulajdonos döntései (a legutolsó számít).
    dontesek: dict[str, AdminKivetelJeloles] = {}
    for j in db.scalars(select(AdminKivetelJeloles).order_by(AdminKivetelJeloles.letrejott_at)):
        dontesek[j.kulcs] = j
    nevek = _nevek(db, {s.get("ki_id") for s in sorok})
    for s in sorok:
        s["ki"] = nevek.get(s.get("ki_id")) if s.get("ki_id") else None
        d = dontesek.get(s["kulcs"])
        s["dontes"] = d.dontes if d else None
        s["dontes_megjegyzes"] = d.megjegyzes if d else None
        s["dontes_at"] = d.letrejott_at if d else None
    if csak_nyitott:
        sorok = [s for s in sorok if s["dontes"] is None]
    # Át nem nézett elöl, azon belül a legfrissebb.
    sorok.sort(key=lambda s: (s["dontes"] is not None, -(s.get("mikor") or s.get("modositva_at") or datetime.min.replace(tzinfo=timezone.utc)).timestamp()))
    return sorok


def _kiadas_ki_mikor(db: Session, expense_id: int) -> dict:
    for s in db.scalars(
        select(AdminTevekenyseg)
        .where(AdminTevekenyseg.targy == "kiadas")
        .order_by(AdminTevekenyseg.letrejott_at.desc())
        .limit(200)
    ):
        if str((s.parameterek or {}).get("item_id")) == str(expense_id) and (s.adat or {}).get("nincs_szamla"):
            return {"ki_id": s.employee_id, "mikor": s.letrejott_at}
    return {"ki_id": None, "mikor": None}


def jeloles(
    db: Session, *, kulcs: str, dontes: str, megjegyzes: str | None, felhasznalo: Employee, feladat: bool = False,
    cim: str | None = None, link: str | None = None,
) -> AdminKivetelJeloles:
    """A tulajdonos döntése egy kivételről. Visszadobásnál (ha kérik) feladat
    megy a figyelt kollégának - ez az EGYETLEN, ami a kollégához eljut, és csak
    a tulajdonos gombnyomására."""
    if dontes not in ("rendben", "visszadobva"):
        raise ValueError("A döntés 'rendben' vagy 'visszadobva' lehet.")
    j = AdminKivetelJeloles(kulcs=kulcs, dontes=dontes, megjegyzes=(megjegyzes or "").strip() or None,
                            employee_id=felhasznalo.id)
    if dontes == "visszadobva" and feladat:
        b = beallitas(db)
        felelos = db.get(Employee, b.figyelt_employee_id) if b.figyelt_employee_id else None
        if felelos is None:
            raise ValueError("Nincs beállítva figyelt kolléga - kinek menjen a feladat?")
        t = Task(
            feladat=f"Ellenőrzés: nézd át újra – {cim or kulcs}"[:500],
            kategoria="Adminisztráció ellenőrzése",
            hatarido=date.today() + timedelta(days=2),
            leiras=(f"{(megjegyzes or '').strip()}\n\n{link or ''}".strip())[:2000] or None,
            felelosok=[felelos],
        )
        db.add(t)
        db.flush()
        j.task_id = t.id
    db.add(j)
    db.commit()
    return j


# ── Lejárt hiányok ──────────────────────────────────────────────────────────


def lejart_hianyok(
    db: Session, *, ma: date | None = None, hatarido: dict[str, int] | None = None, tol: date | None = None
) -> list[dict]:
    """A beállított határidőnél régebben hiányzó papírok (a lezajlott
    forgatások alvállalkozói szerződése, TIG-je, számlája, és a vissza nem
    érkezett aláírt szerződés). A `tol` kezdőnap előtt lezajlott forgatások
    nem számítanak (azok még nem a figyelt kolléga idejére esnek)."""
    from app.services import utokovetes_hianyok

    ma = ma or date.today()
    hatarido = hatarido or dict(ALAP_HATARIDOK)
    m = utokovetes_hianyok.matrix(db, ma=ma, napok=365, csak_hianyos=True)
    szerzodes_idk = {
        r["dokumentumok"]["szerzodes"].get("szerzodes_id")
        for r in m["sorok"]
        if r["dokumentumok"]["szerzodes"]["allapot"] == "alairasra_var"
    } - {None}
    szerzodesek = {c.id: c for c in db.scalars(select(Contract).where(Contract.id.in_(szerzodes_idk)))} if szerzodes_idk else {}

    eredmeny: list[dict] = []
    for r in m["sorok"]:
        napja = r.get("lezajlott_napja")
        if tol is not None and napja is not None and ma - timedelta(days=napja) < tol:
            continue
        for dok in r["hianyzo"]:
            allapot = r["dokumentumok"][dok]["allapot"]
            if dok == "szerzodes" and allapot == "alairasra_var":
                c = szerzodesek.get(r["dokumentumok"]["szerzodes"].get("szerzodes_id"))
                eltelt = szerzodes_emlekezteto.napja(c) if c is not None else None
                tipus, hatar = "alairas", hatarido["alairas"]
            else:
                eltelt, tipus, hatar = napja, dok, hatarido[dok]
            if eltelt is None or eltelt <= hatar:
                continue
            eredmeny.append({
                "kulcs": f"{r['project_id']}:{r['szamlazo_kulcs']}:{tipus}",
                "project_id": r["project_id"],
                "projekt": " · ".join(x for x in (r.get("projektkod"), r.get("project_nev")) if x),
                "forgatas_datuma": r.get("forgatas_datuma"),
                "fel": r.get("szamlazo_nev"),
                "dokumentum": {"szerzodes": "Szerződés", "tig": "TIG", "szamla": "Számla", "alairas": "Aláírt szerződés"}[tipus],
                "tipus": tipus,
                "allapot": r["dokumentumok"][dok]["cimke"],
                "eltelt_nap": eltelt,
                "hatarido_nap": hatar,
                "keses_nap": eltelt - hatar,
                "link": f"/utokovetes/{r['project_id']}",
            })
    eredmeny.sort(key=lambda x: -x["keses_nap"])
    return eredmeny


# ── Heti összesítő ──────────────────────────────────────────────────────────


def _het_kezdete(d: date) -> date:
    return d - timedelta(days=d.weekday())


def heti_osszesito(
    db: Session, *, hetek: int = 8, figyelt_id: int | None = None, ma: date | None = None, kezdonap: date | None = None
) -> dict:
    """Hétről hétre a napló számai - a kezdőnap hetétől (előtte nincs mit nézni)."""
    from app.services.tevekenyseg_naplo import KIVETEL_MUVELETEK

    ma = ma or date.today()
    elso = _het_kezdete(ma) - timedelta(weeks=hetek - 1)
    if kezdonap is not None and _het_kezdete(kezdonap) > elso:
        elso = min(_het_kezdete(kezdonap), _het_kezdete(ma))
        hetek = (_het_kezdete(ma) - elso).days // 7 + 1
    tol = kezdet_idopont(max(elso, kezdonap)) if kezdonap else datetime.combine(elso, datetime.min.time(), tzinfo=timezone.utc)
    szamlalo: dict[date, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    figyelt: dict[date, int] = defaultdict(int)
    for s in db.scalars(select(AdminTevekenyseg).where(AdminTevekenyseg.letrejott_at >= tol)):
        het = _het_kezdete(s.letrejott_at.astimezone(BUDAPEST_IDOZONA).date())
        if s.muvelet in HETI_CSOPORTOK:
            csoport = s.muvelet
        elif s.muvelet in ("fajl_eldobas",):
            csoport = "torles"
        elif s.muvelet in KIVETEL_MUVELETEK:
            csoport = "kivetel"
        else:
            csoport = "egyeb"
        szamlalo[het][csoport] += 1
        szamlalo[het]["osszes"] += 1
        if figyelt_id is not None and s.employee_id == figyelt_id:
            figyelt[het] += 1
    het_sorok = []
    for i in range(hetek):
        het = elso + timedelta(weeks=i)
        sz = szamlalo.get(het, {})
        het_sorok.append({
            "het_kezdete": het.isoformat(),
            "osszes": sz.get("osszes", 0),
            "figyelt": figyelt.get(het, 0),
            **{k: sz.get(k, 0) for k in (*HETI_CSOPORTOK, "egyeb")},
        })
    return {"hetek": list(reversed(het_sorok)), "csoportok": HETI_CSOPORTOK}


def allapot_szamok(db: Session) -> dict:
    """A fejléc számai: át nem nézett kivételek, lejárt hiányok, nyitott jelzések."""
    b = beallitas(db)
    return {
        "atnezetlen_kivetel": len(kivetelek(db, napok=None, csak_nyitott=True, tol=kezdet(b))),
        "lejart_hiany": len(lejart_hianyok(db, hatarido=hataridok(b), tol=kezdet(b))),
        "nyitott_jelzes": db.query(LaraFigyelesJelzes).filter(LaraFigyelesJelzes.lezarva_at.is_(None)).count(),
    }
