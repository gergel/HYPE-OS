from datetime import date

from sqlalchemy import Column, Date, ForeignKey, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

project_crew = Table(
    "project_crew",
    Base.metadata,
    Column("project_id", ForeignKey("projects.id"), primary_key=True),
    Column("employee_id", ForeignKey("employees.id"), primary_key=True),
)


class Project(TimestampMixin, Base):
    """Konkrét forgatás egy Project Code-on belül."""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    nev: Mapped[str] = mapped_column(String(255), nullable=False)

    project_code_id: Mapped[int] = mapped_column(ForeignKey("project_codes.id"), nullable=False)
    campaign_id: Mapped[int | None] = mapped_column(ForeignKey("campaigns.id"))

    forgatas_datuma: Mapped[date | None] = mapped_column(Date)
    helyszin: Mapped[str | None] = mapped_column(String(255))
    allapot: Mapped[str | None] = mapped_column(String(50))

    project_code: Mapped["ProjectCode"] = relationship(back_populates="projects")
    campaign: Mapped["Campaign"] = relationship(back_populates="projects")
    crew: Mapped[list["Employee"]] = relationship(secondary=project_crew, back_populates="projects")

    deliverables: Mapped[list["Deliverable"]] = relationship(back_populates="project")
    callsheets: Mapped[list["Callsheet"]] = relationship(back_populates="project")
    assignments: Mapped[list["Assignment"]] = relationship(back_populates="project")
    media_items: Mapped[list["Media"]] = relationship(back_populates="project")
    folders: Mapped[list["Folder"]] = relationship(back_populates="project")
    portal: Mapped["Portal"] = relationship(back_populates="project", uselist=False)
