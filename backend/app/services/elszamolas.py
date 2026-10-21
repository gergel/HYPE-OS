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

import sqlalchemy as sa
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


# --- Mi számít bele az ÉVES bevételbe? --------------------------------------
#
# Nem minden bevétel-sor pénz, ami befolyt hozzánk ezen az úton. Kétféle van,
# aminek látszania kell (különben a projekt profitja hazudik), de az éves
# bevételbe nem való:
#
#   1. "Nem volt tranzakció" (a Notionból örökölt `bevetel_formaja` érték):
#      a munka meg lett csinálva, de pénzmozgás nem történt.
#   2. Amit a számla-lépésnél kifejezetten kihagytunk a bevételekből
#      (beszámítás, csere, másik cégen át rendezve) - lásd
#      services/megrendeloi_szamla.py.
#
# A projekt SAJÁT bevétele (ProjectCode.bevetel) ettől független: ott MINDEN
# sor számít, mert a profithoz kell. Ez a szabály csak a globális Pénzügyek
# nézetet és a Dashboardot szűri - pontosan úgy, ahogy a kiadás oldalán a
# `hozzaadas_a_kiadasokhoz`.

#: A "nem volt tranzakció" forma felismeréséhez. Kisbetűsítve keressük, mert a
#: mező szabad szöveg (Notion select), és a nagybetűzés soronként változhat.
NEM_VOLT_TRANZAKCIO = "nem volt tranzakc"


def _nem_volt_tranzakcio(forma: Any) -> bool:
    return isinstance(forma, str) and NEM_VOLT_TRANZAKCIO in forma.lower()


def bevetel_beleszamit(sor: Any) -> bool:
    """Beleszámít-e ez a bevétel-sor az ÉVES bevételbe?

    A hiányzó (NULL) jelölés IGENT jelent: a mező bevezetése előtti sorok nem
    tűnhetnek el némán az összesítőkből."""
    if getattr(sor, "beleszamit_a_bevetelekbe", None) is False:
        return False
    return not _nem_volt_tranzakcio(getattr(sor, "bevetel_formaja", None))


def bevetel_kihagyas_oka(sor: Any) -> str | None:
    """Miért NEM számít bele - a felület ezt írja ki a sor mellé. None, ha
    beleszámít."""
    if _nem_volt_tranzakcio(getattr(sor, "bevetel_formaja", None)):
        return "Nem volt tranzakció"
    if getattr(sor, "beleszamit_a_bevetelekbe", None) is False:
        return "Nem kerül a bevételek közé"
    return None


def bevetel_beleszamit_sql(model: Any):
    """Ugyanez SQL-ben, WHERE-hez: ``.where(elszamolas.bevetel_beleszamit_sql(Revenue))``.

    A két ág sorrendje és jelentése azonos a Python-változatéval - két helyen
    ugyanaz a szűrés kell, különben az összesítő és a lista vitatkozna."""
    return sa.and_(
        model.beleszamit_a_bevetelekbe.is_not(False),
        sa.or_(
            model.bevetel_formaja.is_(None),
            sa.not_(func.lower(model.bevetel_formaja).like(f"%{NEM_VOLT_TRANZAKCIO}%")),
        ),
    )
