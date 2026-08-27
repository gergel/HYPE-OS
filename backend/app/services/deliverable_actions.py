"""Az Utómunka (Deliverable) oldal kapcsolatai és gombjai: ki hozta létre / kire
van kiosztva, vinyó-lista, Start/Stop időmérés, megrendelői kontaktok +
levezetett email-lista, "Visszajelzés küldése" gomb (a felhasználó által
küldött Notion automatizmus screenshot alapján) és a chat-szerű kommentek."""

from collections.abc import Iterable
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import check_page_action
from app.models.client import Contact
from app.models.deliverable import Deliverable
from app.models.deliverable_comment import DeliverableComment
from app.models.employee import Employee
from app.models.feedback import Feedback
from app.models.rate import Rate
from app.models.timesheet import Timesheet
from app.models.user_access import PageAccessConfig
from app.schemas.deliverable_actions import (
    AssignableEmployee,
    CommentRead,
    ContactOption,
    TimerEmployeeSummary,
    TimerRunningEntry,
    TimerState,
    VinyoOptions,
)
from app.services import attachments, notifications

UTOMUNKA_PAGE = "/utomunka"


def list_assignable_employees(db: Session) -> list[AssignableEmployee]:
    """Kik választhatók az "Assigned To" mezőbe - csak azok, akiknek van
    jelszavuk (be tudnak lépni) ÉS akiknek nincs korlátozva a hozzáférése az
    /utomunka oldaltól (nincs PageAccessConfig soruk, vagy page_permissions=null,
    vagy szerepel benne az /utomunka kulcs)."""
    configs = {c.employee_id: c.page_permissions for c in db.scalars(select(PageAccessConfig))}
    employees = db.scalars(select(Employee).where(Employee.hashed_password.is_not(None), Employee.is_active.is_(True)))
    result = []
    for e in employees:
        page_permissions = configs.get(e.id)
        if e.id not in configs or page_permissions is None or UTOMUNKA_PAGE in page_permissions:
            result.append(AssignableEmployee(id=e.id, full_name=e.full_name))
    return sorted(result, key=lambda e: e.full_name)


VINYO_OPTIONS = [
    "HYPE_Kiemelt projektek",
    "HYPE_01", "HYPE_02", "HYPE_03", "HYPE_04", "HYPE_05", "HYPE_06", "HYPE_07", "HYPE_08",
    "HYPE_09", "HYPE_10", "HYPE_11", "HYPE_13", "HYPE_14", "HYPE_15", "HYPE_16", "HYPE_17",
    "HYPE_18", "HYPE_19", "HYPE_21", "HYPE_22",
    "MyBook_26_01", "MyBook_26_02", "MyBook_26_03", "MyBook_26_04", "MyBook_26_05",
    "MyBook_25_01", "MyBook_25_02", "MyBook_25_03", "MyBook_25_04", "MyBook_25_05",
    "MyBook_25_06", "MyBook_25_07", "MyBook_25_08", "MyBook_11", "MyBook_12", "MyBook_16",
    "Pajta_01", "Pajta_02", "Pajta_03", "Pajta_04",
    "Sárga_01", "Sárga_02",
    "Archive_24_01", "Archive_24_02", "MyBook_25_09", "Archive_24_04", "MTE_01", "BBGP_01",
    "Archive_24_10",
    "Archive_23_01", "Archive_23_02", "Archive_23_03", "Archive_23_04", "Archive_23_05", "Archive_23_06",
    "Archive_21_101", "Archive_21_102", "Archive_21_103", "Archive_21_104", "Archive_21_105", "Archive_21_106",
    "HYPE_F_01", "HYPE_F_02", "MyBook_F_01", "MyBook_F_02",
    "MEGSEMMISÜLT",
]


