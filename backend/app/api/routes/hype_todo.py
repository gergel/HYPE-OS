from sqlalchemy.orm import Session

from app.api.crud_router import build_crud_router
from app.models.employee import Employee
from app.models.hype_todo import HypeTodoItem
from app.schemas.hype_todo import HypeTodoCreate, HypeTodoRead, HypeTodoUpdate

#: Ezekbe az állapotokba lépéskor rögzítjük, KI tette oda a feladatot (lásd
#: _ellenorzo_rogzitese) - az értékkészlet a Notion szerinti Állapot lista
#: (lásd services/entity_registry.SELECT_FIELD_OVERRIDES["hypeTodo"]).
ELLENORZOTT_ALLAPOTOK = ("Ellenőrzés", "Done")


def _felvezeto_beallitasa(data: dict, _db: Session, current_user: Employee) -> dict:
    """Aki a feladatot felveszi, az az "Aki felvezette" - automatikusan a
    bejelentkezett ember (a felhasználó kérése: ezt ne kelljen kézzel
    kitölteni). A Notion-importból jövő soroknál az importer tölti ki (lásd
    notion_import/importers_wave4.import_hype_todo), ez csak a felületen
    létrehozott sorokra vonatkozik - és csak akkor ír, ha üres."""
    if not data.get("aki_felvezette_id"):
        data["aki_felvezette_id"] = current_user.id
    # Ha valaki rögtön Ellenőrzés/Done állapottal veszi fel, az ő nevére megy
    # a "készbe rakta" is - ugyanaz a szabály, mint állapot-váltásnál.
    if data.get("allapot") in ELLENORZOTT_ALLAPOTOK and not data.get("aki_ellenorizte_id"):
        data["aki_ellenorizte_id"] = current_user.id
    return data


def _ellenorzo_rogzitese(obj: HypeTodoItem, data: dict, _db: Session, current_user: Employee) -> None:
    """Aki a feladatot Ellenőrzés/Done állapotba TESZI, az kerül az "Aki
    ellenőrizte/készbe rakta" mezőbe - automatikusan, minden ilyen
    állapot-váltásnál (mindig az utolsó ilyen művelet gazdája látszik). Csak a
    tényleges VÁLTÁS számít: egy változatlan állapotot is elküldő "mentsük az
    egész űrlapot" jellegű PATCH nem írja át."""
    uj = data.get("allapot")
    if uj in ELLENORZOTT_ALLAPOTOK and uj != obj.allapot:
        data["aki_ellenorizte_id"] = current_user.id


router = build_crud_router(
    model=HypeTodoItem,
    create_schema=HypeTodoCreate,
    update_schema=HypeTodoUpdate,
    read_schema=HypeTodoRead,
    prefix="/hype-todo",
    tags=["hype-todo"],
    page="/hype-todo-lista",
    before_create=_felvezeto_beallitasa,
    before_update=_ellenorzo_rogzitese,
    m2m_fields={"felelos_employee_ids": ("felelosok", Employee)},
    entity_type="hypeTodo",
)
