"""Tudáspróba (2026-09) — Lara tudásának ELLENŐRZÉSE, nem a Tudásháló-%.

Két fajta próba:

1. SZÁMLA-VIZSGA (determinisztikus, modell nélkül):
   - a visszajátszott, ember által jóváhagyott számlák közül a VIZSGAKÉSZLET
     ügyei (lásd ugyek.py: az ügykulcs hash-e szerint, stabilan);
   - Lara VAKON jósol: a tudásából a vizsgaügyek ki vannak véve, és az adott
     számla saját tanulsága sem látszik;
   - a jóslatot a valós rögzítéssel vetjük össze.
   Mérőszámok (külön-külön):
   - lefedettség: hány esetre mert javasolni;
   - pontosság: a javasoltakból hány helyes;
   - „nem tudom”: hányszor tartózkodott jogosan.
   Ha a vizsgakészlet kapcsolója KI volt, a tanító összesítés (megerősítés,
   szabályjavaslat, tapasztalás) láthatta a vizsgaügyeket. Ilyenkor az
   eredmény „szennyezett” jelölést kap, és a szabályból adott jóslat
   esetenként is jelölt.
2. SAJÁT KÉRDÉS: a felhasználó kérdez, és megadhatja az elvárt választ. Lara
   ezt NEM látja; a felhasználó a két választ egymás mellett értékeli.

Csak Lara saját tábláiba ír (futásnapló); üzleti rekordot nem érint.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.admin_agent import LearningRun, SourceEvent

TRIGGER = "tudasproba:szamla"
ALAP_ESETSZAM = 20
MAX_ESETSZAM = 200


def _most() -> datetime:
    return datetime.now(timezone.utc)


def vizsga_esetek(db: Session, arany: float) -> list[dict]:
    """A visszajátszott számlák közül a vizsgakészlet ügyei (legújabb elöl)."""
    from app.admin_agent.onellenorzes import Tudas
    from app.admin_agent.ugyek import vizsga_e

    utolso: dict[str, dict] = {}
    for se in db.scalars(select(SourceEvent).where(SourceEvent.forras == "visszajatszas").order_by(SourceEvent.id)).all():
        m = se.metaadat or {}
        if (m.get("vegso") or {}).get("tipus") and m.get("partner_kulcs") and m.get("bejovo_id"):
            utolso[se.forras_azonosito] = m
    ki = []
    for m in utolso.values():
        eset = (int(m["bejovo_id"]), m["vegso"]["tipus"], tuple(sorted(m["vegso"].get("projektkod_idk") or [])))
        ugy = Tudas.ugy(m["partner_kulcs"], eset)
        if vizsga_e(ugy, arany):
            ki.append({"meta": m, "eset": eset, "ugy": ugy})
    ki.sort(key=lambda x: -x["eset"][0])
    return ki


def szamla_vizsga(db: Session, *, esetszam: int = ALAP_ESETSZAM, inditotta_id: int | None = None) -> dict:
    """Vak jóslat a vizsgaügyeken. A hívó commitál."""
    from app.admin_agent.onellenorzes import Tudas
    from app.admin_agent.ugyek import vizsga_arany, vizsga_e, vizsgakeszlet_be
    from app.admin_agent.visszajatszas import CEL_CIMKE

    esetszam = max(1, min(int(esetszam or ALAP_ESETSZAM), MAX_ESETSZAM))
    arany = vizsga_arany(db)
    kezdes = _most()
    tudas = Tudas(db, kizart=lambda k: vizsga_e(k, arany))
    elkulonitve = vizsgakeszlet_be(db)
    esetek = vizsga_esetek(db, arany)[:esetszam]
    sorok = []
    for x in esetek:
        m, (bid, valos_tipus, valos_kodok) = x["meta"], x["eset"]
        j = tudas.cel(m["partner_kulcs"], kiveve=bid)
        if j is None:
            eredmeny = "nem_tudja"
        elif j["tipus"] != valos_tipus:
            eredmeny = "hibas"
        elif j["kod_idk"] and valos_kodok and tuple(sorted(j["kod_idk"])) != valos_kodok:
            eredmeny = "reszben"  # jó cél, más projektkód
        else:
            eredmeny = "helyes"
        sorok.append({
            "bejovo_id": bid,
            "partner": m.get("partner"),
            "valosag": CEL_CIMKE.get(valos_tipus, valos_tipus),
            "lara": CEL_CIMKE.get(j["tipus"], j["tipus"]) if j else None,
            "forras": j["forras"] if j else None,
            "fajta": j["fajta"] if j else None,
            "eredmeny": eredmeny,
            # A szabályt a megerősítés a vizsgaügyekből is összerakhatta, ha a készlet nem volt elkülönítve.
            "szennyezett_lehet": bool(j and j["fajta"] == "szabaly" and not elkulonitve),
            "link": f"/penzugyek/bejovo-szamlak?id={bid}",
        })
    n = len(sorok)
    helyes = sum(1 for s in sorok if s["eredmeny"] == "helyes")
    reszben = sum(1 for s in sorok if s["eredmeny"] == "reszben")
    hibas = sum(1 for s in sorok if s["eredmeny"] == "hibas")
    nem_tudja = sum(1 for s in sorok if s["eredmeny"] == "nem_tudja")
    javasolt = helyes + reszben + hibas
    osszegzes = {
        "esetszam": n,
        "helyes": helyes,
        "reszben": reszben,
        "hibas": hibas,
        "nem_tudja": nem_tudja,
        "lefedettseg": round(javasolt / n, 3) if n else None,
        "pontossag": round((helyes + 0.5 * reszben) / javasolt, 3) if javasolt else None,
        "szennyezett": not elkulonitve,
        "vizsga_arany": arany,
        "vizsgakeszlet_osszes": len(vizsga_esetek(db, arany)) if n == esetszam else n,
        "esetek": sorok,
        "inditotta_id": inditotta_id,
        "ido_ms": int((_most() - kezdes).total_seconds() * 1000),
    }
    db.add(LearningRun(trigger=TRIGGER, allapot="kesz", kezdes_at=kezdes, veg_at=_most(), osszefoglalo=osszegzes))
    db.flush()
    return osszegzes


def korabbi_futasok(db: Session, limit: int = 10) -> list[dict]:
    sorok = db.scalars(
        select(LearningRun).where(LearningRun.trigger == TRIGGER).order_by(LearningRun.id.desc()).limit(limit)
    ).all()
    return [
        {"id": f.id, "ido": f.veg_at.isoformat() if f.veg_at else None,
         **{k: (f.osszefoglalo or {}).get(k) for k in (
             "esetszam", "helyes", "reszben", "hibas", "nem_tudja", "lefedettseg", "pontossag", "szennyezett")}}
        for f in sorok
    ]
