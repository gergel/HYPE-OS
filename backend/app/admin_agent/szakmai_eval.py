"""Szabályverzióhoz kötött SZAKMAI tesztek (2026-09, F fázis).

A meglévő heti értékelés (evals.py) a biztonsági / pénzügyi invariánsokat
őrzi. Ez a modul azt nézi, hogy EGY SZABÁLY adott VERZIÓJA szakmailag
helyesen viselkedik-e:

- `pozitiv`: a szabály hatókörébe eső eset → a szabály alkalmazandó, és az
  elvárt eredményt adja;
- `ellenpelda`: hasonló, de a hatókörön KÍVÜLI eset (más partner, vagy
  kivétel) → a szabály NEM alkalmazható;
- `hianyos`: hiányzó adat (pl. nincs partner) → a szabály nem dönthet.

Az esetek a szabály verziójához kötöttek (`szabaly_id` + `szabaly_verzio`):
ha a szabály szövege / feltétele változik, a régi esetek nem igazolják az új
verziót.

ÉLESÍTÉSI KAPU (lásd routes: PATCH /rules/{id}): ha a szabály aktuális
verziójához van szakmai eset, az élesítéshez MIND át kell mennie. Ha nincs,
az élesítés a korábbi feltételekkel mehet, de a felület jelzi, hogy nincs
szakmai teszt.

Gépileg csak a partnerhez kötött számla-szabály (`cel_tipus`) és a
papír-szabály (`mezo` + `ertek`) értékelhető; a többi „nem gépi”.
"""

from __future__ import annotations

from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.admin_agent import EvalCase, PlaybookRule, SourceEvent

FAJTAK = ("pozitiv", "ellenpelda", "hianyos")
FORRAS = "szakmai_eval"


class SzakmaiHiba(ValueError):
    pass


def gepi(r: PlaybookRule) -> bool:
    f = r.feltetelek or {}
    return bool(f.get("partner")) and (bool(f.get("cel_tipus")) or ("mezo" in f and "ertek" in f))


def alkalmaz(r: PlaybookRule, bemenet: dict) -> dict:
    """A szabály determinisztikus alkalmazása egy esetre. Vissza:
    {"alkalmazhato": bool, "eredmeny": {...} | None, "ok": str}."""
    from app.admin_agent.memory import partner_kulcs

    f = r.feltetelek or {}
    partner = bemenet.get("partner")
    if not partner or len(partner_kulcs(partner)) < 3:
        return {"alkalmazhato": False, "eredmeny": None, "ok": "hiányzó partner"}
    pk = partner_kulcs(partner)
    if pk != f.get("partner"):
        return {"alkalmazhato": False, "eredmeny": None, "ok": "más partner"}
    if pk in {partner_kulcs(k) for k in (f.get("kivetel_partnerek") or [])} or bemenet.get("kivetel"):
        return {"alkalmazhato": False, "eredmeny": None, "ok": "kivétel"}
    if f.get("cel_tipus"):
        return {"alkalmazhato": True, "eredmeny": {"cel_tipus": f["cel_tipus"]}, "ok": "partner egyezik"}
    return {"alkalmazhato": True, "eredmeny": {f["mezo"]: f["ertek"]}, "ok": "partner egyezik"}


def _ertekel(r: PlaybookRule, c: EvalCase) -> tuple[bool, dict]:
    a = alkalmaz(r, c.bemenet or {})
    elvart = c.elvart or {}
    if c.eset_fajta == "pozitiv":
        ok = a["alkalmazhato"] and all((a["eredmeny"] or {}).get(k) == v for k, v in elvart.items())
    else:  # ellenpelda / hianyos: NEM szabad alkalmazni
        ok = not a["alkalmazhato"]
    return ok, a


def esetek(db: Session, r: PlaybookRule, *, csak_aktualis: bool = True) -> list[EvalCase]:
    felt = [EvalCase.szabaly_id == r.id, EvalCase.ervenyes.is_(True)]
    if csak_aktualis:
        felt.append(EvalCase.szabaly_verzio == r.verzio)
    return list(db.scalars(select(EvalCase).where(*felt).order_by(EvalCase.id)).all())


