"""Mely HÓNAPOKRA várunk belsős TIG-et egy munkatárstól?

A belsős havi TIG minden belsőstől minden hónapra elvárt - de csak addig,
amíg tényleg nálunk dolgozott. Aki márciusban lépett be, attól januárra nincs
mit kérni; aki augusztusban kilépett, attól szeptemberre sincs.

A forrás sorrendje szándékosan ilyen:

1. a felvitt BELSŐS IDŐSZAKOK (models/belsos_idoszak.py) - ez a pontos válasz,
   és ez kezeli azt is, ha valaki kilépett, majd visszajött;
2. ha nincs egy időszak sem, a munkatárs `elso_munkanap` / `utolso_munkanap`
   mezője - ez a Notion-importból már ott van a legtöbb embernél, tehát
   külön adatbevitel nélkül is helyes eredményt ad;
3. ha az sincs, minden hónap beleszámít - vagyis a korábbi viselkedés.

Egy hónap akkor számít, ha a belsős viszony a hónap BÁRMELY napján élt: aki
15-én lépett be, attól arra a hónapra is jár TIG (a fél hónapra)."""

from __future__ import annotations

import calendar
from datetime import date

from sqlalchemy.orm import Session, selectinload

from app.models.belsos_idoszak import BelsosIdoszak
from app.models.employee import Employee


def honap_hatarok(ev: int, honap: int) -> tuple[date, date]:
    """A hónap első és utolsó napja."""
    return date(ev, honap, 1), date(ev, honap, calendar.monthrange(ev, honap)[1])


def _atfedi(kezdet: date | None, veg: date | None, honap_eleje: date, honap_vege: date) -> bool:
    """Belelóg-e a [kezdet, veg] időszak a hónapba? A nyitott végek végtelent
    jelentenek."""
    if kezdet is not None and kezdet > honap_vege:
        return False
    if veg is not None and veg < honap_eleje:
        return False
    return True


def belsos_volt(employee: Employee, ev: int, honap: int) -> bool:
    """Belsős volt-e ez az ember az adott hónapban (akár csak részben)?"""
    eleje, vege = honap_hatarok(ev, honap)
    idoszakok = list(employee.belsos_idoszakok or [])
    if idoszakok:
        return any(_atfedi(i.kezdet, i.veg, eleje, vege) for i in idoszakok)
    return _atfedi(employee.elso_munkanap, employee.utolso_munkanap, eleje, vege)


def belsosok(db: Session, ev: int | None = None, honap: int | None = None) -> list[Employee]:
    """A belsős munkatársak - ha megadsz hónapot, csak akik AKKOR belsősök voltak.

    Az időszakokat egyben töltjük be: a havi összesítő tizenkét hónapra hívja
    ezt, és enélkül emberenként külön lekérdezés futna."""
    from app.models.employee import EmployeeType

    emberek = (
        db.query(Employee)
        .options(selectinload(Employee.belsos_idoszakok))
        .filter(Employee.tipus == EmployeeType.BELSOS)
        .order_by(Employee.full_name)
        .all()
    )
    if ev is None or honap is None:
        return emberek
    return [e for e in emberek if belsos_volt(e, ev, honap)]


def idoszak_szoveg(idoszakok: list[BelsosIdoszak]) -> str:
    """Emberi összefoglaló a felületnek: "2024.03.01. – 2025.08.31., 2026.02.01. –"."""
    if not idoszakok:
        return ""
    reszek = []
    for i in idoszakok:
        kezdet = i.kezdet.strftime("%Y.%m.%d.") if i.kezdet else ""
        veg = i.veg.strftime("%Y.%m.%d.") if i.veg else ""
        reszek.append(f"{kezdet} – {veg}".strip())
    return ", ".join(reszek)
