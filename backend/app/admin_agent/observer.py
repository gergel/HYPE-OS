"""Lara — megfigyelő (projektkód / utókövetés).

A projektkódokon és az utókövetésben történik a szerződések, TIG-ek és a
számlás/kiadási lépések emberi munkája. Ez a modul EZT figyeli, hogy Lara
tanulni tudjon belőle — biztonságosan:

* NEM akaszkodik rá a mentési útvonalra (nincs flush-hook): egy külön,
  ütemezett/kézi FUTÁS olvassa a nemrég változott rekordokat (`updated_at`).
* Csak OLVAS és Lara saját táblái írnak: forrásesemény
  (`aa_source_events`, forras="megfigyeles"), emberi nyomvonal
  (`aa_action_traces`, szereplo="human") és példa-JELÖLT (`aa_memory_chunks`,
  ervenyes=False). Üzleti rekord nem változik.
* Idempotens: egy rekord egy verziója (tábla:id + updated_at) egyszer kerül
  rögzítésre. Rekordonként EGY példa-jelölt van; újrafuttatáskor a még jóvá nem
  hagyott jelölt szövege frissül (pl. javított leírás-logika után).
* Engedélyhez kötött: csak ha az admin bekapcsolta a „Tanulás és megfigyelés"
  forrást (`engedett_forrasok.megfigyeles`). Első futáskor korlátozott
  visszatekintés.
* TANULÁSI KORSZAK: a cég 2026. szeptember 1. óta a HYPE OS felületén dolgozik
  (előtte Notionben). Csak az ettől a naptól itt KELETKEZETT (és nem Notionből
  importált) rekordból lesz példa-jelölt. A régi korszak már meglévő jelöltjei
  félre lesznek téve (nem törlődnek, egyenként jóváhagyhatók), a már jóváhagyott
  régi példák pedig csak az újak után, kisebb súllyal kerülnek elő. A kezdőnap
  a Beállításokban (`limitek.tanulas_kezdete`) állítható.

A PROJEKTKÓD feloldása: a TIG/szerződés jellemzően a PROJEKTEN át kötődik a
projektkódhoz (project_id → projects.project_code_id), nem közvetlenül — ezt is
követjük, különben tévesen „projektkód nélküli" lenne a leírás.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.admin_agent.enums import ActorKind
from app.admin_agent.settings_service import get_settings
from app.models.admin_agent import ActionTrace, MemoryChunk, SourceEvent
from app.models.arajanlat import Arajanlat
from app.models.client import Client
from app.models.contract import Contract
from app.models.employee import Employee
from app.models.finance import Expense, Revenue
from app.models.internal_performance_certificate import InternalPerformanceCertificate
from app.models.megrendeloi_papir import MegrendeloiSzerzodes, MegrendeloiTig, papir_kesz
from app.models.notion_import import NotionImportMap
from app.models.performance_certificate import PerformanceCertificate
from app.models.project import Project
from app.models.project_code import ProjectCode
from app.models.project_code_comment import ProjectCodeComment
from app.models.utalas_felvezetes import UtalasTetel
from app.models.visszavonas import ToroltRekord

FORRAS = "megfigyeles"
#: Első futáskor ennyi napra tekint vissza (nem a teljes előzmény).
ALAP_VISSZATEKINTES_NAP = 7
#: Egy futás legfeljebb ennyi rekordot dolgoz fel típusonként.
MAX_REKORD = 2000

#: A tanulás alapértelmezett kezdete: ettől a naptól dolgozik a cég a HYPE OS
#: felületén. A Beállításokban (`aa_settings.limitek.tanulas_kezdete`) állítható.
ALAP_TANULAS_KEZDETE = date(2026, 9, 1)
#: A régi korszakból származó, még el nem bírált jelölt minősítése.
FELRETEVE = "felreteve"

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
        self._ugyfelek: dict[int, str | None] = {}

    def ugyfel(self, c_id: int | None) -> str | None:
        if c_id is None:
            return None
        if c_id not in self._ugyfelek:
            c = self.db.get(Client, c_id)
            self._ugyfelek[c_id] = _szoveg(c.nev) if c is not None else None
        return self._ugyfelek[c_id]

    def projektkod_megrendelo(self, pc_id: int | None) -> str | None:
        """A projektkód megrendelője (a kód saját mezője, vagy az ügyfél neve)."""
        if pc_id is None:
            return None
        pc = self.db.get(ProjectCode, pc_id)
        if pc is None:
            return None
        return _szoveg(pc.megrendelo_neve) or self.ugyfel(pc.client_id)

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
    tipus: str  # Lara feladattípusa, amihez a tanulság tartozik
    cimke: str  # emberi olvasásra
    leiro: Callable[[_Kontextus, Any], dict]  # a rekord kontextusa (projektkód, partner, tárgy...)
    lezart: Callable[[Any], bool]
    #: Saját leírás-szöveg (ha a sablonos `leiras` nem illik rá, pl. komment).
    szoveg: Callable[[dict], str] | None = None
    #: Rekordonként eltérő feladattípus (pl. a törölt rekord táblája szerint).
    tipus_fn: Callable[[Any], str | None] | None = None
    #: Plusz SQL-szűrés (pl. az árajánlat-SABLON nem tanulság).
    szuro: Any = None
    #: Ennyivel régebbre is visszanéz: ha a rekord csak KÉSŐBB válik lezárttá
    #: (pl. a törlés csak 2 óra után végleges), a következő futások is lássák.
    kesleltetes: timedelta = timedelta(0)


def tanulas_kezdete_datum(db: Session) -> date:
    ertek = (get_settings(db).limitek or {}).get("tanulas_kezdete")
    if isinstance(ertek, str):
        try:
            return date.fromisoformat(ertek[:10])
        except ValueError:
            pass
    return ALAP_TANULAS_KEZDETE


def tanulas_kezdete(db: Session) -> datetime:
    """A tanulás kezdete időpontként (budapesti éjfél)."""
    try:
        from zoneinfo import ZoneInfo

        zona = ZoneInfo("Europe/Budapest")
    except Exception:  # noqa: BLE001 — tzdata nélkül UTC
        zona = timezone.utc
    d = tanulas_kezdete_datum(db)
    return datetime(d.year, d.month, d.day, tzinfo=zona)


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
        "kiadas_tipus": _szoveg(r.tipus),
    }


#: A Notion-import térkép entitásnevei (notion_import_map.entity_type).
_NOTION_ENTITAS = {
    "szerzodes": "Contract",
    "tig": "PerformanceCertificate",
    "belsos_tig": "InternalPerformanceCertificate",
    "kiadas": "Expense",
}

# ── Bővített források (a „gyorsabb tanulás" csomag) ──────────────────────────
# Mind ugyanazon a megfigyelő úton mennek (csak olvas, idempotens, jelöltet
# készít, a tanulás kezdete előtti rekordból nem lesz példa).


def _rovid(v: Any, n: int = 300) -> str | None:
    t = _szoveg(v)
    if t is None:
        return None
    t = " ".join(t.split())
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


def _megrendeloi(k: _Kontextus, r: Any) -> dict:
    """Megrendelői szerződés / TIG — a MINKET fizető fél felé menő papír."""
    reszek = []
    if _szoveg(r.kihagyas_oka):
        reszek.append(f"kihagyva, mert: „{_rovid(r.kihagyas_oka, 200)}”")
    if _szoveg(r.teljesites_szoveg):
        reszek.append(f"teljesítés: {_rovid(r.teljesites_szoveg, 80)}")
    if r.plusz_afa is not None:
        reszek.append("+ÁFA" if r.plusz_afa else "ÁFA nélkül")
    if r.alairt_file_url:
        reszek.append("aláírt példány feltöltve")
    if _szoveg(r.megjegyzes):
        reszek.append(f"megjegyzés: „{_rovid(r.megjegyzes, 200)}”")
    pc_id, kod, projekt = k.kod_es_projekt(r.project_code_id, None)
    return {
        "project_code_id": pc_id,
        "projektkod": kod,
        "projekt": _szoveg(r.projekt_nev) or projekt,
        "partner": _szoveg(r.ceg_neve) or k.ugyfel(r.client_id),
        "targy": _szoveg(r.megbizas_targya),
        "allapot": _szoveg(r.allapot),
        "osszeg": r.netto_osszeg,
        "extra": ", ".join(reszek) or None,
        "plusz_afa": r.plusz_afa,
        "kihagyva": bool(_szoveg(r.kihagyas_oka)) or r.allapot == "Kihagyva",
    }


def _komment(k: _Kontextus, r: ProjectCodeComment) -> dict:
    pc_id, kod, _ = k.kod_es_projekt(r.project_code_id, None)
    pc = k.db.get(ProjectCode, pc_id) if pc_id else None
    return {
        "project_code_id": pc_id,
        "projektkod": kod,
        "projekt": _szoveg(pc.project_nev) if pc is not None else None,
        "partner": k.projektkod_megrendelo(pc_id),
        "szerzo": k.ember(r.employee_id),
        "szoveg": _rovid(r.body, 1200),
        "allapot": "komment",
        "osszeg": None,
    }


def _komment_szoveg(meta: dict) -> str:
    hely = meta.get("projektkod") or "Projektkód"
    if meta.get("projekt"):
        hely += f" · {meta['projekt']}"
    if meta.get("partner"):
        hely += f" (megrendelő: {meta['partner']})"
    ki = meta.get("szerzo") or "A csapat"
    return f"{hely} — {ki} kommentje a projektkódon: „{meta.get('szoveg') or ''}”"


#: A kommentből akkor lesz tanulság, ha van benne tartalom (nem „ok", „köszi").
MIN_KOMMENT_HOSSZ = 25


def _bevetel(k: _Kontextus, r: Revenue) -> dict:
    """Bevétel (a megrendelő fizetése): mikor fizetett a határidőhöz képest."""
    pc_id, kod, projekt = k.kod_es_projekt(r.project_code_id, None)
    pc = k.db.get(ProjectCode, pc_id) if pc_id else None
    reszek = []
    kules: int | None = None
    if r.fizetes_hatarideje and r.fizetes_datuma:
        kules = (r.fizetes_datuma - r.fizetes_hatarideje).days
        if kules > 0:
            reszek.append(f"{kules} nappal a határidő ({r.fizetes_hatarideje.isoformat()}) UTÁN fizetett")
        elif kules < 0:
            reszek.append(f"{-kules} nappal a határidő előtt fizetett")
        else:
            reszek.append("pont a határidőre fizetett")
    elif r.fizetes_datuma:
        reszek.append(f"fizetve: {r.fizetes_datuma.isoformat()}")
    if _szoveg(r.fizetes_modja):
        reszek.append(f"mód: {r.fizetes_modja}")
    if _szoveg(r.bevetel_formaja):
        reszek.append(f"forma: {r.bevetel_formaja}")
    return {
        "project_code_id": pc_id,
        "projektkod": kod,
        "projekt": (_szoveg(pc.project_nev) if pc is not None else None) or projekt,
        "partner": k.projektkod_megrendelo(pc_id),
        "targy": None,
        "allapot": "kifizetve" if r.fizetes_datuma else "nyitott",
        "osszeg": r.netto,
        "extra": ", ".join(reszek) or None,
        "kules_nap": kules,
    }


_UTALAS_CEL = {"kiadas": "kiadásként", "kulsos_tig": "külsős TIG-re", "belsos_tig": "belsős TIG-re", "uj_kiadas": "új kiadásként"}


def _utalas(k: _Kontextus, r: UtalasTetel) -> dict:
    """Utalások felvezetése: egy már elutalt számla, és HOVA sorolta az ember.
    (Lara nem utal — ez a megtörtént utalás könyvelésének tanulsága.)"""
    pc_id = None
    if r.cel_expense_id:
        e = k.db.get(Expense, r.cel_expense_id)
        if e is not None:
            pc_id, _, _ = k.kod_es_projekt(e.project_code_id, e.alvallalkozo_project_id)
    elif r.cel_certificate_id:
        c = k.db.get(PerformanceCertificate, r.cel_certificate_id)
        if c is not None:
            pc_id, _, _ = k.kod_es_projekt(c.project_code_id, c.project_id)
    pc_id, kod, projekt = k.kod_es_projekt(pc_id, None)
    reszek = []
    if r.cel_tipus:
        reszek.append(f"rögzítve {_UTALAS_CEL.get(r.cel_tipus, r.cel_tipus)}")
    if r.elszamolas and r.elszamolas != "tisztazando":
        reszek.append(f"elszámolás: {'Krumpelló' if r.elszamolas == 'krumpello' else 'HYPE'}")
    if r.fizetesi_hatarido and r.utalas_datum:
        kules = (r.utalas_datum - r.fizetesi_hatarido).days
        reszek.append(
            f"{kules} nappal a határidő után utaltuk" if kules > 0
            else ("határidőre utaltuk" if kules == 0 else f"{-kules} nappal a határidő előtt utaltuk")
        )
    if r.osszeg_elteres_elfogadva:
        reszek.append("eltérő összeg / részfizetés elfogadva")
    return {
        "project_code_id": pc_id,
        "projektkod": kod,
        "projekt": projekt,
        "partner": _szoveg(r.kibocsato_nev),
        "targy": f"számla {r.szamlaszam}" if _szoveg(r.szamlaszam) else None,
        "allapot": r.allapot,
        "osszeg": r.netto,
        "extra": ", ".join(reszek) or None,
        "cel_tipus": r.cel_tipus,
        "elszamolas": r.elszamolas,
    }


def _arajanlat(k: _Kontextus, r: Arajanlat) -> dict:
    """Árajánlat → (valószínű) projektkód → számla lánc. Az ajánlat nincs
    közvetlenül projektkódhoz kötve: az ügyfél neve és az időbeli közelség
    alapján keressük meg, és ezt a leírás „valószínű"-ként is mondja."""
    from app.admin_agent.memory import _partner_egyezik, partner_kulcs

    adat = r.adat if isinstance(r.adat, dict) else {}
    tetelek: list[str] = []
    for b in adat.get("blokkok") or []:
        for sz in (b or {}).get("szekciok") or []:
            for t in (sz or {}).get("tetelek") or []:
                nev = _szoveg((t or {}).get("nev"))
                if nev:
                    ar = _szoveg((t or {}).get("egysegar"))
                    tetelek.append(f"{nev}{f' ({ar})' if ar else ''}")
    ugyfel = _szoveg(r.ugyfel) or _szoveg(adat.get("cimzettNev"))
    lanc: list[str] = []
    kulcs = partner_kulcs(ugyfel)
    if len(kulcs) >= 3 and r.created_at is not None:
        tol = (r.created_at - timedelta(days=30)).date()
        ig = (r.created_at + timedelta(days=180)).date()
        for pc in k.db.scalars(
            select(ProjectCode).where(ProjectCode.datum.is_not(None), ProjectCode.datum >= tol, ProjectCode.datum <= ig)
        ).all():
            nev = _szoveg(pc.megrendelo_neve) or k.ugyfel(pc.client_id)
            if nev and _partner_egyezik(kulcs, nev):
                osszeg = _penz(pc.netto_osszeg)
                lanc.append(
                    f"{pc.projektkod}"
                    + (f" ({_szoveg(pc.project_nev)})" if _szoveg(pc.project_nev) else "")
                    + (f", nettó {osszeg}" if osszeg else "")
                    + (f", számla: {pc.szamla_statusza}" if _szoveg(pc.szamla_statusza) else "")
                )
            if len(lanc) >= 3:
                break
    reszek = []
    if tetelek:
        reszek.append("tételek: " + "; ".join(tetelek[:12]) + (" …" if len(tetelek) > 12 else ""))
    if _szoveg(adat.get("kedvezmeny")):
        reszek.append(f"kedvezmény: {adat['kedvezmeny']}")
    reszek.append(
        "valószínű projektkód(ok) ugyanennél az ügyfélnél: " + " | ".join(lanc) if lanc
        else "projektkódot még nem találtam hozzá (ügyfél + időpont alapján)"
    )
    return {
        "project_code_id": None,
        "projektkod": None,
        "projekt": _szoveg(r.nev),
        "partner": ugyfel,
        "targy": _szoveg(r.nev),
        "allapot": "kiadott ajánlat",
        "osszeg": r.vegosszeg,
        "extra": ", ".join(reszek),
        "brand": r.brand,
    }


