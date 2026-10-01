"""HYPE 2027 tábla + a HYPE 2026 tábla rendrakása (a felhasználó kérése).

1. ÉV a munkalapokon: a diszpótábla eddig egyetlen (2026-os) munkafüzet volt.
   Mostantól minden munkalap egy évhez tartozik (`ev`), és a fül neve ÉVENKÉNT
   egyedi - a 2027-es táblának is van „BELSŐS DISZPÓSTÁBLA” lapja.

2. HYPE 2026 rendrakás:
   - a KÜLSŐS lap tetején a nevek sora fölötti/alatti jelmagyarázat-sorok (a
     Sheetből jött 12 soros fejléc-blokkból a 11, ami NEM a nevek sora)
     ELREJTŐDNEK - a nevek sora marad, különben nem látszana, kinek az
     oszlopában jár az ember. Elrejtés, nem törlés: az admin a „Rejtettek
     mutatása” kapcsolóval visszahozhatja;
   - a „Mappanévgenerátor”, a „PROJECT KÓDOK” (teljes projektkód-lista) és az
     „AUTÓK” munkalap TÖRLŐDIK (a celláival és a személyes nézetekkel együtt).
     Az eredetijük a Google Táblázatban megvan.

3. HYPE 2027 tábla - három lap, az átláthatóság kedvéért TÖMÖR fejléccel:
   - BELSŐS DISZPÓSTÁBLA: 2 fejléc-sor (osztály + név), a megadott 13 név
     osztályonként; az oszlop-ember kötés a 2026-os azonos nevű oszlopéból
     öröklődik (vagy egyértelmű keresztnév-egyezésből);
   - KÜLSŐS DISZPÓSTÁBLA: ugyanazok az oszlopok (nevek, kötések, rejtések),
     mint 2026-ban - de a jelmagyarázat-blokk nélkül, 1 fejléc-sorral;
   - ANYDESK ELÉRÉSEK: a 2026-os lap másolata.
   A belsős és a külsős lapon 2027 minden napja egy sor (dátum, a hét napja,
   1. diszpó), hónaponként egy elválasztó sorral.

IDEMPOTENS: a 2026-os lépések újrafuttatva nem csinálnak semmit, a 2027-es
lapok csak akkor jönnek létre, ha még nincs 2027-es munkalap. Szándékosan
nyers SQL, nem az ORM-modellek: egy migráció ne függjön a modellek későbbi
állapotától.

Revision ID: w6r3o74m1n95
Revises: v5q2n63k0l84
"""

from __future__ import annotations

import unicodedata
from datetime import date, timedelta

import sqlalchemy as sa
from alembic import op

revision = "w6r3o74m1n95"
down_revision = "v5q2n63k0l84"
branch_labels = None
depends_on = None

EV_2026 = 2026
EV_2027 = 2027

BELSOS_LAP = "BELSŐS DISZPÓSTÁBLA"
KULSOS_LAP = "KÜLSŐS DISZPÓSTÁBLA"
ANYDESK_LAP = "ANYDESK ELÉRÉSEK"
TORLENDO_LAPOK = ("Mappanévgenerátor", "PROJECT KÓDOK", "AUTÓK")

#: A 2027-es belsős lap oszlopai: osztályonként a nevek (a felhasználó
#: listája; Zsóka új - a gyártási és kreatív osztályhoz került).
BELSOS_2027: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("UTÓMUNKA OSZTÁLY", ("Dia", "Attila")),
    ("CAMERA CREW", ("Ádám", "Geri", "Márk", "Péter", "Áron", "Ricsi", "Martin")),
    ("GYÁRTÁS ÉS KREATÍV OSZTÁLY", ("Bogi", "Zsóka", "Flóra", "Ági")),
)

ALAP_OSZLOPOK = ("DÁTUM", "NAP", "DISZPÓSZÁM")
NAPOK = ("hétfő", "kedd", "szerda", "csütörtök", "péntek", "szombat", "vasárnap")
HONAPOK = (
    "JANUÁR", "FEBRUÁR", "MÁRCIUS", "ÁPRILIS", "MÁJUS", "JÚNIUS",
    "JÚLIUS", "AUGUSZTUS", "SZEPTEMBER", "OKTÓBER", "NOVEMBER", "DECEMBER",
)