def get_vinyo_options(db: Session) -> VinyoOptions:
    """A Notionben kézzel konfigurált, rögzített sorrendű vinyó-lista (lásd a
    felhasználó által küldött screenshotok) - ez adja a frontend multi-select
    választható opcióit. A ténylegesen valaha használt, de a fenti listából
    hiányzó értékeket (pl. régi, azóta törölt Notion opciók) a végére fűzzük,
    hogy semmilyen historikus adat ne tűnjön el a választhatók közül."""
    declared = list(VINYO_OPTIONS)
    declared_set = set(declared)
    extras: dict[str, None] = {}
    for (raw,) in db.execute(select(Deliverable.vinyok).where(Deliverable.vinyok.is_not(None))):
        if isinstance(raw, list):
            for v in raw:
                if isinstance(v, str) and v not in declared_set and v not in extras:
                    extras[v] = None
    return VinyoOptions(options=declared + sorted(extras.keys()))


def _recompute_email_list(deliverable: Deliverable) -> None:
    emails = [c.email for c in deliverable.megrendeloi_kontaktok if c.email]
    deliverable.megrendeloi_email_cimek = ", ".join(emails) if emails else None


def set_contacts(db: Session, deliverable: Deliverable, contact_ids: list[int]) -> Deliverable:
    """A "Megrendelői kontaktok" relációt cseréli le a megadott kontakt-ID-kre,
    és újraszámolja a megrendeloi_email_cimek formula-mezőt (vesszővel
    elválasztott email-lista) - ez utóbbi sosem szerkeszthető közvetlenül."""
    contacts = db.scalars(select(Contact).where(Contact.id.in_(contact_ids))).all() if contact_ids else []
    deliverable.megrendeloi_kontaktok = list(contacts)
    _recompute_email_list(deliverable)
    db.commit()
    db.refresh(deliverable)
    return deliverable


def list_contacts(deliverable: Deliverable) -> list[ContactOption]:
    return [ContactOption(id=c.id, full_name=c.full_name, email=c.email) for c in deliverable.megrendeloi_kontaktok]


def aktualis_orabere(db: Session, employee_id: int) -> float | None:
    """A munkatárs MOSTANI órabére (Rate.orabler) - csak a mérés indításakor
    (illetve utólagos javításkor, ha akkor még nem volt rögzítve) kérdezzük le.
    Utána a Timesheet.akkori_orabere befagy: ha valaki később többet keres, az
    a RÉGI költségeket nem írhatja át.

    Ha több Rate sora is van (mert az emelést új sorként vették fel, nem a
    régit írták át), a LEGUTÓBBI (legnagyobb id) számít - az a mostani
    órabére.

    Az órabéreket a KÉRÉS EGÉSZÉRE, EGYETLEN lekérdezéssel szedjük össze (a
    Session.info-ban tárolva). Enélkül a projektkód-lista minden egyes kódnál
    újra lekérdezte ugyanazoknak a vágóknak az órabérét: 800 kódnál ez 7200
    külön kör volt - a lista lekérdezéseinek 99%-a. Emiatt tartott a betöltés
    másodpercekig, hálózaton át (élesben az adatbázis nem a szolgáltatás
    mellett van) pedig akár percekig. Egy órabér egy kérésen belül nem
    változik meg; aki átírja, az a következő kérésben már az újat látja."""
    return _orabérek(db).get(employee_id)


def _orabérek(db: Session) -> dict[int, float]:
    """{munkatárs id: mostani órabér} - kérésenként egyszer, egy lekérdezésből.

    A rates tábla kicsi (munkatársanként pár sor), ezért olcsóbb egyben
    behozni, mint emberenként külön kérdezni. Ha valakinek több sora van, a
    LEGUTÓBBI (legnagyobb id) marad érvényben: id szerint növekvő sorrendben
    olvassuk, így a későbbi felülírja a korábbit."""
    gyorsito = db.info.get("orabér_gyorsito")
    if gyorsito is None:
        gyorsito = {}
        for employee_id, orabler in db.execute(
            select(Rate.employee_id, Rate.orabler).where(Rate.orabler.is_not(None)).order_by(Rate.id)
        ).all():
            gyorsito[employee_id] = float(orabler)
        db.info["orabér_gyorsito"] = gyorsito
    return gyorsito


def szamolt_koltseg(percek: float, orabere: float | None) -> float | None:
    if orabere is None:
        return None
    return round((percek / 60) * float(orabere), 2)


