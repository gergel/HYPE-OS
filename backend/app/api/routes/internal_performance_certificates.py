"""Belsős TIG - havi, NEM projektenkénti teljesítésigazolás a belsős
(payroll-on lévő) munkatársakhoz: minden belsős embernek pontosan egy TIG-je
kell havonta, függetlenül attól, hány projekten dolgozott azon a hónapon -
ez a végpont-csoport ezért nem projektre, hanem (employee_id, ev, honap)
hármasra épül.

A TIG-ek VISSZAFELÉ készülnek: mindig az ELŐZŐ hónapé az, amit épp csinálunk -
júliusban a júniusi, augusztusban a júliusi. Ezért az admin oldal (lásd
frontend app/(app)/belsos-tig/page.tsx) alapból nem a folyó, hanem az azt
megelőző hónapot mutatja, és felsorolja AZ ÖSSZES belsős munkatársat - akinek
még nincs TIG-je arra a hónapra, annak létre kell hozni vagy kihagyni (ha épp
nem dolgozott).

Ebből következik, hogy a hónapot MINDIG a teljesítés dátuma határozza meg, és
mindig az azt megelőző hónapot jelenti (2026.07.20-i teljesítés = a 2026.
JÚNIUSI TIG) - ha az admin átírja a teljesítési dátumot úgy, hogy másik
hónapot jelöl, a bejegyzés átkerül abba a hónapba (lásd
_apply_teljesites_honap). A teljesítés és a fizetési határidő alapértéke a
következő hónap 20-a (lásd services/hu_datum.tig_hatarido)."""

from __future__ import annotations

import os
from datetime import date, timedelta

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user, require_page_action
from app.models.employee import Employee, EmployeeType
from app.models.employee_monthly_item import (
    TETEL_TIPUSOK,
    TIPUS_SORREND,
    EmployeeMonthlyItem,
    elojeles_osszeg,
)
from app.models.finance import Expense
from app.models.vallalkozas import VallalkozasTag
from app.models.internal_performance_certificate import (
    LEZART_ALLAPOTOK,
    InternalPerformanceCertificate,
    InternalPerformanceCertificateInvoice,
)
from app.schemas.finance import KifizetesIn
from app.schemas.internal_performance_certificate import InternalPerformanceCertificateRead
from app.services import belsos_idoszak, document_storage
from app.services.gdoc_template import gdoc_fill_export_and_store_pdf
from app.services.google_email import send_message
from app.services.hu_datum import (
    belsos_tig_honapja,
    elozo_honap,
    ev_honap_szoveg,
    honap_neve,
    tig_hatarido,
)
from app.services.hu_number_words import szam_betukkel

router = APIRouter(prefix="/belsos-tig", tags=["internal-performance-certificates"])

PAGE = "/belsos-tig"

TERMINAL_STATUSES = {"Kész", "Kiküldve", "Kihagyva"}
#: Lásd models/internal_performance_certificate.LEZART_ALLAPOTOK - az utalandó
#: lista is ebből dolgozik, ezért a modell mellett lakik.
FINALIZED_STATUSES = LEZART_ALLAPOTOK

_BELSOS_TIG_EMAIL_HTML = """\
<p>Kedves {nev},</p>
<p>
  Mellékelten küldjük a <b>{honap}</b> havi teljesítési igazolásodat.<br>
  Kérjük, ellenőrizd az adatokat, és jelezz vissza, ha bármi eltérést látsz.
</p>
<p>Köszönettel,</p>
<br><br>
<table cellpadding="0" cellspacing="0" style="font-family: Arial, sans-serif; font-size: 12px; color: #000;">
  <tr>
    <td style="vertical-align: middle; width: 150px;">
      <img src="https://raw.githubusercontent.com/gergel/ADMIN_projektkod/main/hype_logo_BG_03%20(2).png" alt="Hype logo" width="110">
    </td>
    <td style="padding-left: 20px; vertical-align: middle;">
      <p style="margin: 0; font-size: 12px; font-weight: bold;">HYPE PRODUCTIONS - ADMINISZTRÁCIÓ</p>
      <p style="margin: 0; color: #888; font-size: 12px;">Hype Productions Kft.</p>
    </td>
    <td style="padding-left: 40px; vertical-align: top; color: #888; font-size: 12px;">
      <p style="margin: 0;">Rahman Martin – cégvezető</p>
      <p style="margin: 0;">
        <a href="mailto:martin.rahman@hypestab.hu" style="color: #888; text-decoration: underline;">martin.rahman@hypestab.hu</a><br>
        +36 30 898 7600
      </p>
      <p style="margin: 0;">Barna Blanka – Back office manager</p>
      <p style="margin: 0;">
        <a href="mailto:blanka.barna@hypestab.hu" style="color: #888; text-decoration: underline;">blanka.barna@hypestab.hu</a><br>
        +36 30 758 8751
      </p>
    </td>
  </tr>
</table>
"""


def _belsos_employees(db: Session, ev: int | None = None, honap: int | None = None) -> list[Employee]:
    """A belsős munkatársak - hónap megadásakor csak azok, akik AKKOR belsősök
    voltak.

    Enélkül minden belsőstől minden hónapra TIG-et várnánk, azoktól is, akik
    még nem, vagy már nem dolgoztak nálunk - az ilyen hónapok örökre
    "hiányzóként" állnának a listán (lásd services/belsos_idoszak.py)."""
    return belsos_idoszak.belsosok(db, ev, honap)


def _find(db: Session, employee_id: int, ev: int, honap: int) -> InternalPerformanceCertificate | None:
    return (
        db.query(InternalPerformanceCertificate)
        .filter(
            InternalPerformanceCertificate.employee_id == employee_id,
            InternalPerformanceCertificate.ev == ev,
            InternalPerformanceCertificate.honap == honap,
        )
        .first()
    )


def _get_or_create(db: Session, employee: Employee, ev: int, honap: int) -> InternalPerformanceCertificate:
    existing = _find(db, employee.id, ev, honap)
    if existing is not None:
        return existing
    record = InternalPerformanceCertificate(
        employee_id=employee.id,
        ev=ev,
        honap=honap,
        allapot="Készítés alatt",
        # A megbízás tárgya alapból a munkatárs adatlapjáról jön, de innentől
        # a TIG saját másolata - a felületen szabadon átírható anélkül, hogy
        # a személy törzsadata változna.
        megbizas_targya=employee.megbizas_targya,
        plusz_afa=employee.plusz_afa,
        # A teljesítés a hónapot KÖVETŐ hónapban történik (a hónap onnan
        # számolódik vissza) - alapból annak a 20-a, ahogy a fizetési határidő
        # is: a júniusi TIG-en 07.20. áll. Mindkettő átírható.
        teljesites_datuma=tig_hatarido(ev, honap),
        fizetesi_hatarido=tig_hatarido(ev, honap),
    )
    db.add(record)
    db.flush()
    return record


class CegValasztek(BaseModel):
    """Egy felajánlható cég a havi TIG-hez."""

    vallalkozas_id: int
    nev: str
    #: Ami a cég nevére szóló TIG-re RÁKERÜL (lásd generate_and_send `fields`) -
    #: azért utazik a listával, hogy a kiküldés előtti áttekintő pontosan azt
    #: mutathassa, ami a papírra megy, ne egy másik forrásból vett közelítést.
    szekhely: str | None = None
    adoszam: str | None = None
    kezdet: date | None = None
    veg: date | None = None
    #: Erre a hónapra érvényes-e az időszaka. A lejárt/még nem kezdődött
    #: cégeket is felsoroljuk (hogy egy régi hónapot utólag is lehessen
    #: javítani), de a felület ezeket megkülönbözteti.
    ervenyes: bool = False


def _honap_hatarai(ev: int, honap: int) -> tuple[date, date]:
    elso = date(ev, honap, 1)
    utolso = date(ev + (honap == 12), 1 if honap == 12 else honap + 1, 1) - timedelta(days=1)
    return elso, utolso