def _arajanlat_szoveg(meta: dict) -> str:
    fej = f"Árajánlat „{meta.get('targy') or '—'}”"
    if meta.get("partner"):
        fej += f" — ügyfél: {meta['partner']}"
    if _penz(meta.get("osszeg")):
        fej += f", végösszeg {_penz(meta['osszeg'])}"
    return fej + (f". {meta['extra']}." if meta.get("extra") else ".")


#: A törölt rekord táblája → melyik Lara-feladattípus tanulsága.
TOROLT_TABLAK = {
    "contracts": ("szerzodes", "szerződés"),
    "performance_certificates": ("tig", "TIG"),
    "internal_performance_certificates": ("tig", "belsős TIG"),
    "expenses": ("szamla", "kiadás"),
    "revenues": ("kintlevoseg", "bevétel"),
    "megrendeloi_szerzodesek": ("szerzodes", "megrendelői szerződés"),
    "megrendeloi_tigek": ("tig", "megrendelői TIG"),
    "project_codes": ("projektkod", "projektkód"),
    "bejovo_szamlak": ("szamla", "beérkező számla"),
}
#: Ennyi idő után tekintjük a törlést véglegesnek (addig Ctrl+Z-vel visszahozható
#: — a véletlen törlés nem tanulság).
TORLES_VEGLEGES = timedelta(hours=2)
#: A törölt rekord pillanatképéből ezek a mezők írják le, mi volt az.
_TOROLT_MEZOK = (
    "projektkod", "project_nev", "ceg_neve", "nev", "megnevezes", "kibocsato_nev", "megbizas_targya",
    "kiadas_leiras", "szamlaszam", "netto", "netto_osszeg", "allapot", "szerzodes_allapota", "tipus",
)


