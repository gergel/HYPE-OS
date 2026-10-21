"""utomunka allapot megjelenes

Az Utómunka tábláján az állapot-oszlopok (Aktuális, Javítás, Kész,
Kiküldésre vár...) sorrendje eddig a mező választható értékeinek sorrendje
volt, szín nélkül. Ez a tábla írja le oszloponként, hogy hányadik helyen
jelenjen meg, milyen halvány színnel, és hogy az adott állapot elkészültnek
számít-e (az ilyen anyag nem kerül a lejárt határidejűek közé).

Az állapotok maguk továbbra is szabad szövegek a Deliverable.allapot mezőben -
ez csak a megjelenésüket írja le, tehát egy új állapot felvétele semmit nem
ront el: sor híján a lista végére kerül, szín nélkül.

Kezdéskor feltöltjük azokkal az állapotokkal, amik már használatban vannak, a
jelenlegi sorrendjükben; a "kész" jellegű állapotokat (kész / kiküldve /
kiküldésre vár / lezárva / leadva) elkészültnek jelöljük - épp ez a kérés
kiváltó oka: ami már kész, az ne szerepeljen lejárt határidejűként.

Revision ID: f2e95bf24fae
Revises: 34e707b55613
Create Date: 2026-08-06 11:41:25.113693

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2e95bf24fae'
down_revision: Union[str, Sequence[str], None] = '34e707b55613'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


#: Ékezet/kisbetű-független részletek, amik "elkészült" állapotra utalnak.
KESZ_MINTAK = ("kesz", "kikuld", "lezar", "leadva", "atadva", "done")


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "deliverable_status_configs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("allapot", sa.String(length=50), nullable=False),
        sa.Column("sorrend", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("szin", sa.String(length=20), nullable=True),
        sa.Column("kesz_allapot", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("allapot"),
    )

    # A már használatban lévő állapotok - a "kész" jellegűeket elkészültnek
    # jelölve. Az unaccent kiterjesztés nem feltétlenül van telepítve, ezért
    # kézzel cseréljük az ékezeteket a mintaillesztés előtt.
    minta_feltetel = " OR ".join(
        f"translate(lower(allapot), 'áéíóöőúüű', 'aeiooouuu') LIKE '%{minta}%'" for minta in KESZ_MINTAK
    )
    op.execute(
        f"""
        INSERT INTO deliverable_status_configs (allapot, sorrend, kesz_allapot)
        SELECT allapot,
               row_number() OVER (ORDER BY allapot) - 1,
               ({minta_feltetel})
        FROM (SELECT DISTINCT allapot FROM deliverables WHERE allapot IS NOT NULL AND allapot <> '') AS a
        ON CONFLICT (allapot) DO NOTHING
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("deliverable_status_configs")
