from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class Feedback(TimestampMixin, Base):
    """VÁGÓI VISSZAJELZÉS egy leforgatott anyagról.

    A vágó az utómunka oldalán tölti ki: három pontszám (1-10) és egy szöveges
    rész. A pontszámok a gyártásnak szólnak - ebből derül ki, mit kapott a
    vágó, és min lehet javítani a következő forgatáson.

    Miért önálló rekord, és miért nem az anyagon élnek a számok: egy anyaghoz
    több visszajelzés is születhet (több kör, több vágó), és utólag azt kell
    tudni megnézni, KI mit írt és MIKOR. Az anyagon lévő mezők ezért csak a
    LEGUTÓBBI értékelés másolatai, a történet itt van.

    Amit szándékosan MÁSOLUNK ide (nem hivatkozunk rá): a kész anyag linkje.
    Az anyag linkje később változhat vagy törlődhet, a visszajelzésnek viszont
    évek múlva is arra kell mutatnia, amiről szólt."""

    __tablename__ = "feedbacks"

    id: Mapped[int] = mapped_column(primary_key=True)
    deliverable_id: Mapped[int] = mapped_column(ForeignKey("deliverables.id"), nullable=False)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"))
    forgatta_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))
    # Ki küldte a visszajelzést (a "Visszajelzés küldése" gombot megnyomó
    # felhasználó) - nem ugyanaz, mint forgatta_employee_id (aki a projektet
    # forgatta) - lásd services/deliverable_actions.send_visszajelzes.
    visszajelzo_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))

    technikai_helyesseg: Mapped[float | None] = mapped_column(Numeric(3, 1))
    kreativ_kepivilag: Mapped[float | None] = mapped_column(Numeric(3, 1))
    nyersanyag_felhasznalhatosaga: Mapped[float | None] = mapped_column(Numeric(3, 1))
    ertekeles_kuldese: Mapped[str | None] = mapped_column(String(50))
    visszajelzes_szoveg: Mapped[str | None] = mapped_column(Text)

    #: A kész anyag linkje a visszajelzés pillanatában - lásd az osztály
    #: kommentjét arról, miért másolat és nem hivatkozás.
    kesz_anyag_url: Mapped[str | None] = mapped_column(String(500))
    #: Mikor ment ki válaszként a forgatás diszpó-levelére. Amíg üres, még nem
    #: küldtük ki - ettől lehet egyszer kiküldeni, és látni, hogy megtörtént.
    diszpora_kikuldve: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    deliverable: Mapped["Deliverable"] = relationship(back_populates="feedbacks")
    forgatta: Mapped["Employee"] = relationship(back_populates="feedbacks", foreign_keys=[forgatta_employee_id])
    visszajelzo: Mapped["Employee"] = relationship(foreign_keys=[visszajelzo_employee_id])

    @property
    def atlag(self) -> float | None:
        values = [
            v
            for v in (self.technikai_helyesseg, self.kreativ_kepivilag, self.nyersanyag_felhasznalhatosaga)
            if v is not None
        ]
        return sum(values) / len(values) if values else None
