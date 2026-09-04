"""A vágói játék pontszámítása.

A pont KÉT forrásból jön, és a kettőt szándékosan máshogy kezeljük:

- **Ellenőrzésbe tett anyag (50 pont)**: saját esemény-táblából, mert a pont a
  megtörtént eseményhez tartozik, nem az anyag mai állapotához (lásd
  models/vagoi_jatek.py).
- **Vágás (3 perc = 1 pont)**: a timesheet-ekből SZÁMÍTVA, mert ott az adat
  már megvan és folyamatosan keletkezik. Nem másoljuk át egy pont-táblába:
  egy javított időmérés így magától javítja a pontot is, nem kell
  szinkronban tartani két igazságot.

A végén jön az arányosítás munkanapra - ez teszi összemérhetővé azt, aki 12
napot dolgozott, azzal, aki 22-t.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.deliverable import Deliverable
from app.models.employee import Employee
from app.models.timesheet import Timesheet
from app.models.vagoi_jatek import (
    ALAP_MUNKANAP,
    ELLENORZES_PONT,
    JAVITAS_PONT,
    JOVAHAGYAS_PONT,
    PERC_PER_PONT,
    VagoEllenorzesEsemeny,
    VagoEllenorzesKimenet,
    VagoJatekHonap,
    VagoJatekNap,
)


def _ekezet_nelkul(szoveg: str) -> str:
    """Kisbetűs, ékezet nélküli alak - az állapotnevek szabad szövegek, és
    "Ellenőrzés" / "ellenorzes" / "ELLENŐRZÉSRE VÁR" mind ugyanaz."""
    return "".join(
        c for c in unicodedata.normalize("NFD", szoveg.casefold()) if unicodedata.category(c) != "Mn"
    )


def ellenorzes_allapot(allapot: str | None) -> bool:
    """Ellenőrzésnek számít-e ez az állapot?

    Az állapotok szabad szövegek (admin szerkeszti őket, lásd
    models/deliverable_status.py), ezért nem egy fix listához hasonlítunk,
    hanem a nevében keressük az "ellenőrzés" szót. Így egy átnevezés
    ("Ellenőrzésre vár") nem töri el némán a pontozást."""
    if not allapot:
        return False
    return "ellenorzes" in _ekezet_nelkul(allapot)


def rogzitsd_ellenorzest(db: Session, deliverable: Deliverable, employee: Employee) -> bool:
    """Feljegyzi, hogy ez az anyag ellenőrzésbe került. True, ha ÚJ esemény.

    Idempotens: ugyanahhoz az anyaghoz csak egyszer keletkezik esemény, tehát
    a ki-be kattintgatás nem termel pontot. A commitot a hívóra hagyjuk, hogy
    egy tranzakcióban maradjon az állapotváltással."""
    letezo = db.scalar(
        select(VagoEllenorzesEsemeny).where(VagoEllenorzesEsemeny.deliverable_id == deliverable.id)
    )
    if letezo is not None:
        return False
    db.add(
        VagoEllenorzesEsemeny(
            deliverable_id=deliverable.id,
            employee_id=employee.id,
            idopont=datetime.now(timezone.utc),
            allapot=deliverable.allapot,
        )
    )
    return True


def javitas_allapot(allapot: str | None) -> bool:
    """Javításnak számít-e ez az állapot - ugyanaz a névben-keresős elv, mint
    az ellenorzes_allapot-nál: egy átnevezés ne törje el némán a pontozást."""
    if not allapot:
        return False
    return "javitas" in _ekezet_nelkul(allapot)


def kikuldes_allapot(allapot: str | None) -> bool:
    """Kiküldés-féle állapot-e ("Kiküldésre vár", "Kész kiküldve",
    "Kiküldhető") - az ide lépés a "jó az anyag" ítélet."""
    if not allapot:
        return False
    return "kikuld" in _ekezet_nelkul(allapot)


def aktualis_allapot(allapot: str | None) -> bool:
    """"Aktuális"-féle (épp vágás alatt álló) állapot-e - ugyanaz a
    névben-keresős elv, mint a többi felismerőnél."""
    if not allapot:
        return False
    return "aktualis" in _ekezet_nelkul(allapot)


def rogzitsd_kimenetet(db: Session, deliverable: Deliverable, regi_allapot: str | None) -> bool:
    """A TOVÁBBLÉPŐ anyag ítélete.

    - Ellenőrzésből kiküldés-féle állapotba: +JOVAHAGYAS_PONT ("javítás
      nélkül jó"); ellenőrzésből javításba: JAVITAS_PONT (negatív).
    - JAVÍTÁSBÓL vagy AKTUÁLISBÓL KÖZVETLENÜL kiküldés-féle állapotba (a
      felhasználó kérése): az is +JOVAHAGYAS_PONT - ugyanaz, mintha rögtön
      el lett volna fogadva, csak a lépés nem ment át még egyszer az
      ellenőrzés oszlopon.

    A pontot az kapja, aki az anyagot ellenőrzésbe tette (VagoEllenorzesEsemeny);
    ha ilyen esemény nincs (pl. aktuálisból ugrott rögtön kiküldésre), akkor
    az anyagra kiosztott vágó. Ha egyik sincs, nincs kit jutalmazni.

    Jóváhagyás és javítás anyagonként EGYSZER-EGYSZER jár: a ki-be tologatás
    nem termel újabb pontot, de egy javítás UTÁNI elfogadás plusz pontja a
    korábbi levonás mellett is megszületik. True, ha ÚJ kimenet keletkezett;
    a commit a hívóé."""
    uj_allapot = deliverable.allapot
    if ellenorzes_allapot(uj_allapot):
        return False
    if ellenorzes_allapot(regi_allapot):
        if javitas_allapot(uj_allapot):
            kimenet, pont = "javitas", JAVITAS_PONT
        elif kikuldes_allapot(uj_allapot):
            kimenet, pont = "jovahagyva", JOVAHAGYAS_PONT
        else:
            return False
    elif (javitas_allapot(regi_allapot) or aktualis_allapot(regi_allapot)) and kikuldes_allapot(uj_allapot):
        kimenet, pont = "jovahagyva", JOVAHAGYAS_PONT
    else:
        return False
    letezok = db.scalars(
        select(VagoEllenorzesKimenet).where(VagoEllenorzesKimenet.deliverable_id == deliverable.id)
    ).all()
    # Ugyanabból a fajta ítéletből nem születik második; javítás-ítélet pedig
    # csak ELSŐ ítéletként (aki egyszer már jóvá lett hagyva, azt egy későbbi
    # tologatás ne büntesse).
    if any(k.kimenet == kimenet for k in letezok):
        return False
    if kimenet == "javitas" and letezok:
        return False
    esemeny = db.scalar(
        select(VagoEllenorzesEsemeny).where(VagoEllenorzesEsemeny.deliverable_id == deliverable.id)
    )
    if esemeny is not None:
        employee_id = esemeny.employee_id
    elif kimenet == "jovahagyva" and deliverable.assigned_to_employee_id:
        employee_id = deliverable.assigned_to_employee_id
    else:
        return False
    db.add(
        VagoEllenorzesKimenet(
            deliverable_id=deliverable.id,
            employee_id=employee_id,
            idopont=datetime.now(timezone.utc),
            kimenet=kimenet,
            pont=pont,
            allapot=uj_allapot,
        )
    )
    # A session autoflush=False - flush nélkül egy ugyanebben a tranzakcióban
    # jövő második hívás nem látná ezt a sort, és duplán pontozna.
    db.flush()
    return True


def honap_hatarai(ev: int, honap: int) -> tuple[datetime, datetime]:
    """A hónap [kezdet, vég) határa időbélyegként, BUDAPESTI idő szerint.

    A verseny hónapja a magyar naptár szerint fordul: aki magyar idő szerint
    szeptember 1-én hajnali fél 1-kor tesz ellenőrzésbe egy anyagot, az már a
    szeptemberi versenybe számít - UTC-határokkal még augusztusba esne, mert
    a szerver órája ilyenkor még augusztus 31., este fél 11-et mutat. Az
    összehasonlítás így is helyes: az időbélyegek zóna-tudatosak."""
    from app.services.hu_datum import BUDAPEST_IDOZONA

    kezdet = datetime(ev, honap, 1, tzinfo=BUDAPEST_IDOZONA)
    veg = datetime(ev + (honap == 12), 1 if honap == 12 else honap + 1, 1, tzinfo=BUDAPEST_IDOZONA)
    return kezdet, veg


@dataclass
class Allas:
    """Egy versenyző állása egy hónapban."""

    employee_id: int
    nev: str
    #: Hány anyagot tett ellenőrzésbe, és az abból járó pont.
    ellenorzes_db: int = 0
    ellenorzes_pont: int = 0
    #: Vágással töltött percek és az abból járó pont.
    vagas_perc: float = 0.0
    vagas_pont: int = 0
    #: Hány anyaga ment át ellenőrzésen javítás nélkül (+), és hány került
    #: javításba (-), meg az ezekből járó pont-egyenleg.
    jovahagyas_db: int = 0
    javitas_db: int = 0
    kimenet_pont: int = 0
    #: A kettő összege, arányosítás ELŐTT.
    nyers_pont: int = 0
    #: Ennyi munkanapja volt (beállítás vagy az alapérték).
    munkanap: int = ALAP_MUNKANAP
    #: A verseny hivatalos pontszáma: nyers x (20 / munkanap).
    pont: int = 0
    #: Hányadik helyen áll. 1-től, holtversenynél azonos hely.
    helyezes: int = 0


def _percek_honapra(db: Session, kezdet: datetime, veg: datetime) -> dict[int, float]:
    """Emberenként a hónapban vágással töltött percek.

    A mérés a START dátuma szerint tartozik egy hónapba: az éjfélen átnyúló
    munka annál a napnál marad, amikor elkezdték - így egyetlen mérés sem
    hasad ketté, és a napi/havi összegek is stimmelnek egymással.

    A `time_minutes` erősebb a start/end különbségénél: a lezáráskor oda kerül
    a végleges érték, és a kézzel javított időt is az őrzi (lásd
    services/deliverable_actions.py)."""
    sorok = db.scalars(
        select(Timesheet).where(Timesheet.start_date >= kezdet, Timesheet.start_date < veg)
    ).all()
    eredmeny: dict[int, float] = {}
    for t in sorok:
        percek = float(t.time_minutes) if t.time_minutes is not None else float(t.idotartam_perc or 0)
        if percek <= 0:
            continue
        eredmeny[t.employee_id] = eredmeny.get(t.employee_id, 0.0) + percek
    return eredmeny


def _helyezesek(allasok: list[Allas]) -> None:
    """Helyezés beírása. Holtversenynél AZONOS hely, és a következő hely
    ugyanannyival ugrik (1., 1., 3.) - egy versenyben a holtverseny nem
    dönthető el önkényesen, mondjuk névsor szerint.

    Aki 0 ponton áll, az nem kap helyezést: a "17. helyezett 0 ponttal" nem
    eredmény, csak zaj a listán."""
    elozo_pont: int | None = None
    elozo_hely = 0
    for i, a in enumerate(allasok, start=1):
        if a.pont <= 0:
            a.helyezes = 0
            continue
        if a.pont == elozo_pont:
            a.helyezes = elozo_hely
        else:
            a.helyezes = i
            elozo_hely = i
            elozo_pont = a.pont


def honap_allasa(db: Session, ev: int, honap: int) -> list[Allas]:
    """Egy hónap teljes állása, a legtöbb ponttal elöl.

    Mindenki bekerül, akinek AZ ADOTT HÓNAPBAN volt teljesítménye vagy
    beállított munkanapja - nem az összes munkatárs. Egy verseny listáján a
    nulla pontos nevek csak elfedik, kik versenyeznek valójában."""
    kezdet, veg = honap_hatarai(ev, honap)

    esemenyek = db.scalars(
        select(VagoEllenorzesEsemeny).where(
            VagoEllenorzesEsemeny.idopont >= kezdet, VagoEllenorzesEsemeny.idopont < veg
        )
    ).all()
    kimenetek = db.scalars(
        select(VagoEllenorzesKimenet).where(
            VagoEllenorzesKimenet.idopont >= kezdet, VagoEllenorzesKimenet.idopont < veg
        )
    ).all()
    percek = _percek_honapra(db, kezdet, veg)
    napok = {
        n.employee_id: n
        for n in db.scalars(select(VagoJatekNap).where(VagoJatekNap.ev == ev, VagoJatekNap.honap == honap)).all()
    }

    erintett: set[int] = (
        set(percek) | {e.employee_id for e in esemenyek} | {k.employee_id for k in kimenetek} | set(napok)
    )
    if not erintett:
        return []
    nevek = {
        e.id: e.full_name for e in db.scalars(select(Employee).where(Employee.id.in_(erintett))).all()
    }

    allasok: list[Allas] = []
    for employee_id in erintett:
        sajat_esemenyek = [e for e in esemenyek if e.employee_id == employee_id]
        sajat_kimenetek = [k for k in kimenetek if k.employee_id == employee_id]
        vagas_perc = percek.get(employee_id, 0.0)
        munkanap = napok[employee_id].munkanap if employee_id in napok else ALAP_MUNKANAP
        # 0 vagy negatív munkanap: az arányosítás nullával osztana. Aki egy
        # napot sem dolgozott, annak nincs mit arányosítani sem - marad a
        # nyers pont (ami ilyenkor jellemzően 0).
        szorzo = (ALAP_MUNKANAP / munkanap) if munkanap > 0 else 1.0

        a = Allas(
            employee_id=employee_id,
            nev=nevek.get(employee_id, f"#{employee_id}"),
            ellenorzes_db=len(sajat_esemenyek),
            ellenorzes_pont=len(sajat_esemenyek) * ELLENORZES_PONT,
            vagas_perc=vagas_perc,
            # Lefelé kerekítünk: a megkezdett 3 perc még nem teljes pont.
            vagas_pont=int(vagas_perc // PERC_PER_PONT),
            jovahagyas_db=sum(1 for k in sajat_kimenetek if k.kimenet == "jovahagyva"),
            javitas_db=sum(1 for k in sajat_kimenetek if k.kimenet == "javitas"),
            kimenet_pont=sum(k.pont for k in sajat_kimenetek),
            munkanap=munkanap,
        )
        a.nyers_pont = a.ellenorzes_pont + a.vagas_pont + a.kimenet_pont
        a.pont = round(a.nyers_pont * szorzo)
        allasok.append(a)

    # Azonos pontnál névsor - hogy a lista sorrendje ne ugráljon lekérésenként.
    allasok.sort(key=lambda x: (-x.pont, x.nev))
    _helyezesek(allasok)
    return allasok


def honap_beallitas(db: Session, ev: int, honap: int) -> VagoJatekHonap | None:
    return db.scalar(select(VagoJatekHonap).where(VagoJatekHonap.ev == ev, VagoJatekHonap.honap == honap))


#: A győztes ünneplő widgete ennyi napig látszik a dashboardján a kihirdetés
#: után (a felhasználó kérése: 5 nap).
GYOZTES_WIDGET_NAPOK = 5

#: Az ELSŐ hónap, aminek hónapzáráskor győztest hirdetünk. A korábbi hónapokra
#: van ugyan adat (timesheet-ek), de a játék akkor még nem élt - egy
#: visszamenőleges "megnyerted a júliusi játékot" értesítés olyan versenyről
#: gratulálna, amiről a versenyzők nem is tudtak.
JATEK_KEZDETE: tuple[int, int] = (2026, 8)


def elozo_honap(ma: date) -> tuple[int, int]:
    """A mai naphoz képest az előző hónap (év, hónap) párja."""
    utolso_nap = date(ma.year, ma.month, 1) - timedelta(days=1)
    return utolso_nap.year, utolso_nap.month


def havi_zaras(db: Session) -> None:
    """Hónapváltáskor kihirdeti az ELŐZŐ hónap győztesét - lustán, egyszer.

    Nincs ütemező a rendszerben (ugyanaz a helyzet, mint a
    papirozas_feladatok-nál): az új hónap ELSŐ dashboard- vagy játék-oldal
    lekérése "éri utol" a zárást. A kihirdetés EGYSZER történik
    (kihirdetve_at őrzi), és onnantól a végeredmény kőbe van vésve - egy
    utólag rögzített mérés már nem válthatja le a kihirdetett győztest.

    A kihirdetéskor:
    - a győztes ÉRTESÍTÉST kap (harang + 5 napig ünneplő dashboard-widget,
      lásd routes/dashboard.summary);
    - az adminok értesítést kapnak, hogy adják meg az ÚJ hónap nyereményét
      (a dashboardjukon bekérő widget is nyílik, amíg meg nem adják) - ezzel
      indul újra a játék az új hónapra.

    Versenyhelyzet (több uvicorn worker egyszerre): a hónap sorát FOR
    UPDATE-tel fogjuk meg, így a kihirdetés és az értesítések csak az egyik
    kérésben történnek meg."""
    from sqlalchemy.exc import IntegrityError

    from app.models.employee import SystemRole, van_szerepkore
    from app.services.notifications import create_notification
    from app.services.hu_datum import budapesti_ma, honap_neve

    # BUDAPESTI idő szerint nézzük, mikor fordul a hónap (a felhasználó
    # kérése): a szerver UTC-ben jár, és magyar idő szerint éjfél után még
    # az előző napot mutatná - a kihirdetés így pontban magyar hónapfordulókor
    # válik esedékessé.
    ma = budapesti_ma()
    ev, honap = elozo_honap(ma)

    # Gyors kiugrás zár nélkül: az esetek 99%-ában már megtörtént a zárás.
    sor = honap_beallitas(db, ev, honap)
    if sor is not None and sor.kihirdetve_at is not None:
        return

    if sor is None:
        sor = VagoJatekHonap(ev=ev, honap=honap)
        db.add(sor)
        try:
            db.flush()
        except IntegrityError:
            # Egy másik worker ugyanebben a pillanatban hozta létre - övé a zárás.
            db.rollback()
            return
    else:
        sor = db.execute(
            select(VagoJatekHonap)
            .where(VagoJatekHonap.ev == ev, VagoJatekHonap.honap == honap)
            .with_for_update()
        ).scalar_one()
        if sor.kihirdetve_at is not None:
            return

    # A játék indulása ELŐTTI hónapot csendben zárjuk le (a jelölés kell, hogy
    # ne fussunk neki minden kérésnél), győztes és értesítés nélkül.
    gyoztes = None
    if (ev, honap) >= JATEK_KEZDETE:
        allas = honap_allasa(db, ev, honap)
        gyoztes = next((a for a in allas if a.helyezes == 1), None)
    sor.kihirdetve_at = datetime.now(timezone.utc)
    if gyoztes is not None:
        sor.gyoztes_employee_id = gyoztes.employee_id
        sor.gyoztes_pont = gyoztes.pont
        nyeremeny_resz = f" Nyereményed: {sor.nyeremeny}." if sor.nyeremeny else ""
        create_notification(
            db,
            employee_id=gyoztes.employee_id,
            kind="vagoi_jatek_gyoztes",
            message=(
                f"Gratulálunk! Megnyerted a {honap_neve(honap)} havi vágói játékot"
                f" {gyoztes.pont} ponttal.{nyeremeny_resz}"
            ),
            link="/vagoi-jatek",
        )

    # Az új hónap nyereményét az adminoktól kérjük be - értesítéssel, azonnal.
    # (A dashboard-widget ettől függetlenül addig látszik nekik, amíg a
    # nyereményt meg nem adják, lásd routes/dashboard.summary.)
    uj_sor = honap_beallitas(db, ma.year, ma.month)
    if uj_sor is None or not uj_sor.nyeremeny:
        adminok = db.scalars(select(Employee).where(Employee.is_active.is_(True))).all()
        for admin in adminok:
            if not van_szerepkore(admin, SystemRole.ADMIN):
                continue
            create_notification(
                db,
                employee_id=admin.id,
                kind="vagoi_jatek_nyeremeny",
                message=(
                    f"Új hónap indult a vágói játékban - add meg a {honap_neve(ma.month)}"
                    " havi nyereményt, hogy a verseny elindulhasson!"
                ),
                link="/vagoi-jatek",
            )
    db.commit()


def elozo_honapok(ev: int, honap: int, darab: int) -> list[tuple[int, int]]:
    """Az adott hónapot MEGELŐZŐ `darab` hónap, a legfrissebbel elöl."""
    eredmeny: list[tuple[int, int]] = []
    e, h = ev, honap
    for _ in range(darab):
        elso = date(e, h, 1) - timedelta(days=1)
        e, h = elso.year, elso.month
        eredmeny.append((e, h))
    return eredmeny
