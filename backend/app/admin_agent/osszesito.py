"""Lara — napi „jóváhagyandó" összesítő és a kérdések értesítései.

Két lassú pontot old meg:

1. A Tudástárban a jelöltek időrendben álltak; aki öt percet szán rá, nem
   tudta, melyikkel kezdje. Az ÉRTÉKRANGSOR azt teszi előre, amelyik jóváhagyása
   a legtöbbet segít: sok eset ugyanattól a partnertől, a csoportja egy lépésre
   van az automatikus megerősítéstől, friss, és ember által elutasított AI-
   asszisztens művelet (erős tanulság) — lásd `ertek_rangsor`.
2. Lara kérdései eddig csak a felületen várták a választ. Mostantól az új
   kérdésről értesítés (és bekapcsolt telefonon push) megy annak, aki az adott
   esetet rögzítette — ő tudja, miért döntött így —, egyébként a Lara-
   felelősöknek.

Mindkettő kikapcsolható: `aa_settings.limitek.napi_osszesito`,
`aa_settings.limitek.kerdes_ertesites` (alap: be). Csak értesítést ír (a
meglévő értesítési/push csatornán); üzleti rekord nem változik.
"""

from __future__ import annotations

import math
from collections import Counter
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin_agent.memory import partner_kulcs
from app.admin_agent.observer import FELRETEVE
from app.admin_agent.settings_service import get_settings
from app.core.security import check_page_action
from app.models.admin_agent import LaraKerdes, MemoryChunk, SourceEvent
from app.models.bejovo_szamla import BejovoSzamla
from app.models.employee import Employee, SystemRole, van_szerepkore
from app.services import notifications

PAGE = "/admin-agent"
KIND_OSSZESITO = "lara_osszesito"
KIND_KERDES = "lara_kerdes"
#: Az összesítőben ennyi legértékesebb jelölt szerepel név szerint.
TOP = 3

#: Forrásonkénti alapsúly: ahol a jelölt a legtöbb döntést befolyásolja.
_FORRAS_SULY = {
    "visszajatszas": 1.4,  # számla-besorolás: az éles elemzés közvetlenül használja
    "megfigyeles": 1.0,
    "levelezes": 0.9,
    "asszisztens": 0.8,
}


def _kapcsolo(db: Session, kulcs: str) -> bool:
    return (get_settings(db).limitek or {}).get(kulcs) is not False


def _most() -> datetime:
    return datetime.now(timezone.utc)


# ── Címzettek ─────────────────────────────────────────────────────────────────


def lara_felelosok(db: Session, *, muvelet: str = "view") -> list[Employee]:
    """Aktív admin / adminisztráció, akinek a Lara-oldalon megvan a kért joga
    (a jóváhagyáshoz: "delete" — a tudás-aktiválási jog)."""
    ki = []
    for e in db.scalars(select(Employee).where(Employee.is_active.is_(True))).all():
        if not (van_szerepkore(e, SystemRole.ADMIN) or van_szerepkore(e, SystemRole.ADMINISZTRACIO)):
            continue
        try:
            check_page_action(db, e, PAGE, muvelet)
        except HTTPException:
            continue
        ki.append(e)
    return ki


# ── Értékrangsor ─────────────────────────────────────────────────────────────


def _partner(m: MemoryChunk, esemeny: dict[str, dict]) -> str:
    meta = esemeny.get(m.forras or "") or {}
    return partner_kulcs(meta.get("partner") or "")


def ertek_rangsor(db: Session, *, limit: int | None = None) -> list[tuple[float, MemoryChunk, list[str]]]:
    """A jóváhagyásra váró jelöltek érték szerint csökkenő sorrendben, az okokkal.

    Pontszám (összeadódik):
    * forrás-alapsúly (lásd `_FORRAS_SULY`),
    * log(1 + ugyanattól a partnertől váró/meglévő esetek száma) — egy jóváhagyás
      sok jövőbeli esetet segít,
    * +1, ha a partner-csoportja egy esetre van az automatikus megerősítéstől,
    * +1, ha az AI asszisztensnél ember ELUTASÍTOTT egy műveletet (erős tanulság),
    * frissesség (0..1, 30 nap alatt lecseng)."""
    from app.admin_agent.megerosites import beallitas

    jeloltek = db.scalars(
        select(MemoryChunk).where(
            MemoryChunk.tanulasi_halmaz == "jovahagyott",
            MemoryChunk.ervenyes.is_(False),
            MemoryChunk.visszavont.is_(False),
            MemoryChunk.minosites != FELRETEVE,
            MemoryChunk.regi_korszak.is_(False),
        )
    ).all()
    if not jeloltek:
        return []
    esemeny: dict[str, dict] = {}
    for se in db.scalars(
        select(SourceEvent).where(SourceEvent.forras.in_(("megfigyeles", "visszajatszas"))).order_by(SourceEvent.id)
    ).all():
        esemeny[f"{se.forras}:{se.forras_azonosito}"] = se.metaadat or {}

    osszes = db.scalars(
        select(MemoryChunk).where(MemoryChunk.visszavont.is_(False), MemoryChunk.regi_korszak.is_(False))
    ).all()
    partner_db: Counter = Counter()
    for m in osszes:
        pk = _partner(m, esemeny)
        if len(pk) >= 3:
            partner_db[pk] += 1
    _, min_eset = beallitas(db)
    most = _most()

    ki: list[tuple[float, MemoryChunk, list[str]]] = []
    for m in jeloltek:
        forras = (m.forras or "").split(":")[0]
        pont = _FORRAS_SULY.get(forras, 0.7)
        okok: list[str] = []
        pk = _partner(m, esemeny)
        n = partner_db.get(pk, 0) if len(pk) >= 3 else 0
        if n > 1:
            pont += math.log1p(n)
            okok.append(f"{n} eset ugyanattól a partnertől")
        if n == min_eset - 1:
            pont += 1.0
            okok.append("egy esetre az automatikus megerősítéstől")
        if forras == "asszisztens" and "ELUTASÍT" in (m.tartalom or "").upper():
            pont += 1.0
            okok.append("elutasított művelet — erős tanulság")
        if m.created_at is not None:
            kor = (most - (m.created_at if m.created_at.tzinfo else m.created_at.replace(tzinfo=timezone.utc))).days
            pont += max(0.0, 1 - kor / 30)
        ki.append((round(pont, 3), m, okok))
    ki.sort(key=lambda x: (x[0], x[1].id), reverse=True)
    return ki[:limit] if limit else ki