def futtat(db: Session, r: PlaybookRule) -> dict:
    """A szabály aktuális verziójának szakmai tesztje."""
    if not gepi(r):
        return {"gepi": False, "esetszam": 0, "atment": None, "esetek": [],
                "uzenet": "Ez a szabály gépileg nem tesztelhető (nincs partner + céltípus / mező)."}
    sorok = []
    for c in esetek(db, r):
        ok, a = _ertekel(r, c)
        sorok.append({"id": c.id, "nev": c.nev, "fajta": c.eset_fajta, "bemenet": c.bemenet, "elvart": c.elvart,
                      "kapott": a, "ok": ok})
    fajtak = Counter(s["fajta"] for s in sorok)
    return {
        "gepi": True,
        "szabaly_verzio": r.verzio,
        "esetszam": len(sorok),
        "fajtak": dict(fajtak),
        "atment": all(s["ok"] for s in sorok) if sorok else None,
        "hianyzo_fajta": [f for f in FAJTAK if not fajtak.get(f)],
        "esetek": sorok,
    }


def uj_eset(db: Session, r: PlaybookRule, *, fajta: str, bemenet: dict, elvart: dict | None, nev: str | None = None,
            forras: str = "kezi") -> EvalCase:
    if fajta not in FAJTAK:
        raise SzakmaiHiba("Ismeretlen esetfajta.")
    c = EvalCase(
        nev=(nev or f"{r.cim[:120]} — {fajta}")[:200], tipus="szakmai", altipus=r.hatokor,
        bemenet=bemenet or {}, elvart=elvart, halmaz="szintetikus", forras=f"{FORRAS}:{forras}"[:120],
        ervenyes=True, szabaly_id=r.id, szabaly_verzio=r.verzio, eset_fajta=fajta,
    )
    db.add(c)
    db.flush()
    return c


def esetek_generalasa(db: Session, r: PlaybookRule) -> dict:
    """Kiinduló szakmai esetek a szabály aktuális verziójához (idempotens):
    - pozitív: a szabály partnere (ha van forráseset, annak adataival);
    - ellenpélda: egy MÁSIK partner valós esete, amely máshová került;
    - hiányos: partner nélküli bemenet.
    A generált esetet ember átnézheti / kiegészítheti (pl. kivétel-esettel)."""
    if not gepi(r):
        raise SzakmaiHiba("Ez a szabály gépileg nem tesztelhető.")
    f = r.feltetelek or {}
    meglevo = {c.eset_fajta for c in esetek(db, r)}
    elvart = {"cel_tipus": f["cel_tipus"]} if f.get("cel_tipus") else {f["mezo"]: f["ertek"]}
    uj = 0
    if "pozitiv" not in meglevo:
        uj_eset(db, r, fajta="pozitiv", bemenet={"partner": f.get("partner_nev") or f["partner"]}, elvart=elvart,
                forras="generalt")
        uj += 1
    if "ellenpelda" not in meglevo:
        masik = None
        if f.get("cel_tipus"):
            for se in db.scalars(
                select(SourceEvent).where(SourceEvent.forras == "visszajatszas").order_by(SourceEvent.id.desc()).limit(500)
            ).all():
                m = se.metaadat or {}
                if m.get("partner_kulcs") and m["partner_kulcs"] != f["partner"] and (m.get("vegso") or {}).get("tipus") \
                        and m["vegso"]["tipus"] != f["cel_tipus"]:
                    masik = m.get("partner")
                    break
        uj_eset(db, r, fajta="ellenpelda", bemenet={"partner": masik or "Teljesen más partner (demó) Kft."},
                elvart={"alkalmazhato": False}, forras="generalt")
        uj += 1
    if "hianyos" not in meglevo:
        uj_eset(db, r, fajta="hianyos", bemenet={"partner": None}, elvart={"alkalmazhato": False}, forras="generalt")
        uj += 1
    db.flush()
    return {"uj_eset": uj, **futtat(db, r)}


def elesitesi_kapu(db: Session, r: PlaybookRule) -> tuple[bool, str | None]:
    """(élesíthető-e, ha nem: miért). Nincs szakmai eset → nem blokkol."""
    if not gepi(r):
        return True, None
    e = futtat(db, r)
    if e["esetszam"] == 0:
        return True, None
    if not e["atment"]:
        hibas = [s["nev"] for s in e["esetek"] if not s["ok"]][:3]
        return False, "A szabály szakmai tesztje nem ment át: " + "; ".join(hibas)
    return True, None