def _ceg_valasztek(tagsagok: list[VallalkozasTag], ev: int, honap: int) -> list[CegValasztek]:
    """A munkatárs cégei erre a hónapra, az érvényesekkel elöl.

    Egy tagság akkor érvényes a hónapra, ha az időszaka BELELÓG a hónapba: a
    nyitott (kezdet/vég nélküli) oldal mindig belefér. Így az veszi át a
    javaslatot, aki tényleg akkor volt érvényben."""
    elso, utolso = _honap_hatarai(ev, honap)
    sorok = [
        CegValasztek(
            vallalkozas_id=t.vallalkozas_id,
            nev=t.vallalkozas.nev if t.vallalkozas else f"#{t.vallalkozas_id}",
            szekhely=t.vallalkozas.szekhely if t.vallalkozas else None,
            adoszam=t.vallalkozas.adoszam if t.vallalkozas else None,
            kezdet=t.kezdet,
            veg=t.veg,
            ervenyes=(t.kezdet is None or t.kezdet <= utolso) and (t.veg is None or t.veg >= elso),
        )
        for t in tagsagok
        if t.vallalkozas is None or t.vallalkozas.aktiv
    ]
    sorok.sort(key=lambda x: (not x.ervenyes, x.nev))
    return sorok


def _tagsagok(db: Session, employee_ids: list[int]) -> dict[int, list[VallalkozasTag]]:
    if not employee_ids:
        return {}
    sorok = (
        db.query(VallalkozasTag)
        .options(selectinload(VallalkozasTag.vallalkozas))
        .filter(VallalkozasTag.employee_id.in_(employee_ids))
        .all()
    )
    eredmeny: dict[int, list[VallalkozasTag]] = {}
    for t in sorok:
        eredmeny.setdefault(t.employee_id, []).append(t)
    return eredmeny


def _validate_belsos_employee(db: Session, employee_id: int) -> Employee:
    employee = db.get(Employee, employee_id)
    if employee is None or employee.tipus != EmployeeType.BELSOS:
        raise HTTPException(status_code=400, detail="Ez a végpont csak belsős munkatársakhoz használható.")
    return employee


class MonthEmployeeInfo(BaseModel):
    id: int
    full_name: str
    email: str | None
    # A munkatárs adatlapjáról jövő előtöltés: a TIG űrlap ezekkel indul, ha
    # még nincs bejegyzés arra a hónapra (olyankor `record` üres, tehát nem
    # lenne miből kitölteni).
    megbizas_targya: str | None
    plusz_afa: bool | None
    #: A SAJÁT nevére szóló TIG-re kerülő adatok (amikor nem cégről számláz) -
    #: a kiküldés előtti áttekintő ezekkel mutatja, mi megy ki a papírra.
    szekhely: str | None = None
    adoszam: str | None = None
    #: Kell-e tőle havi TIG. Bejelentett alkalmazottnál NEM: nála a havi
    #: teendő csak a fizetés beírása (lásd models/employee.py
    #: BelsosJogviszony) - a felület ettől függően más vezérlőket mutat.
    kell_tig: bool = True
    #: "megbizas" | "alkalmazott"
    jogviszony: str = "megbizas"
    record: InternalPerformanceCertificateRead | None
    #: A munkatárs cégei erre a hónapra - a TIG készítésekor ebből lehet
    #: választani, melyikről számlázza (lásd _ceg_valasztek).
    cegek: list[CegValasztek] = []
    #: A hónapra érvényes cég azonosítója - ezzel indul az űrlap, ha még nincs
    #: kézzel választva. Több érvényes cégnél nincs javaslat: olyankor
    #: kifejezetten dönteni kell.
    javasolt_vallalkozas_id: int | None = None
    #: A hónap tételei (alapbér + extrák), amikből a TIG összege összeáll -
    #: lásd models/employee_monthly_item.py. Így a TIG készítője látja, MIÉRT
    #: annyi az összeg, nem csak azt, hogy mennyi.
    tetelek: list["HaviTetelRead"] = []


@router.get("", response_model=list[MonthEmployeeInfo])
def list_month(
    ev: int | None = None,
    honap: int | None = None,
    db: Session = Depends(get_db),
    _user: Employee = Depends(get_current_user),
):
    """Az adott hónap összes belsős munkatársa + a hozzájuk tartozó
    TIG-bejegyzés (ha van) - a frontend ebből dönti el, kinél van még teendő
    (nincs bejegyzés / Készítés alatt), és kinél van már lezárva (Kész /
    Kihagyva).

    Hónap nélkül az ELŐZŐ hónapot adjuk: azt csináljuk éppen (júliusban a
    júniusit), a folyó hónap TIG-je csak a következő hónapban lesz esedékes."""
    alap_ev, alap_honap = elozo_honap(date.today())
    ev = ev or alap_ev
    honap = honap or alap_honap
    employees = _belsos_employees(db, ev, honap)
    if not employees:
        return []
    records = (
        db.query(InternalPerformanceCertificate)
        .filter(
            InternalPerformanceCertificate.ev == ev,
            InternalPerformanceCertificate.honap == honap,
            InternalPerformanceCertificate.employee_id.in_([e.id for e in employees]),
        )
        .all()
    )
    lookup = {r.employee_id: r for r in records}

    tetelek = (
        db.query(EmployeeMonthlyItem)
        .filter(
            EmployeeMonthlyItem.ev == ev,
            EmployeeMonthlyItem.honap == honap,
            EmployeeMonthlyItem.employee_id.in_([e.id for e in employees]),
        )
        .all()
    )
    tetelek = sorted(tetelek, key=lambda t: (TIPUS_SORREND.get(t.tipus, 9), t.id))
    tetel_lookup: dict[int, list[HaviTetelRead]] = {}
    for tetel in tetelek:
        tetel_lookup.setdefault(tetel.employee_id, []).append(_tetel_kimenet(tetel))

    tagsag_lookup = _tagsagok(db, [e.id for e in employees])

    def _cegek(employee_id: int) -> list[CegValasztek]:
        return _ceg_valasztek(tagsag_lookup.get(employee_id, []), ev, honap)

    def _javaslat(cegek: list[CegValasztek]) -> int | None:
        ervenyesek = [c for c in cegek if c.ervenyes]
        return ervenyesek[0].vallalkozas_id if len(ervenyesek) == 1 else None

    return [
        MonthEmployeeInfo(
            id=e.id,
            full_name=e.full_name,
            email=e.email,
            megbizas_targya=e.megbizas_targya,
            plusz_afa=e.plusz_afa,
            szekhely=e.vallakozas_szekhely,
            adoszam=e.vallalkozas_adoszama,
            kell_tig=belsos_idoszak.kell_havi_tig(e),
            jogviszony=e.belsos_jogviszony.value,
            record=InternalPerformanceCertificateRead.model_validate(lookup[e.id]) if e.id in lookup else None,
            cegek=_cegek(e.id),
            javasolt_vallalkozas_id=_javaslat(_cegek(e.id)),
            tetelek=tetel_lookup.get(e.id, []),
        )
        for e in employees
    ]


class HaviTeendo(BaseModel):
    """Egy konkrét ember konkrét hiányossága egy hónapban - ebből derül ki,
    KINEK MIT kell még elkészítenie."""

    employee_id: int
    full_name: str
    allapot: str | None
    #: Emberi mondat, hogy mi hiányzik (pl. "Nincs elkezdve", "Számla hiányzik").
    hianyzik: str


class HaviOsszesito(BaseModel):
    """Egy hónap "mappája": kész van-e, és ha nem, mi hiányzik belőle."""

    ev: int
    honap: int
    honap_szoveg: str
    #: A hónap TIG-jeit a KÖVETKEZŐ hónap első napján kell teljesíteni - ez a
    #: határidő (ugyanaz a dátum, amit a TIG teljesítési dátuma alapból kap).
    hatarido: date
    #: Lejárt-e a határidő úgy, hogy még maradt teendő.
    keses: bool
    #: nincs_elkezdve | folyamatban | tig_kesz | lezarva
    allapot: str
    osszes: int
    kesz: int
    kihagyva: int
    hianyzo: int
    brutto_osszesen: float | None
    teendok: list[HaviTeendo]