def start_timer(db: Session, deliverable: Deliverable, current_user: Employee) -> None:
    """"Start" gomb - új, nyitott (end_date=None) Timesheet sort hoz létre a
    bejelentkezett felhasználóhoz - egyszerre csak egy fusson, különben a
    Stop nem tudná egyértelműen eldönteni, melyiket zárja le."""
    open_row = db.scalar(
        select(Timesheet).where(
            Timesheet.deliverable_id == deliverable.id,
            Timesheet.employee_id == current_user.id,
            Timesheet.end_date.is_(None),
        )
    )
    if open_row is not None:
        raise ValueError("Már fut egy időmérés ehhez az anyaghoz - előbb állítsd le.")

    db.add(
        Timesheet(
            employee_id=current_user.id,
            deliverable_id=deliverable.id,
            start_date=datetime.now(timezone.utc),
            akkori_orabere=aktualis_orabere(db, current_user.id),
        )
    )
    db.commit()


def stop_timer(db: Session, deliverable: Deliverable, current_user: Employee, employee_id: int | None = None) -> None:
    """"Stop" gomb - lezárja a nyitott Timesheet sort, kiszámolja a ledolgozott
    percet és (ha van óradíj) a költséget.

    `employee_id`: MÁS ember mérésének leállítása (admin joga, lásd a hívó
    végpontot) - erre azért van szükség, mert egy elfelejtett, éjszakán át
    futó mérőt csak az tud lezárni, aki elindította, ő viszont épp nincs
    gépnél."""
    cel_id = employee_id if employee_id is not None else current_user.id
    open_row = db.scalar(
        select(Timesheet).where(
            Timesheet.deliverable_id == deliverable.id,
            Timesheet.employee_id == cel_id,
            Timesheet.end_date.is_(None),
        )
    )
    if open_row is None:
        raise ValueError("Nincs futó időmérés ehhez az anyaghoz.")

    open_row.end_date = datetime.now(timezone.utc)
    minutes = open_row.idotartam_perc or 0
    open_row.time_minutes = minutes
    # Ha az indításkor még nem volt órabér rögzítve (pl. akkor még nem volt Rate
    # sora), most pótoljuk - innentől ez a sor órabére, egy későbbi emelés már
    # nem írja át.
    if open_row.akkori_orabere is None:
        open_row.akkori_orabere = aktualis_orabere(db, open_row.employee_id)
    open_row.koltseg = szamolt_koltseg(minutes, open_row.akkori_orabere)
    # Az utómunkán is nyilvántartjuk, mikor állították le UTOLJÁRA a mérőt -
    # ugyanaz az adat, amit a Notion importban a 'Timesheet Public' End Date
    # mezője hoz (lásd notion_import/importers_wave2.py). Így a listákon és a
    # kapcsolódó táblákban is látszik, soronkénti külön lekérdezés nélkül.
    deliverable.vagas_leallitva = open_row.end_date
    db.commit()


def _may_see_costs(db: Session, employee: Employee) -> bool:
    """A munkaidőhöz tartozó FORINT összegeket csak az látja, akinek a Pénzügy
    oldalhoz van hozzáférése - a vágóknak jellemzően nincs, nekik az idő
    releváns, a bekerülési költség nem."""
    try:
        check_page_action(db, employee, "/penzugyek", "view")
    except HTTPException:
        return False
    return True


def sor_orabere(db: Session, row: Timesheet, gyorsito: dict[int, float | None]) -> float | None:
    """Melyik órabérrel számol ez a sor: elsődlegesen a méréshez RÖGZÍTETT
    órabér (az az akkori, befagyasztott ár), annak híján a munkatárs mai
    órabére. A gyorsító azért kell, hogy egy anyag több tucat sorára ne
    kérdezzük le ugyanazt az órabért újra és újra."""
    if row.akkori_orabere is not None:
        return float(row.akkori_orabere)
    if row.employee_id not in gyorsito:
        gyorsito[row.employee_id] = aktualis_orabere(db, row.employee_id)
    return gyorsito[row.employee_id]


def sor_percei(row: Timesheet) -> float:
    """A soron eltöltött idő. A rögzített perc az elsődleges (a Notionból
    hozott mérésnél sokszor CSAK ez van meg), különben a két időpont
    különbsége."""
    if row.time_minutes is not None:
        return float(row.time_minutes)
    return float(row.idotartam_perc or 0)


