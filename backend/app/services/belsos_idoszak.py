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
3. ha az sincs, akkor a NYOMAI: a legkorábbi havi TIG-je vagy havi tétele. Aki
   sehol nem szerepel, arról nem állítjuk, hogy dolgozott.

A harmadik pont korábban azt mondta, hogy "minden hónap beleszámít". Ez csendes
elcsúszást okozott: aki tévedésből lett belsősnek jelölve (vagy csak nincs
kitöltve az időszaka), az MINDEN hónap listáján ott állt, évekre visszamenőleg
is - pedig ott semmi keresnivalója. Ha nincs adat, inkább nem találgatunk; a
hiányzó időszakokat a felület külön kiírja, hogy pótolni lehessen.

Egy hónap akkor számít, ha a belsős viszony a hónap BÁRMELY napján élt: aki
15-én lépett be, attól arra a hónapra is jár TIG (a fél hónapra)."""

from __future__ import annotations

import calendar
from datetime import date

from sqlalchemy.orm import Session, selectinload

from app.models.belsos_idoszak import BelsosIdoszak
from app.models.employee import BelsosJogviszony, Employee, EmployeeType


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


def van_idoszak_adat(employee: Employee) -> bool:
    """Tudjuk-e egyáltalán, hogy MIKOR volt belsős ez az ember?

    Ha se felvitt időszaka, se első/utolsó munkanapja nincs, akkor nem tudjuk -
    ilyenkor a havi listákhoz a nyomaiból (meglévő TIG-ek, havi tételek)
    következtetünk, és a felület jelzi, hogy az időszakot pótolni kell."""
    return bool(employee.belsos_idoszakok) or employee.elso_munkanap is not None or (
        employee.utolso_munkanap is not None
    )


def belsos_volt(
    employee: Employee, ev: int, honap: int, nyom_kezdet: date | None = None
) -> bool:
    """Belsős volt-e ez az ember az adott hónapban (akár csak részben)?

    A `nyom_kezdet` csak akkor számít, ha semmilyen időszak-adata nincs: ez a
    legkorábbi hónap, amiről tudjuk, hogy már nálunk volt (lásd
    nyom_kezdetek). Enélkül - adat és nyom híján - NEM soroljuk be a hónapba:
    az "alapból mindenhol ott van" feltevés csak hamis teendőt szülne."""
    eleje, vege = honap_hatarok(ev, honap)
    idoszakok = list(employee.belsos_idoszakok or [])
    if idoszakok:
        return any(_atfedi(i.kezdet, i.veg, eleje, vege) for i in idoszakok)
    if employee.elso_munkanap is not None or employee.utolso_munkanap is not None:
        return _atfedi(employee.elso_munkanap, employee.utolso_munkanap, eleje, vege)
    return nyom_kezdet is not None and _atfedi(nyom_kezdet, None, eleje, vege)


def bizonyithatoan_nem_belsos(employee: Employee, nap: date | None) -> bool:
    """Tudjuk-e BIZONYÍTANI, hogy ez az ember EKKOR nem volt belsős?

    Nem ugyanaz, mint a `not belsos_volt(...)`: itt csak akkor mondunk igent,
    ha van mire alapozni. Adat híján nemet adunk - a "nincs róla adat, tehát
    biztosan nem volt belsős" következtetés éppen a hibás irányba téved.

    Azért kell, mert a belsős státusz IDŐSZAKOS: aki ma belsős, tavaly még
    külsősként dolgozhatott, és fordítva. Egy tavalyi projekten tehát simán
    lehetett ő a számlázó fél valaki más munkájáért - a mai típusa alapján
    viszont a rendszer kizárná (lásd routes/project_szamlazok.py)."""
    if nap is None:
        return False
    idoszakok = list(employee.belsos_idoszakok or [])
    if idoszakok:
        return not any(_atfedi(i.kezdet, i.veg, nap, nap) for i in idoszakok)
    if employee.elso_munkanap is not None or employee.utolso_munkanap is not None:
        return not _atfedi(employee.elso_munkanap, employee.utolso_munkanap, nap, nap)
    return False


def belsos_a_napon(employee: Employee, nap: date | None) -> bool:
    """Belsősként dolgozott-e ez az ember EZEN a napon?

    Ez dönti el egy forgatáson, hogy kitől kell papír (szerződés + TIG) és
    kinek a napidíját írjuk a projekt költségébe. A mai típusa önmagában nem
    válasz: a belsős státusz IDŐSZAKOS, és a projektek visszamenőlegesek. Aki
    ma belsős, tavaly még külsősként dolgozhatott - a tavalyi forgatásán tehát
    ugyanúgy jár neki szerződés és TIG, mint bármely más külsősnek.

    Adat híján a MAI típusa dönt (lásd bizonyithatoan_nem_belsos): ha nem
    tudjuk, mikor volt belsős, nem kezdünk el találgatni."""
    if employee.tipus != EmployeeType.BELSOS:
        return False
    return not bizonyithatoan_nem_belsos(employee, nap)


def nyom_kezdetek(db: Session, employee_ids: list[int]) -> dict[int, date]:
    """Kiről mikortól van NYOMUNK, hogy belsősként dolgozott?

    A legkorábbi havi TIG-je vagy havi tétele hónapjának első napja. Ez a
    tartalék azoknál, akiknek nincs felvitt belsős időszaka: így a lista nem
    csúszik el visszamenőleg olyan hónapokra, ahol az illető nem szerepel
    sehol - de aki egyszer már megjelent, az onnantól ott is marad."""
    if not employee_ids:
        return {}
    from app.models.employee_monthly_item import EmployeeMonthlyItem
    from app.models.internal_performance_certificate import InternalPerformanceCertificate

    legkorabbi: dict[int, tuple[int, int]] = {}
    for tabla in (InternalPerformanceCertificate, EmployeeMonthlyItem):
        for employee_id, ev, honap in db.query(tabla.employee_id, tabla.ev, tabla.honap).filter(
            tabla.employee_id.in_(employee_ids)
        ):
            kulcs = (ev, honap)
            meglevo = legkorabbi.get(employee_id)
            if meglevo is None or kulcs < meglevo:
                legkorabbi[employee_id] = kulcs
    return {emp: date(ev, honap, 1) for emp, (ev, honap) in legkorabbi.items()}


def belsosok(db: Session, ev: int | None = None, honap: int | None = None) -> list[Employee]:
    """A belsős munkatársak - ha megadsz hónapot, csak akik AKKOR belsősök voltak.

    Az időszakokat egyben töltjük be: a havi összesítő tizenkét hónapra hívja
    ezt, és enélkül emberenként külön lekérdezés futna."""
    emberek = (
        db.query(Employee)
        .options(selectinload(Employee.belsos_idoszakok))
        .filter(Employee.tipus == EmployeeType.BELSOS)
        .order_by(Employee.full_name)
        .all()
    )
    if ev is None or honap is None:
        return emberek
    nyomok = nyom_kezdetek(db, [e.id for e in emberek if not van_idoszak_adat(e)])
    return [e for e in emberek if belsos_volt(e, ev, honap, nyomok.get(e.id))]


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


def kell_havi_tig(employee: Employee) -> bool:
    """Kell-e ettől a belsőstől havi teljesítési igazolás?

    A bejelentett ALKALMAZOTT bérét bérszámfejtés fizeti: nála nincs TIG,
    nincs számla és nincs "kifizetve" lépés - a havi teendő pusztán annyi,
    hogy a fizetése be legyen írva az adott hónapra (lásd
    models/employee.py BelsosJogviszony).

    Aki folyamatos MEGBÍZÁSI szerződéssel dolgozik, az havonta számláz, tehát
    nála marad a teljes TIG -> számla -> kifizetés folyamat. Ez az
    alapértelmezés, vagyis a mező bevezetése önmagában senkinél nem változtat
    a viselkedésen."""
    return employee.belsos_jogviszony != BelsosJogviszony.ALKALMAZOTT
