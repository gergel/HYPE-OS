"""A belsős munkatársak munkájának ára EGY PROJEKTEN.

A projekt profitja eddig szebbnek látszott a valóságnál: a külsős stáb és az
utómunka pénzbe került, a saját emberünk munkája viszont ingyennek tűnt.
Pedig egy belsős munkanapja is kerül valamibe - ezt írja meg az admin a
munkatársnál (`Employee.napi_dij`), és innentől minden projekt költségébe
beleszámít, amin az illető stábtag volt.

**Ez SOSEM lesz Kiadás sor.** A belsős alapbére a hónap végén, EGYBEN kerül a
kiadások közé (Belsős TIG, lásd models/employee_monthly_item.py); ha a napidíj
külön is bekerülne, ugyanaz a pénz kétszer szerepelne a Pénzügyekben. Ez a
modul ezért csak SZÁMOL - nem ír az adatbázisba.

A vágókkal nem foglalkozik: ők órabérben dolgoznak, a munkájuk ára a mért
időből jön (Deliverable.koltseg, lásd services/deliverable_actions.py)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy.orm import Session, object_session

from app.services import belsos_idoszak, munkanap_szamlalo


def projekt_napjai(project: Any) -> int:
    """Hány NAPOS ez a forgatás? (Legalább egy.)

    Több napos forgatásnál a stáb minden napon ott van, tehát a napidíj is
    annyiszor jár. Ha a záró dátum hiányzik vagy korábbi a kezdőnél (elírás),
    egy napnak vesszük - inkább becsüljük alá a költséget, mint hogy egy
    rossz dátum megsokszorozza."""
    kezdet = getattr(project, "forgatas_datuma", None)
    veg = getattr(project, "forgatas_datuma_vege", None)
    if kezdet is None or veg is None or veg <= kezdet:
        return 1
    return (veg - kezdet).days + 1


def projekt_napjainak_datumai(project: Any) -> list[date]:
    """A forgatás NAPJAI - konkrét dátumokként.

    Azért kellenek a napok külön-külön, mert az áruk nem feltétlenül azonos: a
    hónap közepén elfogyhat valakinek a szerződött napszáma, és onnantól a
    plusz nap díja jár (lásd services/munkanap_szamlalo.py). Egy több napos,
    hónapfordulón átnyúló forgatásnál ez a különbség napokon belül is
    megjelenik."""
    kezdet = getattr(project, "forgatas_datuma", None)
    if kezdet is None:
        return []
    return [kezdet + timedelta(days=i) for i in range(projekt_napjai(project))]


def projekt_koltsege(project: Any, db: Session | None = None) -> float:
    """A projekten dolgozó BELSŐSÖK napidíjának összege.

    Naponként számolunk, nem "napok × napidíj"-jal: akinek elfogyott a havi
    SZERZŐDÖTT NAPSZÁMA, annál a további napok a PLUSZ NAPI DÍJON mennek (lásd
    services/munkanap_szamlalo.napi_dij_a_napra). A kettő ugyanaz marad
    mindenkinél, akinél nincs megadva se napszám, se plusz díj.

    Akinek nincs beírt napidíja, az nullával szerepel - nem tippelünk helyette
    összeget, mert egy kitalált szám rosszabb, mint a hiánya: az utóbbi
    legalább látszik a napidíj-oszlopban.

    "Belsős" A FORGATÁS NAPJÁRA értendő: aki ma belsős, de akkor még
    külsősként dolgozott, annak a munkája a TIG-jén szerepel költségként - a
    napidíja itt ráadásként megduplázná (lásd
    services/belsos_idoszak.belsos_a_napon).

    A `db` a diszpótábla munkanapjaihoz kell. Ha nincs (a hívó egy sima
    objektumon számol), a MUNKAMENETBŐL vesszük - és ha az sincs, mindenki a
    rendes napidíján számol: adat híján nem árazunk át semmit."""
    napok = projekt_napjainak_datumai(project)
    elso_nap = getattr(project, "forgatas_datuma", None)
    munkamenet = db if db is not None else object_session(project)
    osszeg = 0.0
    for tag in getattr(project, "crew", []) or []:
        if not tag.napi_dij or not belsos_idoszak.belsos_a_napon(tag, elso_nap):
            continue
        if munkamenet is None or not tag.szerzodott_napok or tag.plusz_nap_napi_dij is None:
            osszeg += float(tag.napi_dij) * len(napok or [elso_nap])
            continue
        osszeg += sum(munkanap_szamlalo.napi_dij_a_napra(munkamenet, tag, nap) for nap in napok)
    return osszeg


def projektkod_koltsege(project_code: Any, db: Session | None = None) -> float:
    """Ugyanez a projektkód ALATT futó összes forgatásra."""
    munkamenet = db if db is not None else object_session(project_code)
    return sum(projekt_koltsege(p, munkamenet) for p in getattr(project_code, "projects", []) or [])
