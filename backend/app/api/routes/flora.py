from datetime import datetime

from fastapi import Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.crud_router import build_crud_router
from app.core.database import get_db
from app.core.security import Role, require_page_action
from app.models.employee import Employee
from app.models.flora_feladat import FloraFeladat
from app.models.flora_komment import FloraKomment
from app.schemas.flora_feladat import FloraFeladatCreate, FloraFeladatRead, FloraFeladatUpdate
from app.services import notifications

PAGE = "/flora"

#: A durva admin/operator szerepkör-kapu itt nem érvényes: a FLÓRA táblán épp
#: a kreatív/vágó szerepkörűek dolgoznak - akinek admin jogot adott az
#: oldalra, az húzhatja a kártyákat és írhat hozzászólást (ugyanaz az elv,
#: mint az Utómunkánál, lásd routes/postproduction.py _MINDEN_SZEREPKOR).
_MINDEN_SZEREPKOR = tuple(Role)

router = build_crud_router(
    model=FloraFeladat,
    create_schema=FloraFeladatCreate,
    update_schema=FloraFeladatUpdate,
    read_schema=FloraFeladatRead,
    prefix="/flora",
    tags=["flora"],
    page=PAGE,
    write_roles=_MINDEN_SZEREPKOR,
    entity_type="floraFeladat",
)


# --- Hozzászólások -----------------------------------------------------------
# Ugyanaz a chat-szerű minta, mint az Utómunkánál és a Project Code-nál (lásd
# routes/project_codes.py) - a Notion-import a kártyák Notion-beli kommentjeit
# is ide hozza (lásd notion_import/importers_wave4.import_flora_design).


class FloraKommentCreate(BaseModel):
    body: str


class FloraKommentRead(BaseModel):
    id: int
    flora_feladat_id: int
    employee_id: int
    employee_name: str
    body: str
    created_at: datetime


def _komment_read(c: FloraKomment) -> FloraKommentRead:
    return FloraKommentRead(
        id=c.id,
        flora_feladat_id=c.flora_feladat_id,
        employee_id=c.employee_id,
        employee_name=c.employee.full_name,
        body=c.body,
        created_at=c.created_at,
    )


@router.get("/{flora_id}/comments", response_model=list[FloraKommentRead])
def get_comments(
    flora_id: int,
    db: Session = Depends(get_db),
    _user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
):
    if db.get(FloraFeladat, flora_id) is None:
        raise HTTPException(status_code=404, detail="A feladat nem található.")
    rows = db.scalars(
        select(FloraKomment).where(FloraKomment.flora_feladat_id == flora_id).order_by(FloraKomment.created_at)
    ).all()
    return [_komment_read(c) for c in rows]


@router.post("/{flora_id}/comments", response_model=FloraKommentRead, status_code=201)
def post_comment(
    flora_id: int,
    payload: FloraKommentCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)),
):
    feladat = db.get(FloraFeladat, flora_id)
    if feladat is None:
        raise HTTPException(status_code=404, detail="A feladat nem található.")
    body = payload.body.strip()
    if not body:
        raise HTTPException(status_code=400, detail="A hozzászólás nem lehet üres.")

    comment = FloraKomment(flora_feladat_id=flora_id, employee_id=current_user.id, body=body)
    db.add(comment)
    db.commit()
    db.refresh(comment)

    # @Név említésnél értesítést kap a megemlített, és a feladat felelőse is
    # értesül - ugyanaz a minta, mint az Utómunka hozzászólásainál (lásd
    # services/deliverable_actions.add_comment).
    title = feladat.megnevezes or f"FLÓRA feladat #{feladat.id}"
    mar_ertesitett: set[int] = set()
    for employee_id in notifications.extract_mentioned_employee_ids(body, db):
        notifications.create_notification(
            db,
            employee_id=employee_id,
            kind="mention",
            message=f"{current_user.full_name} megemlített egy hozzászólásban: {title}",
            link=f"/flora/{feladat.id}",
            actor_id=current_user.id,
        )
        mar_ertesitett.add(employee_id)
    if feladat.felelos_id and feladat.felelos_id not in mar_ertesitett:
        notifications.create_notification(
            db,
            employee_id=feladat.felelos_id,
            kind="comment",
            message=f"{current_user.full_name} kommentelt: {title}",
            link=f"/flora/{feladat.id}",
            actor_id=current_user.id,
        )
    db.commit()

    return _komment_read(comment)
