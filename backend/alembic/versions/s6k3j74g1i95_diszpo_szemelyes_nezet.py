"""Diszpótábla: személyes nézetek (saját oszlop-elrejtés és -szélesség).

A HYPE 2026 táblán az elrejtés eddig csak admin-vezérlő volt, és mindenkire
vonatkozott. A felhasználó kérése, hogy mindenki a SAJÁT képernyőjét is
rendezhesse: mely oszlopok ne látszódjanak neki, és milyen szélesek legyenek -
anélkül, hogy ezzel másét átrendezné vagy adatot törölne. Ezt tárolja az új
diszpo_nezetek tábla, munkatársanként és munkalaponként egy sorban.

Az oszlopokat a stabil diszpo_oszlopok.id azonosítja (nem az idx, amit a
beszúrás eltol).

Revision ID: s6k3j74g1i95
Revises: r5j2i63f0h84
Create Date: 2026-09-11
"""

from alembic import op
import sqlalchemy as sa

revision = "s6k3j74g1i95"
down_revision = "r5j2i63f0h84"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "diszpo_nezetek",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "employee_id",
            sa.Integer(),
            sa.ForeignKey("employees.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "munkalap_id",
            sa.Integer(),
            sa.ForeignKey("diszpo_munkalapok.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("rejtett_oszlop_idk", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("oszlop_szelessegek", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("employee_id", "munkalap_id", name="uq_diszpo_nezet"),
    )


def downgrade() -> None:
    op.drop_table("diszpo_nezetek")