def _honap_teendoje(record: InternalPerformanceCertificate | None, *, kell_tig: bool = True) -> str | None:
    """Mi hiányzik még ehhez az emberhez ebben a hónapban? None = kész.

    BEJELENTETT ALKALMAZOTTNÁL (kell_tig=False) a folyamat lényegesen rövidebb:
    a bérét bérszámfejtés fizeti, tehát nincs TIG, nincs számla és nincs
    "kifizetve" lépés - egyedül az számít, be van-e írva a hónapra a fizetése
    (lásd services/belsos_idoszak.kell_havi_tig)."""
    if record is not None and record.allapot == "Kihagyva":
        return None
    if not kell_tig:
        if record is None or record.netto_osszeg is None or float(record.netto_osszeg) == 0:
            return "Fizetés nincs beírva"
        return None
    if record is None:
        return "Nincs elkezdve"
    if record.allapot not in FINALIZED_STATUSES:
        if record.netto_osszeg is None:
            return "Készítés alatt – összeg nincs megadva"
        return "Készítés alatt – még nincs kiküldve"
    if not record.invoices:
        return "Számla hiányzik"
    if not record.szamla_kifizetve:
        return "Kifizetés hiányzik"
    return None


class IdoszakHianyzik(BaseModel):
    """Egy belsős, akiről nem tudjuk, mettől meddig volt az."""

    employee_id: int
    full_name: str
    #: Mettől soroljuk be a nyomai alapján (legkorábbi TIG-je/havi tétele).
    #: Üres, ha semmilyen nyoma nincs - ő sehol nem jelenik meg a havi
    #: listákon, amíg az időszaka nincs megadva.
    nyom_kezdet: date | None = None


@router.get("/idoszak-hianyzik", response_model=list[IdoszakHianyzik])
def idoszak_hianyzik(db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
    """Azok a belsősök, akiknek nincs megadva a belsős időszaka.

    Miért kell külön kiírni? Mert a havi listák időszak nélkül nem
    találgatnak: aki sehol nem szerepel, az nem is jelenik meg egyik hónapnál
    sem (lásd services/belsos_idoszak.py). Ez így pontos, de csak akkor
    biztonságos, ha a hiány LÁTSZIK - különben egy elfelejtett időszak miatt
    csendben kimaradna valakinek a havi TIG-je."""
    emberek = [e for e in belsos_idoszak.belsosok(db) if not belsos_idoszak.van_idoszak_adat(e)]
    nyomok = belsos_idoszak.nyom_kezdetek(db, [e.id for e in emberek])
    return [
        IdoszakHianyzik(employee_id=e.id, full_name=e.full_name, nyom_kezdet=nyomok.get(e.id))
        for e in emberek
    ]


@router.get("/attekintes", response_model=list[HaviOsszesito])
def havi_attekintes(
    honapok: int = 12,
    db: Session = Depends(get_db),
    _user: Employee = Depends(get_current_user),
):
    """HAVI ÁTTEKINTÉS ("mappázás"): hónaponként külön, hogy melyik hónap van
    kész, és ahol nincs, ott pontosan kinek mi hiányzik - anélkül, hogy a
    hónapok összefolynának.

    A hónap akkor "lezárva", ha minden belsős munkatársnak vagy kiküldött
    TIG-je van feltöltött ÉS kifizetett számlával, vagy ki lett hagyva. A
    köztes állapot a "tig_kesz": a TIG-ek elkészültek, de a számla/kifizetés
    még hátravan.

    Azok a hónapok jelennek meg, amikre már van bejegyzés, plusz az utolsó
    `honapok` hónap - hogy a még el sem kezdett hónapok is látszódjanak,
    ne csak azok, amikhez valaki már hozzányúlt."""
    today = date.today()
    # Hónaponként szűrünk (ki volt AKKOR belsős), ezért itt a teljes lista kell.
    employees = _belsos_employees(db)

    records = db.query(InternalPerformanceCertificate).all()
    honap_szerint: dict[tuple[int, int], list[InternalPerformanceCertificate]] = {}
    for r in records:
        honap_szerint.setdefault((r.ev, r.honap), []).append(r)

    # Az utolsó N hónap (a folyó hónappal együtt) + minden olyan hónap, amiben
    # már van bejegyzés.
    # A folyó hónap TIG-je még nem esedékes (azt a következő hónapban
    # készítjük), ezért a visszafelé számolás az ELŐZŐ hónappal indul.
    honap_kulcsok: set[tuple[int, int]] = set(honap_szerint.keys())
    ev, honap = elozo_honap(today)
    for _ in range(max(honapok, 1)):
        honap_kulcsok.add((ev, honap))
        ev, honap = elozo_honap(date(ev, honap, 1))

    # A legelső bejegyzésnél RÉGEBBI hónapokat elhagyjuk: azok a rendszer
    # használatba vétele előttiek, örökre "hiányosnak" látszanának, és csak
    # elfednék az igazi teendőket. (Ha még egyetlen bejegyzés sincs, marad az
    # utolsó N hónap - egy friss rendszeren pont azokkal kell kezdeni.)
    if honap_szerint:
        legkorabbi = min(honap_szerint)
        honap_kulcsok = {k for k in honap_kulcsok if k >= legkorabbi}

    # Akinek nincs felvitt belsős időszaka, annál a NYOMAI mondják meg,
    # mettől számít belsősnek (lásd services/belsos_idoszak.py) - enélkül
    # minden hónapban ott állna a neve.
    nyomok = belsos_idoszak.nyom_kezdetek(
        db, [e.id for e in employees if not belsos_idoszak.van_idoszak_adat(e)]
    )

    eredmeny: list[HaviOsszesito] = []
    for kulcs in sorted(honap_kulcsok, reverse=True):
        ev, honap = kulcs
        sorok = {r.employee_id: r for r in honap_szerint.get(kulcs, [])}
        # Csak azok, akik EBBEN a hónapban belsősök voltak (lásd
        # services/belsos_idoszak.py) - aki akkor még nem, vagy már nem
        # dolgozott nálunk, attól nincs mit várni.
        #
        # A MÁR NEM belsősök is beleszámítanak, ha erre a hónapra van
        # bejegyzésük - különben a munkájuk (és az összegük) eltűnne a hónap
        # összesítéséből. Ez viszont CSAK belsősökre igaz: egy sosem-belsős
        # emberhez tartozó (jellemzően importból maradt) bejegyzés nem
        # csinálhat teendőt. Enélkül az áttekintés olyan nevet is felsorolt,
        # ami a hónap megnyitásakor nincs is a listán - lásd _belsos_employees.
        emberek = [e for e in employees if belsos_idoszak.belsos_volt(e, ev, honap, nyomok.get(e.id))]
        ismert = {e.id for e in emberek}
        for employee_id in sorok:
            if employee_id not in ismert:
                korabbi = db.get(Employee, employee_id)
                if korabbi is not None and korabbi.tipus == EmployeeType.BELSOS:
                    emberek.append(korabbi)

        teendok: list[HaviTeendo] = []
        kesz = kihagyva = 0
        brutto = 0.0
        van_brutto = False
        for e in emberek:
            record = sorok.get(e.id)
            if record is not None:
                # A bruttó a séma számított mezője (nettó + ÁFA, ha kell) -
                # szándékosan onnan vesszük, hogy a képlet egy helyen legyen.
                osszeg = InternalPerformanceCertificateRead.model_validate(record).brutto_osszeg
                if osszeg is not None:
                    brutto += float(osszeg)
                    van_brutto = True
            hianyzik = _honap_teendoje(record, kell_tig=belsos_idoszak.kell_havi_tig(e))
            if hianyzik is None:
                if record is not None and record.allapot == "Kihagyva":
                    kihagyva += 1
                else:
                    kesz += 1
                continue
            teendok.append(
                HaviTeendo(
                    employee_id=e.id,
                    full_name=e.full_name,
                    allapot=record.allapot if record is not None else None,
                    hianyzik=hianyzik,
                )
            )

        hatarido = tig_hatarido(ev, honap)
        van_bejegyzes = bool(sorok)
        if not teendok:
            allapot = "lezarva"
        elif not van_bejegyzes:
            allapot = "nincs_elkezdve"
        elif all(t.hianyzik in ("Számla hiányzik", "Kifizetés hiányzik") for t in teendok):
            allapot = "tig_kesz"
        else:
            allapot = "folyamatban"

        eredmeny.append(
            HaviOsszesito(
                ev=ev,
                honap=honap,
                honap_szoveg=ev_honap_szoveg(ev, honap),
                hatarido=hatarido,
                keses=bool(teendok) and today > hatarido,
                allapot=allapot,
                osszes=len(emberek),
                kesz=kesz,
                kihagyva=kihagyva,
                hianyzo=len(teendok),
                brutto_osszesen=brutto if van_brutto else None,
                teendok=sorted(teendok, key=lambda t: t.full_name),
            )
        )
    return eredmeny


@router.get("/employee/{employee_id}", response_model=list[InternalPerformanceCertificateRead])
def list_for_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(get_current_user),
):
    """Egy munkatárs ÖSSZES belsős TIG-je, a legfrissebb hónappal elöl - ezt
    mutatja a személy adatlapján a "Belsős TIG-ek" szekció (havi bontásban az
    összeg, az állapot és a kiküldött igazolás linkje)."""
    return (
        db.query(InternalPerformanceCertificate)
        .filter(InternalPerformanceCertificate.employee_id == employee_id)
        .order_by(InternalPerformanceCertificate.ev.desc(), InternalPerformanceCertificate.honap.desc())
        .all()
    )


