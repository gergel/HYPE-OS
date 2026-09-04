from datetime import datetime

from pydantic import BaseModel

from app.schemas.document_attachment import DocumentAttachmentRead


class AssignableEmployee(BaseModel):
    id: int
    full_name: str


class VinyoOptions(BaseModel):
    options: list[str]
    #: Kezelheti-e a lekérő a vinyó-neveket (új/átnevezés/törlés) - admin,
    #: vagy akinek admin külön megadta (lásd models/deliverable_status.
    #: vinyo_kezelo_employee_ids).
    kezelheto: bool = False


class ContactOption(BaseModel):
    id: int
    full_name: str
    email: str | None = None


class ContactIdsPayload(BaseModel):
    contact_ids: list[int]


class CommentCreate(BaseModel):
    body: str


class CommentUpdate(BaseModel):
    """Saját hozzászólás átírása (a felhasználó kérése) - lásd
    services/deliverable_actions.edit_comment."""

    body: str


class CommentRead(BaseModel):
    id: int
    deliverable_id: int
    employee_id: int
    employee_name: str
    body: str
    created_at: datetime
    #: Mikor írták át utoljára - ebből látszik a "(szerkesztve)" jelölés.
    updated_at: datetime | None = None
    #: A hozzászóláshoz mellékelt fájlok - lásd
    #: services/attachments.py ("deliverableComment" entity_type).
    attachments: list[DocumentAttachmentRead] = []


class TimerEmployeeSummary(BaseModel):
    employee_id: int
    full_name: str
    total_minutes: float
    total_cost: float | None = None


class TimerRunningEntry(BaseModel):
    """Épp FUTÓ időmérés - névvel, hogy a felületen ne csak egy csupasz óra
    ketyegjen, hanem az is látszódjon, kinél fut."""

    employee_id: int
    full_name: str
    since: datetime
    #: A mérés indításakor RÖGZÍTETT órabér (Timesheet.akkori_orabere) - ebből
    #: számolja a felület másodpercenként a még futó mérés költségét is, hogy ne
    #: csak leállítás után derüljön ki, mennyibe kerül. Ha a felhasználó nem
    #: láthatja a forintokat, üresen megy vissza.
    orabere: float | None = None


class TimerState(BaseModel):
    my_running_since: datetime | None
    running: list[TimerRunningEntry] = []
    by_employee: list[TimerEmployeeSummary]
    total_minutes: float
    total_cost: float | None = None
    #: Munkaidő-sor azonosítója -> a sor költsége. Azért innen jön (és nem a
    #: sor `koltseg` oszlopából), mert a rögzített összeg gyakran hiányzik, és
    #: ilyenkor az időből + órabérből SZÁMOLJUK - a listának és az
    #: összesítésnek pedig ugyanazt kell mutatnia. Üres, ha a felhasználó nem
    #: láthatja a forintokat.
    sor_koltsegek: dict[int, float] = {}
