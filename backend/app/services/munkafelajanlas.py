"""Munkafelajánlások - a folyamat lelke (lásd models/munkafelajanlas.py).

Itt él minden, aminek pontosnak kell lennie:
- a határidő SZERVEROLDALI ellenőrzése (magyar idő, Europe/Budapest),
- a személyre szóló e-mailek összeállítása és könyvelt kiküldése (a
  sikertelen küldés újrapróbálható a sikeresek megismétlése nélkül),
- a zárolt, egy-nyertes kiválasztás (két egyidejű döntés sem adhat két
  nyertest), és a döntés tartós rögzítése (egy értesítési hiba nem írja
  felül és nem törli a döntést)."""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.employee import Employee
from app.models.munkafelajanlas import Ajanlatkeres, AjanlatMeghivott, MunkaArajanlat
from app.services import google_email

logger = logging.getLogger(__name__)

BUDAPEST = ZoneInfo("Europe/Budapest")

#: A meghívóban kötelező, jól látható tájékoztatás (a felhasználó pontos szövege).
TAJEKOZTATO = (
    "Kérjük, a megadott határidőig küldd el árajánlatodat. A beérkezett ajánlatok közül "
    "a válaszadási határidő lejárta után választunk, és az eredményről külön értesítünk. "
    "Az ajánlat beküldése még nem jelent megbízást."
)

HONAPOK = (
    "január", "február", "március", "április", "május", "június",
    "július", "augusztus", "szeptember", "október", "november", "december",
)


def most_utc() -> datetime:
    """Tz-mentes UTC 'most' - az adatbázis DateTime oszlopaival összevethető."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def budapest_datetime_utc(ertek: str) -> datetime:
    """A felületről jövő "YYYY-MM-DDTHH:MM" időpont MAGYAR IDŐ szerint értendő
    (a felhasználó kérése) - itt váltjuk UTC-re a tároláshoz."""
    try:
        naiv = datetime.fromisoformat(ertek)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Érvénytelen időpont-formátum (ÉÉÉÉ-HH-NNTóó:pp).") from exc
    if naiv.tzinfo is None:
        helyi = naiv.replace(tzinfo=BUDAPEST)
    else:
        helyi = naiv
    return helyi.astimezone(timezone.utc).replace(tzinfo=None)


def budapest_szoveg(utc_naiv: datetime | None) -> str:
    """Az UTC-ben tárolt időpont magyar idő szerinti, emberi alakja:
    "2026. szeptember 20. (vasárnap) 18:00"."""
    if utc_naiv is None:
        return "–"
    helyi = utc_naiv.replace(tzinfo=timezone.utc).astimezone(BUDAPEST)
    napok = ("hétfő", "kedd", "szerda", "csütörtök", "péntek", "szombat", "vasárnap")
    return (
        f"{helyi.year}. {HONAPOK[helyi.month - 1]} {helyi.day}. ({napok[helyi.weekday()]}) "
        f"{helyi.hour:02d}:{helyi.minute:02d}"
    )


def hatralevo_szoveg(hatarido_utc: datetime, mostani: datetime | None = None) -> str:
    """"1 nap 4 óra 32 perc" alakú hátralévő idő - a meghívó levélbe a
    kiküldés pillanatában (ott nem frissül, ezért a pontos határidő az
    elsődleges), a személyes oldalon pedig élő visszaszámláló megy."""
    mostani = mostani or most_utc()
    mp = int((hatarido_utc - mostani).total_seconds())
    if mp <= 0:
        return "lejárt"
    nap, marad = divmod(mp, 86400)
    ora, marad = divmod(marad, 3600)
    perc = marad // 60
    darabok = []
    if nap:
        darabok.append(f"{nap} nap")
    if ora:
        darabok.append(f"{ora} óra")
    darabok.append(f"{perc} perc")
    return " ".join(darabok)


def lejart(ak: Ajanlatkeres, mostani: datetime | None = None) -> bool:
    if ak.valaszadasi_hatarido is None:
        return False
    return (mostani or most_utc()) >= ak.valaszadasi_hatarido


def effektiv_allapot(ak: Ajanlatkeres, mostani: datetime | None = None) -> str:
    """A megjelenített állapot: az "ajanlatadas" a határidő lejártával
    automatikusan "dontesre_var"-ként látszik - tárolni nem kell, az időből
    mindig kiszámolható (és nem is csúszhat el)."""
    if ak.allapot == "ajanlatadas" and lejart(ak, mostani):
        return "dontesre_var"
    return ak.allapot


def keresztnev(teljes_nev: str) -> str:
    """Magyar névsorrend: az utolsó szó a keresztnév ("Forgató Feri" -> "Feri")."""
    darabok = (teljes_nev or "").split()
    return darabok[-1] if darabok else ""


def ajanlati_link(token: str) -> str:
    alap = (settings.frontend_base_url or "").rstrip("/")
    return f"{alap}/ajanlat/{token}"


def uj_token() -> str:
    return secrets.token_urlsafe(24)


def osszeg_szoveg(osszeg, penznem: str, brutto: bool) -> str:
    try:
        formazott = f"{float(osszeg):,.0f}".replace(",", " ")
    except (TypeError, ValueError):
        formazott = str(osszeg)
    return f"{formazott} {penznem} ({'bruttó' if brutto else 'nettó'})"


# ---------------------------------------------------------------------------
# E-mail sablonok (a felhasználó által megadott minták szerint). Egyik levél
# sem tartalmazza más résztvevő nevét vagy ajánlati összegét.
# ---------------------------------------------------------------------------

_STILUS = 'style="font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#222;line-height:1.55"'


def _sor(cimke: str, ertek: str | None) -> str:
    if not ertek:
        return ""
    return f"<p style='margin:2px 0'><strong>{cimke}:</strong> {ertek}</p>"


def meghivo_email(ak: Ajanlatkeres, m: AjanlatMeghivott) -> tuple[str, str]:
    """(tárgy, html) - a személyre szóló ajánlatkérő levél."""
    nev = keresztnev(m.employee.full_name)
    hatarido = budapest_szoveg(ak.valaszadasi_hatarido)
    hatra = hatralevo_szoveg(ak.valaszadasi_hatarido) if ak.valaszadasi_hatarido else "–"
    link = ajanlati_link(m.token)
    targy = f"Árajánlat-kérés – {ak.projekt_nev} / {ak.munkakor}"
    html = f"""<div {_STILUS}>
