"""Az árajánlat-készítő üzleti logikája: számozás, sablonból létrehozás,
tételkezelés (ár-snapshot), variáns / új verzió, sablon mentése ajánlatból,
katalógus-átárazás ártörténettel. A hívó commitál."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.employee import Employee
from app.models.quote import (
    ARAZASI_MODOK,
    BRANDEK,
    EGYSEGEK,
    STATUSZOK,
    Quote,
    QuoteCatalogItem,
    QuoteCatalogPriceHistory,
    QuoteItem,
    QuoteNotePreset,
    QuoteNumberCounter,
    QuoteTemplate,
    QuoteTemplateItem,
)
from app.quotes.szamitas import Osszesites, osszesit

SZAM_ELOTAG = {"HYPE": "HYPE", "CB": "CB"}
ALAP_CIMKE = "A PROJECT TELJES KÖLTSÉGE"


class AjanlatHiba(ValueError):
    """Érvénytelen kérés (400)."""


class NincsMeg(LookupError):
    """Nem létező rekord (404)."""


def _most() -> datetime:
    return datetime.now(timezone.utc)


def _ellenoriz(ertek, megengedett: tuple[str, ...], mit: str):
    if ertek is not None and ertek not in megengedett:
        raise AjanlatHiba(f"Érvénytelen {mit}: {ertek}")


# ── Számozás ─────────────────────────────────────────────────────────────────


def kovetkezo_szam(db: Session, brand: str, ev: int | None = None) -> str:
    """Évente újrainduló sorszám márkánként: HYPE-2026-0001, CB-2026-0001."""
    _ellenoriz(brand, BRANDEK, "márka")
    ev = ev or _most().year
    sz = db.scalar(
        select(QuoteNumberCounter)
        .where(QuoteNumberCounter.brand == brand, QuoteNumberCounter.year == ev)
        .with_for_update()
    )
    if sz is None:
        # Első ajánlat az évben: a meglévő számokból indulunk (ha valaki kézzel
        # vitt fel számot), különben 1-ről.
        elotag = f"{SZAM_ELOTAG[brand]}-{ev}-"
        utolso = db.scalar(select(func.max(Quote.number)).where(Quote.number.like(f"{elotag}%")))
        kezdo = int(utolso.rsplit("-", 1)[-1]) if utolso and utolso.rsplit("-", 1)[-1].isdigit() else 0
        sz = QuoteNumberCounter(brand=brand, year=ev, last=kezdo)
        db.add(sz)
    sz.last += 1
    db.flush()
    return f"{SZAM_ELOTAG[brand]}-{ev}-{sz.last:04d}"


# ── Összegzés ────────────────────────────────────────────────────────────────


def osszegzes(q: Quote) -> Osszesites:
    return osszesit(
        q.items, kedvezmeny_szazalek=q.discount_percent, kedvezmeny_osszeg=q.discount_amount,
        afa_szazalek=q.vat_percent, arazas=q.pricing_mode, honapok=q.months,
    )


def ujraszamol(q: Quote) -> Osszesites:
    o = osszegzes(q)
    q.net_total = o.netto
    return o


def _atszamoz(q: Quote) -> None:
    for i, it in enumerate(sorted(q.items, key=lambda x: (x.sort_order, x.id or 0))):
        it.sort_order = (i + 1) * 10


# ── Létrehozás sablonból ─────────────────────────────────────────────────────


def sablon_sorbol(ts: QuoteTemplateItem) -> dict:
    c = ts.catalog_item
    return {
        "catalog_item_id": ts.catalog_item_id,
        "section": ts.section,
        "name": ts.name_override or (c.name if c else ""),
        "description": ts.description_override if ts.description_override is not None
        else (c.default_description if c else None),
        "unit": ts.unit_override or (c.unit if c else None),
        "occasions": ts.default_occasions,
        "quantity": ts.default_quantity,
        "unit_price": ts.price_override if ts.price_override is not None else (c.base_price if c else 0),
        "is_optional": ts.is_optional,
    }


def sablon_osszeg(t: QuoteTemplate) -> int:
    """A sablon alap-végösszege (opcionális sorok nélkül) - a kártyán."""
    sorok = [QuoteItem(**{**sablon_sorbol(ts), "line_discount_percent": 0}) for ts in t.items]
    return osszesit(sorok, arazas=t.pricing_mode).netto


def _alap_megjegyzes(db: Session, t: QuoteTemplate | None) -> str | None:
    if t is not None and t.default_note_id:
        n = db.get(QuoteNotePreset, t.default_note_id)
        if n is not None:
            return n.text
    n = db.scalar(select(QuoteNotePreset).order_by(QuoteNotePreset.sort_order, QuoteNotePreset.id).limit(1))
    return n.text if n is not None else None


FEJ_MEZOK = (
    "brand", "client_id", "project_name", "event_date_from", "event_date_to", "location", "status",
    "pricing_mode", "months", "discount_percent", "discount_amount", "vat_percent", "summary_label",
    "occasions_label", "note_text", "internal_note",
)


def _fej_ellenorzes(db: Session, adat: dict) -> None:
    _ellenoriz(adat.get("brand"), BRANDEK, "márka")
    _ellenoriz(adat.get("status"), STATUSZOK, "státusz")
    _ellenoriz(adat.get("pricing_mode"), ARAZASI_MODOK, "árazási mód")
    if adat.get("client_id") is not None and db.get(Client, adat["client_id"]) is None:
        raise AjanlatHiba("Nincs ilyen ügyfél.")
    if adat.get("months") is not None and adat["months"] < 1:
        raise AjanlatHiba("A hónapok száma legalább 1.")
    pct = adat.get("discount_percent")
    if pct is not None and not (0 <= pct <= 100):
        raise AjanlatHiba("A kedvezmény 0 és 100% között lehet.")
    if adat.get("discount_amount") is not None and adat["discount_amount"] < 0:
        raise AjanlatHiba("A kedvezmény összege nem lehet negatív.")


def letrehoz(db: Session, user: Employee | None, adat: dict) -> Quote:
    """Új ajánlat - `template_id` esetén a sablon sorai töltik fel (az
    opcionális sablonsorok opcionálisként kerülnek be)."""
    adat = {k: v for k, v in adat.items() if v is not None}
    _fej_ellenorzes(db, adat)
    t = None
    if adat.get("template_id"):
        t = db.get(QuoteTemplate, adat["template_id"])
        if t is None:
            raise NincsMeg("Nincs ilyen sablon.")
    brand = adat.get("brand") or (t.brand if t else "HYPE")
    q = Quote(
        number=kovetkezo_szam(db, brand), brand=brand, version=1, status="draft",
        pricing_mode=adat.get("pricing_mode") or (t.pricing_mode if t else "one_off"),
        summary_label=adat.get("summary_label") or (t.summary_label if t else None) or ALAP_CIMKE,
        occasions_label=adat.get("occasions_label") or (t.occasions_label if t else None),
        template_id=t.id if t else None,
        note_text=adat["note_text"] if "note_text" in adat else _alap_megjegyzes(db, t),
        created_by=user.id if user else None,
    )
    for k in FEJ_MEZOK:
        if k in adat and k not in ("brand", "status", "pricing_mode", "summary_label", "occasions_label", "note_text"):
            setattr(q, k, adat[k])
    db.add(q)
    if t is not None:
        for i, ts in enumerate(t.items):
            q.items.append(QuoteItem(**sablon_sorbol(ts), sort_order=(i + 1) * 10))
    ujraszamol(q)
    db.flush()
    return q


def modosit(db: Session, q: Quote, adat: dict) -> Quote:
    _fej_ellenorzes(db, adat)
    if adat.get("brand") and adat["brand"] != q.brand:
        # A szám márkánként fut: márkaváltásnál új számot kap - de csak ha még
        # nincs másik verziója ugyanezen a számon.
        tobb = db.scalar(select(func.count()).select_from(Quote).where(Quote.number == q.number, Quote.id != q.id))
        if tobb:
            raise AjanlatHiba("Ennek az ajánlatnak már több verziója van - a márka nem váltható.")
        q.number = kovetkezo_szam(db, adat["brand"])
    for k, v in adat.items():
        if k in FEJ_MEZOK:
            setattr(q, k, v)
    if adat.get("status") == "sent" and q.sent_at is None:
        q.sent_at = _most()
    ujraszamol(q)
    db.flush()
    return q


# ── Tételek ──────────────────────────────────────────────────────────────────

SOR_MEZOK = ("section", "name", "description", "occasions", "quantity", "unit", "unit_price",
             "line_discount_percent", "is_optional", "catalog_item_id")


def _sor_ellenorzes(adat: dict) -> None:
    _ellenoriz(adat.get("unit"), EGYSEGEK, "egység")
    for k in ("occasions", "quantity", "unit_price"):
        if adat.get(k) is not None and adat[k] < 0:
            raise AjanlatHiba("Az alkalom, a mennyiség és az egységár nem lehet negatív.")
    p = adat.get("line_discount_percent")
    if p is not None and not (0 <= p <= 100):
        raise AjanlatHiba("A sorkedvezmény 0 és 100% között lehet.")


def _beszur(q: Quote, it: QuoteItem, szekcio: str | None, utan: int | None = None) -> None:
    """A sor a szekciója végére (vagy egy adott sor után) kerül."""
    sorok = sorted(q.items, key=lambda x: x.sort_order)
    if utan is not None:
        cel = next((x for x in sorok if x.id == utan), None)
        poz = cel.sort_order + 5 if cel else (sorok[-1].sort_order + 10 if sorok else 10)
    else:
        szekcio_sorai = [x for x in sorok if (x.section or None) == (szekcio or None)]
        poz = (szekcio_sorai[-1].sort_order + 5) if szekcio_sorai else ((sorok[-1].sort_order + 10) if sorok else 10)
    it.sort_order = poz
    q.items.append(it)
    _atszamoz(q)


def sor_hozzaad(db: Session, q: Quote, adat: dict) -> QuoteItem:
    _sor_ellenorzes(adat)
    utan = adat.pop("after_item_id", None)
    it = QuoteItem(**{k: v for k, v in adat.items() if k in SOR_MEZOK and v is not None})
    _beszur(q, it, it.section, utan)
    ujraszamol(q)
    db.flush()
    return it


def katalogusbol(db: Session, q: Quote, catalog_item_id: int, section: str | None = None) -> QuoteItem:
    c = db.get(QuoteCatalogItem, catalog_item_id)
    if c is None:
        raise NincsMeg("Nincs ilyen katalógus-tétel.")
    it = QuoteItem(
        catalog_item_id=c.id, section=section, name=c.name, description=c.default_description,
        unit=c.unit, occasions=1, quantity=1, unit_price=c.base_price,
    )
    _beszur(q, it, section)
    ujraszamol(q)
    db.flush()
    return it


def sor(q: Quote, item_id: int) -> QuoteItem:
    it = next((x for x in q.items if x.id == item_id), None)
    if it is None:
        raise NincsMeg("Nincs ilyen sor az ajánlatban.")
    return it


def sor_modosit(db: Session, q: Quote, item_id: int, adat: dict) -> QuoteItem:
    it = sor(q, item_id)
    _sor_ellenorzes(adat)
    if "catalog_item_id" in adat and adat["catalog_item_id"] is not None:
        # Csere (pl. LED fal P4.8 → P3.9): a katalógus-tétel adatai bemásolódnak.
        c = db.get(QuoteCatalogItem, adat["catalog_item_id"])
        if c is None:
            raise NincsMeg("Nincs ilyen katalógus-tétel.")
        it.catalog_item_id, it.name, it.description, it.unit, it.unit_price = (
            c.id, c.name, c.default_description, c.unit, c.base_price)
        adat = {k: v for k, v in adat.items() if k != "catalog_item_id"}
    for k, v in adat.items():
        if k in SOR_MEZOK:
            setattr(it, k, v)
    ujraszamol(q)
    db.flush()
    return it


def sor_torol(db: Session, q: Quote, item_id: int) -> None:
    it = sor(q, item_id)
    q.items.remove(it)
    db.delete(it)
    ujraszamol(q)
    db.flush()


def sor_duplikal(db: Session, q: Quote, item_id: int) -> QuoteItem:
    it = sor(q, item_id)
    uj = QuoteItem(**{k: getattr(it, k) for k in SOR_MEZOK})
    _beszur(q, uj, it.section, utan=it.id)
    ujraszamol(q)
    db.flush()
    return uj


def atrendez(db: Session, q: Quote, sorrend: list[dict]) -> None:
    """`sorrend`: [{"id": 5, "section": "Eszközök"}, ...] - a lista sorrendje az
    új sorrend; a `section` kulcs (ha van) át is helyezi a sort."""
    ids = [x["id"] for x in sorrend]
    if sorted(ids) != sorted(i.id for i in q.items):
        raise AjanlatHiba("A sorrendnek az ajánlat összes sorát pontosan egyszer kell tartalmaznia.")
    by_id = {i.id: i for i in q.items}
    for poz, x in enumerate(sorrend):
        it = by_id[x["id"]]
        it.sort_order = (poz + 1) * 10
        if "section" in x:
            it.section = x["section"] or None
    db.flush()


def arak_frissitese(db: Session, q: Quote, item_ids: list[int] | None) -> int:
    """A kijelölt (None: minden katalógusos) sor ára a mostani katalógusárra."""
    db_frissult = 0
    for it in q.items:
        if it.catalog_item_id is None or (item_ids is not None and it.id not in item_ids):
            continue
        c = db.get(QuoteCatalogItem, it.catalog_item_id)
        if c is not None and it.unit_price != c.base_price:
            it.unit_price = c.base_price
            db_frissult += 1
    ujraszamol(q)
    db.flush()
    return db_frissult


# ── Variáns, új verzió, sablon mentése ───────────────────────────────────────


def _masol(q: Quote, uj: Quote) -> Quote:
    for k in FEJ_MEZOK:
        if k not in ("status", "brand"):
            setattr(uj, k, getattr(q, k))
    uj.template_id = q.template_id
    for it in sorted(q.items, key=lambda x: x.sort_order):
        uj.items.append(QuoteItem(**{k: getattr(it, k) for k in SOR_MEZOK}, sort_order=it.sort_order))
    ujraszamol(uj)
    return uj


def duplikal(db: Session, user: Employee | None, q: Quote) -> Quote:
    """Új VARIÁNS (pl. „2 kamerás” / „3 kamerás”): új szám, a lánc az eredetire mutat."""
    uj = Quote(number=kovetkezo_szam(db, q.brand), brand=q.brand, version=1, status="draft",
               parent_quote_id=q.id, created_by=user.id if user else None)
    db.add(_masol(q, uj))
    db.flush()
    return uj


def uj_verzio(db: Session, user: Employee | None, q: Quote) -> Quote:
    """v2, v3…: ugyanaz a szám, eggyel nagyobb verzió."""
    max_v = db.scalar(select(func.max(Quote.version)).where(Quote.number == q.number)) or q.version
    uj = Quote(number=q.number, brand=q.brand, version=max_v + 1, status="draft",
               parent_quote_id=q.id, created_by=user.id if user else None)
    db.add(_masol(q, uj))
    db.flush()
    return uj


def sablon_ajanlatbol(db: Session, q: Quote, nev: str, leiras: str | None = None) -> QuoteTemplate:
    if not (nev or "").strip():
        raise AjanlatHiba("Adj nevet a sablonnak.")
    t = QuoteTemplate(
        name=nev.strip(), description=leiras, brand=q.brand, pricing_mode=q.pricing_mode,
        summary_label=q.summary_label, occasions_label=q.occasions_label,
        sort_order=(db.scalar(select(func.max(QuoteTemplate.sort_order))) or 0) + 10,
    )
    for i, it in enumerate(sorted(q.items, key=lambda x: x.sort_order)):
        c = db.get(QuoteCatalogItem, it.catalog_item_id) if it.catalog_item_id else None
        t.items.append(QuoteTemplateItem(
            catalog_item_id=c.id if c else None, section=it.section,
            name_override=None if c and c.name == it.name else it.name,
            description_override=None if c and (c.default_description or None) == (it.description or None)
            else it.description,
            unit_override=None if c and c.unit == it.unit else it.unit,
            default_occasions=it.occasions, default_quantity=it.quantity,
            price_override=None if c and c.base_price == it.unit_price else it.unit_price,
            is_optional=it.is_optional, sort_order=(i + 1) * 10,
        ))
    db.add(t)
    db.flush()
    return t


# ── Katalógus ────────────────────────────────────────────────────────────────


def katalogus_ar(db: Session, c: QuoteCatalogItem, uj_ar: int, user: Employee | None) -> None:
    """Átárazás ártörténettel. A meglévő ajánlatok NEM változnak (ár-snapshot)."""
    if uj_ar < 0:
        raise AjanlatHiba("Az ár nem lehet negatív.")
    if uj_ar == c.base_price:
        return
    db.add(QuoteCatalogPriceHistory(catalog_item_id=c.id, old_price=c.base_price, new_price=uj_ar,
                                    changed_by=user.id if user else None))
    c.base_price = uj_ar
    c.updated_by = user.id if user else None


def utolso_ar(db: Session, catalog_item_ids: list[int] | None, client_id: int, kiveve_quote_id: int | None = None
              ) -> dict[int, dict]:
    """Az adott ügyfélnek legutóbb adott ár tételenként (tipp a felületen)."""
    q = (
        select(QuoteItem.catalog_item_id, QuoteItem.unit_price, Quote.number, Quote.version, Quote.created_at)
        .join(Quote, Quote.id == QuoteItem.quote_id)
        .where(Quote.client_id == client_id, QuoteItem.catalog_item_id.is_not(None))
        .order_by(Quote.created_at.desc(), Quote.id.desc())
    )
    if catalog_item_ids is not None:
        q = q.where(QuoteItem.catalog_item_id.in_(catalog_item_ids))
    if kiveve_quote_id is not None:
        q = q.where(Quote.id != kiveve_quote_id)
    ki: dict[int, dict] = {}
    for cid, ar, szam, verzio, mikor in db.execute(q).all():
        if cid not in ki:
            ki[cid] = {"unit_price": ar, "quote_number": szam, "version": verzio,
                       "date": mikor.date().isoformat() if mikor else None}
    return ki


def lista(db: Session, *, status: str | None = None, brand: str | None = None, client_id: int | None = None,
          datum_tol=None, datum_ig=None, q: str | None = None, limit: int = 500) -> list[Quote]:
    s = select(Quote)
    if status:
        s = s.where(Quote.status == status)
    if brand:
        s = s.where(Quote.brand == brand)
    if client_id:
        s = s.where(Quote.client_id == client_id)
    if datum_tol:
        s = s.where(func.coalesce(Quote.event_date_from, func.date(Quote.created_at)) >= datum_tol)
    if datum_ig:
        s = s.where(func.coalesce(Quote.event_date_from, func.date(Quote.created_at)) <= datum_ig)
    if q and q.strip():
        minta = f"%{q.strip()}%"
        s = s.outerjoin(Client, Client.id == Quote.client_id).where(or_(
            Quote.number.ilike(minta), Quote.project_name.ilike(minta), Quote.location.ilike(minta),
            Client.nev.ilike(minta),
        ))
    return list(db.scalars(s.order_by(Quote.created_at.desc(), Quote.id.desc()).limit(limit)))