def _torolt(k: _Kontextus, r: ToroltRekord) -> dict:
    adat = r.adatok if isinstance(r.adatok, dict) else {}
    _, cimke = TOROLT_TABLAK.get(r.tabla, (None, r.tabla))
    pc_id = adat.get("project_code_id") if isinstance(adat.get("project_code_id"), int) else None
    pc_id, kod, projekt = k.kod_es_projekt(pc_id, adat.get("project_id") if isinstance(adat.get("project_id"), int) else None)
    mezok = [f"{m}: {_rovid(adat[m], 120)}" for m in _TOROLT_MEZOK if _szoveg(str(adat[m]) if adat.get(m) is not None else None)]
    elt = None
    try:
        letrejott = datetime.fromisoformat(str(adat.get("created_at")))
        if r.created_at is not None:
            elt = r.created_at - (letrejott if letrejott.tzinfo else letrejott.replace(tzinfo=timezone.utc))
    except (TypeError, ValueError):
        pass
    return {
        "project_code_id": pc_id,
        "projektkod": kod,
        "projekt": projekt,
        "cimke": cimke,
        "tema_kulcs": TOROLT_TABLAK.get(r.tabla, ("projektkod", ""))[0],
        "torolte": k.ember(r.employee_id),
        "mezok": mezok[:8],
        "elt_nap": round(elt.total_seconds() / 86400, 1) if elt is not None else None,
        "partner": _szoveg(adat.get("ceg_neve")) or _szoveg(adat.get("kibocsato_nev")) or _szoveg(adat.get("megnevezes")),
        "allapot": "törölve",
        "osszeg": None,
    }


