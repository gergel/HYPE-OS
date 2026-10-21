from datetime import datetime

from pydantic import BaseModel


class ArajanlatBase(BaseModel):
    nev: str
    sablon: bool = False
    #: "hype" | "contentbee" - lásd models/arajanlat.py.
    brand: str = "hype"
    ugyfel: str | None = None
    vegosszeg: float | None = None
    #: A teljes szerkesztő-állapot egyben - lásd models/arajanlat.Arajanlat.adat.
    adat: dict = {}


class ArajanlatCreate(ArajanlatBase):
    pass


class ArajanlatUpdate(ArajanlatBase):
    pass


class ArajanlatRead(ArajanlatBase):
    id: int
    #: A lista "utoljára módosítva" oszlopa.
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ArajanlatListItem(BaseModel):
    """A lista-nézet a tartalom NÉLKÜL: a JSON az ajánlatokkal együtt nő, és a
    listának csak a fejléc-adatok kellenek."""

    id: int
    nev: str
    sablon: bool
    brand: str
    ugyfel: str | None = None
    vegosszeg: float | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ArajanlatTetelBase(BaseModel):
    nev: str
    megjegyzes: str | None = None
    szekcio: str | None = None
    egysegar: float | None = None
    sorrend: int = 0


class ArajanlatTetelCreate(ArajanlatTetelBase):
    pass


class ArajanlatTetelUpdate(ArajanlatTetelBase):
    pass


class ArajanlatTetelRead(ArajanlatTetelBase):
    id: int

    model_config = {"from_attributes": True}