def sor_koltsege(db: Session, row: Timesheet, gyorsito: dict[int, float | None]) -> float | None:
    """Egy munkaidő-sor költsége.

    Ha van rögzített összeg (a mérés leállításakor számolt, vagy a Notionból
    hozott), az a mérvadó. Ha nincs - és az importált soroknál jellemzően
    nincs -, akkor az IDŐBŐL és az órabérből számoljuk, mert enélkül a
    felületen csak egy gondolatjel állna, és a vágás költsége sehol nem
    jönne ki."""
    if row.koltseg is not None:
        return float(row.koltseg)
    return szamolt_koltseg(sor_percei(row), sor_orabere(db, row, gyorsito))


def anyag_osszesitok(db: Session, deliverable_ids: list[int]) -> dict[int, dict[str, float]]:
    """Anyagonként a MÉRT idő és az abból adódó költség - egyetlen lekérdezésből.

    Ez a VÁGÁS ÁRÁNAK egyetlen forrása: ugyanaz a szám, ami az anyag oldalán a
    "Munkaidő-elszámolások" tábla alján áll. A `Deliverable.koltseg` mező NEM
    használható erre: az egy régi, kézzel/importból beírt összeg, ami nem
    követi a méréseket - egy utólag rögzített vagy törölt sor után ott elavult
    szám maradna, és a projekt költsége hazudna.

    A még FUTÓ mérések kimaradnak: azoknak nincs végleges idejük. A felület a
    futó mérést másodpercenként külön mutatja (lásd TimerControls), a rögzített
    költségbe viszont csak a leállított sorok kerülnek."""
    if not deliverable_ids:
        return {}
    sorok = db.scalars(select(Timesheet).where(Timesheet.deliverable_id.in_(deliverable_ids))).all()
    return sorok_osszesitese(db, sorok)


def sorok_osszesitese(db: Session, sorok: Iterable[Timesheet]) -> dict[int, dict[str, float]]:
    """Ugyanaz, de MÁR BETÖLTÖTT munkaidő-sorokból - így a hívó eldöntheti,
    hogy kérdez-e külön (lásd anyag_osszesitok), vagy egy eager loaddal
    behozott kapcsolatból dolgozik. A projektkód-lista az utóbbit teszi:
    soronként külön lekérdezve ez több száz kör lenne."""
    gyorsito: dict[int, float | None] = {}
    eredmeny: dict[int, dict[str, float]] = {}
    for row in sorok:
        if row.deliverable_id is None:
            continue
        if row.end_date is None and row.start_date is not None:
            continue
        cel = eredmeny.setdefault(row.deliverable_id, {"percek": 0.0, "koltseg": 0.0})
        cel["percek"] += sor_percei(row)
        koltseg = sor_koltsege(db, row, gyorsito)
        if koltseg is not None:
            cel["koltseg"] += koltseg
    return eredmeny


def anyag_koltsege(osszesitok: dict[int, dict[str, float]], deliverable: Deliverable) -> float:
    """Egy anyag vágási ára a projekt költségéhez.

    Elsődlegesen a MÉRT munkaidőből (ez a valós szám, ez áll az anyag oldalán
    a "Munkaidő-elszámolások" tábla alján is). A `Deliverable.koltseg` mező
    csak akkor jön szóba, ha az anyagon EGYÁLTALÁN NINCS mérés: a régi,
    Notionból hozott anyagoknál ez az egyetlen ismert összeg, és nullát írni
    oda rosszabb hazugság lenne, mint egy régi számot.

    Amíg van mérés, a mező NEM számít - épp ez volt a hiba: a mező nem követi a
    méréseket, tehát egy utólag rögzített vagy törölt sor után elavult szám
    maradt benne."""
    sor = osszesitok.get(deliverable.id)
    if sor is not None:
        return float(sor["koltseg"])
    return float(deliverable.koltseg or 0)