class TigDraftIn(BaseModel):
    #: Melyik saját cégéről számlázza ezt a hónapot. A None azt jelenti: "nem
    #: küldted meg a mezőt" (a régi hívások így működnek tovább), a -1 pedig
    #: azt, hogy "állítsd vissza a saját nevére" - egy sima None-nal nem lehet
    #: kitörölni egy már beállított céget.
    vallalkozas_id: int | None = None
    netto_osszeg: float | None = None
    plusz_afa: bool | None = None
    megjegyzes: str | None = None
    megbizas_targya: str | None = None
    teljesites_datuma: date | None = None
    keltezes: date | None = None
    #: A számla útja: meddig kell fizetni, és mikor utaltuk el. (A Notionból
    #: áthozott régi TIG-eknél ez a két dátum már megvan - lásd
    #: notion_import/importers_belsos.py.)
    fizetesi_hatarido: date | None = None
    utalas_datuma: date | None = None


_DRAFT_FIELDS = (
    "netto_osszeg",
    "plusz_afa",
    "megjegyzes",
    "megbizas_targya",
    "teljesites_datuma",
    "keltezes",
    "fizetesi_hatarido",
    "utalas_datuma",
)


def _apply_draft_fields(record: InternalPerformanceCertificate, payload: TigDraftIn) -> None:
    for field in _DRAFT_FIELDS:
        value = getattr(payload, field)
        if value is not None:
            setattr(record, field, value)
    if payload.vallalkozas_id is not None:
        # A -1 a "vissza a saját nevére" jelzés, lásd TigDraftIn.
        record.vallalkozas_id = None if payload.vallalkozas_id < 0 else payload.vallalkozas_id


def _apply_teljesites_honap(db: Session, record: InternalPerformanceCertificate) -> None:
    """A teljesítés dátuma dönti el, melyik hónap TIG-je ez - mindig az azt
    MEGELŐZŐ hónap. Ha az admin olyan dátumot ad meg, ami másik hónapra
    mutat, a bejegyzés átkerül oda (a havi nézetben onnantól ott látszik).

    Ha a cél-hónapban már van TIG ugyanannak az embernek, nem írjuk felül -
    az adatbázis egyediség-megkötése (uq_internal_tig_employee_month) úgyis
    megakadályozná, csak nyers 500-zal; itt beszédes hibát adunk helyette."""
    if record.teljesites_datuma is None:
        return
    ev, honap = elozo_honap(record.teljesites_datuma)
    if (ev, honap) == (record.ev, record.honap):
        return
    utkozes = _find(db, record.employee_id, ev, honap)
    if utkozes is not None and utkozes.id != record.id:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Ehhez a teljesítési dátumhoz a(z) {ev_honap_szoveg(ev, honap)} hónap tartozna, "
                "de ott már van Belsős TIG ehhez a munkatárshoz."
            ),
        )
    record.ev = ev
    record.honap = honap


@router.post("/{employee_id}/{ev}/{honap}/save", response_model=InternalPerformanceCertificateRead)
def save_draft(
    employee_id: int,
    ev: int,
    honap: int,
    payload: TigDraftIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "create")),
):
    employee = _validate_belsos_employee(db, employee_id)
    record = _get_or_create(db, employee, ev, honap)
    if record.allapot in TERMINAL_STATUSES:
        raise HTTPException(status_code=400, detail="Ehhez a hónaphoz már véglegesített Belsős TIG tartozik.")
    _apply_draft_fields(record, payload)
    _apply_teljesites_honap(db, record)
    db.commit()
    db.refresh(record)
    return InternalPerformanceCertificateRead.model_validate(record)


@router.post("/{employee_id}/{ev}/{honap}/generalas-es-kuldes", response_model=InternalPerformanceCertificateRead)
def generate_and_send(
    employee_id: int,
    ev: int,
    honap: int,
    payload: TigDraftIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "create")),
):
    """A csatolt belsős-TIG program (belsos-TIG-main) menete, egy az egyben:
    a Google Docs sablon másolása, a {{placeholder}}-ek cseréje, PDF export, a
    PDF feltöltése a Drive célmappába, az ideiglenes Doc törlése, végül az
    email a munkatársnak - a PDF csatolmánnyal. A Drive-ra feltöltött PDF
    linkje kerül a rekordba (file_url), tehát a rendszerben tárolt hivatkozás
    a KÉSZ igazolásra mutat, nem egy szerkeszthető dokumentumra.

    Sablon nélkül nem küldünk: egy PDF nélküli TIG-email nem ér semmit, ezért
    inkább beszédes hibát adunk a hiányzó beállítás nevével."""
    employee = _validate_belsos_employee(db, employee_id)
    record = _get_or_create(db, employee, ev, honap)
    if record.allapot in TERMINAL_STATUSES:
        raise HTTPException(status_code=400, detail="Ehhez a hónaphoz már véglegesített Belsős TIG tartozik.")
    _apply_draft_fields(record, payload)
    _apply_teljesites_honap(db, record)

    if not record.netto_osszeg or record.netto_osszeg <= 0:
        raise HTTPException(status_code=400, detail="Add meg a nettó összeget.")
    if not employee.email:
        raise HTTPException(status_code=400, detail=f"{employee.full_name} nem kapott email címet, így nem lehet kiküldeni a TIG-et.")
    if not settings.belsos_tig_template_id:
        db.commit()
        raise HTTPException(
            status_code=503,
            detail=(
                "Nincs beállítva a Belsős TIG dokumentum-sablon, így a PDF nem generálható. "
                "Állítsd be a GDOC_BELSOS_TIG_TEMPLATE_ID (vagy GOOGLE_DRIVE_TEMPLATE_ID) "
                "környezeti változót a backendhez."
            ),
        )

    keltezes = record.keltezes or date.today()
    record.keltezes = keltezes
    # A dokumentum és az email tárgya is a DÁTUMOKBÓL számolt hónapot viseli
    # (lásd hu_datum.belsos_tig_honapja): a 07.20-i teljesítésű a JÚNIUSI.
    honap_szoveg = ev_honap_szoveg(
        *belsos_tig_honapja(
            record.ev, record.honap, record.teljesites_datuma, record.fizetesi_hatarido, record.utalas_datuma
        )
    )
    # Fájlnév és tárgy az eredeti program formátumában ("2026. május_Név_TIG").
    base_name = f"{honap_szoveg}_{(record.vallalkozas.nev if record.vallalkozas else employee.full_name)}_TIG"

    # Ha a hónapot valamelyik SAJÁT CÉGÉRŐL számlázza, a papír a cég nevére
    # szól (név, székhely, adószám) - a levél viszont továbbra is a
    # munkatársnak megy, mert a cég az övé, ő intézi.
    ceg = record.vallalkozas
    fields = {
        "nev": ceg.nev if ceg else employee.full_name,
        "hely": (ceg.szekhely if ceg else employee.vallakozas_szekhely) or "",
        "adoszam": (ceg.adoszam if ceg else employee.vallalkozas_adoszama) or "",
        "targy": record.megbizas_targya or "",
        # Az eredeti sablonban a {{tido}} a HÓNAP szövege (nem a teljesítés
        # napja) - a teljesítés dátuma csak a hónap kiszámolására szolgál.
        "tido": honap_szoveg,
        "honap": honap_szoveg,
        # Ezres elválasztó ponttal, ahogy az eredeti program írja: "120.000".
        "netto": f"{record.netto_osszeg:,.0f}".replace(",", "."),
        "kelt": keltezes.strftime("%Y.%m.%d."),
        "afa": "+ ÁFA" if record.plusz_afa else "",
        "nettoki": szam_betukkel(record.netto_osszeg),
    }

    try:
        pdf_bytes, pdf_link = gdoc_fill_export_and_store_pdf(
            template_file_id=settings.belsos_tig_template_id,
            base_name=base_name,
            fields=fields,
            output_folder_id=settings.belsos_tig_folder_id or None,
        )
        subject = f"{employee.full_name}_{honap_szoveg} - hónap_TIG"
        html = _BELSOS_TIG_EMAIL_HTML.format(nev=employee.full_name, honap=honap_szoveg)
        send_message([employee.email], subject, html, pdf_bytes=pdf_bytes, pdf_filename=f"{base_name}.pdf")
    except RuntimeError as exc:
        # A kitöltött adatokat akkor is mentsük el, ha a küldés elhasal (pl.
        # hiányzó Google hitelesítő adat) - ne vesszen el az eddigi munka.
        db.commit()
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    record.allapot = "Kiküldve"
    record.file_url = pdf_link
    db.commit()
    db.refresh(record)
    return InternalPerformanceCertificateRead.model_validate(record)


