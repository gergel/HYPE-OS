"""Szamlazo fel: vallalkozas, projekt-szamlazo, TIG tetelek

A "ki számláz kiért" fogalom bevezetése:

- vallalkozasok / vallalkozas_tagok: a számlázó cég és a hozzá tartozó emberek;
- contracts.vallalkozas_id: keretszerződés (és eseti szerződés) köthető céggel;
- project_szamlazok: egy projekten egy stábtag munkájáért más is számlázhat;
- performance_certificate_tetelek: egy TIG több ember / több projekt munkáját
  is igazolhatja (a meglévő TIG-ek egytételesként töltődnek fel).

Revision ID: 7b2196c6e985
Revises: 1f535034bcb3
Create Date: 2026-08-07 21:36:45.217187

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7b2196c6e985'
down_revision: Union[str, Sequence[str], None] = '1f535034bcb3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('vallalkozasok',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('nev', sa.String(length=255), nullable=False),
    sa.Column('szekhely', sa.String(length=500), nullable=True),
    sa.Column('adoszam', sa.String(length=50), nullable=True),
    sa.Column('kepviselo', sa.String(length=255), nullable=True),
    sa.Column('nyilvantartasi_szam', sa.String(length=100), nullable=True),
    sa.Column('email', sa.String(length=255), nullable=True),
    sa.Column('megbizas_targya', sa.String(length=255), nullable=True),
    sa.Column('plusz_afa', sa.Boolean(), nullable=True),
    sa.Column('megjegyzes', sa.Text(), nullable=True),
    sa.Column('aktiv', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_vallalkozasok_adoszam'), 'vallalkozasok', ['adoszam'], unique=False)
    op.create_table('project_szamlazok',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=False),
    sa.Column('employee_id', sa.Integer(), nullable=False),
    sa.Column('szamlazo_employee_id', sa.Integer(), nullable=True),
    sa.Column('szamlazo_vallalkozas_id', sa.Integer(), nullable=True),
    sa.Column('megjegyzes', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['szamlazo_employee_id'], ['employees.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['szamlazo_vallalkozas_id'], ['vallalkozasok.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('project_id', 'employee_id', name='uq_project_szamlazo')
    )
    op.create_index(op.f('ix_project_szamlazok_employee_id'), 'project_szamlazok', ['employee_id'], unique=False)
    op.create_index(op.f('ix_project_szamlazok_project_id'), 'project_szamlazok', ['project_id'], unique=False)
    op.create_table('vallalkozas_tagok',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('vallalkozas_id', sa.Integer(), nullable=False),
    sa.Column('employee_id', sa.Integer(), nullable=False),
    sa.Column('kezdet', sa.Date(), nullable=True),
    sa.Column('veg', sa.Date(), nullable=True),
    sa.Column('megjegyzes', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['vallalkozas_id'], ['vallalkozasok.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('vallalkozas_id', 'employee_id', name='uq_vallalkozas_tag')
    )
    op.create_index(op.f('ix_vallalkozas_tagok_employee_id'), 'vallalkozas_tagok', ['employee_id'], unique=False)
    op.create_index(op.f('ix_vallalkozas_tagok_vallalkozas_id'), 'vallalkozas_tagok', ['vallalkozas_id'], unique=False)
    op.create_table('performance_certificate_tetelek',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('certificate_id', sa.Integer(), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=False),
    sa.Column('employee_id', sa.Integer(), nullable=False),
    sa.Column('netto_osszeg', sa.Numeric(precision=12, scale=2), nullable=True, comment='Ebből ennyi az övé - ha tudható'),
    sa.Column('megnevezes', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['certificate_id'], ['performance_certificates.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('certificate_id', 'project_id', 'employee_id', name='uq_tig_tetel')
    )
    op.create_index(op.f('ix_performance_certificate_tetelek_certificate_id'), 'performance_certificate_tetelek', ['certificate_id'], unique=False)
    op.create_index(op.f('ix_performance_certificate_tetelek_employee_id'), 'performance_certificate_tetelek', ['employee_id'], unique=False)
    op.create_index(op.f('ix_performance_certificate_tetelek_project_id'), 'performance_certificate_tetelek', ['project_id'], unique=False)

    op.add_column('contracts', sa.Column('vallalkozas_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_contracts_vallalkozas', 'contracts', 'vallalkozasok', ['vallalkozas_id'], ['id'])

    op.add_column('performance_certificates', sa.Column('vallalkozas_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_performance_certificates_vallalkozas', 'performance_certificates', 'vallalkozasok', ['vallalkozas_id'], ['id']
    )
    # A TIG mostantól szólhat CÉG nevére is - ilyenkor nincs mögötte ember.
    op.alter_column('performance_certificates', 'employee_id', existing_type=sa.INTEGER(), nullable=True)

    _backfill_tetelek()
    _seed_vallalkozasok()


def _backfill_tetelek() -> None:
    """Minden meglévő TIG egytételes lesz: pontosan azt fedi, amiről eddig is
    szólt (a saját projektje + a saját embere). Enélkül a tételek szerint
    számoló utókövetés az összes régi TIG-et "hiányzónak" látná."""
    op.execute(
        sa.text(
            """
            INSERT INTO performance_certificate_tetelek
                (certificate_id, project_id, employee_id, netto_osszeg, megnevezes)
            SELECT id, project_id, employee_id, netto_osszeg, megbizas_targya
            FROM performance_certificates
            WHERE employee_id IS NOT NULL
            """
        )
    )


def _seed_vallalkozasok() -> None:
    """Kezdő céglista azokból az adószámokból, amiken TÖBB ember osztozik.

    Csak ezeket vesszük fel: ha egy adószám egyetlen emberhez tartozik, az az
    ő saját (egyszemélyes) vállalkozása - abból cég-entitást csinálni több
    száz felesleges sort jelentene. A több emberes adószám viszont pontosan az
    az eset, amiért ez a tábla készült: egy cég küld több embert.

    A lista innentől kézzel szerkeszthető - ez csak indulóállapot."""
    kapcsolat = op.get_bind()
    sorok = kapcsolat.execute(
        sa.text(
            """
            SELECT regexp_replace(vallalkozas_adoszama, '[^0-9]', '', 'g') AS kulcs,
                   id, full_name, vallakozas_neve, vallakozas_szekhely,
                   vallalkozas_adoszama, vallalkozas_kepviselo, nyilvantartasi_szam, email
            FROM employees
            WHERE vallalkozas_adoszama IS NOT NULL
              AND regexp_replace(vallalkozas_adoszama, '[^0-9]', '', 'g') <> ''
            ORDER BY id
            """
        )
    ).mappings().all()

    csoportok: dict[str, list[dict]] = {}
    for sor in sorok:
        csoportok.setdefault(sor["kulcs"], []).append(dict(sor))

    for tagok in csoportok.values():
        if len(tagok) < 2:
            continue
        elso = next((t for t in tagok if (t["vallakozas_neve"] or "").strip()), tagok[0])
        nev = (elso["vallakozas_neve"] or "").strip() or f"Adószám {elso['vallalkozas_adoszama']}"
        vallalkozas_id = kapcsolat.execute(
            sa.text(
                """
                INSERT INTO vallalkozasok (nev, szekhely, adoszam, kepviselo, nyilvantartasi_szam, aktiv)
                VALUES (:nev, :szekhely, :adoszam, :kepviselo, :nyilvszam, TRUE)
                RETURNING id
                """
            ),
            {
                "nev": nev[:255],
                "szekhely": elso["vallakozas_szekhely"],
                "adoszam": elso["vallalkozas_adoszama"],
                "kepviselo": elso["vallalkozas_kepviselo"],
                "nyilvszam": elso["nyilvantartasi_szam"],
            },
        ).scalar_one()
        for tag in tagok:
            kapcsolat.execute(
                sa.text(
                    "INSERT INTO vallalkozas_tagok (vallalkozas_id, employee_id) VALUES (:v, :e)"
                ),
                {"v": vallalkozas_id, "e": tag["id"]},
            )


def downgrade() -> None:
    """Downgrade schema."""
    # A cég nevére szóló TIG-eknek nincs hova visszamenniük: a NOT NULL
    # visszaállítása előtt törölni kell őket, különben a migráció elszáll.
    op.execute("DELETE FROM performance_certificates WHERE employee_id IS NULL")
    op.alter_column('performance_certificates', 'employee_id', existing_type=sa.INTEGER(), nullable=False)
    op.drop_constraint('fk_performance_certificates_vallalkozas', 'performance_certificates', type_='foreignkey')
    op.drop_column('performance_certificates', 'vallalkozas_id')

    op.drop_constraint('fk_contracts_vallalkozas', 'contracts', type_='foreignkey')
    op.drop_column('contracts', 'vallalkozas_id')

    op.drop_index(op.f('ix_performance_certificate_tetelek_project_id'), table_name='performance_certificate_tetelek')
    op.drop_index(op.f('ix_performance_certificate_tetelek_employee_id'), table_name='performance_certificate_tetelek')
    op.drop_index(op.f('ix_performance_certificate_tetelek_certificate_id'), table_name='performance_certificate_tetelek')
    op.drop_table('performance_certificate_tetelek')
    op.drop_index(op.f('ix_vallalkozas_tagok_vallalkozas_id'), table_name='vallalkozas_tagok')
    op.drop_index(op.f('ix_vallalkozas_tagok_employee_id'), table_name='vallalkozas_tagok')
    op.drop_table('vallalkozas_tagok')
    op.drop_index(op.f('ix_project_szamlazok_project_id'), table_name='project_szamlazok')
    op.drop_index(op.f('ix_project_szamlazok_employee_id'), table_name='project_szamlazok')
    op.drop_table('project_szamlazok')
    op.drop_index(op.f('ix_vallalkozasok_adoszam'), table_name='vallalkozasok')
    op.drop_table('vallalkozasok')
