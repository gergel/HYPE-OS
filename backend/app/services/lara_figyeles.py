"""LARA FIGYELÉSE - a kiválasztott (adminisztrációs) kolléga munkájának
folyamatos figyelése.

A felhasználó kérése (2026-10): Lara figyelje folyamatosan egy adott ember
munkáját, és az Adminisztráció ellenőrzése oldalon CSAK a tulajdonosnak
jelezzen, ha valami szokatlan, vagy nem azt adja, amit vártunk.

Biztonság:
- új automatizmus, ezért SAJÁT kapcsolóval megy, alapból KIKAPCSOLVA
  (AdminEllenorzesBeallitas.lara_figyeles), és a Lara-vészleállítás is
  megállítja;
- csak OLVAS: a tevékenységnaplót és a papírok állapotát nézi, semmit nem
  módosít, senkinek nem ír - a jelzés csak egy sor a lara_figyeles_jelzesek
  táblában, amit kizárólag az ellenőrző oldal mutat;
- ugyanarról a dologról egyszer jelez (egyedi kulcs).

A szabályok egyszerűek és megmagyarázhatók - minden jelzés megmondja, miért
szólt Lara:
- kihagyás semmitmondó (vagy hiányzó) indokkal;
- sok kihagyás/kivétel egy napon;
- törlés, eldobott feltöltött papír;
- "van már szerződése" jelölés (nem itt készült papír - megvan-e valóban);
- kézi állapot-átállítás kiküldöttre/készre (kiküldés nélkül);
- kifizetettnek jelölt TIG, amihez nincs számla;
- "sosem lesz számlája" jelölés nagy összegű kiadáson;
- jócskán (a határidőn túl még egy héttel) késő papír;
- inaktivitás: napok óta nincs tevékenység, miközben vannak lejárt hiányok."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.admin_ellenorzes import AdminTevekenyseg, LaraFigyelesJelzes
from app.models.employee import Employee
from app.models.performance_certificate import PerformanceCertificate
from app.services import admin_ellenorzes

#: Ennél rövidebb kihagyás-indok semmitmondó (pl. "nem kell", "-", "x").
MIN_INDOK_HOSSZ = 15
#: Egy napon ennyi kivételtől szól Lara.
SOK_KIVETEL_NAPONTA = 3
#: E fölött a "sosem lesz számlája" jelölés gyanús (bruttó Ft).
NAGY_OSSZEG = 100_000
#: A határidőn túl még ennyi nap késés után szól (a sima lejárt hiány a
#: "Lejárt hiányok" fülön látszik, ide csak a nagyon csúszók jönnek).
KESES_JELZES_NAP = 7
#: Ennyi munkanap tétlenség után szól (ha közben vannak lejárt hiányok).
INAKTIV_MUNKANAP = 3
#: Ennyi napra visszamenőleg nézi a naplót.
VISSZATEKINTES_NAP = 30

HATTER_NEV = "lara_admin_figyeles"


def _most() -> datetime:
    return datetime.now(timezone.utc)


def _vesz_leallitas(db: Session) -> bool:
    try:
        from app.admin_agent.settings_service import get_settings

        return bool(get_settings(db).kill_switch)
    except Exception:  # noqa: BLE001 - ha a Lara-beállítás nem olvasható, inkább álljunk meg
        return True


def _munkanapok_kozott(tol: date, ig: date) -> int:
    n, d = 0, tol
    while d < ig:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n += 1
    return n


def _jelzes(
    db: Session, *, kulcs: str, szabaly: str, cim: str, leiras: str, link: str | None, employee_id: int,
    szint: str = "figyelem", adat: dict | None = None,
) -> bool:
    """Új jelzés - ha ugyanerről már szólt Lara, nem ismétli."""
    if db.scalar(select(LaraFigyelesJelzes.id).where(LaraFigyelesJelzes.kulcs == kulcs)) is not None:
        return False
    try:
        with db.begin_nested():
            db.add(LaraFigyelesJelzes(
                kulcs=kulcs[:150], szabaly=szabaly, szint=szint, cim=cim[:300], leiras=leiras, link=link,
                employee_id=employee_id, adat=adat,
            ))
    except IntegrityError:
        return False
    return True


def futtat(db: Session, *, most: datetime | None = None, kenyszer: bool = False) -> dict:
    """Egy figyelési kör. `kenyszer` = a tulajdonos kézzel indította (akkor is
    lefut, ha a kapcsoló ki van kapcsolva - de csak olvas és jelez)."""
    most = most or _most()
    b = admin_ellenorzes.beallitas(db)
    if not b.lara_figyeles and not kenyszer:
        return {"allapot": "kikapcsolva", "uj_jelzes": 0}
    if _vesz_leallitas(db):
        return {"allapot": "veszleallitas", "uj_jelzes": 0}
    figyelt = db.get(Employee, b.figyelt_employee_id) if b.figyelt_employee_id else None
    if figyelt is None:
        return {"allapot": "nincs_figyelt", "uj_jelzes": 0}

    nev = figyelt.full_name
    sorok = db.scalars(
        select(AdminTevekenyseg)
        .where(
            AdminTevekenyseg.employee_id == figyelt.id,
            AdminTevekenyseg.letrejott_at >= most - timedelta(days=VISSZATEKINTES_NAP),
        )
        .order_by(AdminTevekenyseg.letrejott_at)
    ).all()
    uj = 0

    def link_of(s: AdminTevekenyseg) -> str | None:
        return admin_ellenorzes._naplo_link(s)

    kivetelek_naponta: dict[date, list[AdminTevekenyseg]] = defaultdict(list)
    for s in sorok:
        adat = s.adat or {}
        mikor = s.letrejott_at.astimezone().strftime("%Y.%m.%d. %H:%M")
        if s.muvelet in ("kihagyas", "szamla_kihagyas", "mar_van"):
            kivetelek_naponta[s.letrejott_at.date()].append(s)
        if s.muvelet in ("kihagyas", "szamla_kihagyas"):
            indok = (adat.get("kihagyas_oka") or adat.get("szamla_kihagyas_oka") or "").strip()
            if len(indok) < MIN_INDOK_HOSSZ:
                uj += _jelzes(
                    db, kulcs=f"indok:{s.id}", szabaly="semmitmondo_indok", employee_id=figyelt.id, link=link_of(s),
                    cim=f"{nev}: kihagyás {'indok nélkül' if not indok else 'semmitmondó indokkal'}",
                    leiras=f"{s.leiras} ({mikor}). Indok: „{indok or '–'}”. Egy kihagyásnak fél év múlva is érthetőnek kell lennie.",
                )
        elif s.muvelet in ("torles", "fajl_eldobas"):
            uj += _jelzes(
                db, kulcs=f"torles:{s.id}", szabaly="torles", employee_id=figyelt.id, link=link_of(s),
                cim=f"{nev}: {s.leiras}",
                leiras=f"{mikor}. Törlés után a papír már nem látszik a listákban - érdemes megnézni, indokolt volt-e.",
            )
        elif s.muvelet == "mar_van":
            uj += _jelzes(
                db, kulcs=f"mar_van:{s.id}", szabaly="mar_van", employee_id=figyelt.id, link=link_of(s), szint="info",
                cim=f"{nev}: „van már szerződése” jelölés",
                leiras=f"{mikor}. A szerződés nem itt készült - nézd meg, valóban megvan-e a papír.",
            )
        elif s.muvelet == "allapot" and str(adat.get("allapot") or "") in ("Kiküldve", "Kész"):
            uj += _jelzes(
                db, kulcs=f"allapot:{s.id}", szabaly="kezi_allapot", employee_id=figyelt.id, link=link_of(s),
                cim=f"{nev}: kézzel „{adat.get('allapot')}” állapotba tette ({s.targy})",
                leiras=f"{mikor}. Kiküldés nélkül lett kiküldöttnek/késznek jelölve - megvan valóban a papír?",
            )
        elif s.muvelet == "kifizetes" and s.targy == "tig":
            p = s.parameterek or {}
            tig = _tig_a_naplobol(db, p)
            if tig is not None and not tig.invoices and not tig.szamla_kihagyva:
                uj += _jelzes(
                    db, kulcs=f"szamla_nelkul:{s.id}", szabaly="kifizetes_szamla_nelkul", employee_id=figyelt.id,
                    link=link_of(s), cim=f"{nev}: kifizetettnek jelölt TIG számla nélkül",
                    leiras=f"{mikor}. A TIG-hez nincs feltöltött számla, mégis kifizetettnek jelölte.",
                )
        elif s.targy == "kiadas" and adat.get("nincs_szamla") is True:
            osszeg = adat.get("brutto") or adat.get("netto")
            try:
                osszeg = float(osszeg) if osszeg is not None else None
            except (TypeError, ValueError):
                osszeg = None
            if osszeg is not None and osszeg >= NAGY_OSSZEG:
                uj += _jelzes(
                    db, kulcs=f"nincs_szamla:{s.id}", szabaly="nincs_szamla_nagy", employee_id=figyelt.id,
                    link=link_of(s), cim=f"{nev}: „sosem lesz számlája” {osszeg:,.0f} Ft-os kiadáson".replace(",", " "),
                    leiras=f"{mikor}. Nagy összegnél ritka, hogy tényleg ne legyen számla.",
                )

    for nap, lista in kivetelek_naponta.items():
        if len(lista) >= SOK_KIVETEL_NAPONTA:
            uj += _jelzes(
                db, kulcs=f"sok_kivetel:{figyelt.id}:{nap.isoformat()}", szabaly="sok_kivetel", employee_id=figyelt.id,
                link="/admin-ellenorzes?ful=kivetelek",
                cim=f"{nev}: {len(lista)} kihagyás/kivétel egy napon ({nap.strftime('%Y.%m.%d.')})",
                leiras="Szokatlanul sok kivétel egyszerre: " + "; ".join(s.leiras for s in lista[:6]),
            )

    lejart = admin_ellenorzes.lejart_hianyok(db, ma=most.date(), hatarido=admin_ellenorzes.hataridok(b))
    for h in lejart:
        if h["keses_nap"] >= KESES_JELZES_NAP:
            uj += _jelzes(
                db, kulcs=f"keses:{h['kulcs']}", szabaly="nagy_keses", employee_id=figyelt.id, link=h["link"],
                cim=f"{h['dokumentum']} {h['keses_nap']} napja késik: {h['projekt']} – {h['fel']}",
                leiras=f"Határidő: {h['hatarido_nap']} nap, eltelt: {h['eltelt_nap']} nap. Állapot: {h['allapot']}.",
            )

    utolso = sorok[-1].letrejott_at.date() if sorok else None
    tetlen = _munkanapok_kozott(utolso, most.date()) if utolso else INAKTIV_MUNKANAP
    if lejart and tetlen >= INAKTIV_MUNKANAP:
        het = most.date().isocalendar()
        uj += _jelzes(
            db, kulcs=f"inaktiv:{figyelt.id}:{het[0]}-{het[1]}", szabaly="inaktivitas", employee_id=figyelt.id,
            link="/admin-ellenorzes?ful=lejart",
            cim=f"{nev}: {tetlen} munkanapja nincs papírozási tevékenység",
            leiras=f"Közben {len(lejart)} papír van a határidőn túl. Utolsó tevékenység: "
            + (utolso.strftime("%Y.%m.%d.") if utolso else "nincs a naplóban") + ".",
        )

    b.utolso_futas_at = most
    db.commit()
    return {"allapot": "lefutott", "uj_jelzes": uj, "figyelt": nev}


def _tig_a_naplobol(db: Session, p: dict) -> PerformanceCertificate | None:
    """A naplósor paramétereiből a TIG (projekt + számlázó fél)."""
    try:
        project_id = int(p.get("project_id")) if p.get("project_id") else None
    except (TypeError, ValueError):
        return None
    kulcs = str(p.get("szamlazo_kulcs") or "")
    if project_id is None or not kulcs:
        return None
    q = select(PerformanceCertificate).where(PerformanceCertificate.project_id == project_id)
    if kulcs.startswith("v"):
        q = q.where(PerformanceCertificate.vallalkozas_id == int(kulcs[1:]))
    else:
        q = q.where(PerformanceCertificate.employee_id == int(kulcs.lstrip("e")), PerformanceCertificate.vallalkozas_id.is_(None))
    return db.scalars(q).first()


def hatter_futas(naplo) -> dict:
    """Az időzített kör (main.py) - saját munkamenettel."""
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        eredmeny = futtat(db)
        naplo(f"Lara figyelése: {eredmeny}")
        return eredmeny
    finally:
        db.close()