@router.post("/{employee_id}/{ev}/{honap}/skip", response_model=InternalPerformanceCertificateRead)
def skip(
    employee_id: int,
    ev: int,
    honap: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    employee = _validate_belsos_employee(db, employee_id)
    record = _get_or_create(db, employee, ev, honap)
    if record.allapot in TERMINAL_STATUSES:
        raise HTTPException(status_code=400, detail="Ehhez a hónaphoz már véglegesített Belsős TIG tartozik.")
    record.allapot = "Kihagyva"
    db.commit()
    db.refresh(record)
    return InternalPerformanceCertificateRead.model_validate(record)


class AllapotIn(BaseModel):
    allapot: str


ALLOWED_STATUSES = ["Készítés alatt", "Kiküldve", "Kihagyva"]


@router.post("/{employee_id}/{ev}/{honap}/allapot", response_model=InternalPerformanceCertificateRead)
def set_allapot(
    employee_id: int,
    ev: int,
    honap: int,
    payload: AllapotIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """A TIG állapotának KÉZI átállítása. Aki az oldalon szerkeszthet, itt is
    javíthat: pl. visszavehet egy tévesen kiküldöttre állított TIG-et, vagy
    kiküldöttnek jelölhet egyet, amit a rendszeren kívül küldtek el. A
    generálás/küldés folyamat változatlan - ez csak az állapot javítása."""
    if payload.allapot not in ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail=f"Ismeretlen állapot. Választható: {', '.join(ALLOWED_STATUSES)}")
    employee = _validate_belsos_employee(db, employee_id)
    record = _get_or_create(db, employee, ev, honap)
    record.allapot = payload.allapot
    db.commit()
    db.refresh(record)
    return InternalPerformanceCertificateRead.model_validate(record)


def _honap_rekordja(db: Session, employee_id: int, ev: int, honap: int) -> InternalPerformanceCertificate:
    """A hónap TIG-je, ha kell, létrehozva.

    Szándékosan NEM követeli meg, hogy a TIG már ki legyen küldve: a papírok
    (számla, aláírt TIG) sokszor visszamenőleg kerülnek elő - régi hónapokhoz,
    amikhez a TIG nem itt készült (pl. Notionból hozott évek). Ha ilyenkor a
    feltöltés elutasítaná a fájlt, a dokumentumnak nem lenne hova kerülnie."""
    employee = _validate_belsos_employee(db, employee_id)
    return _get_or_create(db, employee, ev, honap)


def _get_finalized_or_404(db: Session, employee_id: int, ev: int, honap: int) -> InternalPerformanceCertificate:
    record = _find(db, employee_id, ev, honap)
    if record is None:
        raise HTTPException(status_code=404, detail="Ehhez a hónaphoz nem tartozik Belsős TIG bejegyzés.")
    if record.allapot not in FINALIZED_STATUSES:
        raise HTTPException(
            status_code=400,
            detail="Kifizetettnek csak kiküldött (véglegesített) Belsős TIG jelölhető.",
        )
    return record


@router.post("/{employee_id}/{ev}/{honap}/szamla", response_model=InternalPerformanceCertificateRead)
async def upload_szamla(
    employee_id: int,
    ev: int,
    honap: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """Egy Belsős TIG-hez tetszőleges számú számla tölthető fel - minden
    hívás egy ÚJ számla-sort hoz létre (nem írja felül az előzőt), lásd
    InternalPerformanceCertificateInvoice modell-kommentje."""
    record = _honap_rekordja(db, employee_id, ev, honap)
    filename = file.filename or "szamla"
    content_type = file.content_type or "application/octet-stream"
    invoice = InternalPerformanceCertificateInvoice(
        certificate_id=record.id, filename=filename, content_type=content_type, storage_key="", url=""
    )
    db.add(invoice)
    db.flush()
    ext = os.path.splitext(filename)[1]
    key = f"belsos-tig-szamla/{employee_id}/{ev}-{honap:02d}-{invoice.id}{ext}"
    data = await file.read()
    url = document_storage.upload_bytes(data, key, content_type)
    invoice.storage_key = key
    invoice.url = url
    db.commit()
    db.refresh(record)
    return InternalPerformanceCertificateRead.model_validate(record)


@router.delete("/{employee_id}/{ev}/{honap}/szamla/{invoice_id}", response_model=InternalPerformanceCertificateRead)
def delete_szamla(
    employee_id: int,
    ev: int,
    honap: int,
    invoice_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "delete")),
):
    record = _find(db, employee_id, ev, honap)
    if record is None:
        raise HTTPException(status_code=404, detail="Ehhez a hónaphoz nem tartozik Belsős TIG bejegyzés.")
    invoice = db.get(InternalPerformanceCertificateInvoice, invoice_id)
    if invoice is None or invoice.certificate_id != record.id:
        raise HTTPException(status_code=404, detail="A számla nem található.")
    # Tárhely-kulcs nélküli (régi, importált) sor is törölhető legyen: enélkül
    # a Törlés gomb pont azoknál a soroknál nem működne, amiknél a fájl amúgy
    # sincs a mi tárhelyünkön.
    if invoice.storage_key:
        document_storage.delete_object(invoice.storage_key)
    db.delete(invoice)
    db.commit()
    db.refresh(record)
    return InternalPerformanceCertificateRead.model_validate(record)


