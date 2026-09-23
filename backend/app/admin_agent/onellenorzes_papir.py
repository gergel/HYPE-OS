"""Lara — önellenőrzés a papírozáson (eseti szerződések és TIG-ek, Utókövetés).

A projektkódokhoz / forgatásokhoz készülő szerződéseknél és TIG-eknél az ember
a Utókövetés oldalon dönt. Lara ezekre a döntésekre is „vakon" jósol a
jelenlegi tudásával (az adott rekord saját tanulsága nélkül), összeveti a
valósággal, és ahol nem érti az eltérést, kérdez. Vizsgált döntések:

* ``kihagyas``  — kellett-e a papír, vagy kihagyták (indoklással),
* ``osszeg``    — a nettó összeg eltért-e a lefedett tételek összegétől,
* ``afa``       — +ÁFA vagy sem,
* ``targy``     — a megbízás tárgya,
* ``szamla_kihagyas`` — (TIG) kellett-e hozzá számla.

Tudás (``PapirTudas``): az élesített, partnerhez kötött papír-szabályok
(``feltetelek.mezo``/``ertek``), a JÓVÁHAGYOTT megfigyelt példák rekordjai és
a Lara kérdéseire adott magyarázatok. Alapértelmezés tudás nélkül: a papír
kell, az összeg = a tételek összege, számla kell (ÁFA-t és tárgyat tudás nélkül
nem jósol). Csak olvas; üzleti rekord nem változik.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin_agent.enums import RuleState
from app.admin_agent.memory import partner_kulcs
from app.admin_agent.observer import FIGYELT, _Kontextus, _notion_rekordok, _regi
from app.models.admin_agent import LaraKerdes, MemoryChunk, PlaybookRule
from app.models.contract import Contract, ContractType
from app.models.performance_certificate import PerformanceCertificate

TERULETEK = ("szerzodes", "tig")
TERULET_CIMKE = {"szamla": "Számlák", "szerzodes": "Szerződések", "tig": "TIG-ek"}
PAPIR_CIMKE = {"szerzodes": "szerződés", "tig": "TIG"}
#: Ragozott alakok a kérdésekhez.
_TARGYESET = {"szerzodes": "szerződését", "tig": "TIG-jét"}
_NAL = {"szerzodes": "szerződésénél", "tig": "TIG-jénél"}
_NEK = {"szerzodes": "szerződésének", "tig": "TIG-jének"}
DIMENZIO_CIMKE = {
    "kihagyas": "kell-e a papír",
    "osszeg": "nettó összeg",
    "afa": "+ÁFA",
    "targy": "megbízás tárgya",
    "szamla_kihagyas": "kell-e számla",
}
LEZART = {
    "szerzodes": {"Kiküldve", "Kihagyva", "Van már szerződés"},
    "tig": {"Kiküldve", "Kihagyva"},
}
MIN_ESET = 2
EGYETERTES = 0.8
HASONLOSAG = 0.6


def _norm(s: str | None) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", s)).strip()


def hasonlo(a: str | None, b: str | None) -> bool:
    ta, tb = set(_norm(a).split()), set(_norm(b).split())
    if not ta or not tb:
        return False
    return len(ta & tb) / len(ta | tb) >= HASONLOSAG


def _tetel_osszeg(r) -> float | None:
    tetelek = list(getattr(r, "tetelek", None) or [])
    if not tetelek or any(t.netto_osszeg is None for t in tetelek):
        return None
    return float(sum(float(t.netto_osszeg) for t in tetelek))


def ertekek(terulet: str, r) -> dict:
    """Egy lezárt papír döntései (a valóság)."""
    allapot = r.szerzodes_allapota if terulet == "szerzodes" else r.allapot
    kihagyva = allapot == "Kihagyva"
    tetel = _tetel_osszeg(r)
    netto = float(r.netto_osszeg) if r.netto_osszeg is not None else None
    ki = {
        "kihagyas": kihagyva,
        "kihagyas_oka": (r.kihagyas_oka or "").strip() or None,
        "osszeg": (abs(netto - tetel) >= 1) if (not kihagyva and netto is not None and tetel is not None) else None,
        "tetel_osszeg": tetel,
        "netto": netto,
        "afa": r.plusz_afa if not kihagyva else None,
        "targy": None if kihagyva else ((r.megbizas_targya or "").strip() or None),
        "szamla_kihagyas": None,
        "szamla_kihagyas_oka": None,
    }
    if terulet == "tig" and not kihagyva and allapot == "Kiküldve":
        ki["szamla_kihagyas"] = bool(r.szamla_kihagyva)
        ki["szamla_kihagyas_oka"] = (r.szamla_kihagyas_oka or "").strip() or None
    return ki


def _lezart_rekordok(db: Session, terulet: str, kezdet: datetime) -> list:
    if terulet == "szerzodes":
        q = select(Contract).where(
            Contract.tipus == ContractType.ALVALLALKOZOI,
            Contract.keretszerzodes.is_(False),
            Contract.szerzodes_allapota.in_(LEZART["szerzodes"]),
        )
        model = Contract
    else:
        q = select(PerformanceCertificate).where(PerformanceCertificate.allapot.in_(LEZART["tig"]))
        model = PerformanceCertificate
    sorok = db.scalars(q.where(model.created_at >= kezdet).order_by(model.id)).all()
    figyelt = next(f for f in FIGYELT if f.kulcs == terulet)
    notion = _notion_rekordok(db, figyelt, [r.id for r in sorok])
    return [r for r in sorok if not _regi(r.created_at, r.id in notion, kezdet)]


def _leiras(k: _Kontextus, terulet: str, r) -> dict:
    f = next(x for x in FIGYELT if x.kulcs == terulet)
    return f.leiro(k, r)


class PapirTudas:
    """Lara jóváhagyott tudása a papírozásról: (terület, partner) → döntések."""

    def __init__(self, db: Session):
        self.szabalyok: dict[tuple[str, str, str], PlaybookRule] = {}
        for r in db.scalars(
            select(PlaybookRule)
            .where(PlaybookRule.hatokor.in_(TERULETEK), PlaybookRule.allapot == RuleState.ACTIVE.value)
            .order_by(PlaybookRule.prioritas.asc(), PlaybookRule.id.asc())
        ).all():
            f = r.feltetelek or {}
            if f.get("partner") and f.get("mezo") in DIMENZIO_CIMKE:
                self.szabalyok[(r.hatokor, f["partner"], f["mezo"])] = r  # a legerősebb/legújabb nyer

        # Jóváhagyott megfigyelt példák → a rekordok döntései.
        self.esetek: dict[tuple[str, str], list[tuple[str, dict]]] = defaultdict(list)
        jovahagyott = {
            m.forras
            for m in db.scalars(
                select(MemoryChunk).where(
                    MemoryChunk.forras.like("megfigyeles:%"),
                    MemoryChunk.ervenyes.is_(True),
                    MemoryChunk.visszavont.is_(False),
                )
            ).all()
        }
        ktx = _Kontextus(db)
        for terulet in TERULETEK:
            ids = [int(f.split(":")[2]) for f in jovahagyott if f.startswith(f"megfigyeles:{terulet}:")]
            model = Contract if terulet == "szerzodes" else PerformanceCertificate
            for i in range(0, len(ids), 500):
                for r in db.scalars(select(model).where(model.id.in_(ids[i : i + 500]))).all():
                    kulcs = partner_kulcs(_leiras(ktx, terulet, r).get("partner"))
                    if len(kulcs) >= 3:
                        self.esetek[(terulet, kulcs)].append((f"{terulet}:{r.id}", ertekek(terulet, r)))
        # Magyarázattal megválaszolt kérdések (a „mindig így" szabályként él).
        for k in db.scalars(
            select(LaraKerdes).where(LaraKerdes.tipus == "papir", LaraKerdes.valasz_tipus == "magyarazat")
        ).all():
            c = k.kontextus or {}
            if not c.get("partner_kulcs") or c.get("dimenzio") not in DIMENZIO_CIMKE:
                continue
            for e in c.get("esetek") or []:
                self.esetek[(c["terulet"], c["partner_kulcs"])].append(
                    (e.get("rekord") or "", {c["dimenzio"]: (c.get("valosag") or {}).get("ertek")})
                )

    def josol(self, terulet: str, kulcs: str, dim: str, kiveve: str | None = None,
              alapertelmezes: bool = True) -> tuple[object, str] | None:
        """(várt érték, forrás) — vagy None, ha erre nincs jóslat. Az
        `alapertelmezes=False` csak a valódi tudást adja (szabály / esetek)."""
        r = self.szabalyok.get((terulet, kulcs, dim))
        if r is not None:
            return r.feltetelek.get("ertek"), f"élesített szabály: „{r.cim}”"
        ertek = [e[dim] for azon, e in self.esetek.get((terulet, kulcs), []) if azon != kiveve and e.get(dim) is not None]
        if dim == "targy":
            ertek = [x for x in ertek if x]
        if len(ertek) >= MIN_ESET:
            if dim == "targy":
                # A leggyakoribb (normalizáltan azonos) megfogalmazás.
                cs = Counter(_norm(x) for x in ertek)
                norm, db_ = cs.most_common(1)[0]
                if db_ / len(ertek) >= EGYETERTES:
                    eredeti = next(x for x in ertek if _norm(x) == norm)
                    return eredeti, f"{db_} jóváhagyott korábbi eset"
            else:
                v, db_ = Counter(ertek).most_common(1)[0]
                if db_ / len(ertek) >= EGYETERTES:
                    return v, f"{db_} jóváhagyott korábbi eset"
        if not alapertelmezes:
            return None
        alap = {
            "kihagyas": (False, "alapértelmezés: a papír kell"),
            "osszeg": (False, "alapértelmezés: a tételek összege"),
            "szamla_kihagyas": (False, "alapértelmezés: számla kell"),
        }
        return alap.get(dim)


def ertek_szoveg(dim: str, v, e: dict | None = None) -> str:
    if dim == "kihagyas":
        return "kihagyva" + (f" (indok: „{e['kihagyas_oka']}”)" if e and e.get("kihagyas_oka") else "") if v else "elkészült"
    if dim == "osszeg":
        if e and e.get("tetel_osszeg") is not None and e.get("netto") is not None:
            return f"tételek {e['tetel_osszeg']:,.0f} Ft → rögzítve {e['netto']:,.0f} Ft".replace(",", " ")
        return "eltérhet a tételek összegétől" if v else "a tételek összege"
    if dim == "afa":
        return "+ÁFA" if v else "ÁFA nélkül"
    if dim == "szamla_kihagyas":
        return "számla kihagyva" + (f" (indok: „{e['szamla_kihagyas_oka']}”)" if e and e.get("szamla_kihagyas_oka") else "") if v else "számla kell"
    return f"„{v}”" if v else "—"


def egyezik(dim: str, josolt, valos) -> bool:
    if dim == "targy":
        return hasonlo(str(josolt), str(valos))
    if dim == "osszeg":
        # Ha Lara tudja, hogy nála eltérhet, az eltérés „érthető" — nincs meglepetés.
        return bool(josolt) or not valos
    return bool(josolt) == bool(valos)


def papir_ellenorzes(db: Session, kezdet: datetime, megvalaszolt: set[tuple[str, str]]) -> tuple[dict, dict]:
    """Vak jóslat minden lezárt papír döntéseire. Vissza: (területenkénti
    statisztika, kérdés-csoportok kulcs szerint)."""
    tudas = PapirTudas(db)
    ktx = _Kontextus(db)
    stat: dict[str, Counter] = {t: Counter() for t in TERULETEK}
    csoport: dict[str, dict] = {}
    for terulet in TERULETEK:
        for r in _lezart_rekordok(db, terulet, kezdet):
            meta = _leiras(ktx, terulet, r)
            partner = meta.get("partner")
            kulcs = partner_kulcs(partner)
            if len(kulcs) < 3:
                continue
            azon = f"{terulet}:{r.id}"
            valos = ertekek(terulet, r)
            for dim in DIMENZIO_CIMKE:
                v = valos.get(dim)
                if v is None:
                    continue
                j = tudas.josol(terulet, kulcs, dim, kiveve=azon)
                if j is None:
                    continue  # erre nincs jóslat (pl. ÁFA/tárgy tudás nélkül)
                jv, alap = j
                if egyezik(dim, jv, v):
                    stat[terulet]["egyezik"] += 1
                    continue
                stat[terulet]["elter"] += 1
                if (azon, dim) in megvalaszolt:
                    stat[terulet]["megmagyarazva"] += 1
                    continue
                ck = f"papir:{terulet}:{dim}:{kulcs}"
                g = csoport.setdefault(
                    ck,
                    {
                        "terulet": terulet,
                        "dimenzio": dim,
                        "partner": partner,
                        "partner_kulcs": kulcs,
                        "valosag": {"ertek": v if dim != "osszeg" else True, "szoveg": ertek_szoveg(dim, v)},
                        "esetek": [],
                    },
                )
                g["esetek"].append(
                    {
                        "rekord": azon,
                        "rekord_id": r.id,
                        "projektkod": meta.get("projektkod"),
                        "projekt": meta.get("projekt"),
                        "datum": (r.updated_at or r.created_at).date().isoformat() if (r.updated_at or r.created_at) else None,
                        "netto": f"{valos['netto']:,.0f} Ft".replace(",", " ") if valos.get("netto") is not None else None,
                        "lara_szoveg": ertek_szoveg(dim, jv),
                        "lara_alap": f"{alap} alapján" if not alap.startswith("alapértelmezés") else alap,
                        "valosag_szoveg": ertek_szoveg(dim, v, valos),
                    }
                )
    return stat, csoport


def papir_kerdes_szoveg(g: dict) -> str:
    t = g["terulet"]
    p = g["partner"]
    n = len(g["esetek"])
    e = g["esetek"][0]
    dim = g["dimenzio"]
    if dim == "kihagyas" and g["valosag"]["ertek"]:
        oka = e["valosag_szoveg"].removeprefix("kihagyva").strip()
        return (f"A(z) „{p}” {_TARGYESET[t]} {n} esetben kihagytátok{(' ' + oka) if oka else ''}, pedig azt vártam, "
                "hogy kell. Nála ez mindig kihagyható?")
    if dim == "kihagyas":
        return (f"A(z) „{p}” {_TARGYESET[t]} azt vártam, hogy kihagyjátok ({e['lara_alap']}), de {n} esetben "
                "elkészült. Miért kellett most mégis?")
    if dim == "osszeg":
        return (f"A(z) „{p}” {_NEK[t]} nettó összege {n} esetben eltért a lefedett tételek összegétől "
                f"({e['valosag_szoveg']}). Miért? Nála ez rendszeres?")
    if dim == "afa":
        return (f"A(z) „{p}” {_NAL[t]} {e['lara_szoveg']} számítottam ({e['lara_alap']}), "
                f"de {n} esetben {g['valosag']['szoveg']} lett. Miért változott?")
    if dim == "targy":
        return (f"A(z) „{p}” {_NEK[t]} megbízási tárgya eddig {e['lara_szoveg']} volt, most {n} esetben "
                f"{e['valosag_szoveg']}. Miért változott? Mostantól ez az új megfogalmazás?")
    return (f"A(z) „{p}” TIG-jénél {n} esetben {e['valosag_szoveg']}, pedig azt vártam, hogy számla kell. "
            "Nála mindig így van?")


def papir_szabaly(k: LaraKerdes, szoveg: str | None, aktiv: bool) -> PlaybookRule:
    c = k.kontextus or {}
    t, dim = c["terulet"], c["dimenzio"]
    v = (c.get("valosag") or {}).get("ertek")
    cim = f"{k.partner_nev}: {PAPIR_CIMKE[t]} — {DIMENZIO_CIMKE[dim]}: {(c.get('valosag') or {}).get('szoveg')}"
    return PlaybookRule(
        hatokor=t,
        cim=cim[:200],
        tartalom=(
            f"A(z) „{k.partner_nev}” {_NAL[t]} ({DIMENZIO_CIMKE[dim]}) mindig így: "
            f"{(c.get('valosag') or {}).get('szoveg')}."
            + (f" Indoklás: {szoveg}" if szoveg else "")
            + " (Lara kérdésére adott emberi válasz alapján.)"
        ),
        feltetelek={
            "forras": "kerdes",
            "kerdes_id": k.id,
            "partner": c.get("partner_kulcs"),
            "partner_nev": k.partner_nev,
            "mezo": dim,
            "ertek": v,
        },
        prioritas=10,
        verzio=1,
        allapot=RuleState.ACTIVE.value if aktiv else RuleState.PENDING.value,
        forras_esetek={"rekordok": [e.get("rekord") for e in c.get("esetek") or []]},
    )


def papir_tudas_tartalom(k: LaraKerdes, valasz_tipus: str) -> str:
    c = k.kontextus or {}
    t, dim = c.get("terulet"), c.get("dimenzio")
    v = (c.get("valosag") or {}).get("szoveg")
    n = len(c.get("esetek") or [])
    if valasz_tipus == "kivetel":
        return f"„{k.partner_nev}” {PAPIR_CIMKE.get(t, t)}: {n} esetben egyszeri kivétel ({DIMENZIO_CIMKE.get(dim, dim)}: {v}). Nem általános."
    return f"„{k.partner_nev}” {PAPIR_CIMKE.get(t, t)} — {DIMENZIO_CIMKE.get(dim, dim)}: {v}."