def _kulcs(szoveg: str | None) -> str:
    """Ékezet- és kisbetű-független névkulcs (mint a services/hu_szoveg)."""
    nfkd = unicodedata.normalize("NFKD", (szoveg or "").strip().lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def upgrade() -> None:
    # ── 1. ÉV ───────────────────────────────────────────────────────────────
    op.add_column(
        "diszpo_munkalapok",
        sa.Column("ev", sa.Integer(), nullable=False, server_default="2026"),
    )
    op.create_index("ix_diszpo_munkalapok_ev", "diszpo_munkalapok", ["ev"])
    op.drop_index("ix_diszpo_munkalapok_nev", table_name="diszpo_munkalapok")
    op.create_index("ix_diszpo_munkalapok_nev", "diszpo_munkalapok", ["nev"])
    op.create_unique_constraint("uq_diszpo_munkalap_ev_nev", "diszpo_munkalapok", ["ev", "nev"])

    conn = op.get_bind()
    _rendrakas_2026(conn)
    _tabla_2027(conn)


def _lap(conn, ev: int, nev: str):
    return conn.execute(
        sa.text("SELECT id, fejlec_sorok, sor_szam, oszlop_szam FROM diszpo_munkalapok WHERE ev = :ev AND nev = :nev"),
        {"ev": ev, "nev": nev},
    ).first()


def _rendrakas_2026(conn) -> None:
    # A törlendő munkalapok - a gyerektáblák a CASCADE ellenére is kifejezetten
    # (a sorrend így adatbázis-beállítástól független).
    for nev in TORLENDO_LAPOK:
        lap = _lap(conn, EV_2026, nev)
        if lap is None:
            continue
        for tabla in ("diszpo_cellak", "diszpo_sorok", "diszpo_oszlopok", "diszpo_nezetek"):
            conn.execute(sa.text(f"DELETE FROM {tabla} WHERE munkalap_id = :id"), {"id": lap.id})
        conn.execute(sa.text("DELETE FROM diszpo_munkalapok WHERE id = :id"), {"id": lap.id})

    # A külsős lap fejléc-blokkjából minden sor rejtett, ami nem a nevek sora.
    # A nevek sora az, amelyikben a legtöbb kitöltött cella áll a D oszloptól
    # (ugyanaz a szabály, mint services/diszpo_sheet_sync.nevsor_indexe).
    kulsos = _lap(conn, EV_2026, KULSOS_LAP)
    if kulsos is None or kulsos.fejlec_sorok <= 1:
        return
    nevsor = conn.execute(
        sa.text(
            "SELECT sor_idx FROM diszpo_cellak "
            "WHERE munkalap_id = :id AND sor_idx < :fej AND oszlop_idx >= 3 "
            "AND ertek IS NOT NULL AND ertek <> '' "
            "GROUP BY sor_idx ORDER BY COUNT(*) DESC, sor_idx DESC LIMIT 1"
        ),
        {"id": kulsos.id, "fej": kulsos.fejlec_sorok},
    ).scalar()
    if nevsor is None:
        return
    conn.execute(
        sa.text(
            "UPDATE diszpo_sorok SET rejtett = TRUE "
            "WHERE munkalap_id = :id AND idx < :fej AND idx <> :nevsor AND rejtett = FALSE"
        ),
        {"id": kulsos.id, "fej": kulsos.fejlec_sorok, "nevsor": nevsor},
    )


def _uj_lap(conn, nev: str, sorrend: int, fejlec_sorok: int) -> int:
    return conn.execute(
        sa.text(
            "INSERT INTO diszpo_munkalapok (ev, nev, sorrend, sor_szam, oszlop_szam, fejlec_sorok, created_at, updated_at) "
            "VALUES (:ev, :nev, :sorrend, 0, 0, :fej, now(), now()) RETURNING id"
        ),
        {"ev": EV_2027, "nev": nev, "sorrend": sorrend, "fej": fejlec_sorok},
    ).scalar_one()


def _oszlopok_be(conn, lap_id: int, oszlopok: list[dict]) -> None:
    for o in oszlopok:
        conn.execute(
            sa.text(
                "INSERT INTO diszpo_oszlopok (munkalap_id, idx, cimke, csoport, employee_id, rejtett, created_at, updated_at) "
                "VALUES (:lap, :idx, :cimke, :csoport, :emp, :rejtett, now(), now())"
            ),
            {"lap": lap_id, **o},
        )


def _cellak_be(conn, lap_id: int, cellak: list[tuple[int, int, str | None, str | None]]) -> None:
    if not cellak:
        return
    conn.execute(
        sa.text(
            "INSERT INTO diszpo_cellak (munkalap_id, sor_idx, oszlop_idx, ertek, szin, created_at, updated_at) "
            "VALUES (:lap, :sor, :oszlop, :ertek, :szin, now(), now())"
        ),
        [{"lap": lap_id, "sor": r, "oszlop": c, "ertek": e, "szin": sz} for r, c, e, sz in cellak],
    )


def _ev_sorai(conn, lap_id: int, kezdo_idx: int) -> tuple[int, list[tuple[int, int, str | None, str | None]]]:
    """2027 minden napja egy sor, hónaponként egy elválasztóval. Visszaadja a
    következő szabad sorindexet és a dátum-oszlopok celláit."""
    sorok: list[dict] = []
    cellak: list[tuple[int, int, str | None, str | None]] = []
    idx = kezdo_idx
    nap = date(EV_2027, 1, 1)
    while nap.year == EV_2027:
        if nap.day == 1:
            sorok.append({"idx": idx, "datum": None, "nap": None, "szam": None, "elv": True})
            cellak.append((idx, 0, f"{HONAPOK[nap.month - 1]} {EV_2027}", None))
            idx += 1
        sorok.append({"idx": idx, "datum": nap, "nap": NAPOK[nap.weekday()], "szam": 1, "elv": False})
        cellak.append((idx, 0, nap.strftime("%Y.%m.%d."), None))
        cellak.append((idx, 1, NAPOK[nap.weekday()], None))
        cellak.append((idx, 2, "1", None))
        idx += 1
        nap += timedelta(days=1)
    conn.execute(
        sa.text(
            "INSERT INTO diszpo_sorok (munkalap_id, idx, datum, nap, diszposzam, elvalaszto, rejtett, created_at, updated_at) "
            "VALUES (:lap, :idx, :datum, :nap, :szam, :elv, FALSE, now(), now())"
        ),
        [{"lap": lap_id, **s} for s in sorok],
    )
    return idx, cellak


def _fejlec_sorok_be(conn, lap_id: int, darab: int) -> None:
    conn.execute(
        sa.text(
            "INSERT INTO diszpo_sorok (munkalap_id, idx, datum, nap, diszposzam, elvalaszto, rejtett, created_at, updated_at) "
            "VALUES (:lap, :idx, NULL, NULL, NULL, FALSE, FALSE, now(), now())"
        ),
        [{"lap": lap_id, "idx": i} for i in range(darab)],
    )


def _meret(conn, lap_id: int, sor_szam: int, oszlop_szam: int) -> None:
    conn.execute(
        sa.text("UPDATE diszpo_munkalapok SET sor_szam = :s, oszlop_szam = :o WHERE id = :id"),
        {"s": sor_szam, "o": oszlop_szam, "id": lap_id},
    )


def _tabla_2027(conn) -> None:
    if conn.execute(sa.text("SELECT 1 FROM diszpo_munkalapok WHERE ev = :ev LIMIT 1"), {"ev": EV_2027}).first():
        return

    # ── BELSŐS ──────────────────────────────────────────────────────────────
    # Az oszlop-ember kötés: a 2026-os azonos nevű oszlopé, különben egy
    # EGYÉRTELMŰ keresztnév-egyezés az aktív munkatársak közt.
    korabbi: dict[str, int] = {}
    belsos_2026 = _lap(conn, EV_2026, BELSOS_LAP)
    if belsos_2026 is not None:
        for cimke, emp in conn.execute(
            sa.text(
                "SELECT cimke, employee_id FROM diszpo_oszlopok "
                "WHERE munkalap_id = :id AND employee_id IS NOT NULL AND cimke IS NOT NULL"
            ),
            {"id": belsos_2026.id},
        ):
            korabbi[_kulcs(cimke)] = emp
    nevterkep: dict[str, set[int]] = {}
    for emp_id, teljes_nev in conn.execute(
        sa.text("SELECT id, full_name FROM employees WHERE is_active IS NOT FALSE")
    ):
        for resz in (teljes_nev or "").split():
            nevterkep.setdefault(_kulcs(resz), set()).add(emp_id)

    def ember(nev: str) -> int | None:
        if _kulcs(nev) in korabbi:
            return korabbi[_kulcs(nev)]
        jeloltek = nevterkep.get(_kulcs(nev), set())
        return next(iter(jeloltek)) if len(jeloltek) == 1 else None

    lap_id = _uj_lap(conn, BELSOS_LAP, 0, 2)
    oszlopok = [
        {"idx": i, "cimke": c, "csoport": None, "emp": None, "rejtett": False} for i, c in enumerate(ALAP_OSZLOPOK)
    ]
    cellak: list[tuple[int, int, str | None, str | None]] = [(0, i, c, None) for i, c in enumerate(ALAP_OSZLOPOK)]
    idx = len(ALAP_OSZLOPOK)
    for csoport, nevek in BELSOS_2027:
        cellak.append((0, idx, csoport, None))
        for nev in nevek:
            oszlopok.append({"idx": idx, "cimke": nev, "csoport": csoport, "emp": ember(nev), "rejtett": False})
            cellak.append((1, idx, nev, None))
            idx += 1
    _oszlopok_be(conn, lap_id, oszlopok)
    _fejlec_sorok_be(conn, lap_id, 2)
    sor_szam, napcellak = _ev_sorai(conn, lap_id, 2)
    _cellak_be(conn, lap_id, cellak + napcellak)
    _meret(conn, lap_id, sor_szam, len(oszlopok))

    # ── KÜLSŐS ──────────────────────────────────────────────────────────────
    # Ugyanazok az oszlopok, mint 2026-ban - a jelmagyarázat-blokk nélkül.
    lap_id = _uj_lap(conn, KULSOS_LAP, 1, 1)
    kulsos_2026 = _lap(conn, EV_2026, KULSOS_LAP)
    regi = (
        conn.execute(
            sa.text(
                "SELECT idx, cimke, csoport, employee_id, rejtett FROM diszpo_oszlopok "
                "WHERE munkalap_id = :id ORDER BY idx"
            ),
            {"id": kulsos_2026.id},
        ).all()
        if kulsos_2026 is not None
        else []
    )
    oszlop_szam = max(len(ALAP_OSZLOPOK), (regi[-1].idx + 1) if regi else 0)
    regi_terkep = {o.idx: o for o in regi}
    oszlopok = []
    cellak = []
    for i in range(oszlop_szam):
        o = regi_terkep.get(i)
        cimke = ALAP_OSZLOPOK[i] if i < len(ALAP_OSZLOPOK) else (o.cimke if o else None)
        oszlopok.append(
            {
                "idx": i,
                "cimke": cimke,
                "csoport": o.csoport if o else None,
                "emp": o.employee_id if o and i >= len(ALAP_OSZLOPOK) else None,
                "rejtett": bool(o.rejtett) if o and i >= len(ALAP_OSZLOPOK) else False,
            }
        )
        if cimke:
            cellak.append((0, i, cimke, None))
    _oszlopok_be(conn, lap_id, oszlopok)
    _fejlec_sorok_be(conn, lap_id, 1)
    sor_szam, napcellak = _ev_sorai(conn, lap_id, 1)
    _cellak_be(conn, lap_id, cellak + napcellak)
    _meret(conn, lap_id, sor_szam, oszlop_szam)

    # ── ANYDESK ─────────────────────────────────────────────────────────────
    anydesk_2026 = _lap(conn, EV_2026, ANYDESK_LAP)
    if anydesk_2026 is None:
        return
    lap_id = _uj_lap(conn, ANYDESK_LAP, 2, anydesk_2026.fejlec_sorok)
    for tabla, oszlopok_sql in (
        ("diszpo_oszlopok", "idx, cimke, csoport, employee_id, rejtett"),
        ("diszpo_sorok", "idx, datum, nap, diszposzam, elvalaszto, rejtett"),
        ("diszpo_cellak", "sor_idx, oszlop_idx, ertek, szin"),
    ):
        conn.execute(
            sa.text(
                f"INSERT INTO {tabla} (munkalap_id, {oszlopok_sql}, created_at, updated_at) "
                f"SELECT :uj, {oszlopok_sql}, now(), now() FROM {tabla} WHERE munkalap_id = :regi"
            ),
            {"uj": lap_id, "regi": anydesk_2026.id},
        )
    _meret(conn, lap_id, anydesk_2026.sor_szam, anydesk_2026.oszlop_szam)


def downgrade() -> None:
    # A 2027-es lapok eltávolíthatók; a 2026-os törlés és rejtés nem
    # fordítható vissza innen (a törölt lapok eredetije a Google Táblázatban
    # van, a rejtett sorok a felületről visszahozhatók).
    conn = op.get_bind()
    for (lap_id,) in conn.execute(sa.text("SELECT id FROM diszpo_munkalapok WHERE ev = :ev"), {"ev": EV_2027}).all():
        for tabla in ("diszpo_cellak", "diszpo_sorok", "diszpo_oszlopok", "diszpo_nezetek"):
            conn.execute(sa.text(f"DELETE FROM {tabla} WHERE munkalap_id = :id"), {"id": lap_id})
        conn.execute(sa.text("DELETE FROM diszpo_munkalapok WHERE id = :id"), {"id": lap_id})
    op.drop_constraint("uq_diszpo_munkalap_ev_nev", "diszpo_munkalapok", type_="unique")
    op.drop_index("ix_diszpo_munkalapok_nev", table_name="diszpo_munkalapok")
    op.create_index("ix_diszpo_munkalapok_nev", "diszpo_munkalapok", ["nev"], unique=True)
    op.drop_index("ix_diszpo_munkalapok_ev", table_name="diszpo_munkalapok")
    op.drop_column("diszpo_munkalapok", "ev")
