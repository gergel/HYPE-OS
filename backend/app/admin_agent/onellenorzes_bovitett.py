"""Lara — BŐVÍTETT önellenőrzés: a teljes projektkód-papírozás, a kimenő
számlák (bevétel), a teljes Utókövetés, és a rendszer egésze.

A felhasználó kérése: Lara, ahogy átnézi az egészet és az adminisztrációt,
folyamatosan tesztelje magát, és MINDIG kérdezzen, ha nem érti, miért van
valami úgy, ahogy — a kérdéseken át gyorsabban tanul és jobban megérti a
rendszert. Három rész (mind csak olvas; csak Lara kérdés-táblájába ír a hívó):

1. **Vak jóslat az adminisztrációs döntésekre** (`tipus="admin_dontes"`) — a
   meglévő számla- és alvállalkozói papír-önellenőrzés kiegészítése:
     * megrendelői szerződés és TIG: kihagyták-e, +ÁFA-e;
     * projektkód-döntések: papír nélkül, számla kihagyva, bevételbe ne kerüljön;
     * bevétel (kimenő számla): a megrendelő a szokásához képest késett-e;
     * belsős TIG: a havi összeg változott-e, +ÁFA-e.
   Lara a partner TÖBBI lezárt esetéből (≥2, ≥80% egyetértés) és a kérdéseire
   adott válaszokból jósol — az adott eset saját tanulsága nélkül.
2. **Elvárás-ellenőrzés a projektkód egészén** (`tipus="rendszer_elteres"`):
   amit a rendszer logikája szerint várna, de nem így van, és indoklás sincs —
   a megrendelő fizetett, de nincs papír; a TIG kiment, de 30 nap után sincs
   bevétel; alvállalkozót kifizettünk szerződés és TIG nélkül.
3. **Fogalom-kérdések a teljes rendszerről** (`tipus="rendszer_fogalom"`): mit
   jelent egy állapot-érték (pl. az utómunkában a „Javításra vár"), és jár-e
   vele adminisztrációs teendő. Adagolva (futásonként kevés), hogy ne árassza el.

Egy kérdésre adott válasz: „rendben / mindig így" és „magyarázat" → tudás (és
a hasonló eset nem kérdés többé), „egyszeri kivétel" → csak az az eset, „hiba"
→ feladat Lara felelősének a javításra (lásd `valasz`).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin_agent.memory import partner_kulcs
from app.models.admin_agent import AdminTask, LaraKerdes, MemoryChunk

TIPUS_DONTES = "admin_dontes"
TIPUS_ELTERES = "rendszer_elteres"
TIPUS_FOGALOM = "rendszer_fogalom"
BOVITETT_TIPUSOK = (TIPUS_DONTES, TIPUS_ELTERES, TIPUS_FOGALOM)
TANITO = ("mindig", "magyarazat")

MIN_ESET = 2
EGYETERTES = 0.8
#: Bevétel: ennyi nap eltérés a partner szokásától még „érthető".
KESES_TURES = 15
#: Belsős TIG: ennyi Ft eltérés még ugyanaz az összeg.
OSSZEG_TURES = 1.0
#: Megrendelői TIG kiküldése után ennyi nappal várunk bevételt.
TIG_UTAN_NAP = 30
#: Fogalom-kérdésből futásonként legfeljebb ennyi új, és egyszerre ennyi nyitott.
FOGALOM_UJ_MAX = 3
FOGALOM_NYITOTT_MAX = 8
#: Egy állapot-érték akkor „jelentős", ha legalább ennyi tétel áll rajta.
FOGALOM_MIN_DB = 3

TERULET_CIMKE = {
    "megrendeloi_szerzodes": "Megrendelői szerződés",
    "megrendeloi_tig": "Megrendelői TIG",
    "projektkod": "Projektkód",
    "bevetel": "Bevétel (kimenő számla)",
    "belsos_tig": "Belsős TIG",
    "elvaras": "Eltérés a várttól",
    "fogalom": "Rendszer-fogalom",
}
DIM_CIMKE = {
    "kihagyas": "kell-e a papír",
    "afa": "+ÁFA",
    "papir_nelkul": "papír nélkül",
    "szamla_kihagyva": "számla kihagyva",
    "bevetelbe_ne": "bevételbe ne kerüljön",
    "keses": "fizetési késés",
    "havi_osszeg": "havi összeg",
}
#: A válasz tudásának hatóköre (melyik feladattípusnál jön elő).
HATOKOR = {
    "megrendeloi_szerzodes": "szerzodes", "megrendeloi_tig": "tig", "projektkod": "projektkod",
    "bevetel": "kintlevoseg", "belsos_tig": "tig",
}


def _most() -> datetime:
    return datetime.now(timezone.utc)


def _ft(v) -> str | None:
    return f"{float(v):,.0f} Ft".replace(",", " ") if v is not None else None


def _igen(v) -> bool:
    return bool(v)


def _aware(d: datetime | None) -> datetime | None:
    if d is None:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _ido(s: str | None) -> datetime | None:
    try:
        return _aware(datetime.fromisoformat(s)) if s else None
    except ValueError:
        return None


# ── 0) A válaszokból és a lezárt kérdésekből nyert tudás ─────────────────────


class Valaszok:
    """Mit tanult Lara a bővített kérdéseire adott válaszokból."""

    def __init__(self, db: Session):
        #: (terület, dimenzió, partner) → (a „mindig így" / megmagyarázott érték,
        #: mikortól: a megválaszolt esetek legkésőbbi időpontja). Csak az ennél
        #: ÚJABB esetekre vonatkozik — „mostantól így" nem teszi hibássá a múltat.
        self.elvart: dict[tuple[str, str, str], tuple[Any, datetime | None]] = {}
        #: (ellenőrzés, partner) — ennél a partnernél ez rendben van.
        self.rendben: set[tuple[str, str]] = set()
        #: (terület/ellenőrzés/fogalom, eset-azonosító) — már megválaszolt eset.
        self.eset: set[tuple[str, str]] = set()
        #: már megválaszolt fogalmak kulcsai.
        self.fogalom: set[str] = set()
        for k in db.scalars(select(LaraKerdes).where(LaraKerdes.tipus.in_(BOVITETT_TIPUSOK))).all():
            c = k.kontextus or {}
            if k.allapot == "nyitott":
                continue
            if k.tipus == TIPUS_FOGALOM:
                self.fogalom.add(k.kulcs)
                continue
            jel = c.get("terulet") if k.tipus == TIPUS_DONTES else c.get("ellenorzes")
            for e in c.get("esetek") or []:
                self.eset.add((f"{jel}:{c.get('dimenzio', '')}", str(e.get("rekord"))))
            if k.valasz_tipus in TANITO and c.get("partner_kulcs"):
                if k.tipus == TIPUS_DONTES:
                    idok = [_ido(e.get("ido")) for e in c.get("esetek") or []]
                    idok = [i for i in idok if i]
                    self.elvart[(c["terulet"], c["dimenzio"], c["partner_kulcs"])] = (
                        (c.get("valosag") or {}).get("ertek"), max(idok) if idok else None)
                else:
                    self.rendben.add((c.get("ellenorzes"), c["partner_kulcs"]))


# ── 1) Vak jóslat az adminisztrációs döntésekre ──────────────────────────────


class _Rekord:
    __slots__ = ("azon", "partner", "kulcs", "ertekek", "meta", "ido")

    def __init__(self, azon: str, partner: str | None, ertekek: dict, meta: dict, ido: datetime | None):
        self.azon = azon
        self.partner = partner or ""
        self.kulcs = partner_kulcs(partner)
        self.ertekek = ertekek
        self.meta = meta
        self.ido = ido


def _pc_meta(pc) -> dict:
    return {"projektkod": getattr(pc, "projektkod", None), "projekt": getattr(pc, "project_nev", None),
            "project_code_id": getattr(pc, "id", None)}


def _megrendeloi(db: Session, model, kezdet: datetime, terulet: str) -> list[_Rekord]:
    from app.models.client import Client
    from app.models.megrendeloi_papir import KIHAGYVA, papir_kesz
    from app.models.project_code import ProjectCode

    ki = []
    ugyfel = dict(db.execute(select(Client.id, Client.nev)).all())
    for r in db.scalars(select(model).where(model.created_at >= kezdet)).all():
        if not papir_kesz(r):
            continue
        pc = db.get(ProjectCode, r.project_code_id)
        partner = (r.ceg_neve or "").strip() or ugyfel.get(r.client_id) or (pc.megrendelo_neve if pc else None)
        ert = {"kihagyas": r.allapot == KIHAGYVA and not r.alairt_file_url, "afa": r.plusz_afa}
        meta = {**_pc_meta(pc), "netto": _ft(r.netto_osszeg), "indok": (r.kihagyas_oka or "").strip() or None}
        ki.append(_Rekord(f"{terulet}:{r.id}", partner, ert, meta, r.updated_at or r.created_at))
    return ki


def _projektkodok(db: Session, kezdet: datetime) -> list[_Rekord]:
    from app.models.client import Client
    from app.models.project_code import ProjectCode

    ugyfel = dict(db.execute(select(Client.id, Client.nev)).all())
    ki = []
    for pc in db.scalars(select(ProjectCode).where(ProjectCode.created_at >= kezdet)).all():
        partner = (pc.megrendelo_neve or "").strip() or ugyfel.get(pc.client_id)
        ert = {"papir_nelkul": bool(pc.papir_nelkul), "szamla_kihagyva": bool(pc.szamla_kihagyva),
               "bevetelbe_ne": bool(pc.bevetelbe_ne_keruljon)}
        indok = {"papir_nelkul": pc.papir_nelkul_indoka, "szamla_kihagyva": pc.szamla_kihagyas_oka,
                 "bevetelbe_ne": pc.bevetel_kihagyas_oka}
        meta = {**_pc_meta(pc), "indokok": {k: (v or "").strip() or None for k, v in indok.items()}}
        ki.append(_Rekord(f"projektkod:{pc.id}", partner, ert, meta, pc.updated_at or pc.created_at))
    return ki


def _bevetelek(db: Session, kezdet: datetime) -> list[_Rekord]:
    from app.models.client import Client
    from app.models.finance import Revenue
    from app.models.project_code import ProjectCode

    ugyfel = dict(db.execute(select(Client.id, Client.nev)).all())
    ki = []
    for r in db.scalars(
        select(Revenue).where(Revenue.created_at >= kezdet, Revenue.fizetes_datuma.is_not(None),
                              Revenue.fizetes_hatarideje.is_not(None))
    ).all():
        pc = db.get(ProjectCode, r.project_code_id) if r.project_code_id else None
        partner = ((pc.megrendelo_neve or "").strip() or ugyfel.get(pc.client_id)) if pc else None
        keses = (r.fizetes_datuma - r.fizetes_hatarideje).days
        meta = {**_pc_meta(pc), "netto": _ft(r.netto), "hatarido": r.fizetes_hatarideje.isoformat(),
                "fizetve": r.fizetes_datuma.isoformat()}
        ki.append(_Rekord(f"bevetel:{r.id}", partner, {"keses": keses}, meta, r.updated_at or r.created_at))
    return ki


def _belsos_tigek(db: Session, kezdet: datetime) -> list[_Rekord]:
    from app.admin_agent.observer import _allapot_lezart
    from app.models.employee import Employee
    from app.models.internal_performance_certificate import InternalPerformanceCertificate as B

    nevek = dict(db.execute(select(Employee.id, Employee.full_name)).all())
    ki = []
    sorok = db.scalars(select(B).where(B.created_at >= kezdet).order_by(B.employee_id, B.ev, B.honap)).all()
    for r in sorok:
        if not _allapot_lezart(r.allapot):
            continue
        ert = {"havi_osszeg": float(r.netto_osszeg) if r.netto_osszeg is not None else None, "afa": r.plusz_afa,
               "_idoszak": (r.ev, r.honap)}
        meta = {"projektkod": None, "projekt": f"Belsős TIG {r.ev}.{int(r.honap):02d}", "netto": _ft(r.netto_osszeg)}
        ki.append(_Rekord(f"belsos_tig:{r.id}", nevek.get(r.employee_id), ert, meta, r.updated_at or r.created_at))
    return ki


def _megrendeloi_szerzodesek(db: Session, kezdet: datetime) -> list[_Rekord]:
    from app.models.megrendeloi_papir import MegrendeloiSzerzodes

    return _megrendeloi(db, MegrendeloiSzerzodes, kezdet, "megrendeloi_szerzodes")


def _megrendeloi_tigek(db: Session, kezdet: datetime) -> list[_Rekord]:
    from app.models.megrendeloi_papir import MegrendeloiTig

    return _megrendeloi(db, MegrendeloiTig, kezdet, "megrendeloi_tig")


#: terület → (rekord-gyűjtő, vizsgált dimenziók, alapértelmezés tudás nélkül)
TERULETEK: dict[str, tuple[Callable[[Session, datetime], list[_Rekord]], tuple[str, ...], dict]] = {
    "megrendeloi_szerzodes": (_megrendeloi_szerzodesek, ("kihagyas", "afa"), {"kihagyas": False}),
    "megrendeloi_tig": (_megrendeloi_tigek, ("kihagyas", "afa"), {"kihagyas": False}),
    "projektkod": (_projektkodok, ("papir_nelkul", "szamla_kihagyva", "bevetelbe_ne"),
                   {"papir_nelkul": False, "szamla_kihagyva": False, "bevetelbe_ne": False}),
    "bevetel": (_bevetelek, ("keses",), {"keses": 0}),
    "belsos_tig": (_belsos_tigek, ("havi_osszeg", "afa"), {}),
}


def ertek_szoveg(dim: str, v, meta: dict | None = None) -> str:
    meta = meta or {}
    if dim == "kihagyas":
        return ("kihagyva" + (f" (indok: „{meta['indok']}”)" if meta.get("indok") else "")) if v else "elkészült"
    if dim == "afa":
        return "+ÁFA" if v else "ÁFA nélkül"
    if dim in ("papir_nelkul", "szamla_kihagyva", "bevetelbe_ne"):
        indok = (meta.get("indokok") or {}).get(dim)
        return ("igen" + (f" (indok: „{indok}”)" if indok else " (indoklás nélkül)")) if v else "nem"
    if dim == "keses":
        return f"{v} nap késés" if v > 0 else ("határidőre" if v == 0 else f"{-v} nappal előbb")
    if dim == "havi_osszeg":
        return _ft(v) or "—"
    return str(v)


def _josol(r: _Rekord, dim: str, tarsak: list[_Rekord], terulet: str, valaszok: Valaszok, alap: dict):
    """(várt érték, alap szövege) vagy None. A saját eset tanulsága nélkül."""
    kulcs = (terulet, dim, r.kulcs)
    if kulcs in valaszok.elvart:
        v, ota = valaszok.elvart[kulcs]
        if ota is None or _aware(r.ido) is None or _aware(r.ido) > ota:
            return v, "a kérdésemre adott válaszotok"
        # A válasz előtti esetet csak a szintén korábbi esetekhez mérjük.
        tarsak = [t for t in tarsak if _aware(t.ido) is not None and _aware(t.ido) <= ota]
    if dim == "havi_osszeg":
        # Az előző hónap összege ugyanennél a munkatársnál.
        elozo = [t for t in tarsak if t.ertekek.get("_idoszak") < r.ertekek.get("_idoszak")
                 and t.ertekek.get("havi_osszeg") is not None]
        if not elozo:
            return None
        e = max(elozo, key=lambda t: t.ertekek["_idoszak"])
        return e.ertekek["havi_osszeg"], f"az előző hónap ({e.ertekek['_idoszak'][0]}.{e.ertekek['_idoszak'][1]:02d})"
    ertekek = [t.ertekek.get(dim) for t in tarsak if t.ertekek.get(dim) is not None]
    if dim == "keses":
        if len(ertekek) >= MIN_ESET:
            return round(median(ertekek)), f"{len(ertekek)} korábbi fizetése"
        return alap.get(dim), "alapértelmezés: határidőre"
    if len(ertekek) >= MIN_ESET:
        v, n = Counter(ertekek).most_common(1)[0]
        if n / len(ertekek) >= EGYETERTES:
            return v, f"{n} korábbi esete"
    if dim in alap:
        return alap[dim], "alapértelmezés"
    return None


def _egyezik(dim: str, josolt, valos) -> bool:
    if dim == "keses":
        return valos <= max(josolt, 0) + KESES_TURES
    if dim == "havi_osszeg":
        return valos is None or abs(float(valos) - float(josolt)) <= OSSZEG_TURES
    return _igen(josolt) == _igen(valos)


def dontes_ellenorzes(db: Session, kezdet: datetime, valaszok: Valaszok) -> tuple[dict[str, Counter], dict[str, dict]]:
    stat: dict[str, Counter] = {t: Counter() for t in TERULETEK}
    csoport: dict[str, dict] = {}
    for terulet, (gyujto, dimek, alap) in TERULETEK.items():
        try:
            rekordok = gyujto(db, kezdet)
        except Exception:  # noqa: BLE001 — egy terület hibája ne állítsa meg a többit
            stat[terulet]["hiba"] += 1
            continue
        partnerenkent: dict[str, list[_Rekord]] = defaultdict(list)
        for r in rekordok:
            if len(r.kulcs) >= 3:
                partnerenkent[r.kulcs].append(r)
        for kulcs, lista in partnerenkent.items():
            for r in lista:
                tarsak = [t for t in lista if t.azon != r.azon]
                for dim in dimek:
                    v = r.ertekek.get(dim)
                    if v is None:
                        continue
                    j = _josol(r, dim, tarsak, terulet, valaszok, alap)
                    if j is None or j[0] is None:
                        continue
                    jv, alapszoveg = j
                    if _egyezik(dim, jv, v):
                        stat[terulet]["egyezik"] += 1
                        continue
                    stat[terulet]["elter"] += 1
                    if (f"{terulet}:{dim}", r.azon) in valaszok.eset:
                        stat[terulet]["megmagyarazva"] += 1
                        continue
                    ck = f"dontes:{terulet}:{dim}:{kulcs}"
                    g = csoport.setdefault(ck, {
                        "tipus": TIPUS_DONTES, "terulet": terulet, "dimenzio": dim,
                        "cimke": f"{TERULET_CIMKE[terulet]} · {DIM_CIMKE.get(dim, dim)}",
                        "partner": r.partner, "partner_kulcs": kulcs,
                        # Numerikus dimenziónál (késés, havi összeg) a tényleges érték: a
                        # „mindig így" válasz után ez lesz a várt érték.
                        "valosag": {"ertek": v,
                                    "szoveg": ertek_szoveg(dim, v, r.meta)},
                        "esetek": [],
                    })
                    g["esetek"].append({
                        "rekord": r.azon, "projektkod": r.meta.get("projektkod"), "projekt": r.meta.get("projekt"),
                        "project_code_id": r.meta.get("project_code_id"), "netto": r.meta.get("netto"),
                        "datum": r.ido.date().isoformat() if r.ido else None,
                        "ido": _aware(r.ido).isoformat() if r.ido else None,
                        "lara_szoveg": ertek_szoveg(dim, jv), "lara_alap": f"{alapszoveg} alapján",
                        "valosag_szoveg": ertek_szoveg(dim, v, r.meta),
                    })
    return stat, csoport


# ── 2) Elvárás-ellenőrzés a projektkód egészén ───────────────────────────────

ELLENORZES_CIMKE = {
    "fizetve_papir_nelkul": "A megrendelő fizetett, de nincs papír",
    "tig_utan_nincs_bevetel": "A TIG kiment, de nincs bevétel",
    "alvallalkozo_papir_nelkul": "Alvállalkozó kifizetve szerződés és TIG nélkül",
}


def elvaras_ellenorzes(db: Session, kezdet: datetime, valaszok: Valaszok) -> tuple[Counter, dict[str, dict]]:
    from app.models.client import Client
    from app.models.contract import Contract
    from app.models.employee import Employee
    from app.models.finance import Expense, Revenue
    from app.models.megrendeloi_papir import KIHAGYVA, MegrendeloiSzerzodes, MegrendeloiTig, papir_kesz
    from app.models.performance_certificate import PerformanceCertificate
    from app.models.project import Project
    from app.models.project_code import ProjectCode

    stat: Counter = Counter()
    csoport: dict[str, dict] = {}
    ugyfel = dict(db.execute(select(Client.id, Client.nev)).all())
    most = _most()

    def _megrendelo(pc) -> str | None:
        return (pc.megrendelo_neve or "").strip() or ugyfel.get(pc.client_id)

    def _eset(ellenorzes: str, partner: str | None, azon: str, pc, reszlet: str) -> None:
        kulcs = partner_kulcs(partner)
        if len(kulcs) < 3:
            kulcs = f"kod{getattr(pc, 'id', '')}"
        if (ellenorzes, kulcs) in valaszok.rendben:
            stat["rendben_valasz"] += 1
            return
        if (f"{ellenorzes}:", azon) in valaszok.eset:
            stat["megmagyarazva"] += 1
            return
        stat["kerdeses"] += 1
        g = csoport.setdefault(f"elteres:{ellenorzes}:{kulcs}", {
            "tipus": TIPUS_ELTERES, "ellenorzes": ellenorzes, "cimke": ELLENORZES_CIMKE[ellenorzes],
            "partner": partner or (pc.projektkod if pc else "?"), "partner_kulcs": kulcs, "esetek": [],
        })
        g["esetek"].append({"rekord": azon, **_pc_meta(pc), "valosag_szoveg": reszlet})

    papirok: dict[int, list] = defaultdict(list)
    for m in (MegrendeloiSzerzodes, MegrendeloiTig):
        for r in db.scalars(select(m)).all():
            papirok[r.project_code_id].append(r)
    bevetel_kodok = set(db.scalars(select(Revenue.project_code_id).where(Revenue.project_code_id.is_not(None))).all())
    fizetve_kodok = set(db.scalars(select(Revenue.project_code_id).where(Revenue.fizetes_datuma.is_not(None))).all())

    kodok = {pc.id: pc for pc in db.scalars(select(ProjectCode).where(ProjectCode.created_at >= kezdet)).all()}
    for pc_id, pc in kodok.items():
        # E1: a megrendelő fizetett, de nincs lezárt megrendelői papír és indoklás.
        if pc_id in fizetve_kodok:
            stat["vizsgalt"] += 1
            if not any(papir_kesz(p) for p in papirok.get(pc_id, [])) and not pc.papir_nelkul \
                    and not pc.tranzakcio_nelkul_lezarva:
                _eset("fizetve_papir_nelkul", _megrendelo(pc), f"projektkod:{pc_id}", pc,
                      "a megrendelő fizetett, lezárt megrendelői szerződés/TIG nincs, „papír nélkül” jelölés sincs")
            else:
                stat["rendben"] += 1
        # E2: kiküldött megrendelői TIG, 30 nap után sincs bevétel.
        for p in papirok.get(pc_id, []):
            if not isinstance(p, MegrendeloiTig) or not papir_kesz(p) or p.allapot == KIHAGYVA:
                continue
            ido = p.updated_at or p.created_at
            if ido is None or ido > most - timedelta(days=TIG_UTAN_NAP):
                continue
            stat["vizsgalt"] += 1
            if pc_id not in bevetel_kodok and not pc.szamla_kihagyva and not pc.bevetelbe_ne_keruljon:
                _eset("tig_utan_nincs_bevetel", _megrendelo(pc), f"megrendeloi_tig:{p.id}", pc,
                      f"a TIG {ido.date().isoformat()} óta lezárt, bevétel/számla nincs rögzítve, kihagyás sincs jelölve")
            else:
                stat["rendben"] += 1

    # E3: alvállalkozói kiadás kifizetve, de nincs hozzá szerződés és TIG.
    proj_kod = dict(db.execute(select(Project.id, Project.project_code_id)).all())
    nevek = dict(db.execute(select(Employee.id, Employee.full_name)).all())
    papir_par: set[tuple[int, int]] = set()
    for m in (Contract, PerformanceCertificate):
        for emp, pcid, pid in db.execute(select(m.employee_id, m.project_code_id, m.project_id)).all():
            kod = pcid or proj_kod.get(pid)
            if emp and kod:
                papir_par.add((emp, kod))
    for e in db.scalars(
        select(Expense).where(Expense.created_at >= kezdet, Expense.kesz.is_(True), Expense.employee_id.is_not(None))
    ).all():
        if (e.tipus or "").strip().lower() != "kulsos":
            continue
        kod = e.project_code_id or proj_kod.get(e.alvallalkozo_project_id)
        if not kod:
            continue
        stat["vizsgalt"] += 1
        if (e.employee_id, kod) in papir_par:
            stat["rendben"] += 1
            continue
        pc = kodok.get(kod) or db.get(ProjectCode, kod)
        _eset("alvallalkozo_papir_nelkul", nevek.get(e.employee_id), f"kiadas:{e.id}", pc,
              f"kifizetve {_ft(e.netto) or ''}, de ennél a projektkódnál nincs szerződése és TIG-je")
    return stat, csoport


# ── 3) Fogalom-kérdések a teljes rendszerről ─────────────────────────────────


def fogalom_ellenorzes(db: Session, valaszok: Valaszok) -> tuple[Counter, dict[str, dict]]:
    """Az állapot-jellegű mezők jelentős értékei: amit Lara még nem ért, arra
    (adagolva) rákérdez. A projekthez kötött és az adminisztrációs területek elöl."""
    from app.admin_agent.rendszer import _allapot_oszlopok, _eloszlas, _figyelt_tablak, modul_nev

    stat: Counter = Counter()
    jeloltek: list[tuple[int, str, dict]] = []
    nyitott = {k.kulcs for k in db.scalars(
        select(LaraKerdes).where(LaraKerdes.tipus == TIPUS_FOGALOM, LaraKerdes.allapot == "nyitott")).all()}
    for nev, t in _figyelt_tablak(db).items():
        prio = 2 if ("project_code_id" in t.c or "project_id" in t.c) else 1
        for o in _allapot_oszlopok(t)[:3]:
            if str(getattr(o.type, "python_type", "")) == "<class 'bool'>":
                continue
            try:
                with db.begin_nested():
                    eloszlas = _eloszlas(db, t, o) or []
            except Exception:  # noqa: BLE001
                continue
            for ertek, n in eloszlas:
                if n < FOGALOM_MIN_DB or ertek in ("igen", "nem"):
                    continue
                kulcs = f"fogalom|{nev}|{o.name}|{ertek}"[:200]
                stat["jelentos"] += 1
                if kulcs in valaszok.fogalom:
                    stat["megertett"] += 1
                    continue
                if kulcs in nyitott:
                    stat["kerdezett"] += 1
                    continue
                jeloltek.append((prio * 100000 + n, kulcs, {
                    "tipus": TIPUS_FOGALOM, "tabla": nev, "oszlop": o.name, "ertek": ertek, "darab": n,
                    "modul": modul_nev(nev), "cimke": f"Rendszer-fogalom · {modul_nev(nev)}",
                    "partner": modul_nev(nev), "partner_kulcs": nev, "esetek": [],
                }))
    hely = max(0, min(FOGALOM_UJ_MAX, FOGALOM_NYITOTT_MAX - len(nyitott)))
    jeloltek.sort(key=lambda x: x[0], reverse=True)
    return stat, {k: g for _, k, g in jeloltek[:hely]}


# ── Kérdés-szöveg + válasz ───────────────────────────────────────────────────


def kerdes_szoveg(g: dict) -> str:
    n = len(g.get("esetek") or [])
    p = g.get("partner") or "?"
    if g["tipus"] == TIPUS_FOGALOM:
        return (f"A(z) {g['modul']} területen a(z) „{g['oszlop']}” mezőben {g['darab']} tétel áll a(z) "
                f"„{g['ertek']}” értéken. Mit jelent ez nálatok, és jár-e vele adminisztrációs teendő "
                "(számla, TIG, szerződés)?")
    if g["tipus"] == TIPUS_ELTERES:
        e = g["esetek"][0]
        felsorolas = ", ".join(x.get("projektkod") or x["rekord"] for x in g["esetek"][:4]) + (" …" if n > 4 else "")
        return (f"{g['cimke']}: „{p}” — {n} esetben ({felsorolas}). Első eset: {e['valosag_szoveg']}. "
                "Miért van így? Ha ez nála rendben van, tanítsd meg; ha hiba, szólj, és feladatot készítek rá.")
    e = g["esetek"][0]
    dim = DIM_CIMKE.get(g["dimenzio"], g["dimenzio"])
    return (f"{TERULET_CIMKE[g['terulet']]} — „{p}”, {dim}: {e['lara_szoveg']} számítottam "
            f"({e['lara_alap']}), de {n} esetben {g['valosag']['szoveg']} lett. Miért? Nála ez mostantól így van?")


def valasz(db: Session, k: LaraKerdes, valasz_tipus: str, szoveg: str | None, eredmeny: dict) -> None:
    """A bővített kérdések válasza → tudás / javítási feladat. A hívó zár és commitál."""
    c = k.kontextus or {}
    if k.tipus == TIPUS_FOGALOM and valasz_tipus in ("mindig", "magyarazat", "kivetel"):
        if not szoveg:
            from app.admin_agent.onellenorzes import ValaszHiba

            raise ValaszHiba("Írd le röviden, mit jelent ez az állapot — ebből tanul Lara.")
        tartalom = (f"Rendszer-fogalom — {c.get('modul')} (`{c.get('tabla')}`), {c.get('oszlop')} = "
                    f"„{c.get('ertek')}”: {szoveg}")
        hatokor = "rendszer"
    elif valasz_tipus in ("mindig", "magyarazat", "kivetel"):
        n = len(c.get("esetek") or [])
        if k.tipus == TIPUS_ELTERES:
            alap = f"{c.get('cimke')} — „{k.partner_nev}” ({n} eset)"
            tartalom = (alap + (": egyszeri kivétel." if valasz_tipus == "kivetel" else ": ennél a partnernél ez rendben van, így szokás."))
            hatokor = "rendszer"
        else:
            alap = f"{TERULET_CIMKE.get(c.get('terulet'), c.get('terulet'))} — „{k.partner_nev}”, {DIM_CIMKE.get(c.get('dimenzio'), '')}"
            tartalom = alap + (f": {n} esetben egyszeri kivételként {(c.get('valosag') or {}).get('szoveg')}. Nem általános."
                               if valasz_tipus == "kivetel" else f": mindig így — {(c.get('valosag') or {}).get('szoveg')}.")
            hatokor = HATOKOR.get(c.get("terulet"), "rendszer")
        if szoveg:
            tartalom += f" Magyarázat (ember): {szoveg}"
    else:
        tartalom = None
        hatokor = "rendszer"
    if tartalom:
        m = MemoryChunk(hatokor=hatokor, tartalom=tartalom, forras=f"kerdes:{k.id}", minosites="jovahagyott",
                        tanulasi_halmaz="jovahagyott", ervenyes=True, regi_korszak=False)
        db.add(m)
        db.flush()
        eredmeny["pelda_id"] = m.id
    if valasz_tipus == "hibas" and k.tipus != TIPUS_FOGALOM:
        # Hiba a rögzítésben → javítási feladat Lara felelősének (adminisztráció).
        from app.admin_agent.enums import TaskState, TaskType
        from app.admin_agent.settings_service import lara_felelos

        eset = (c.get("esetek") or [{}])[0]
        f = lara_felelos(db)
        t = AdminTask(
            tipus=TaskType.EGYEB.value, cim=f"Javítandó (Lara kérdéséből): {c.get('cimke') or ''} — {k.partner_nev}"[:300],
            osszefoglalo=(k.kerdes or "")[:2000] + (f"\n\nMegjegyzés: {szoveg}" if szoveg else ""),
            allapot=TaskState.NEW.value, trust_level="L0", project_code_id=eset.get("project_code_id"),
            partner_nev=(k.partner_nev or "")[:255] or None, felelos_id=f.id if f else None,
            forras_referenciak={"lara_kerdes_id": k.id},
        )
        db.add(t)
        db.flush()
        eredmeny["feladat_id"] = t.id


def bovitett_ellenorzes(db: Session, kezdet: datetime) -> tuple[dict[str, dict], dict[str, dict]]:
    """Mindhárom rész. Vissza: (területenkénti statisztika, kérdés-csoportok)."""
    valaszok = Valaszok(db)
    dontes_stat, dontes_cs = dontes_ellenorzes(db, kezdet, valaszok)
    elv_stat, elv_cs = elvaras_ellenorzes(db, kezdet, valaszok)
    fog_stat, fog_cs = fogalom_ellenorzes(db, valaszok)

    def _t(c: Counter) -> dict:
        n = c["egyezik"] + c["elter"]
        return {"ellenorzott": n, "egyezik": c["egyezik"], "elter": c["elter"], "nem_tudta": 0,
                "megmagyarazva": c["megmagyarazva"], "talalati_arany": round(c["egyezik"] / n, 3) if n else None}

    teruletek = {t: _t(c) for t, c in dontes_stat.items()}
    n = elv_stat["vizsgalt"]
    teruletek["elvaras"] = {
        "ellenorzott": n, "egyezik": elv_stat["rendben"] + elv_stat["rendben_valasz"],
        "elter": elv_stat["kerdeses"] + elv_stat["megmagyarazva"], "nem_tudta": 0,
        "megmagyarazva": elv_stat["megmagyarazva"] + elv_stat["rendben_valasz"],
        "talalati_arany": round((n - elv_stat["kerdeses"]) / n, 3) if n else None,
    }
    j = fog_stat["jelentos"]
    teruletek["fogalom"] = {
        "ellenorzott": j, "egyezik": fog_stat["megertett"], "elter": j - fog_stat["megertett"], "nem_tudta": 0,
        "megmagyarazva": fog_stat["megertett"], "talalati_arany": round(fog_stat["megertett"] / j, 3) if j else None,
    }
    return teruletek, {**dontes_cs, **elv_cs, **fog_cs}