# ── Napi összesítő ───────────────────────────────────────────────────────────


def napi_osszesito(db: Session) -> dict:
    """Értesítés a jóváhagyásra jogosultaknak: hány jelölt vár, és melyik a
    legértékesebb (az első `TOP`). Ha nincs várakozó jelölt, nem ír semmit. A hívó commitál."""
    if not _kapcsolo(db, "napi_osszesito"):
        return {"bekapcsolva": False, "ertesitve": 0}
    rangsor = ertek_rangsor(db)
    if not rangsor:
        return {"bekapcsolva": True, "varakozo": 0, "ertesitve": 0}
    kerdes = len(db.scalars(select(LaraKerdes.id).where(LaraKerdes.allapot == "nyitott")).all())
    top = "; ".join(
        (m.tartalom or "").split("\n")[0][:70] + ("…" if len((m.tartalom or "").split("\n")[0]) > 70 else "")
        for _, m, _ in rangsor[:TOP]
    )
    uzenet = (
        f"Lara napi összesítője: {len(rangsor)} tudás-jelölt vár jóváhagyásra"
        + (f", {kerdes} kérdés válaszra" if kerdes else "")
        + f". A legértékesebbek elöl: {top}"
    )
    cimzettek = lara_felelosok(db, muvelet="delete")
    for e in cimzettek:
        notifications.create_notification(
            db, employee_id=e.id, kind=KIND_OSSZESITO, message=uzenet, link="/admin-agent/tudastar?rendezes=ertek"
        )
    db.flush()
    return {"bekapcsolva": True, "varakozo": len(rangsor), "kerdes": kerdes, "ertesitve": len(cimzettek)}


# ── Kérdés-értesítés ─────────────────────────────────────────────────────────


def _rogzito(db: Session, k: LaraKerdes) -> int | None:
    """Aki az esetet rögzítette (a számla jóváhagyója) — ő tudja, miért így."""
    if k.tipus != "szamla_besorolas":
        return None
    idk = [int(e.get("bejovo_id") or 0) for e in (k.kontextus or {}).get("esetek") or []]
    szam = Counter(
        b.jovahagyo_employee_id
        for b in db.scalars(select(BejovoSzamla).where(BejovoSzamla.id.in_(idk))).all()
        if b.jovahagyo_employee_id
    )
    return szam.most_common(1)[0][0] if szam else None


def kerdes_ertesites(db: Session, kerdesek: list[LaraKerdes]) -> int:
    """Az ÚJ kérdésekről értesítés. Címzettenként egy értesítés (több kérdésnél
    összefoglalva), hogy egy első futás 25 kérdése ne 25 push legyen."""
    if not kerdesek or not _kapcsolo(db, "kerdes_ertesites"):
        return 0
    felelosok: list[Employee] | None = None
    cimzettenkent: dict[int, list[LaraKerdes]] = {}
    for k in kerdesek:
        rogzito = _rogzito(db, k)
        aktiv = db.get(Employee, rogzito) if rogzito else None
        if aktiv is not None and aktiv.is_active:
            idk = [aktiv.id]
        else:
            if felelosok is None:
                felelosok = lara_felelosok(db)
            idk = [e.id for e in felelosok]
        for i in idk:
            cimzettenkent.setdefault(i, []).append(k)
    for emp_id, lista in cimzettenkent.items():
        if len(lista) == 1:
            k = lista[0]
            partner = k.partner_nev or "egy partner"
            uzenet = f"Lara kérdése ({partner}): {(k.kerdes or '').strip()[:300]}"
        else:
            nevek = ", ".join(sorted({k.partner_nev or "?" for k in lista})[:4])
            uzenet = f"Larának {len(lista)} új kérdése van ({nevek}{'…' if len(lista) > 4 else ''}) — egy rövid válasz is tudássá válik."
        notifications.create_notification(
            db, employee_id=emp_id, kind=KIND_KERDES, message=uzenet, link="/admin-agent/kerdesek"
        )
    db.flush()
    return len(cimzettenkent)
