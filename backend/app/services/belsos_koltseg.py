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

from typing import Any

from app.models.employee import EmployeeType


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


def projekt_koltsege(project: Any) -> float:
    """A projekten dolgozó BELSŐSÖK napidíjának összege (napok × napidíj).

    Akinek nincs beírt napidíja, az nullával szerepel - nem tippelünk helyette
    összeget, mert egy kitalált szám rosszabb, mint a hiánya: az utóbbi
    legalább látszik a napidíj-oszlopban."""
    napok = projekt_napjai(project)
    return sum(
        float(tag.napi_dij) * napok
        for tag in getattr(project, "crew", []) or []
        if tag.tipus == EmployeeType.BELSOS and tag.napi_dij
    )


def projektkod_koltsege(project_code: Any) -> float:
    """Ugyanez a projektkód ALATT futó összes forgatásra."""
    return sum(projekt_koltsege(p) for p in getattr(project_code, "projects", []) or [])