@router.post("/{employee_id}/{ev}/{honap}/tig-fajl", response_model=InternalPerformanceCertificateRead)
async def upload_tig_fajl(
    employee_id: int,
    ev: int,
    honap: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """A hónap TIG dokumentumának feltöltése - egyben a KIKÜLDÉS KIHAGYÁSA.

    A rendszerben készülő TIG-et a generálás teszi be (az a Drive-on marad),
    de van, amikor a papír nem itt készül: régi, Notionból hozott hónapok
    igazolása, vagy egy máshol megírt/aláírva visszakapott TIG. Ilyenkor
    nincs mit generálni és nincs kinek kiküldeni, csak rögzíteni: a fájl az
    R2-re kerül, és a hónap `file_url`-je erre mutat.

    Megbízásos belsősnél a feltöltés az ÁLLAPOTOT is átállítja "Kiküldve"-re
    (ha még nem volt lezárva): a hónap papírja megvan, tehát ugyanoda jut,
    mint a generálás és kiküldés útján - innentől számla is tölthető hozzá.
    Bejelentett alkalmazottnál az állapotot NEM nyúljuk: nála nincs kiküldés,
    amit ki lehetne hagyni (a bérét bérszámfejtés fizeti), a feltöltött papír
    a fizetési jegyzék - a "Kiküldve" ott csak lezárná a hónapot, és nem
    lehetne javítani a beírt fizetést.

    Egy hónapnak EGY TIG dokumentuma van (ellentétben a számlákkal, amikből
    több is lehet): egy újabb feltöltés lecseréli az előzőt, és ha az a mi
    tárhelyünkön volt, azt az objektumot el is dobjuk."""
    record = _honap_rekordja(db, employee_id, ev, honap)
    employee = _validate_belsos_employee(db, employee_id)
    filename = file.filename or "tig"
    content_type = file.content_type or "application/octet-stream"
    data = await file.read()

    regi_kulcs = record.file_storage_key
    kulcs = f"belsos-tig-dokumentum/{employee_id}/{ev}-{honap:02d}-{record.id}{os.path.splitext(filename)[1]}"
    record.file_url = document_storage.upload_bytes(data, kulcs, content_type)
    record.file_storage_key = kulcs
    if belsos_idoszak.kell_havi_tig(employee) and record.allapot not in TERMINAL_STATUSES:
        record.allapot = "Kiküldve"
    db.commit()
    # A cserélt fájl törlése CSAK a mentés után, és csak ha tényleg másik
    # objektum volt - így egy elhasalt feltöltésnél nem marad se régi, se új.
    if regi_kulcs and regi_kulcs != kulcs:
        document_storage.delete_object(regi_kulcs)
    db.refresh(record)
    return InternalPerformanceCertificateRead.model_validate(record)


@router.delete("/{employee_id}/{ev}/{honap}/tig-fajl", response_model=InternalPerformanceCertificateRead)
def delete_tig_fajl(
    employee_id: int,
    ev: int,
    honap: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "delete")),
):
    """A hónaphoz tartozó TIG dokumentum hivatkozásának törlése.

    Ha a fájl a mi tárhelyünkön van, az objektumot is töröljük. A generált,
    Drive-on lévő PDF-nél csak a hivatkozás tűnik el: a Drive-ról nem a mi
    dolgunk törölni, és a dokumentum ott a helyén marad."""
    record = _find(db, employee_id, ev, honap)
    if record is None:
        raise HTTPException(status_code=404, detail="Ehhez a hónaphoz nem tartozik Belsős TIG bejegyzés.")
    if not record.file_url:
        raise HTTPException(status_code=404, detail="Ehhez a hónaphoz nincs TIG dokumentum.")
    kulcs = record.file_storage_key
    record.file_url = None
    record.file_storage_key = None
    db.commit()
    if kulcs:
        document_storage.delete_object(kulcs)
    db.refresh(record)
    return InternalPerformanceCertificateRead.model_validate(record)


@router.post("/{employee_id}/{ev}/{honap}/szamla-kifizetve", response_model=InternalPerformanceCertificateRead)
def mark_szamla_kifizetve(
    employee_id: int,
    ev: int,
    honap: int,
    payload: KifizetesIn | None = None,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    """A hónap számlájának kifizetettként jelölése - alapból Kiadás sort is
    hoz létre a Pénzügyben.

    `kiadasba_kerul=false` esetén CSAK a papír állapotát jelöljük: a pénz
    tényleg elment, de a költség máshol van elszámolva, és egy itteni Kiadás
    sor megkétszerezné a Pénzügy összesítőit (lásd
    schemas/finance.KifizetesIn)."""
    record = _get_finalized_or_404(db, employee_id, ev, honap)
    if not record.invoices:
        raise HTTPException(status_code=400, detail="Előbb töltsd fel a számlát.")

    if payload is not None and not payload.kiadasba_kerul:
        record.szamla_kifizetve = True
        db.commit()
        db.refresh(record)
        return InternalPerformanceCertificateRead.model_validate(record)

    # float(): a Numeric oszlop az adatbázisból Decimal-ként jön vissza, és a
    # Decimal * float TypeError-t dob (lásd performance_certificates.py).
    brutto = (
        round(float(record.netto_osszeg) * 1.27, 2)
        if (record.plusz_afa and record.netto_osszeg)
        else record.netto_osszeg
    )

    expense = db.get(Expense, record.expense_id) if record.expense_id is not None else None
    if expense is None:
        expense = Expense(
            # A hónap a TIG dátumaiból (lásd hu_datum.belsos_tig_honapja): a
            # 07.20-i határidejű a JÚNIUSI elszámolásé.
            megnevezes=(
                f"Belsős TIG - {record.employee.full_name} - "
                f"{ev_honap_szoveg(*belsos_tig_honapja(record.ev, record.honap, record.teljesites_datuma, record.fizetesi_hatarido, record.utalas_datuma))}"
            ),
            employee_id=record.employee_id,
            tipus="belsos",
            netto=record.netto_osszeg,
            brutto=brutto,
            hozzaadas_a_kiadasokhoz=True,
        )
        db.add(expense)
        db.flush()
        record.expense_id = expense.id
    else:
        expense.netto = record.netto_osszeg
        expense.brutto = brutto

    expense.kesz = True
    expense.fizetes_datuma = date.today()
    record.szamla_kifizetve = True
    db.commit()
    db.refresh(record)
    return InternalPerformanceCertificateRead.model_validate(record)


# ─────────────────────────────────────────────────────────────────────────────
# Havi tételek: az alapbér és a hozzáadódó extrák
#
# Miért nem elég a TIG egyetlen "nettó összeg" mezője: az összeg hónap közben,
# darabonként áll össze (alapbér + túlóra + benzin + étkezés…), gyakran más
# ember viszi fel, mint aki majd a TIG-et elkészíti. Ha csak egy szám lenne, a
# TIG készítőjének kellene fejben összeadnia - és nem is látná, mi miből jött.
# Ezért a tételek a forrás, a TIG összege pedig belőlük SZÁMOLÓDIK.
# ─────────────────────────────────────────────────────────────────────────────


class HaviTetelIn(BaseModel):
    tipus: str = "extra"
    megnevezes: str
    osszeg: float = 0
    project_code_id: int | None = None
    #: A tétel pontos napja (pl. mikor volt a túlóra, mikor vonták le).
    #: SZÁNDÉKOSAN nem befolyásolja, melyik hónaphoz tartozik a tétel: azt
    #: kizárólag az URL-ben megadott (ev, honap) dönti el. Így egy hónap végi
    #: elszámolásba be lehet tenni egy más napra eső tételt is anélkül, hogy
    #: átugrana egy másik hónapba.
    datum: date | None = None
    megjegyzes: str | None = None


class HaviTetelPatch(BaseModel):
    """Részleges módosítás: CSAK a ténylegesen elküldött mezőket írjuk át.

    Külön séma a felvitelitől, mert ott minden mező kötelező. Ha itt is a
    felviteli sémát használnánk, egy "csak az összeget írom át" kérés némán
    törölné a tétel projektkódját és dátumát - a hiányzó mező ugyanis
    None-ként érkezne."""

    tipus: str | None = None
    megnevezes: str | None = None
    osszeg: float | None = None
    project_code_id: int | None = None
    datum: date | None = None
    megjegyzes: str | None = None


class HaviTetelRead(BaseModel):
    id: int
    employee_id: int
    ev: int
    honap: int
    tipus: str
    megnevezes: str
    osszeg: float
    project_code_id: int | None = None
    projektkod: str | None = None
    datum: date | None = None
    megjegyzes: str | None = None
    #: Ha ez a tétel egy pénzügyi kiadás-sorral ugyanaz a költség (Notionból
    #: mindkettőként bejön), akkor annak az azonosítója - a munkatárs
    #: adatlapja ez alapján nem írja ki kétszer ugyanazt az összeget.
    expense_id: int | None = None

    model_config = {"from_attributes": True}


def _tetel_kimenet(tetel: EmployeeMonthlyItem) -> HaviTetelRead:
    adat = HaviTetelRead.model_validate(tetel)
    adat.projektkod = tetel.project_code.projektkod if tetel.project_code else None
    return adat


def _honap_tetelei(db: Session, employee_id: int, ev: int, honap: int) -> list[EmployeeMonthlyItem]:
    sorok = (
        db.query(EmployeeMonthlyItem)
        .filter(
            EmployeeMonthlyItem.employee_id == employee_id,
            EmployeeMonthlyItem.ev == ev,
            EmployeeMonthlyItem.honap == honap,
        )
        .all()
    )
    # Alapbér -> extrák -> levonandók, típuson belül felvitel szerint: így a
    # lista úgy olvasható, ahogy az összeg összeáll (lásd TIPUS_SORREND).
    return sorted(sorok, key=lambda t: (TIPUS_SORREND.get(t.tipus, 9), t.id))


def _tiltsd_ha_lezart(db: Session, employee_id: int, ev: int, honap: int) -> None:
    """Véglegesített (kiküldött/kész/kihagyott) hónaphoz nem lehet tételt
    felvinni, módosítani vagy törölni.

    Azért tiltás és nem "csendben engedjük", mert az egész szerkezet azon áll,
    hogy A TÉTELEK ÖSSZEGE = A TIG ÖSSZEGE. Egy kiküldött igazolás összegét
    utólag nem írhatjuk át, tehát ha a tételt mégis engednénk, a bontás és a
    kiküldött összeg némán szétcsúszna - és épp az lenne megtévesztő, amit ez
    a nézet meg akar mutatni. Egy később felmerülő költség a KÖVETKEZŐ hónapra
    vihető fel (vagy a hónap állapotát kell visszaállítani)."""
    record = _find(db, employee_id, ev, honap)
    if record is not None and record.allapot in TERMINAL_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=(
                f"A(z) {ev_honap_szoveg(ev, honap)} hónap Belsős TIG-je már véglegesítve van "
                f'("{record.allapot}"), ezért a tételei nem módosíthatók. Vidd fel a következő '
                "hónapra, vagy állítsd vissza a hónap állapotát."
            ),
        )


