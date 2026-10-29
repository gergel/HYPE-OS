"""Régi árajánlatok importja + év-sorszámos ajánlatszámok (2026-001).

A felhasználó kérései (2026-10-29):
1. A Google Drive „árajánlatok” mappájában lévő összes régi (Excelben készült)
   árajánlat kerüljön fel az Árajánlatok oldalra „régi árajánlatként”, a HYPE OS
   ajánlat-kinézetével, hogy elő lehessen venni, átírni és menteni.
2. Az ajánlatszám ne hasonlítson a projektkódra (HYPE-2026-0001 ↔ HYPE26-0388):
   legyen év-sorszám, pl. 2026-001.

Mit csinál:
- két új, nem kötelező oszlop a `quotes` táblán: `legacy_source` (a régi
  ajánlat forrása: év/fájlnév) és `legacy_drive_id` (link az eredetire);
- betölti az `app/quotes/regi_ajanlatok.json` ajánlatait (a
  `scripts/regi_arajanlatok_kinyerese.py` állította elő az XLSX-ekből) - a már
  meglévő `legacy_source`-t kihagyja, így újrafuttatva sem duplikál;
  az ügyfelet csak akkor köti be, ha a fájlnév eleje (pl. „NEMZETI SZÍNHÁZ”)
  pontosan egy meglévő ügyfél neve;
- MINDEN ajánlatot átszámoz év-sorszámra időrendben (a régiek a Drive-mappájuk
  évével, az itt készültek a létrehozásuk évével); a verziók együtt maradnak;
- a számlálót márkától függetlenre („ALL”) állítja.

Downgrade: a régi ajánlatok törlődnek és az oszlopok megszűnnek; az
átszámozás nem fordítható vissza (a régi HYPE-2026-0001 számok nem állnak vissza).

Revision ID: r1g2i3a4j5n6
Revises: n4h5a6t7i8d9
"""

import json
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "r1g2i3a4j5n6"
down_revision = "n4h5a6t7i8d9"
branch_labels = None
depends_on = None

ADAT = Path(__file__).resolve().parents[2] / "app" / "quotes" / "regi_ajanlatok.json"

quotes = sa.table(
    "quotes",
    sa.column("id", sa.Integer), sa.column("number", sa.String), sa.column("brand", sa.String),
    sa.column("client_id", sa.Integer), sa.column("project_name", sa.String),
    sa.column("event_date_from", sa.Date), sa.column("event_date_to", sa.Date),
    sa.column("status", sa.String), sa.column("pricing_mode", sa.String), sa.column("months", sa.Integer),
    sa.column("discount_percent", sa.Numeric), sa.column("discount_amount", sa.BigInteger),
    sa.column("vat_percent", sa.Numeric), sa.column("summary_label", sa.String),
    sa.column("note_text", sa.Text), sa.column("internal_note", sa.Text), sa.column("version", sa.Integer),
    sa.column("net_total", sa.BigInteger), sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)), sa.column("sent_at", sa.DateTime(timezone=True)),
    sa.column("legacy_source", sa.String), sa.column("legacy_drive_id", sa.String),
)
quote_items = sa.table(
    "quote_items",
    sa.column("quote_id", sa.Integer), sa.column("section", sa.String), sa.column("name", sa.String),
    sa.column("description", sa.Text), sa.column("occasions", sa.Numeric), sa.column("quantity", sa.Numeric),
    sa.column("unit_price", sa.BigInteger), sa.column("line_discount_percent", sa.Numeric),
    sa.column("is_optional", sa.Boolean), sa.column("sort_order", sa.Integer),
)
counters = sa.table("quote_number_counters", sa.column("brand", sa.String), sa.column("year", sa.Integer),
                    sa.column("last", sa.Integer))


def _sor_osszeg(t: dict) -> int:
    alap = t["occasions"] * t["quantity"] * t["unit_price"]
    return int(round(alap * (1 - (t.get("line_discount_percent") or 0) / 100)))


def _netto(a: dict) -> int:
    resz = sum(_sor_osszeg(t) for t in a["items"] if not t.get("is_optional"))
    kedv = int(round(resz * (a.get("discount_percent") or 0) / 100)) + int(a.get("discount_amount") or 0)
    return max(0, resz - min(kedv, resz))


def _ft(x: float) -> str:
    return f"{int(round(x)):,}".replace(",", " ") + " Ft"


def _belso_megjegyzes(a: dict) -> str:
    sorok = [f"Régi árajánlat, importálva a Drive-ról: {a['source']}"]
    if a.get("title"):
        sorok.append(f"Eredeti cím: {a['title']}")
    if a.get("original_totals"):
        sorok.append("Az eredeti táblázat összesítői: " + ", ".join(_ft(x) for x in a["original_totals"]))
    if a.get("currency_note"):
        sorok.append(a["currency_note"])
    if a.get("internal_note"):
        sorok.append(a["internal_note"])
    return "\n".join(sorok)