def _torolt_szoveg(meta: dict) -> str:
    hely = meta.get("projektkod") or "Projektkód nélkül"
    if meta.get("projekt"):
        hely += f" · {meta['projekt']}"
    ki = meta.get("torolte") or "Valaki"
    mikor = ""
    if meta.get("elt_nap") is not None:
        mikor = " a létrehozása után " + (
            "kevesebb mint egy órával" if meta["elt_nap"] < 0.05 else f"{meta['elt_nap']:g} nappal"
        )
    mi = "; ".join(meta.get("mezok") or []) or "részletek nélkül"
    return (
        f"{hely} — {ki} TÖRÖLT egy {meta.get('cimke') or 'rekordot'}{mikor} (és nem hozta vissza). "
        f"Ami törlődött: {mi}. Negatív tanulság: ilyet nem így kellett volna létrehozni."
    )


def _torles_vegleges(r: ToroltRekord) -> bool:
    return (
        not r.visszaallitva
        and r.tabla in TOROLT_TABLAK
        and r.created_at is not None
        and _most() - r.created_at >= TORLES_VEGLEGES
    )


FIGYELT: tuple[Figyelt, ...] = (
    Figyelt("szerzodes", Contract, "szerzodes", "szerződés", _szerzodes, lambda r: _allapot_lezart(r.szerzodes_allapota)),
    Figyelt("tig", PerformanceCertificate, "tig", "TIG", _tig, lambda r: _allapot_lezart(r.allapot)),
    Figyelt("belsos_tig", InternalPerformanceCertificate, "tig", "belsős TIG", _belsos_tig, lambda r: _allapot_lezart(r.allapot)),
    Figyelt("kiadas", Expense, "szamla", "kiadás/számla", _kiadas, lambda r: bool(r.kesz)),
    Figyelt("megrendeloi_szerzodes", MegrendeloiSzerzodes, "szerzodes", "megrendelői szerződés", _megrendeloi, papir_kesz),
    Figyelt("megrendeloi_tig", MegrendeloiTig, "tig", "megrendelői TIG", _megrendeloi, papir_kesz),
    Figyelt(
        "projektkod_komment", ProjectCodeComment, "projektkod", "projektkód-komment", _komment,
        lambda r: len((r.body or "").strip()) >= MIN_KOMMENT_HOSSZ, szoveg=_komment_szoveg,
    ),
    Figyelt("bevetel", Revenue, "kintlevoseg", "bevétel (megrendelői fizetés)", _bevetel, lambda r: r.fizetes_datuma is not None),
    Figyelt(
        "utalas", UtalasTetel, "szamla", "utalás felvezetése", _utalas,
        lambda r: r.rogzitve_at is not None and r.visszavonva_at is None,
    ),
    Figyelt(
        "arajanlat", Arajanlat, "arajanlat", "árajánlat", _arajanlat,
        lambda r: bool(_szoveg(r.ugyfel) or _szoveg((r.adat or {}).get("cimzettNev") if isinstance(r.adat, dict) else None)),
        szoveg=_arajanlat_szoveg, szuro=Arajanlat.sablon.is_(False),
    ),
    Figyelt(
        "torles", ToroltRekord, "projektkod", "törölt rekord", _torolt, _torles_vegleges,
        szoveg=_torolt_szoveg, tipus_fn=lambda r: TOROLT_TABLAK.get(r.tabla, ("projektkod", ""))[0],
        szuro=ToroltRekord.tabla.in_(tuple(TOROLT_TABLAK)), kesleltetes=TORLES_VEGLEGES + timedelta(hours=1),
    ),
)
#: A Tudástár/Tudásháló számára: melyik forrásazonosító-előtag mit jelent.
FORRAS_CIMKEK = {f.kulcs: f.cimke for f in FIGYELT}


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
    """Emberileg olvasható, tömör leírás a példához (ebből tanul Lara)."""
    if f.szoveg is not None:
        return f.szoveg(meta)
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