def _ujraszamol_tig_osszeget(db: Session, employee: Employee, ev: int, honap: int) -> None:
    """A hónap TIG-jének nettó összege = a havi tételek összege.

    Ha még nincs TIG erre a hónapra, létrehozzuk (piszkozatként) - különben az
    első felvitt extra sehol nem látszódna.

    Az UTOLSÓ tétel törlésekor az összeg 0-ra áll (nem marad ott az előző,
    immár fedezet nélküli szám): a hónap összege végig a tételekből jön, tehát
    ha nem maradt tétel, nincs mi kiadja az összeget. Új TIG-et ilyenkor nem
    hozunk létre - egy üres hónapnak nem kell igazolás."""
    tetelek = _honap_tetelei(db, employee.id, ev, honap)
    if not tetelek:
        record = _find(db, employee.id, ev, honap)
        if record is not None:
            record.netto_osszeg = 0
        return
    record = _get_or_create(db, employee, ev, honap)
    record.netto_osszeg = float(sum(elojeles_osszeg(t.tipus, t.osszeg) for t in tetelek))


@router.get("/{employee_id}/{ev}/{honap}/tetelek", response_model=list[HaviTetelRead])
def list_havi_tetelek(
    employee_id: int,
    ev: int,
    honap: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(get_current_user),
):
    return [_tetel_kimenet(t) for t in _honap_tetelei(db, employee_id, ev, honap)]


@router.post("/{employee_id}/{ev}/{honap}/tetelek", response_model=HaviTetelRead)
def create_havi_tetel(
    employee_id: int,
    ev: int,
    honap: int,
    payload: HaviTetelIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "create")),
):
    employee = _validate_belsos_employee(db, employee_id)
    _tiltsd_ha_lezart(db, employee_id, ev, honap)
    if payload.tipus not in TETEL_TIPUSOK:
        raise HTTPException(status_code=400, detail=f"Ismeretlen tétel-típus: {payload.tipus}")
    if payload.tipus == "alapber" and any(
        t.tipus == "alapber" for t in _honap_tetelei(db, employee_id, ev, honap)
    ):
        raise HTTPException(status_code=409, detail="Ehhez a hónaphoz már van alapbér felvéve.")

    tetel = EmployeeMonthlyItem(
        employee_id=employee_id,
        ev=ev,
        honap=honap,
        tipus=payload.tipus,
        megnevezes=payload.megnevezes.strip() or ("Alapbér" if payload.tipus == "alapber" else "Extra"),
        osszeg=payload.osszeg,
        project_code_id=payload.project_code_id,
        datum=payload.datum,
        megjegyzes=payload.megjegyzes,
    )
    db.add(tetel)
    db.flush()
    _ujraszamol_tig_osszeget(db, employee, ev, honap)
    db.commit()
    db.refresh(tetel)
    return _tetel_kimenet(tetel)


@router.patch("/tetelek/{tetel_id}", response_model=HaviTetelRead)
def update_havi_tetel(
    tetel_id: int,
    payload: HaviTetelPatch,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit")),
):
    tetel = db.get(EmployeeMonthlyItem, tetel_id)
    if tetel is None:
        raise HTTPException(status_code=404, detail="A tétel nem található")
    _tiltsd_ha_lezart(db, tetel.employee_id, tetel.ev, tetel.honap)

    valtozok = payload.model_dump(exclude_unset=True)
    uj_tipus = valtozok.get("tipus")
    if uj_tipus is not None:
        if uj_tipus not in TETEL_TIPUSOK:
            raise HTTPException(status_code=400, detail=f"Ismeretlen tétel-típus: {uj_tipus}")
        # Alapbérből hónaponként csak egy lehet - ugyanaz a szabály, mint
        # felvitelnél; enélkül átminősítéssel meg lehetne kerülni.
        if uj_tipus == "alapber" and any(
            t.tipus == "alapber" and t.id != tetel.id
            for t in _honap_tetelei(db, tetel.employee_id, tetel.ev, tetel.honap)
        ):
            raise HTTPException(status_code=409, detail="Ehhez a hónaphoz már van alapbér felvéve.")

    # Csak a ténylegesen elküldött mezők - lásd HaviTetelPatch.
    for mezo, ertek in valtozok.items():
        if mezo == "megnevezes":
            ertek = (ertek or "").strip() or tetel.megnevezes
        # Az (ev, honap) SZÁNDÉKOSAN nincs a módosítható mezők közt: egy tétel
        # hovatartozását mindig a hónap-választás dönti el, nem a dátuma.
        setattr(tetel, mezo, ertek)
    db.flush()
    _ujraszamol_tig_osszeget(db, tetel.employee, tetel.ev, tetel.honap)
    db.commit()
    db.refresh(tetel)
    return _tetel_kimenet(tetel)


@router.delete("/tetelek/{tetel_id}", status_code=204)
def delete_havi_tetel(
    tetel_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "delete")),
):
    tetel = db.get(EmployeeMonthlyItem, tetel_id)
    if tetel is None:
        raise HTTPException(status_code=404, detail="A tétel nem található")
    _tiltsd_ha_lezart(db, tetel.employee_id, tetel.ev, tetel.honap)
    employee, ev, honap = tetel.employee, tetel.ev, tetel.honap
    db.delete(tetel)
    db.flush()
    _ujraszamol_tig_osszeget(db, employee, ev, honap)
    db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Bejelentett alkalmazott havi fizetése
#
# Nála nincs TIG és nincs számla, ezért a fenti folyamat egyetlen lépéssé
# rövidül: beírjuk a hónap nettó bérét, és ezzel kész a hónap.
# ─────────────────────────────────────────────────────────────────────────────


