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
    "Kérjük, a megadott határidőig jelezd, ha érdekel a feladat és ráérsz. A jelentkezők "
    "közül a határidő lejárta után választunk, és az eredményről külön értesítünk. "
    "A jelentkezés még nem jelent megbízást."
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


def ajanlati_link(token: str) -> str:
    alap = (settings.frontend_base_url or "").rstrip("/")
    return f"{alap}/ajanlat/{token}"


def uj_token() -> str:
    return secrets.token_urlsafe(24)


# ---------------------------------------------------------------------------
# E-mail sablonok (a felhasználó által megadott minták szerint). Egyik levél
# sem tartalmazza más résztvevő nevét vagy ajánlati összegét.
# ---------------------------------------------------------------------------

_STILUS = 'style="font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#222;line-height:1.55"'

#: Egységes levélzárás (a felhasználó kérése): "Köszönettel," + ugyanaz a
#: HYPE-aláírás, mint a diszpó-leveleknél.
ZARAS = "<p>Köszönettel,</p>" + google_email.HYPE_ALAIRAS_HTML


def _sor(cimke: str, ertek: str | None) -> str:
    if not ertek:
        return ""
    return f"<p style='margin:2px 0'><strong>{cimke}:</strong> {ertek}</p>"


def meghivo_email(ak: Ajanlatkeres, m: AjanlatMeghivott) -> tuple[str, str]:
    """(tárgy, html) - a személyre szóló ajánlatkérő levél."""
    nev = (m.employee.full_name or "").strip()
    hatarido = budapest_szoveg(ak.valaszadasi_hatarido)
    hatra = hatralevo_szoveg(ak.valaszadasi_hatarido) if ak.valaszadasi_hatarido else "–"
    link = ajanlati_link(m.token)
    targy = f"Munkafelajánlás – {ak.projekt_nev} / {ak.munkakor}"
    html = f"""<div {_STILUS}>
<p>Kedves {nev}!</p>
<p>Szeretnénk megkérdezni, érdekel-e az alábbi feladat, és ráérsz-e:</p>
{_sor("Projekt", ak.projekt_nev)}
{_sor("Munkakör", ak.munkakor)}
{_sor("Feladat", ak.leiras)}
{_sor("A munkavégzés várható időpontja", ak.munkavegzes_idopont)}
{_sor("Helyszín", ak.helyszin)}
{_sor("Teljesítési határidő", ak.teljesitesi_hatarido)}
<p style="margin:14px 0 2px 0"><strong>Válaszadási határidő: {hatarido} (magyar idő szerint)</strong></p>
<p style="margin:2px 0;color:#555">A levél kiküldésekor ennyi idő volt hátra: {hatra}. Ez az érték itt nem frissül
- a jelentkezési oldalon élő visszaszámlálót találsz.</p>
<p style="margin:18px 0">
  <a href="{link}" style="background:#111;color:#fff;padding:10px 18px;border-radius:6px;text-decoration:none;display:inline-block">Érdekel, jelentkezem</a>
</p>
<p style="margin:2px 0;color:#555">Ha nem érsz rá, kérjük, azt is jelezd az oldalon - azzal is sokat segítesz.</p>
<p style="border:1px solid #ddd;border-radius:6px;padding:10px 12px;background:#f7f7f7"><strong>{TAJEKOZTATO}</strong></p>
{ZARAS}
</div>"""
    return targy, html


def nyertes_email(ak: Ajanlatkeres, m: AjanlatMeghivott) -> tuple[str, str]:
    nev = (m.employee.full_name or "").strip()
    kapcsolattarto = ak.kapcsolattarto.full_name if ak.kapcsolattarto else "a HYPE csapata"
    feladat_nev = f"{ak.projekt_nev} – {ak.munkakor}"
    targy = f"Számítunk rád! – {ak.projekt_nev} / {ak.munkakor}"
    html = f"""<div {_STILUS}>
<p>Kedves {nev}!</p>
<p>Köszönjük a jelentkezésedet! Örömmel jelezzük, hogy a(z) <strong>{feladat_nev}</strong> feladatra téged választottunk.</p>
{_sor("Időpont", ak.munkavegzes_idopont)}
{_sor("Helyszín", ak.helyszin)}
{_sor("Feladat", ak.leiras)}
<p>A munka a tiéd, számítunk rád! A további részletekkel kapcsolatban {kapcsolattarto} segít.</p>
<p>Köszönjük, hogy velünk dolgozol!</p>
{ZARAS}
</div>"""
    return targy, html


