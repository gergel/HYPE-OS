"""A HYPE 2027 tábla migrációjának adat-lépései (w6r3o74m1n95).

Egy tranzakcióban fut a helyi adatbázison, és a végén VISSZAGÖRGETŐDIK - a
meglévő adathoz nem nyúl. Egy kicsi, a 2026-os Sheet alakját követő 2026-os
táblát épít fel (külsős lap 12 soros fejléc-blokkal, a nevek a 11. sorban;
belsős lap két fejléc-sorral; AnyDesk; és a három törlendő lap), és ezen
ellenőrzi a rendrakást és a 2027-es lapokat."""

from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path

import pytest
import sqlalchemy as sa

from app.core.database import engine

_spec = importlib.util.spec_from_file_location(
    "hype_2027_migracio", Path(__file__).parents[1] / "alembic/versions/w6r3o74m1n95_hype_2027_tabla.py"
)
migracio = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(migracio)


def _lap(conn, ev: int, nev: str, fejlec: int, sorok: int, oszlopok: int) -> int:
    return conn.execute(
        sa.text(
            "INSERT INTO diszpo_munkalapok (ev, nev, sorrend, sor_szam, oszlop_szam, fejlec_sorok) "
            "VALUES (:ev, :nev, 0, :s, :o, :f) RETURNING id"
        ),
        {"ev": ev, "nev": nev, "s": sorok, "o": oszlopok, "f": fejlec},
    ).scalar_one()


def _sorok(conn, lap: int, darab: int) -> None:
    for i in range(darab):
        conn.execute(
            sa.text("INSERT INTO diszpo_sorok (munkalap_id, idx, elvalaszto, rejtett) VALUES (:l, :i, FALSE, FALSE)"),
            {"l": lap, "i": i},
        )


def _cella(conn, lap: int, sor: int, oszlop: int, ertek: str) -> None:
    conn.execute(
        sa.text("INSERT INTO diszpo_cellak (munkalap_id, sor_idx, oszlop_idx, ertek) VALUES (:l, :s, :o, :e)"),
        {"l": lap, "s": sor, "o": oszlop, "e": ertek},
    )


def _oszlop(conn, lap: int, idx: int, cimke: str | None, employee_id: int | None = None, rejtett: bool = False):
    conn.execute(
        sa.text(
            "INSERT INTO diszpo_oszlopok (munkalap_id, idx, cimke, employee_id, rejtett) "
            "VALUES (:l, :i, :c, :e, :r)"
        ),
        {"l": lap, "i": idx, "c": cimke, "e": employee_id, "r": rejtett},
    )


@pytest.fixture
def conn():
    with engine.connect() as c:
        tx = c.begin()
        try:
            # Tiszta lap: a tranzakción belül eltüntetjük a meglévő táblát.
            for tabla in ("diszpo_cellak", "diszpo_sorok", "diszpo_oszlopok", "diszpo_nezetek", "diszpo_munkalapok"):
                c.execute(sa.text(f"DELETE FROM {tabla}"))
            yield c
        finally:
            tx.rollback()


