"""Forrásonkénti forgatás-vég segéd-mezők + újabb teljes naptár-újraszinkron

A forgatas_datuma_vege körüli visszatérő adatvesztés gyökere: több folyamat
(naptár-szinkron, Notion-import, kézi szerkesztés) ugyanazt az egy mezőt
írta, és mindig az nyert, amelyik épp NEM ismerte a véget. Az új felépítésben
minden forrás a SAJÁT, kizárólagos oszlopába tükrözi, amit lát
(naptar_datum_vege / notion_datum_vege - lásd models/project.py), a
megjelenített vég pedig ezekből áll össze (schemas/project.veg_datum).
Amit egy forrás egyszer leírt, azt más folyamat - régi kódverzió sem -
írhatja felül, mert az oszlopát rajta kívül senki nem ismeri.

A sync_token törlése újra teljes naptár-újraszinkront vált ki a deploy utáni
első futásnál, hogy az új naptar_datum_vege oszlop minden meglévő eseményre
azonnal feltöltődjön (a Google amúgy csak a változott eseményeket küldené).

Revision ID: b91d64e0a7c5
Revises: e7f4c92ab1d3
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b91d64e0a7c5"
down_revision: Union[str, Sequence[str], None] = "e7f4c92ab1d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("naptar_datum_vege", sa.Date(), nullable=True, comment="A Google Naptár-esemény vége (a szinkron saját tükre - más nem írja)"),
    )
    op.add_column(
        "projects",
        sa.Column("notion_datum_vege", sa.Date(), nullable=True, comment="A Notion szerinti forgatás-vég (az import saját tükre - más nem írja)"),
    )
    # Amit a régi kód a forgatas_datuma_vege-ben mégis meghagyott, azt
    # kiindulásként átmásoljuk a naptár-tükörbe is - jobb kiindulás, mint az
    # üres oszlop, és a következő teljes újraszinkron úgyis pontosít.
    kapcsolat = op.get_bind()
    kapcsolat.execute(
        sa.text("UPDATE projects SET naptar_datum_vege = forgatas_datuma_vege WHERE forgatas_datuma_vege IS NOT NULL")
    )
    if sa.inspect(kapcsolat).has_table("calendar_sync_state"):
        kapcsolat.execute(sa.text("UPDATE calendar_sync_state SET sync_token = NULL"))


def downgrade() -> None:
    op.drop_column("projects", "notion_datum_vege")
    op.drop_column("projects", "naptar_datum_vege")
