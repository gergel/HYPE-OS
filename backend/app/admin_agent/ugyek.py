"""Összekapcsolt esetek (2026-09, D fázis): EGY ÜZLETI ÜGY = EGY ESET.

Eddig a megerősítés és az önellenőrzés REKORDOKAT számolt: ha egy partner
ugyanarra a projektkódra öt számlát küldött, az öt „egybehangzó esetnek”
számított, holott egyetlen üzleti döntés ismétlődött. Ez a modul adja az ügy
kulcsát, amely szerint a darabszám számít:

- van projektkód: `pk:<projektkód-idk>|p:<partnerkulcs>` — ugyanannak a
  partnernek ugyanarra a projektkódra (projektkódokra) eső dokumentumai EGY ügy;
- nincs projektkód (pl. havi közüzemi számla): a dokumentum maga az ügy
  (`egyedi:<azonosító>`), mert minden hónap külön döntés.

ELKÜLÖNÍTETT VIZSGAKÉSZLET (`limitek.vizsgakeszlet`, alap: KI): az ügyek egy
determinisztikus része (`vizsga_arany`, alap 20%, az ügykulcs hash-e szerint)
vizsgaeset. Bekapcsolva ezek az ügyek sem az összesítésbe (megerősítés,
önellenőrzés tudása), sem a Tudáspróba tanító tudásába nem kerülnek, így a
vizsga válasza nem szivároghat át sem közvetlenül, sem profilon vagy levezetett
tudáson át. Kikapcsolva a Tudáspróba eredménye „szennyezett” jelölést kap
(Lara tanulhatott ugyanabból az ügyből).
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable

from sqlalchemy.orm import Session

ALAP_VIZSGA_ARANY = 0.2


def ugy_kulcs(*, partner: str | None, projektkod_idk: Iterable[int] | None = None,
              sajat: str | int | None = None) -> str | None:
    """Az üzleti ügy kulcsa. Projektkód nélkül a dokumentum maga az ügy
    (`sajat`); ha az sincs, None."""
    from app.admin_agent.memory import partner_kulcs

    kodok = sorted({int(k) for k in (projektkod_idk or []) if k})
    pk = partner_kulcs(partner) if partner else ""
    if kodok:
        return f"pk:{','.join(map(str, kodok))}|p:{pk or '-'}"[:200]
    if sajat is not None and str(sajat):
        return f"egyedi:{sajat}"[:200]
    return None


def meta_ugy_kulcs(meta: dict | None, *, sajat: str | int | None) -> str | None:
    """Egy forrásesemény metaadatából (megfigyelés / visszajátszás)."""
    m = meta or {}
    kodok = list(m.get("projektkod_idk") or (m.get("vegso") or {}).get("projektkod_idk") or [])
    if not kodok and isinstance(m.get("project_code_id"), int):
        kodok = [m["project_code_id"]]
    return ugy_kulcs(partner=m.get("partner") or m.get("partner_kulcs"), projektkod_idk=kodok, sajat=sajat)


def _limitek(db: Session) -> dict:
    from app.admin_agent.settings_service import get_settings

    return get_settings(db).limitek or {}


def vizsgakeszlet_be(db: Session) -> bool:
    """Az elkülönített vizsgakészlet be van-e kapcsolva (alap: NEM)."""
    return _limitek(db).get("vizsgakeszlet") is True


def vizsga_arany(db: Session) -> float:
    try:
        a = float(_limitek(db).get("vizsga_arany") or ALAP_VIZSGA_ARANY)
    except (TypeError, ValueError):
        a = ALAP_VIZSGA_ARANY
    return max(0.05, min(a, 0.5))


def vizsga_e(kulcs: str | None, arany: float = ALAP_VIZSGA_ARANY) -> bool:
    """Stabil (futásonként azonos) besorolás az ügykulcs hash-e szerint."""
    if not kulcs:
        return False
    h = int(hashlib.sha256(kulcs.encode("utf-8")).hexdigest()[:8], 16)
    return (h % 1000) < int(arany * 1000)


def kizart(db: Session):
    """Függvény: ügykulcs -> kizárandó-e a TANÍTÓ összesítésből. Kikapcsolt
    vizsgakészletnél semmi sincs kizárva (a meglévő viselkedés marad)."""
    if not vizsgakeszlet_be(db):
        return lambda _k: False
    arany = vizsga_arany(db)
    return lambda k: vizsga_e(k, arany)
