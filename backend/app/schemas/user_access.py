from pydantic import BaseModel

PagePermissions = dict[str, list[str]]


class PageAccessRead(BaseModel):
    employee_id: int
    page_permissions: PagePermissions | None = None
    #: Csak ezeket az utómunka-anyagokat láthatja (None = mindet).
    lathato_deliverable_idk: list[int] | None = None

    model_config = {"from_attributes": True}


class PageAccessUpdate(BaseModel):
    page_permissions: PagePermissions | None = None
    lathato_deliverable_idk: list[int] | None = None


class MyAccess(BaseModel):
    """allowed_pages: a page_permissions kulcsai (visszafelé kompatibilis a
    middleware-rel/Sidebar-ral, amik csak azt nézik, mely oldalak láthatók).
    page_permissions: a teljes, oldalankénti művelet-lista (view mindig
    implicit egy szereplő kulcsnál - a frontend ez alapján tiltja le pl. a
    Törlés/Szerkesztés gombokat olyan oldalakon, ahol nincs rá jogosultság)."""

    allowed_pages: list[str] | None = None
    page_permissions: PagePermissions | None = None
    #: Ha ki van töltve, a felhasználó CSAK ezeket az utómunka-anyagokat
    #: láthatja (külsős vágó fiókja) - a felület ebből tudja, hogy a
    #: listák/menük helyett egyenesen az anyagra vigye.
    lathato_deliverable_idk: list[int] | None = None