class FizetesIn(BaseModel):
    """A bejelentett alkalmazott havi fizetése."""

    #: A hónap nettó bére (az alapbér tétel összege).
    netto_ber: float


@router.post("/{employee_id}/{ev}/{honap}/fizetes", response_model=InternalPerformanceCertificateRead)
def save_fizetes(
    employee_id: int,
    ev: int,
    honap: int,
    payload: FizetesIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "create")),
):
    """A bejelentett alkalmazott havi fizetésének rögzítése egy lépésben.

    A nettó bért a hónap ALAPBÉR TÉTELEKÉNT tesszük el, nem közvetlenül a
    bejegyzés összegébe: a hónap nettó összege mindenkinél a tételekből
    számolódik (lásd _ujraszamol_tig_osszeget), tehát ha ezt megkerülnénk, egy
    később felvitt extra némán felülírná a beírt fizetést."""
    employee = _validate_belsos_employee(db, employee_id)
    if belsos_idoszak.kell_havi_tig(employee):
        raise HTTPException(
            status_code=400,
            detail=(
                f"{employee.full_name} megbízási szerződéssel dolgozik, nála havi TIG készül. "
                "A fizetés beírása bejelentett alkalmazotthoz való."
            ),
        )
    _tiltsd_ha_lezart(db, employee_id, ev, honap)

    alapber = next((t for t in _honap_tetelei(db, employee_id, ev, honap) if t.tipus == "alapber"), None)
    if alapber is None:
        alapber = EmployeeMonthlyItem(
            employee_id=employee_id, ev=ev, honap=honap, tipus="alapber", megnevezes="Munkabér", osszeg=payload.netto_ber
        )
        db.add(alapber)
    else:
        alapber.osszeg = payload.netto_ber
    db.flush()

    _ujraszamol_tig_osszeget(db, employee, ev, honap)
    record = _get_or_create(db, employee, ev, honap)
    db.commit()
    db.refresh(record)
    return InternalPerformanceCertificateRead.model_validate(record)


class HaviKoltseg(BaseModel):
    """Egy hónap: mibe került nekünk ez az ember."""

    ev: int
    honap: int
    honap_nev: str
    tig_id: int | None = None
    allapot: str | None = None
    netto_osszeg: float | None = None
    brutto_osszeg: float | None = None
    alapber: float = 0
    extra: float = 0
    #: A levonandó tételek összege POZITÍVAN - a nettó összegből már le van vonva.
    levonas: float = 0
    tetelek: list[HaviTetelRead] = []


class EvesKoltseg(BaseModel):
    ev: int
    osszesen: float
    honapok: list[HaviKoltseg]


class HonapReszletek(BaseModel):
    """Egy munkatárs EGY hónapja teljes egészében - ezt nyitja meg a saját
    oldala (lásd frontend app/(app)/belsos-tig/[employeeId]/[ev]/[honap])."""

    employee_id: int
    full_name: str
    ev: int
    honap: int
    honap_nev: str
    record: InternalPerformanceCertificateRead | None = None
    tetelek: list[HaviTetelRead] = []
    alapber: float = 0
    extra: float = 0
    #: A levonandó tételek összege POZITÍVAN; az `osszesen`-ből már levontuk.
    levonas: float = 0
    osszesen: float = 0


@router.get("/{employee_id}/{ev}/{honap}/reszletek", response_model=HonapReszletek)
def honap_reszletek(
    employee_id: int,
    ev: int,
    honap: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(get_current_user),
):
    """Egy hónap teljes képe: az alapbér, a hozzáadott extrák, a szumma, és a
    hónap TIG-je (állapot, dokumentum, számlák).

    Az `osszesen` a TÉTELEK összege - ez az, ami a TIG-re kerül. Ha egy régi
    hónapnál nincsenek tételek (a tételes nyilvántartás előttről), a TIG-en
    rögzített nettó összeget adjuk vissza, hogy a nézet akkor se legyen üres."""
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Munkatárs nem található")

    record = _find(db, employee_id, ev, honap)
    tetelek = _honap_tetelei(db, employee_id, ev, honap)
    alapber = float(sum(float(t.osszeg or 0) for t in tetelek if t.tipus == "alapber"))
    extra = float(sum(float(t.osszeg or 0) for t in tetelek if t.tipus == "extra"))
    levonas = float(sum(float(t.osszeg or 0) for t in tetelek if t.tipus == "levonando"))
    olvasott = InternalPerformanceCertificateRead.model_validate(record) if record is not None else None

    return HonapReszletek(
        employee_id=employee_id,
        full_name=employee.full_name,
        ev=ev,
        honap=honap,
        honap_nev=honap_neve(honap),
        record=olvasott,
        tetelek=[_tetel_kimenet(t) for t in tetelek],
        alapber=alapber,
        extra=extra,
        levonas=levonas,
        osszesen=(
            alapber + extra - levonas
            if tetelek
            else float(olvasott.netto_osszeg or 0)
            if olvasott
            else 0
        ),
    )


@router.get("/employee/{employee_id}/koltsegek", response_model=list[EvesKoltseg])
def employee_koltsegek(
    employee_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(get_current_user),
):
    """Egy munkatárs havi költségei ÉVEKRE csoportosítva, évente összesítve -
    ez válaszolja meg az adatlapon, hogy "mibe került nekünk ez az ember".

    Két forrásból áll össze, hónapra vetítve: a hónap Belsős TIG-je (ez a
    kifizetett összeg) és a hónaphoz rögzített tételek (ebből látszik, MIBŐL
    jött ki). Az évi összeg a TIG-ek nettó összege - a tételek ugyanazt az
    összeget bontják, nem jönnek hozzá még egyszer."""
    tigek = (
        db.query(InternalPerformanceCertificate)
        .filter(InternalPerformanceCertificate.employee_id == employee_id)
        .all()
    )
    tetelek = (
        db.query(EmployeeMonthlyItem).filter(EmployeeMonthlyItem.employee_id == employee_id).all()
    )

    honapok: dict[tuple[int, int], HaviKoltseg] = {}

    def _honap(ev: int, honap: int) -> HaviKoltseg:
        kulcs = (ev, honap)
        if kulcs not in honapok:
            honapok[kulcs] = HaviKoltseg(ev=ev, honap=honap, honap_nev=honap_neve(honap))
        return honapok[kulcs]

    for tig in tigek:
        adat = _honap(tig.ev, tig.honap)
        olvasott = InternalPerformanceCertificateRead.model_validate(tig)
        adat.tig_id = tig.id
        adat.allapot = tig.allapot
        adat.netto_osszeg = olvasott.netto_osszeg
        adat.brutto_osszeg = olvasott.brutto_osszeg

    for tetel in tetelek:
        adat = _honap(tetel.ev, tetel.honap)
        adat.tetelek.append(_tetel_kimenet(tetel))
        if tetel.tipus == "alapber":
            adat.alapber += float(tetel.osszeg or 0)
        elif tetel.tipus == "levonando":
            adat.levonas += float(tetel.osszeg or 0)
        else:
            adat.extra += float(tetel.osszeg or 0)

    evek: dict[int, list[HaviKoltseg]] = {}
    for adat in honapok.values():
        adat.tetelek.sort(key=lambda t: (TIPUS_SORREND.get(t.tipus, 9), t.id))
        # Ha a hónapnak még nincs TIG-en rögzített összege, a TÉTELEK adják ki -
        # különben egy tételekkel teli hónap 0 Ft-ként jelenne meg, és az éves
        # összesítőből is kimaradna.
        if adat.netto_osszeg is None and adat.tetelek:
            adat.netto_osszeg = adat.alapber + adat.extra - adat.levonas
        evek.setdefault(adat.ev, []).append(adat)

    return [
        EvesKoltseg(
            ev=ev,
            osszesen=float(sum(h.netto_osszeg or 0 for h in sorted_honapok)),
            honapok=sorted_honapok,
        )
        for ev, sorted_honapok in (
            (ev, sorted(lista, key=lambda h: h.honap, reverse=True)) for ev, lista in evek.items()
        )
    ]