def _notion_rekordok(db: Session, f: Figyelt, ids: list[int]) -> set[int]:
    """Az adott rekordok közül melyik jött Notion-importból."""
    ki: set[int] = set()
    entitas = _NOTION_ENTITAS.get(f.kulcs)
    if entitas is None:
        return ki  # ez a forrás nem Notionből jött (HYPE OS-ben keletkezett)
    for i in range(0, len(ids), 1000):
        resz = ids[i : i + 1000]
        ki.update(
            db.scalars(
                select(NotionImportMap.entity_id).where(
                    NotionImportMap.entity_type == entitas, NotionImportMap.entity_id.in_(resz)
                )
            ).all()
        )
    return ki


def _regi(keletkezes: datetime | None, notionbol: bool, kezdet: datetime) -> bool:
    """Régi korszak: Notionből importált, vagy a tanulás kezdete előtt keletkezett."""
    return notionbol or keletkezes is None or keletkezes < kezdet


def korszak_rendezes(db: Session) -> dict:
    """A megfigyelt példák besorolása a tanulási korszak szerint (idempotens).

    - a forrásrekord keletkezése + a régi-korszak jelző a példára kerül;
    - a régi korszak még el nem bírált jelöltje FÉLRE lesz téve (nem törlődik,
      egyenként jóváhagyható); ha a kezdőnap korábbra kerül, visszajön jelöltnek;
    - a jóváhagyott és az elvetett példa állapota nem változik (csak a jelző)."""
    kezdet = tanulas_kezdete(db)
    peldak = db.scalars(select(MemoryChunk).where(MemoryChunk.forras.like(f"{FORRAS}:%"))).all()
    tablankent: dict[str, dict[int, list[MemoryChunk]]] = {}
    for m in peldak:
        reszek = (m.forras or "").split(":")
        if len(reszek) != 3 or not reszek[2].isdigit():
            continue
        tablankent.setdefault(reszek[1], {}).setdefault(int(reszek[2]), []).append(m)

    felreteve = visszahozva = regi_jovahagyott = 0
    for f in FIGYELT:
        csoport = tablankent.get(f.kulcs)
        if not csoport:
            continue
        ids = list(csoport)
        keletkezes: dict[int, datetime | None] = {}
        for i in range(0, len(ids), 1000):
            for rid, created in db.execute(
                select(f.model.id, f.model.created_at).where(f.model.id.in_(ids[i : i + 1000]))
            ).all():
                keletkezes[rid] = created
        notion = _notion_rekordok(db, f, ids)
        for rid, lista in csoport.items():
            if rid not in keletkezes:
                continue  # a forrásrekord azóta törölve — nem nyúlunk hozzá
            regi = _regi(keletkezes[rid], rid in notion, kezdet)
            for m in lista:
                m.forras_keletkezes = keletkezes[rid]
                m.regi_korszak = regi
                if m.visszavont:
                    continue
                if m.ervenyes:
                    regi_jovahagyott += int(regi)
                elif regi and m.minosites != FELRETEVE:
                    m.minosites = FELRETEVE
                    felreteve += 1
                elif not regi and m.minosites == FELRETEVE:
                    m.minosites = "jelolt"
                    visszahozva += 1
    return {
        "tanulas_kezdete": kezdet.date().isoformat(),
        "felreteve": felreteve,
        "visszahozva": visszahozva,
        "regi_jovahagyott": regi_jovahagyott,
    }


