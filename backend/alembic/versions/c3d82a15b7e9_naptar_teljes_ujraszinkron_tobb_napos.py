"""Egyszeri teljes naptár-újraszinkron a több napos forgatások végének pótlásához

Adatmigráció, nem sémaváltozás: a naptár-szinkron (és a Notion-import) eddig
kitörölte a több napos forgatások VÉGÉT (lásd a 76acf31 commit javításait) -
a már bent lévő projekteken viszont a vég csak akkor jönne meg újra, ha a
Google-esemény megváltozik, mert a szinkron a sync_token birtokában CSAK a
változott eseményeket kéri le (lásd models/calendar_sync.py). Egy változatlan,
több napos esemény tehát örökre csonka maradna.

A sync_token törlésével a deploy utáni ELSŐ (percenkénti) futás teljes
újraszinkront végez a szokásos időablakban (14 nap vissza, ~18 hónap előre,
lásd services/google_calendar.py FULL_SYNC_*), és minden eseményt a már
javított logikával dolgoz fel - a több napos naptár-események vége így kézi
beavatkozás nélkül visszapótlódik.

Idempotens és ártalmatlan: üres/friss adatbázison (vagy naptár-szinkron
nélkül) nincs sor, nem csinál semmit; a token törlése adatvesztés nélkül
csak egy teljes újraolvasást vált ki.

Revision ID: c3d82a15b7e9
Revises: 977891229a8d
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3d82a15b7e9"
down_revision: Union[str, Sequence[str], None] = "977891229a8d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    kapcsolat = op.get_bind()
    if sa.inspect(kapcsolat).has_table("calendar_sync_state"):
        kapcsolat.execute(sa.text("UPDATE calendar_sync_state SET sync_token = NULL"))


def downgrade() -> None:
    """Nincs visszaút: a régi sync_token nem állítható vissza (nem is kell -
    a token hiánya csak egy teljes újraszinkront vált ki, adat nem vész el)."""
