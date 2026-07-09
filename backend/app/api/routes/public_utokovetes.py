"""Publikus (bejelentkezés nélküli) utókövető kérdőív végpontjai - a forgatás
vége után 12 órával kiküldött automatikus emailben (lásd workers/dispo_tasks.py)
küldött link erre mutat. A linket egy `utokoveto_token`-nel azonosítjuk (nem a
nyers project_id-vel), hogy a bejelentkezést nem igénylő, publikus végpont ne
legyen egyszerűen kitalálható/enumerálható - lásd Project.utokoveto_token.

A projekt neve/kódja/dátuma az űrlapon csak megjelenítésre (előtöltésre)
szolgál, nem a válaszadó tölti ki manuálisan - mivel a link már projekt-
specifikus (a tokenen keresztül), nincs értelme külön beírt projektkód-
mezőt tárolni, ami elcsúszhatna a valós projekttől egy elgépelés miatt."""

from __future__ import annotations

import os
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.post_shoot_feedback import PostShootFeedback
from app.models.project import Project
from app.schemas.post_shoot_feedback import PostShootFeedbackRead
from app.services import document_storage

router = APIRouter(prefix="/public/utokovetes", tags=["utokovetes-public"])

MAX_FILES = 10
MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024


def _get_project_or_404(db: Session, token: str) -> Project:
    project = db.query(Project).filter(Project.utokoveto_token == token).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Érvénytelen vagy lejárt link.")
    return project


class ProjectPrefill(BaseModel):
    project_nev: str | None
    projektkod: str | None
    forgatas_datuma: date | None
    forgatas_datuma_vege: date | None


@router.get("/{token}", response_model=ProjectPrefill)
def get_prefill(token: str, db: Session = Depends(get_db)):
    project = _get_project_or_404(db, token)
    return ProjectPrefill(
        project_nev=project.nev,
        projektkod=project.projektkod_szoveg,
        forgatas_datuma=project.forgatas_datuma,
        forgatas_datuma_vege=project.forgatas_datuma_vege,
    )


@router.post("/{token}", response_model=PostShootFeedbackRead, status_code=201)
async def submit_feedback(
    token: str,
    erdemleges_tortent: str | None = Form(None),
    technika_info: str | None = Form(None),
    egyeb: str | None = Form(None),
    files: list[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
):
    project = _get_project_or_404(db, token)
    if len(files) > MAX_FILES:
        raise HTTPException(status_code=400, detail=f"Legfeljebb {MAX_FILES} fájl tölthető fel.")

    feedback = PostShootFeedback(
        project_id=project.id,
        erdemleges_tortent=erdemleges_tortent or None,
        technika_info=technika_info or None,
        egyeb=egyeb or None,
    )
    db.add(feedback)
    db.flush()

    werk_fotok = []
    for index, file in enumerate(files):
        data = await file.read()
        if len(data) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=400, detail=f"A(z) „{file.filename}” fájl mérete meghaladja a 100 MB-os korlátot."
            )
        ext = os.path.splitext(file.filename or "kep.jpg")[1] or ".jpg"
        key = f"werk-fotok/{project.id}/{feedback.id}/{index}{ext}"
        url = document_storage.upload_bytes(data, key, file.content_type or "application/octet-stream")
        werk_fotok.append({"url": url, "filename": file.filename or "kep.jpg"})

    feedback.werk_fotok = werk_fotok
    db.commit()
    db.refresh(feedback)
    return feedback
