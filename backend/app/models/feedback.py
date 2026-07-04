from sqlalchemy import ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class Feedback(TimestampMixin, Base):
    """Gombos visszajelzés - a vágó egy gombbal küldi át az Utómunka oldalról."""

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
