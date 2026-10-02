"""Egy eszköz MUNKA-STATISZTIKÁJA - automatikusan, a rendszer adataiból.

A felhasználó kérése: az eszköz adatlapján ne kézzel vezetett szám álljon,
hanem a rendszer SZÁMOLJA ki,
- hány napot dolgozott (egy forgatás több napos is lehet - MINDEN nap
  számít, amin dolgozott, akkor is, ha csak pár órát; két forgatás
  ugyanazon a napon EGY nap),
- hány forgatáson vett részt (és melyiken),
- hol volt utoljára.

HONNAN TUDJUK? Forgatásonként (projektenként) a legjobb elérhető forrásból:

1. ESZKÖZKIVITEL - ha a forgatáshoz van (nem teszt) kivitel, az a TÉNY: az
   eszköz csak akkor számít, ha tényleg kivitték (kivitt_db > 0), és a napjai
   a kint töltött napok (a kivitel lezárásától a visszahozatal lezárásáig,
   amíg nincs visszahozva: máig). Ha a kivitelt még nem zárták le, a
   forgatás napjai számítanak.
2. FOGLALÁS - ahol (még) nincs kivitel, ott a projektre foglalt eszköz a
   forgatás napjaival számít.

Csak a MÁR ELKEZDŐDÖTT forgatások és a mai napig eltelt napok számítanak: egy
jövőbeli foglalás még nem munka.

Az eredmény a kimenő adatba kerül (lásd routes/equipment._statisztika_kimenet)
- mindig friss, nem kell semmilyen eseménynél újraszámolni."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.equipment import Assignment
from app.models.eszkoz_kivitel import EszkozKivitel, EszkozKivitelTetel
from app.models.project import Project
from app.services.hu_datum import BUDAPEST_IDOZONA, budapesti_ma

FORRAS_KIVITEL = "kivitel"
FORRAS_FOGLALAS = "foglalas"


@dataclass
class Forgatas:
    project_id: int
    nev: str
    helyszin: str | None
    kezdet: date
    vege: date
    #: Ezen a forgatáson az eszköz munkanapjai (a mai napig).
    napok: list[date]
    forras: str


@dataclass
class EszkozStatisztika:
    forgatasok: list[Forgatas] = field(default_factory=list)

    @property
    def napok(self) -> set[date]:
        return {nap for f in self.forgatasok for nap in f.napok}

    @property
    def napok_szama(self) -> int:
        return len(self.napok)

    @property
    def utolso(self) -> Forgatas | None:
        return max(self.forgatasok, key=lambda f: (f.vege, f.kezdet), default=None)

    @property
    def ahol_utoljara_volt(self) -> str | None:
        f = self.utolso
        if f is None:
            return None
        datum = f.kezdet.strftime("%Y.%m.%d.")
        if f.vege != f.kezdet:
            datum += f" – {f.vege.strftime('%m.%d.')}"
        hely = f" · {f.helyszin.strip()}" if f.helyszin and f.helyszin.strip() else ""
        return f"{f.nev}{hely} · {datum}"


def forgatas_vege(p: Project) -> date | None:
    """A forgatás záró napja - ugyanaz a szabály, mint a schemas/project
    veg_datum-ja (kézi zárnál csak a kézi vég, különben az első ismert)."""
    if p.forgatas_datuma is None:
        return None
    if p.forgatas_datum_kezzel_beallitva:
        jelolt = p.forgatas_datuma_vege
    else:
        jelolt = p.forgatas_datuma_vege or p.naptar_datum_vege or p.notion_datum_vege
    return jelolt if jelolt is not None and jelolt > p.forgatas_datuma else p.forgatas_datuma


def _napok(tol: date, ig: date, ma: date) -> list[date]:
    ig = min(ig, ma)
    if ig < tol:
        return []
    return [tol + timedelta(days=i) for i in range((ig - tol).days + 1)]


def _helyi_nap(ido: datetime) -> date:
    return ido.astimezone(BUDAPEST_IDOZONA).date() if ido.tzinfo else ido.date()


def statisztikak(db: Session, equipment_ids: list[int], ma: date | None = None) -> dict[int, EszkozStatisztika]:
    """eszköz-id -> statisztika, KÉT lekérdezésből (a lista minden sorára is
    gyors)."""
    ma = ma or budapesti_ma()
    eredmeny: dict[int, EszkozStatisztika] = {eid: EszkozStatisztika() for eid in equipment_ids}
    if not equipment_ids:
        return eredmeny

    # 1. ESZKÖZKIVITEL: a nem teszt kivitelek tételei.
    kivitel_sorok = db.execute(
        select(EszkozKivitelTetel, EszkozKivitel, Project)
        .join(EszkozKivitel, EszkozKivitel.id == EszkozKivitelTetel.kivitel_id)
        .join(Project, Project.id == EszkozKivitel.project_id)
        .where(EszkozKivitelTetel.equipment_id.in_(equipment_ids), EszkozKivitel.teszt.is_(False))
    ).all()
    # Mely projektekhez VAN kivitel (bármelyik eszközzel) - ott a kivitel dönt,
    # a foglalás nem számít.
    kiviteles_projektek: set[int] = set(
        db.scalars(
            select(EszkozKivitel.project_id).where(
                EszkozKivitel.project_id.is_not(None), EszkozKivitel.teszt.is_(False)
            )
        ).all()
    )
    for tetel, kivitel, p in kivitel_sorok:
        if tetel.kivitt_db <= 0 or (p.forgatas_datuma is None and kivitel.kivitel_lezarva_at is None):
            continue
        vege = forgatas_vege(p) or p.forgatas_datuma
        if kivitel.kivitel_lezarva_at is not None:
            tol = _helyi_nap(kivitel.kivitel_lezarva_at)
            ig = _helyi_nap(kivitel.vissza_lezarva_at) if kivitel.vissza_lezarva_at else ma
            kezdet, zaro = tol, max(ig, tol)
        else:
            kezdet, zaro = p.forgatas_datuma, vege
        napok = _napok(kezdet, zaro, ma)
        if not napok:
            continue
        eredmeny[tetel.equipment_id].forgatasok.append(
            Forgatas(p.id, p.nev, p.helyszin, kezdet, min(zaro, ma), napok, FORRAS_KIVITEL)
        )

    # 2. FOGLALÁS: ahol nincs kivitel.
    foglalasok = db.execute(
        select(Assignment.equipment_id, Project)
        .join(Project, Project.id == Assignment.project_id)
        .where(Assignment.equipment_id.in_(equipment_ids), Project.forgatas_datuma.is_not(None))
    ).all()
    latott: set[tuple[int, int]] = set()
    for eid, p in foglalasok:
        if p.id in kiviteles_projektek or (eid, p.id) in latott:
            continue
        latott.add((eid, p.id))
        vege = forgatas_vege(p) or p.forgatas_datuma
        napok = _napok(p.forgatas_datuma, vege, ma)
        if not napok:
            continue
        eredmeny[eid].forgatasok.append(
            Forgatas(p.id, p.nev, p.helyszin, p.forgatas_datuma, min(vege, ma), napok, FORRAS_FOGLALAS)
        )

    for stat in eredmeny.values():
        stat.forgatasok.sort(key=lambda f: (f.kezdet, f.project_id), reverse=True)
    return eredmeny
