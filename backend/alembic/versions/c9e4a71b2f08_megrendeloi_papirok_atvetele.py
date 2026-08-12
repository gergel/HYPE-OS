"""A Notionból örökölt megrendelői papírok átvétele

Adatmigráció, nem sémaváltozás. A HYPE ADMIN projektkódok Notion-táblából a
megrendelői szerződések és teljesítési igazolások adatai (név, dátum, összeg)
és maguk a feltöltött papírok már be vannak importálva - de LAPOS MEZŐKBE és
általános csatolmányokba, amikből a rendszer nem tud papírt csinálni.

Ez a lépés abból készít valódi MegrendeloiSzerzodes / MegrendeloiTig
rekordokat, hogy a régi papírok is megjelenjenek a gyűjtőoldalakon, és ne
"hiányzó papírként" álljanak örökre a teendők között.

Miért migrációban? Mert így Notion-hozzáférés nélkül, a deploy pillanatában
megvan - nem kell hozzá API-kulcs, és nem kell megvárni a következő importot.
Ugyanaz a kód fut, mint az import-katalógus "Megrendelői papírok" lépésében
(lásd services/megrendeloi_papir_atvetel.py), tehát a kettő nem csúszhat el.

Idempotens: az átvett sorokat a megjegyzésük azonosítja, újrafuttatáskor azokat
frissíti. Amit a felületen kézzel készítettek, ahhoz nem nyúl.

Revision ID: c9e4a71b2f08
Revises: b7d3f1a90c24
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy.orm import Session

revision: str = "c9e4a71b2f08"
down_revision: Union[str, Sequence[str], None] = "b7d3f1a90c24"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # A modellek importja a függvényen belül: a migrációs modul betöltésekor
    # még nem biztos, hogy az alkalmazás importálható állapotban van.
    from app.services import megrendeloi_papir_atvetel

    kapcsolat = op.get_bind()
    with Session(bind=kapcsolat) as db:
        merleg = megrendeloi_papir_atvetel.vedd_at_mindent(db)
        db.flush()
    print(f"Megrendelői papírok átvéve - {merleg}")


def downgrade() -> None:
    """Csak az ÁTVETT sorokat törli - amit a felületen készítettek, marad.

    A megkülönböztetés a megjegyzésen múlik, ugyanazon a jelölőn, amivel az
    átvétel is dolgozik."""
    from app.models.megrendeloi_papir import MegrendeloiSzerzodes, MegrendeloiTig
    from app.services.megrendeloi_papir_atvetel import ATVETT_MEGJEGYZES

    kapcsolat = op.get_bind()
    with Session(bind=kapcsolat) as db:
        for modell in (MegrendeloiSzerzodes, MegrendeloiTig):
            db.query(modell).filter(modell.megjegyzes == ATVETT_MEGJEGYZES).delete(synchronize_session=False)
        db.flush()