def vesztes_email(ak: Ajanlatkeres, m: AjanlatMeghivott) -> tuple[str, str]:
    """Annak, aki JELENTKEZETT, de nem őt választottuk ("ezt most más vitte
    el" - a felhasználó kérése)."""
    nev = (m.employee.full_name or "").strip()
    feladat_nev = f"{ak.projekt_nev} – {ak.munkakor}"
    targy = f"Visszajelzés a jelentkezésedre – {ak.projekt_nev}"
    html = f"""<div {_STILUS}>
<p>Kedves {nev}!</p>
<p>Köszönjük, hogy jelezted: érdekel a(z) <strong>{feladat_nev}</strong> feladat, és ráérsz.</p>
<p>Sajnos ezt a munkát most egy másik partnerünk vitte el. Nagyon köszönjük az érdeklődésedet;
örülünk, ha a következő lehetőségnél is számíthatunk rád!</p>
{ZARAS}
</div>"""
    return targy, html


def nem_adott_email(ak: Ajanlatkeres, m: AjanlatMeghivott) -> tuple[str, str]:
    """RÖVID lezáró annak, aki meghívót kapott, de nem jelentkezett -
    kifejezetten NEM köszön meg nem létező jelentkezést (a felhasználó kérése)."""
    nev = (m.employee.full_name or "").strip()
    feladat_nev = f"{ak.projekt_nev} – {ak.munkakor}"
    targy = f"Lezárult a munkafelajánlás – {ak.projekt_nev}"
    html = f"""<div {_STILUS}>
<p>Kedves {nev}!</p>
<p>A(z) <strong>{feladat_nev}</strong> feladatra kiírt megkeresésünk lezárult, a pozíciót betöltöttük.</p>
<p>Reméljük, egy következő lehetőségnél együtt tudunk dolgozni!</p>
{ZARAS}
</div>"""
    return targy, html


def nyertes_nelkul_email(ak: Ajanlatkeres, m: AjanlatMeghivott, adott_ajanlatot: bool) -> tuple[str, str]:
    """Nyertes nélküli lezárás - ennek megfelelő, külön szöveg."""
    nev = (m.employee.full_name or "").strip()
    feladat_nev = f"{ak.projekt_nev} – {ak.munkakor}"
    targy = f"Lezárult a munkafelajánlás – {ak.projekt_nev}"
    if adott_ajanlatot:
        torzs = (
            f"<p>Köszönjük a jelentkezésedet a(z) <strong>{feladat_nev}</strong> feladatra. "
            "A megkeresést most a feladat kiosztása nélkül zártuk le.</p>"
            "<p>Nagyon köszönjük az érdeklődésedet; örülünk, ha a következő lehetőségnél is számíthatunk rád!</p>"
        )
    else:
        torzs = (
            f"<p>A(z) <strong>{feladat_nev}</strong> feladatra kiírt megkeresésünket a feladat "
            "kiosztása nélkül lezártuk.</p>"
            "<p>Reméljük, egy következő lehetőségnél együtt tudunk dolgozni!</p>"
        )
    html = f"""<div {_STILUS}>
<p>Kedves {nev}!</p>
{torzs}
{ZARAS}
</div>"""
    return targy, html


