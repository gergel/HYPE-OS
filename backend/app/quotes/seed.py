"""Az árajánlat-készítő alapadatainak betöltése - IDEMPOTENS.

Újrafuttatva nem duplikál, és a felületen már átírt tételeket / sablonokat
NEM írja felül: a katalógus-tétel a `seed_key`, a sablon a `seed_key`, a
kategória és a megjegyzés a neve alapján ismerődik fel; ami megvan, marad.

Futtatás: `python -m app.quotes.seed` (vagy a felületen a Katalógus oldal
„Alapadatok betöltése” gombja)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.quote import (
    QuoteCatalogCategory,
    QuoteCatalogItem,
    QuoteNotePreset,
    QuoteTemplate,
    QuoteTemplateItem,
)
from app.quotes import seed_adat as A


def _tetel_kulcs(n: int) -> str:
    return f"c{n:03d}"


def seed(db: Session) -> dict:
    """Vissza: mennyi új kategória / tétel / sablon / megjegyzés jött létre."""
    uj = {"kategoria": 0, "tetel": 0, "sablon": 0, "megjegyzes": 0}

    kategoriak = {k.name: k for k in db.scalars(select(QuoteCatalogCategory)).all()}
    for i, nev in enumerate(A.KATEGORIAK):
        if nev not in kategoriak:
            kategoriak[nev] = QuoteCatalogCategory(name=nev, sort_order=(i + 1) * 10)
            db.add(kategoriak[nev])
            uj["kategoria"] += 1
    db.flush()

    variansa = {n: csoport for csoport, tagok in A.VARIANSOK.items() for n in tagok}
    tetelek = {t.seed_key: t for t in db.scalars(select(QuoteCatalogItem).where(QuoteCatalogItem.seed_key.is_not(None)))}
    for n, kat, nev, leiras, egyseg, ar, mn, mx in A.TETELEK:
        kulcs = _tetel_kulcs(n)
        if kulcs in tetelek:
            continue
        tetelek[kulcs] = QuoteCatalogItem(
            category_id=kategoriak[kat].id, name=nev, default_description=leiras or None, unit=egyseg,
            base_price=ar, price_min=mn, price_max=mx, sort_order=n * 10, seed_key=kulcs,
            tags=[f"variant:{variansa[n]}"] if n in variansa else [],
        )
        db.add(tetelek[kulcs])
        uj["tetel"] += 1
    db.flush()

    megjegyzes = db.scalar(select(QuoteNotePreset).where(QuoteNotePreset.name == A.MEGJEGYZES_NEV))
    if megjegyzes is None:
        megjegyzes = QuoteNotePreset(name=A.MEGJEGYZES_NEV, text=A.MEGJEGYZES, sort_order=10)
        db.add(megjegyzes)
        db.flush()
        uj["megjegyzes"] += 1

    meglevo = set(db.scalars(select(QuoteTemplate.seed_key).where(QuoteTemplate.seed_key.is_not(None))))
    for i, sb in enumerate(A.SABLONOK):
        if sb["kulcs"] in meglevo:
            continue
        t = QuoteTemplate(
            name=sb["nev"], description=sb["leiras"], brand="HYPE", pricing_mode=sb["mod"],
            summary_label=sb["cimke"], occasions_label=sb.get("alkalom_felirat"), typical_total=sb["tipikus"],
            default_note_id=megjegyzes.id, sort_order=(i + 1) * 10, seed_key=sb["kulcs"],
        )
        sor = 0
        for szekcio, sorok in sb["szekciok"]:
            for x in sorok:
                sor += 10
                t.items.append(QuoteTemplateItem(
                    catalog_item_id=tetelek[_tetel_kulcs(x["tetel"])].id if x["tetel"] else None,
                    section=szekcio, name_override=x["nev"], description_override=x["leiras"],
                    unit_override=x["egyseg"], default_occasions=x["alkalom"], default_quantity=x["menny"],
                    price_override=x["ar"], is_optional=x["opcio"], sort_order=sor,
                ))
        db.add(t)
        uj["sablon"] += 1
    db.flush()
    return uj


def main() -> None:
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        eredmeny = seed(db)
        db.commit()
    finally:
        db.close()
    print(f"Árajánlat-alapadatok betöltve (új): {eredmeny}")


if __name__ == "__main__":
    main()
