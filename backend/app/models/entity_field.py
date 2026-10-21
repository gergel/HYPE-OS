"""Mezők eltávolítása és saját mezők létrehozása - a Notionből áthozott
mezőkészletből sok itt már nem kell, viszont időnként kell olyan, ami ott nem
volt.

MIÉRT NEM valódi DROP COLUMN: az entitások SQLAlchemy modellként, Python
kódban vannak leírva (app/models/*.py), és minden lekérdezés a modell összes
oszlopát felsorolja. Ha egy oszlopot elejtenénk az adatbázisból, a modell
attól még hivatkozna rá, és az ADOTT ENTITÁS MINDEN lekérdezése azonnal
elszállna. Ezért a "törlés" itt azt jelenti, hogy a mező eltűnik az egész
rendszerből (részletnézet, listák, kereshetőség, szerkesztés, mezőtípusok), és
- ha a felhasználó kéri - a benne tárolt adatot is TÉNYLEGESEN kiürítjük
(UPDATE ... SET oszlop = NULL). A mező visszahozható, de az adata ilyenkor már
nincs meg.
"""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EntityFieldConfig(Base):
    """Egy MODELL-mező (valódi DB-oszlop) rendszerszintű eltávolítása. Nem
    keverendő a FieldVisibilityConfig-gal: az munkatársanként szabályozza, ki
    mit lát; ez viszont mindenkire vonatkozik - a mező többé nem része a
    rendszernek."""

    __tablename__ = "entity_field_configs"
    __table_args__ = (UniqueConstraint("entity_type", "field_name", name="uq_entity_field_config"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    hidden: Mapped[bool] = mapped_column(nullable=False, default=True)
    #: Ki és mikor távolította el - hogy egy eltűnt mezőnél utólag is
    #: kideríthető legyen, mi történt vele.
    removed_by_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())
    #: Az eltávolításkor kiürítettük-e az oszlop adatait is.
    data_wiped: Mapped[bool] = mapped_column(nullable=False, default=False)


class CustomFieldDef(Base):
    """Admin által létrehozott, saját mező egy entitástípuson. Az értékei a
    CustomFieldValue táblában vannak (nem külön oszlopban), így új mező
    felvételéhez nem kell sématmódosítás és újraindítás."""

    __tablename__ = "custom_field_defs"
    __table_args__ = (UniqueConstraint("entity_type", "field_key", name="uq_custom_field_def"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    #: Gépi kulcs (a rekord JSON-jában ezen a néven jelenik meg, tehát úgy
    #: viselkedik, mint bármelyik valódi oszlop - lásd crud_router).
    field_key: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    #: text | number | boolean | date | datetime | select
    field_type: Mapped[str] = mapped_column(String(20), nullable=False, default="text")
    #: select típusnál a választható értékek
    options: Mapped[list | None] = mapped_column(JSON)
    sort_order: Mapped[int] = mapped_column(nullable=False, default=0)
    created_by_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CustomFieldValue(Base):
    """Egy saját mező értéke EGY rekordon. Azért külön tábla (és nem oszlop),
    mert így egy új mező felvétele nem sémaváltozás - a felhasználó a
    Beállítások oldalon, futás közben hoz létre mezőt."""

    __tablename__ = "custom_field_values"
    __table_args__ = (
        UniqueConstraint("entity_type", "record_id", "field_key", name="uq_custom_field_value"),
        # A rekord adatlapjának betöltése mindig (entity_type, record_id)
        # szerint kérdez - enélkül teljes táblát olvasna minden megnyitáskor.
        Index("ix_custom_field_values_record", "entity_type", "record_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    record_id: Mapped[int] = mapped_column(nullable=False)
    field_key: Mapped[str] = mapped_column(String(100), nullable=False)
    #: Az érték nyers JSON-ként (szöveg/szám/logikai/null) - a megjelenítéshez
    #: és a beviteli mező típusához a CustomFieldDef.field_type ad támpontot.
    value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSON)
