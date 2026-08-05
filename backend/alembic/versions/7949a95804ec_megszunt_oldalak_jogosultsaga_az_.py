"""megszunt oldalak jogosultsaga az utokovetesre

Az "Alvállalkozók szerződése" és a "Teljesítési igazolások" külön menüpont
megszűnt (az Utókövetés oldal a kettőt egyben kezeli), így a hozzájuk tartozó
műveletek jogosultsága is az Utókövetés oldalé lett. Akinek eddig a két régi
oldalra volt joga, az ne veszítse el a műveleteket: a régi kulcsok jogait
beolvasztjuk az "/utokovetes" kulcsba, majd a holt kulcsokat eldobjuk.

Revision ID: 7949a95804ec
Revises: 6baf94ce5eb2
Create Date: 2026-08-05 19:50:10.841861

"""
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '7949a95804ec'
down_revision: Union[str, Sequence[str], None] = '6baf94ce5eb2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

REGI_OLDALAK = ("/alvallalkozoi-szerzodesek", "/teljesitesi-igazolasok")
UJ_OLDAL = "/utokovetes"


def upgrade() -> None:
    """Upgrade schema."""
    kapcsolat = op.get_bind()
    sorok = kapcsolat.execute(
        sa.text("SELECT id, page_permissions FROM page_access_configs WHERE page_permissions IS NOT NULL")
    ).fetchall()
    for sor_id, jogok in sorok:
        if not isinstance(jogok, dict):
            continue
        if not any(regi in jogok for regi in REGI_OLDALAK):
            continue
        egyesitett = set(jogok.get(UJ_OLDAL) or [])
        for regi in REGI_OLDALAK:
            egyesitett.update(jogok.pop(regi, []) or [])
        # A kulcs puszta jelenléte adja a láthatóságot - ha valakinek volt joga
        # a régi oldalakhoz, mostantól az Utókövetést látja helyettük.
        jogok[UJ_OLDAL] = sorted(egyesitett)
        kapcsolat.execute(
            sa.text("UPDATE page_access_configs SET page_permissions = CAST(:jogok AS json) WHERE id = :id"),
            {"jogok": json.dumps(jogok), "id": sor_id},
        )


def downgrade() -> None:
    """Downgrade schema."""
    # A két régi oldal külön jogosultsága nem állítható vissza (nem tudjuk,
    # melyik jog melyikből jött), és nincs is hova: a menüpontok megszűntek.
    pass