def visszavonas_email(ak: Ajanlatkeres, m: AjanlatMeghivott) -> tuple[str, str]:
    nev = (m.employee.full_name or "").strip()
    feladat_nev = f"{ak.projekt_nev} – {ak.munkakor}"
    targy = f"Visszavont munkafelajánlás – {ak.projekt_nev}"
    html = f"""<div {_STILUS}>
<p>Kedves {nev}!</p>
<p>A(z) <strong>{feladat_nev}</strong> feladatra kiírt megkeresésünket visszavontuk - a feladatra
most nem keresünk partnert.</p>
<p>Köszönjük a megértésedet, és reméljük, hamarosan együtt dolgozhatunk!</p>
{ZARAS}
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
        adott = m.ajanlat is not None and m.ajanlat.visszavonva is None and m.ajanlat.vallalja
        # Aki kifejezetten jelezte, hogy NEM ÉR RÁ, annak nem küldünk
        # eredmény-levelet: ő már lemondta, se "más vitte el", se rövid
        # lezáró nem jár neki (a felhasználó kérése szerinti gombhoz).
        lemondta = m.ajanlat is not None and m.ajanlat.visszavonva is None and not m.ajanlat.vallalja
        if lemondta and ak.allapot in ("kiosztva", "lezarva_nyertes_nelkul"):
            continue
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
    if ajanlat is None or ajanlat.visszavonva is not None or not ajanlat.vallalja:
        raise HTTPException(status_code=400, detail="Ez a meghívott nem jelentkezett (vagy nem ér rá).")

    # Díjazást a rendszer NEM tart nyilván (a felhasználó kérése): az árban a
    # kiválasztottal a rendszeren kívül egyeznek meg.
    ak.nyertes_meghivott_id = meghivott.id
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
    megjegyzes: str | None,
    vallalja: bool,
) -> MunkaArajanlat:
    """JELENTKEZÉS beküldése/módosítása a személyes linkről ("érdekel és
    ráérek") - árat nem kérünk és nem tárolunk (a felhasználó kérése: a
    díjazásról a kiválasztottal a rendszeren kívül egyeznek meg). A határidőt
    ITT, a szerveren ellenőrizzük: lejárat után egy korábban megnyitott űrlap
    sem tud jelentkezni - a visszaszámláló és a gomb letiltása csak kényelem."""
    m = token_alapjan(db, token)
    ak = m.ajanlatkeres
    if ak.allapot != "ajanlatadas":
        raise HTTPException(status_code=410, detail="Ez a munkafelajánlás már nem fogad jelentkezést.")
    if lejart(ak):
        raise HTTPException(
            status_code=410,
            detail="A jelentkezés lezárult. A kiválasztás folyamatban van, az eredményről külön értesítünk.",
        )
    if not vallalja:
        raise HTTPException(
            status_code=400,
            detail="A jelentkezéshez erősítsd meg, hogy érdekel a feladat, és a megadott időpontban ráérsz.",
        )
    mostani = most_utc()
    if m.ajanlat is None:
        m.ajanlat = MunkaArajanlat(
            megjegyzes=(megjegyzes or "").strip() or None,
            vallalja=True,
            bekuldve=mostani,
        )
    else:
        a = m.ajanlat
        a.megjegyzes = (megjegyzes or "").strip() or None
        a.vallalja = True
        a.modositva = mostani
        # Visszavont jelentkezés újra beküldve: újra él.
        if a.visszavonva is not None:
            a.visszavonva = None
            a.bekuldve = a.bekuldve or mostani
    db.commit()
    db.refresh(m)
    return m.ajanlat


def nem_er_ra_bekuldes(db: Session, token: str, megjegyzes: str | None) -> MunkaArajanlat:
    """"SAJNOS NEM ÉREK RÁ" válasz (a felhasználó kérése): a meghívott
    kifejezetten jelzi, hogy nem vállalja - ez más, mint a nem-válaszolás.
    A határidőig ez is meggondolható (újra lehet jelentkezni)."""
    m = token_alapjan(db, token)
    ak = m.ajanlatkeres
    if ak.allapot != "ajanlatadas":
        raise HTTPException(status_code=410, detail="Ez a munkafelajánlás már nem fogad választ.")
    if lejart(ak):
        raise HTTPException(status_code=410, detail="A válaszadás lezárult.")
    mostani = most_utc()
    if m.ajanlat is None:
        m.ajanlat = MunkaArajanlat(
            megjegyzes=(megjegyzes or "").strip() or None,
            vallalja=False,
            bekuldve=mostani,
        )
    else:
        a = m.ajanlat
        a.vallalja = False
        a.megjegyzes = (megjegyzes or "").strip() or None
        a.modositva = mostani
        a.visszavonva = None
    db.commit()
    db.refresh(m)
    return m.ajanlat


def ajanlat_visszavonas(db: Session, token: str) -> None:
    m = token_alapjan(db, token)
    ak = m.ajanlatkeres
    if ak.allapot != "ajanlatadas" or lejart(ak):
        raise HTTPException(status_code=410, detail="A jelentkezés lezárult - már nem vonható vissza.")
    if m.ajanlat is None or m.ajanlat.visszavonva is not None:
        raise HTTPException(status_code=400, detail="Nincs visszavonható jelentkezés.")
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
