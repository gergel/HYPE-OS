from pydantic import BaseModel

from app.models.employee import SystemRole


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    full_name: str
    email: str | None
    role: SystemRole
    #: További szerepkörök az elsődlegesen felül - a felület ezek alapján is
    #: dönt a gombok megjelenítéséről (lásd frontend lib/permissions.ts).
    tovabbi_szerepkorok: list[str] | None = None
    #: Aktív-e a fiók. Enélkül a "Fiókom" kártya állapotjelzője MINDENKINÉL
    #: "Inaktív"-ot mutatott (a mező hiányzott a válaszból, tehát a felületen
    #: undefined lett) - lásd frontend components/AccountCard.tsx.
    is_active: bool = True
    #: A felület témája ehhez az emberhez ("sotet" / "vilagos"). None = még nem
    #: választott, olyankor a sötét alap érvényes.
    tema: str | None = None
    #: VÉDETT RENDSZERGAZDA-e (lásd core/security.vedett_rendszergazda). A
    #: felület ebből tudja, hogy ennek a fióknak minden gombot mutasson, és
    #: hogy a saját sorát ne engedje inaktívra/korlátozásra állítani.
    vedett_admin: bool = False

    model_config = {"from_attributes": True}


#: A választható témák. Szűk, zárt lista: a `data-theme` attribútumba kerül,
#: tehát ide csak olyan érték juthat be, amire van CSS (lásd
#: frontend/app/globals.css).
TEMAK: tuple[str, ...] = ("sotet", "vilagos")


class TemaIn(BaseModel):
    tema: str
