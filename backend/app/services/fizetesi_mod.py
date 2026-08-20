"""HOGYAN mozgott a pénz - és mennyi készpénz van emiatt a kasszában.

Minden kiadásnál és bevételnél megadható, milyen úton ment/jött a pénz. Ez nem
könyvelési finomság: a KÉSZPÉNZ egy fizikai doboz, aminek van egyenlege, és azt
csak akkor tudjuk, ha minden készpénzes tétel meg van jelölve. Az utalás és a
bankkártya a bankszámlát mozgatja, a kasszát nem.

    kassza egyenleg = a készpénzes BEVÉTELEK - a készpénzes KIADÁSOK

A lista SZÁNDÉKOSAN zárt és egy helyen áll: ha mindenki maga írja be ("kp",
"készpénz", "KP"), akkor az összesítés annyi felé szakad, ahányféleképp
leírták - és a kassza egyenlege pont annyival lesz hamis.
"""

from __future__ import annotations

from typing import Any

from app.services.hu_szoveg import ekezet_nelkul

KESZPENZ = "Készpénz"
ATUTALAS = "Átutalás"
BANKKARTYA = "Bankkártya"

#: KIADÁSNÁL mind a három út járható: a céges kártyával fizetett tétel sem a
#: kasszából, sem külön utalással nem megy.
KIADAS_MODOK: tuple[str, ...] = (KESZPENZ, ATUTALAS, BANKKARTYA)

#: BEVÉTELNÉL kettő: vagy kézbe kapjuk (kassza), vagy a számlára érkezik.
#: Bankkártyás fizetés nálunk nincs - nem fogadunk kártyát, a terminálos
#: bevétel a Krumpellóé, annak saját, napi kassza-zárása van (lásd
#: models/krumpello.py).
BEVETEL_MODOK: tuple[str, ...] = (KESZPENZ, ATUTALAS)

#: Amit készpénznek ismerünk el. A Notionből örökölt sorokon "KP" és "Kp." is
#: előfordul, és mind ugyanazt jelenti.
#:
#: A "készpénz" ÉKEZETES alak nem duplikátum: a Pythonos út ékezet nélkül
#: hasonlít (lásd keszpenzes), az SQL-es viszont csak kisbetűsít (nincs minden
#: telepítésen ékezet-eltávolító függvény), tehát ott az ékezetes alak az, ami
#: ténylegesen illeszkedik.
KESZPENZ_ALAKOK: frozenset[str] = frozenset({"keszpenz", "készpénz", "kp", "kp.", "cash"})


def keszpenzes(mod: Any) -> bool:
    """Készpénzben mozgott-e ez a tétel? Üres/ismeretlen mód: NEM.

    Az üres nem "talán": ha nincs megjelölve, nem tudjuk, tehát nem is
    számoljuk bele a kasszába. Egy találgatott egyenleg rosszabb, mint egy
    hiányos - az utóbbin legalább látszik, mennyi tétel nincs megjelölve."""
    if mod is None:
        return False
    return ekezet_nelkul(str(mod)) in KESZPENZ_ALAKOK


def keszpenz_sql(oszlop):
    """Ugyanez SQL-ben - az összesítők ebből szűrnek.

    A Pythonos és az SQL-es alak PÁRBAN van: ha az egyik változik, a másikat is
    állítani kell, különben a lista mást mutatna, mint az egyenleg."""
    from sqlalchemy import func

    # Az adatbázisban nincs ékezet-eltávolító függvény minden telepítésen,
    # ezért a néhány tényleges alakot soroljuk fel kisbetűsítve.
    return func.lower(func.coalesce(oszlop, "")).in_(sorted(KESZPENZ_ALAKOK))
