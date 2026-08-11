"""Az összes külsős teljesítési igazolás EGY listában.

Az eseti szerződések (routes/eseti_szerzodesek.py) párja a TIG oldalán, és
ugyanazért kell: eddig csak szétszórva lehetett rájuk látni - projektenként az
Utókövetésen, emberenként a munkatárs adatlapján -, tehát arra a kérdésre, hogy
"hol tart a külsős TIG-ezés összességében", nem volt hely, ahol válasz lett volna.

A KIHAGYOTTAK is benne vannak, az indokukkal együtt. Ez a lista lényege: egy
kihagyott TIG ugyanúgy elszámolás, mint egy kiküldött, csak papír nélkül - ha
kimaradna innen, pont az a néhány tétel tűnne el, amit a legvalószínűbben
számon kérnek később.

A belsős TIG-ek NINCSENEK itt: azok haviak, nem projektenkéntiek, és saját
oldaluk van (lásd /belsos-tig)."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.security import require_page_action
from app.models.employee import Employee, EmployeeType
from app.models.performance_certificate import PerformanceCertificate, PerformanceCertificateTetel
from app.models.project import Project
from app.services import szamlazo

router = APIRouter(prefix="/kulsos-tigek", tags=["performance-certificates"])

#: A TIG-műveletek az Utókövetés oldalhoz tartoznak (lásd
#: routes/performance_certificates.py) - ez a gyűjtő lista is annak a joga.
PAGE = "/utokovetes"


class KulsosTig(BaseModel):
    id: int

    #: A SZÁMLÁZÓ FÉL, akinek a nevére a TIG szól: ember VAGY vállalkozás.
    employee_id: int | None = None
    employee_nev: str | None = None
    vallalkozas_id: int | None = None
    vallalkozas_nev: str | None = None
    #: Kinek a munkáját igazolja - a TIG tételeiből. Egynél több akkor, ha a
    #: fél más(ok) nevében is számláz (lásd services/szamlazo.py).
    lefedettek: list[str] = []

    #: A TIG "otthona". A tételei ettől több projektet is érinthetnek.
    project_id: int | None = None
    project_nev: str | None = None
    projektkod: str | None = None
    forgatas_datuma: date | None = None
    #: Hány projekt munkáját igazolja összesen (1 = csak a sajátját).
    projektek_szama: int = 1

    allapot: str | None = None
    #: MIÉRT hagytuk ki - csak a kihagyottaknál van kitöltve.
    kihagyas_oka: str | None = None
    megbizas_targya: str | None = None
    netto_osszeg: float | None = None
    brutto_osszeg: float | None = None
    plusz_afa: bool | None = None
    teljesites_szoveg: str | None = None
    keltezes: date | None = None
    file_url: str | None = None
    #: A TIG után jövő lépés: számla és kifizetés.
    szamla_db: int = 0
    szamla_kifizetve: bool = False


def _teljesites(t: PerformanceCertificate) -> str | None:
    """Ugyanaz a szöveg, ami a papírra kerül: elsősorban a szabad szöveges
    mező, és csak a régi, dátumpáros bejegyzéseknél a két dátumból."""
    szoveg = (t.teljesites_szoveg or "").strip()
    if szoveg:
        return szoveg
    if t.teljesites_vege and t.teljesites_vege != t.teljesites_kezdete:
        kezdet = t.teljesites_kezdete.strftime("%Y.%m.%d.") if t.teljesites_kezdete else ""
        return f"{kezdet} - {t.teljesites_vege.strftime('%Y.%m.%d.')}"
    if t.teljesites_kezdete:
        return t.teljesites_kezdete.strftime("%Y.%m.%d.")
    return None


@router.get("", response_model=list[KulsosTig])
def list_kulsos_tigek(
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view")),
):
    """Minden külsős TIG - a kihagyottakkal és az indokukkal együtt.

    A legfrissebb elöl: a forgatás dátuma szerint, dátum nélkül a keltezés,
    végül az azonosító dönt."""
    tigek = (
        db.query(PerformanceCertificate)
        .options(
            selectinload(PerformanceCertificate.employee),
            selectinload(PerformanceCertificate.vallalkozas),
            selectinload(PerformanceCertificate.invoices),
            selectinload(PerformanceCertificate.tetelek).selectinload(PerformanceCertificateTetel.employee),
            selectinload(PerformanceCertificate.project).selectinload(Project.project_code),
            selectinload(PerformanceCertificate.project).selectinload(Project.crew),
        )
        .all()
    )
    # A tétel nélküli (Notion-importból vagy kézi javításból maradt) TIG-eknél
    # a "kit fed le" a projekt-beosztásból jön - ugyanaz a visszafelé
    # kompatibilis szabály, mint a papír-fedettségnél (lásd
    # services/papir_fedettseg.py).
    felulirasok = szamlazo.load_felulirasok(db, {t.project_id for t in tigek if t.project_id})

    sorok: list[KulsosTig] = []
    for t in tigek:
        netto = float(t.netto_osszeg) if t.netto_osszeg is not None else None
        projekt = t.project
        kulcs = f"v{t.vallalkozas_id}" if t.vallalkozas_id else (f"e{t.employee_id}" if t.employee_id else None)

        if t.tetelek:
            lefedettek = [tetel.employee.full_name for tetel in t.tetelek if tetel.employee is not None]
            projektek_szama = len({tetel.project_id for tetel in t.tetelek})
        elif projekt is not None and kulcs is not None:
            lefedettek = [
                e.full_name
                for e in projekt.crew
                if e.tipus != EmployeeType.BELSOS
                and szamlazo.szamlazo_fele(projekt, e, felulirasok).kulcs == kulcs
            ]
            projektek_szama = 1
        else:
            lefedettek = []
            projektek_szama = 1

        sorok.append(
            KulsosTig(
                id=t.id,
                employee_id=t.employee_id,
                employee_nev=t.employee.full_name if t.employee else None,
                vallalkozas_id=t.vallalkozas_id,
                vallalkozas_nev=t.vallalkozas.nev if t.vallalkozas else None,
                lefedettek=lefedettek,
                project_id=t.project_id,
                project_nev=projekt.nev if projekt else None,
                projektkod=projekt.project_code.projektkod if projekt and projekt.project_code else None,
                forgatas_datuma=projekt.forgatas_datuma if projekt else None,
                projektek_szama=projektek_szama,
                allapot=t.allapot,
                kihagyas_oka=t.kihagyas_oka,
                megbizas_targya=t.megbizas_targya,
                netto_osszeg=netto,
                brutto_osszeg=round(netto * 1.27, 2) if (netto is not None and t.plusz_afa) else netto,
                plusz_afa=t.plusz_afa,
                teljesites_szoveg=_teljesites(t),
                keltezes=t.keltezes,
                file_url=t.file_url,
                szamla_db=len(t.invoices),
                szamla_kifizetve=bool(t.szamla_kifizetve),
            )
        )

    sorok.sort(key=lambda s: (s.forgatas_datuma or s.keltezes or date.min, s.id), reverse=True)
    return sorok


class TigTetelInfo(BaseModel):
    """Egy tétel a TIG-en: kinek a munkája, melyik projekten."""

    project_id: int
    project_nev: str | None = None
    projektkod: str | None = None
    forgatas_datuma: date | None = None
    employee_id: int
    employee_nev: str | None = None
    netto_osszeg: float | None = None
    megnevezes: str | None = None


class TigSzamlaInfo(BaseModel):
    id: int
    filename: str
    url: str


class KulsosTigReszlet(KulsosTig):
    """A TIG teljes adatlapja - a listasor mezőin FELÜL a papírra kerülő
    adatok, a tételek és a feltöltött számlák.

    Azért külön séma, és nem a listáé: a lista több száz sor lehet, oda nem
    kell minden mező és minden kapcsolt rekord - a részletet viszont csak egy
    sorra kérjük le, amikor a felhasználó tényleg belenéz."""

    ceg_neve: str | None = None
    szekhely: str | None = None
    adoszam: str | None = None
    email: str | None = None
    tetelek: list[TigTetelInfo] = []
    szamlak: list[TigSzamlaInfo] = []


@router.get("/{tig_id}", response_model=KulsosTigReszlet)
def get_kulsos_tig(
    tig_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view")),
):
    """EGY külsős TIG minden adata - ezt nyitja meg a listán a sorra kattintás.

    A tételek mondják meg, kinek a munkáját melyik projekten igazolja: a
    felugró ablakban pont ez a kérdés, ha a TIG több embert vagy több
    forgatást fed le egy papíron."""
    t = (
        db.query(PerformanceCertificate)
        .options(
            selectinload(PerformanceCertificate.employee),
            selectinload(PerformanceCertificate.vallalkozas),
            selectinload(PerformanceCertificate.invoices),
            selectinload(PerformanceCertificate.tetelek).selectinload(PerformanceCertificateTetel.employee),
            selectinload(PerformanceCertificate.tetelek)
            .selectinload(PerformanceCertificateTetel.project)
            .selectinload(Project.project_code),
            selectinload(PerformanceCertificate.project).selectinload(Project.project_code),
            selectinload(PerformanceCertificate.project).selectinload(Project.crew),
        )
        .filter(PerformanceCertificate.id == tig_id)
        .first()
    )
    if t is None:
        raise HTTPException(status_code=404, detail="Ez a teljesítési igazolás nem található.")

    felulirasok = szamlazo.load_felulirasok(db, {t.project_id} if t.project_id else set())
    netto = float(t.netto_osszeg) if t.netto_osszeg is not None else None
    projekt = t.project
    kulcs = f"v{t.vallalkozas_id}" if t.vallalkozas_id else (f"e{t.employee_id}" if t.employee_id else None)

    if t.tetelek:
        lefedettek = [tetel.employee.full_name for tetel in t.tetelek if tetel.employee is not None]
        projektek_szama = len({tetel.project_id for tetel in t.tetelek})
    elif projekt is not None and kulcs is not None:
        lefedettek = [
            e.full_name
            for e in projekt.crew
            if e.tipus != EmployeeType.BELSOS and szamlazo.szamlazo_fele(projekt, e, felulirasok).kulcs == kulcs
        ]
        projektek_szama = 1
    else:
        lefedettek = []
        projektek_szama = 1

    return KulsosTigReszlet(
        id=t.id,
        employee_id=t.employee_id,
        employee_nev=t.employee.full_name if t.employee else None,
        vallalkozas_id=t.vallalkozas_id,
        vallalkozas_nev=t.vallalkozas.nev if t.vallalkozas else None,
        lefedettek=lefedettek,
        project_id=t.project_id,
        project_nev=projekt.nev if projekt else None,
        projektkod=projekt.project_code.projektkod if projekt and projekt.project_code else None,
        forgatas_datuma=projekt.forgatas_datuma if projekt else None,
        projektek_szama=projektek_szama,
        allapot=t.allapot,
        kihagyas_oka=t.kihagyas_oka,
        megbizas_targya=t.megbizas_targya,
        netto_osszeg=netto,
        brutto_osszeg=round(netto * 1.27, 2) if (netto is not None and t.plusz_afa) else netto,
        plusz_afa=t.plusz_afa,
        teljesites_szoveg=_teljesites(t),
        keltezes=t.keltezes,
        file_url=t.file_url,
        szamla_db=len(t.invoices),
        szamla_kifizetve=bool(t.szamla_kifizetve),
        ceg_neve=t.ceg_neve,
        szekhely=t.szekhely,
        adoszam=t.adoszam,
        email=t.email,
        tetelek=[
            TigTetelInfo(
                project_id=tetel.project_id,
                project_nev=tetel.project.nev if tetel.project else None,
                projektkod=(
                    tetel.project.project_code.projektkod
                    if tetel.project and tetel.project.project_code
                    else None
                ),
                forgatas_datuma=tetel.project.forgatas_datuma if tetel.project else None,
                employee_id=tetel.employee_id,
                employee_nev=tetel.employee.full_name if tetel.employee else None,
                netto_osszeg=float(tetel.netto_osszeg) if tetel.netto_osszeg is not None else None,
                megnevezes=tetel.megnevezes,
            )
            for tetel in t.tetelek
        ],
        szamlak=[TigSzamlaInfo(id=f.id, filename=f.filename, url=f.url) for f in t.invoices],
    )
