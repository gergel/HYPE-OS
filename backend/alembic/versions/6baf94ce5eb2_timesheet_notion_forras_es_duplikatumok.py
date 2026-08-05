"""timesheet notion forras es duplikatumok

A HYPE Notionban ugyanaz a mérés a 'Timesheet Public' ÉS a 'Timesheet Private'
táblában is szerepelhet (egy szinkron-worker tartotta párban őket, lásd
docs/hype_os_migration_map.md 5. pont). Az import mindkét táblát behozta, így
egy-egy anyagon kétszer annyi munkaidő (és költség) jött ki, mint Notionban.

Ez a migráció felveszi a forrás-jelölést (public/private), kitölti a már
importált sorokon, és törli a megkettőzött méréseket - a Public sort tartva
meg, mert az utómunka leállítási ideje is onnan jön.

Revision ID: 6baf94ce5eb2
Revises: 49c37444b7f4
Create Date: 2026-08-05 15:53:09.389212

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6baf94ce5eb2'
down_revision: Union[str, Sequence[str], None] = '49c37444b7f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("timesheets", sa.Column("notion_forras", sa.String(length=20), nullable=True))

    # A privát sorok ismertetőjele: LÉTEZIK rajtuk a "Timesheet Public"
    # relation mező (a másik táblára mutat). Az importnál a nem létező mező
    # NULL-t ad, az üres relation viszont üres tömböt - tehát a NULL a public
    # tábla, minden tömb (üres is) a private tábla sora.
    op.execute(
        """
        UPDATE timesheets t
        SET notion_forras = CASE
            WHEN t.timesheet_public_notion_ids IS NOT NULL THEN 'private' ELSE 'public' END
        WHERE EXISTS (
            SELECT 1 FROM notion_import_map m
            WHERE m.entity_type = 'Timesheet' AND m.entity_id = t.id
        )
        """
    )

    # 1. Biztos párosítás: a privát sor relationje pont egy importált public
    #    sorra mutat -> ugyanaz a mérés.
    #
    # A JSON mező nem garantáltan tömb: éles adatban skalár (egyetlen string)
    # is előfordul, amin a jsonb_array_elements_text hibára fut ("cannot
    # extract elements from a scalar"). Ezért típus szerint normalizáljuk:
    # tömb marad tömb, skalárból egyelemű tömb lesz, minden más üres.
    op.execute(
        """
        CREATE TEMP TABLE torlendo_timesheet AS
        WITH parok AS (
            SELECT t.id,
                   CASE jsonb_typeof(to_jsonb(t.timesheet_public_notion_ids))
                       WHEN 'array' THEN to_jsonb(t.timesheet_public_notion_ids)
                       WHEN 'string' THEN jsonb_build_array(to_jsonb(t.timesheet_public_notion_ids))
                       ELSE '[]'::jsonb
                   END AS page_idk
            FROM timesheets t
            WHERE t.notion_forras = 'private'
        )
        SELECT DISTINCT parok.id
        FROM parok
        JOIN LATERAL jsonb_array_elements_text(parok.page_idk) AS par(page_id) ON TRUE
        JOIN notion_import_map m
          ON m.entity_type = 'Timesheet' AND m.notion_page_id = par.page_id
        JOIN timesheets p ON p.id = m.entity_id AND p.notion_forras = 'public'
        """
    )

    # 2. Ahol a relation üres maradt (a Notion névalapú párosítása gyakran
    #    szakadt): ugyanaz az ember, ugyanaz az anyag, ugyanaz a kezdő PERC -
    #    két mérés nem indulhat ugyanabban a percben ugyanarra.
    op.execute(
        """
        INSERT INTO torlendo_timesheet (id)
        SELECT DISTINCT t.id
        FROM timesheets t
        JOIN timesheets p
          ON p.notion_forras = 'public'
         AND p.employee_id = t.employee_id
         AND p.deliverable_id IS NOT DISTINCT FROM t.deliverable_id
         AND date_trunc('minute', p.start_date) = date_trunc('minute', t.start_date)
        WHERE t.notion_forras = 'private'
          AND t.start_date IS NOT NULL
          AND t.id NOT IN (SELECT id FROM torlendo_timesheet)
        """
    )

    op.execute(
        """
        DELETE FROM notion_import_map m
        WHERE m.entity_type = 'Timesheet'
          AND m.entity_id IN (SELECT id FROM torlendo_timesheet)
        """
    )
    op.execute("DELETE FROM timesheets WHERE id IN (SELECT id FROM torlendo_timesheet)")
    op.execute("DROP TABLE torlendo_timesheet")


def downgrade() -> None:
    """Downgrade schema."""
    # A törölt duplikátumok nem állíthatók vissza (és nem is kellenek): egy
    # újrafuttatott import a Notionból amúgy is a helyes, egyszeres állapotot
    # hozza. Csak az oszlopot vesszük vissza.
    op.drop_column("timesheets", "notion_forras")
