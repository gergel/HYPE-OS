from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class EmployeeDocument(TimestampMixin, Base):
    """Egy munkatárshoz feltöltött dokumentum (pl. munkaszerződés) - egy
    munkatársnak több fájlja is lehet, egyenként feltölthetők/törölhetők
    (lásd crew.py munkaszerzodesek végpontjai)."""

    __tablename__ = "employee_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    # az R2 objektumkulcs (nem csak a publikus URL) - enélkül a törléskor nem
    # tudnánk visszafejteni, melyik objektumot kell törölni a tárhelyről.
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(100))

    employee: Mapped["Employee"] = relationship(back_populates="documents")
