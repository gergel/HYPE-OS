"""Árajánlat-készítő API (`/api/v1/quotes/...`) - lásd app/quotes/ és
docs/arajanlat-keszito.md.

Minden végpont az „/arajanlatok” oldal jogán áll (a Beállításokban KÜLÖN
adható hozzáférés): nézés = view, új ajánlat / ügyfél = create, minden
szerkesztés (ajánlat, katalógus, sablon, megjegyzés) = edit, törlés = delete.
A szerepkör-kapu itt nyitott (minden szerepkör) - a valódi kapu az oldal-jog,
ugyanúgy, mint a korábbi árajánlat-végpontoknál.

A tétel-műveletek a TELJES ajánlatot adják vissza (összesítővel), így a
felület egy válaszból szinkronizál."""

from __future__ import annotations

from datetime import date
from urllib.parse import quote as url_quote

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import Role, require_page_action
from app.models.client import Client
from app.models.employee import Employee
from app.models.quote import (
    EGYSEGEK,
    Quote,
    QuoteCatalogCategory,
    QuoteCatalogItem,
    QuoteCatalogPriceHistory,
    QuoteItem,
    QuoteNotePreset,
    QuoteTemplate,
    QuoteTemplateItem,
)
from app.quotes import export as E
from app.quotes import service as S
from app.quotes.szamitas import sor_osszeg
from app.schemas import quote as Q

PAGE = "/arajanlatok"
_R = tuple(Role)

router = APIRouter(prefix="/quotes", tags=["arajanlat-keszito"])


def _jog(muvelet: str):
    return require_page_action(PAGE, muvelet, *_R)