def get_timer_state(db: Session, deliverable: Deliverable, current_user: Employee) -> TimerState:
    rows = db.scalars(select(Timesheet).where(Timesheet.deliverable_id == deliverable.id)).all()

    my_running_since = None
    futo: list[tuple[int, datetime, float | None]] = []
    by_employee_minutes: dict[int, float] = {}
    by_employee_cost: dict[int, float] = {}
    sor_koltsegek: dict[int, float] = {}
    orabere_gyorsito: dict[int, float | None] = {}
    for row in rows:
        if row.end_date is None and row.start_date is not None:
            # Az órabért is visszaadjuk, hogy a felület a MÉG FUTÓ mérés
            # költségét is tudja másodpercenként számolni (lásd TimerControls).
            futo.append((row.employee_id, row.start_date, sor_orabere(db, row, orabere_gyorsito)))
            if row.employee_id == current_user.id:
                my_running_since = row.start_date
            continue
        # Minden, ami NEM fut, beleszámít a bontásba - az is, aminek nincs
        # kezdő/záró időpontja, csak rögzített perce. (A Notionból hozott
        # méréseknél előfordul, hogy csak a mért idő van meg; enélkül az
        # anyagon lett volna összes idő, de nem látszott volna, KI dolgozta.)
        by_employee_minutes[row.employee_id] = by_employee_minutes.get(row.employee_id, 0) + sor_percei(row)
        koltseg = sor_koltsege(db, row, orabere_gyorsito)
        if koltseg is not None:
            by_employee_cost[row.employee_id] = by_employee_cost.get(row.employee_id, 0) + koltseg
            sor_koltsegek[row.id] = koltseg

    employee_ids = list({*by_employee_minutes.keys(), *(eid for eid, _, _ in futo)})
    names = {e.id: e.full_name for e in db.scalars(select(Employee).where(Employee.id.in_(employee_ids)))} if employee_ids else {}

    by_employee = [
        TimerEmployeeSummary(
            employee_id=eid,
            full_name=names.get(eid, "Ismeretlen"),
            total_minutes=minutes,
            total_cost=by_employee_cost.get(eid),
        )
        for eid, minutes in by_employee_minutes.items()
    ]
    total_minutes = sum(by_employee_minutes.values())
    total_cost = sum(by_employee_cost.values()) if by_employee_cost else None

    # A költséget nem csak elrejtjük a felületen: aki nem láthatja, annak a
    # válaszban sincs benne. Ez az órabérre is áll - abból ki lehetne számolni.
    lathat_koltseget = _may_see_costs(db, current_user)
    if not lathat_koltseget:
        by_employee = [s.model_copy(update={"total_cost": None}) for s in by_employee]
        total_cost = None
        sor_koltsegek = {}

    running = [
        TimerRunningEntry(
            employee_id=eid,
            full_name=names.get(eid, "Ismeretlen"),
            since=since,
            orabere=orabere if lathat_koltseget else None,
        )
        for eid, since, orabere in futo
    ]

    return TimerState(
        my_running_since=my_running_since,
        running=running,
        by_employee=by_employee,
        total_minutes=total_minutes,
        total_cost=total_cost,
        sor_koltsegek=sor_koltsegek,
    )


#: A pontozás skálája. Egy helyen áll, hogy a felület és az ellenőrzés
#: sose csússzon szét.
PONT_MIN, PONT_MAX = 1, 10


def _ellenoriz_pont(nev: str, ertek: float | None) -> None:
    if ertek is None:
        return
    if not PONT_MIN <= ertek <= PONT_MAX:
        raise ValueError(f"A(z) {nev} pontszám {PONT_MIN} és {PONT_MAX} közé eshet (kapott: {ertek}).")


