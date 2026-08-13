"""Mennyibe kerültek a KÜLSŐSÖK egy projektkódon.

A külsős munka ára a TELJESÍTÉSI IGAZOLÁSOKON (TIG) áll: az mondja meg, kinek
mennyit fizetünk az adott forgatásért. A kifizetéskor ebből keletkezik a Kiadás
sor (lásd routes/performance_certificates.py), de a költség már a kifizetés
ELŐTT is valóságos: a számla be van adva, a pénz ki fog menni. Ha csak a
kifizetett sorokat számolnánk, minden még nem rendezett projekt profitja
hazudna - épp az, amelyik friss.

Ezért a projektkód költségébe **a TIG-ek erre a kódra eső része** kerül, nem a
belőlük keletkezett Kiadás sor. A kettő ugyanaz a pénz: a TIG-ből származó
Kiadás sorokat ezért ki is hagyjuk a kiadás-összegzésből (`tig_kiadas_idk`),
különben kétszer szerepelnének.

**Miért "rá eső rész"?** Egy TIG több projekt munkáját is igazolhatja - egy
ember egy számlán küldi be az egész hetet (lásd
PerformanceCertificateTetel). Ilyenkor a teljes összeg nem ehhez a
projektkódhoz tartozik, csak az a rész, ami az ide tartozó forgatásokra jut."""

from __future__ import annotations

from typing import Any


def _brutto(netto: float, plusz_afa: bool | None) -> float:
    """Ugyanaz a szabály, mint a kifizetésnél: ha a megbízott ÁFÁ-s, a bruttó
    az irányadó, mert ennyi megy ki a házból."""
    return round(netto * 1.27, 2) if plusz_afa else netto


def _tig_resze(cert: Any, projekt_idk: set[int]) -> float:
    """Ebből a TIG-ből mennyi jut a megadott projektekre (nettó)?

    Ha a TIG tételesítve van, a tételek döntenek. A tétel-összeg SZÁNDÉKOSAN
    opcionális (a valóságban gyakran csak a végösszeget tudjuk, azt nem osztjuk
    fel emberre/napra) - ha nincs kitöltve, a TIG összegét egyenlően osztjuk el
    a tételei közt. Ez becslés, de sokkal közelebb van a valósághoz, mint a
    másik két lehetőség: az egészet ideírni (a többi projekt költségét is
    idehúzná), vagy nullát (mintha ingyen lett volna)."""
    osszeg = float(cert.netto_osszeg or 0)
    if not osszeg:
        return 0.0

    tetelek = list(cert.tetelek or [])
    if not tetelek:
        return osszeg if cert.project_id in projekt_idk else 0.0

    sajat = [t for t in tetelek if t.project_id in projekt_idk]
    if not sajat:
        return 0.0
    if all(t.netto_osszeg is not None for t in tetelek):
        return float(sum(t.netto_osszeg for t in sajat))
    return osszeg * len(sajat) / len(tetelek)


def projektkod_kulsos(project_code: Any) -> tuple[float, set[int]]:
    """(a projektkódra eső külsős TIG-összeg bruttóban, a TIG-ekhez tartozó
    Kiadás sorok id-jei).

    A második érték azért kell, hogy a hívó ne számolja bele MÉG egyszer
    ugyanazt a pénzt a kiadás-sorokból (lásd models/project_code.py).

    A KIHAGYOTT TIG-ek is beleszámítanak, ha van rajtuk összeg: a kihagyás azt
    jelenti, hogy a papír nem itt készül (máshol van, vagy nem kell) - a
    kifizetést nem törli el."""
    projektek = list(getattr(project_code, "projects", []) or [])
    projekt_idk = {p.id for p in projektek}
    if not projekt_idk:
        return 0.0, set()

    # Ugyanaz a TIG két forgatáson keresztül is ideérhet (több tétel), ezért
    # azonosító szerint gyűjtjük.
    certek: dict[int, Any] = {}
    for projekt in projektek:
        for cert in getattr(projekt, "performance_certificates", []) or []:
            certek[cert.id] = cert
        for tetel in getattr(projekt, "tig_tetelek", []) or []:
            if tetel.certificate is not None:
                certek[tetel.certificate.id] = tetel.certificate

    osszeg = 0.0
    kiadas_idk: set[int] = set()
    for cert in certek.values():
        resz = _tig_resze(cert, projekt_idk)
        if resz:
            osszeg += _brutto(resz, cert.plusz_afa)
        if cert.expense_id is not None:
            kiadas_idk.add(cert.expense_id)
    return osszeg, kiadas_idk
