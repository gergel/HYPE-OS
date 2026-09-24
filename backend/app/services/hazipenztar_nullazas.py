"""A HÁZIPÉNZTÁR NULLÁZÁSA - minden készpénzes tétel törlése, tiszta lappal.

A felhasználó kérése (2026-09-24): a házipénztár induljon NULLÁRÓL, mintha még
egyetlen készpénz-felvétel és -költés sem történt volna, és onnan vezessék fel
újra. Ezért MINDEN készpénzes tétel törlődik, bárhol is van:

- a `kp_forgalmak` tábla MINDEN sora (a Notionből örökölt is);
- minden KÉSZPÉNZES kiadás (`Expense.kifizetes_modja` = készpénz), kifizetett
  és függő egyaránt;
- a régi ATM-felvételekhez automatikusan létrehozott "Bankkártya" kiadás-sorok
  (az átvezetés mostantól nem csinál kiadást, lásd services/kassza.py);
- minden KÉSZPÉNZES bevétel (`Revenue.fizetes_modja` = készpénz).

MI TÖRTÉNIK A RÁJUK MUTATÓ REKORDOKKAL? Ugyanaz, mint egy kézi törlésnél:

- a kiadást létrehozó TIG „nincs kifizetve” állapotba kerül (lásd
  services/kiadas_kapcsolatok.py) - újra rögzíthető, és akkor újra létrejön;
- a projektkód megrendelői számlájának „Kifizetve” jelölése visszaáll - a
  projektkód újra kintlévőségként látszik, amíg a készpénzes kifizetést újra
  rögzítik (az akkor újra bevételt ÉS házipénztár-sort csinál);
- a portál-fizetés és a havi tétel hivatkozása leold, maguk megmaradnak.

A FELTÖLTÖTT FÁJLOK A TÁRHELYEN MARADNAK: csak a csatolmány-sor törlődik, a
fájl nem - a mentésben ott a helye (storage_key, url), tehát egy számla sosem
vész el végleg.

MENTÉS: a végrehajtás előtt MINDEN törlendő sor (és csatolmány-adata) egy
JSON-mentésbe kerül, amit a végpont visszaad, és - ha van tárhely - fel is
tölt. Ebből bármelyik tétel visszaállítható.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.document_attachment import DocumentAttachment
from app.models.finance import Expense, KpForgalom, Revenue
from app.models.portal import Payment
from app.services import document_storage, elszamolas, kiadas_kapcsolatok
from app.services import fizetesi_mod as fizetesi_mod_szolg

#: A régi ATM-felvételhez automatikusan létrehozott kiadás-sor leírása (lásd
#: a megszűnt routes/finance._kp_felvetel_kiadas_sorral).
ATM_KIADAS_LEIRAS = "Készpénzfelvétel a bankszámláról a kasszába (automatikus átvezetés a KP forgalomból)"

#: Ezt kell beírni a végrehajtáshoz - egy véletlen kattintás ne törölhessen.
MEGEROSITES = "NULLÁZÁS"


@dataclass
class Celpontok:
    kp_forgalom: list[KpForgalom] = field(default_factory=list)
    kiadasok: list[Expense] = field(default_factory=list)
    bevetelek: list[Revenue] = field(default_factory=list)


def celpontok(db: Session) -> Celpontok:
    """Mi törlődne - még semmit nem töröl."""
    return Celpontok(
        kp_forgalom=list(db.scalars(select(KpForgalom).order_by(KpForgalom.id)).all()),
        kiadasok=list(
            db.scalars(
                select(Expense)
                .where(
                    or_(
                        fizetesi_mod_szolg.keszpenz_sql(Expense.kifizetes_modja),
                        Expense.kiadas_leiras == ATM_KIADAS_LEIRAS,
                    )
                )
                .order_by(Expense.id)
            ).all()
        ),
        bevetelek=list(
            db.scalars(
                select(Revenue).where(fizetesi_mod_szolg.keszpenz_sql(Revenue.fizetes_modja)).order_by(Revenue.id)
            ).all()
        ),
    )


def _json_ertek(v: Any) -> Any:
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    return v


def _sor(obj: Any) -> dict:
    return {c.name: _json_ertek(getattr(obj, c.key, None)) for c in obj.__table__.columns}


def _csatolmanyok(db: Session, entity_type: str, idk: list[int]) -> list[DocumentAttachment]:
    if not idk:
        return []
    return list(
        db.scalars(
            select(DocumentAttachment).where(
                DocumentAttachment.entity_type == entity_type, DocumentAttachment.entity_id.in_(idk)
            )
        ).all()
    )


def _kifizetesi_csatolmanyok(db: Session, revenue_idk: list[int]) -> list[DocumentAttachment]:
    """A megrendelői számlák, amiknek a „Kifizetve” jelölése a törlendő
    bevételre mutat - ezeket vissza kell állítani."""
    if not revenue_idk:
        return []
    return list(db.scalars(select(DocumentAttachment).where(DocumentAttachment.revenue_id.in_(revenue_idk))).all())


def elonezet(db: Session, c: Celpontok | None = None) -> dict:
    """Darabszám és összeg fajtánként - a megerősítő ablakhoz."""
    c = c or celpontok(db)
    return {
        "kp_forgalom_db": len(c.kp_forgalom),
        "kp_forgalom_osszeg": sum(abs(float(f.forintban or 0)) for f in c.kp_forgalom),
        "kiadas_db": len(c.kiadasok),
        "kiadas_osszeg": sum(elszamolas.brutto_osszeg(e) for e in c.kiadasok),
        "bevetel_db": len(c.bevetelek),
        "bevetel_osszeg": sum(elszamolas.brutto_osszeg(r) for r in c.bevetelek),
        "kifizetes_visszaallitas_db": len(_kifizetesi_csatolmanyok(db, [r.id for r in c.bevetelek])),
        "megerosites": MEGEROSITES,
    }


def mentes(db: Session, c: Celpontok | None = None) -> dict:
    """A törlendő sorok TELJES mentése (JSON-ba írható) - minden oszlop, és a
    csatolmányok adatai a fájl helyével együtt."""
    c = c or celpontok(db)
    kp_idk = [f.id for f in c.kp_forgalom]
    kiadas_idk = [e.id for e in c.kiadasok]
    bevetel_idk = [r.id for r in c.bevetelek]
    return {
        "keszult": datetime.now(timezone.utc).isoformat(),
        "leiras": "Házipénztár nullázása előtti mentés - a törölt sorok és csatolmányaik.",
        "kp_forgalmak": [_sor(f) for f in c.kp_forgalom],
        "kiadasok": [_sor(e) for e in c.kiadasok],
        "bevetelek": [_sor(r) for r in c.bevetelek],
        "csatolmanyok": [
            _sor(a)
            for a in _csatolmanyok(db, "kpForgalom", kp_idk)
            + _csatolmanyok(db, "expense", kiadas_idk)
            + _csatolmanyok(db, "autoKiadas", kiadas_idk)
            + _csatolmanyok(db, "revenue", bevetel_idk)
        ],
        "visszaallitott_kifizetesek": [_sor(a) for a in _kifizetesi_csatolmanyok(db, bevetel_idk)],
    }


def vegrehajt(db: Session) -> dict:
    """A nullázás. Előbb ment, aztán töröl - egy tranzakcióban; a commit a
    hívóé."""
    c = celpontok(db)
    osszegzes = elonezet(db, c)
    mentett = mentes(db, c)

    mentes_kulcs = None
    if document_storage.is_configured():
        kulcs = f"mentesek/hazipenztar-nullazas-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}.json"
        document_storage.upload_bytes(
            json.dumps(mentett, ensure_ascii=False, indent=1).encode("utf-8"), kulcs, "application/json"
        )
        mentes_kulcs = kulcs

    kp_idk = [f.id for f in c.kp_forgalom]
    kiadas_idk = [e.id for e in c.kiadasok]
    bevetel_idk = [r.id for r in c.bevetelek]

    # Csatolmány-SOROK törlése (a fájl a tárhelyen marad, lásd fent).
    for a in (
        _csatolmanyok(db, "kpForgalom", kp_idk)
        + _csatolmanyok(db, "expense", kiadas_idk)
        + _csatolmanyok(db, "autoKiadas", kiadas_idk)
        + _csatolmanyok(db, "revenue", bevetel_idk)
    ):
        db.delete(a)

    for f in c.kp_forgalom:
        db.delete(f)
    db.flush()

    for e in c.kiadasok:
        kiadas_kapcsolatok.bontsd_le_a_kapcsolatokat(e, db)
        db.delete(e)

    for a in _kifizetesi_csatolmanyok(db, bevetel_idk):
        a.revenue_id = None
        a.kifizetve_datuma = None
        a.tranzakcio_nelkul_lezarva = False
        a.bevetelbe_ne_keruljon = False
        a.bevetel_kihagyas_oka = None
    if bevetel_idk:
        for p in db.scalars(select(Payment).where(Payment.revenue_id.in_(bevetel_idk))).all():
            p.revenue_id = None
    db.flush()
    for r in c.bevetelek:
        db.delete(r)
    db.flush()

    return {**osszegzes, "mentes_kulcs": mentes_kulcs, "mentes": mentett}
