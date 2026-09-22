"""Admin-Ágens — megfigyelő (projektkód / utókövetés).

A projektkódokon és az utókövetésben történik a szerződések, TIG-ek és a
számlás/kiadási lépések emberi munkája. Ez a modul EZT figyeli, hogy az ügynök
tanulni tudjon belőle — biztonságosan:

* NEM akaszkodik rá a mentési útvonalra (nincs flush-hook): egy külön,
  ütemezett/kézi FUTÁS olvassa a nemrég változott rekordokat (`updated_at`).
  Így a meglévő mentések sebességét és helyességét semmi nem érinti.
* Csak OLVAS és az ágens saját táblái írnak: forrásesemény
  (`aa_source_events`, forras="megfigyeles"), emberi nyomvonal
  (`aa_action_traces`, szereplo="human") és példa-JELÖLT (`aa_memory_chunks`,
  ervenyes=False). Üzleti rekord nem változik.
* Idempotens: egy rekord egy verziója (tábla:id + updated_at) egyszer kerül
  rögzítésre (a forrásesemény egyedi kulcsa védi). Rekordonként EGY példa-jelölt
  van, ami frissül, ha a rekord tovább változik.
* Engedélyhez kötött: csak ha az admin a Beállításokban bekapcsolta a
  „Tanulás és megfigyelés" forrást (`engedett_forrasok.megfigyeles`). Első
  futáskor csak korlátozott visszatekintés (nem a teljes régi előzmény).
* A példa-jelölt NEM kerül éles döntésbe, amíg ember jóvá nem hagyja
  (Tudástár → Példák).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.admin_agent.enums import ActorKind
from app.admin_agent.settings_service import get_settings
from app.models.admin_agent import ActionTrace, MemoryChunk, SourceEvent
from app.models.contract import Contract
from app.models.finance import Expense
from app.models.internal_performance_certificate import InternalPerformanceCertificate
from app.models.performance_certificate import PerformanceCertificate
from app.models.project_code import ProjectCode

FORRAS = "megfigyeles"
#: Első futáskor ennyi napra tekint vissza (nem a teljes előzmény).
ALAP_VISSZATEKINTES_NAP = 7
#: Egy futás legfeljebb ennyi rekordot dolgoz fel típusonként.
MAX_REKORD = 500

#: Az emberi munka „lezárt" állapotai (PONTOS egyezés, kisbetűsítve —
#: a „Készítés alatt" NEM lezárt, pedig tartalmazza a „kész" szót).
LEZART_ALLAPOTOK = {"kiküldve", "aláírva", "kész", "elkészült", "lezárva", "teljesítve", "elfogadva"}


@dataclass(frozen=True)
class Figyelt:
    kulcs: str  # a forrásazonosító előtagja
    model: Any
    tipus: str  # az ágens feladattípusa, amihez a tanulság tartozik
    cimke: str  # emberi olvasásra
    allapot_mezo: str | None
    osszeg_mezo: str | None
    nev_mezok: tuple[str, ...]


FIGYELT: tuple[Figyelt, ...] = (
    Figyelt("szerzodes", Contract, "szerzodes", "szerződés", "szerzodes_allapota", "netto_osszeg", ("nev", "megnevezes", "targy")),
    Figyelt("tig", PerformanceCertificate, "tig", "TIG", "allapot", "netto_osszeg", ("megnevezes", "nev", "targy")),
    Figyelt("belsos_tig", InternalPerformanceCertificate, "tig", "belsős TIG", "allapot", "netto_osszeg", ("megnevezes", "nev")),
    Figyelt("kiadas", Expense, "szamla", "kiadás/számla", "szamla_statusza", "netto", ("megnevezes", "leiras")),
)


def _most() -> datetime:
    return datetime.now(timezone.utc)


def engedelyezve(db: Session) -> bool:
    s = get_settings(db)
    return bool((s.engedett_forrasok or {}).get(FORRAS))


def _lezart(f: Figyelt, rekord: Any) -> bool:
    if f.model is Expense:
        return bool(getattr(rekord, "kesz", False))
    ertek = getattr(rekord, f.allapot_mezo, None) if f.allapot_mezo else None
    return isinstance(ertek, str) and ertek.strip().lower() in LEZART_ALLAPOTOK


def _nev(f: Figyelt, rekord: Any) -> str | None:
    for m in f.nev_mezok:
        v = getattr(rekord, m, None)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _utolso_ido(db: Session) -> datetime | None:
    """A legutóbb rögzített megfigyelés forrásideje (a következő futás innen
    indul, kis átfedéssel — a duplikációt az egyedi kulcs védi)."""
    se = db.scalar(
        select(SourceEvent).where(SourceEvent.forras == FORRAS).order_by(SourceEvent.id.desc()).limit(1)
    )
    if se is None or not se.metaadat:
        return None
    try:
        return datetime.fromisoformat(se.metaadat.get("updated_at"))
    except (TypeError, ValueError):
        return None


def megfigyeles(db: Session, *, visszatekintes_nap: int | None = None, kenyszeritett: bool = False) -> dict:
    """Egy megfigyelő futás. A hívó commitál. Ha a forrás nincs engedélyezve és
    nem kényszerített (kézi) a futás, nem csinál semmit.

    Vissza: összefoglaló (új megfigyelések, új/frissített példa-jelöltek)."""
    if not kenyszeritett and not engedelyezve(db):
        return {"engedelyezve": False, "uj_megfigyeles": 0, "uj_pelda": 0, "frissitett_pelda": 0}

    utolso = _utolso_ido(db)
    if visszatekintes_nap is not None:
        tol = _most() - timedelta(days=visszatekintes_nap)
    elif utolso is not None:
        tol = utolso - timedelta(hours=1)  # átfedés; a dedup az egyedi kulcson
    else:
        tol = _most() - timedelta(days=ALAP_VISSZATEKINTES_NAP)

    kodok: dict[int, str] = {}

    def projektkod(pid: int | None) -> str | None:
        if pid is None:
            return None
        if pid not in kodok:
            pc = db.get(ProjectCode, pid)
            kodok[pid] = (pc.projektkod if pc is not None else None) or f"#{pid}"
        return kodok[pid]

    uj_megfigyeles = 0
    uj_pelda = 0
    frissitett_pelda = 0
    tipusonkent: dict[str, int] = {}

    for f in FIGYELT:
        rekordok = db.scalars(
            select(f.model)
            .where(f.model.updated_at.is_not(None), f.model.updated_at >= tol)
            .order_by(f.model.updated_at)
            .limit(MAX_REKORD)
        ).all()
        for r in rekordok:
            frissitve = r.updated_at
            azonosito = f"{f.kulcs}:{r.id}"
            verzio = frissitve.isoformat() if frissitve else "ismeretlen"
            pid = getattr(r, "project_code_id", None)
            allapot = getattr(r, f.allapot_mezo, None) if f.allapot_mezo else None
            if f.model is Expense:
                allapot = "kifizetve" if getattr(r, "kesz", False) else (allapot or "nyitott")
            osszeg = getattr(r, f.osszeg_mezo, None) if f.osszeg_mezo else None
            meta = {
                "tabla": f.kulcs,
                "rekord_id": r.id,
                "project_code_id": pid,
                "projektkod": projektkod(pid),
                "allapot": allapot,
                "osszeg": float(osszeg) if osszeg is not None else None,
                "nev": _nev(f, r),
                "updated_at": verzio,
            }

            # Idempotens forrásesemény (tábla:id + verzió). SAVEPOINT-ban, hogy
            # egy ütközés ne görgesse vissza a teljes futást.
            try:
                with db.begin_nested():
                    db.add(
                        SourceEvent(
                            forras=FORRAS,
                            forras_azonosito=azonosito,
                            forras_verzio=verzio,
                            allapot="feldolgozva",
                            metaadat=meta,
                            feldolgozva_at=_most(),
                        )
                    )
            except IntegrityError:
                continue  # ez a verzió már rögzítve — nincs dupla

            uj_megfigyeles += 1
            tipusonkent[f.tipus] = tipusonkent.get(f.tipus, 0) + 1
            db.add(
                ActionTrace(
                    task_id=None,
                    szereplo=ActorKind.HUMAN.value,
                    muvelet="megfigyelt_valtozas",
                    eroforras=azonosito,
                    diff=meta,
                    eredmeny="megfigyelve",
                    tortent_at=frissitve or _most(),
                )
            )

            # Lezárt emberi munkából példa-JELÖLT (egy rekord = egy jelölt).
            if _lezart(f, r):
                tartalom = (
                    f"{meta['projektkod'] or 'projektkód nélkül'}: a(z) {f.cimke}"
                    + (f" „{meta['nev']}”" if meta["nev"] else "")
                    + f" {allapot or 'lezárt'} állapotba került"
                    + (f", nettó {meta['osszeg']:,.0f} Ft".replace(",", " ") if meta["osszeg"] is not None else "")
                    + "."
                )
                forras_ref = f"{FORRAS}:{azonosito}"
                pelda = db.scalar(select(MemoryChunk).where(MemoryChunk.forras == forras_ref))
                if pelda is None:
                    db.add(
                        MemoryChunk(
                            hatokor=f.tipus,
                            tartalom=tartalom,
                            forras=forras_ref,
                            forras_verzio=verzio,
                            minosites="jelolt",
                            tanulasi_halmaz="jovahagyott",
                            ervenyes=False,  # emberi jóváhagyásig NEM használható
                        )
                    )
                    uj_pelda += 1
                elif pelda.forras_verzio != verzio and not pelda.visszavont:
                    pelda.tartalom = tartalom
                    pelda.forras_verzio = verzio
                    frissitett_pelda += 1

    return {
        "engedelyezve": True,
        "tol": tol.isoformat(),
        "uj_megfigyeles": uj_megfigyeles,
        "uj_pelda": uj_pelda,
        "frissitett_pelda": frissitett_pelda,
        "tipusonkent": tipusonkent,
    }
