"""A védett rendszergazda fiók helyreállítása

Adatmigráció, nem sémaváltozás: a védett rendszergazda fiókja (lásd
core/security.vedett_rendszergazda) inaktívra volt állítva, és így nem lehetett
belépni vele - miközben épp ez az a fiók, amivel a jogosultságokat vissza
lehetne adni. Adatbázis-hozzáférés nélkül ez kívülről nem javítható, ezért a
deploy javítsa magától.

A futásidejű védelem (a belépés helyreállítja a fiókot, és nem lehet többé
kikapcsolni) külön van; ez a migráció csak azt intézi, hogy a MOSTANI, rossz
állapot azonnal rendbe jöjjön, ne csak a következő belépéskor.

Idempotens: ha már jó az állapot, nem csinál semmit. Ha a címhez nem tartozik
sor, szintén nem - egy üres/friss adatbázison is lefut.

Revision ID: b7d3f1a90c24
Revises: a1c48e6f2b35
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b7d3f1a90c24"
down_revision: Union[str, Sequence[str], None] = "a1c48e6f2b35"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _vedett_cimek() -> list[str]:
    """A beállításból, hogy ne kelljen a címet a migrációba égetni."""
    from app.core.security import vedett_admin_emailek

    return sorted(vedett_admin_emailek())


def upgrade() -> None:
    cimek = _vedett_cimek()
    if not cimek:
        return
    kapcsolat = op.get_bind()

    # Az e-mail nem egyedi, és a kisbetű/nagybetű sem garantált - ezért
    # lower()-rel keresünk, és MINDEN egyező sorra futunk.
    ids = [
        sor[0]
        for sor in kapcsolat.execute(
            sa.text("SELECT id FROM employees WHERE lower(trim(email)) IN :cimek").bindparams(
                sa.bindparam("cimek", value=tuple(cimek), expanding=True)
            )
        )
    ]
    if not ids:
        return

    kapcsolat.execute(
        sa.text("UPDATE employees SET is_active = true, role = 'admin' WHERE id IN :ids").bindparams(
            sa.bindparam("ids", value=tuple(ids), expanding=True)
        )
    )
    # A korlátozó sorok is menjenek: enélkül a menü és a middleware attól még
    # elrejtené az oldalakat, hogy a backend már mindent beenged.
    vizsgalo = sa.inspect(kapcsolat)
    for tabla in ("page_access_configs", "field_visibility_configs"):
        if vizsgalo.has_table(tabla):
            kapcsolat.execute(
                sa.text(f"DELETE FROM {tabla} WHERE employee_id IN :ids").bindparams(
                    sa.bindparam("ids", value=tuple(ids), expanding=True)
                )
            )


def downgrade() -> None:
    """Nincs visszaút: egy fiók újbóli kizárása nem az, amit egy visszagörgetés
    során bárki akarna, és a korábbi (hibás) állapotot sem őriztük meg."""
