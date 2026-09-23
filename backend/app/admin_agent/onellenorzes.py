"""Lara — önellenőrző, folyamatos tanulás.

A háttérben (ütemezve és kézzel is) Lara végignézi a MÁR ELVÉGZETT munkát:
minden, a tanulás kezdete óta rögzített számlára megmondja, mit javasolt volna
a JELENLEGI tudásával — „vakon", azaz az adott számla saját tanulságát nem
látva —, és összeveti azzal, amit az ember valóban rögzített.

* Ha egyezik: a tudása működik (ez adja a találati arányt, futásonként).
* Ha eltér, vagy nem tudott javasolni, és a tudása sem magyarázza a valóságot:
  KÉRDEZ. Partnerenként és végső céltípusonként egy kérdés gyűjti az eseteket.
* A válasz tudássá válik:
    - „mindig így" → partnerre szabott szabály (jelölt; jogosultsággal és sikeres
      értékelés után azonnal élesíthető),
    - „magyarázat" → jóváhagyott tudás a magyarázattal (a következő hasonló
      esetnél már ez alapján javasol),
    - „egyszeri kivétel" → feljegyzi, de nem általánosít,
    - „hibás rögzítés" → Lara javaslata volt a jó; nem tanul belőle (a rögzítést
      a Pénzügyekben kell javítani).

A tudás, amiből Lara jósol (`Tudas`): az élesített, partnerhez kötött
szabályok, a jóváhagyott visszajátszott esetek és a megválaszolt kérdések.
Ugyanezt használja az éles számla-elemzés is (lásd pipeline_szamla).

Csak olvas + Lara saját tábláiba ír; üzleti rekord nem változik.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin_agent.enums import RuleState
from app.admin_agent.memory import partner_kulcs
from app.admin_agent.observer import tanulas_kezdete
from app.admin_agent.visszajatszas import (
    CEL_CIMKE,
    Cel,
    _ft,
    _kodok_szoveg,
    _szamlak,
    erkezteto_javaslata,
    osszevet,
    vegso_dontes,
)
from app.models.admin_agent import LaraKerdes, LearningRun, MemoryChunk, PlaybookRule, SourceEvent
from app.models.bejovo_szamla import CEL_TIPUSOK

TRIGGER = "onellenorzes"
#: Egyszerre legfeljebb ennyi nyitott kérdés (ne árassza el a csapatot).
MAX_NYITOTT = 25
#: Esetekből (szabály nélkül) akkor jósol, ha legalább ennyi egybehangzó eset van…
MIN_ESET = 2
#: …és az esetek legalább ekkora része ugyanoda került.
EGYETERTES = 0.8
#: A tudást adó válaszfajták (a kivétel és a hibás rögzítés nem általánosít).
TANITO_VALASZOK = ("mindig", "magyarazat")


def _most() -> datetime:
    return datetime.now(timezone.utc)


class Tudas:
    """Lara jelenlegi, JÓVÁHAGYOTT tudása a számlák besorolásáról, partnerenként."""

    def __init__(self, db: Session):
        self.szabalyok: dict[str, list[PlaybookRule]] = defaultdict(list)
        for r in db.scalars(
            select(PlaybookRule)
            .where(PlaybookRule.hatokor == "szamla", PlaybookRule.allapot == RuleState.ACTIVE.value)
            .order_by(PlaybookRule.prioritas.desc(), PlaybookRule.id.desc())
        ).all():
            f = r.feltetelek or {}
            if f.get("partner") and f.get("cel_tipus") in CEL_TIPUSOK:
                self.szabalyok[f["partner"]].append(r)

        # Esetek: (bejovo_id, céltípus, projektkód-idk) — csak jóváhagyott tudásból.
        self.esetek: dict[str, list[tuple[int, str, tuple[int, ...]]]] = defaultdict(list)
        jovahagyott = {
            m.forras
            for m in db.scalars(
                select(MemoryChunk).where(
                    MemoryChunk.forras.like("visszajatszas:%"),
                    MemoryChunk.ervenyes.is_(True),
                    MemoryChunk.visszavont.is_(False),
                )
            ).all()
        }
        for se in db.scalars(select(SourceEvent).where(SourceEvent.forras == "visszajatszas")).all():
            m = se.metaadat or {}
            if f"visszajatszas:{se.forras_azonosito}" not in jovahagyott or not m.get("partner_kulcs"):
                continue
            v = m.get("vegso") or {}
            if v.get("tipus"):
                self.esetek[m["partner_kulcs"]].append(
                    (int(m.get("bejovo_id") or 0), v["tipus"], tuple(sorted(v.get("projektkod_idk") or [])))
                )
        for k in db.scalars(
            select(LaraKerdes).where(LaraKerdes.valasz_tipus.in_(TANITO_VALASZOK))
        ).all():
            ktx = k.kontextus or {}
            kulcs = ktx.get("partner_kulcs")
            v = ktx.get("valosag") or {}
            if not kulcs or not v.get("tipus"):
                continue
            for e in ktx.get("esetek") or []:
                self.esetek[kulcs].append((int(e.get("bejovo_id") or 0), v["tipus"], tuple(sorted(e.get("vegso_kod_idk") or []))))

    def cel(self, kulcs: str, kiveve: int | None = None) -> dict | None:
        """Mit tud Lara erről a partnerről? A `kiveve` számla saját tanulságát nem
        használja (vak jóslat — nincs „puskázás")."""
        if len(kulcs) < 3:
            return None
        szab = self.szabalyok.get(kulcs) or []
        if szab:
            tipusok = {r.feltetelek["cel_tipus"] for r in szab}
            r = szab[0]
            return {
                "tipus": r.feltetelek["cel_tipus"],
                "kod_idk": [int(x) for x in (r.feltetelek.get("projektkod_idk") or [])],
                "forras": f"élesített szabály: „{r.cim}”",
                "fajta": "szabaly",
                "szabaly_id": r.id,
                "ellentmondo": len(tipusok) > 1,
            }
        esetek = [e for e in self.esetek.get(kulcs, []) if e[0] != kiveve]
        if len(esetek) < MIN_ESET:
            return None
        tipus, db_ = Counter(e[1] for e in esetek).most_common(1)[0]
        if db_ / len(esetek) < EGYETERTES:
            return None
        kodok = {e[2] for e in esetek if e[1] == tipus}
        return {
            "tipus": tipus,
            "kod_idk": list(kodok.pop()) if len(kodok) == 1 else [],
            "forras": f"{db_} jóváhagyott korábbi eset",
            "fajta": "peldak",
            "szabaly_id": None,
            "ellentmondo": False,
        }


def lara_javaslata(db: Session, tudas: Tudas, b) -> tuple[Cel | None, str | None]:
    """Mit javasolt volna Lara ERRE a számlára a jelenlegi tudásával? A tanult
    tudás elsőbbséget kap; ha nincs, az érkeztető (dokumentum-alapú) javaslata."""
    t = tudas.cel(partner_kulcs(b.kibocsato_nev), kiveve=b.id)
    if t:
        return Cel(t["tipus"], None, frozenset(t["kod_idk"])), f"{t['forras']} alapján"
    erk = erkezteto_javaslata(db, b)
    if erk.tipus:
        return erk, "az érkeztető javaslata alapján"
    return None, None


def _cel_szoveg(db: Session, tipus: str | None, kod_idk) -> str:
    s = CEL_CIMKE.get(tipus or "", tipus or "nincs cél")
    kod = _kodok_szoveg(db, frozenset(kod_idk or []))
    return s + (f" (projektkód: {kod})" if kod else "")


def _kerdes_szoveg(db: Session, partner: str, esetek: list[dict], valosag: dict) -> str:
    n = len(esetek)
    vs = _cel_szoveg(db, valosag["tipus"], valosag.get("kod_idk"))
    javasolt = [e for e in esetek if e.get("lara_tipus")]
    if not javasolt:
        return (
            f"Nem tudtam, hová kerülnek a(z) „{partner}” számlái. {n} esetben így rögzítettétek: {vs}. "
            "Miért így? Nála mindig így kell?"
        )
    e = javasolt[0]
    ls = _cel_szoveg(db, e["lara_tipus"], e.get("lara_kod_idk"))
    return (
        f"A(z) „{partner}” számláinál ezt javasoltam volna: {ls} ({e.get('lara_alap')}), "
        f"de {n} esetben így rögzítettétek: {vs}. Miért így? Nála mindig így kell?"
    )


def onellenorzes(db: Session, *, trigger: str = TRIGGER) -> dict:
    """Egy önellenőrző futás. A hívó commitál."""
    kezdet = tanulas_kezdete(db)
    tudas = Tudas(db)
    megvalaszolt: set[int] = set()
    for k in db.scalars(select(LaraKerdes).where(LaraKerdes.allapot != "nyitott")).all():
        for e in (k.kontextus or {}).get("esetek") or []:
            megvalaszolt.add(int(e.get("bejovo_id") or 0))

    stat = Counter()
    csoport: dict[str, dict] = {}
    for b in _szamlak(db, kezdet):
        vegso = vegso_dontes(db, b)
        javasolt, alap = lara_javaslata(db, tudas, b)
        eredmeny = "nem_tudta" if javasolt is None else osszevet(javasolt, vegso)
        stat[eredmeny] += 1
        if eredmeny == "egyezik":
            continue
        if b.id in megvalaszolt:
            stat["megmagyarazva"] += 1
            continue
        kulcs = partner_kulcs(b.kibocsato_nev)
        if len(kulcs) < 3 or not vegso.tipus:
            continue
        ck = f"{kulcs}|{vegso.tipus}"
        g = csoport.setdefault(
            ck,
            {"partner": b.kibocsato_nev or kulcs, "partner_kulcs": kulcs,
             "valosag": {"tipus": vegso.tipus, "kod_idk": sorted(vegso.projektkod_idk),
                         "szoveg": _cel_szoveg(db, vegso.tipus, vegso.projektkod_idk)},
             "esetek": []},
        )
        g["esetek"].append(
            {
                "bejovo_id": b.id,
                "szamlaszam": b.szamlaszam,
                "netto": _ft(b.netto),
                "datum": b.jovahagyva_at.date().isoformat() if b.jovahagyva_at else None,
                "vegso_kod_idk": sorted(vegso.projektkod_idk),
                "vegso_szoveg": _cel_szoveg(db, vegso.tipus, vegso.projektkod_idk),
                "lara_szoveg": _cel_szoveg(db, javasolt.tipus, javasolt.projektkod_idk) if javasolt else None,
                "lara_tipus": javasolt.tipus if javasolt else None,
                "lara_kod_idk": sorted(javasolt.projektkod_idk) if javasolt else [],
                "lara_alap": alap,
            }
        )

    nyitott = {k.kulcs: k for k in db.scalars(select(LaraKerdes).where(LaraKerdes.allapot == "nyitott")).all()}
    uj = bovitett = 0
    for ck, g in csoport.items():
        if ck in nyitott:
            k = nyitott[ck]
            regi = {e["bejovo_id"] for e in (k.kontextus or {}).get("esetek") or []}
            friss = [e for e in g["esetek"] if e["bejovo_id"] not in regi]
            if friss:
                ktx = dict(k.kontextus or {})
                ktx["esetek"] = list(ktx.get("esetek") or []) + friss
                k.kontextus = ktx
                k.kerdes = _kerdes_szoveg(db, g["partner"], ktx["esetek"], g["valosag"])
                bovitett += 1
            continue
        if len(nyitott) + uj >= MAX_NYITOTT:
            stat["kerdes_varolistan"] += 1
            continue
        db.add(
            LaraKerdes(
                tipus="szamla_besorolas",
                allapot="nyitott",
                kulcs=ck,
                partner_nev=(g["partner"] or "")[:300],
                kerdes=_kerdes_szoveg(db, g["partner"], g["esetek"], g["valosag"]),
                kontextus=g,
            )
        )
        uj += 1

    ellenorzott = stat["egyezik"] + stat["elter"] + stat["nem_tudta"]
    osszefoglalo = {
        "ellenorzott": ellenorzott,
        "egyezik": stat["egyezik"],
        "elter": stat["elter"],
        "nem_tudta": stat["nem_tudta"],
        "megmagyarazva": stat["megmagyarazva"],
        "talalati_arany": round(stat["egyezik"] / ellenorzott, 3) if ellenorzott else None,
        "uj_kerdes": uj,
        "bovitett_kerdes": bovitett,
        "varolistan": stat["kerdes_varolistan"],
        "szabalyok": sum(len(v) for v in tudas.szabalyok.values()),
        "tanult_partnerek": len(tudas.esetek),
    }
    most = _most()
    db.add(LearningRun(trigger=trigger, allapot="kesz", kezdes_at=most, veg_at=most, osszefoglalo=osszefoglalo))
    db.flush()
    return osszefoglalo


# ── Válasz a kérdésre → tudás ─────────────────────────────────────────────────


class ValaszHiba(ValueError):
    pass


def valaszol(db: Session, k: LaraKerdes, *, valasz_tipus: str, magyarazat: str | None, user_id: int,
             elesithet: bool) -> dict:
    """A kérdés megválaszolása. A hívó commitál. `elesithet`: a felhasználónak
    van szabály-élesítési joga ÉS az utolsó értékelés átment — ekkor a „mindig
    így" válaszból született szabály azonnal aktív."""
    if k.allapot != "nyitott":
        raise ValaszHiba("Erre a kérdésre már válaszoltak.")
    if valasz_tipus not in ("mindig", "kivetel", "magyarazat", "hibas", "elvet"):
        raise ValaszHiba("Ismeretlen válaszfajta.")
    szoveg = (magyarazat or "").strip() or None
    if valasz_tipus == "magyarazat" and not szoveg:
        raise ValaszHiba("Írd le röviden, miért így van — ebből tanul Lara.")

    ktx = k.kontextus or {}
    v = ktx.get("valosag") or {}
    partner = k.partner_nev or ktx.get("partner_kulcs") or "?"
    celszoveg = _cel_szoveg(db, v.get("tipus"), v.get("kod_idk"))
    n = len(ktx.get("esetek") or [])
    eredmeny: dict = {"szabaly_id": None, "szabaly_allapot": None, "pelda_id": None}

    if valasz_tipus in ("mindig", "magyarazat", "kivetel"):
        if valasz_tipus == "kivetel":
            tartalom = f"„{partner}”: {n} számla egyszeri kivételként így került rögzítésre: {celszoveg}. Nem általános szabály."
        else:
            tartalom = f"„{partner}” számlái: {celszoveg}."
        if szoveg:
            tartalom += f" Magyarázat (ember): {szoveg}"
        m = MemoryChunk(
            hatokor="szamla",
            tartalom=tartalom,
            forras=f"kerdes:{k.id}",
            minosites="jovahagyott",
            tanulasi_halmaz="jovahagyott",
            ervenyes=True,  # ember magyarázta — kifejezett jóváhagyás
            regi_korszak=False,
        )
        db.add(m)
        db.flush()
        eredmeny["pelda_id"] = m.id

    if valasz_tipus == "mindig" and v.get("tipus"):
        kodok = {tuple(e.get("vegso_kod_idk") or []) for e in ktx.get("esetek") or []}
        kod_idk = list(kodok.pop()) if len(kodok) == 1 else []
        aktiv = elesithet
        r = PlaybookRule(
            hatokor="szamla",
            cim=f"{partner}: {celszoveg}"[:200],
            tartalom=(
                f"A(z) „{partner}” számlái mindig így kerülnek rögzítésre: {celszoveg}."
                + (f" Indoklás: {szoveg}" if szoveg else "")
                + " (Lara kérdésére adott emberi válasz alapján.)"
            ),
            feltetelek={
                "forras": "kerdes",
                "kerdes_id": k.id,
                "partner": ktx.get("partner_kulcs"),
                "partner_nev": partner,
                "cel_tipus": v["tipus"],
                "projektkod_idk": kod_idk,
            },
            prioritas=10,
            verzio=1,
            allapot=RuleState.ACTIVE.value if aktiv else RuleState.PENDING.value,
            forras_esetek={"bejovo_idk": [e.get("bejovo_id") for e in ktx.get("esetek") or []]},
        )
        db.add(r)
        db.flush()
        k.szabaly_id = r.id
        eredmeny["szabaly_id"] = r.id
        eredmeny["szabaly_allapot"] = r.allapot

    k.allapot = "elvetve" if valasz_tipus == "elvet" else "megvalaszolt"
    k.valasz_tipus = valasz_tipus
    k.valasz_szoveg = szoveg
    k.megvalaszolta_employee_id = user_id
    k.megvalaszolva_at = _most()
    db.flush()
    return eredmeny


def futasok(db: Session, limit: int = 30) -> list[dict]:
    sorok = db.scalars(
        select(LearningRun).where(LearningRun.trigger.like(f"{TRIGGER}%")).order_by(LearningRun.id.desc()).limit(limit)
    ).all()
    return [
        {"id": r.id, "trigger": r.trigger, "veg_at": r.veg_at.isoformat() if r.veg_at else None, **(r.osszefoglalo or {})}
        for r in sorok
    ]
