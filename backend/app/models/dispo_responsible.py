import enum

from sqlalchemy import Enum as SAEnum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class DispoSide(str, enum.Enum):
    """A diszpó két, egymástól FÜGGETLEN felelősségi oldala - más-más
    feltétellel tekinthető elvégzettnek (lásd api/routes/dashboard.py my_tasks):

    - GYARTAS: a gyártási oldal dolga az előzetes diszpó kiküldése, tehát a
      teendő akkor kerül le, ha az előzetes KIMENT - VAGY ha a teljes diszpó
      ment ki előzetes nélkül (a felhasználó kifejezett kérése: ilyenkor a
      gyártásnak sincs már mit tennie).
    - TECHNIKA: a technikai oldal a teljes (technika listás) diszpót várja,
      így ez a teendő KIZÁRÓLAG a teljes diszpó kiküldésére tűnik el - az
      előzetes önmagában nem elég."""

    GYARTAS = "gyartas"
    TECHNIKA = "technika"


class DispoResponsible(TimestampMixin, Base):
    """Ki felel a diszpó kiküldéséért - a Beállítások oldalon állítható,
    oldalanként AKÁRHÁNY ember (a felhasználó kérése), és ugyanaz az ember
    mindkét oldalon szerepelhet (ilyenkor két külön teendőt lát, mert a kettő
    más-más feltétellel kerül le).

    Ezeknek az embereknek a "Teendőim" widget minden nap felhozza a MÁSNAPI
    forgatások diszpóit, amíg a saját oldaluk szerinti küldés meg nem történt."""

    __tablename__ = "dispo_responsibles"
    __table_args__ = (UniqueConstraint("employee_id", "oldal", name="uq_dispo_responsible_employee_side"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    oldal: Mapped[DispoSide] = mapped_column(SAEnum(DispoSide, name="dispo_side"), nullable=False)
