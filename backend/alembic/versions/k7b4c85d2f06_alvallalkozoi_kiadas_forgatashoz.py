"""Alvállalkozói kiadások forgatáshoz kötése visszamenőleg.

A felhasználó hibajelzése: ugyanaz a munka KÉTSZER jelent meg az
utókövetésben - egyszer a forgatás soraként (ahol a szerződés már ki is
ment), egyszer pedig "forgatás nélkül", projektkód-szintű teendőként. Az ok:
a külsős, emberhez kötött kiadás alvallalkozo_project_id mezője üresen
maradt (a kitöltő automatika csak a felvitelkor futott, a régebbi vagy
utólag módosított sorokon nem), a projektkód-szintű ág pedig pont az üres
mezős kiadásokból dolgozik.

Ez a migráció a meglévő sorokon pótolja a hozzárendelést, ugyanazzal a
szabállyal, mint a felvitelkori automatika (api/routes/finance.py
_alvallalkozo_forgatas_kitoltese): a projektkód LEGFRISSEBB forgatását kapja.

KIVÉTEL: ahol az illetőnek már készült PROJEKTKÓD-SZINTŰ szerződése vagy
TIG-je (Contract.project_code_id / PerformanceCertificate.project_code_id),
ott a kiadás marad forgatás nélkül - a hozzárendelés eltüntetné a kész
papírokat a listáról, és a forgatás-ágon újra kérné őket.

Revision ID: k7b4c85d2f06
Revises: j6a3b74c1e95
Create Date: 2026-09-07
"""

import sqlalchemy as sa
from alembic import op

revision = "k7b4c85d2f06"
down_revision = "j6a3b74c1e95"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE expenses e
            SET alvallalkozo_project_id = (
                SELECT p.id FROM projects p
                WHERE p.project_code_id = e.project_code_id
                ORDER BY p.forgatas_datuma DESC NULLS LAST, p.id DESC
                LIMIT 1
            )
            WHERE e.alvallalkozo_project_id IS NULL
              AND e.employee_id IS NOT NULL
              AND e.project_code_id IS NOT NULL
              AND lower(trim(e.tipus)) = 'kulsos'
              AND EXISTS (
                  SELECT 1 FROM projects p WHERE p.project_code_id = e.project_code_id
              )
              AND NOT EXISTS (
                  SELECT 1 FROM contracts c
                  WHERE c.project_code_id = e.project_code_id AND c.employee_id = e.employee_id
              )
              AND NOT EXISTS (
                  SELECT 1 FROM performance_certificates pc
                  WHERE pc.project_code_id = e.project_code_id AND pc.employee_id = e.employee_id
              )
            """
        )
    )


def downgrade() -> None:
    # Adat-pótlás - nem állítjuk vissza az üres mezőket: nem tudni, melyik
    # sor volt eredetileg üres.
    pass
