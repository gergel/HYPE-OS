"""A kiadás-alapú alvállalkozók TIG-jeinek visszakötése az EREDETI kiadás-
sorukra (a felhasználó hibajelzése, pl. 26-0291 / NDR): kötés nélkül a
projektkód bontása a TIG összegét ÉS a kézi kiadást is beszámolta, a
kifizetés pedig egy MÁSODIK, "TIG - ..." kiadás-sort hozott létre - ugyanaz
a pénz kétszer. Az új TIG-piszkozatok már kötve születnek (lásd
performance_certificates._alvallalkozoi_kiadas_a_felhez); ez a migráció a
MEGLÉVŐ adatot rendezi:

1. a kötetlen TIG-ek megkapják a hozzájuk tartozó kézi kiadás-sort;
2. ahol a kifizetés már létrehozta a duplikált "TIG - ..." sort, ott a
   fizetés-állapot átkerül a kézi sorra, a TIG átkötődik rá, és a duplikált
   sor (a számla-csatolmányaival együtt átmozgatva) törlődik.

Revision ID: o2g9f30c7e51
Revises: n0e7f18a5c39
Create Date: 2026-09-12
"""

import sqlalchemy as sa
from alembic import op

revision = "o2g9f30c7e51"
down_revision = "n0e7f18a5c39"
branch_labels = None
depends_on = None


def _kezi_kiadas_id(conn, employee_id, project_id, project_code_id):
    """A TIG feléhez tartozó KÉZI (nem TIG-ből keletkezett), még kötetlen
    alvállalkozói kiadás - determinisztikusan a legrégebbi."""
    return conn.execute(
        sa.text(
            """
            SELECT e.id FROM expenses e
            WHERE e.employee_id = :emp
              AND lower(trim(COALESCE(e.tipus, ''))) = 'kulsos'
              AND COALESCE(e.megnevezes, '') NOT LIKE 'TIG -%'
              AND e.id NOT IN (
                  SELECT expense_id FROM performance_certificates WHERE expense_id IS NOT NULL
              )
              AND (
                    (CAST(:pid AS integer) IS NOT NULL AND (
                        e.alvallalkozo_project_id = :pid
                        OR (e.alvallalkozo_project_id IS NULL AND e.project_code_id =
                            (SELECT project_code_id FROM projects WHERE id = :pid))
                    ))
                 OR (CAST(:pcid AS integer) IS NOT NULL
                     AND e.alvallalkozo_project_id IS NULL
                     AND e.project_code_id = :pcid)
              )
            ORDER BY e.id
            LIMIT 1
            """
        ),
        {"emp": employee_id, "pid": project_id, "pcid": project_code_id},
    ).scalar()


def upgrade() -> None:
    conn = op.get_bind()
    certek = (
        conn.execute(
            sa.text(
                """
                SELECT id, employee_id, project_id, project_code_id, expense_id
                FROM performance_certificates
                WHERE employee_id IS NOT NULL
                ORDER BY id
                """
            )
        )
        .mappings()
        .all()
    )

    for cert in certek:
        # 1) Kötetlen TIG: megkapja a kézi kiadását.
        if cert["expense_id"] is None:
            kezi = _kezi_kiadas_id(conn, cert["employee_id"], cert["project_id"], cert["project_code_id"])
            if kezi is not None:
                conn.execute(
                    sa.text("UPDATE performance_certificates SET expense_id = :e WHERE id = :c"),
                    {"e": kezi, "c": cert["id"]},
                )
            continue

        # 2) A kifizetés által létrehozott "TIG - ..." sor MELLETT él egy kézi
        # kiadás is: a fizetés-állapot átmegy a kézire, a TIG átkötődik, a
        # duplikált sor törlődik.
        auto = conn.execute(
            sa.text(
                """
                SELECT id, kesz, fizetes_datuma, kiadas_datuma, fizetes_hatarideje
                FROM expenses
                WHERE id = :e AND COALESCE(megnevezes, '') LIKE 'TIG -%'
                """
            ),
            {"e": cert["expense_id"]},
        ).mappings().first()
        if auto is None:
            continue
        kezi = _kezi_kiadas_id(conn, cert["employee_id"], cert["project_id"], cert["project_code_id"])
        if kezi is None:
            continue
        # Ha a duplikált sorra bárki más is hivatkozik, nem nyúlunk hozzá.
        hivatkozik = conn.execute(
            sa.text(
                """
                SELECT (SELECT COUNT(*) FROM employee_monthly_items WHERE expense_id = :e)
                     + (SELECT COUNT(*) FROM internal_performance_certificates WHERE expense_id = :e)
                     + (SELECT COUNT(*) FROM performance_certificates WHERE expense_id = :e AND id != :c)
                """
            ),
            {"e": auto["id"], "c": cert["id"]},
        ).scalar()
        if hivatkozik:
            continue
        conn.execute(
            sa.text(
                """
                UPDATE expenses SET
                    kesz = CASE WHEN :kesz THEN true ELSE kesz END,
                    fizetes_datuma = COALESCE(fizetes_datuma, :fd),
                    kiadas_datuma = COALESCE(kiadas_datuma, :kd),
                    fizetes_hatarideje = COALESCE(fizetes_hatarideje, :fh)
                WHERE id = :kezi
                """
            ),
            {
                "kesz": bool(auto["kesz"]),
                "fd": auto["fizetes_datuma"],
                "kd": auto["kiadas_datuma"],
                "fh": auto["fizetes_hatarideje"],
                "kezi": kezi,
            },
        )
        conn.execute(
            sa.text(
                "UPDATE document_attachments SET entity_id = :kezi "
                "WHERE entity_type = 'expense' AND entity_id = :auto"
            ),
            {"kezi": kezi, "auto": auto["id"]},
        )
        conn.execute(
            sa.text("UPDATE performance_certificates SET expense_id = :kezi WHERE id = :c"),
            {"kezi": kezi, "c": cert["id"]},
        )
        conn.execute(sa.text("DELETE FROM expenses WHERE id = :e"), {"e": auto["id"]})


def downgrade() -> None:
    # Adat-javítás: a szétválogatott duplikátumok nem állíthatók vissza -
    # nincs mit visszacsinálni (az új kötések ártalmatlanok visszafelé is).
    pass