<p>Szia {nev}!</p>
<p>Szeretnénk árajánlatot kérni tőled az alábbi feladatra:</p>
{_sor("Projekt", ak.projekt_nev)}
{_sor("Munkakör", ak.munkakor)}
{_sor("Feladat", ak.leiras)}
{_sor("A munkavégzés várható időpontja", ak.munkavegzes_idopont)}
{_sor("Helyszín", ak.helyszin)}
{_sor("Teljesítési határidő", ak.teljesitesi_hatarido)}
<p style="margin:14px 0 2px 0"><strong>Válaszadási határidő: {hatarido} (magyar idő szerint)</strong></p>
<p style="margin:2px 0;color:#555">A levél kiküldésekor ennyi idő volt hátra: {hatra}. Ez az érték itt nem frissül
- az ajánlati oldalon élő visszaszámlálót találsz.</p>
<p style="margin:18px 0">
  <a href="{link}" style="background:#111;color:#fff;padding:10px 18px;border-radius:6px;text-decoration:none;display:inline-block">Árajánlatot adok</a>
</p>
<p style="border:1px solid #ddd;border-radius:6px;padding:10px 12px;background:#f7f7f7"><strong>{TAJEKOZTATO}</strong></p>
<p>Üdv,<br/>A HYPE csapata</p>
</div>"""
    return targy, html


def nyertes_email(ak: Ajanlatkeres, m: AjanlatMeghivott) -> tuple[str, str]:
    nev = keresztnev(m.employee.full_name)
    kapcsolattarto = ak.kapcsolattarto.full_name if ak.kapcsolattarto else "a HYPE csapata"
    osszeg = osszeg_szoveg(ak.elfogadott_osszeg, ak.elfogadott_penznem or "HUF", bool(ak.elfogadott_brutto))
    feladat_nev = f"{ak.projekt_nev} – {ak.munkakor}"
    targy = f"Számítunk rád! – {ak.projekt_nev} / {ak.munkakor}"
    html = f"""<div {_STILUS}>
