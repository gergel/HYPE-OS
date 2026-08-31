from sqlalchemy import JSON, Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class DeliverableStatusConfig(TimestampMixin, Base):
    """Egy utómunka-ÁLLAPOT megjelenése és jelentése a felületen.

    Maguk az állapotok (Aktuális, Javítás, Kész, Kiküldésre vár...) továbbra is
    szabad szövegek a Deliverable.allapot mezőben, és a választható értékeket az
    admin a mező-beállításoknál szerkeszti - ez a tábla csak azt írja le, hogy
    egy állapot HOL és MILYEN SZÍNNEL jelenjen meg az Utómunka tábláján, és
    hogy elkészültnek számít-e.

    Amelyik állapothoz nincs sor, az a lista végére kerül, szín nélkül - tehát
    egy új állapot felvétele semmit nem ront el, csak nincs még beállítva."""

    __tablename__ = "deliverable_status_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    #: Maga az állapot szövege (ez a kapocs a Deliverable.allapot felé).
    allapot: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    #: Hányadik oszlop legyen a táblán (növekvő sorrendben).
    sorrend: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    #: Az oszlop (és a benne lévő kártyák) halvány színe - "#rrggbb". Üresen
    #: hagyva az oszlop a semleges alapszínt kapja.
    szin: Mapped[str | None] = mapped_column(String(20))
    #: Elkészültnek számít-e. Ami ilyen állapotban van, azt a rendszer NEM
    #: sorolja a lejárt határidejűek közé - a munka ott már megvan, csak a
    #: papírozás/kiküldés van hátra (lásd api/routes/dashboard.py).
    kesz_allapot: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    #: AUTOMATIKUS KIOSZTÁS: ha egy anyag EBBE az állapotba kerül, a rendszer
    #: ezekre a munkatársakra osztja ki (employee id-k listája) - mert ebben a
    #: fázisban nekik van vele dolguk (pl. Ellenőrzés/Beérkező -> az ellenőr,
    #: Kiküldhető -> akik kiküldik). Üres/None = nincs szabály, a kiosztás
    #: marad, ahogy volt. A lista az Utómunka tábla "Nézet beállítása"
    #: paneljén szerkeszthető (lásd routes/postproduction.set_allapot_beallitasok,
    #: a váltást a _after_deliverable_update hajtja végre).
    auto_kiosztott_employee_ids: Mapped[list | None] = mapped_column(JSON)


class DeliverableBoardConfig(TimestampMixin, Base):
    """Az Utómunka "Vágó nézet" tábláján a KÁRTYÁKON megjelenő adatok.

    Egyetlen sor az egész rendszerre (a tábla mindenkinek ugyanaz) - ezért nem
    munkatársanként tároljuk, mint a dashboard-widgeteket: itt arról van szó,
    hogy a csapat mit lát hasznosnak a kártyán, nem egyéni ízlésről.

    kartya_mezok=None -> az alapértelmezés (határidő + kiosztott ember)."""

    __tablename__ = "deliverable_board_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    #: A Deliverable mezőneveinek listája, a kártyán ebben a sorrendben.
    kartya_mezok: Mapped[list[str] | None] = mapped_column(JSON)
