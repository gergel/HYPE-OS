"""Admin-Ágens — háttér-tanuló (distill).

A tanulás első változata: retrieval + verziózott playbook. NINCS automatikus
fine-tuning, sem forráskód/prompt/jogosultság csendes átírása. A folyamat a
korrekciókból (emberi javításokból) készít SZABÁLY-JELÖLTEKET és példa-
jelölteket — ezek `pending`/érvénytelen állapotban maradnak, amíg ember tartalmi
jóváhagyást nem ad. Alapelvek (master prompt 11.):

* Egyetlen javításból nem lesz általános aktív szabály (küszöb + emberi jóváhagyás).
* A jelölt nem aktiválhatja magát; konfliktusnál nincs csendes felülírás.
* Idempotens: csak az `uj` korrekciókat dolgozza fel, majd `feldolgozva`-ra
  állítja — újraindításkor nem dolgozza fel kétszer ugyanazt.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin_agent.enums import CorrectionType, RuleState
from app.models.admin_agent import AdminTask, Correction, LearningRun, MemoryChunk, PlaybookRule

#: Ennyi HASONLÓ korrekció kell egy szabály-JELÖLTHEZ (egy javításból nem lesz szabály).
SZABALY_KUSZOB = 2


def _most() -> datetime:
    return datetime.now(timezone.utc)


def _csoport_kulcs(t: AdminTask, c: Correction) -> tuple[str, tuple[str, ...]]:
    """Hasonlóság kulcsa: (feladattípus, az érintett mezők halmaza)."""
    mezok = tuple(sorted((c.mezo_diff or {}).keys()))
    return (t.tipus, mezok)


def distill(db: Session, *, trigger: str = "manual") -> LearningRun:
    """Az `uj` korrekciók feldolgozása szabály-/példa-jelöltekké. A hívó
    commitál. A tényszerű hibákból (a legerősebb jel) csoportosított
    szabály-jelölt lesz; a besorolandó esetekből SOP-kérés-számláló nő."""
    run = LearningRun(trigger=trigger, allapot="futott", kezdes_at=_most())
    db.add(run)
    db.flush()

    sorok = db.execute(
        select(Correction, AdminTask)
        .join(AdminTask, AdminTask.id == Correction.task_id)
        .where(Correction.feldolgozas_allapot == "uj")
        .order_by(Correction.id)
    ).all()

    csoportok: dict[tuple[str, tuple[str, ...]], list[Correction]] = defaultdict(list)
    sop = 0
    utolso_id = None
    for c, t in sorok:
        utolso_id = c.id
        if c.tipus == CorrectionType.BESOROLANDO.value:
            # Kétes eset: nem csoportosítunk belőle szabályt, SOP-kérés lesz.
            sop += 1
        elif c.tipus in (CorrectionType.TENYSZERU_HIBA.value, CorrectionType.STILUS.value):
            csoportok[_csoport_kulcs(t, c)].append(c)
        # EGYSZERI_KIVETEL / UJ_UZLETI_ADAT: nem szabályosít.

    uj_szabaly = 0
    uj_pelda = 0
    for (tipus, mezok), lista in csoportok.items():
        # Példa-JELÖLT minden korrekcióból (érvénytelen, amíg ember jóvá nem hagyja).
        for c in lista:
            db.add(
                MemoryChunk(
                    hatokor=tipus,
                    tartalom=f"Javítás ({', '.join(mezok) or 'általános'}): {c.magyarazat or ''}".strip(),
                    forras=f"correction:{c.id}",
                    minosites="jelolt",
                    tanulasi_halmaz="jovahagyott",
                    ervenyes=False,  # NEM használható éles döntésben jóváhagyásig
                )
            )
            uj_pelda += 1
        if len(lista) >= SZABALY_KUSZOB:
            db.add(
                PlaybookRule(
                    hatokor=tipus,
                    cim=f"Ismétlődő javítás: {', '.join(mezok) or 'általános'} ({tipus})",
                    feltetelek={"tipus": tipus, "mezok": list(mezok)},
                    tartalom=(
                        f"{len(lista)} hasonló emberi javítás alapján: nézd át a(z) "
                        f"{', '.join(mezok) or 'érintett'} mező(ke)t ennél a feladattípusnál."
                    ),
                    prioritas=0,
                    verzio=1,
                    allapot=RuleState.PENDING.value,  # gépi jelölt, emberi jóváhagyásra vár
                    forras_esetek={"correction_ids": [c.id for c in lista]},
                )
            )
            uj_szabaly += 1

    for c, _ in sorok:
        c.feldolgozas_allapot = "feldolgozva"

    run.feldolgozott_korrekciok = len(sorok)
    run.uj_szabaly_jeloltek = uj_szabaly
    run.uj_pelda_jeloltek = uj_pelda
    run.sop_keresek = sop
    run.kurzor = str(utolso_id) if utolso_id is not None else run.kurzor
    run.osszefoglalo = {"csoportok": len(csoportok), "kuszob": SZABALY_KUSZOB}
    run.allapot = "kesz"
    run.veg_at = _most()
    return run
