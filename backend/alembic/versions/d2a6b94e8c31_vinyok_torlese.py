"""Öt vinyó törlése a hozzájuk tartozó utómunkákkal együtt.

A felhasználó kérése: az Archive_23_01, Archive_23_02, Archive_23_03,
Archive_24_02 és Sárga_02 vinyók kerüljenek ki a rendszerből, a rajtuk lévő
utómunkákkal együtt.

Egy utómunka akkor törlődik, ha MINDEN vinyója a törlendők közül való - ha
egy anyag egy megmaradó vinyón is rajta van, azt nem visszük el, csak a
vinyó-lista fogy el alóla a beállításokból. A törlés ugyanazt takarítja el,
amit a felület törlés-gombja (lásd crud_router.delete_item és a Deliverable
kapcsolatai): munkaidő-sorok, visszajelzések, hozzászólások, vágói
ellenőrzés-események, kontakt- és kiosztás-kötések, saját mezők,
Notion-leképezés; a portál nem törlődik, csak elengedi az anyagot.

A vinyó-nevek a beállított opció-listából (deliverable_board_configs.
vinyo_opciok) is kikerülnek - a kódbeli tartalék-lista
(services/deliverable_actions.VINYO_OPTIONS) ugyanebben a körben frissül.

Revision ID: d2a6b94e8c31
Revises: c1f5a83b7d29
"""

from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op

revision = "d2a6b94e8c31"
down_revision = "c1f5a83b7d29"
branch_labels = None
depends_on = None

TOROLT_VINYOK = {"Archive_23_01", "Archive_23_02", "Archive_23_03", "Archive_24_02", "Sárga_02"}

#: A kapcsolódó táblák, amikben az utómunka sora nyomot hagy - a sorrend
#: számít: előbb a hivatkozók, a végén maga a deliverables.
KAPCSOLODO_TORLES = (
    ("vago_ellenorzes_esemenyek", "deliverable_id"),
    ("vago_ellenorzes_kimenetek", "deliverable_id"),
    ("deliverable_comments", "deliverable_id"),
    ("feedbacks", "deliverable_id"),
    ("timesheets", "deliverable_id"),
    ("deliverable_contacts", "deliverable_id"),
    ("deliverable_kiosztottak", "deliverable_id"),
)


def _vinyo_lista(nyers) -> list[str]:
    if isinstance(nyers, str):
        try:
            nyers = json.loads(nyers)
        except ValueError:
            return []
    if not isinstance(nyers, list):
        return []
    return [str(v).strip() for v in nyers if v and str(v).strip()]


def upgrade() -> None:
    conn = op.get_bind()

    # 1) Az érintett utómunkák összegyűjtése.
    idk: list[int] = []
    for did, nev, nyers in conn.execute(
        sa.text("SELECT id, projekt_neve, vinyok FROM deliverables WHERE vinyok IS NOT NULL")
    ):
        vinyok = _vinyo_lista(nyers)
        if vinyok and all(v in TOROLT_VINYOK for v in vinyok):
            idk.append(did)
            print(f"Törlésre jelölve: #{did} {nev} ({', '.join(vinyok)})")

    # 2) A kapcsolódó sorok, majd maguk az utómunkák.
    if idk:
        be = sa.bindparam("idk", expanding=True)
        for tabla, oszlop in KAPCSOLODO_TORLES:
            conn.execute(
                sa.text(f"DELETE FROM {tabla} WHERE {oszlop} IN :idk").bindparams(be),
                {"idk": idk},
            )
        # A portál megmarad (a kiküldött linkek élnek), csak elengedi az anyagot.
        conn.execute(
            sa.text("UPDATE portals SET deliverable_id = NULL WHERE deliverable_id IN :idk").bindparams(be),
            {"idk": idk},
        )
        conn.execute(
            sa.text(
                "DELETE FROM custom_field_values WHERE entity_type = 'deliverable' AND record_id IN :idk"
            ).bindparams(be),
            {"idk": idk},
        )
        conn.execute(
            sa.text(
                "DELETE FROM notion_import_map WHERE entity_type = 'Deliverable' AND entity_id IN :idk"
            ).bindparams(be),
            {"idk": idk},
        )
        conn.execute(sa.text("DELETE FROM deliverables WHERE id IN :idk").bindparams(be), {"idk": idk})
        print(f"{len(idk)} utómunka törölve.")
    else:
        print("Nincs törlendő utómunka (már lefutott, vagy nincs ilyen vinyójú anyag).")

    # 3) A vinyó-nevek kivétele a beállított opció-listából.
    for cid, nyers in conn.execute(
        sa.text("SELECT id, vinyo_opciok FROM deliverable_board_configs WHERE vinyo_opciok IS NOT NULL")
    ):
        opciok = _vinyo_lista(nyers)
        maradek = [v for v in opciok if v not in TOROLT_VINYOK]
        if len(maradek) != len(opciok):
            conn.execute(
                sa.text("UPDATE deliverable_board_configs SET vinyo_opciok = CAST(:v AS json) WHERE id = :c"),
                {"v": json.dumps(maradek, ensure_ascii=False), "c": cid},
            )
            print(f"Vinyó-opciók frissítve (config #{cid}): {len(opciok)} -> {len(maradek)}.")


def downgrade() -> None:
    # A törölt utómunkák nem állíthatók vissza.
    pass
