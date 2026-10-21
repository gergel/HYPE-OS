"""Globális kereső - a TopBar jobb felső "Keresés bármiben…" mezője mögötti
végpont: EGY lekérdezéssel végigmegy az összes olyan entitástípuson, amit a
bejelentkezett felhasználó egyáltalán megnézhet, és típusonként csoportosítva
adja vissza a találatokat, kész linkkel a rekord részletnézetére.

Jogosultság: pontosan ugyanaz a check_page_action (lásd core/security.py),
amit a listaoldalak és az AI Assistant is használ - amihez a felhasználónak
nincs "view" joga, arra rá se keresünk, tehát a kereső sosem szivárogtathat
ki olyan rekordot, amit a UI-n egyébként nem látna.

Miért kell külön keresőmező-lista entitásonként (SEARCH_FIELDS) ahelyett,
hogy minden szöveges oszlopban keresnénk? Mert a táblák nagyon szélesek (a
Project ~80 oszlop), és a legtöbb oszlop technikai (URL-ek, thread-id-k,
státusz-flagek) - ezekben keresve a találatok nagy része értelmezhetetlen
lenne a felhasználónak, a lekérdezés pedig feleslegesen lassú."""

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import String, cast, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import check_page_action, get_current_user
from app.models.employee import Employee
from app.services.entity_registry import ENTITY_MODELS

router = APIRouter(prefix="/search", tags=["search"])


@dataclass(frozen=True)
class SearchEntity:
    """Egy entitástípus keresési leírója.

    page: a jogosultsági "oldal" kulcs (lásd frontend/lib/nav.ts) - ezzel
      döntjük el, hogy az adott felhasználónak megmutathatjuk-e egyáltalán.
    label/sublabel: melyik mezőt mutassuk a találat fő- ill. alcímeként.
    fields: ezekben az oszlopokban keresünk (lásd modul-docstring).
    href: a részletnézet útvonala a frontenden, {id} helyőrzővel.
    """

    title: str
    page: str
    href: str
    label: str
    fields: tuple[str, ...]
    sublabel: tuple[str, ...] = field(default_factory=tuple)


# A sorrend a találati lista csoport-sorrendje is egyben.
SEARCH_ENTITIES: dict[str, SearchEntity] = {
    "project": SearchEntity(
        title="Projektek",
        page="/projektek",
        href="/projektek/{id}",
        label="nev",
        fields=("nev", "projektkod_szoveg", "helyszin", "esemeny", "description"),
        sublabel=("projektkod_szoveg", "helyszin"),
    ),
    "projectCode": SearchEntity(
        title="Project Code-ok",
        page="/projektek/project-kodok",
        href="/projektek/project-kodok/{id}",
        label="projektkod",
        fields=("projektkod", "szerzodes_targya", "megjegyzes"),
        sublabel=("esemeny_allapota",),
    ),
    "client": SearchEntity(
        title="Ügyfelek",
        page="/ugyfelek",
        href="/ugyfelek/{id}",
        label="nev",
        fields=("nev", "adoszam", "szekhely", "kepviselo"),
        sublabel=("szekhely",),
    ),
    "employee": SearchEntity(
        title="Csapat",
        page="/csapat",
        href="/csapat/{id}",
        label="full_name",
        fields=("full_name", "email", "telefon", "vallakozas_neve", "vallalkozas_adoszama"),
        sublabel=("tipus", "email"),
    ),
    "equipment": SearchEntity(
        title="Eszközök",
        page="/felszereles",
        href="/felszereles/{id}",
        label="nev",
        fields=("nev", "serial_number", "kategoria", "qr_kod", "megjegyzes"),
        sublabel=("kategoria", "serial_number"),
    ),
    "campaign": SearchEntity(
        title="Kampányok",
        page="/kampanyok",
        href="/kampanyok/{id}",
        label="nev",
        fields=("nev", "leiras", "kampany_statusza"),
        sublabel=("kampany_statusza",),
    ),
    "task": SearchEntity(
        title="Feladatok",
        page="/feladatok",
        href="/feladatok/{id}",
        label="feladat",
        fields=("feladat", "leiras", "kategoria", "ugyfel"),
        sublabel=("allapot", "kategoria"),
    ),
    "deliverable": SearchEntity(
        title="Utómunka",
        page="/utomunka",
        href="/utomunka/{id}",
        label="projekt_neve",
        fields=("projekt_neve", "projektkod_szoveg", "esemeny_neve", "vagas_leiras"),
        sublabel=("allapot", "projektkod_szoveg"),
    ),
    "expense": SearchEntity(
        title="Kiadások",
        page="/penzugyek",
        href="/penzugyek/kiadas/{id}",
        label="megnevezes",
        fields=("megnevezes", "szamla", "megjegyzes", "kiadas_megnevezese_projekt_kod"),
        sublabel=("tipus",),
    ),
    "revenue": SearchEntity(
        title="Bevételek",
        page="/penzugyek",
        href="/penzugyek/bevetel/{id}",
        label="nev",
        fields=("nev", "bevetel_formaja", "megjegyzes"),
        sublabel=("bevetel_formaja",),
    ),
}

MAX_PER_ENTITY = 5
MIN_QUERY_LENGTH = 2


class SearchHit(BaseModel):
    id: int
    label: str
    sublabel: str | None = None
    href: str


class SearchGroup(BaseModel):
    entity_type: str
    title: str
    hits: list[SearchHit]
    # Van-e a megmutatott MAX_PER_ENTITY találaton túl is - a frontend ebből
    # tudja kiírni, hogy érdemes pontosítani a keresést.
    truncated: bool


def _may_view(db: Session, user: Employee, page: str) -> bool:
    try:
        check_page_action(db, user, page, "view")
    except Exception:
        return False
    return True


def _text(value) -> str | None:
    if value is None:
        return None
    text = str(getattr(value, "value", value)).strip()
    return text or None


@router.get("", response_model=list[SearchGroup])
def global_search(
    q: str = Query("", description="Keresett szöveg"),
    db: Session = Depends(get_db),
    user: Employee = Depends(get_current_user),
) -> list[SearchGroup]:
    needle = q.strip()
    if len(needle) < MIN_QUERY_LENGTH:
        return []
    pattern = f"%{needle}%"

    groups: list[SearchGroup] = []
    for entity_type, meta in SEARCH_ENTITIES.items():
        model = ENTITY_MODELS.get(entity_type)
        if model is None or not _may_view(db, user, meta.page):
            continue

        columns = [model.__table__.columns[name] for name in meta.fields if name in model.__table__.columns]
        if not columns:
            continue
        # cast(String): a nem szöveges oszlopokban (pl. enum) is keressünk,
        # ILIKE ugyanis csak szövegen értelmezett.
        conditions = [cast(column, String).ilike(pattern) for column in columns]

        rows = db.scalars(
            select(model).where(or_(*conditions)).order_by(model.id.desc()).limit(MAX_PER_ENTITY + 1)
        ).all()
        if not rows:
            continue

        truncated = len(rows) > MAX_PER_ENTITY
        hits = []
        for row in rows[:MAX_PER_ENTITY]:
            label = _text(getattr(row, meta.label, None)) or f"#{row.id}"
            parts = [_text(getattr(row, name, None)) for name in meta.sublabel]
            hits.append(
                SearchHit(
                    id=row.id,
                    label=label,
                    sublabel=" · ".join([p for p in parts if p]) or None,
                    href=meta.href.format(id=row.id),
                )
            )
        groups.append(SearchGroup(entity_type=entity_type, title=meta.title, hits=hits, truncated=truncated))

    return groups
