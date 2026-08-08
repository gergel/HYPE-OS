"""Mettől meddig volt valaki BELSŐS munkatárs.

Miért kell? Mert a belsős havi TIG minden belsőstől MINDEN hónapra elvárt -
és ez hazug azoknál a hónapoknál, amikor az illető még nem, vagy már nem
dolgozott nálunk. Az ilyen hónapok örökre "hiányzó TIG"-ként állnának a
Belsős TIG oldalon, elfedve az igazi teendőket.

Egy embernél TÖBB időszak is lehet: kilép, majd fél év múlva visszajön. Ezért
nem elég egy dátumpár a munkatárs adatlapján - ugyanaz a szerkezet kell, mint
a keretszerződés érvényességénél (lásd models/contract.py ContractPeriod).

Ha valakinél EGYETLEN időszak sincs, visszaesünk a munkatárs
`elso_munkanap` / `utolso_munkanap` mezőire (ezek a Notion-importból már
jönnek), és ha azok is üresek, minden hónapra várunk tőle TIG-et - vagyis a
korábbi viselkedés marad. Lásd services/belsos_idoszak.py."""

from datetime import date

from sqlalchemy import Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class BelsosIdoszak(TimestampMixin, Base):
    """Egy időszak, amíg az illető belsős volt.

    A nyitott vég (veg IS NULL) azt jelenti: "azóta is itt van". A nyitott
    kezdet (kezdet IS NULL) azt, hogy "a kezdetektől" - ez a régi, dátum
    nélküli bejegyzéseknek kell."""

    __tablename__ = "belsos_idoszakok"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kezdet: Mapped[date | None] = mapped_column(Date)
    veg: Mapped[date | None] = mapped_column(Date)
    megjegyzes: Mapped[str | None] = mapped_column(String(255))

    employee: Mapped["Employee"] = relationship(back_populates="belsos_idoszakok")
