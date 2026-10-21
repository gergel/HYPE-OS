"""naptar es notion duplikalt projektek osszevonasa

Ugyanaz a forgatás két forrásból is bekerülhetett (Google Naptár és Notion
"Main Database"), és a két forrásnak más az azonosítója - így sok projekt
duplán jött létre. A jövőbeli duplikációt a közös párosítási szabály
akadályozza meg (lásd services/project_matching.py); ez a migráció a MÁR
MEGLÉVŐ párokat vonja össze.

Csak biztos esetben: azonos név (kis/nagybetűtől és többszörös szóköztől
függetlenül) + azonos kezdő dátum, ahol az egyik sor a naptárból jött (van
naptáresemény-ID-je, és nincs Notion-oldala), a másik pedig a Notionból. A
naptáros sort ilyenkor is CSAK akkor dobjuk el, ha rajta a naptárból jött
adatokon kívül semmi nincs (nincs utómunkája, diszpója, szerződése, TIG-je,
portálja, stábja) - a naptáreseményt előtte átkötjük a megmaradó sorra.
Amin dolgoztak már, az érintetlen marad.

Revision ID: d2aafe7bd0bd
Revises: 7949a95804ec
Create Date: 2026-08-06 05:13:01.723761

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd2aafe7bd0bd'
down_revision: Union[str, Sequence[str], None] = '7949a95804ec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# A naptáros sor csak akkor dobható el, ha EGYIK gyerektáblában sincs sora.
FUGGO_TABLAK = (
    ("deliverables", "project_id"),
    ("callsheets", "project_id"),
    ("assignments", "project_id"),
    ("contracts", "project_id"),
    ("post_shoot_feedbacks", "project_id"),
    ("performance_certificates", "project_id"),
    ("media_items", "project_id"),
    ("folders", "project_id"),
    ("portals", "project_id"),
    ("project_crew", "project_id"),
    ("projects", "feldarabolas_szulo_id"),
)


def upgrade() -> None:
    """Upgrade schema."""
    nincs_mas_adat = " AND ".join(
        f"NOT EXISTS (SELECT 1 FROM {tabla} x WHERE x.{oszlop} = naptar.id)" for tabla, oszlop in FUGGO_TABLAK
    )
    op.execute(
        f"""
        CREATE TEMP TABLE osszevonando_projekt AS
        WITH kulcsok AS (
            SELECT p.id,
                   p.forgatas_datuma,
                   lower(regexp_replace(btrim(p.nev), '\\s+', ' ', 'g')) AS nev_kulcs,
                   p.google_calendar_event_id,
                   EXISTS (
                       SELECT 1 FROM notion_import_map m
                       WHERE m.entity_type = 'Project' AND m.entity_id = p.id
                   ) AS notionos
            FROM projects p
            WHERE p.forgatas_datuma IS NOT NULL AND btrim(coalesce(p.nev, '')) <> ''
        )
        SELECT DISTINCT ON (naptar.id)
               naptar.id AS iker_id,
               notion.id AS cel_id,
               naptar.google_calendar_event_id AS esemeny_id
        FROM kulcsok naptar
        JOIN kulcsok notion
          ON notion.nev_kulcs = naptar.nev_kulcs
         AND notion.forgatas_datuma = naptar.forgatas_datuma
         AND notion.id <> naptar.id
        WHERE naptar.google_calendar_event_id IS NOT NULL
          AND naptar.notionos = false
          AND notion.notionos = true
          AND {nincs_mas_adat}
        ORDER BY naptar.id, notion.id
        """
    )

    # A megmaradó sor üres mezőit kitöltjük a naptáros ikerből (helyszín,
    # időpontok, szín) - ezeket csak a naptár tudja.
    op.execute(
        """
        UPDATE projects cel
        SET forgatas_kezdes_ido = COALESCE(cel.forgatas_kezdes_ido, iker.forgatas_kezdes_ido),
            forgatas_veg_ido = COALESCE(cel.forgatas_veg_ido, iker.forgatas_veg_ido),
            helyszin = COALESCE(NULLIF(cel.helyszin, ''), iker.helyszin),
            description = COALESCE(NULLIF(cel.description, ''), iker.description),
            naptar_szin = COALESCE(cel.naptar_szin, iker.naptar_szin)
        FROM osszevonando_projekt o
        JOIN projects iker ON iker.id = o.iker_id
        WHERE cel.id = o.cel_id
        """
    )

    # Előbb a törlés, csak utána az esemény-ID átkötése: a
    # google_calendar_event_id EGYEDI, a két sor egy pillanatig sem lóghat
    # ugyanarra az eseményre.
    op.execute("DELETE FROM projects WHERE id IN (SELECT iker_id FROM osszevonando_projekt)")
    op.execute(
        """
        UPDATE projects cel
        SET google_calendar_event_id = o.esemeny_id
        FROM osszevonando_projekt o
        WHERE cel.id = o.cel_id AND cel.google_calendar_event_id IS NULL
        """
    )
    op.execute("DROP TABLE osszevonando_projekt")


def downgrade() -> None:
    """Downgrade schema."""
    # A beolvasztott (üres) naptár-másolatok nem állíthatók vissza - és nem is
    # kellenek: a naptár-szinkron a megmaradó projektet frissíti tovább.
    pass
