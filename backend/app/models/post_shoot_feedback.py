from sqlalchemy import JSON, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class PostShootFeedback(TimestampMixin, Base):
    """A diszpó kiküldése után, a forgatás vége után 12 órával kiküldött
    utókövető email kérdőívének kitöltött válasza - nyilvános (bejelentkezés
    nélküli) űrlapon érkezik, lásd api/routes/public_utokovetes.py."""

    __tablename__ = "post_shoot_feedbacks"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)

    erdemleges_tortent: Mapped[str | None] = mapped_column(Text, comment="Történt-e bármi érdemleges a forgatással kapcsolatban")
    technika_info: Mapped[str | None] = mapped_column(Text, comment="Infó a nálad levő technikával kapcsolatban")
    egyeb: Mapped[str | None] = mapped_column(Text, comment="Bármi egyéb, amit itt hagynál a diszpódat követően")
    # [{"url": "...", "filename": "..."}] - nincs szükség egyedi törlésre/
    # kezelésre (mint a munkaszerződés dokumentumoknál), csak megtekintésre.
    werk_fotok: Mapped[list | None] = mapped_column(JSON)

    project: Mapped["Project"] = relationship(back_populates="post_shoot_feedbacks")
