"""Munkafelajánlások - belső (kezelő) és publikus (személyes linkes) végpontok.

Belső: ajánlatkérés létrehozása, meghívottak, kiküldés/újraküldés, ajánlat-
összehasonlítás, kiválasztás (csak a határidő után), lezárás nyertes nélkül,
visszavonás, eredmény-értesítők.

Publikus: a meghívott a saját tokenjével látja a feladatot, beküldheti,
módosíthatja és visszavonhatja az ajánlatát a határidőig - mások nevét,
ajánlatát és a jelentkezők számát SOHA nem látja."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.security import Role, get_current_user, require_page_action
from app.models.employee import Employee
from app.models.munkafelajanlas import Ajanlatkeres, AjanlatMeghivott
from app.services import munkafelajanlas as szolg
from fastapi import HTTPException

PAGE = "/munkafelajanlasok"
#: A szerepkör-kaput itt is a page_permissions helyettesíti (mint a FLÓRA-nál).
_MINDEN_SZEREPKOR = tuple(Role)

router = APIRouter(prefix="/munkafelajanlasok", tags=["munkafelajanlasok"])
public_router = APIRouter(prefix="/public/ajanlat", tags=["munkafelajanlasok-public"])


# --- Sémák -------------------------------------------------------------------


class AjanlatkeresIn(BaseModel):
    #: A MEGLÉVŐ projektek közül választva (a felhasználó kérése) - a
    #: felület ezt küldi; a projekt_nev csak tartalék (pl. API-hívónak).
    project_id: int | None = None
    projekt_nev: str = ""
    munkakor: str
    leiras: str | None = None
    helyszin: str | None = None
    munkavegzes_idopont: str | None = None
    teljesitesi_hatarido: str | None = None
    #: "YYYY-MM-DDTHH:MM" MAGYAR IDŐ szerint (Europe/Budapest) - a szerver
    #: váltja UTC-re (lásd services/munkafelajanlas.budapest_datetime_utc).
    valaszadasi_hatarido: str | None = None
    kapcsolattarto_id: int | None = None
    meghivott_employee_ids: list[int] = []


class MeghivottakIn(BaseModel):
    employee_ids: list[int]


class KivalasztasIn(BaseModel):
    meghivott_id: int


class LezarasIn(BaseModel):
    megjegyzes: str | None = None


class AjanlatInfo(BaseModel):
    osszeg: float
    penznem: str
    brutto: bool
    megjegyzes: str | None
    vallalja: bool
    bekuldve: str | None
    modositva: str | None
    visszavonva: bool
    #: bekuldve / visszavonva / elfogadva / elutasitva - a belső tábla
    #: "ajánlat állapota" oszlopa.
    allapot: str


class MeghivottInfo(BaseModel):
    id: int
    employee_id: int
    nev: str
    email: str | None
    link: str
    meghivo_kikuldve: str | None
    meghivo_hiba: str | None
    eredmeny_kikuldve: str | None
    eredmeny_hiba: str | None
    nyertes: bool
    ajanlat: AjanlatInfo | None


class AjanlatkeresOut(BaseModel):
    id: int
    project_id: int | None
    projekt_nev: str
    munkakor: str
    leiras: str | None
    helyszin: str | None
    munkavegzes_idopont: str | None
    teljesitesi_hatarido: str | None
    valaszadasi_hatarido: str | None  # ISO UTC ("...Z")
    valaszadasi_hatarido_szoveg: str  # magyar idő szerint, emberi alakban
    lejart: bool
    allapot: str  # effektív (dontesre_var származtatva)
    kapcsolattarto_id: int | None
    kapcsolattarto_nev: str | None
    nyertes_meghivott_id: int | None
    elfogadott_osszeg: float | None
    elfogadott_penznem: str | None
    elfogadott_brutto: bool | None
    lezarva: str | None
    lezaras_megjegyzes: str | None
    meghivott_db: int
    ajanlat_db: int
    kuldes_hiba_db: int


class AjanlatkeresReszlet(AjanlatkeresOut):
    meghivottak: list[MeghivottInfo]


# --- Kimenet-építők ----------------------------------------------------------


def _iso(dt) -> str | None:
    return dt.isoformat() + "Z" if dt is not None else None


def _ajanlat_info(ak: Ajanlatkeres, m: AjanlatMeghivott) -> AjanlatInfo | None:
    a = m.ajanlat
    if a is None:
        return None
    if a.visszavonva is not None:
        allapot = "visszavonva"
    elif ak.allapot == "kiosztva":
        allapot = "elfogadva" if m.id == ak.nyertes_meghivott_id else "elutasitva"
    else:
        allapot = "bekuldve"
    return AjanlatInfo(
        osszeg=float(a.osszeg),
        penznem=a.penznem,
        brutto=a.brutto,
        megjegyzes=a.megjegyzes,
        vallalja=a.vallalja,
        bekuldve=_iso(a.bekuldve),
        modositva=_iso(a.modositva),
        visszavonva=a.visszavonva is not None,
        allapot=allapot,
    )


def _meghivott_info(ak: Ajanlatkeres, m: AjanlatMeghivott) -> MeghivottInfo:
    return MeghivottInfo(
        id=m.id,
        employee_id=m.employee_id,
        nev=m.employee.full_name if m.employee else f"#{m.employee_id}",
        email=m.email_cim or (m.employee.email if m.employee else None),
        link=szolg.ajanlati_link(m.token),
        meghivo_kikuldve=_iso(m.meghivo_kikuldve),
        meghivo_hiba=m.meghivo_hiba,
        eredmeny_kikuldve=_iso(m.eredmeny_kikuldve),
        eredmeny_hiba=m.eredmeny_hiba,
        nyertes=m.id == ak.nyertes_meghivott_id,
        ajanlat=_ajanlat_info(ak, m),
    )


def _kimenet(ak: Ajanlatkeres) -> AjanlatkeresOut:
    elo_ajanlatok = [m for m in ak.meghivottak if m.ajanlat is not None and m.ajanlat.visszavonva is None]
    kuldes_hibak = sum(1 for m in ak.meghivottak if m.meghivo_hiba or m.eredmeny_hiba)
    return AjanlatkeresOut(
        id=ak.id,
        project_id=ak.project_id,
        projekt_nev=ak.projekt_nev,
        munkakor=ak.munkakor,
        leiras=ak.leiras,
        helyszin=ak.helyszin,
        munkavegzes_idopont=ak.munkavegzes_idopont,
        teljesitesi_hatarido=ak.teljesitesi_hatarido,
        valaszadasi_hatarido=_iso(ak.valaszadasi_hatarido),
        valaszadasi_hatarido_szoveg=szolg.budapest_szoveg(ak.valaszadasi_hatarido),
        lejart=szolg.lejart(ak),
        allapot=szolg.effektiv_allapot(ak),
        kapcsolattarto_id=ak.kapcsolattarto_id,
        kapcsolattarto_nev=ak.kapcsolattarto.full_name if ak.kapcsolattarto else None,
        nyertes_meghivott_id=ak.nyertes_meghivott_id,
        elfogadott_osszeg=float(ak.elfogadott_osszeg) if ak.elfogadott_osszeg is not None else None,
        elfogadott_penznem=ak.elfogadott_penznem,
        elfogadott_brutto=ak.elfogadott_brutto,
        lezarva=_iso(ak.lezarva),
        lezaras_megjegyzes=ak.lezaras_megjegyzes,
        meghivott_db=len(ak.meghivottak),
        ajanlat_db=len(elo_ajanlatok),
        kuldes_hiba_db=kuldes_hibak,
    )


def _reszlet(ak: Ajanlatkeres) -> AjanlatkeresReszlet:
    alap = _kimenet(ak)
    return AjanlatkeresReszlet(
        **alap.model_dump(),
        meghivottak=[_meghivott_info(ak, m) for m in ak.meghivottak],
    )


def _projekt_nev_feloldas(db: Session, payload: AjanlatkeresIn) -> str:
    """A projekt a MEGLÉVŐ projektek közül választandó (a felhasználó
    kérése): a project_id-ból vesszük a nevet. A szabad szöveges projekt_nev
    csak tartalék (pl. AI-asszisztens vagy API-hívó), project_id nélkül."""
    if payload.project_id is not None:
        from app.models.project import Project

        projekt = db.get(Project, payload.project_id)
        if projekt is None:
            raise HTTPException(status_code=400, detail="A kiválasztott projekt nem található.")
        return projekt.nev
    nev = (payload.projekt_nev or "").strip()
    if not nev:
        raise HTTPException(status_code=400, detail="Válaszd ki a projektet a meglévő projektek közül.")
    return nev


def _betolt(db: Session, ajanlatkeres_id: int) -> Ajanlatkeres:
    ak = db.execute(
        select(Ajanlatkeres)
        .where(Ajanlatkeres.id == ajanlatkeres_id)
        .options(selectinload(Ajanlatkeres.meghivottak).selectinload(AjanlatMeghivott.ajanlat))
    ).scalar_one_or_none()
    if ak is None:
        raise HTTPException(status_code=404, detail="Az ajánlatkérés nem található.")
    return ak


# --- Belső végpontok ---------------------------------------------------------


@router.get("", response_model=list[AjanlatkeresOut])
def lista(
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
):
    sorok = db.scalars(
        select(Ajanlatkeres)
        .options(selectinload(Ajanlatkeres.meghivottak).selectinload(AjanlatMeghivott.ajanlat))
        .order_by(Ajanlatkeres.id.desc())
    ).all()
    return [_kimenet(ak) for ak in sorok]


@router.post("", response_model=AjanlatkeresReszlet, status_code=201)
def letrehozas(
    payload: AjanlatkeresIn,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_page_action(PAGE, "create", *_MINDEN_SZEREPKOR)),
):
    """Új ajánlatkérés PISZKOZATKÉNT - a kiküldés külön, szándékos lépés.
    Felajánlott díjat szándékosan nem lehet megadni: az árat a meghívott
    külsősök ajánlják meg (a felhasználó kérése). A projekt a MEGLÉVŐ
    projektek közül választandó (project_id) - a neve pillanatképként
    másolódik át."""
    projekt_nev = _projekt_nev_feloldas(db, payload)
    if not payload.munkakor.strip():
        raise HTTPException(status_code=400, detail="A munkakör megadása kötelező.")
    ak = Ajanlatkeres(
        project_id=payload.project_id,
        projekt_nev=projekt_nev,
        munkakor=payload.munkakor.strip(),
        leiras=(payload.leiras or "").strip() or None,
        helyszin=(payload.helyszin or "").strip() or None,
        munkavegzes_idopont=(payload.munkavegzes_idopont or "").strip() or None,
        teljesitesi_hatarido=(payload.teljesitesi_hatarido or "").strip() or None,
        valaszadasi_hatarido=(
            szolg.budapest_datetime_utc(payload.valaszadasi_hatarido) if payload.valaszadasi_hatarido else None
        ),
        kapcsolattarto_id=payload.kapcsolattarto_id,
        letrehozta_id=current_user.id,
    )
    db.add(ak)
    db.commit()
    db.refresh(ak)
    if payload.meghivott_employee_ids:
        szolg.meghivottak_beallitasa(db, ak, payload.meghivott_employee_ids)
    return _reszlet(_betolt(db, ak.id))


@router.get("/{ajanlatkeres_id}", response_model=AjanlatkeresReszlet)
def reszletek(
    ajanlatkeres_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
):
    return _reszlet(_betolt(db, ajanlatkeres_id))


@router.patch("/{ajanlatkeres_id}", response_model=AjanlatkeresReszlet)
def modositas(
    ajanlatkeres_id: int,
    payload: AjanlatkeresIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """A feladat adatai piszkozatban szabadon szerkeszthetők; kiküldés után
    már csak a válaszadási határidő HOSSZABBÍTHATÓ (a meghívottak a kiküldött
    levélben szereplő feltételekre adnak ajánlatot - azok nem cserélhetők ki
    alattuk)."""
    ak = _betolt(db, ajanlatkeres_id)
    if ak.allapot == "piszkozat":
        if payload.project_id is not None or (payload.projekt_nev or "").strip():
            ak.projekt_nev = _projekt_nev_feloldas(db, payload)
            ak.project_id = payload.project_id
        ak.munkakor = payload.munkakor.strip() or ak.munkakor
        ak.leiras = (payload.leiras or "").strip() or None
        ak.helyszin = (payload.helyszin or "").strip() or None
        ak.munkavegzes_idopont = (payload.munkavegzes_idopont or "").strip() or None
        ak.teljesitesi_hatarido = (payload.teljesitesi_hatarido or "").strip() or None
        ak.kapcsolattarto_id = payload.kapcsolattarto_id
        if payload.valaszadasi_hatarido:
            ak.valaszadasi_hatarido = szolg.budapest_datetime_utc(payload.valaszadasi_hatarido)
    elif ak.allapot == "ajanlatadas":
        if not payload.valaszadasi_hatarido:
            raise HTTPException(status_code=400, detail="Kiküldés után csak a válaszadási határidő módosítható.")
        uj = szolg.budapest_datetime_utc(payload.valaszadasi_hatarido)
        if ak.valaszadasi_hatarido and uj < ak.valaszadasi_hatarido:
            raise HTTPException(
                status_code=400,
                detail="A határidő csak hosszabbítható - rövidítéssel a már megkapott levelekben szereplő "
                "határidő hazudna.",
            )
        ak.valaszadasi_hatarido = uj
    else:
        raise HTTPException(status_code=400, detail="Lezárt ajánlatkérés nem módosítható.")
    db.commit()
    return _reszlet(_betolt(db, ajanlatkeres_id))


@router.delete("/{ajanlatkeres_id}", status_code=204)
def torles(
    ajanlatkeres_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "delete", *_MINDEN_SZEREPKOR)),
):
    """Csak PISZKOZAT törölhető - amiről már ment ki levél, azt visszavonni
    lehet (a meghívottak értesítésével), nem nyomtalanul eltüntetni."""
    ak = _betolt(db, ajanlatkeres_id)
    if ak.allapot != "piszkozat":
        raise HTTPException(status_code=400, detail="Csak piszkozat törölhető - a kiküldöttet vond vissza.")
    db.delete(ak)
    db.commit()


@router.put("/{ajanlatkeres_id}/meghivottak", response_model=AjanlatkeresReszlet)
def meghivottak(
    ajanlatkeres_id: int,
    payload: MeghivottakIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    ak = _betolt(db, ajanlatkeres_id)
    szolg.meghivottak_beallitasa(db, ak, payload.employee_ids)
    return _reszlet(_betolt(db, ajanlatkeres_id))


@router.post("/{ajanlatkeres_id}/kikuldes", response_model=AjanlatkeresReszlet)
def kikuldes(
    ajanlatkeres_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """Az ajánlatkérés ÉLESÍTÉSE: piszkozat -> ajánlatadás folyamatban, és a
    személyre szóló meghívók kiküldése. Ha egy levél elhasal, az állapot attól
    még él: a hibás küldés az /ujrakuldes-sel ismételhető."""
    ak = _betolt(db, ajanlatkeres_id)
    if ak.allapot == "ajanlatadas":
        # Idempotencia: az ismételt kattintás nem duplikál levelet - csak a
        # még ki nem küldötteket pótolja.
        szolg.meghivok_kikuldese(db, ak)
        return _reszlet(_betolt(db, ajanlatkeres_id))
    if ak.allapot != "piszkozat":
        raise HTTPException(status_code=400, detail="Csak piszkozat küldhető ki.")
    if not ak.meghivottak:
        raise HTTPException(status_code=400, detail="Előbb válaszd ki, mely külsősöknek menjen az ajánlatkérés.")
    if ak.valaszadasi_hatarido is None:
        raise HTTPException(status_code=400, detail="A válaszadási határidő megadása kötelező a kiküldéshez.")
    if szolg.lejart(ak):
        raise HTTPException(status_code=400, detail="A válaszadási határidő a múltban van - előbb igazítsd ki.")
    ak.allapot = "ajanlatadas"
    db.commit()
    szolg.meghivok_kikuldese(db, ak)
    return _reszlet(_betolt(db, ajanlatkeres_id))


@router.post("/{ajanlatkeres_id}/ujrakuldes", response_model=AjanlatkeresReszlet)
def ujrakuldes(
    ajanlatkeres_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """A SIKERTELEN küldések megismétlése - a már sikeresen kézbesített
    levelek nem mennek ki még egyszer (meghívó és eredmény-értesítő is)."""
    ak = _betolt(db, ajanlatkeres_id)
    if ak.allapot == "ajanlatadas":
        szolg.meghivok_kikuldese(db, ak, csak_hibasak=False)
    elif ak.allapot in ("kiosztva", "lezarva_nyertes_nelkul", "visszavonva"):
        szolg.eredmenyek_kikuldese(db, ak, csak_hibasak=False)
    else:
        raise HTTPException(status_code=400, detail="Ebben az állapotban nincs mit újraküldeni.")
    return _reszlet(_betolt(db, ajanlatkeres_id))


@router.post("/{ajanlatkeres_id}/kivalasztas", response_model=AjanlatkeresReszlet)
def kivalasztas(
    ajanlatkeres_id: int,
    payload: KivalasztasIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    """A NYERTES kijelölése - csak a határidő lejárta után, zárolással (két
    egyidejű döntés sem adhat két nyertest), a döntés tartós rögzítésével.
    Az eredmény-értesítők a döntés VÉGLEGESÍTÉSE után mennek ki - egy
    levélhiba nem érinti a döntést, csak újraküldhető marad."""
    ak = szolg.kivalasztas(db, ajanlatkeres_id, payload.meghivott_id)
    ak = _betolt(db, ak.id)
    szolg.eredmenyek_kikuldese(db, ak)
    return _reszlet(_betolt(db, ajanlatkeres_id))


@router.post("/{ajanlatkeres_id}/lezaras-nyertes-nelkul", response_model=AjanlatkeresReszlet)
def lezaras_nyertes_nelkul(
    ajanlatkeres_id: int,
    payload: LezarasIn,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    ak = szolg.lezaras_nyertes_nelkul(db, ajanlatkeres_id, payload.megjegyzes)
    ak = _betolt(db, ak.id)
    szolg.eredmenyek_kikuldese(db, ak)
    return _reszlet(_betolt(db, ajanlatkeres_id))


@router.post("/{ajanlatkeres_id}/visszavonas", response_model=AjanlatkeresReszlet)
def visszavonas(
    ajanlatkeres_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)),
):
    ak = szolg.visszavonas(db, ajanlatkeres_id)
    ak = _betolt(db, ak.id)
    szolg.eredmenyek_kikuldese(db, ak)
    return _reszlet(_betolt(db, ajanlatkeres_id))


# --- Publikus (személyes linkes) végpontok -----------------------------------


class PublikusAjanlat(BaseModel):
    osszeg: float
    penznem: str
    brutto: bool
    megjegyzes: str | None
    vallalja: bool
    bekuldve: str | None
    modositva: str | None
    visszavonva: bool


class PublikusValasz(BaseModel):
    projekt_nev: str
    munkakor: str
    leiras: str | None
    helyszin: str | None
    munkavegzes_idopont: str | None
    teljesitesi_hatarido: str | None
    valaszadasi_hatarido_szoveg: str
    #: Hátralévő másodpercek a SZERVER órája szerint - a kliens élő
    #: visszaszámlálója ebből indul, nem a látogató gépének órájából.
    hatralevo_mp: int
    lejart: bool
    #: lezárult-e az ajánlatkérés maga (döntés/lezárás/visszavonás történt).
    lezarult: bool
    sajat_ajanlat: PublikusAjanlat | None


class PublikusAjanlatIn(BaseModel):
    osszeg: float
    penznem: str = "HUF"
    brutto: bool = False
    megjegyzes: str | None = None
    vallalja: bool = False


def _publikus_valasz(m: AjanlatMeghivott) -> PublikusValasz:
    ak = m.ajanlatkeres
    hatralevo = 0
    if ak.valaszadasi_hatarido is not None:
        hatralevo = max(0, int((ak.valaszadasi_hatarido - szolg.most_utc()).total_seconds()))
    a = m.ajanlat
    return PublikusValasz(
        projekt_nev=ak.projekt_nev,
        munkakor=ak.munkakor,
        leiras=ak.leiras,
        helyszin=ak.helyszin,
        munkavegzes_idopont=ak.munkavegzes_idopont,
        teljesitesi_hatarido=ak.teljesitesi_hatarido,
        valaszadasi_hatarido_szoveg=szolg.budapest_szoveg(ak.valaszadasi_hatarido),
        hatralevo_mp=hatralevo,
        lejart=szolg.lejart(ak),
        lezarult=ak.allapot in ("kiosztva", "lezarva_nyertes_nelkul", "visszavonva"),
        sajat_ajanlat=(
            PublikusAjanlat(
                osszeg=float(a.osszeg),
                penznem=a.penznem,
                brutto=a.brutto,
                megjegyzes=a.megjegyzes,
                vallalja=a.vallalja,
                bekuldve=a.bekuldve.isoformat() + "Z" if a.bekuldve else None,
                modositva=a.modositva.isoformat() + "Z" if a.modositva else None,
                visszavonva=a.visszavonva is not None,
            )
            if a is not None
            else None
        ),
    )


@public_router.get("/{token}", response_model=PublikusValasz)
def publikus_adatok(token: str, db: Session = Depends(get_db)):
    """A személyes ajánlati oldal adatai. Mások nevét, ajánlatát, árát vagy a
    jelentkezők számát SZÁNDÉKOSAN nem adjuk ki - csak a saját ajánlatot."""
    return _publikus_valasz(szolg.token_alapjan(db, token))


@public_router.put("/{token}", response_model=PublikusValasz)
def publikus_bekuldes(token: str, payload: PublikusAjanlatIn, db: Session = Depends(get_db)):
    """Ajánlat beküldése/módosítása. A határidőt a SZERVER ellenőrzi: lejárat
    után egy korábban megnyitott űrlap sem adhat be ajánlatot (410)."""
    szolg.ajanlat_bekuldes(
        db,
        token,
        osszeg=payload.osszeg,
        penznem=payload.penznem,
        brutto=payload.brutto,
        megjegyzes=payload.megjegyzes,
        vallalja=payload.vallalja,
    )
    return _publikus_valasz(szolg.token_alapjan(db, token))


@public_router.delete("/{token}", response_model=PublikusValasz)
def publikus_visszavonas(token: str, db: Session = Depends(get_db)):
    szolg.ajanlat_visszavonas(db, token)
    return _publikus_valasz(szolg.token_alapjan(db, token))