def _epit_2026(conn) -> dict[str, int]:
    emp = conn.execute(sa.text("SELECT id FROM employees ORDER BY id LIMIT 1")).scalar()
    lapok: dict[str, int] = {}
    # KÜLSŐS: 12 fejléc-sor, a nevek a 11. sorban (idx 10), majd 2 nap.
    k = _lap(conn, 2026, "KÜLSŐS DISZPÓSTÁBLA", 12, 14, 6)
    _sorok(conn, k, 14)
    for i, jel in enumerate(["broadcast", "egyéb", "operatőr", "sminkes", "fotó"]):
        _cella(conn, k, i + 1, 1, jel)
    for c, nev in enumerate(["BALLA BERCI (demó)", "GINO (demó)", "PITE (demó)"], start=3):
        _cella(conn, k, 10, c, nev)
        _oszlop(conn, k, c, nev, employee_id=emp if c == 3 else None, rejtett=c == 5)
    for c in range(3):
        _oszlop(conn, k, c, None)
    lapok["kulsos"] = k
    # BELSŐS: a 2026-os ÁDÁM oszlop kötése öröklődjön a 2027-es „Ádám”-ra.
    b = _lap(conn, 2026, "BELSŐS DISZPÓSTÁBLA", 2, 2, 4)
    _sorok(conn, b, 2)
    _oszlop(conn, b, 3, "ÁDÁM", employee_id=emp)
    lapok["belsos"] = b
    # ANYDESK + a három törlendő lap.
    a = _lap(conn, 2026, "ANYDESK ELÉRÉSEK", 1, 2, 2)
    _sorok(conn, a, 2)
    _oszlop(conn, a, 0, "gép név")
    _cella(conn, a, 1, 0, "workstation (demó)")
    lapok["anydesk"] = a
    for nev in migracio.TORLENDO_LAPOK:
        t = _lap(conn, 2026, nev, 1, 1, 1)
        _sorok(conn, t, 1)
        _cella(conn, t, 0, 0, "x")
    lapok["emp"] = emp
    return lapok


def test_rendrakas_2026_elrejti_a_jelmagyarazatot_es_torli_a_lapokat(conn):
    lapok = _epit_2026(conn)
    migracio._rendrakas_2026(conn)

    rejtett = [
        r[0]
        for r in conn.execute(
            sa.text("SELECT idx FROM diszpo_sorok WHERE munkalap_id = :l AND rejtett ORDER BY idx"),
            {"l": lapok["kulsos"]},
        )
    ]
    # A 12 fejléc-sorból a 11, ami nem a nevek sora; a napok sorai maradnak.
    assert rejtett == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 11]
    nevek = conn.execute(
        sa.text("SELECT nev FROM diszpo_munkalapok WHERE ev = 2026 ORDER BY nev")
    ).scalars().all()
    assert sorted(nevek) == sorted(["ANYDESK ELÉRÉSEK", "BELSŐS DISZPÓSTÁBLA", "KÜLSŐS DISZPÓSTÁBLA"])

    # Újrafuttatva nem változik semmi.
    migracio._rendrakas_2026(conn)
    assert conn.execute(
        sa.text("SELECT COUNT(*) FROM diszpo_sorok WHERE munkalap_id = :l AND rejtett"), {"l": lapok["kulsos"]}
    ).scalar() == 11


