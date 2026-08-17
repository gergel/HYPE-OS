"""Projektek és vágások bekötése a valódi projektkódjukhoz

Eddig a projektkód két külön dolog volt: SZÖVEG a projekten/vágáson
(`projektkod_szoveg` - így érkezett a Notionból és a naptárból), és önálló
rekord a Project Code táblában. A kettő nem volt összekötve, ezért a projektkód
adatlapja nem tudta megmondani, hány forgatás és hány vágás tartozik alá.

Ez a migráció összeköti őket a kód szövege alapján, és LEOLDJA azokat, amik az
importok gyűjtőjéhez ("NAPTAR-IMPORT", "ISMERETLEN-NOTION-IMPORT") voltak
kötve: a gyűjtő nem válasz, csak egy halom. Ami oda került, az úgy néz ki,
mintha el lenne intézve - pedig épp ellenkezőleg. Amihez nincs valódi
projektkód, az maradjon kötetlen, és akkor kerüljön a helyére, amikor tényleg
megkapja a kódját. Az így üressé vált gyűjtők a projektkódok listájából is
kikerülnek (amelyikre még mutat bármi, az marad - azt előbb rendezni kell).

A logika a services/projektkod_kotes.py-ban él (ugyanaz fut a mindennapi
mentéseknél is), ezért a kettő nem csúszhat el egymástól. A tömeges menet
szándékosan CSAK a döntéshez kellő három oszlopot olvassa, és kötegelt
UPDATE-tel ír: így a lépés nem függ a modellek mai oszloplistájától (egy
később hozzáadott oszlopot a régi séma még nem ismerne), és éles méretű
adaton is másodpercek alatt lefut - a soronkénti feldolgozás percekig
tartott, amibe a deploy bele is halt.

Revision ID: b5e1a94c7d20
Revises: a3c9d1f28b45
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.orm import Session

revision: str = "b5e1a94c7d20"
down_revision: Union[str, Sequence[str], None] = "a3c9d1f28b45"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from app.services import projektkod_kotes

    # A projekt projektkódja mostantól ÜRES is lehet. Eddig kötelező volt,
    # és pontosan ezért kellett a két gyűjtő kód: kellett valami, amibe a
    # kód nélkül érkező naptár/Notion sorok beleférnek. Ha viszont lehet
    # üresen hagyni, akkor a kód nélküli forgatás egyszerűen kötetlen marad,
    # és akkor kerül a helyére, amikor tényleg megkapja a kódját.
    op.alter_column("projects", "project_code_id", existing_type=sa.Integer(), nullable=True)

    db = Session(bind=op.get_bind())
    eredmeny = projektkod_kotes.kosd_ossze_mindent(db)
    db.commit()
    print(
        "Projektkód-kötés: "
        f"{eredmeny['projekt_bekotve']} projekt és {eredmeny['vagas_bekotve']} vágás bekötve, "
        f"{eredmeny['projekt_leoldva']} projekt és {eredmeny['vagas_leoldva']} vágás leoldva a gyűjtőről, "
        f"{eredmeny['gyujto_torolve']} üressé vált gyűjtő kód törölve."
    )


def downgrade() -> None:
    """A kötést nem állítjuk vissza: az az ADAT javítása volt, nem séma-változás
    (a régi, gyűjtőbe söpört állapot nem is rekonstruálható). A NOT NULL-t sem
    tesszük vissza: a kötetlen sorok miatt el sem tudná fogadni az adatbázis."""
