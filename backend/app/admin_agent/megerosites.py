"""Lara — megerősítés: a VALÓSÁG által igazolt példák automatikus jóváhagyása,
és szabályjavaslat a jóváhagyott példák csoportjaiból.

A lassú pont eddig az volt, hogy MINDEN tudás-jelölt kézi jóváhagyásra várt a
Tudástárban. Egy jelölt azonban nem csak emberi jóváhagyással igazolódhat: ha
ugyanannál a partnernél az emberek TÖBBSZÖR, egybehangzóan ugyanúgy döntöttek
(pl. a „Kovács Kft." számlái háromszor is új kiadásként kerültek rögzítésre,
másképp egyszer sem), akkor az egyes esetek már nem egyedi, esetleg hibás
döntések, hanem a cég bevett gyakorlata. Ezeket Lara magától jóváhagyja.

Biztonsági elvek:

* Csak PÉLDA hagyható jóvá automatikusan — SZABÁLY soha. A csoportokból
  készülő szabályjavaslat mindig `pending`, élesíteni csak ember tudja (a
  Tudástárban, a meglévő jogosultsággal).
* Egy csoport akkor igazolt, ha legalább `min_eset` (alap 3) eset van benne, és
  a partner adott forrásbeli eseteinek legalább 80%-a így alakult. Ha a
  csoportban akár egy ELVETETT példa is van (ember kifejezetten nemet mondott),
  a csoport nem hagyható jóvá automatikusan.
* A szabad szöveges források (projektkód-komment, árajánlat) és a negatív jel
  (törölt rekord) sosem hagyhatók jóvá automatikusan — azokat embernek kell
  elolvasnia. A megtörtént fizetés (bevétel) viszont TÉNY: önmagában igazolt.
* A régi korszak (Notion) félretett jelöltjei kimaradnak.
* Minden automatikus jóváhagyás nyomot hagy (`aa_action_traces`), a Tudástárban
  „automatikusan jóváhagyva" címkét kap, és egy kattintással elvethető.
* Kikapcsolható: `aa_settings.limitek.auto_jovahagyas` (alap: be).

Csak Lara saját tábláiba ír; üzleti rekord nem változik. A hívó commitál.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import mean
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin_agent.enums import ActorKind, RuleState
from app.admin_agent.memory import partner_kulcs
from app.admin_agent.observer import FELRETEVE, FORRAS_CIMKEK
from app.admin_agent.settings_service import get_settings
from app.admin_agent.visszajatszas import CEL_CIMKE
from app.models.admin_agent import ActionTrace, LearningRun, MemoryChunk, PlaybookRule, SourceEvent
from app.models.contract import Contract
from app.models.performance_certificate import PerformanceCertificate

#: Az automatikusan jóváhagyott példa minősítése (a Tudástár ebből címkéz).
AUTO = "auto_jovahagyott"
ALAP_MIN_ESET = 3
EGYETERTES = 0.8
#: Szabályjavaslathoz ennyi JÓVÁHAGYOTT (kézi vagy automatikus) eset kell…
SZABALY_MIN_ESET = 5
#: …és a partner eseteinek legalább ekkora része így alakult.
SZABALY_EGYETERTES = 0.9
#: A bevétel-szabály (fizetési szokás) ennyi fizetésből készül.
BEVETEL_MIN_ESET = 3
#: Szabad szöveg / negatív jel: csak ember hagyhatja jóvá.
KEZI_FORRASOK = frozenset({"projektkod_komment", "arajanlat", "torles"})
#: Megtörtént tény: önmagában igazolt.
TENY_FORRASOK = frozenset({"bevetel"})
TRIGGER = "megerosites"


def _most() -> datetime:
    return datetime.now(timezone.utc)


def beallitas(db: Session) -> tuple[bool, int]:
    """(be van-e kapcsolva, min. esetszám) — a Beállításokból."""
    lim = get_settings(db).limitek or {}
    be = lim.get("auto_jovahagyas")
    try:
        n = int(lim.get("auto_jovahagyas_min") or ALAP_MIN_ESET)
    except (TypeError, ValueError):
        n = ALAP_MIN_ESET
    return (be is not False), max(2, min(n, 20))


@dataclass
class _Elem:
    chunk: MemoryChunk
    kulcs: str  # a forrás (pl. "kiadas", "visszajatszas")
    partner: str  # normalizált partnerkulcs
    partner_nev: str
    minta: tuple
    meta: dict


def _norm(v: Any) -> str:
    return " ".join(str(v).strip().lower().split()) if v is not None else ""


def _papir_minta(kulcs: str, r: Any) -> tuple:
    from app.admin_agent.onellenorzes_papir import ertekek

    e = ertekek(kulcs, r)
    return ("papir", bool(e["kihagyas"]), e["afa"])


def _elemek(db: Session) -> list[_Elem]:
    """A megfigyelt és a visszajátszott példák, a döntés-mintájukkal."""
    chunks = db.scalars(
        select(MemoryChunk).where(
            MemoryChunk.forras.like("megfigyeles:%") | MemoryChunk.forras.like("visszajatszas:%"),
            MemoryChunk.regi_korszak.is_(False),
            MemoryChunk.minosites != FELRETEVE,
        )
    ).all()
    if not chunks:
        return []

    # A forrásesemények (rekordonként a legutóbbi) — ebben van a partner és a döntés.
    esemeny: dict[tuple[str, str], dict] = {}
    for se in db.scalars(
        select(SourceEvent).where(SourceEvent.forras.in_(("megfigyeles", "visszajatszas"))).order_by(SourceEvent.id)
    ).all():
        esemeny[(se.forras, se.forras_azonosito)] = se.metaadat or {}

    # A papír-döntésekhez (szerződés / TIG) a rekord maga kell.
    papir_ids: dict[str, set[int]] = defaultdict(set)
    for m in chunks:
        r = (m.forras or "").split(":")
        if r[0] == "megfigyeles" and len(r) == 3 and r[1] in ("szerzodes", "tig") and r[2].isdigit():
            papir_ids[r[1]].add(int(r[2]))
    rekordok: dict[tuple[str, int], Any] = {}
    for kulcs, model in (("szerzodes", Contract), ("tig", PerformanceCertificate)):
        ids = list(papir_ids.get(kulcs) or [])
        for i in range(0, len(ids), 1000):
            for r in db.scalars(select(model).where(model.id.in_(ids[i : i + 1000]))).all():
                rekordok[(kulcs, r.id)] = r

    ki: list[_Elem] = []
    for m in chunks:
        reszek = (m.forras or "").split(":", 1)
        if len(reszek) != 2:
            continue
        forras, azon = reszek
        meta = esemeny.get((forras, azon))
        if meta is None:
            continue
        if forras == "visszajatszas":
            kulcs = "visszajatszas"
            tipus = (meta.get("vegso") or {}).get("tipus")
            if not tipus:
                continue
            minta: tuple = ("cel", tipus)
        else:
            kulcs = azon.split(":")[0]
            if kulcs in ("szerzodes", "tig"):
                r = rekordok.get((kulcs, int(azon.split(":")[1]))) if azon.split(":")[1].isdigit() else None
                if r is None:
                    continue
                minta = _papir_minta(kulcs, r)
            elif kulcs in ("megrendeloi_szerzodes", "megrendeloi_tig"):
                minta = ("papir", bool(meta.get("kihagyva")), meta.get("plusz_afa"))
            elif kulcs == "belsos_tig":
                minta = ("allapot", _norm(meta.get("allapot")))
            elif kulcs == "kiadas":
                minta = ("tipus", _norm(meta.get("kiadas_tipus")))
            elif kulcs == "utalas":
                minta = ("cel", meta.get("cel_tipus"), meta.get("elszamolas"))
            elif kulcs in TENY_FORRASOK:
                minta = ("teny",)
            else:
                minta = ("szoveg",)  # kézi forrás — csoportba sem kerül
        nev = (meta.get("partner") or "").strip()
        pk = partner_kulcs(nev)
        if len(pk) < 3:
            continue
        ki.append(_Elem(m, kulcs, pk, nev, minta, meta))
    return ki


def _minta_szoveg(kulcs: str, minta: tuple) -> str:
    if kulcs == "visszajatszas":
        return f"a számlája {CEL_CIMKE.get(minta[1], minta[1])} lett"
    if minta[0] == "papir":
        reszek = ["a papírt kihagyták" if minta[1] else "papír készült"]
        if minta[2] is not None:
            reszek.append("+ÁFA-val" if minta[2] else "ÁFA nélkül")
        return ", ".join(reszek)
    if minta[0] == "allapot":
        return f"állapot: {minta[1] or '—'}"
    if minta[0] == "tipus":
        return f"kiadás-típus: {minta[1] or 'nincs megadva'}"
    if minta[0] == "cel":
        cel = {"kiadas": "kiadásként", "kulsos_tig": "külsős TIG-re", "belsos_tig": "belsős TIG-re",
               "uj_kiadas": "új kiadásként"}.get(minta[1] or "", minta[1] or "?")
        return f"az utalást {cel} rögzítettétek" + (
            f", elszámolás: {'Krumpelló' if minta[2] == 'krumpello' else 'HYPE'}" if minta[2] in ("hype", "krumpello") else ""
        )
    return "megtörtént"


def _cimke(kulcs: str) -> str:
    return "számla" if kulcs == "visszajatszas" else FORRAS_CIMKEK.get(kulcs, kulcs)


def futtat(db: Session, *, trigger: str = TRIGGER) -> dict:
    """Egy megerősítő futás: automatikus jóváhagyás + szabályjavaslatok."""
    be, min_eset = beallitas(db)
    elemek = _elemek(db)

    csoportok: dict[tuple, list[_Elem]] = defaultdict(list)
    partner_ossz: Counter = Counter()
    for e in elemek:
        if e.kulcs in KEZI_FORRASOK or e.minta == ("szoveg",):
            continue
        csoportok[(e.kulcs, e.partner, e.minta)].append(e)
        partner_ossz[(e.kulcs, e.partner)] += 1

    most = _most()
    jovahagyott = 0
    blokkolt = 0
    reszletek: list[dict] = []
    if be:
        for (kulcs, pk, minta), lista in csoportok.items():
            n = len(lista)
            arany = n / partner_ossz[(kulcs, pk)]
            teny = minta == ("teny",)
            if not teny and (n < min_eset or arany < EGYETERTES):
                continue
            if any(e.chunk.visszavont for e in lista):
                blokkolt += 1  # ember elvetett egy ilyet — nem döntünk helyette
                continue
            uj = [e for e in lista if not e.chunk.ervenyes and not e.chunk.visszavont and e.chunk.minosites == "jelolt"]
            for e in uj:
                e.chunk.ervenyes = True
                e.chunk.minosites = AUTO
                db.add(
                    ActionTrace(
                        task_id=None,
                        szereplo=ActorKind.AGENT.value,
                        muvelet="auto_jovahagyas",
                        eroforras=f"memory:{e.chunk.id}",
                        diff={
                            "forras": e.chunk.forras,
                            "partner": e.partner_nev,
                            "minta": _minta_szoveg(kulcs, minta),
                            "esetszam": n,
                            "arany": round(arany, 3),
                            "teny": teny,
                        },
                        eredmeny="jovahagyva",
                        tortent_at=most,
                    )
                )
            if uj:
                jovahagyott += len(uj)
                reszletek.append(
                    {"partner": lista[0].partner_nev, "forras": _cimke(kulcs), "minta": _minta_szoveg(kulcs, minta),
                     "esetszam": n, "jovahagyva": len(uj)}
                )

    szabaly = _szabalyjavaslatok(db, csoportok, partner_ossz)
    osszefoglalo = {
        "bekapcsolva": be,
        "min_eset": min_eset,
        "vizsgalt_pelda": len(elemek),
        "csoport": len(csoportok),
        "auto_jovahagyott": jovahagyott,
        "blokkolt_csoport": blokkolt,
        "reszletek": reszletek[:30],
        **szabaly,
    }
    db.add(LearningRun(trigger=trigger, allapot="kesz", kezdes_at=most, veg_at=_most(), osszefoglalo=osszefoglalo))
    db.flush()
    return osszefoglalo


# ── Szabályjavaslat a jóváhagyott csoportokból ───────────────────────────────


def _meglevo(db: Session) -> dict[str, PlaybookRule]:
    ki: dict[str, PlaybookRule] = {}
    for r in db.scalars(
        select(PlaybookRule).where(PlaybookRule.allapot != RuleState.RETIRED.value)
    ).all():
        mk = (r.feltetelek or {}).get("minta_kulcs")
        if mk:
            ki[mk] = r
    return ki


def _ment(db: Session, meglevo: dict[str, PlaybookRule], mk: str, *, hatokor: str, cim: str, tartalom: str,
          feltetelek: dict, esetek: list[str]) -> str:
    """Új `pending` szabály, vagy a még jóvá nem hagyott javaslat frissítése.
    Élesített (vagy ember által elvetett) szabályhoz nem nyúl."""
    r = meglevo.get(mk)
    if r is not None:
        if r.allapot == RuleState.PENDING.value and (r.tartalom != tartalom or (r.forras_esetek or {}).get("peldak") != esetek):
            r.tartalom = tartalom
            r.cim = cim[:200]
            r.forras_esetek = {"peldak": esetek}
            return "frissitve"
        return "megvan"
    r = PlaybookRule(
        hatokor=hatokor,
        cim=cim[:200],
        tartalom=tartalom,
        feltetelek={"forras": "megerosites", "minta_kulcs": mk, **feltetelek},
        prioritas=5,
        verzio=1,
        allapot=RuleState.PENDING.value,  # SOHA nem élesedik magától
        forras_esetek={"peldak": esetek},
    )
    db.add(r)
    meglevo[mk] = r
    return "uj"


def _szabalyjavaslatok(db: Session, csoportok: dict, partner_ossz: Counter) -> dict:
    meglevo = _meglevo(db)
    stat: Counter = Counter()
    for (kulcs, pk, minta), lista in csoportok.items():
        ervenyes = [e for e in lista if e.chunk.ervenyes and not e.chunk.visszavont]
        partner = lista[0].partner_nev
        esetek = sorted(e.chunk.forras for e in ervenyes)[:50]

        if minta == ("teny",):
            # Fizetési szokás: átlagos késés a határidőhöz képest.
            kulesek = [e.meta.get("kules_nap") for e in ervenyes if isinstance(e.meta.get("kules_nap"), int)]
            if len(kulesek) < BEVETEL_MIN_ESET:
                continue
            atlag = round(mean(kulesek))
            leiras = (
                f"átlagosan {atlag} nappal a határidő UTÁN fizet" if atlag > 0
                else ("általában határidőre fizet" if atlag == 0 else f"átlagosan {-atlag} nappal a határidő előtt fizet")
            )
            mk = f"bevetel|{pk}"
            stat[_ment(
                db, meglevo, mk, hatokor="kintlevoseg",
                cim=f"{partner}: {leiras}",
                tartalom=(
                    f"A(z) „{partner}” megrendelő {leiras} ({len(kulesek)} rögzített fizetés alapján; "
                    f"a legnagyobb késés {max(kulesek)} nap). A kintlevőségeknél ehhez mérd, mikor kell jelezni."
                ),
                feltetelek={"partner": pk, "partner_nev": partner, "atlag_kules_nap": atlag, "fizetesek": len(kulesek)},
                esetek=esetek,
            )] += 1
            continue

        n = len(ervenyes)
        if n < SZABALY_MIN_ESET or n / partner_ossz[(kulcs, pk)] < SZABALY_EGYETERTES:
            continue
        if any(e.chunk.visszavont for e in lista):
            continue
        mk = f"{kulcs}|{pk}|{json.dumps(list(minta), ensure_ascii=False)}"
        hatter = f"(Lara javaslata: {n} jóváhagyott, egybehangzó eset alapján; élesíteni ember tudja.)"

        if kulcs == "visszajatszas":
            # Ugyanaz a formátum, amit az önellenőrzés és az éles számla-elemzés olvas.
            stat[_ment(
                db, meglevo, mk, hatokor="szamla",
                cim=f"{partner}: {CEL_CIMKE.get(minta[1], minta[1])}",
                tartalom=f"A(z) „{partner}” számlái rendre így kerülnek rögzítésre: {CEL_CIMKE.get(minta[1], minta[1])}. {hatter}",
                feltetelek={"partner": pk, "partner_nev": partner, "cel_tipus": minta[1], "projektkod_idk": []},
                esetek=esetek,
            )] += 1
        elif kulcs in ("szerzodes", "tig") and minta[0] == "papir":
            # A papír-önellenőrzés formátuma: dimenziónként egy szabály (mezo/ertek).
            papir = "szerződés" if kulcs == "szerzodes" else "TIG"
            if minta[1]:
                stat[_ment(
                    db, meglevo, mk + "|kihagyas", hatokor=kulcs,
                    cim=f"{partner}: {papir} — nem készül (kihagyva)",
                    tartalom=f"A(z) „{partner}” esetén a {papir} rendre KIMARAD. {hatter}",
                    feltetelek={"partner": pk, "partner_nev": partner, "mezo": "kihagyas", "ertek": True},
                    esetek=esetek,
                )] += 1
            elif minta[2] is not None:
                stat[_ment(
                    db, meglevo, mk + "|afa", hatokor=kulcs,
                    cim=f"{partner}: {papir} — {'+ÁFA' if minta[2] else 'ÁFA nélkül'}",
                    tartalom=f"A(z) „{partner}” {papir}ja rendre {'+ÁFA-s' if minta[2] else 'ÁFA nélküli'}. {hatter}",
                    feltetelek={"partner": pk, "partner_nev": partner, "mezo": "afa", "ertek": bool(minta[2])},
                    esetek=esetek,
                )] += 1
        else:
            hatokor = ervenyes[0].chunk.hatokor
            szoveg = _minta_szoveg(kulcs, minta)
            stat[_ment(
                db, meglevo, mk, hatokor=hatokor,
                cim=f"{partner}: {_cimke(kulcs)} — {szoveg}",
                tartalom=f"A(z) „{partner}” — {_cimke(kulcs)}: rendre így: {szoveg}. {hatter}",
                feltetelek={"partner": pk, "partner_nev": partner, "forras_tipus": kulcs, "minta": list(minta)},
                esetek=esetek,
            )] += 1
    db.flush()
    return {"uj_szabalyjavaslat": stat["uj"], "frissitett_szabalyjavaslat": stat["frissitve"]}


def allapot(db: Session) -> dict:
    """A Tanulás oldal kártyájához: mennyit hagyott jóvá magától Lara, és a
    legutóbbi futások."""
    auto = db.scalars(select(MemoryChunk).where(MemoryChunk.minosites == AUTO)).all()
    javaslatok = [
        r for r in db.scalars(select(PlaybookRule).where(PlaybookRule.allapot == RuleState.PENDING.value)).all()
        if (r.feltetelek or {}).get("forras") == "megerosites"
    ]
    be, min_eset = beallitas(db)
    futasok = db.scalars(
        select(LearningRun).where(LearningRun.trigger.like(f"{TRIGGER}%")).order_by(LearningRun.id.desc()).limit(10)
    ).all()
    return {
        "bekapcsolva": be,
        "min_eset": min_eset,
        "auto_jovahagyott": sum(1 for m in auto if m.ervenyes and not m.visszavont),
        "auto_elvetve": sum(1 for m in auto if m.visszavont),
        "szabalyjavaslat": len(javaslatok),
        "futasok": [
            {"id": f.id, "trigger": f.trigger, "veg_at": f.veg_at.isoformat() if f.veg_at else None,
             **{k: (f.osszefoglalo or {}).get(k) for k in ("auto_jovahagyott", "uj_szabalyjavaslat", "vizsgalt_pelda")}}
            for f in futasok
        ],
    }
