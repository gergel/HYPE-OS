"""Admin-Ágens — számla-felvezetés L0 árnyék-elemzés.

Ez a modul köti a beérkező számla (BejovoSzamla) meglévő érkeztető-folyamatát
az ágens-gerinchez: forrásesemény → feladat → ügynökfutás → nyomvonal →
művelet-javaslat, a szerver-oldali policy engine-en át. FONTOS invariánsok:

* L0 (árnyék): itt SEMMILYEN üzleti rekord nem jön létre, és külső hívás sem
  történik — csak az ágens saját `aa_` táblái íródnak. A tényleges rögzítés
  továbbra is a meglévő pénzügyi szolgáltatáson (``szamla_erkeztetes.jovahagy``)
  keresztül, emberi jóváhagyással történik; a javaslat payloadja pontosan azt a
  ``dontes`` alakot írja le, amit az a szolgáltatás vár — de VÉGRE NEM HAJTJUK.
* A döntést (végrehajtható-e, jóváhagyás kell-e, vagy tiltott) kizárólag a
  policy engine hozza (``settings_service.resolve_decision``). A modell nem
  minősítheti magát kevésbé kockázatosnak.
* Idempotens: ugyanarra a számlára ugyanabban az állapotban újrafuttatva nem
  keletkezik duplikált forrásesemény/feladat/javaslat.

A számla-felvezetés kockázata R2 (belső pénzügyi rekord írása): alapból emberi
jóváhagyás-köteles, L0-ban tiltott (árnyék). A banki utalás VÉGREHAJTÁSA nem
része ennek a modulnak.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin_agent.enums import (
    ActorKind,
    AgentRunState,
    ApprovalState,
    ProposalState,
    RiskClass,
    TaskState,
    TaskType,
)
from app.admin_agent.policy import Decision
from app.admin_agent.settings_service import resolve_decision
from app.models.admin_agent import (
    ActionProposal,
    ActionTrace,
    AdminTask,
    AgentRun,
    Approval,
    SourceEvent,
)
from app.models.bejovo_szamla import BejovoSzamla

#: A számla-felvezetés (belső pénzügyi rekord írása) kockázati osztálya.
#: Szerver-oldali, a modell nem csökkentheti.
SZAMLA_KOCKAZAT = RiskClass.R2

#: A javaslatot majd EZ a meglévő szolgáltatás-belépő hajtaná végre (L1+).
VEGREHAJTO_ESZKOZ = "szamla_erkeztetes.jovahagy"

FORRAS = "bejovo_szamla"


def _most() -> datetime:
    return datetime.now(timezone.utc)


def _hash(payload: dict) -> str:
    nyers = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(nyers.encode("utf-8")).hexdigest()


def _cel_tipus(bejovo: BejovoSzamla) -> str | None:
    """A javaslat célja (altípus): amit az érkeztető már kitalált. Ez lesz a
    trust-policy altípusa (pl. 'kiadas_uj', 'mukodesi', 'bontas')."""
    if bejovo.cel_tipus:
        return bejovo.cel_tipus
    javaslat = bejovo.javaslat or {}
    cel = javaslat.get("cel_tipus")
    return cel if isinstance(cel, str) else None


def _javaslat_payload(bejovo: BejovoSzamla, cel_tipus: str | None) -> dict:
    """A ``jovahagy`` szolgáltatás által várt ``dontes`` alak — a meglévő
    érkeztető-javaslatból származtatva. Csak LEÍRJUK, mit tennénk; nem hajtjuk
    végre. A pénzügyi invariánsokat (bevétel projektkódhoz, kiadás projekten,
    nincs dupla könyvelés) maga a szolgáltatás őrzi — mi csak azt a bemenetet
    állítjuk elő, amit az kapna."""
    javaslat = bejovo.javaslat or {}
    payload: dict = {
        "cel_tipus": cel_tipus,
        "cel_project_code_id": bejovo.cel_project_code_id or javaslat.get("cel_project_code_id"),
        "cel_project_id": bejovo.cel_project_id or javaslat.get("cel_project_id"),
        "cel_expense_id": bejovo.cel_expense_id or javaslat.get("cel_expense_id"),
        "netto": float(bejovo.netto) if bejovo.netto is not None else None,
        "brutto": float(bejovo.brutto) if bejovo.brutto is not None else None,
        "penznem": bejovo.penznem,
        "felosztas": javaslat.get("felosztas") or bejovo.bontas,
    }
    # A None-mezőket meghagyjuk: a payload_hash így pontosan tükrözi, mi hiányzik
    # (ezekre az ellenőrzések figyelmeztetnek).
    return payload


def _ellenorzesek(bejovo: BejovoSzamla, cel_tipus: str | None, payload: dict) -> dict:
    """Determinista, szerver-oldali ellenőrzések (nem a modell mondja). Ezek
    döntik el, hogy a javaslat hiányos-e — a hiányos javaslat nem mehet
    végrehajtásra, jóváhagyás mellett sem."""
    hianyok: list[str] = []
    if not cel_tipus:
        hianyok.append("Nincs meghatározva a cél (hová kerüljön a számla).")
    if bejovo.brutto is None and bejovo.netto is None:
        hianyok.append("Hiányzik az összeg (nettó/bruttó).")
    if cel_tipus in ("kiadas_uj", "mukodesi", "auto") and not (
        payload.get("cel_project_code_id") or payload.get("cel_project_id") or cel_tipus == "mukodesi"
    ):
        hianyok.append("Kiadáshoz projekt vagy projektkód szükséges.")
    if bejovo.dokumentum_tipus in ("dijbekero", "ertesito"):
        hianyok.append("Díjbekérő/értesítő nem rögzíthető végleges kiadásként — a számlát kell megvárni.")
    return {"rendben": not hianyok, "hianyok": hianyok}


def _forras_esemeny(db: Session, bejovo: BejovoSzamla) -> SourceEvent:
    """Idempotens forrásesemény: (forras, azonosító, verzió=állapot). Ugyanaz a
    számla ugyanabban az állapotban ugyanazt az eseményt adja vissza."""
    verzio = bejovo.allapot
    se = db.scalar(
        select(SourceEvent).where(
            SourceEvent.forras == FORRAS,
            SourceEvent.forras_azonosito == str(bejovo.id),
            SourceEvent.forras_verzio == verzio,
        )
    )
    if se is not None:
        return se
    se = SourceEvent(
        forras=FORRAS,
        forras_azonosito=str(bejovo.id),
        forras_verzio=verzio,
        allapot="feldolgozva",
        metaadat={
            "szamlaszam": bejovo.szamlaszam,
            "kibocsato_nev": bejovo.kibocsato_nev,
            "fajl_nev": bejovo.fajl_nev,
        },
        tartalom_hash=bejovo.fajl_hash,
        feldolgozva_at=_most(),
    )
    db.add(se)
    db.flush()
    return se


def _feladat(db: Session, bejovo: BejovoSzamla, se: SourceEvent) -> AdminTask:
    """Idempotens feladat: egy beérkező számlához EGY feladat (a
    forras_referenciak alapján). A legutóbbi forrásesemény azonosítóját is
    frissítjük rajta."""
    letezo = db.scalar(
        select(AdminTask).where(
            AdminTask.tipus == TaskType.SZAMLA.value,
            AdminTask.forras_referenciak["bejovo_szamla_id"].astext == str(bejovo.id),
        )
    )
    cim = f"Számla: {bejovo.kibocsato_nev or bejovo.szamlaszam or bejovo.fajl_nev or f'#{bejovo.id}'}"
    if letezo is not None:
        letezo.source_event_id = se.id
        return letezo
    t = AdminTask(
        source_event_id=se.id,
        tipus=TaskType.SZAMLA.value,
        altipus=_cel_tipus(bejovo),
        cim=cim[:300],
        osszefoglalo=None,
        allapot=TaskState.NEW.value,
        prioritas=0,
        trust_level="L0",
        project_id=bejovo.cel_project_id,
        project_code_id=bejovo.cel_project_code_id,
        partner_nev=(bejovo.kibocsato_nev or "").strip()[:255] or None,
        forras_referenciak={"bejovo_szamla_id": bejovo.id},
    )
    db.add(t)
    db.flush()
    return t


def arnyek_elemzes(db: Session, bejovo: BejovoSzamla, *, trigger: str = "manual") -> AdminTask:
    """Egy beérkező számla L0 árnyék-elemzése. A hívó commitál.

    Létrehozza (idempotensen) a forráseseményt, a feladatot, egy ügynökfutást,
    a nyomvonalat és a művelet-javaslatot, a döntést a policy engine adja. L0-ban
    a döntés BLOCKED (árnyék): a javaslat rögzül, de nem hajtódik végre, és
    jóváhagyás sem jön létre. Semmilyen üzleti rekord nem változik.
    """
    se = _forras_esemeny(db, bejovo)
    t = _feladat(db, bejovo, se)

    cel_tipus = _cel_tipus(bejovo)
    t.altipus = cel_tipus

    run = AgentRun(
        task_id=t.id,
        trigger=trigger,
        allapot=AgentRunState.RUNNING.value,
        provider="szabaly",  # determinista leképezés a meglévő érkeztető-javaslatból (nem LLM)
        kezdes_at=_most(),
        terv={"lepes": "arnyek_elemzes", "forras": FORRAS, "bejovo_id": bejovo.id},
    )
    db.add(run)
    db.flush()

    payload = _javaslat_payload(bejovo, cel_tipus)
    ellenorzesek = _ellenorzesek(bejovo, cel_tipus, payload)

    db.add(
        ActionTrace(
            task_id=t.id,
            run_id=run.id,
            szereplo=ActorKind.AGENT.value,
            muvelet="elemzes",
            eroforras=FORRAS,
            diff={"bejovo_allapot": bejovo.allapot, "cel_tipus": cel_tipus, "ellenorzesek": ellenorzesek},
            eredmeny="rendben" if ellenorzesek["rendben"] else "hianyos",
            tortent_at=_most(),
        )
    )

    # A DÖNTÉST a policy engine hozza — a beállítások és a trust-policy alapján.
    dontes = resolve_decision(db, risk=SZAMLA_KOCKAZAT, tipus=TaskType.SZAMLA.value, altipus=cel_tipus)

    javaslat = ActionProposal(
        task_id=t.id,
        run_id=run.id,
        eszkoz=VEGREHAJTO_ESZKOZ,
        payload=payload,
        cel_verziok={"bejovo_szamla": {"id": bejovo.id, "allapot": bejovo.allapot}},
        payload_hash=_hash(payload),
        kockazat=SZAMLA_KOCKAZAT.value,
        ellenorzesek=ellenorzesek,
        allapot=ProposalState.DRAFT.value if not ellenorzesek["rendben"] else ProposalState.READY.value,
    )
    db.add(javaslat)
    db.flush()

    db.add(
        ActionTrace(
            task_id=t.id,
            run_id=run.id,
            szereplo=ActorKind.SYSTEM.value,
            muvelet="policy_dontes",
            eroforras=VEGREHAJTO_ESZKOZ,
            diff={"decision": dontes.decision.value, "reason": dontes.reason, "kockazat": SZAMLA_KOCKAZAT.value},
            eredmeny=dontes.decision.value,
            tortent_at=_most(),
        )
    )

    # A feladat állapota a döntés + az ellenőrzések szerint. L0-ban a döntés
    # BLOCKED → a javaslat kész, de árnyék (nem hajtódik végre).
    if not ellenorzesek["rendben"]:
        t.allapot = TaskState.NEEDS_INFO.value
        t.blokkolo_ok = "; ".join(ellenorzesek["hianyok"])
    elif dontes.decision is Decision.NEEDS_APPROVAL:
        t.allapot = TaskState.AWAITING_APPROVAL.value
        t.blokkolo_ok = None
        db.add(
            Approval(
                proposal_id=javaslat.id,
                payload_hash=javaslat.payload_hash,
                allapot=ApprovalState.PENDING.value,
            )
        )
    elif dontes.decision is Decision.AUTO:
        # L0-ban ide nem jutunk; a végrehajtó réteg a D/E fázis.
        t.allapot = TaskState.QUEUED.value
        t.blokkolo_ok = None
    else:  # BLOCKED (árnyék / modul ki / vészleállítás)
        t.allapot = TaskState.PROPOSAL_READY.value
        t.blokkolo_ok = dontes.reason

    t.kockazat = SZAMLA_KOCKAZAT.value
    t.row_version += 1

    run.allapot = AgentRunState.SUCCEEDED.value
    run.veg_at = _most()

    return t
