from datetime import datetime

from fastapi import Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.crud_router import build_crud_router
from app.core.database import get_db
from app.core.security import Role, require_page_action
from app.models.employee import Employee
from app.models.hype_todo import HypeTodoItem
from app.models.hype_todo_komment import HypeTodoKomment
from app.schemas.hype_todo import HypeTodoCreate, HypeTodoRead, HypeTodoUpdate
from app.services import notifications

PAGE = "/hype-todo-lista"

#: A durva admin/operator szerepkör-kapu itt nem érvényes: akinek admin jogot
#: adott a HYPE TO-DO oldalra, az a szerepkörétől függetlenül dolgozhat rajta
#: (ugyanaz az elv, mint az Utómunkánál - lásd routes/postproduction.py).
_MINDEN_SZEREPKOR = tuple(Role)

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
    page=PAGE,
    write_roles=_MINDEN_SZEREPKOR,
    before_create=_felvezeto_beallitasa,
    before_update=_ellenorzo_rogzitese,
    m2m_fields={"felelos_employee_ids": ("felelosok", Employee)},
    entity_type="hypeTodo",
)


# --- Hozzászólások -----------------------------------------------------------
# Ugyanaz a chat-szerű minta, mint az Utómunkánál és a FLÓRA táblánál (lásd
# routes/flora.py) - a Notion-import a feladatok Notion-beli kommentjeit is
# ide hozza (lásd notion_import/importers_wave4.import_hype_todo).


class TodoKommentCreate(BaseModel):
    body: str


class TodoKommentRead(BaseModel):
    id: int
    hype_todo_id: int
    employee_id: int
    employee_name: str
    body: str
    created_at: datetime


def _komment_read(c: HypeTodoKomment) -> TodoKommentRead:
    return TodoKommentRead(
        id=c.id,
        hype_todo_id=c.hype_todo_id,
        employee_id=c.employee_id,
        employee_name=c.employee.full_name,
        body=c.body,
        created_at=c.created_at,
    )


@router.get("/{todo_id}/comments", response_model=list[TodoKommentRead])
def get_comments(
    todo_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
):
    if db.get(HypeTodoItem, todo_id) is None:
        raise HTTPException(status_code=404, detail="A feladat nem található.")
    rows = db.scalars(
        select(HypeTodoKomment).where(HypeTodoKomment.hype_todo_id == todo_id).order_by(HypeTodoKomment.created_at)
    ).all()
    return [_komment_read(c) for c in rows]


@router.post("/{todo_id}/comments", response_model=TodoKommentRead, status_code=201)
def post_comment(
    todo_id: int,
    payload: TodoKommentCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
):
    feladat = db.get(HypeTodoItem, todo_id)
    if feladat is None:
        raise HTTPException(status_code=404, detail="A feladat nem található.")
    body = payload.body.strip()
    if not body:
        raise HTTPException(status_code=400, detail="A hozzászólás nem lehet üres.")

    comment = HypeTodoKomment(hype_todo_id=todo_id, employee_id=current_user.id, body=body)
    db.add(comment)
    db.commit()
    db.refresh(comment)

    # @Név említésnél értesítést kap a megemlített, és a feladat FELELŐSEI is
    # értesülnek - ugyanaz a minta, mint az Utómunka hozzászólásainál.
    title = feladat.feladat or f"Feladat #{feladat.id}"
    mar_ertesitett: set[int] = set()
    for employee_id in notifications.extract_mentioned_employee_ids(body, db):
        notifications.create_notification(
            db,
            employee_id=employee_id,
            kind="mention",
            message=f"{current_user.full_name} megemlített egy hozzászólásban: {title}",
            link=f"/hype-todo-lista/{feladat.id}",
            actor_id=current_user.id,
        )
        mar_ertesitett.add(employee_id)
    for felelos in feladat.felelosok:
        if felelos.id in mar_ertesitett:
            continue
        notifications.create_notification(
            db,
            employee_id=felelos.id,
            kind="comment",
            message=f"{current_user.full_name} kommentelt: {title}",
            link=f"/hype-todo-lista/{feladat.id}",
            actor_id=current_user.id,
        )
        mar_ertesitett.add(felelos.id)
    db.commit()

    return _komment_read(comment)
