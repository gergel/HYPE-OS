"""belsos tig notion mezok es havi tetel forras

A Notionban vezetett Belsős TIG nyilvántartásból két dátum eddig nem fért be a
sémánkba (a számla fizetési határideje és az utalás napja), a Notionból átemelt
számlának pedig nem volt forrás-azonosítója, amivel egy újrafuttatott import
felismerhetné, hogy azt a fájlt már áthozta. A havi tétel is kap egy saját
Notion-azonosítót és egy hivatkozást a vele azonos pénzügyi kiadás-sorra.

Revision ID: 8445b2b6a200
Revises: 97ad387144b1
Create Date: 2026-08-05 08:23:27.419392

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8445b2b6a200'
down_revision: Union[str, Sequence[str], None] = '97ad387144b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "internal_performance_certificates",
        sa.Column("fizetesi_hatarido", sa.Date(), nullable=True, comment="A számla fizetési határideje"),
    )
    op.add_column(
        "internal_performance_certificates",
        sa.Column("utalas_datuma", sa.Date(), nullable=True, comment="Mikor utaltuk el ténylegesen"),
    )

    op.add_column(
        "internal_performance_certificate_invoices",
        sa.Column("notion_forras", sa.String(length=700), nullable=True),
    )
    op.create_index(
        "ix_internal_performance_certificate_invoices_notion_forras",
        "internal_performance_certificate_invoices",
        ["notion_forras"],
    )

    op.add_column("employee_monthly_items", sa.Column("notion_page_id", sa.String(length=64), nullable=True))
    op.create_index(
        "ix_employee_monthly_items_notion_page_id",
        "employee_monthly_items",
        ["notion_page_id"],
        unique=True,
    )
    op.add_column("employee_monthly_items", sa.Column("expense_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_employee_monthly_items_expense_id",
        "employee_monthly_items",
        "expenses",
        ["expense_id"],
        ["id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("fk_employee_monthly_items_expense_id", "employee_monthly_items", type_="foreignkey")
    op.drop_column("employee_monthly_items", "expense_id")
    op.drop_index("ix_employee_monthly_items_notion_page_id", table_name="employee_monthly_items")
    op.drop_column("employee_monthly_items", "notion_page_id")

    op.drop_index(
        "ix_internal_performance_certificate_invoices_notion_forras",
        table_name="internal_performance_certificate_invoices",
    )
    op.drop_column("internal_performance_certificate_invoices", "notion_forras")

    op.drop_column("internal_performance_certificates", "utalas_datuma")
    op.drop_column("internal_performance_certificates", "fizetesi_hatarido")
