"""belsos tig honap a datumokbol

A belsős TIG hónapját a rendszer szabálya szerint a DÁTUMOK adják, és mindig
az azt megelőző hónapot jelentik: a 2026.07.20-i teljesítés / fizetési
határidő a 2026. JÚNIUSI TIG-é (lásd services/hu_datum.elozo_honap és
routes/internal_performance_certificates._apply_teljesites_honap, ami minden
mentésnél ezt érvényesíti).

A Notionból áthozott soroknál viszont a lap CÍME (illetve a hónap-mező)
döntött, az pedig a készítés hónapját viseli - a júliusi lapon a júniusi
elszámolás van -, így ezek egy hónappal elcsúsztak. A Pénzügy -> utalásra
váró listában ez látszik meg: a 07.20-i határidejű tétel "júliusi" helyett
"júniusi" kell legyen.

Ez a migráció a dátumok szerint igazítja a hónapot:
  teljesítés dátuma > fizetési határidő > utalás dátuma
- az első kitöltöttet vesszük, és abból számolunk vissza egy hónapot. Dátum
nélküli sorhoz nincs mihez igazodni, azt nem bántjuk; ütközésnél (ha a cél
hónapra ugyanannak az embernek már van TIG-je) szintén kihagyjuk a sort.

A hónap tételei (alapbér/extrák/levonások) a TIG-gel együtt mozdulnak.

Az előző migráció (0b3653c111b6) egy gyengébb jelölés alapján dolgozott (a
bejegyzés a saját hónapjában készült), mert dátum nélküli soroknál nincs más
fogódzó. Ahol VAN dátum, ott ez a migráció a mérvadó, és felülírja az ottani
döntést - a dátum a rendszer saját szabálya, a created_at csak becslés.

Revision ID: ea6d72c343c3
Revises: 0b3653c111b6
Create Date: 2026-08-06 09:26:23.439306

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'ea6d72c343c3'
down_revision: Union[str, Sequence[str], None] = '0b3653c111b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# A dátumból számolt hónap (a dátum hónapját megelőző hónap), és csak azok a
# sorok, ahol ez eltér a jelenleg tárolttól - és a cél hónap még szabad.
ERINTETT = """
    SELECT t.id,
           t.employee_id,
           t.ev AS regi_ev,
           t.honap AS regi_honap,
           EXTRACT(YEAR FROM (d.alap - INTERVAL '1 month'))::int AS uj_ev,
           EXTRACT(MONTH FROM (d.alap - INTERVAL '1 month'))::int AS uj_honap
    FROM internal_performance_certificates t
    CROSS JOIN LATERAL (
        SELECT COALESCE(t.teljesites_datuma, t.fizetesi_hatarido, t.utalas_datuma) AS alap
    ) d
    WHERE d.alap IS NOT NULL
      AND (t.ev, t.honap) IS DISTINCT FROM (
          EXTRACT(YEAR FROM (d.alap - INTERVAL '1 month'))::int,
          EXTRACT(MONTH FROM (d.alap - INTERVAL '1 month'))::int
      )
      AND NOT EXISTS (
          SELECT 1 FROM internal_performance_certificates m
          WHERE m.employee_id = t.employee_id
            AND m.id <> t.id
            AND m.ev = EXTRACT(YEAR FROM (d.alap - INTERVAL '1 month'))::int
            AND m.honap = EXTRACT(MONTH FROM (d.alap - INTERVAL '1 month'))::int
      )
"""

# A hónap tételei a TIG-gel együtt mozdulnak - de csak akkor, ha a cél
# hónapban még nincs tétele az illetőnek: két hónap tételeit nem olvasztjuk
# össze.
TETEL_LEPTETES = """
    UPDATE employee_monthly_items i
    SET ev = e.uj_ev, honap = e.uj_honap
    FROM _tig_datum_igazitas e
    WHERE i.employee_id = e.employee_id
      AND i.ev = e.regi_ev
      AND i.honap = e.regi_honap
      AND NOT EXISTS (
          SELECT 1 FROM employee_monthly_items mas
          WHERE mas.employee_id = e.employee_id
            AND mas.ev = e.uj_ev
            AND mas.honap = e.uj_honap
      )
"""

TIG_IGAZITAS = """
    UPDATE internal_performance_certificates t
    SET ev = e.uj_ev, honap = e.uj_honap
    FROM _tig_datum_igazitas e
    WHERE t.id = e.id
"""


def upgrade() -> None:
    """Upgrade schema."""
    # Előbb rögzítjük az érintett sorokat: a tételeket ugyanahhoz a listához
    # kell igazítani, a TIG-ek léptetése után viszont a feltétel már nem állna.
    op.execute(f"CREATE TEMP TABLE _tig_datum_igazitas ON COMMIT DROP AS {ERINTETT}")
    op.execute(TETEL_LEPTETES)
    op.execute(TIG_IGAZITAS)


def downgrade() -> None:
    """Downgrade schema."""
    # Adatjavítás, nem sémaváltozás: a régi (elcsúszott) hónap nem
    # rekonstruálható, és nem is cél visszaállítani.
    pass