def test_2027_lapok_letrejonnek(conn):
    lapok = _epit_2026(conn)
    migracio._tabla_2027(conn)

    lapok_2027 = conn.execute(
        sa.text("SELECT id, nev, fejlec_sorok, oszlop_szam FROM diszpo_munkalapok WHERE ev = 2027 ORDER BY sorrend")
    ).all()
    assert [lap.nev for lap in lapok_2027] == ["BELSŐS DISZPÓSTÁBLA", "KÜLSŐS DISZPÓSTÁBLA", "ANYDESK ELÉRÉSEK"]
    belsos, kulsos, anydesk = lapok_2027

    # BELSŐS: a 13 megadott név, osztályonként; az Ádám-kötés öröklődött.
    oszlopok = conn.execute(
        sa.text("SELECT cimke, csoport, employee_id FROM diszpo_oszlopok WHERE munkalap_id = :l AND idx >= 3 ORDER BY idx"),
        {"l": belsos.id},
    ).all()
    assert [o.cimke for o in oszlopok] == [
        "Dia", "Attila", "Ádám", "Geri", "Márk", "Péter", "Áron", "Ricsi", "Martin", "Bogi", "Zsóka", "Flóra", "Ági",
    ]
    assert {o.csoport for o in oszlopok} == {"UTÓMUNKA OSZTÁLY", "CAMERA CREW", "GYÁRTÁS ÉS KREATÍV OSZTÁLY"}
    assert next(o for o in oszlopok if o.cimke == "Ádám").employee_id == lapok["emp"]
    assert belsos.fejlec_sorok == 2

    # 2027 minden napja egy sor, 12 hónap-elválasztóval.
    napok = conn.execute(
        sa.text("SELECT COUNT(*) FROM diszpo_sorok WHERE munkalap_id = :l AND datum IS NOT NULL"), {"l": belsos.id}
    ).scalar()
    elvalasztok = conn.execute(
        sa.text("SELECT COUNT(*) FROM diszpo_sorok WHERE munkalap_id = :l AND elvalaszto"), {"l": belsos.id}
    ).scalar()
    assert (napok, elvalasztok) == (365, 12)
    elso = conn.execute(
        sa.text("SELECT datum, nap FROM diszpo_sorok WHERE munkalap_id = :l AND datum IS NOT NULL ORDER BY idx LIMIT 1"),
        {"l": belsos.id},
    ).first()
    assert (elso.datum, elso.nap) == (date(2027, 1, 1), "péntek")

    # KÜLSŐS: ugyanazok a nevek, kötések és rejtések, 1 fejléc-sorral.
    assert kulsos.fejlec_sorok == 1
    k_oszlopok = conn.execute(
        sa.text("SELECT idx, cimke, employee_id, rejtett FROM diszpo_oszlopok WHERE munkalap_id = :l ORDER BY idx"),
        {"l": kulsos.id},
    ).all()
    assert [o.cimke for o in k_oszlopok] == ["DÁTUM", "NAP", "DISZPÓSZÁM", "BALLA BERCI (demó)", "GINO (demó)", "PITE (demó)"]
    assert k_oszlopok[3].employee_id == lapok["emp"]
    assert k_oszlopok[5].rejtett is True
    fejlec = conn.execute(
        sa.text("SELECT ertek FROM diszpo_cellak WHERE munkalap_id = :l AND sor_idx = 0 AND oszlop_idx = 4"),
        {"l": kulsos.id},
    ).scalar()
    assert fejlec == "GINO (demó)"

    # ANYDESK: a 2026-os lap másolata.
    assert conn.execute(
        sa.text("SELECT ertek FROM diszpo_cellak WHERE munkalap_id = :l AND sor_idx = 1 AND oszlop_idx = 0"),
        {"l": anydesk.id},
    ).scalar() == "workstation (demó)"

    # Újrafuttatva nem jön létre második 2027-es tábla.
    migracio._tabla_2027(conn)
    assert conn.execute(sa.text("SELECT COUNT(*) FROM diszpo_munkalapok WHERE ev = 2027")).scalar() == 3


_spec_torles = importlib.util.spec_from_file_location(
    "hype_2027_oszlop_torles", Path(__file__).parents[1] / "alembic/versions/x7s4p85n2o06_hype_2027_kulsos_oszlopok_torlese.py"
)
oszlop_torles = importlib.util.module_from_spec(_spec_torles)
_spec_torles.loader.exec_module(oszlop_torles)


