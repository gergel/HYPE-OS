"""Megbízási szerződés MÓDOSÍTÁSA - egy megrendelői keretszerződéshez.

Miért külön tábla, és nem néhány mező a `Contract`-on? Mert egy keretszerződést
az évek alatt TÖBBSZÖR is módosítanak (székhely, cégjegyzékszám, díjazás), és
mindegyik módosítás önálló papír: saját keltezéssel, saját kiküldéssel, saját
aláírt példánnyal. Egyetlen `modositas_file_url` mező a másodiknál felülírná az
elsőt - és pont az veszne el, amit a szerződés mellé évekig meg kell őrizni.

A CÉGADATOK itt is MÁSOLATBAN vannak (lásd models/megrendeloi_papir.py): a
papír azt kell hogy őrizze, ami rajta van. Ha a megrendelő fél év múlva megint
székhelyet vált, a korábbi módosítás attól még a korábbi adatokkal kelt.

Az ÁLLAPOTOK szándékosan mások, mint a többi papíré. Ott a "Kiküldve" a
végállomás, mert a lényeg a kiküldés; itt viszont a módosítás akkor ér valamit,
ha ALÁÍRVA VISSZAJÖTT - a folyamat tehát csak az aláírt példány feltöltésével
zárul le."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

#: A módosítás útja. A sorrend a folyamat sorrendje.
ALLAPOTOK: tuple[str, ...] = ("Készítés alatt", "Aláírásra vár", "Kész")
#: Amiből már nincs teendő.
LEZART_ALLAPOTOK: frozenset[str] = frozenset({"Kész"})


class KeretModositas(TimestampMixin, Base):
    """Egy szerződésmódosítás egy megrendelői keretszerződéshez."""

    __tablename__ = "keret_modositasok"

    id: Mapped[int] = mapped_column(primary_key=True)
    contract_id: Mapped[int] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # --- a papírra kerülő adatok (MÁSOLAT, lásd a modul leírását) ---
    ceg_neve: Mapped[str | None] = mapped_column(String(255))
    szekhely: Mapped[str | None] = mapped_column(String(500))
    adoszam: Mapped[str | None] = mapped_column(String(50))
    kepviselo: Mapped[str | None] = mapped_column(String(255))
    nyilvantartasi_szam: Mapped[str | None] = mapped_column(String(100))
    #: Melyik címre ment ki - a keret e-mail címének pillanatképe.
    email: Mapped[str | None] = mapped_column(String(255))
    keltezes: Mapped[date | None] = mapped_column(Date)

    allapot: Mapped[str | None] = mapped_column(String(50), default="Készítés alatt")
    #: A generált (Drive-link) vagy feltöltött (R2) módosítás.
    file_url: Mapped[str | None] = mapped_column(String(500))
    file_storage_key: Mapped[str | None] = mapped_column(String(500))
    #: Az ALÁÍRVA visszakapott példány - amíg nincs, a módosítás aláírásra vár.
    alairt_file_url: Mapped[str | None] = mapped_column(String(500))
    alairt_file_storage_key: Mapped[str | None] = mapped_column(String(500))

    #: Mikor és ki küldte ki. Az "elküldtem-e már" kérdésre a felületen ebből
    #: jön a válasz - az `allapot` átállítható kézzel is, ez nem.
    kikuldve: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    kikuldte_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))

    #: A kiküldött levél szövege, ahogy a felhasználó megírta (sima szöveg, a
    #: Gmail-aláírás nélkül). Azért tároljuk, mert a módosításnál a levél maga
    #: is része az ügynek: fél év múlva az a kérdés, hogy MIT írtunk nekik,
    #: nem csak az, hogy küldtünk-e valamit.
    level_szoveg: Mapped[str | None] = mapped_column(Text)
    megjegyzes: Mapped[str | None] = mapped_column(Text)

    contract: Mapped["Contract"] = relationship(back_populates="modositasok")
    kikuldte: Mapped["Employee | None"] = relationship()