def _utolso_ido(db: Session) -> datetime | None:
    # A legutóbbi események LEGKÉSŐBBI verzióideje (nem az utolsó sor: a
    # késleltetett forrás — pl. a törlés — régebbi verziót is rögzíthet utoljára).
    legkesobb: datetime | None = None
    for se in db.scalars(
        select(SourceEvent).where(SourceEvent.forras == FORRAS).order_by(SourceEvent.id.desc()).limit(200)
    ).all():
        try:
            t = datetime.fromisoformat((se.metaadat or {}).get("updated_at"))
        except (TypeError, ValueError):
            continue
        if legkesobb is None or t > legkesobb:
            legkesobb = t
    return legkesobb


def megfigyeles(
    db: Session,
    *,
    visszatekintes_nap: int | None = None,
    kenyszeritett: bool = False,
    kezdettol: bool = False,
) -> dict:
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
    # A tanulás kezdete előtt keletkezett rekord úgysem lehet új példa —
    # régebbre nem nézünk vissza. (`kezdettol`: pontosan a kezdőnaptól.)
    kezdet = tanulas_kezdete(db)
    tol = kezdet if kezdettol else max(tol, kezdet)

    k = _Kontextus(db)
    uj_megfigyeles = 0
    uj_pelda = 0
    frissitett_pelda = 0
    kihagyott_regi = 0
    tipusonkent: dict[str, int] = {}

    for f in FIGYELT:
        extra = [f.szuro] if f.szuro is not None else []
        rekordok = db.scalars(
            select(f.model)
            .where(f.model.updated_at.is_not(None), f.model.updated_at >= max(tol - f.kesleltetes, kezdet), *extra)
            .order_by(f.model.updated_at)
            .limit(MAX_REKORD)
        ).all()
        notion = _notion_rekordok(db, f, [r.id for r in rekordok])
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
                tipusonkent[f.cimke] = tipusonkent.get(f.cimke, 0) + 1
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
            if _regi(r.created_at, r.id in notion, kezdet):
                # Régi korszak (Notion / a tanulás kezdete előtt): nem lesz
                # belőle új példa; a meglévő jelöltjét a korszak_rendezes teszi félre.
                kihagyott_regi += 1
                continue
            # Lezárt emberi munkából példa-JELÖLT (egy rekord = egy jelölt).
            tartalom = leiras(f, meta)
            forras_ref = f"{FORRAS}:{azonosito}"
            pelda = db.scalar(select(MemoryChunk).where(MemoryChunk.forras == forras_ref))
            if pelda is None:
                db.add(
                    MemoryChunk(
                        hatokor=(f.tipus_fn(r) if f.tipus_fn else None) or f.tipus,
                        tartalom=tartalom,
                        forras=forras_ref,
                        forras_verzio=verzio,
                        minosites="jelolt",
                        tanulasi_halmaz="jovahagyott",
                        ervenyes=False,  # emberi jóváhagyásig NEM használható
                        forras_keletkezes=r.created_at,
                        regi_korszak=False,
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

    db.flush()
    korszak = korszak_rendezes(db)
    return {
        "engedelyezve": True,
        "tol": tol.isoformat(),
        "uj_megfigyeles": uj_megfigyeles,
        "uj_pelda": uj_pelda,
        "frissitett_pelda": frissitett_pelda,
        "kihagyott_regi": kihagyott_regi,
        "tipusonkent": tipusonkent,
        "korszak": korszak,
    }
