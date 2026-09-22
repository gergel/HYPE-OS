"""Admin-Ágens — megfigyelő (projektkód / utókövetés).

A projektkódokon és az utókövetésben történik a szerződések, TIG-ek és a
számlás/kiadási lépések emberi munkája. Ez a modul EZT figyeli, hogy az ügynök
tanulni tudjon belőle — biztonságosan:

* NEM akaszkodik rá a mentési útvonalra (nincs flush-hook): egy külön,
  ütemezett/kézi FUTÁS olvassa a nemrég változott rekordokat (`updated_at`).
* Csak OLVAS és az ágens saját táblái írnak: forrásesemény
  (`aa_source_events`, forras="megfigyeles"), emberi nyomvonal
  (`aa_action_traces`, szereplo="human") és példa-JELÖLT (`aa_memory_chunks`,
  ervenyes=False). Üzleti rekord nem változik.
* Idempotens: egy rekord egy verziója (tábla:id + updated_at) egyszer kerül
  rögzítésre. Rekordonként EGY példa-jelölt van; újrafuttatáskor a még jóvá nem
  hagyott jelölt szövege frissül (pl. javított leírás-logika után).
* Engedélyhez kötött: csak ha az admin bekapcsolta a „Tanulás és megfigyelés"
  forrást (`engedett_forrasok.megfigyeles`). Első futáskor korlátozott
  visszatekintés.

A PROJEKTKÓD feloldása: a TIG/szerződés jellemzően a PROJEKTEN át kötődik a
projektkódhoz (project_id → projects.project_code_id), nem közvetlenül — ezt is
követjük, különben tévesen „projektkód nélküli" lenne a leírás.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.admin_agent.enums import ActorKind
from app.admin_agent.settings_service import get_settings
from app.models.admin_agent import ActionTrace, MemoryChunk, SourceEvent
from app.models.contract import Contract
from app.models.employee import Employee
from app.models.finance import Expense
from app.models.internal_performance_certificate import InternalPerformanceCertificate
from app.models.performance_certificate import PerformanceCertificate
from app.models.project import Project
from app.models.project_code import ProjectCode

FORRAS = "megfigyeles"
#: Első futáskor ennyi napra tekint vissza (nem a teljes előzmény).
ALAP_VISSZATEKINTES_NAP = 7
#: Egy futás legfeljebb ennyi rekordot dolgoz fel típusonként.
MAX_REKORD = 2000

#: Az emberi munka „lezárt" állapotai (PONTOS egyezés, kisbetűsítve —
#: a „Készítés alatt" NEM lezárt, pedig tartalmazza a „kész" szót).
LEZART_ALLAPOTOK = {"kiküldve", "aláírva", "kész", "elkészült", "lezárva", "teljesítve", "elfogadva"}


def _most() -> datetime:
    return datetime.now(timezone.utc)


def _szoveg(v: Any) -> str | None:
    if isinstance(v, str) and v.strip():
        return v.strip()
    return None


class _Kontextus:
    """Cache-elt feloldások egy futáson belül (projektkód, projekt, dolgozó)."""

    def __init__(self, db: Session):
        self.db = db
        self._kodok: dict[int, str | None] = {}
        self._projektek: dict[int, tuple[int | None, str | None]] = {}
        self._emberek: dict[int, str | None] = {}

    def projektkod(self, pc_id: int | None) -> str | None:
        if pc_id is None:
            return None
        if pc_id not in self._kodok:
            pc = self.db.get(ProjectCode, pc_id)
            self._kodok[pc_id] = (pc.projektkod if pc is not None else None) or f"#{pc_id}"
        return self._kodok[pc_id]

    def projekt(self, p_id: int | None) -> tuple[int | None, str | None]:
        """(projektkód-id, projektnév) egy projektből."""
        if p_id is None:
            return None, None
        if p_id not in self._projektek:
            p = self.db.get(Project, p_id)
            self._projektek[p_id] = (p.project_code_id, _szoveg(p.nev)) if p is not None else (None, None)
        return self._projektek[p_id]

    def ember(self, e_id: int | None) -> str | None:
        if e_id is None:
            return None
        if e_id not in self._emberek:
            e = self.db.get(Employee, e_id)
            self._emberek[e_id] = _szoveg(getattr(e, "full_name", None)) if e is not None else None
        return self._emberek[e_id]

    def kod_es_projekt(self, pc_id: int | None, p_id: int | None) -> tuple[int | None, str | None, str | None]:
        """Projektkód közvetlenül VAGY a projekten át. Vissza: (pc_id, kód, projektnév)."""
        projekt_pc, projekt_nev = self.projekt(p_id)
        vegso = pc_id if pc_id is not None else projekt_pc
        return vegso, self.projektkod(vegso), projekt_nev


@dataclass(frozen=True)
class Figyelt:
    kulcs: str  # a forrásazonosító előtagja
    model: Any
    tipus: str  # az ágens feladattípusa, amihez a tanulság tartozik
    cimke: str  # emberi olvasásra
    leiro: Callable[[_Kontextus, Any], dict]  # a rekord kontextusa (projektkód, partner, tárgy...)
    lezart: Callable[[Any], bool]


def _allapot_lezart(v: Any) -> bool:
    return isinstance(v, str) and v.strip().lower() in LEZART_ALLAPOTOK


def _szerzodes(k: _Kontextus, r: Contract) -> dict:
    pc_id, kod, projekt = k.kod_es_projekt(r.project_code_id, r.project_id)
    return {
        "project_code_id": pc_id,
        "projektkod": kod,
        "projekt": projekt,
        "partner": _szoveg(r.ceg_neve) or _szoveg(r.nev) or k.ember(r.employee_id),
        "targy": _szoveg(r.megbizas_targya),
        "allapot": _szoveg(r.szerzodes_allapota),
        "osszeg": r.netto_osszeg,
        "extra": f"típus: {r.tipus}" if getattr(r, "tipus", None) else None,
    }


def _tig(k: _Kontextus, r: PerformanceCertificate) -> dict:
    pc_id, kod, projekt = k.kod_es_projekt(r.project_code_id, r.project_id)
    teljesites = _szoveg(r.teljesites_szoveg)
    if not teljesites and r.teljesites_kezdete:
        teljesites = r.teljesites_kezdete.isoformat() + (f"–{r.teljesites_vege.isoformat()}" if r.teljesites_vege else "")
    return {
        "project_code_id": pc_id,
        "projektkod": kod,
        "projekt": projekt,
        "partner": _szoveg(r.ceg_neve) or k.ember(r.employee_id),
        "targy": _szoveg(r.megbizas_targya),
        "allapot": _szoveg(r.allapot),
        "osszeg": r.netto_osszeg,
        "extra": f"teljesítés: {teljesites}" if teljesites else None,
    }


def _belsos_tig(k: _Kontextus, r: InternalPerformanceCertificate) -> dict:
    return {
        "project_code_id": None,
        # A belsős TIG HAVI, dolgozóhoz kötött — nem projektkódos (ez nem hiba).
        "projektkod": None,
        "projekt": None,
        "idoszak": f"{r.ev}.{int(r.honap):02d}" if r.ev and r.honap else None,
        "partner": k.ember(r.employee_id),
        "targy": _szoveg(r.megbizas_targya),
        "allapot": _szoveg(r.allapot),
        "osszeg": r.netto_osszeg,
        "extra": None,
    }


def _kiadas(k: _Kontextus, r: Expense) -> dict:
    pc_id, kod, projekt = k.kod_es_projekt(r.project_code_id, r.alvallalkozo_project_id)
    return {
        "project_code_id": pc_id,
        "projektkod": kod,
        "projekt": projekt,
        "partner": _szoveg(r.megnevezes),
        "targy": _szoveg(r.kiadas_leiras),
        "allapot": "kifizetve" if r.kesz else (_szoveg(r.szamla_statusza) or "nyitott"),
        "osszeg": r.netto,
        "extra": f"típus: {r.tipus}" if _szoveg(r.tipus) else None,
    }


FIGYELT: tuple[Figyelt, ...] = (
    Figyelt("szerzodes", Contract, "szerzodes", "szerződés", _szerzodes, lambda r: _allapot_lezart(r.szerzodes_allapota)),
    Figyelt("tig", PerformanceCertificate, "tig", "TIG", _tig, lambda r: _allapot_lezart(r.allapot)),
    Figyelt("belsos_tig", InternalPerformanceCertificate, "tig", "belsős TIG", _belsos_tig, lambda r: _allapot_lezart(r.allapot)),
    Figyelt("kiadas", Expense, "szamla", "kiadás/számla", _kiadas, lambda r: bool(r.kesz)),
)


def engedelyezve(db: Session) -> bool:
    s = get_settings(db)
    return bool((s.engedett_forrasok or {}).get(FORRAS))


def _penz(v: Any) -> str | None:
    if v is None:
        return None
    try:
        return f"{float(v):,.0f} Ft".replace(",", " ")
    except (TypeError, ValueError):
        return None


def leiras(f: Figyelt, meta: dict) -> str:
    """Emberileg olvasható, tömör leírás a példához (ebből tanul az ügynök)."""
    if meta.get("projektkod"):
        hely = meta["projektkod"] + (f" · {meta['projekt']}" if meta.get("projekt") else "")
    elif f.kulcs == "belsos_tig":
        hely = "Belsős (havi) TIG" + (f" {meta['idoszak']}" if meta.get("idoszak") else "")
    elif meta.get("projekt"):
        hely = f"Projekt: {meta['projekt']} (projektkód nélkül)"
    else:
        hely = "Projektkód nélkül"
    reszek = [f"{hely} — {f.cimke}"]
    if meta.get("partner"):
        reszek[0] += f": {meta['partner']}"
    if meta.get("targy"):
        reszek.append(f"tárgy: „{meta['targy']}”")
    reszek.append(f"állapot: {meta.get('allapot') or 'lezárt'}")
    if _penz(meta.get("osszeg")):
        reszek.append(f"nettó {_penz(meta['osszeg'])}")
    if meta.get("extra"):
        reszek.append(meta["extra"])
    return ", ".join(reszek) + "."


def _utolso_ido(db: Session) -> datetime | None:
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
    nem kényszerített (kézi) a futás, nem csinál semmit."""
    if not kenyszeritett and not engedelyezve(db):
        return {"engedelyezve": False, "uj_megfigyeles": 0, "uj_pelda": 0, "frissitett_pelda": 0}

    utolso = _utolso_ido(db)
    if visszatekintes_nap is not None:
        tol = _most() - timedelta(days=visszatekintes_nap)
    elif utolso is not None:
        tol = utolso - timedelta(hours=1)  # átfedés; a dedup az egyedi kulcson
    else:
        tol = _most() - timedelta(days=ALAP_VISSZATEKINTES_NAP)

    k = _Kontextus(db)
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
            meta = f.leiro(k, r)
            meta["osszeg"] = float(meta["osszeg"]) if meta.get("osszeg") is not None else None
            meta.update({"tabla": f.kulcs, "rekord_id": r.id, "updated_at": verzio})

            # Idempotens forrásesemény (tábla:id + verzió) SAVEPOINT-ban.
            uj = True
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
                uj = False  # ez a verzió már rögzítve — nincs új megfigyelés

            if uj:
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

            if not f.lezart(r):
                continue
            # Lezárt emberi munkából példa-JELÖLT (egy rekord = egy jelölt).
            tartalom = leiras(f, meta)
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
            elif not pelda.visszavont and (pelda.tartalom != tartalom or pelda.forras_verzio != verzio):
                # A még jóvá nem hagyott jelölt szövege frissül; a JÓVÁHAGYOTT
                # példa tartalmát csak akkor írjuk, ha maga a rekord változott
                # (új verzió) — ilyenkor újra jelölt lesz, hogy ember nézze át.
                if pelda.ervenyes and pelda.forras_verzio == verzio:
                    continue
                if pelda.ervenyes:
                    pelda.ervenyes = False
                    pelda.minosites = "jelolt"
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
