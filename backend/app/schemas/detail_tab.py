from pydantic import BaseModel


class DetailTabRead(BaseModel):
    tab_key: str
    label: str
    icon: str | None = None
    field_keys: list[str] = []

    model_config = {"from_attributes": True}


class DetailTabWrite(BaseModel):
    tab_key: str
    label: str
    icon: str | None = None
    field_keys: list[str] = []


class DetailTabConfigWrite(BaseModel):
    """A teljes fül-lista egy entitástípushoz - PUT-tal az egészet felülírja
    (töröl mindent ami korábban volt, majd beszúrja az újat), hogy az admin
    felület egyszerűen az egész, szerkesztett listát visszaküldhesse egyben
    (sorrend = tömbindex), ne kelljen külön create/update/delete/reorder
    végpontokat hívogatnia."""

    tabs: list[DetailTabWrite]


class DetailTabConfigRead(BaseModel):
    entity_type: str
    tabs: list[DetailTabRead]
