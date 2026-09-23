"""HYRON — visszajátszás a rögzített számlákon + találati arány.

Amikor kevés az új adat, a MÁR ELVÉGZETT munkából is lehet tanulni: a tanulás
kezdete óta rögzített (jóváhagyott) beérkező számláknál összevetjük, mit
javasolt eredetileg az érkeztető (`BejovoSzamla.javaslat`), és mit döntött
végül az ember (a számla végső céljai / bontása).

Minden számlából:
* PÉLDA-JELÖLT a végső emberi döntéssel (konkrétan: partner → cél, projektkód),
  megjelölve, hogy az érkeztető eltalálta-e — emberi jóváhagyásig NEM éles;
* forrásesemény az összevetés eredményével (ebből a TALÁLATI ARÁNY);
* ha a HYRON már elemezte a számlát a döntés ELŐTT, az ő javaslatát is
  összevetjük (HYRON saját találati aránya).

Partnerenként, ha legalább két eset egybehangzóan ugyanoda került, SZABÁLY-
JELÖLT születik (pl. „Turcsik Márk számlái: új kiadás a HYPE26-0012 kódon").
A szabály csak értékelés után, emberi élesítéssel lesz aktív.

Csak olvas + HYRON saját tábláiba ír; üzleti rekord nem változik.
Idempotens: egy számla egy jóváhagyása egyszer kerül feldolgozásra.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.admin_agent.enums import RuleState
from app.admin_agent.memory import partner_kulcs
from app.admin_agent.observer import tanulas_kezdete
from app.models.admin_agent import ActionProposal, AdminTask, MemoryChunk, PlaybookRule, SourceEvent
from app.models.bejovo_szamla import ALLAPOT_JOVAHAGYVA, BejovoSzamla
from app.models.finance import Expense
from app.models.performance_certificate import PerformanceCertificate
from app.models.project import Project
from app.models.project_code import ProjectCode

FORRAS = "visszajatszas"
#: Szabály-jelölthöz legalább ennyi eset kell egy partnernél…
MIN_ESET = 2
#: …és az esetek legalább ekkora része ugyanoda került.
EGYETERTES = 0.8

CEL_CIMKE = {
    "kiadas_uj": "új kiadás",
    "kiadas_csatolas": "csatolás meglévő kiadáshoz",
    "kulsos_tig": "meglévő külsős TIG",
    "belsos_tig": "meglévő belsős TIG",
    "erezsi": "E-Rezsi időszak",
    "auto": "autóköltség",
    "kp": "KP-tétel bizonylata",
    "mukodesi": "általános működési költség (projekt nélkül)",
    "kimeno": "kimenő számla",
    "bontas": "bontás több cél között",
    "egyeb": "egyéb / tisztázandó",
}

#: Céltípusonként melyik mező azonosítja a konkrét célrekordot.
CEL_MEZO = {
    "kiadas_uj": "cel_project_code_id",
    "kiadas_csatolas": "cel_expense_id",
    "kulsos_tig": "cel_certificate_id",
    "belsos_tig": "cel_internal_certificate_id",
    "erezsi": "cel_kotelezettseg_idoszak_id",
    "auto": "cel_auto_id",
    "kp": "cel_kp_forgalom_id",
}


def _most() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Cel:
    tipus: str | None
    #: A konkrét célrekord (mező, id), ha ismert.
    celpont: tuple[str, int] | None = None
    projektkod_idk: frozenset[int] = field(default_factory=frozenset)


# ── Projektkód feloldása a célrekordból ──────────────────────────────────────


def _pk_projektbol(db: Session, project_id: int | None) -> int | None:
    if project_id is None:
        return None
    p = db.get(Project, project_id)
    return p.project_code_id if p is not None else None


def _pk_celbol(db: Session, mezo: str, cel_id: int) -> int | None:
    if mezo == "cel_project_code_id":
        return cel_id
    if mezo == "cel_certificate_id":
        c = db.get(PerformanceCertificate, cel_id)
        if c is None:
            return None
        return c.project_code_id or _pk_projektbol(db, c.project_id)
    if mezo == "cel_expense_id":
        e = db.get(Expense, cel_id)
        if e is None:
            return None
        return e.project_code_id or _pk_projektbol(db, e.alvallalkozo_project_id)
    return None


def vegso_dontes(db: Session, b: BejovoSzamla) -> Cel:
    """Amit az ember végül döntött (a jóváhagyott számla céljai / bontása)."""
    tipus = b.cel_tipus
    kodok: set[int] = set()
    celpont = None
    sorok = b.bontas if isinstance(b.bontas, list) else (b.bontas or {}).get("sorok") if isinstance(b.bontas, dict) else None
    if tipus == "bontas" and sorok:
        for s in sorok:
            if not isinstance(s, dict):
                continue
            if s.get("project_code_id"):
                kodok.add(int(s["project_code_id"]))
            elif s.get("cel_id") and CEL_MEZO.get(s.get("cel_tipus") or ""):
                pk = _pk_celbol(db, CEL_MEZO[s["cel_tipus"]], int(s["cel_id"]))
                if pk:
                    kodok.add(pk)
        return Cel(tipus, None, frozenset(kodok))
    mezo = CEL_MEZO.get(tipus or "")
    if mezo and getattr(b, mezo, None):
        celpont = (mezo, int(getattr(b, mezo)))
        pk = _pk_celbol(db, mezo, celpont[1])
        if pk:
            kodok.add(pk)
    if b.cel_project_code_id:
        kodok.add(b.cel_project_code_id)
    elif b.cel_project_id:
        pk = _pk_projektbol(db, b.cel_project_id)
        if pk:
            kodok.add(pk)
    if not kodok and b.rogzitett_expense_id and tipus not in ("mukodesi", "belsos_tig", "erezsi"):
        pk = _pk_celbol(db, "cel_expense_id", b.rogzitett_expense_id)
        if pk:
            kodok.add(pk)
    return Cel(tipus, celpont, frozenset(kodok))


def erkezteto_javaslata(db: Session, b: BejovoSzamla) -> Cel:
    """Amit az érkeztető eredetileg javasolt. Az újabb javaslatokban pillanatkép
    van a javasolt célról (`javasolt_cel`); a régebbieknél az alternatívákból
    állítjuk vissza, CSAK ha egyértelmű (különben csak a típust vetjük össze)."""
    j = b.javaslat or {}
    tipus = j.get("tipus") if isinstance(j.get("tipus"), str) else None
    if not tipus:
        return Cel(None)
    mezo = CEL_MEZO.get(tipus)
    celpont = None
    pillanatkep = j.get("javasolt_cel") if isinstance(j.get("javasolt_cel"), dict) else None
    if mezo and pillanatkep and pillanatkep.get(mezo):
        celpont = (mezo, int(pillanatkep[mezo]))
    elif mezo:
        azonos = [a for a in (j.get("alternativak") or []) if isinstance(a, dict) and a.get("tipus") == tipus and a.get("cel_id")]
        if len(azonos) == 1:
            celpont = (mezo, int(azonos[0]["cel_id"]))
    kodok: set[int] = set()
    if celpont:
        pk = _pk_celbol(db, *celpont)
        if pk:
            kodok.add(pk)
    return Cel(tipus, celpont, frozenset(kodok))


def osszevet(javasolt: Cel, vegso: Cel) -> str:
    """"egyezik" | "elter" | "nem_javasolt"."""
    if not javasolt.tipus:
        return "nem_javasolt"
    if javasolt.tipus != vegso.tipus:
        return "elter"
    if javasolt.celpont and vegso.celpont and javasolt.celpont != vegso.celpont:
        return "elter"
    if javasolt.projektkod_idk and vegso.projektkod_idk and javasolt.projektkod_idk != vegso.projektkod_idk:
        return "elter"
    return "egyezik"


def _ugynok_javaslata(db: Session, b: BejovoSzamla) -> Cel | None:
    """A HYRON utolsó, a jóváhagyás ELŐTT készült javaslata (ha volt)."""
    task = db.scalar(
        select(AdminTask).where(AdminTask.forras_referenciak["bejovo_szamla_id"].astext == str(b.id)).limit(1)
    )
    if task is None:
        return None
    felt = [ActionProposal.task_id == task.id]
    if b.jovahagyva_at is not None:
        felt.append(ActionProposal.created_at < b.jovahagyva_at)
    p = db.scalar(select(ActionProposal).where(*felt).order_by(ActionProposal.id.desc()).limit(1))
    if p is None:
        return None
    pl = p.payload or {}
    tipus = pl.get("cel_tipus") if isinstance(pl.get("cel_tipus"), str) else None
    kod = pl.get("cel_project_code_id")
    return Cel(tipus, None, frozenset({int(kod)}) if kod else frozenset())


# ── Leírás ───────────────────────────────────────────────────────────────────


def _kodok_szoveg(db: Session, idk: frozenset[int]) -> str | None:
    if not idk:
        return None
    nevek = []
    for i in sorted(idk):
        pc = db.get(ProjectCode, i)
        nevek.append((pc.projektkod if pc is not None else None) or f"#{i}")
    return ", ".join(nevek)


def _cel_szoveg(db: Session, c: Cel) -> str:
    s = CEL_CIMKE.get(c.tipus or "", c.tipus or "nincs cél")
    kod = _kodok_szoveg(db, c.projektkod_idk)
    return s + (f" (projektkód: {kod})" if kod else "")


def _ft(v) -> str | None:
    try:
        return f"{float(v):,.0f} Ft".replace(",", " ")
    except (TypeError, ValueError):
        return None


def leiras(db: Session, b: BejovoSzamla, javasolt: Cel, vegso: Cel, eredmeny: str) -> str:
    fej = f"Beérkező számla — {b.kibocsato_nev or 'ismeretlen kibocsátó'}"
    if b.szamlaszam:
        fej += f" ({b.szamlaszam})"
    if _ft(b.netto):
        fej += f", nettó {_ft(b.netto)}"
    mondat = f"{fej}: a HELYES besorolás {_cel_szoveg(db, vegso)}."
    if eredmeny == "egyezik":
        mondat += " Az érkeztető is ezt javasolta."
    elif eredmeny == "elter":
        mondat += f" Az érkeztető tévesen ezt javasolta: {_cel_szoveg(db, javasolt)}."
    else:
        mondat += " Az érkeztető nem tudott javaslatot adni — ember döntött."
    return mondat


# ── Futás ────────────────────────────────────────────────────────────────────


def _szamlak(db: Session, kezdet: datetime) -> list[BejovoSzamla]:
    return list(
        db.scalars(
            select(BejovoSzamla)
            .where(
                BejovoSzamla.allapot == ALLAPOT_JOVAHAGYVA,
                BejovoSzamla.valtozat_szamla_id.is_(None),  # XML-változat / részletező nem önálló
                BejovoSzamla.jovahagyva_at.is_not(None),
                BejovoSzamla.jovahagyva_at >= kezdet,
                BejovoSzamla.cel_tipus.is_not(None),
            )
            .order_by(BejovoSzamla.jovahagyva_at)
        ).all()
    )


def visszajatszas(db: Session) -> dict:
    """Egy visszajátszó futás. A hívó commitál."""
    kezdet = tanulas_kezdete(db)
    uj = frissitett_pelda = uj_pelda = 0
    for b in _szamlak(db, kezdet):
        javasolt = erkezteto_javaslata(db, b)
        vegso = vegso_dontes(db, b)
        eredmeny = osszevet(javasolt, vegso)
        ugynok = _ugynok_javaslata(db, b)
        ugynok_eredmeny = osszevet(ugynok, vegso) if ugynok is not None else None
        meta = {
            "bejovo_id": b.id,
            "partner": b.kibocsato_nev,
            "partner_kulcs": partner_kulcs(b.kibocsato_nev),
            "jovahagyva_at": b.jovahagyva_at.isoformat(),
            "eredmeny": eredmeny,
            "ugynok_eredmeny": ugynok_eredmeny,
            "javasolt": {"tipus": javasolt.tipus, "projektkod_idk": sorted(javasolt.projektkod_idk)},
            "vegso": {"tipus": vegso.tipus, "projektkod_idk": sorted(vegso.projektkod_idk)},
        }
        try:
            with db.begin_nested():
                db.add(
                    SourceEvent(
                        forras=FORRAS,
                        forras_azonosito=f"bejovo:{b.id}",
                        forras_verzio=b.jovahagyva_at.isoformat(),
                        allapot="feldolgozva",
                        metaadat=meta,
                        feldolgozva_at=_most(),
                    )
                )
            uj += 1
        except IntegrityError:
            pass  # ez a jóváhagyás már visszajátszva

        tartalom = leiras(db, b, javasolt, vegso, eredmeny)
        forras_ref = f"{FORRAS}:bejovo:{b.id}"
        pelda = db.scalar(select(MemoryChunk).where(MemoryChunk.forras == forras_ref))
        if pelda is None:
            db.add(
                MemoryChunk(
                    hatokor="szamla",
                    tartalom=tartalom,
                    forras=forras_ref,
                    forras_verzio=b.jovahagyva_at.isoformat(),
                    minosites="jelolt",
                    tanulasi_halmaz="jovahagyott",
                    ervenyes=False,  # emberi jóváhagyásig NEM használható
                    forras_keletkezes=b.created_at,
                    regi_korszak=False,
                )
            )
            uj_pelda += 1
        elif not pelda.ervenyes and not pelda.visszavont and pelda.tartalom != tartalom:
            pelda.tartalom = tartalom
            frissitett_pelda += 1
    db.flush()
    szabaly = szabaly_jeloltek(db)
    return {
        "tanulas_kezdete": kezdet.date().isoformat(),
        "uj_szamla": uj,
        "uj_pelda": uj_pelda,
        "frissitett_pelda": frissitett_pelda,
        **szabaly,
        "osszesites": osszesites(db),
    }


def _esemenyek(db: Session) -> list[dict]:
    """A tanulás kezdete óta visszajátszott számlák (számlánként a legutóbbi)."""
    kezdet = tanulas_kezdete(db).isoformat()
    utolso: dict[str, dict] = {}
    for se in db.scalars(select(SourceEvent).where(SourceEvent.forras == FORRAS).order_by(SourceEvent.id)).all():
        m = se.metaadat or {}
        if (m.get("jovahagyva_at") or "") >= kezdet:
            utolso[se.forras_azonosito] = m
    return list(utolso.values())


def szabaly_jeloltek(db: Session) -> dict:
    """Partnerenként egybehangzó emberi döntésekből szabály-JELÖLT (pending).
    Idempotens: ugyanarra a partnerre ugyanazzal a tartalommal nem készül új;
    visszavont (retired) azonos tartalmat nem hozunk vissza."""
    csoport: dict[str, list[dict]] = defaultdict(list)
    for m in _esemenyek(db):
        if m.get("partner_kulcs"):
            csoport[m["partner_kulcs"]].append(m)

    letezo = [
        r for r in db.scalars(select(PlaybookRule).where(PlaybookRule.hatokor == "szamla")).all()
        if (r.feltetelek or {}).get("forras") == FORRAS
    ]
    uj = frissitett = 0
    for kulcs, esetek in csoport.items():
        if len(esetek) < MIN_ESET:
            continue
        tipusok = Counter(e["vegso"]["tipus"] for e in esetek)
        tipus, db_tipus = tipusok.most_common(1)[0]
        if db_tipus / len(esetek) < EGYETERTES or tipus in (None, "egyeb", "bontas"):
            continue
        azonos = [e for e in esetek if e["vegso"]["tipus"] == tipus]
        kod_halmazok = {tuple(e["vegso"]["projektkod_idk"]) for e in azonos}
        kod = kod_halmazok.pop() if len(kod_halmazok) == 1 else None
        kod_szoveg = _kodok_szoveg(db, frozenset(kod)) if kod else None
        tevedes = sum(1 for e in esetek if e["eredmeny"] != "egyezik")
        partner = esetek[-1].get("partner") or kulcs
        cim = f"{partner}: {CEL_CIMKE.get(tipus, tipus)}" + (f" ({kod_szoveg})" if kod_szoveg else "")
        tartalom = (
            f"A(z) „{partner}” számláit az ember {db_tipus}/{len(esetek)} esetben így rögzítette: "
            f"{CEL_CIMKE.get(tipus, tipus)}"
            + (f", a(z) {kod_szoveg} projektkódon" if kod_szoveg else "")
            + ". Új számlájánál ezt javasold elsőként, de a dokumentumban szereplő eltérő projektkód "
            "vagy utasítás felülírja."
            + (f" Az érkeztető {tevedes} esetben ezt nem találta el." if tevedes else "")
        )
        feltetelek = {"forras": FORRAS, "partner": kulcs, "cel_tipus": tipus, "projektkod_idk": list(kod or [])}
        sajat = [r for r in letezo if (r.feltetelek or {}).get("partner") == kulcs]
        if any(r.tartalom == tartalom for r in sajat):
            continue  # már megvan (akár aktív, akár visszavont)
        nyitott = [r for r in sajat if r.allapot in (RuleState.PENDING.value, RuleState.DRAFT.value)]
        if nyitott:
            r = nyitott[0]
            r.cim, r.tartalom, r.feltetelek = cim, tartalom, feltetelek
            r.forras_esetek = {"bejovo_idk": [e["bejovo_id"] for e in esetek]}
            frissitett += 1
            continue
        db.add(
            PlaybookRule(
                hatokor="szamla",
                cim=cim[:200],
                tartalom=tartalom,
                feltetelek=feltetelek,
                prioritas=10,  # partnerre szabott: az általános előtt
                verzio=1 + max((r.verzio for r in sajat), default=0),
                allapot=RuleState.PENDING.value,  # gépi jelölt: értékelés + emberi élesítés kell
                forras_esetek={"bejovo_idk": [e["bejovo_id"] for e in esetek]},
            )
        )
        uj += 1
    return {"uj_szabaly_jelolt": uj, "frissitett_szabaly_jelolt": frissitett}


def osszesites(db: Session) -> dict:
    """Találati arány: az érkeztető (és ahol volt, HYRON) javaslata hányszor
    egyezett a végső emberi döntéssel — összesen és hetente."""
    esetek = _esemenyek(db)
    szam = Counter(e["eredmeny"] for e in esetek)
    ugynok = Counter(e["ugynok_eredmeny"] for e in esetek if e.get("ugynok_eredmeny") in ("egyezik", "elter"))

    def arany(c: Counter) -> float | None:
        n = c["egyezik"] + c["elter"]
        return round(c["egyezik"] / n, 3) if n else None

    hetente: dict[str, Counter] = defaultdict(Counter)
    for e in esetek:
        try:
            d = datetime.fromisoformat(e["jovahagyva_at"])
        except (TypeError, ValueError):
            continue
        ev, het, _ = d.isocalendar()
        hetente[f"{ev}-W{het:02d}"][e["eredmeny"]] += 1
    return {
        "szamlak": len(esetek),
        "egyezik": szam["egyezik"],
        "elter": szam["elter"],
        "nem_javasolt": szam["nem_javasolt"],
        "erkezteto_arany": arany(szam),
        "ugynok_egyezik": ugynok["egyezik"],
        "ugynok_elter": ugynok["elter"],
        "ugynok_arany": arany(ugynok),
        "hetente": [
            {"het": h, "szamlak": sum(c.values()), "egyezik": c["egyezik"], "elter": c["elter"],
             "nem_javasolt": c["nem_javasolt"], "arany": arany(c)}
            for h, c in sorted(hetente.items())
        ],
    }
