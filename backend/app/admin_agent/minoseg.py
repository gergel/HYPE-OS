"""Lara VALÓS minőségmérése (2026-09, F fázis) — öt KÜLÖN mérőszám.

A Tudásháló százaléka a kapcsolatok BIZONYÍTÉK-ERŐSSÉGE, nem feladat-
pontosság; ezért itt nem szerepel, és nem is keverjük vele. Minden mérőszám
mellett ott a mintaszám (n); n = 0 esetén „nincs adat”, nem 0%.

1. `tudas_megtalalasa`: a kérdésekhez talált-e releváns, jóváhagyott tudást
   (az ÉRTÉKELT beszélgetés-válaszokon: hivatkozott-e tudásra, és helyesnek
   értékelték-e).
2. `uj_eseteken`: helyesség ÚJ, nem látott eseteken — a Tudáspróba
   vizsgaügyein (vak jóslat) és az önellenőrzés legutóbbi körén. A
   „szennyezett” jelölés megmarad.
3. `emberi_javitas`: Lara javaslatainak mekkora részét kellett embernek
   javítania (az elmúlt `NAPOK` napban).
4. `indokolt_kerdezes`: Lara kérdéseiből hány vezetett tudáshoz vagy
   rögzítési hiba feltárásához, és hányat vetettek el feleslegesként.
5. `tanulasi_keses`: mennyi idő telik el a tudás keletkezésétől addig, hogy a
   döntésben használható lesz (medián, perc), forrás-fajtánként.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import median

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.admin_agent import (
    ActionProposal,
    Correction,
    LaraBeszelgetesUzenet,
    LaraKerdes,
    LearningRun,
    MemoryChunk,
)

NAPOK = 30


def _arany(szamlalo: int, nevezo: int) -> float | None:
    return round(szamlalo / nevezo, 3) if nevezo else None


def tudas_megtalalasa(db: Session, tol: datetime) -> dict:
    sorok = db.scalars(
        select(LaraBeszelgetesUzenet).where(
            LaraBeszelgetesUzenet.szerep == "lara", LaraBeszelgetesUzenet.ertekeles.is_not(None),
            LaraBeszelgetesUzenet.created_at >= tol,
        )
    ).all()
    sorok = [u for u in sorok if (u.adat or {}).get("tipus") is None]  # a tanítás-üzenetek nem válaszok
    hivatkozott = [u for u in sorok if (u.adat or {}).get("hivatkozott")]
    talalt = [u for u in sorok if (u.adat or {}).get("felhasznalt_tudas")]
    return {
        "n": len(sorok),
        "talalt_tudast": _arany(len(talalt), len(sorok)),
        "hivatkozott_tudasra": _arany(len(hivatkozott), len(sorok)),
        "helyes_ha_hivatkozott": _arany(sum(1 for u in hivatkozott if u.ertekeles == "helyes"), len(hivatkozott)),
        "helyes_osszes": _arany(sum(1 for u in sorok if u.ertekeles == "helyes"), len(sorok)),
        "leiras": "Értékelt „Kérdezz Larától” válaszok: talált-e jóváhagyott tudást, hivatkozott-e rá, "
                  "és helyesnek értékelték-e.",
    }


def uj_eseteken(db: Session) -> dict:
    proba = db.scalar(
        select(LearningRun).where(LearningRun.trigger == "tudasproba:szamla").order_by(LearningRun.id.desc())
    )
    onell = db.scalar(
        select(LearningRun).where(LearningRun.trigger.like("onellenorzes%")).order_by(LearningRun.id.desc())
    )
    p = proba.osszefoglalo if proba else {}
    return {
        "tudasproba": {
            "n": (p or {}).get("esetszam", 0),
            "lefedettseg": (p or {}).get("lefedettseg"),
            "pontossag": (p or {}).get("pontossag"),
            "szennyezett": (p or {}).get("szennyezett"),
            "ido": proba.veg_at.isoformat() if proba and proba.veg_at else None,
        },
        "onellenorzes_teruletek": {
            t: {"talalati_arany": d.get("talalati_arany"), "n": d.get("ellenorzott")}
            for t, d in (((onell.osszefoglalo or {}).get("teruletek") or {}).items() if onell else [])
        },
        "leiras": "Helyesség olyan eseteken, amelyeket Lara nem látott tanításként (Tudáspróba: vak jóslat "
                  "a vizsgaügyeken; önellenőrzés: jóslat a rögzített munkán).",
    }


def emberi_javitas(db: Session, tol: datetime) -> dict:
    javaslatok = db.scalar(select(func.count(ActionProposal.id)).where(ActionProposal.created_at >= tol)) or 0
    javitott = db.scalar(
        select(func.count(func.distinct(Correction.proposal_id))).where(
            Correction.created_at >= tol, Correction.proposal_id.is_not(None)
        )
    ) or 0
    return {
        "n": javaslatok,
        "javitott_arany": _arany(javitott, javaslatok),
        "javitott": javitott,
        "leiras": f"Az elmúlt {NAPOK} nap Lara-javaslataiból hányat kellett embernek javítania.",
    }


def indokolt_kerdezes(db: Session, tol: datetime) -> dict:
    sorok = db.scalars(
        select(LaraKerdes).where(LaraKerdes.allapot != "nyitott", LaraKerdes.megvalaszolva_at >= tol)
    ).all()
    tanito = sum(1 for k in sorok if k.valasz_tipus in ("mindig", "magyarazat", "kivetel"))
    hiba = sum(1 for k in sorok if k.valasz_tipus == "hibas")
    elvetett = sum(1 for k in sorok if k.allapot == "elvetve")
    return {
        "n": len(sorok),
        "indokolt_arany": _arany(tanito + hiba, len(sorok)),
        "tudashoz_vezetett": tanito,
        "rogzitesi_hibat_tart_fel": hiba,
        "felesleges": elvetett,
        "leiras": f"Az elmúlt {NAPOK} napban megválaszolt kérdések: tanulság vagy rögzítési hiba lett belőle, "
                  "vagy feleslegesként elvetették.",
    }


def tanulasi_keses(db: Session, tol: datetime) -> dict:
    sorok = db.scalars(
        select(MemoryChunk).where(MemoryChunk.felhasznalhato_at >= tol, MemoryChunk.created_at.is_not(None))
    ).all()
    csoport: dict[str, list[float]] = {}
    for m in sorok:
        f = (m.forras or "").split(":", 1)[0] or "egyeb"
        f = {"correction": "javitas_magyarazat", "kerdes": "kerdesre_valasz", "tanitas": "tanitas",
             "megfigyeles": "megfigyelt_eset", "visszajatszas": "szamla_eset"}.get(f, f)
        perc = (m.felhasznalhato_at - m.created_at).total_seconds() / 60
        csoport.setdefault(f, []).append(max(0.0, perc))
    return {
        "n": len(sorok),
        "median_perc": round(median([p for v in csoport.values() for p in v]), 1) if sorok else None,
        "forrasonkent": {k: {"n": len(v), "median_perc": round(median(v), 1)} for k, v in sorted(csoport.items())},
        "leiras": "A tudás keletkezésétől a használhatóvá válásáig eltelt idő (a 2026-09-es bővítés óta mérve).",
    }


def meres(db: Session) -> dict:
    tol = datetime.now(timezone.utc) - timedelta(days=NAPOK)
    return {
        "idoszak_nap": NAPOK,
        "tudas_megtalalasa": tudas_megtalalasa(db, tol),
        "uj_eseteken": uj_eseteken(db),
        "emberi_javitas": emberi_javitas(db, tol),
        "indokolt_kerdezes": indokolt_kerdezes(db, tol),
        "tanulasi_keses": tanulasi_keses(db, tol),
        "megjegyzes": "A Tudásháló százaléka a kapcsolatok bizonyíték-erőssége — nem feladat-pontosság, ezért itt "
                      "nem szerepel.",
    }
