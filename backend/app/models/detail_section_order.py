from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class DetailSectionOrder(TimestampMixin, Base):
    """A részletnézet szekció-kártyáinak ("widgetek") megjelenítési sorrendje
    entitástípusonként - a felhasználó a részletnézetben húzással rendezi át
    őket, és onnantól az adott típus MINDEN rekordjánál ez a sorrend érvényes
    (lásd frontend/components/DetailSections.tsx).

    MIÉRT NEM a meglévő DetailTabConfig.sort_order? Mert a részletnézetben
    megjelenő kártyák egy része NEM DB-driven fül: a bespoke widgetek (pl.
    "Diszpó küldése", "Szerződés & TIG", "Csapat & Utómunka") és a szintetikus
    "Egyéb" gyűjtő kártya kódban keletkeznek, nincs hozzájuk detail_tab_configs
    sor. Ha a sorrendet ott tárolnánk, ezeket nem lehetne átrendezni - vagy
    ál-fülsorokat kellene létrehozni nekik, ami viszont megjelenne az admin
    fül-szerkesztőjében szerkeszthető mezőcsoportként, holott nem azok.

    A `section_keys` egy egyszerű kulcslista; ami nincs benne (pl. egy újonnan
    hozzáadott widget), az a lista VÉGÉRE kerül, a saját természetes
    sorrendjében - így egy régi mentés sosem tüntet el új kártyát."""

    __tablename__ = "detail_section_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    section_keys: Mapped[list[str]] = mapped_column(JSON, default=list)
