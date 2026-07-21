from sqlalchemy import JSON, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class DetailTabConfig(TimestampMixin, Base):
    """Admin által szerkeszthető fül-elrendezés egy entitástípus részletnézetéhez
    (lásd Beállítások oldal) - mely fülek jelenjenek meg, milyen sorrendben, és
    melyik mező melyik fülhöz tartozzon. entity_type ugyanaz a kulcs, mint a
    FieldVisibilityConfig-nál (pl. "project"). Egy adott entity_type-hoz nincs
    kötelezően minden mezőt lefedni: amit egyetlen fül field_keys listája sem
    tartalmaz, az a frontend/backend oldalon egyaránt egy szintetikus "_other"
    (Egyéb) fülre esik (lásd services/detail_tabs.py) - így soha nem vész el
    mező azért, mert admin még nem sorolta be sehova.

    A fül-szintű nézési/szerkesztési jogosultság a MEGLÉVŐ PageAccessConfig
    mechanizmust bővíti ki (nem külön táblával) - a kulcs "{page}:{tab_key}"
    alakú (pl. "/projektek:diszpo"), ugyanúgy ellenőrizve, mint egy sima oldal
    (lásd core/security.check_page_action, api/crud_router.py update_item)."""

    __tablename__ = "detail_tab_configs"
    __table_args__ = (UniqueConstraint("entity_type", "tab_key", name="uq_detail_tab_entity_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    tab_key: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    icon: Mapped[str | None] = mapped_column(String(50), comment="lucide-react ikon neve, opcionális")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    field_keys: Mapped[list[str]] = mapped_column(JSON, default=list)