<p>Szia {nev}!</p>
<p>Köszönjük az ajánlatodat! Örömmel jelezzük, hogy a(z) <strong>{feladat_nev}</strong> feladatra téged választottunk.</p>
<p>Az ajánlatodban szereplő <strong>{osszeg}</strong> díjazást elfogadtuk.</p>
{_sor("Időpont", ak.munkavegzes_idopont)}
{_sor("Helyszín", ak.helyszin)}
{_sor("Feladat", ak.leiras)}
<p>A munka a tiéd, számítunk rád! A további részletekkel kapcsolatban {kapcsolattarto} segít.</p>
<p>Köszönjük, hogy velünk dolgozol!<br/>A HYPE csapata</p>
</div>"""
    return targy, html


def vesztes_email(ak: Ajanlatkeres, m: AjanlatMeghivott) -> tuple[str, str]:
    """Annak, aki ADOTT ajánlatot, de nem őt választottuk."""
    nev = keresztnev(m.employee.full_name)
    feladat_nev = f"{ak.projekt_nev} – {ak.munkakor}"
    targy = f"Visszajelzés az ajánlatodra – {ak.projekt_nev}"
    html = f"""<div {_STILUS}>
<p>Szia {nev}!</p>
<p>Köszönjük, hogy időt szántál az ajánlatadásra, és jelezted, hogy szívesen dolgoznál velünk a(z)
<strong>{feladat_nev}</strong> feladaton.</p>
<p>Erre a munkára most egy másik partnerünket választottuk. Nagyon köszönjük az érdeklődésedet;
örülünk, ha a következő lehetőségnél is számíthatunk rád!</p>
<p>Üdv,<br/>A HYPE csapata</p>
</div>"""
    return targy, html


def nem_adott_email(ak: Ajanlatkeres, m: AjanlatMeghivott) -> tuple[str, str]:
    """RÖVID lezáró annak, aki meghívót kapott, de nem adott ajánlatot -
    kifejezetten NEM köszön meg nem létező ajánlatot (a felhasználó kérése)."""
    nev = keresztnev(m.employee.full_name)
    feladat_nev = f"{ak.projekt_nev} – {ak.munkakor}"
    targy = f"Lezárult az ajánlatkérés – {ak.projekt_nev}"
    html = f"""<div {_STILUS}>
<p>Szia {nev}!</p>
<p>A(z) <strong>{feladat_nev}</strong> feladatra kiírt ajánlatkérésünk lezárult, a pozíciót betöltöttük.</p>
<p>Reméljük, egy következő lehetőségnél együtt tudunk dolgozni!</p>
<p>Üdv,<br/>A HYPE csapata</p>
</div>"""
    return targy, html


def nyertes_nelkul_email(ak: Ajanlatkeres, m: AjanlatMeghivott, adott_ajanlatot: bool) -> tuple[str, str]:
    """Nyertes nélküli lezárás - ennek megfelelő, külön szöveg."""
    nev = keresztnev(m.employee.full_name)
    feladat_nev = f"{ak.projekt_nev} – {ak.munkakor}"
    targy = f"Lezárult az ajánlatkérés – {ak.projekt_nev}"
    if adott_ajanlatot:
        torzs = (
            f"<p>Köszönjük az ajánlatodat a(z) <strong>{feladat_nev}</strong> feladatra. "
            "Az ajánlatkérést most nyertes kihirdetése nélkül zártuk le - a feladat kiosztására "
            "ezúttal nem került sor.</p>"
            "<p>Nagyon köszönjük az érdeklődésedet; örülünk, ha a következő lehetőségnél is számíthatunk rád!</p>"
        )
    else:
        torzs = (
            f"<p>A(z) <strong>{feladat_nev}</strong> feladatra kiírt ajánlatkérésünket nyertes "
            "kihirdetése nélkül lezártuk.</p>"
            "<p>Reméljük, egy következő lehetőségnél együtt tudunk dolgozni!</p>"
        )
    html = f"""<div {_STILUS}>
<p>Szia {nev}!</p>
{torzs}
<p>Üdv,<br/>A HYPE csapata</p>
</div>"""
    return targy, html


def visszavonas_email(ak: Ajanlatkeres, m: AjanlatMeghivott) -> tuple[str, str]:
    nev = keresztnev(m.employee.full_name)
    feladat_nev = f"{ak.projekt_nev} – {ak.munkakor}"
    targy = f"Visszavont ajánlatkérés – {ak.projekt_nev}"
    html = f"""<div {_STILUS}>