def test_2027_kulsos_d_g_oszlopok_torlese_nev_szerint(conn):
    # A D-G a négy törlendő név - közéjük ékelve egy MARAD oszlop, hogy
    # látszódjon: a név dönt, nem a betűjel.
    cimkek = ["DÁTUM", "NAP", "DISZPÓSZÁM", "BALLA BERCI", "GINO", "MARAD (demó)", "PITE", "Stream Terminal", "UTOLSÓ (demó)"]
    lap = _lap(conn, 2027, "KÜLSŐS DISZPÓSTÁBLA", 1, 2, len(cimkek))
    _sorok(conn, lap, 2)
    for i, c in enumerate(cimkek):
        _oszlop(conn, lap, i, c)
        _cella(conn, lap, 0, i, c)
        _cella(conn, lap, 1, i, f"munka {i} (demó)")
    # A 2026-os azonos nevű lapot nem érintheti.
    regi = _lap(conn, 2026, "KÜLSŐS DISZPÓSTÁBLA", 1, 1, 4)
    _oszlop(conn, regi, 3, "GINO")

    assert oszlop_torles.torles(conn) == [3, 4, 6, 7]

    maradt = conn.execute(
        sa.text("SELECT idx, cimke FROM diszpo_oszlopok WHERE munkalap_id = :l ORDER BY idx"), {"l": lap}
    ).all()
    assert [(o.idx, o.cimke) for o in maradt] == [
        (0, "DÁTUM"), (1, "NAP"), (2, "DISZPÓSZÁM"), (3, "MARAD (demó)"), (4, "UTOLSÓ (demó)"),
    ]
    # A cellák is a helyükre csúsztak.
    assert conn.execute(
        sa.text("SELECT ertek FROM diszpo_cellak WHERE munkalap_id = :l AND sor_idx = 1 AND oszlop_idx = 4"), {"l": lap}
    ).scalar() == "munka 8 (demó)"
    assert conn.execute(sa.text("SELECT oszlop_szam FROM diszpo_munkalapok WHERE id = :l"), {"l": lap}).scalar() == 5
    assert conn.execute(sa.text("SELECT COUNT(*) FROM diszpo_oszlopok WHERE munkalap_id = :l"), {"l": regi}).scalar() == 1
    # Újrafuttatva nem töröl semmit.
    assert oszlop_torles.torles(conn) == []


_spec_ures = importlib.util.spec_from_file_location(
    "hype_2026_ures_oszlopok", Path(__file__).parents[1] / "alembic/versions/y8t5q96o3p17_hype_2026_kulsos_ures_oszlopok.py"
)
ures_oszlopok = importlib.util.module_from_spec(_spec_ures)
_spec_ures.loader.exec_module(ures_oszlopok)


def test_2026_kulsos_ures_b_e_oszlopok_torlese(conn):
    # A = dátum, B-E üres (a D-ben viszont egy dátumos sorban van szöveg - az
    # marad), F = nap, G = név.
    cimkek = ["DÁTUM", None, None, None, None, "fotó + op", "GINO (demó)"]
    lap = _lap(conn, 2026, "KÜLSŐS DISZPÓSTÁBLA", 1, 3, len(cimkek))
    _sorok(conn, lap, 3)
    conn.execute(sa.text("UPDATE diszpo_sorok SET datum = '2026-01-01' WHERE munkalap_id = :l AND idx >= 1"), {"l": lap})
    for i, c in enumerate(cimkek):
        _oszlop(conn, lap, i, c)
        if c:
            _cella(conn, lap, 0, i, c)
    # A jelmagyarázat-sor (nem dátumos) „üresen hagyva” jele nem számít tartalomnak.
    conn.execute(
        sa.text("INSERT INTO diszpo_cellak (munkalap_id, sor_idx, oszlop_idx, szin) VALUES (:l, 0, 2, 'feher')"),
        {"l": lap},
    )
    _cella(conn, lap, 2, 3, "HYPE26-0001 (demó)")
    _cella(conn, lap, 1, 5, "csütörtök")

    assert ures_oszlopok.torles(conn) == [1, 2, 4]

    maradt = conn.execute(
        sa.text("SELECT idx, cimke FROM diszpo_oszlopok WHERE munkalap_id = :l ORDER BY idx"), {"l": lap}
    ).all()
    assert [(o.idx, o.cimke) for o in maradt] == [(0, "DÁTUM"), (1, None), (2, "fotó + op"), (3, "GINO (demó)")]
    assert conn.execute(
        sa.text("SELECT ertek FROM diszpo_cellak WHERE munkalap_id = :l AND sor_idx = 1 AND oszlop_idx = 2"), {"l": lap}
    ).scalar() == "csütörtök"
    assert conn.execute(sa.text("SELECT oszlop_szam FROM diszpo_munkalapok WHERE id = :l"), {"l": lap}).scalar() == 4
    # Újrafuttatva a kitöltött oszlop marad, más nem üres - nem töröl.
    assert ures_oszlopok.torles(conn) == []
