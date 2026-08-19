"""Az ELSZÁMOLÁS közös szabálya: mennyi egy tétel, ha összeadjuk.

**A nettó a mérvadó** - bevételnél és kiadásnál egyaránt. Ez nem stílus
kérdése: az ÁFA átfolyó tétel, a cégnél sem bevételként, sem költségként nem
marad ott. Ha a bevételt bruttóban, a kiadást szintén bruttóban néznénk, a
kettő különbsége (a "profit") az ÁFA-tartalmak különbségével csúszna el -
annál nagyobbal, minél jobban eltér a két oldal ÁFA-kulcsa (nem minden
szállító áfás, és nem mindegyik 27%).

Korábban a rendszer a BRUTTÓT vette elsőnek mindenütt, ahol volt. Ez két
igazságot csinált egy számból: ugyanannak a projektnek a profitja mást
mutatott attól függően, hogy a sorain kitöltötték-e a bruttót vagy sem
(a kézzel felvitt tételeknél csak a nettót kérjük be, a Notionból hozottakon
viszont gyakran a bruttó is ott van).

A szabály tehát:

    összeg = nettó, ha meg van adva; különben a bruttó (jobb híján)

A bruttóra visszaesés nem az ÁFA-s szemlélet visszacsempészése, hanem
adathiány kezelése: ha egy régi soron CSAK bruttó van, az még mindig
közelebb van az igazsághoz, mint a nulla. ÁFÁ-t viszont nem "számolunk
vissza" belőle: a 27%-os osztás ugyanolyan találgatás lenne, mint a
felszorzás.

A BRUTTÓ nem tűnik el: ahol a tényleges pénzmozgás a kérdés (mennyi megy ki a
bankszámláról), ott külön kiírjuk - lásd a Pénzügyek összesítőjének
`ytd_bevetel_brutto` / `ytd_kiadas_brutto` mezőit. Az elszámolásban viszont
mindenütt a nettó szerepel.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func

#: A magyar általános ÁFA-kulcs szorzója. Csak ott használjuk, ahol a bruttót
#: TÁJÉKOZTATÁSUL írjuk ki egy ismerten áfás nettó mellé - összeadni sosem.
AFA_SZORZO = 1.27


def osszeg(sor: Any) -> float:
    """Egy bevétel-/kiadás-sor elszámolási összege: a NETTÓ.

    Ha a nettó nincs megadva, a bruttóra esünk vissza (lásd a modul
    fejlécét) - üres soron nulla."""
    ertek = getattr(sor, "netto", None)
    if ertek is not None:
        return float(ertek)
    return float(getattr(sor, "brutto", None) or 0)


def brutto_osszeg(sor: Any) -> float:
    """Ugyanaz fordítva: a TÉNYLEG mozgó pénz (bruttó), nettóra visszaesve.

    Csak tájékoztató kiírásokhoz - összesítésbe, profitba nem való."""
    ertek = getattr(sor, "brutto", None)
    if ertek is not None:
        return float(ertek)
    return float(getattr(sor, "netto", None) or 0)


def netto_sql(model: Any):
    """Ugyanez a szabály SQL-ben, összegzéshez:
    ``func.sum(elszamolas.netto_sql(Revenue))``.

    A COALESCE sorrendje szándékosan azonos a Python-változatéval - két helyen
    ugyanaz a szám kell, különben az összesítő és a kártya vitatkozna."""
    return func.coalesce(model.netto, model.brutto, 0)


def brutto_sql(model: Any):
    """A tájékoztató bruttó összeg SQL-ben (lásd `brutto_osszeg`)."""
    return func.coalesce(model.brutto, model.netto, 0)