<p>Szia {nev}!</p>
<p>A(z) <strong>{feladat_nev}</strong> feladatra kiírt ajánlatkérésünket visszavontuk - a feladatra
most nem keresünk partnert.</p>
<p>Köszönjük a megértésedet, és reméljük, hamarosan együtt dolgozhatunk!</p>
<p>Üdv,<br/>A HYPE csapata</p>
</div>"""
    return targy, html


# ---------------------------------------------------------------------------
# Könyvelt küldés: a kiküldés sikere/hibája meghívottanként rögzül, az
# újrapróbálás CSAK a sikertelen leveleket ismétli.
# ---------------------------------------------------------------------------


def _cimzett(m: AjanlatMeghivott) -> str | None:
    return (m.email_cim or (m.employee.email if m.employee else None) or "").strip() or None


def meghivok_kikuldese(db: Session, ak: Ajanlatkeres, csak_hibasak: bool = False) -> dict:
    """A meghívók kiküldése. Idempotens: aki már sikeresen megkapta, annak nem
    megy újra; hibánál a hiba szövege eltárolódik, és újrapróbálható."""
    kikuldve = 0
    hibak: list[str] = []
    for m in ak.meghivottak:
        if m.meghivo_kikuldve is not None:
            continue
        if csak_hibasak and m.meghivo_hiba is None:
            continue
        cim = _cimzett(m)
        if not cim:
            m.meghivo_hiba = "Nincs e-mail cím a munkatárs adatlapján."
            hibak.append(f"{m.employee.full_name}: nincs e-mail cím")
            continue
        m.email_cim = cim
        targy, html = meghivo_email(ak, m)
        try:
            google_email.send_message([cim], targy, html)
            m.meghivo_kikuldve = most_utc()
            m.meghivo_hiba = None
            kikuldve += 1
        except Exception as exc:  # noqa: BLE001 - a hibát tároljuk, nem dobjuk tovább
            m.meghivo_hiba = str(exc)
            hibak.append(f"{m.employee.full_name}: {exc}")
        # Minden kísérlet után mentünk: egy későbbi összeomlás se veszítse el,
        # kinek ment már ki levél (dupla küldés ellen).
        db.commit()
    return {"kikuldve": kikuldve, "hibak": hibak}


def eredmenyek_kikuldese(db: Session, ak: Ajanlatkeres, csak_hibasak: bool = False) -> dict:
    """Az eredmény-értesítők kiküldése a döntés (vagy nyertes nélküli lezárás /
    visszavonás) után. Ugyanaz a könyvelés, mint a meghívóknál."""
    kikuldve = 0
    hibak: list[str] = []
    for m in ak.meghivottak:
        if m.eredmeny_kikuldve is not None:
            continue
        if csak_hibasak and m.eredmeny_hiba is None:
            continue
        # Aki meghívót sem kapott (pl. nincs címe), annak eredményt sem tudunk küldeni.
        cim = _cimzett(m)
        if not cim:
            m.eredmeny_hiba = "Nincs e-mail cím a munkatárs adatlapján."
            hibak.append(f"{m.employee.full_name}: nincs e-mail cím")
            continue
        adott = m.ajanlat is not None and m.ajanlat.visszavonva is None
        if ak.allapot == "kiosztva":
            if m.id == ak.nyertes_meghivott_id:
                targy, html = nyertes_email(ak, m)
            elif adott:
                targy, html = vesztes_email(ak, m)
            else:
                targy, html = nem_adott_email(ak, m)
        elif ak.allapot == "lezarva_nyertes_nelkul":
            targy, html = nyertes_nelkul_email(ak, m, adott)
        elif ak.allapot == "visszavonva":
            # Csak annak, aki egyáltalán kapott meghívót - akinek ki sem ment,
            # azt nem zavarjuk visszavonó levéllel.
            if m.meghivo_kikuldve is None:
                continue
            targy, html = visszavonas_email(ak, m)
        else:
            continue
        try:
            google_email.send_message([cim], targy, html)
            m.eredmeny_kikuldve = most_utc()
            m.eredmeny_hiba = None
            kikuldve += 1
        except Exception as exc:  # noqa: BLE001
            m.eredmeny_hiba = str(exc)
            hibak.append(f"{m.employee.full_name}: {exc}")
        db.commit()
    return {"kikuldve": kikuldve, "hibak": hibak}


# ---------------------------------------------------------------------------
# Kiválasztás és lezárás - zárolással (két egyidejű döntés sem adhat két nyertest).
# ---------------------------------------------------------------------------


def _zarolt_ajanlatkeres(db: Session, ajanlatkeres_id: int) -> Ajanlatkeres:
    ak = db.execute(
        select(Ajanlatkeres).where(Ajanlatkeres.id == ajanlatkeres_id).with_for_update()
    ).scalar_one_or_none()
    if ak is None:
        raise HTTPException(status_code=404, detail="Az ajánlatkérés nem található.")
    return ak


def kivalasztas(db: Session, ajanlatkeres_id: int, meghivott_id: int) -> Ajanlatkeres:
    """A NYERTES kijelölése. Csak a válaszadási határidő lejárta után, csak
    élő (nem visszavont) ajánlatra, és csak egyszer - a sor zárolva van, tehát
    két egyidejű belső döntés közül a második hibát kap, nem második nyertest."""
    ak = _zarolt_ajanlatkeres(db, ajanlatkeres_id)
    if ak.allapot == "kiosztva":
        raise HTTPException(status_code=409, detail="Ehhez a pozícióhoz már van kiválasztott nyertes.")
    if ak.allapot != "ajanlatadas":
        raise HTTPException(status_code=400, detail="Ez az ajánlatkérés nem áll döntésre váró állapotban.")
    if not lejart(ak):
        raise HTTPException(
            status_code=400,
            detail="A kiválasztás csak a válaszadási határidő lejárta után lehetséges "
            f"(határidő: {budapest_szoveg(ak.valaszadasi_hatarido)} magyar idő szerint).",
        )
    meghivott = next((m for m in ak.meghivottak if m.id == meghivott_id), None)
    if meghivott is None:
        raise HTTPException(status_code=404, detail="A meghívott nem tartozik ehhez az ajánlatkéréshez.")
    ajanlat = meghivott.ajanlat
    if ajanlat is None or ajanlat.visszavonva is not None:
        raise HTTPException(status_code=400, detail="Ennek a meghívottnak nincs élő árajánlata.")

    ak.nyertes_meghivott_id = meghivott.id
    ak.elfogadott_osszeg = ajanlat.osszeg
    ak.elfogadott_penznem = ajanlat.penznem
    ak.elfogadott_brutto = ajanlat.brutto
    ak.allapot = "kiosztva"
    ak.lezarva = most_utc()
    # A DÖNTÉS ITT VÉGLEGESEN RÖGZÜL - az értesítők küldése ez UTÁN, külön
    # lépésben megy (eredmenyek_kikuldese): egy levélhiba nem írhatja felül
    # és nem törölheti a döntést.
    db.commit()
    db.refresh(ak)
    return ak


def lezaras_nyertes_nelkul(db: Session, ajanlatkeres_id: int, megjegyzes: str | None) -> Ajanlatkeres:
    ak = _zarolt_ajanlatkeres(db, ajanlatkeres_id)
    if ak.allapot == "kiosztva":
        raise HTTPException(status_code=409, detail="Ehhez a pozícióhoz már van kiválasztott nyertes.")
    if ak.allapot not in ("ajanlatadas",):
        raise HTTPException(status_code=400, detail="Csak folyamatban lévő ajánlatkérés zárható le.")
    ak.allapot = "lezarva_nyertes_nelkul"
    ak.lezarva = most_utc()
    ak.lezaras_megjegyzes = (megjegyzes or "").strip() or None
    db.commit()
    db.refresh(ak)
    return ak


def visszavonas(db: Session, ajanlatkeres_id: int) -> Ajanlatkeres:
    ak = _zarolt_ajanlatkeres(db, ajanlatkeres_id)
    if ak.allapot in ("kiosztva", "lezarva_nyertes_nelkul", "visszavonva"):
        raise HTTPException(status_code=400, detail="Ez az ajánlatkérés már lezárult.")
    ak.allapot = "visszavonva"
    ak.lezarva = most_utc()
    db.commit()
    db.refresh(ak)
    return ak


def token_alapjan(db: Session, token: str) -> AjanlatMeghivott:
    m = db.scalar(select(AjanlatMeghivott).where(AjanlatMeghivott.token == token))
    if m is None:
        raise HTTPException(status_code=404, detail="Ez az ajánlati link nem érvényes.")
    return m


def ajanlat_bekuldes(
    db: Session,
    token: str,
    *,
    osszeg: float,
    penznem: str,
    brutto: bool,
    megjegyzes: str | None,
    vallalja: bool,
) -> MunkaArajanlat:
    """Ajánlat beküldése/módosítása a személyes linkről. A határidőt ITT, a
    szerveren ellenőrizzük (a felhasználó kérése): lejárat után egy korábban
    megnyitott űrlap sem adhat be ajánlatot - a visszaszámláló és a gomb
    letiltása csak kényelem."""
    m = token_alapjan(db, token)
    ak = m.ajanlatkeres
    if ak.allapot != "ajanlatadas":
        raise HTTPException(status_code=410, detail="Ez az ajánlatkérés már nem fogad ajánlatot.")
    if lejart(ak):
        raise HTTPException(
            status_code=410,
            detail="Az ajánlatadás lezárult. A kiválasztás folyamatban van, az eredményről külön értesítünk.",
        )
    if osszeg is None or float(osszeg) <= 0:
        raise HTTPException(status_code=400, detail="Az ajánlott összeg kötelező, és nullánál nagyobb kell legyen.")
    if not vallalja:
        raise HTTPException(
            status_code=400,
            detail="Az ajánlat beküldéséhez erősítsd meg, hogy a megadott időpont és feladat vállalható.",
        )
    penznem = (penznem or "HUF").strip().upper()[:10]
    mostani = most_utc()
    if m.ajanlat is None:
        m.ajanlat = MunkaArajanlat(
            osszeg=osszeg,
            penznem=penznem,
            brutto=brutto,
            megjegyzes=(megjegyzes or "").strip() or None,
            vallalja=True,
            bekuldve=mostani,
        )
    else:
        a = m.ajanlat
        a.osszeg = osszeg
        a.penznem = penznem
        a.brutto = brutto
        a.megjegyzes = (megjegyzes or "").strip() or None
        a.vallalja = True
        a.modositva = mostani
        # Visszavont ajánlat újra beküldve: újra él.
        if a.visszavonva is not None:
            a.visszavonva = None
            a.bekuldve = a.bekuldve or mostani
    db.commit()
    db.refresh(m)
    return m.ajanlat


def ajanlat_visszavonas(db: Session, token: str) -> None:
    m = token_alapjan(db, token)
    ak = m.ajanlatkeres
    if ak.allapot != "ajanlatadas" or lejart(ak):
        raise HTTPException(status_code=410, detail="Az ajánlatadás lezárult - az ajánlat már nem vonható vissza.")
    if m.ajanlat is None or m.ajanlat.visszavonva is not None:
        raise HTTPException(status_code=400, detail="Nincs visszavonható ajánlat.")
    m.ajanlat.visszavonva = most_utc()
    db.commit()


def meghivottak_beallitasa(db: Session, ak: Ajanlatkeres, employee_ids: list[int]) -> None:
    """A meghívotti kör beállítása (csak piszkozatban). A megmaradók tokenje
    nem változik; az újak friss tokent kapnak; a kikerülők sora törlődik."""
    if ak.allapot != "piszkozat":
        raise HTTPException(status_code=400, detail="A meghívottak csak piszkozat állapotban módosíthatók.")
    kert = list(dict.fromkeys(employee_ids))
    letezok = set(db.scalars(select(Employee.id).where(Employee.id.in_(kert))).all()) if kert else set()
    hianyzo = [i for i in kert if i not in letezok]
    if hianyzo:
        raise HTTPException(status_code=400, detail=f"Ismeretlen munkatárs-azonosító: {hianyzo}")
    megvan = {m.employee_id: m for m in ak.meghivottak}
    for m in list(ak.meghivottak):
        if m.employee_id not in letezok:
            db.delete(m)
    for eid in kert:
        if eid not in megvan:
            db.add(AjanlatMeghivott(ajanlatkeres_id=ak.id, employee_id=eid, token=uj_token()))
    db.commit()
