"""Ki vezette fel az utómunkát - a Notionból importált anyagoknál pótolva.

A felhasználó kérése: minden utómunka adatlapján látszódjon, ki hozta létre.
A Notionból importált anyagoknál a felvezető csak nyers Notion-hivatkozásként
került át (aki_felvezette_az_utomunkat_notion_ids), az összekötött munkatárs
(aki_felvezette_employee_id) üres maradt. Ez a migráció a notion_import_map
alapján kitölti - CSAK az üres mezőket, a meglévő értékhez nem nyúl. Ami nem
oldható fel (a munkatárs nincs importálva), az üres marad. A visszaállítás
nem törli a kitöltött értékeket (nem különböztethetők meg a kézzel
megadottaktól).

Revision ID: n4f5e6l7v8z9
Revises: m3k4a5r6o7s8
"""

from alembic import op

revision = "n4f5e6l7v8z9"
down_revision = "m3k4a5r6o7s8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE deliverables d
        SET aki_felvezette_employee_id = sub.entity_id
        FROM (
            SELECT DISTINCT ON (d2.id) d2.id AS deliverable_id, m.entity_id
            FROM deliverables d2
            CROSS JOIN LATERAL json_array_elements_text(
                CASE WHEN json_typeof(d2.aki_felvezette_az_utomunkat_notion_ids) = 'array'
                     THEN d2.aki_felvezette_az_utomunkat_notion_ids ELSE '[]'::json END
            )
                WITH ORDINALITY AS e(notion_id, sorrend)
            JOIN notion_import_map m
                ON m.entity_type = 'Employee'
               AND replace(m.notion_page_id, '-', '') = replace(e.notion_id, '-', '')
            JOIN employees emp ON emp.id = m.entity_id
            WHERE d2.aki_felvezette_employee_id IS NULL
            ORDER BY d2.id, e.sorrend
        ) sub
        WHERE d.id = sub.deliverable_id
        """
    )


def downgrade() -> None:
    pass
