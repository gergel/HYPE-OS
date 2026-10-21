"""Migrációs segédek - hogy egy séma-módosítás ne állítsa meg a deployt.

A HIBA, amit megelőz: a konténer indulásakor fut az `alembic upgrade head`
(lásd Dockerfile CMD), miközben az ELŐZŐ konténer még kiszolgálja a
forgalmat. Minden séma-módosítás (ADD COLUMN, ALTER COLUMN, index) ACCESS
EXCLUSIVE zárolást kér a táblára, amit a PostgreSQL csak akkor ad meg, ha
senki más nem olvassa épp azt a táblát.

Ha épp fut egy lekérdezés rajta, a DDL BEÁLL A SORBA - alapértelmezés szerint
korlátlan ideig. És mivel a zárolási sor FIFO, mögé beáll minden további
olvasó is: onnantól nemcsak a deploy áll, hanem a régi alkalmazás is
elkezd hibázni azon a táblán. Kívülről ez annyit mutat, hogy a deploy
"csak fut" percekig, hibaüzenet nélkül.

A megoldás: rövid `lock_timeout` mellett próbálkozunk, és ha nem kapjuk meg a
zárolást, ELENGEDJÜK (nem tartjuk fenn a sort), várunk, majd újra próbáljuk.
Így egy pillanatnyi forgalom nem akasztja meg a deployt, egy tartósan nyitva
felejtett tranzakció pedig beszédes hibával áll meg, nem néma várakozással.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

from sqlalchemy.exc import DBAPIError, OperationalError

log = logging.getLogger("alembic.migracio")

#: Meddig várjon EGY próbálkozás a zárolásra. Rövid: ennyi idő alatt a
#: tipikus lekérdezés lefut, ennél tovább várni már a sort tartaná fenn.
LOCK_TIMEOUT = "3s"
#: Hányszor próbálkozzunk, és mennyit várjunk a próbálkozások között. A
#: szorzatuk a türelmi idő (alapból ~1 perc), ami bőven elég egy lassabb
#: lista-lekérdezés lefutásához, de nem nyúlik a deploy időkorlátjába.
PROBALKOZAS = 12
VARAKOZAS_MP = 5.0


def _zarolasi_hiba(hiba: BaseException) -> bool:
    """Zárolásra várás miatt bukott el, vagy valami másért?

    A `lock_timeout` lejártát a PostgreSQL 55P03 (lock_not_available) kóddal
    jelzi. Minden más hiba (rossz oszlopnév, hiányzó tábla) VALÓDI hiba, azt
    nem próbálgatjuk újra."""
    kod = getattr(getattr(hiba, "orig", None), "pgcode", None)
    if kod == "55P03":
        return True
    return "lock timeout" in str(hiba).lower() or "canceling statement due to lock timeout" in str(hiba).lower()


def zarasbiztos_ddl(op, muvelet: Callable[[], None], *, leiras: str) -> None:
    """Séma-módosítás futtatása úgy, hogy ne álljon be egy zárolás mögé.

    Használat a migrációban::

        zarasbiztos_ddl(
            op,
            lambda: op.add_column("projects", sa.Column("x", sa.Text())),
            leiras="projects.x oszlop",
        )

    SAVEPOINT-on belül fut: az Alembic az egész migrációt egy tranzakcióban
    hajtja végre, ott egy elbukott utasítás az EGÉSZ tranzakciót
    használhatatlanná tenné - a mentőpont viszont visszagörgethető anélkül,
    hogy az addigi lépések elvesznének (ugyanaz a minta, mint a Notion
    importban, lásd notion_import/engine.py safe_upsert).

    A `SET LOCAL` is a mentőponthoz tartozik, tehát a visszagörgetéssel
    magától visszaáll - nem szivárog ki a következő lépésekre."""
    bind = op.get_bind()
    # SQLite-on (tesztek) nincs lock_timeout és nincs mit sorban állni: ott a
    # műveletet egyszerűen lefuttatjuk.
    if bind.dialect.name != "postgresql":
        muvelet()
        return

    for probalkozas in range(1, PROBALKOZAS + 1):
        mentopont = bind.begin_nested()
        try:
            bind.exec_driver_sql(f"SET LOCAL lock_timeout = '{LOCK_TIMEOUT}'")
            muvelet()
            mentopont.commit()
            return
        except (OperationalError, DBAPIError) as hiba:
            mentopont.rollback()
            if not _zarolasi_hiba(hiba):
                raise
            log.warning(
                "A(z) %s módosítása nem kapta meg a zárolást (%d/%d) - várok %.0f mp-et.",
                leiras,
                probalkozas,
                PROBALKOZAS,
                VARAKOZAS_MP,
            )
            if probalkozas < PROBALKOZAS:
                time.sleep(VARAKOZAS_MP)

    raise RuntimeError(
        f"A(z) {leiras} módosítása {PROBALKOZAS} próbálkozás után sem kapta meg a táblazárolást. "
        "Valaki tartósan fogja a táblát - tipikusan egy nyitva felejtett ('idle in transaction') "
        "kapcsolat. Nézd meg a pg_stat_activity nézetet, zárd le azt a kapcsolatot, és indítsd újra a deployt."
    )