def send_visszajelzes(
    db: Session,
    deliverable: Deliverable,
    current_user: Employee,
    *,
    nyersanyag_felhasznalhatosaga: float | None = None,
    technikai_helyesseg: float | None = None,
    kreativ_kepivilag: float | None = None,
    megjegyzes: str | None = None,
) -> Feedback:
    """Egy vágói visszajelzés rögzítése az űrlapról.

    Három pontszám (1-10) és egy szöveges rész. A pontszámok üresen is
    hagyhatók - van, amikor csak leírni akar valamit a vágó -, de legalább az
    egyiket kérjük, különben a visszajelzés nem mond semmit.

    A kész anyag linkjét MÁSOLJUK a rekordba (lásd models/feedback.py), és az
    anyagra is ráírjuk a mostani pontszámokat, hogy a listákban a legutóbbi
    értékelés látszódjon - a történetet viszont a Feedback sorok őrzik."""
    _ellenoriz_pont("nyersanyag felhasználhatósága", nyersanyag_felhasznalhatosaga)
    _ellenoriz_pont("technikai helyesség", technikai_helyesseg)
    _ellenoriz_pont("kreativitás és képi világ", kreativ_kepivilag)

    szoveg = (megjegyzes or "").strip() or None
    if nyersanyag_felhasznalhatosaga is None and technikai_helyesseg is None and kreativ_kepivilag is None and not szoveg:
        raise ValueError("Adj legalább egy pontszámot vagy írj megjegyzést.")

    feedback = Feedback(
        deliverable_id=deliverable.id,
        project_id=deliverable.project_id,
        visszajelzo_employee_id=current_user.id,
        technikai_helyesseg=technikai_helyesseg,
        kreativ_kepivilag=kreativ_kepivilag,
        nyersanyag_felhasznalhatosaga=nyersanyag_felhasznalhatosaga,
        visszajelzes_szoveg=szoveg,
        kesz_anyag_url=deliverable.kesz_anyag_url,
    )
    db.add(feedback)

    # Az anyagon a LEGUTÓBBI értékelés látszik (a listák ezt mutatják) - a
    # korábbi köröket a Feedback sorok őrzik.
    deliverable.technikai_helyesseg = technikai_helyesseg
    deliverable.kreativ_es_kepi_vilag = kreativ_kepivilag
    deliverable.nyersanyag_felhasznalhatosaga = nyersanyag_felhasznalhatosaga
    deliverable.egyeb_megjegyzes = szoveg

    db.commit()
    db.refresh(feedback)
    return feedback


def list_comments(db: Session, deliverable_id: int) -> list[CommentRead]:
    rows = db.scalars(
        select(DeliverableComment)
        .where(DeliverableComment.deliverable_id == deliverable_id)
        .order_by(DeliverableComment.created_at)
    ).all()
    csatolmanyok = attachments.list_for_many(db, "deliverableComment", [c.id for c in rows])
    return [
        CommentRead(
            id=c.id,
            deliverable_id=c.deliverable_id,
            employee_id=c.employee_id,
            employee_name=c.employee.full_name,
            body=c.body,
            created_at=c.created_at,
            attachments=csatolmanyok.get(c.id, []),
        )
        for c in rows
    ]


def add_comment(db: Session, deliverable_id: int, current_user: Employee, body: str) -> CommentRead:
    comment = DeliverableComment(deliverable_id=deliverable_id, employee_id=current_user.id, body=body)
    db.add(comment)
    db.commit()
    db.refresh(comment)

    deliverable = db.get(Deliverable, deliverable_id)
    title = deliverable.projekt_neve or f"Anyag #{deliverable.id}"
    already_notified: set[int] = set()

    for employee_id in notifications.extract_mentioned_employee_ids(body, db):
        notifications.create_notification(
            db,
            employee_id=employee_id,
            kind="mention",
            message=f"{current_user.full_name} megemlített egy hozzászólásban: {title}",
            link=f"{UTOMUNKA_PAGE}/{deliverable.id}",
            actor_id=current_user.id,
        )
        already_notified.add(employee_id)

    for employee_id in filter(None, [deliverable.assigned_to_employee_id, deliverable.aki_felvezette_employee_id]):
        if employee_id in already_notified:
            continue
        notifications.create_notification(
            db,
            employee_id=employee_id,
            kind="comment",
            message=f"{current_user.full_name} kommentelt: {title}",
            link=f"{UTOMUNKA_PAGE}/{deliverable.id}",
            actor_id=current_user.id,
        )
        already_notified.add(employee_id)

    db.commit()
    return CommentRead(
        id=comment.id,
        deliverable_id=comment.deliverable_id,
        employee_id=comment.employee_id,
        employee_name=current_user.full_name,
        body=comment.body,
        created_at=comment.created_at,
        attachments=[],
    )
