from pydantic import BaseModel


class ContactBase(BaseModel):
    full_name: str
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    phone: str | None = None


class ContactCreate(ContactBase):
    client_id: int


class ContactUpdate(BaseModel):
    full_name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    phone: str | None = None


class ContactRead(ContactBase):
    id: int
    client_id: int
    extra: dict | None = None

    model_config = {"from_attributes": True}


class ClientBase(BaseModel):
    nev: str
    adoszam: str | None = None
    szekhely: str | None = None
    nyilvantartasi_szam: str | None = None
    kepviselo: str | None = None


class ClientCreate(ClientBase):
    pass


class ClientUpdate(BaseModel):
    nev: str | None = None
    adoszam: str | None = None
    szekhely: str | None = None
    nyilvantartasi_szam: str | None = None
    kepviselo: str | None = None


class ClientRead(ClientBase):
    id: int

    model_config = {"from_attributes": True}
