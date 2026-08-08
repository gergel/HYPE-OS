"""Megrendelői kontaktok - kikkel tartjuk a kapcsolatot az ügyfél oldalán, és
kiknek megy majd a kész anyag.

A kontaktok maguk a Notion "Megrendelői kontaktok" táblájából jönnek (lásd
notion_import/importers.py), és a rendszerben eddig is léteztek - csak az
ügyfél adatlapjába zárva. Ez a végpont adja hozzá azt a két dolgot, ami egy
önálló oldalhoz kell:

1. EGY LISTA az összes kontaktról, az ügyfele nevével együtt - enélkül nem
   lehet rákeresni valakire anélkül, hogy tudnánk, melyik cégnél van;
2. a KAPCSOLAT AZ UTÓMUNKÁVAL: hány kész anyagnál van beállítva, hogy neki is
   ki kell küldeni. Ez teszi láthatóvá, kinek megy ténylegesen anyag.

A felvitel/módosítás/törlés SZÁNDÉKOSAN nem itt van, hanem a meglévő
/contacts CRUD végponton (routes/clients.py) - ugyanaz az adat, egy helyen
kezelve. Az oldal jogosultsága is közös az Ügyfelekével."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.client import Client, Contact
from app.models.deliverable import deliverable_contacts
from app.models.employee import Employee

router = APIRouter(prefix="/megrendeloi-kontaktok", tags=["clients"])

#: Az oldal a Ügyfelek jogosultságát használja: ugyanaz az adat, csak másik nézet.
PAGE = "/ugyfelek"


class KontaktRead(BaseModel):
    id: int
    full_name: str
    email: str | None = None
    phone: str | None = None
    client_id: int
    client_nev: str | None = None
    #: Hány utómunka-anyagnál van beállítva, hogy neki is ki kell küldeni.
    anyagok_szama: int = 0


@router.get("", response_model=list[KontaktRead])
def list_kontaktok(db: Session = Depends(get_db), _user: Employee = Depends(get_current_user)):
    """Az összes megrendelői kontakt, ügyfélnév szerint rendezve.

    Egy lekérdezés adja a kontaktot, az ügyfele nevét és azt is, hány anyaghoz
    van hozzárendelve - enélkül kontaktonként külön kérdés menne az anyagokra
    (több száz kontaktnál ez a lista megnyitását tenné használhatatlanná)."""
    anyagok = (
        select(
            deliverable_contacts.c.contact_id.label("contact_id"),
            func.count().label("darab"),
        )
        .group_by(deliverable_contacts.c.contact_id)
        .subquery()
    )
    sorok = db.execute(
        select(Contact, Client.nev, func.coalesce(anyagok.c.darab, 0))
        .join(Client, Contact.client_id == Client.id, isouter=True)
        .join(anyagok, anyagok.c.contact_id == Contact.id, isouter=True)
        .order_by(Client.nev, Contact.full_name)
    ).all()
    return [
        KontaktRead(
            id=kontakt.id,
            full_name=kontakt.full_name,
            email=kontakt.email,
            phone=kontakt.phone,
            client_id=kontakt.client_id,
            client_nev=client_nev,
            anyagok_szama=int(darab or 0),
        )
        for kontakt, client_nev, darab in sorok
    ]