def _import(conn) -> dict:
    if not ADAT.exists():
        return {}
    adat = json.loads(ADAT.read_text(encoding="utf-8"))
    meglevo = set(conn.execute(sa.text("SELECT legacy_source FROM quotes WHERE legacy_source IS NOT NULL")).scalars())
    ugyfelek: dict[str, list[int]] = defaultdict(list)
    for cid, nev in conn.execute(sa.text("SELECT id, nev FROM clients")).all():
        if nev:
            ugyfelek[nev.strip().casefold()].append(cid)
    for i, a in enumerate(adat):
        if a["source"] in meglevo:
            continue
        jelolt = ugyfelek.get((a.get("client_guess") or "").strip().casefold(), [])
        mikor = datetime.fromisoformat(a["date"].replace("Z", "+00:00")).astimezone(timezone.utc)
        qid = conn.execute(
            quotes.insert().returning(quotes.c.id).values(
                # Ideiglenes, egyedi szám - az átszámozás adja a végsőt.
                number=f"IMPORT-{i:05d}", brand=a["brand"], client_id=jelolt[0] if len(jelolt) == 1 else None,
                project_name=a["project_name"][:255],
                event_date_from=date.fromisoformat(a["event_date_from"]) if a.get("event_date_from") else None,
                event_date_to=date.fromisoformat(a["event_date_to"]) if a.get("event_date_to") else None,
                status="sent", pricing_mode="one_off", months=12,
                discount_percent=a.get("discount_percent") or 0, discount_amount=a.get("discount_amount") or 0,
                vat_percent=27, summary_label=(a.get("summary_label") or "A PROJECT TELJES KÖLTSÉGE")[:120],
                note_text=a.get("note_text"), internal_note=_belso_megjegyzes(a), version=1,
                net_total=_netto(a), created_at=mikor, updated_at=mikor, sent_at=mikor,
                legacy_source=a["source"][:400], legacy_drive_id=a.get("drive_id"),
            )
        ).scalar_one()
        conn.execute(quote_items.insert(), [
            {
                "quote_id": qid, "section": (t.get("section") or None) and t["section"][:120],
                "name": t["name"][:255], "description": t.get("description"),
                "occasions": t["occasions"], "quantity": t["quantity"], "unit_price": int(t["unit_price"]),
                "line_discount_percent": t.get("line_discount_percent") or 0,
                "is_optional": bool(t.get("is_optional")), "sort_order": (j + 1) * 10,
            }
            for j, t in enumerate(a["items"])
        ])
    # A régiek évét a Drive-mappa adja (2024 / 2025 / 2026) - a számozáshoz.
    return {a["source"][:400]: a.get("year") for a in adat}


def _atszamoz(conn, regi_ev: dict) -> None:
    sorok = conn.execute(sa.text(
        "SELECT id, number, version, created_at, legacy_source FROM quotes ORDER BY created_at, id"
    )).all()
    # A verziók (azonos szám) egy csoport: a legkorábbi verzió dönti el a helyét.
    csoportok: dict[str, dict] = {}
    for qid, szam, _verzio, mikor, forras in sorok:
        cs = csoportok.setdefault(szam, {"ids": [], "mikor": mikor, "ev": None})
        cs["ids"].append(qid)
        ev = regi_ev.get(forras) if forras else None
        if cs["ev"] is None:
            cs["ev"] = ev or (mikor.year if mikor else datetime.now(timezone.utc).year)
    evenkent: dict[int, list[dict]] = defaultdict(list)
    for cs in csoportok.values():
        evenkent[cs["ev"]].append(cs)
    # Két lépés, hogy az új számok ne ütközzenek a régiekkel (number+version egyedi).
    conn.execute(sa.text("UPDATE quotes SET number = 'ATSZAMOZAS-' || id"))
    utolso: dict[int, int] = {}
    atir = sa.text("UPDATE quotes SET number = :szam WHERE id IN :ids").bindparams(
        sa.bindparam("ids", expanding=True))
    for ev, lista in evenkent.items():
        lista.sort(key=lambda c: (c["mikor"] or datetime.min.replace(tzinfo=timezone.utc), min(c["ids"])))
        for n, cs in enumerate(lista, start=1):
            conn.execute(atir, {"szam": f"{ev}-{n:03d}", "ids": cs["ids"]})
        utolso[ev] = len(lista)
    conn.execute(counters.delete())
    if utolso:
        conn.execute(counters.insert(), [{"brand": "ALL", "year": ev, "last": n} for ev, n in utolso.items()])


def upgrade() -> None:
    op.add_column("quotes", sa.Column("legacy_source", sa.String(400), nullable=True,
                                      comment="Régi ajánlat forrása (Drive: év/fájlnév)"))
    op.add_column("quotes", sa.Column("legacy_drive_id", sa.String(80), nullable=True,
                                      comment="Régi ajánlat eredeti fájljának Drive-azonosítója"))
    op.create_unique_constraint("uq_quotes_legacy_source", "quotes", ["legacy_source"])
    conn = op.get_bind()
    regi_ev = _import(conn)
    _atszamoz(conn, regi_ev)


def downgrade() -> None:
    op.execute("DELETE FROM quotes WHERE legacy_source IS NOT NULL")
    op.drop_constraint("uq_quotes_legacy_source", "quotes", type_="unique")
    op.drop_column("quotes", "legacy_drive_id")
    op.drop_column("quotes", "legacy_source")