def _hiba(exc: Exception) -> HTTPException:
    if isinstance(exc, S.NincsMeg):
        return HTTPException(status_code=404, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


def _nem_null(adat: dict, mezok: tuple[str, ...]) -> dict:
    """A kötelező mezőkre küldött null nem törlés, hanem „nem változik”."""
    return {k: v for k, v in adat.items() if not (k in mezok and v is None)}


# ── Szerializálás ────────────────────────────────────────────────────────────


def _szam(x) -> float:
    return float(x or 0)


def _katalogus_tetel(c: QuoteCatalogItem) -> dict:
    return {
        "id": c.id, "category_id": c.category_id, "category": c.category.name if c.category else None,
        "name": c.name, "default_description": c.default_description, "unit": c.unit, "base_price": c.base_price,
        "price_min": c.price_min, "price_max": c.price_max, "price_median": c.price_median,
        "is_active": c.is_active, "sort_order": c.sort_order, "tags": c.tags or [],
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


def _sor(it: QuoteItem, katalogus: dict[int, QuoteCatalogItem]) -> dict:
    c = katalogus.get(it.catalog_item_id) if it.catalog_item_id else None
    return {
        "id": it.id, "catalog_item_id": it.catalog_item_id, "section": it.section, "name": it.name,
        "description": it.description, "occasions": _szam(it.occasions), "quantity": _szam(it.quantity),
        "unit": it.unit, "unit_price": it.unit_price, "line_discount_percent": _szam(it.line_discount_percent),
        "is_optional": it.is_optional, "sort_order": it.sort_order,
        "line_total": sor_osszeg(it.occasions, it.quantity, it.unit_price, it.line_discount_percent),
        # A jelenlegi katalógusár - a felület jelzi, ha eltér („frissít?”).
        "catalog_price": c.base_price if c else None,
        "variant_tags": [t for t in (c.tags or []) if t.startswith("variant:")] if c else [],
    }


def _ajanlat(db: Session, q: Quote) -> dict:
    ids = {i.catalog_item_id for i in q.items if i.catalog_item_id}
    katalogus = {c.id: c for c in db.scalars(select(QuoteCatalogItem).where(QuoteCatalogItem.id.in_(ids)))} if ids else {}
    ugyfel = db.get(Client, q.client_id) if q.client_id else None
    sablon = db.get(QuoteTemplate, q.template_id) if q.template_id else None
    verziok = db.execute(
        select(Quote.id, Quote.version, Quote.status, Quote.created_at, Quote.net_total)
        .where(Quote.number == q.number).order_by(Quote.version)
    ).all()
    szulo = db.get(Quote, q.parent_quote_id) if q.parent_quote_id else None
    return {
        "id": q.id, "number": q.number, "version": q.version, "brand": q.brand,
        "client_id": q.client_id, "client": {"id": ugyfel.id, "nev": ugyfel.nev} if ugyfel else None,
        "project_name": q.project_name,
        "event_date_from": q.event_date_from.isoformat() if q.event_date_from else None,
        "event_date_to": q.event_date_to.isoformat() if q.event_date_to else None,
        "location": q.location, "status": q.status, "pricing_mode": q.pricing_mode, "months": q.months,
        "discount_percent": _szam(q.discount_percent), "discount_amount": q.discount_amount,
        "vat_percent": _szam(q.vat_percent), "summary_label": q.summary_label,
        "occasions_label": q.occasions_label, "note_text": q.note_text, "internal_note": q.internal_note,
        "parent_quote_id": q.parent_quote_id,
        "parent": {"id": szulo.id, "number": szulo.number, "version": szulo.version} if szulo else None,
        "template_id": q.template_id, "template_name": sablon.name if sablon else None,
        "net_total": q.net_total, "created_by": q.created_by,
        "created_at": q.created_at.isoformat() if q.created_at else None,
        "updated_at": q.updated_at.isoformat() if q.updated_at else None,
        "sent_at": q.sent_at.isoformat() if q.sent_at else None,
        "items": [_sor(i, katalogus) for i in sorted(q.items, key=lambda x: x.sort_order)],
        "totals": S.osszegzes(q).dict(),
        "versions": [{"id": v.id, "version": v.version, "status": v.status, "net_total": v.net_total,
                      "created_at": v.created_at.isoformat() if v.created_at else None} for v in verziok],
    }


def _lista_elem(q: Quote, ugyfelek: dict[int, str]) -> dict:
    return {
        "id": q.id, "number": q.number, "version": q.version, "brand": q.brand, "client_id": q.client_id,
        "client_name": ugyfelek.get(q.client_id) if q.client_id else None, "project_name": q.project_name,
        "event_date_from": q.event_date_from.isoformat() if q.event_date_from else None,
        "event_date_to": q.event_date_to.isoformat() if q.event_date_to else None,
        "location": q.location, "status": q.status, "pricing_mode": q.pricing_mode, "net_total": q.net_total,
        "created_at": q.created_at.isoformat() if q.created_at else None,
        "updated_at": q.updated_at.isoformat() if q.updated_at else None,
    }


def _sablon(t: QuoteTemplate, reszletes: bool = False) -> dict:
    ki = {
        "id": t.id, "name": t.name, "description": t.description, "brand": t.brand,
        "pricing_mode": t.pricing_mode, "summary_label": t.summary_label, "occasions_label": t.occasions_label,
        "typical_total": t.typical_total, "default_note_id": t.default_note_id, "sort_order": t.sort_order,
        "is_active": t.is_active, "item_count": len(t.items), "base_total": S.sablon_osszeg(t),
    }
    if reszletes:
        ki["items"] = [{
            "id": ts.id, "catalog_item_id": ts.catalog_item_id, "section": ts.section,
            "name_override": ts.name_override, "description_override": ts.description_override,
            "unit_override": ts.unit_override, "default_occasions": _szam(ts.default_occasions),
            "default_quantity": _szam(ts.default_quantity), "price_override": ts.price_override,
            "is_optional": ts.is_optional, "sort_order": ts.sort_order,
            "catalog_item": _katalogus_tetel(ts.catalog_item) if ts.catalog_item else None,
            # A sorból így lesz ajánlat-sor (név, leírás, egység, ár a felülírásokkal).
            "effective": {**(e := S.sablon_sorbol(ts)), "occasions": _szam(e["occasions"]),
                          "quantity": _szam(e["quantity"])},
        } for ts in t.items]
    return ki


def _ajanlat_vagy_404(db: Session, quote_id: int) -> Quote:
    q = db.get(Quote, quote_id)
    if q is None:
        raise HTTPException(status_code=404, detail="Nincs ilyen árajánlat.")
    return q


# ── Katalógus: kategóriák ────────────────────────────────────────────────────


@router.get("/catalog/categories")
def kategoriak(db: Session = Depends(get_db), _u: Employee = Depends(_jog("view"))):
    sorok = db.scalars(select(QuoteCatalogCategory).order_by(QuoteCatalogCategory.sort_order,
                                                             QuoteCatalogCategory.id)).all()
    return [{"id": k.id, "name": k.name, "sort_order": k.sort_order} for k in sorok]


@router.post("/catalog/categories", status_code=201)
def kategoria_uj(body: Q.KategoriaIn, db: Session = Depends(get_db), _u: Employee = Depends(_jog("edit"))):
    if db.scalar(select(QuoteCatalogCategory).where(QuoteCatalogCategory.name == body.name.strip())):
        raise HTTPException(status_code=400, detail="Van már ilyen nevű kategória.")
    sorrend = body.sort_order if body.sort_order is not None else (
        (db.scalar(select(func.max(QuoteCatalogCategory.sort_order))) or 0) + 10)
    k = QuoteCatalogCategory(name=body.name.strip(), sort_order=sorrend)
    db.add(k)
    db.commit()
    return {"id": k.id, "name": k.name, "sort_order": k.sort_order}


@router.patch("/catalog/categories/{category_id}")
def kategoria_modosit(category_id: int, body: Q.KategoriaPatch, db: Session = Depends(get_db),
                      _u: Employee = Depends(_jog("edit"))):
    k = db.get(QuoteCatalogCategory, category_id)
    if k is None:
        raise HTTPException(status_code=404, detail="Nincs ilyen kategória.")
    for mezo, ertek in _nem_null(body.model_dump(exclude_unset=True), ("name", "sort_order")).items():
        setattr(k, mezo, ertek.strip() if isinstance(ertek, str) else ertek)
    db.commit()
    return {"id": k.id, "name": k.name, "sort_order": k.sort_order}


@router.delete("/catalog/categories/{category_id}", status_code=204)
def kategoria_torol(category_id: int, db: Session = Depends(get_db), _u: Employee = Depends(_jog("edit"))):
    k = db.get(QuoteCatalogCategory, category_id)
    if k is None:
        raise HTTPException(status_code=404, detail="Nincs ilyen kategória.")
    if db.scalar(select(func.count()).select_from(QuoteCatalogItem).where(QuoteCatalogItem.category_id == k.id)):
        raise HTTPException(status_code=400, detail="A kategóriában tételek vannak - előbb helyezd át őket.")
    db.delete(k)
    db.commit()
    return Response(status_code=204)


# ── Katalógus: tételek ───────────────────────────────────────────────────────


@router.get("/catalog/items")
def katalogus(
    q: str | None = None, category: int | None = None, include_inactive: bool = False,
    db: Session = Depends(get_db), _u: Employee = Depends(_jog("view")),
):
    s = select(QuoteCatalogItem).join(QuoteCatalogCategory)
    if not include_inactive:
        s = s.where(QuoteCatalogItem.is_active.is_(True))
    if category:
        s = s.where(QuoteCatalogItem.category_id == category)
    if q and q.strip():
        minta = f"%{q.strip()}%"
        s = s.where(QuoteCatalogItem.name.ilike(minta) | QuoteCatalogItem.default_description.ilike(minta))
    s = s.order_by(QuoteCatalogCategory.sort_order, QuoteCatalogItem.sort_order, QuoteCatalogItem.id)
    return [_katalogus_tetel(c) for c in db.scalars(s)]


def _katalogus_ellenorzes(db: Session, adat: dict) -> None:
    if adat.get("unit") is not None and adat["unit"] not in EGYSEGEK:
        raise HTTPException(status_code=400, detail=f"Érvénytelen egység: {adat['unit']}")
    if adat.get("category_id") is not None and db.get(QuoteCatalogCategory, adat["category_id"]) is None:
        raise HTTPException(status_code=400, detail="Nincs ilyen kategória.")


@router.post("/catalog/items", status_code=201)
def katalogus_uj(body: Q.KatalogusTetelIn, db: Session = Depends(get_db), user: Employee = Depends(_jog("edit"))):
    adat = body.model_dump()
    _katalogus_ellenorzes(db, adat)
    if adat["sort_order"] is None:
        adat["sort_order"] = (db.scalar(select(func.max(QuoteCatalogItem.sort_order))
                                        .where(QuoteCatalogItem.category_id == body.category_id)) or 0) + 10
    c = QuoteCatalogItem(**adat, updated_by=user.id)
    db.add(c)
    db.flush()
    db.add(QuoteCatalogPriceHistory(catalog_item_id=c.id, old_price=None, new_price=c.base_price,
                                    changed_by=user.id))
    db.commit()
    return _katalogus_tetel(c)


@router.patch("/catalog/items/{item_id}")
def katalogus_modosit(item_id: int, body: Q.KatalogusTetelPatch, db: Session = Depends(get_db),
                      user: Employee = Depends(_jog("edit"))):
    c = db.get(QuoteCatalogItem, item_id)
    if c is None:
        raise HTTPException(status_code=404, detail="Nincs ilyen katalógus-tétel.")
    adat = _nem_null(body.model_dump(exclude_unset=True),
                     ("category_id", "name", "unit", "base_price", "is_active", "sort_order", "tags"))
    _katalogus_ellenorzes(db, adat)
    if "base_price" in adat:
        S.katalogus_ar(db, c, adat.pop("base_price"), user)
    for mezo, ertek in adat.items():
        setattr(c, mezo, ertek)
    c.updated_by = user.id
    db.commit()
    db.refresh(c)
    return _katalogus_tetel(c)


@router.delete("/catalog/items/{item_id}")
def katalogus_archival(item_id: int, db: Session = Depends(get_db), user: Employee = Depends(_jog("edit"))):
    """ARCHIVÁLÁS (nem törlés): a meglévő ajánlatok és sablonok hivatkozása
    megmarad, a tétel csak a katalógus-panelből tűnik el."""
    c = db.get(QuoteCatalogItem, item_id)
    if c is None:
        raise HTTPException(status_code=404, detail="Nincs ilyen katalógus-tétel.")
    c.is_active = False
    c.updated_by = user.id
    db.commit()
    return _katalogus_tetel(c)


@router.get("/catalog/items/{item_id}/history")
def katalogus_tortenet(item_id: int, db: Session = Depends(get_db), _u: Employee = Depends(_jog("view"))):
    if db.get(QuoteCatalogItem, item_id) is None:
        raise HTTPException(status_code=404, detail="Nincs ilyen katalógus-tétel.")
    sorok = db.execute(
        select(QuoteCatalogPriceHistory, Employee.full_name)
        .outerjoin(Employee, Employee.id == QuoteCatalogPriceHistory.changed_by)
        .where(QuoteCatalogPriceHistory.catalog_item_id == item_id)
        .order_by(QuoteCatalogPriceHistory.changed_at.desc(), QuoteCatalogPriceHistory.id.desc())
    ).all()
    return [{"id": h.id, "old_price": h.old_price, "new_price": h.new_price,
             "changed_at": h.changed_at.isoformat() if h.changed_at else None, "changed_by": nev}
            for h, nev in sorok]


@router.get("/catalog/items/{item_id}/last-price")
def utolso_ar(item_id: int, client_id: int, db: Session = Depends(get_db), _u: Employee = Depends(_jog("view"))):
    """Az adott ügyfélnek legutóbb adott ár (tipp a felületen) - None, ha még nem volt."""
    return S.utolso_ar(db, [item_id], client_id).get(item_id)


# ── Megjegyzés-sablonok ──────────────────────────────────────────────────────


def _megjegyzes(n: QuoteNotePreset) -> dict:
    return {"id": n.id, "name": n.name, "text": n.text, "sort_order": n.sort_order}


@router.get("/notes")
def megjegyzesek(db: Session = Depends(get_db), _u: Employee = Depends(_jog("view"))):
    return [_megjegyzes(n) for n in db.scalars(select(QuoteNotePreset).order_by(QuoteNotePreset.sort_order,
                                                                                  QuoteNotePreset.id))]


@router.post("/notes", status_code=201)
def megjegyzes_uj(body: Q.MegjegyzesIn, db: Session = Depends(get_db), _u: Employee = Depends(_jog("edit"))):
    if db.scalar(select(QuoteNotePreset).where(QuoteNotePreset.name == body.name.strip())):
        raise HTTPException(status_code=400, detail="Van már ilyen nevű megjegyzés-sablon.")
    n = QuoteNotePreset(name=body.name.strip(), text=body.text, sort_order=body.sort_order or 100)
    db.add(n)
    db.commit()
    return _megjegyzes(n)


@router.patch("/notes/{note_id}")
def megjegyzes_modosit(note_id: int, body: Q.MegjegyzesPatch, db: Session = Depends(get_db),
                       _u: Employee = Depends(_jog("edit"))):
    n = db.get(QuoteNotePreset, note_id)
    if n is None:
        raise HTTPException(status_code=404, detail="Nincs ilyen megjegyzés-sablon.")
    for mezo, ertek in _nem_null(body.model_dump(exclude_unset=True), ("name", "text", "sort_order")).items():
        setattr(n, mezo, ertek)
    db.commit()
    return _megjegyzes(n)


@router.delete("/notes/{note_id}", status_code=204)
def megjegyzes_torol(note_id: int, db: Session = Depends(get_db), _u: Employee = Depends(_jog("edit"))):
    n = db.get(QuoteNotePreset, note_id)
    if n is None:
        raise HTTPException(status_code=404, detail="Nincs ilyen megjegyzés-sablon.")
    db.delete(n)
    db.commit()
    return Response(status_code=204)


# ── Ügyfelek (a meglévő `clients` tábla) ─────────────────────────────────────


@router.get("/clients")
def ugyfelek(q: str | None = None, limit: int = Query(default=20, le=200), db: Session = Depends(get_db),
             _u: Employee = Depends(_jog("view"))):
    s = select(Client)
    if q and q.strip():
        s = s.where(Client.nev.ilike(f"%{q.strip()}%"))
    return [{"id": c.id, "nev": c.nev, "adoszam": c.adoszam, "szekhely": c.szekhely}
            for c in db.scalars(s.order_by(Client.nev).limit(limit))]


@router.post("/clients", status_code=201)
def ugyfel_uj(body: Q.UgyfelIn, db: Session = Depends(get_db), _u: Employee = Depends(_jog("create"))):
    """Új ügyfél felvétele az ajánlat indításakor. Ha azonos nevű már van, azt adja vissza."""
    nev = body.nev.strip()
    c = db.scalar(select(Client).where(func.lower(Client.nev) == nev.lower()))
    if c is None:
        c = Client(nev=nev, adoszam=body.adoszam, szekhely=body.szekhely)
        db.add(c)
        db.commit()
    return {"id": c.id, "nev": c.nev, "adoszam": c.adoszam, "szekhely": c.szekhely}


# ── Sablonok ─────────────────────────────────────────────────────────────────


def _sablon_vagy_404(db: Session, template_id: int) -> QuoteTemplate:
    t = db.get(QuoteTemplate, template_id)
    if t is None:
        raise HTTPException(status_code=404, detail="Nincs ilyen sablon.")
    return t


def _sablon_ellenorzes(adat: dict) -> None:
    if adat.get("brand") is not None and adat["brand"] not in ("HYPE", "CB"):
        raise HTTPException(status_code=400, detail="Érvénytelen márka.")
    if adat.get("pricing_mode") is not None and adat["pricing_mode"] not in ("one_off", "monthly"):
        raise HTTPException(status_code=400, detail="Érvénytelen árazási mód.")


@router.get("/templates")
def sablonok(include_inactive: bool = False, db: Session = Depends(get_db), _u: Employee = Depends(_jog("view"))):
    s = select(QuoteTemplate)
    if not include_inactive:
        s = s.where(QuoteTemplate.is_active.is_(True))
    return [_sablon(t) for t in db.scalars(s.order_by(QuoteTemplate.sort_order, QuoteTemplate.id))]


@router.post("/templates", status_code=201)
def sablon_uj(body: Q.SablonIn, db: Session = Depends(get_db), _u: Employee = Depends(_jog("edit"))):
    adat = body.model_dump()
    _sablon_ellenorzes(adat)
    if adat["sort_order"] is None:
        adat["sort_order"] = (db.scalar(select(func.max(QuoteTemplate.sort_order))) or 0) + 10
    t = QuoteTemplate(**adat)
    db.add(t)
    db.commit()
    return _sablon(t, True)


@router.post("/templates/from-quote/{quote_id}", status_code=201)
def sablon_ajanlatbol(quote_id: int, body: Q.SablonAjanlatbolIn, db: Session = Depends(get_db),
                      _u: Employee = Depends(_jog("edit"))):
    q = _ajanlat_vagy_404(db, quote_id)
    try:
        t = S.sablon_ajanlatbol(db, q, body.name, body.description)
    except (S.AjanlatHiba, S.NincsMeg) as exc:
        raise _hiba(exc) from exc
    db.commit()
    return _sablon(t, True)


@router.get("/templates/{template_id}")
def sablon(template_id: int, db: Session = Depends(get_db), _u: Employee = Depends(_jog("view"))):
    return _sablon(_sablon_vagy_404(db, template_id), True)


@router.patch("/templates/{template_id}")
def sablon_modosit(template_id: int, body: Q.SablonPatch, db: Session = Depends(get_db),
                   _u: Employee = Depends(_jog("edit"))):
    t = _sablon_vagy_404(db, template_id)
    adat = _nem_null(body.model_dump(exclude_unset=True),
                     ("name", "brand", "pricing_mode", "sort_order", "is_active"))
    _sablon_ellenorzes(adat)
    for mezo, ertek in adat.items():
        setattr(t, mezo, ertek)
    db.commit()
    return _sablon(t, True)


@router.delete("/templates/{template_id}", status_code=204)
def sablon_torol(template_id: int, db: Session = Depends(get_db), _u: Employee = Depends(_jog("edit"))):
    """A sablon törlése a belőle készült ajánlatokat nem érinti (csak a
    „honnan indult” hivatkozás ürül)."""
    db.delete(_sablon_vagy_404(db, template_id))
    db.commit()
    return Response(status_code=204)


@router.get("/templates/{template_id}/items")
def sablon_sorok(template_id: int, db: Session = Depends(get_db), _u: Employee = Depends(_jog("view"))):
    return _sablon(_sablon_vagy_404(db, template_id), True)["items"]


def _sablon_sor_ellenorzes(db: Session, adat: dict) -> None:
    if adat.get("catalog_item_id") is not None and db.get(QuoteCatalogItem, adat["catalog_item_id"]) is None:
        raise HTTPException(status_code=400, detail="Nincs ilyen katalógus-tétel.")
    if adat.get("unit_override") is not None and adat["unit_override"] not in EGYSEGEK:
        raise HTTPException(status_code=400, detail="Érvénytelen egység.")


@router.post("/templates/{template_id}/items", status_code=201)
def sablon_sor_uj(template_id: int, body: Q.SablonSorIn, db: Session = Depends(get_db),
                  _u: Employee = Depends(_jog("edit"))):
    t = _sablon_vagy_404(db, template_id)
    adat = body.model_dump()
    _sablon_sor_ellenorzes(db, adat)
    if adat["catalog_item_id"] is None and not (adat.get("name_override") or "").strip():
        raise HTTPException(status_code=400, detail="Egyedi sornál adj meg megnevezést.")
    t.items.append(QuoteTemplateItem(**adat, sort_order=(max((x.sort_order for x in t.items), default=0) + 10)))
    db.commit()
    db.refresh(t)
    return _sablon(t, True)


@router.patch("/templates/{template_id}/items/reorder")
def sablon_sorrend(template_id: int, body: Q.SorrendIn, db: Session = Depends(get_db),
                   _u: Employee = Depends(_jog("edit"))):
    t = _sablon_vagy_404(db, template_id)
    ids = [x.id for x in body.items]
    if sorted(ids) != sorted(x.id for x in t.items):
        raise HTTPException(status_code=400, detail="A sorrendnek a sablon összes sorát tartalmaznia kell.")
    by_id = {x.id: x for x in t.items}
    for poz, elem in enumerate(body.items):
        by_id[elem.id].sort_order = (poz + 1) * 10
        if "section" in elem.model_fields_set:
            by_id[elem.id].section = elem.section or None
    db.commit()
    db.refresh(t)
    return _sablon(t, True)


@router.patch("/templates/{template_id}/items/{item_id}")
def sablon_sor_modosit(template_id: int, item_id: int, body: Q.SablonSorPatch, db: Session = Depends(get_db),
                       _u: Employee = Depends(_jog("edit"))):
    t = _sablon_vagy_404(db, template_id)
    ts = next((x for x in t.items if x.id == item_id), None)
    if ts is None:
        raise HTTPException(status_code=404, detail="Nincs ilyen sablonsor.")
    adat = _nem_null(body.model_dump(exclude_unset=True), ("default_occasions", "default_quantity", "is_optional"))
    _sablon_sor_ellenorzes(db, adat)
    for mezo, ertek in adat.items():
        setattr(ts, mezo, ertek)
    db.commit()
    db.refresh(t)
    return _sablon(t, True)


@router.delete("/templates/{template_id}/items/{item_id}")
def sablon_sor_torol(template_id: int, item_id: int, db: Session = Depends(get_db),
                     _u: Employee = Depends(_jog("edit"))):
    t = _sablon_vagy_404(db, template_id)
    ts = next((x for x in t.items if x.id == item_id), None)
    if ts is None:
        raise HTTPException(status_code=404, detail="Nincs ilyen sablonsor.")
    t.items.remove(ts)
    db.commit()
    db.refresh(t)
    return _sablon(t, True)


# ── Alapadatok ───────────────────────────────────────────────────────────────


@router.post("/seed")
def alapadatok(db: Session = Depends(get_db), _u: Employee = Depends(_jog("edit"))):
    """A 98 katalógus-tétel, 10 sablon és a standard megjegyzés betöltése.
    Idempotens: a már meglévőt (és a felületen átírtat) nem írja felül."""
    from app.quotes.seed import seed

    eredmeny = seed(db)
    db.commit()
    return eredmeny


# ── Ajánlatok ────────────────────────────────────────────────────────────────


@router.get("")
def ajanlatok(
    status: str | None = None, brand: str | None = None, client_id: int | None = None,
    date_from: date | None = None, date_to: date | None = None, q: str | None = None,
    limit: int = Query(default=500, le=2000),
    db: Session = Depends(get_db), _u: Employee = Depends(_jog("view")),
):
    sorok = S.lista(db, status=status, brand=brand, client_id=client_id, datum_tol=date_from, datum_ig=date_to,
                    q=q, limit=limit)
    ids = {x.client_id for x in sorok if x.client_id}
    ugyfelek = dict(db.execute(select(Client.id, Client.nev).where(Client.id.in_(ids))).all()) if ids else {}
    return [_lista_elem(x, ugyfelek) for x in sorok]


@router.post("", status_code=201)
def ajanlat_uj(body: Q.AjanlatIn, db: Session = Depends(get_db), user: Employee = Depends(_jog("create"))):
    try:
        q = S.letrehoz(db, user, body.model_dump(exclude_unset=True))
    except (S.AjanlatHiba, S.NincsMeg) as exc:
        raise _hiba(exc) from exc
    db.commit()
    return _ajanlat(db, q)


@router.get("/{quote_id}")
def ajanlat(quote_id: int, db: Session = Depends(get_db), _u: Employee = Depends(_jog("view"))):
    return _ajanlat(db, _ajanlat_vagy_404(db, quote_id))


@router.patch("/{quote_id}")
def ajanlat_modosit(quote_id: int, body: Q.AjanlatPatch, db: Session = Depends(get_db),
                    _u: Employee = Depends(_jog("edit"))):
    q = _ajanlat_vagy_404(db, quote_id)
    adat = _nem_null(body.model_dump(exclude_unset=True), (
        "brand", "project_name", "status", "pricing_mode", "months", "discount_percent", "discount_amount",
        "vat_percent"))
    try:
        S.modosit(db, q, adat)
    except (S.AjanlatHiba, S.NincsMeg) as exc:
        raise _hiba(exc) from exc
    db.commit()
    return _ajanlat(db, q)


@router.delete("/{quote_id}", status_code=204)
def ajanlat_torol(quote_id: int, db: Session = Depends(get_db), _u: Employee = Depends(_jog("delete"))):
    q = _ajanlat_vagy_404(db, quote_id)
    db.delete(q)
    db.commit()
    return Response(status_code=204)


_SOR_KOTELEZO = ("name", "occasions", "quantity", "unit_price", "line_discount_percent", "is_optional")


@router.post("/{quote_id}/items", status_code=201)
def sor_uj(quote_id: int, body: Q.SorIn, db: Session = Depends(get_db), _u: Employee = Depends(_jog("edit"))):
    q = _ajanlat_vagy_404(db, quote_id)
    try:
        S.sor_hozzaad(db, q, body.model_dump())
    except (S.AjanlatHiba, S.NincsMeg) as exc:
        raise _hiba(exc) from exc
    db.commit()
    return _ajanlat(db, q)


@router.post("/{quote_id}/items/from-catalog", status_code=201)
def sor_katalogusbol(quote_id: int, body: Q.KatalogusbolIn, db: Session = Depends(get_db),
                     _u: Employee = Depends(_jog("edit"))):
    q = _ajanlat_vagy_404(db, quote_id)
    try:
        S.katalogusbol(db, q, body.catalog_item_id, body.section)
    except (S.AjanlatHiba, S.NincsMeg) as exc:
        raise _hiba(exc) from exc
    db.commit()
    return _ajanlat(db, q)


@router.patch("/{quote_id}/items/reorder")
def sor_sorrend(quote_id: int, body: Q.SorrendIn, db: Session = Depends(get_db),
                _u: Employee = Depends(_jog("edit"))):
    q = _ajanlat_vagy_404(db, quote_id)
    try:
        S.atrendez(db, q, [e.model_dump(include={"id"} | ({"section"} & e.model_fields_set)) for e in body.items])
    except (S.AjanlatHiba, S.NincsMeg) as exc:
        raise _hiba(exc) from exc
    db.commit()
    return _ajanlat(db, q)


@router.patch("/{quote_id}/items/{item_id}")
def sor_modosit(quote_id: int, item_id: int, body: Q.SorPatch, db: Session = Depends(get_db),
                _u: Employee = Depends(_jog("edit"))):
    q = _ajanlat_vagy_404(db, quote_id)
    try:
        S.sor_modosit(db, q, item_id, _nem_null(body.model_dump(exclude_unset=True), _SOR_KOTELEZO))
    except (S.AjanlatHiba, S.NincsMeg) as exc:
        raise _hiba(exc) from exc
    db.commit()
    return _ajanlat(db, q)


@router.post("/{quote_id}/items/{item_id}/duplicate", status_code=201)
def sor_duplikal(quote_id: int, item_id: int, db: Session = Depends(get_db), _u: Employee = Depends(_jog("edit"))):
    q = _ajanlat_vagy_404(db, quote_id)
    try:
        S.sor_duplikal(db, q, item_id)
    except (S.AjanlatHiba, S.NincsMeg) as exc:
        raise _hiba(exc) from exc
    db.commit()
    return _ajanlat(db, q)


@router.delete("/{quote_id}/items/{item_id}")
def sor_torol(quote_id: int, item_id: int, db: Session = Depends(get_db), _u: Employee = Depends(_jog("edit"))):
    q = _ajanlat_vagy_404(db, quote_id)
    try:
        S.sor_torol(db, q, item_id)
    except (S.AjanlatHiba, S.NincsMeg) as exc:
        raise _hiba(exc) from exc
    db.commit()
    return _ajanlat(db, q)


@router.post("/{quote_id}/duplicate", status_code=201)
def variant_duplikal(quote_id: int, db: Session = Depends(get_db), user: Employee = Depends(_jog("create"))):
    uj = S.duplikal(db, user, _ajanlat_vagy_404(db, quote_id))
    db.commit()
    return _ajanlat(db, uj)


@router.post("/{quote_id}/new-version", status_code=201)
def uj_verzio(quote_id: int, db: Session = Depends(get_db), user: Employee = Depends(_jog("create"))):
    uj = S.uj_verzio(db, user, _ajanlat_vagy_404(db, quote_id))
    db.commit()
    return _ajanlat(db, uj)


@router.post("/{quote_id}/refresh-prices")
def arak_frissitese(quote_id: int, body: Q.ArFrissitesIn | None = None, db: Session = Depends(get_db),
                    _u: Employee = Depends(_jog("edit"))):
    q = _ajanlat_vagy_404(db, quote_id)
    db_frissult = S.arak_frissitese(db, q, (body or Q.ArFrissitesIn()).item_ids)
    db.commit()
    return {**_ajanlat(db, q), "refreshed": db_frissult}


@router.get("/{quote_id}/client-prices")
def ugyfel_arai(quote_id: int, db: Session = Depends(get_db), _u: Employee = Depends(_jog("view"))):
    """Az ajánlat ügyfelének legutóbb adott árak katalógus-tételenként (a
    katalógus-panel tippje) - ügyfél nélkül üres."""
    q = _ajanlat_vagy_404(db, quote_id)
    if not q.client_id:
        return {}
    return {str(k): v for k, v in S.utolso_ar(db, None, q.client_id, kiveve_quote_id=q.id).items()}


def _letoltes(tartalom: bytes, nev: str, mime: str) -> Response:
    import unicodedata

    ascii_nev = unicodedata.normalize("NFKD", nev).encode("ascii", "ignore").decode() or "arajanlat"
    return Response(
        content=tartalom, media_type=mime,
        headers={"Content-Disposition": f"attachment; filename=\"{ascii_nev}\"; filename*=UTF-8''{url_quote(nev)}"},
    )


@router.get("/{quote_id}/export.xlsx")
def export_xlsx(quote_id: int, db: Session = Depends(get_db), _u: Employee = Depends(_jog("view"))):
    q = _ajanlat_vagy_404(db, quote_id)
    return _letoltes(E.xlsx(db, q), E.fajlnev(db, q, "xlsx"),
                     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@router.get("/{quote_id}/export.pdf")
def export_pdf(quote_id: int, db: Session = Depends(get_db), _u: Employee = Depends(_jog("view"))):
    q = _ajanlat_vagy_404(db, quote_id)
    return _letoltes(E.pdf(db, q), E.fajlnev(db, q, "pdf"), "application/pdf")
