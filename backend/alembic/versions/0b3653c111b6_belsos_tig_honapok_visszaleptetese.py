"""belsos tig honapok visszaleptetese

A belsős TIG-ek VISSZAFELÉ készülnek: júliusban a júniusi, augusztusban a
júliusi. A rendszer viszont sokáig a FOLYÓ hónapot ajánlotta fel a Belsős TIG
oldalon, ezért az akkor rögzített bejegyzések a készítés hónapjára mentődtek -
az augusztusban készített (valójában júliusi) TIG "2026. augusztus havi
TIG"-ként látszik, például a Pénzügy -> utalásra váró listában.

Ez a migráció ezeket lépteti vissza egy hónappal. A jelölés egyértelmű: a
bejegyzés a SAJÁT hónapjában készült (created_at ugyanabban a naptári
hónapban, mint az (ev, honap)) - ilyet csak a régi alapértelmezés tudott
csinálni, a szabály szerint rögzített TIG mindig a következő hónapban
keletkezik. Amit a Notionból hoztunk át (ott már visszaszámolva jött), vagy
amit a következő hónapban rögzítettek, azt nem bántjuk.

A teljesítés dátuma és a fizetési határidő is a hónaphoz igazodik (a következő
hónap 20-a - lásd services/hu_datum.tig_hatarido), de csak ott, ahol eddig is
a régi alapértelmezés (a következő hónap elseje) állt: a kézzel beírt dátumot
nem írjuk felül. A hónap tételei (alapbér/extrák/levonások) a TIG-gel együtt
mozdulnak, különben a TIG összege és a mögötte lévő tételek elválnának.

Ütközés esetén (ha a cél hónapra ugyanannak az embernek már van TIG-je)
érintetlenül hagyjuk a sort - ott két bejegyzés van ugyanarra a hónapra, azt
csak ember tudja eldönteni.

Revision ID: 0b3653c111b6
Revises: 2e4f22d51a5d
Create Date: 2026-08-06 08:59:48.411695

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '0b3653c111b6'
down_revision: Union[str, Sequence[str], None] = '2e4f22d51a5d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# A visszaléptetendő sorok: a saját hónapjukban létrehozott bejegyzések,
# amelyeknél a cél hónap még szabad ugyanannál az embernél.
ERINTETT = """
    SELECT t.id,
           t.employee_id,
           t.ev AS regi_ev,
           t.honap AS regi_honap,
           CASE WHEN t.honap = 1 THEN t.ev - 1 ELSE t.ev END AS uj_ev,
           CASE WHEN t.honap = 1 THEN 12 ELSE t.honap - 1 END AS uj_honap
    FROM internal_performance_certificates t
    WHERE t.created_at IS NOT NULL
      AND EXTRACT(YEAR FROM t.created_at) = t.ev
      AND EXTRACT(MONTH FROM t.created_at) = t.honap
      AND NOT EXISTS (
          SELECT 1 FROM internal_performance_certificates m
          WHERE m.employee_id = t.employee_id
            AND m.id <> t.id
            AND m.ev = CASE WHEN t.honap = 1 THEN t.ev - 1 ELSE t.ev END
            AND m.honap = CASE WHEN t.honap = 1 THEN 12 ELSE t.honap - 1 END
      )
"""

# A TIG-ek léptetése. A dátumok csak akkor mozdulnak, ha eddig is a régi
# alapértelmezés (a hónapot követő hónap elseje) állt bennük - a kézzel beírt
# dátumot nem írjuk felül.
TIG_LEPTETES = """
    UPDATE internal_performance_certificates t
    SET ev = e.uj_ev,
        honap = e.uj_honap,
        teljesites_datuma = CASE
            WHEN t.teljesites_datuma = (make_date(e.regi_ev, e.regi_honap, 1) + INTERVAL '1 month')::date
                THEN (make_date(e.uj_ev, e.uj_honap, 1) + INTERVAL '1 month' + INTERVAL '19 days')::date
            ELSE t.teljesites_datuma
        END,
        fizetesi_hatarido = CASE
            WHEN t.fizetesi_hatarido = (make_date(e.regi_ev, e.regi_honap, 1) + INTERVAL '1 month')::date
                THEN (make_date(e.uj_ev, e.uj_honap, 1) + INTERVAL '1 month' + INTERVAL '19 days')::date
            ELSE t.fizetesi_hatarido
        END
    FROM _tig_leptetes e
    WHERE t.id = e.id
"""

# A hónap tételei a TIG-gel együtt mozdulnak - de csak akkor, ha a cél
# hónapban még nincs tétele az illetőnek: két hónap tételeit nem olvasztjuk
# össze.
TETEL_LEPTETES = """
    UPDATE employee_monthly_items i
    SET ev = e.uj_ev, honap = e.uj_honap
    FROM _tig_leptetes e
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


def upgrade() -> None:
    """Upgrade schema."""
    # Előbb RÖGZÍTJÜK, mely sorok mozdulnak: a léptetés után a jelölés (a saját
    # hónapjában készült) már nem ismerhető fel - sőt, akkor pont úgy néznének
    # ki, mint a helyesen rögzített sorok. A havi tételeket viszont ugyanezekhez
    # a sorokhoz kell igazítani, tehát a listát meg kell őrizni.
    op.execute(f"CREATE TEMP TABLE _tig_leptetes ON COMMIT DROP AS {ERINTETT}")
    op.execute(TETEL_LEPTETES)
    op.execute(TIG_LEPTETES)


def downgrade() -> None:
    """Downgrade schema."""
    # Nincs visszaút: a visszaléptetés után már nem különböztethető meg, melyik
    # sor volt eredetileg elcsúszva - egy vak "előre léptetés" a helyesen
    # rögzített bejegyzéseket rontaná el. Adatjavítás, nem sémaváltozás.
    pass
