"""Háttérfeladat-állapot tábla + hiányzó indexek a gyakran szűrt oszlopokra.

- hatter_feladatok: a Notion import és a diszpó sheet-szinkron "fut-e már?"
  zárja és naplója - adatbázisban, mert több uvicorn worker fut, és a
  memóriabeli állapotot csak egy worker látná (lásd
  services/hatter_feladat.py).
- Indexek: a realtime változás-figyelő (routes/realtime.py) és a
  hozzászólás-listák másodpercenként szűrnek ezekre az oszlopokra, de a
  Postgres a FK-oszlopokat nem indexeli magától - eddig minden ilyen
  lekérdezés a teljes táblát olvasta végig.

Revision ID: d4b7e29c8f16
Revises: c8e4f61a9d25
Create Date: 2026-08-31
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "d4b7e29c8f16"
down_revision = "c8e4f61a9d25"
branch_labels = None
depends_on = None

INDEXEK = (
    ("ix_notifications_employee_id", "notifications", "employee_id"),
    ("ix_deliverable_comments_deliverable_id", "deliverable_comments", "deliverable_id"),
    ("ix_project_code_comments_project_code_id", "project_code_comments", "project_code_id"),
    ("ix_flora_kommentek_flora_feladat_id", "flora_kommentek", "flora_feladat_id"),
    ("ix_hype_todo_kommentek_hype_todo_id", "hype_todo_kommentek", "hype_todo_id"),
    ("ix_assignments_project_id", "assignments", "project_id"),
    ("ix_callsheets_project_id", "callsheets", "project_id"),
)


def upgrade() -> None:
    op.create_table(
        "hatter_feladatok",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nev", sa.String(length=100), nullable=False, unique=True, index=True),
        sa.Column("running", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("log", sa.Text(), nullable=False, server_default=""),
        sa.Column("reszletek", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    for nev, tabla, oszlop in INDEXEK:
        op.create_index(nev, tabla, [oszlop], if_not_exists=True)


def downgrade() -> None:
    for nev, tabla, _oszlop in INDEXEK:
        op.drop_index(nev, table_name=tabla, if_exists=True)
    op.drop_table("hatter_feladatok")
