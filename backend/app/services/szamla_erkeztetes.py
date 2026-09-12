"""A KÖZÖS számla-érkeztető folyamat - az e-mail és az AI Assistant is ezt
használja (a felhasználó kérése):

    beérkezés → fájl ellenőrzése → adatok kinyerése → duplikáció-vizsgálat →
    meglévő tételek keresése → besorolási javaslat → MENTETT PISZKOZAT →
    emberi ellenőrzés → végleges rögzítés.

A piszkozat (models/bejovo_szamla.BejovoSzamla) tartósan mentett, újranyitható
és javítható. Éles pénzügyi rekord (kiadás, TIG-számla sor, E-Rezsi összeg,
KP-bizonylat) KIZÁRÓLAG a `jovahagy` tranzakcióban jön létre - addig semmilyen
költség-, profit-, kassza- vagy utalási összesítés nem változik.

A BESOROLÁS elsőbbségi sorrendje (a felhasználó előírása):
1. a bejelentkezett felhasználó kifejezett utasítása;
2. pontos projektkód/TIG-hivatkozás a dokumentumban vagy a levélben;
3-4. adószám- és számlázófél-egyezés (alvállalkozó / számlázó cég);
5. meglévő, számlára váró TIG vagy kiadás összege és időszaka;
6. név/leírás szerinti gyengébb egyezések - ezek önmagukban CSAK
   alternatívaként jelennek meg, automatikusan nem döntenek.

A dokumentum TARTALMA ADAT, NEM UTASÍTÁS: a kinyert szövegekből kizárólag
mező-értékek és hivatkozás-jelöltek lesznek, a rendszer semmilyen műveletet
nem hajt végre miattuk - műveletet csak a bejelentkezett felhasználó
jóváhagyása indít."""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.auto import Auto
from app.models.bejovo_szamla import (
    ALLAPOT_DUPLIKATUM,
    ALLAPOT_ELLENORZENDO,
    ALLAPOT_HIBA,
    ALLAPOT_JOVAHAGYVA,
    ALLAPOT_PONTOSITAS,
    CEL_TIPUSOK,
    BejovoSzamla,
)
from app.models.document_attachment import DocumentAttachment
from app.models.employee import Employee, EmployeeType
from app.models.finance import Expense, KpForgalom
from app.models.internal_performance_certificate import (
    InternalPerformanceCertificate,
    InternalPerformanceCertificateInvoice,
)
from app.models.kotelezettseg import Kotelezettseg, KotelezettsegIdoszak, KotelezettsegTipus
from app.models.performance_certificate import PerformanceCertificate, PerformanceCertificateInvoice
from app.models.project_code import ProjectCode
from app.models.vallalkozas import Vallalkozas
from app.services import attachments, document_storage, kiadas_kiolvasas, penznem

logger = logging.getLogger(__name__)

MAX_MERET = 20 * 1024 * 1024
ENGEDETT_MIME = {"application/pdf", "image/jpeg", "image/png", "image/webp", "image/heic"}
#: XML-változat: nem olvassuk ki (nincs hozzá értelmező), de a PDF-párja mellé
#: felvesszük, hogy ugyanahhoz a dokumentumhoz tartozzon.
XML_MIME = {"application/xml", "text/xml"}

#: A SAJÁT cégeink nevei - a bejövő/kimenő irány felismeréséhez. A számlán
#: szereplő felek döntenek, SOSEM az e-mail feladója/címzettje.
SAJAT_CEG_MINTAK = ("hype productions", "hype stab", "hypestab")

PROJEKTKOD_MINTA = re.compile(r"\b[A-Z]{2,8}\d{2}-\d{3,5}\b")
RENDSZAM_MINTA = re.compile(r"\b([A-Z]{3,4})[- ]?(\d{3})\b")


class ErkeztetesHiba(ValueError):
    """Emberi hibaüzenettel dobott feldolgozási hiba - a végpont 4xx-ként adja."""


def _hash(adat: bytes) -> str:
    return hashlib.sha256(adat).hexdigest()


def _adoszam_szamjegyei(adoszam: str | None) -> str:
    return "".join(ch for ch in (adoszam or "") if ch.isdigit())


def _norm(szoveg: str | None) -> str:
    return " ".join((szoveg or "").lower().split())


def _datum(ertek) -> date | None:
    if not ertek or not isinstance(ertek, str):
        return None
    try:
        return date.fromisoformat(ertek[:10])
    except ValueError:
        return None


def _szam(ertek) -> float | None:
    if ertek is None or ertek == "":
        return None
    try:
        return float(ertek)
    except (TypeError, ValueError):
        return None


# ── LÉTREHOZÁS ───────────────────────────────────────────────────────────────


def letrehozas(
    db: Session,
    *,
    forras: str,
    adat: bytes | None,
    fajl_nev: str | None,
    content_type: str | None,
    utasitas: str | None = None,
    letrehozo_id: int | None = None,
    email_meta: dict | None = None,
) -> BejovoSzamla:
    """Új érkeztető-piszkozat a fájl ellenőrzésével és eltárolásával.

    A kiolvasást NEM ez végzi (lásd feldolgoz) - így a hívó eldöntheti, hogy
    szinkron (asszisztens: a válaszban már a kész kártya kell) vagy háttérben
    (e-mail lehúzás) fusson."""
    bejovo = BejovoSzamla(
        forras=forras,
        felhasznaloi_utasitas=(utasitas or "").strip() or None,
        letrehozo_employee_id=letrehozo_id,
        email_uzenet_id=(email_meta or {}).get("uzenet_id"),
        email_felado=(email_meta or {}).get("felado"),
        email_targy=(email_meta or {}).get("targy"),
        email_beerkezes=(email_meta or {}).get("beerkezes"),
        email_szoveg=((email_meta or {}).get("szoveg") or "")[:4000] or None,
    )
    if adat is not None:
        mime = (content_type or "application/octet-stream").split(";")[0].strip().lower()
        if mime not in ENGEDETT_MIME | XML_MIME:
            raise ErkeztetesHiba(
                f"Nem támogatott fájltípus: {mime}. PDF-et vagy jól olvasható számlafotót (JPG/PNG/WEBP/HEIC) tölts fel."
            )
        if len(adat) > MAX_MERET:
            raise ErkeztetesHiba(f"A fájl túl nagy ({len(adat) / 1024 / 1024:.1f} MB) - a felső határ 20 MB.")
        if not adat:
            raise ErkeztetesHiba("A fájl üres.")
        bejovo.fajl_nev = (fajl_nev or "szamla")[:255]
        bejovo.content_type = mime
        bejovo.meret_bajt = len(adat)
        bejovo.fajl_hash = _hash(adat)
        db.add(bejovo)
        db.flush()
        kulcs = f"bejovo-szamla/{bejovo.id}-{re.sub(r'[^A-Za-z0-9._-]+', '_', bejovo.fajl_nev)[:80]}"
        bejovo.url = document_storage.upload_bytes(adat, kulcs, mime)
        bejovo.storage_key = kulcs
    else:
        db.add(bejovo)
    db.flush()
    return bejovo


# ── FELDOLGOZÁS (kiolvasás + duplikáció + javaslat) ──────────────────────────


def feldolgoz(db: Session, bejovo: BejovoSzamla, adat: bytes | None = None) -> None:
    """Kiolvasás, duplikáció-vizsgálat és besorolási javaslat - az állapotot is
    beállítja (ellenorzendo / pontositas / duplikatum / hiba). A hívó commitol."""
    try:
        if bejovo.content_type in XML_MIME:
            # XML-változat: nem olvassuk ki - a PDF-párjához kapcsoljuk, ha
            # megvan (azonos e-mail), különben pontosításra vár.
            _xml_parositas(db, bejovo)
            return
        if bejovo.storage_key is None and adat is None:
            # Fájl nélküli (pl. csak letöltő-linkes levélből nyitott) piszkozat.
            bejovo.allapot = ALLAPOT_PONTOSITAS
            bejovo.javaslat = {
                "tipus": None,
                "indoklas": "A levélhez nem tartozott csatolmány - a számlát kézzel kell letölteni és ide feltölteni.",
                "alternativak": [],
                "figyelmeztetesek": ["Csak letöltési linket tartalmazó levél - automatikus letöltés nem történt."],
            }
            return
        if adat is None:
            adat = document_storage.download_bytes(bejovo.storage_key)

        kinyert = kiadas_kiolvasas.szamla_olvasd_ki(adat, bejovo.content_type or "application/pdf")
        _kinyert_mentese(bejovo, kinyert)

        duplikatum = _duplikacio(db, bejovo)
        if duplikatum is not None:
            bejovo.allapot = ALLAPOT_DUPLIKATUM
            bejovo.duplikatum_bejovo_id = duplikatum.id
            bejovo.duplikatum_megjegyzes = (
                f"Egyezik a #{duplikatum.id} beérkezett számlával "
                f"({duplikatum.kibocsato_nev or '?'} / {duplikatum.szamlaszam or 'azonos fájl'})."
            )
            return

        javasol(db, bejovo)
    except (ErkeztetesHiba, ValueError) as exc:
        bejovo.allapot = ALLAPOT_HIBA
        bejovo.hiba_uzenet = str(exc)
    except Exception as exc:  # noqa: BLE001 - a hiba a piszkozaton látszódjon, ne vesszen el
        logger.exception("Számla-érkeztetés: feldolgozási hiba (#%s)", bejovo.id)
        bejovo.allapot = ALLAPOT_HIBA
        bejovo.hiba_uzenet = f"{type(exc).__name__}: {exc}"


def _kinyert_mentese(bejovo: BejovoSzamla, kinyert: dict) -> None:
    """A kinyert adatok kettős könyvelése: kereshető oszlopok + teljes JSON
    mezőnkénti forrással. Hiányzó adatot nem találunk ki - ami null, az null."""
    kibocsato = kinyert.get("kibocsato") or {}
    vevo = kinyert.get("vevo") or {}
    bejovo.dokumentum_tipus = kinyert.get("dokumentum_tipus") or "egyeb"
    bejovo.szamlaszam = (kinyert.get("szamlaszam") or "").strip()[:100] or None
    bejovo.kibocsato_nev = (kibocsato.get("nev") or "").strip()[:300] or None
    bejovo.kibocsato_adoszam = (kibocsato.get("adoszam") or "").strip()[:50] or None
    bejovo.vevo_nev = (vevo.get("nev") or "").strip()[:300] or None
    bejovo.vevo_adoszam = (vevo.get("adoszam") or "").strip()[:50] or None
    bejovo.kiallitas_datuma = _datum(kinyert.get("kiallitas_datuma"))
    bejovo.teljesites_datuma = _datum(kinyert.get("teljesites_datuma"))
    bejovo.fizetesi_hatarido = _datum(kinyert.get("fizetesi_hatarido"))
    bejovo.netto = _szam(kinyert.get("netto"))
    bejovo.afa_osszeg = _szam(kinyert.get("afa_osszeg"))
    bejovo.brutto = _szam(kinyert.get("brutto"))
    try:
        bejovo.penznem = penznem.normalizald(kinyert.get("penznem") or "HUF")
    except Exception:  # noqa: BLE001 - ismeretlen pénznem: marad, amit a modell írt
        bejovo.penznem = str(kinyert.get("penznem") or "HUF")[:3].upper()
    bejovo.irany = _irany(bejovo)

    # A nettó/áfa/bruttó ELTÉRÉSÉT jelezzük, de nem írjuk felül a számla
    # eredeti összegeit újraszámolással (a felhasználó előírása).
    figyelmeztetesek: list[str] = []
    if bejovo.netto is not None and bejovo.brutto is not None and bejovo.afa_osszeg is not None:
        if abs(float(bejovo.netto) + float(bejovo.afa_osszeg) - float(bejovo.brutto)) > 1:
            figyelmeztetesek.append(
                "A nettó + áfa nem adja ki a bruttót a kiolvasott adatok szerint - ellenőrizd a dokumentumon."
            )
    bejovo.kinyert = {
        "mezok": kinyert,
        # Mezőnkénti FORRÁS: itt minden a dokumentumból jött; a felhasználói
        # javítást az ellenőrző (PATCH) írja át "felhasznalo"-ra.
        "mezo_forrasok": {k: "dokumentum" for k, v in kinyert.items() if v not in (None, [], {}, "")},
        "bizonytalan": list(kinyert.get("bizonytalan_mezok") or []),
        "osszeg_figyelmeztetesek": figyelmeztetesek,
    }


def _irany(bejovo: BejovoSzamla) -> str:
    """bejovo | kimeno | ismeretlen - a SZÁMLÁN szereplő felek alapján."""

    def sajat(nev: str | None) -> bool:
        n = _norm(nev)
        return bool(n) and any(minta in n for minta in SAJAT_CEG_MINTAK)

    if sajat(bejovo.kibocsato_nev):
        return "kimeno"
    if sajat(bejovo.vevo_nev):
        return "bejovo"
    return "ismeretlen"


def _xml_parositas(db: Session, bejovo: BejovoSzamla) -> None:
    """Ugyanazon számla XML-változata: az azonos levélből érkezett PDF-hez
    kapcsoljuk - a kettő EGY dokumentum, nem két számla."""
    tars = None
    if bejovo.email_uzenet_id:
        tars = db.scalar(
            select(BejovoSzamla)
            .where(
                BejovoSzamla.email_uzenet_id == bejovo.email_uzenet_id,
                BejovoSzamla.id != bejovo.id,
                BejovoSzamla.content_type == "application/pdf",
            )
            .order_by(BejovoSzamla.id)
        )
    if tars is not None:
        bejovo.valtozat_szamla_id = tars.id
        bejovo.allapot = ALLAPOT_JOVAHAGYVA  # a változat nem önálló teendő
        bejovo.javaslat = {
            "tipus": None,
            "indoklas": f"A #{tars.id} számla XML-változata - a feldolgozás a PDF-en történik.",
            "alternativak": [],
            "figyelmeztetesek": [],
        }
    else:
        bejovo.allapot = ALLAPOT_PONTOSITAS
        bejovo.javaslat = {
            "tipus": None,
            "indoklas": "Önállóan érkezett XML-számla - a rendszer a PDF/kép változatot tudja kiolvasni.",
            "alternativak": [],
            "figyelmeztetesek": ["XML-változat PDF-pár nélkül - kézi ellenőrzés kell."],
        }


# ── DUPLIKÁCIÓ ───────────────────────────────────────────────────────────────


def _duplikacio(db: Session, bejovo: BejovoSzamla) -> BejovoSzamla | None:
    """Ugyanaz a számla másodszor? Fájl-lenyomat, majd kibocsátó+számlaszám.

    Azonos számlaszám ELTÉRŐ összeggel nem csendes duplikátum, hanem ütközés:
    pontosításra küldjük, a figyelmeztetéssel (lásd javasol)."""
    if bejovo.fajl_hash:
        talalat = db.scalar(
            select(BejovoSzamla)
            .where(
                BejovoSzamla.fajl_hash == bejovo.fajl_hash,
                BejovoSzamla.id != bejovo.id,
                BejovoSzamla.allapot.notin_(["nem_szamla", "hiba"]),
            )
            .order_by(BejovoSzamla.id)
        )
        if talalat is not None:
            return talalat
    if bejovo.szamlaszam and (bejovo.kibocsato_adoszam or bejovo.kibocsato_nev):
        jeloltek = db.scalars(
            select(BejovoSzamla).where(
                func.lower(BejovoSzamla.szamlaszam) == bejovo.szamlaszam.lower(),
                BejovoSzamla.id != bejovo.id,
                BejovoSzamla.allapot.in_([ALLAPOT_ELLENORZENDO, ALLAPOT_PONTOSITAS, ALLAPOT_JOVAHAGYVA]),
            )
        ).all()
        sajat_ado = _adoszam_szamjegyei(bejovo.kibocsato_adoszam)
        for j in jeloltek:
            ado_egyezik = sajat_ado and _adoszam_szamjegyei(j.kibocsato_adoszam) == sajat_ado
            nev_egyezik = _norm(j.kibocsato_nev) == _norm(bejovo.kibocsato_nev) and bejovo.kibocsato_nev
            if not (ado_egyezik or nev_egyezik):
                continue
            # Azonos összeg + pénznem = duplikátum; eltérő = ütközés (a hívó
            # a javaslatban jelzi) - azt nem itt döntjük el.
            if (
                j.netto is not None
                and bejovo.netto is not None
                and abs(float(j.netto) - float(bejovo.netto)) < 0.01
                and j.penznem == bejovo.penznem
            ):
                return j
    return None


def _szamlaszam_utkozes(db: Session, bejovo: BejovoSzamla) -> str | None:
    if not bejovo.szamlaszam:
        return None
    masik = db.scalar(
        select(BejovoSzamla).where(
            func.lower(BejovoSzamla.szamlaszam) == bejovo.szamlaszam.lower(),
            BejovoSzamla.id != bejovo.id,
            BejovoSzamla.allapot.in_([ALLAPOT_ELLENORZENDO, ALLAPOT_PONTOSITAS, ALLAPOT_JOVAHAGYVA]),
        )
    )
    if masik is not None and (
        bejovo.netto is None
        or masik.netto is None
        or abs(float(masik.netto) - float(bejovo.netto)) >= 0.01
        or masik.penznem != bejovo.penznem
    ):
        return (
            f"Azonos számlaszám ({bejovo.szamlaszam}) már szerepel a #{masik.id} tételen ELTÉRŐ tartalommal - "
            "ütközés, nézd meg mindkettőt."
        )
    return None


# ── BESOROLÁSI JAVASLAT ──────────────────────────────────────────────────────


def javasol(db: Session, bejovo: BejovoSzamla) -> None:
    """Besorolási javaslat + alternatívák + állapot (ellenorzendo/pontositas).

    Újrafuttatható: a felhasználói utasítás módosítása után is ez fut le, a
    már kinyert adatokon (nem olvas ki újra)."""
    figyelmeztetesek: list[str] = list((bejovo.kinyert or {}).get("osszeg_figyelmeztetesek") or [])
    utkozes = _szamlaszam_utkozes(db, bejovo)
    if utkozes:
        figyelmeztetesek.append(utkozes)

    alternativak: list[dict] = []
    tipus: str | None = None
    indoklas = ""

    utasitas = _norm(bejovo.felhasznaloi_utasitas)
    mezok = (bejovo.kinyert or {}).get("mezok") or {}
    szovegek = " ".join(
        filter(
            None,
            [
                bejovo.felhasznaloi_utasitas or "",
                bejovo.email_targy or "",
                bejovo.email_szoveg or "",
                " ".join(mezok.get("projektkod_hivatkozasok") or []),
                mezok.get("megjegyzes") or "",
            ],
        )
    )

    # 1-2) Projektkód: a felhasználó utasításából vagy a dokumentum/levél
    # hivatkozásából - VALÓDI rekordra oldva.
    kodok = list(dict.fromkeys(PROJEKTKOD_MINTA.findall(szovegek.upper())))
    projekt_kodok: list[ProjectCode] = []
    for kod in kodok[:5]:
        pc = db.scalar(select(ProjectCode).where(func.upper(ProjectCode.projektkod) == kod))
        if pc is not None:
            projekt_kodok.append(pc)

    # 3-4) Számlázó fél: adószám a legerősebb, aztán cégnév/név.
    fel_employee = kiadas_kiolvasas.alvallalkozo_egyeztetes(
        db,
        {
            "adoszam": bejovo.kibocsato_adoszam,
            "megnevezes": bejovo.kibocsato_nev,
            "kepviselo": ((mezok.get("kibocsato") or {}).get("nev")),
        },
    )
    fel_vallalkozas = None
    sajat_ado = _adoszam_szamjegyei(bejovo.kibocsato_adoszam)
    if sajat_ado:
        for v in db.scalars(select(Vallalkozas)).all():
            if _adoszam_szamjegyei(v.adoszam) == sajat_ado:
                fel_vallalkozas = v
                break
    if fel_vallalkozas is None and bejovo.kibocsato_nev:
        fel_vallalkozas = db.scalar(
            select(Vallalkozas).where(func.lower(Vallalkozas.nev) == _norm(bejovo.kibocsato_nev))
        )

    # 5) Meglévő, számlára váró tételek a félhez.
    tig_jeloltek = _kulsos_tig_jeloltek(db, bejovo, fel_employee, fel_vallalkozas)
    belsos_jelolt = _belsos_tig_jelolt(db, bejovo, fel_employee)
    kiadas_jeloltek = _kiadas_jeloltek(db, bejovo, fel_employee)
    erezsi_jelolt = _erezsi_jelolt(db, bejovo)
    auto_jelolt = _auto_jelolt(db, szovegek)

    for cert, ok in tig_jeloltek:
        alternativak.append(
            {
                "tipus": "kulsos_tig",
                "cel_id": cert.id,
                "cimke": _tig_cimke(cert),
                "indoklas": ok,
            }
        )
    if belsos_jelolt is not None:
        cert, ok = belsos_jelolt
        alternativak.append(
            {"tipus": "belsos_tig", "cel_id": cert.id, "cimke": f"Belsős TIG {cert.ev}. {cert.honap}. hó", "indoklas": ok}
        )
    for exp, ok in kiadas_jeloltek:
        alternativak.append(
            {
                "tipus": "kiadas_csatolas",
                "cel_id": exp.id,
                "cimke": f"Kiadás #{exp.id}: {exp.megnevezes} ({exp.kiadas_leiras or '-'})",
                "indoklas": ok,
            }
        )
    if erezsi_jelolt is not None:
        idoszak, ok = erezsi_jelolt
        alternativak.append(
            {
                "tipus": "erezsi",
                "cel_id": idoszak.id,
                "cimke": f"E-Rezsi: {idoszak.kotelezettseg.nev} - {idoszak.esedekesseg}",
                "indoklas": ok,
            }
        )
    if auto_jelolt is not None:
        auto, ok = auto_jelolt
        alternativak.append({"tipus": "auto", "cel_id": auto.id, "cimke": f"Autó: {auto.rendszam}", "indoklas": ok})
    for pc in projekt_kodok:
        alternativak.append(
            {
                "tipus": "kiadas_uj",
                "cel_id": pc.id,
                "cimke": f"Új kiadás a(z) {pc.projektkod} projektkódhoz",
                "indoklas": "A projektkód szerepel a dokumentumban/levélben/utasításban.",
            }
        )

    # A JAVASLAT kiválasztása - a felhasználó szava az első.
    if bejovo.dokumentum_tipus == "dijbekero":
        tipus = "egyeb"
        indoklas = "Díjbekérő (proforma) - nem rögzíthető végleges számlaként. Várd meg a számlát, vagy kezeld kézzel."
        figyelmeztetesek.append("Díjbekérő: végleges számlaként nem rögzíthető.")
    elif bejovo.irany == "kimeno":
        tipus = "kimeno"
        indoklas = (
            "A számlát a saját cégünk állította ki (kimenő/megrendelői számla) - a megrendelői folyamatban a helye, "
            "kiadásként nem rögzíthető."
        )
    elif utasitas and ("általános" in utasitas or "altalanos" in utasitas or "működési" in utasitas or "mukodesi" in utasitas):
        tipus = "mukodesi"
        indoklas = "A felhasználó utasítása szerint általános működési költség (tudatosan projekt nélkül)."
    elif utasitas and "tig" in utasitas and tig_jeloltek:
        tipus = "kulsos_tig"
        bejovo.cel_certificate_id = tig_jeloltek[0][0].id
        indoklas = f"A felhasználó TIG-hez kérte; a legjobb egyezés: {_tig_cimke(tig_jeloltek[0][0])}."
    elif utasitas and ("belsős" in utasitas or "belsos" in utasitas) and belsos_jelolt is not None:
        tipus = "belsos_tig"
        bejovo.cel_internal_certificate_id = belsos_jelolt[0].id
        indoklas = f"A felhasználó belsős TIG-hez kérte ({belsos_jelolt[0].ev}. {belsos_jelolt[0].honap}. hó)."
    elif auto_jelolt is not None and utasitas and ("autó" in utasitas or "auto" in utasitas or "szerviz" in utasitas):
        tipus = "auto"
        bejovo.cel_auto_id = auto_jelolt[0].id
        indoklas = f"A felhasználó autóhoz kérte; az azonosított jármű: {auto_jelolt[0].rendszam}."
    elif tig_jeloltek and tig_jeloltek[0][1].startswith("Összeg"):
        # Erős TIG-egyezés (fél + összeg): a TIG-ben már elszámolt költség nem
        # lehet még egyszer kiadás.
        tipus = "kulsos_tig"
        bejovo.cel_certificate_id = tig_jeloltek[0][0].id
        indoklas = f"Számlára váró külsős TIG a félnél, egyező összeggel: {_tig_cimke(tig_jeloltek[0][0])}."
    elif erezsi_jelolt is not None:
        tipus = "erezsi"
        bejovo.cel_kotelezettseg_idoszak_id = erezsi_jelolt[0].id
        indoklas = erezsi_jelolt[1]
    elif len(projekt_kodok) == 1:
        tipus = "kiadas_uj"
        bejovo.cel_project_code_id = projekt_kodok[0].id
        indoklas = f"A(z) {projekt_kodok[0].projektkod} projektkód egyértelműen szerepel - új kiadás készül hozzá (nem kifizetettként)."
        if fel_employee is not None:
            bejovo.cel_employee_id = fel_employee.id
    elif len(projekt_kodok) > 1:
        tipus = None
        indoklas = "Több projektkód is szerepel - válaszd ki, melyikhez tartozik (vagy oszd fel az ellenőrzőben)."
    elif kiadas_jeloltek:
        tipus = "kiadas_csatolas"
        bejovo.cel_expense_id = kiadas_jeloltek[0][0].id
        indoklas = f"Meglévő, számlára váró kiadás a félnél: {kiadas_jeloltek[0][1]}"
    else:
        tipus = None
        indoklas = (
            "Nem dönthető el egyértelműen, hová tartozik - a feladó neve vagy hasonló összeg önmagában nem elég. "
            "Válassz célt az ellenőrzőben."
        )

    bejovo.cel_tipus = tipus
    bejovo.javaslat = {
        "tipus": tipus,
        "indoklas": indoklas,
        "alternativak": alternativak[:8],
        "figyelmeztetesek": figyelmeztetesek,
    }
    bejovo.allapot = ALLAPOT_ELLENORZENDO if tipus else ALLAPOT_PONTOSITAS
    if bejovo.dokumentum_tipus in ("modosito", "storno") and not (bejovo.kinyert or {}).get("mezok", {}).get(
        "elozmeny_szamlaszam"
    ):
        bejovo.allapot = ALLAPOT_PONTOSITAS
        bejovo.javaslat["figyelmeztetesek"].append(
            "Módosító/sztornó számla előzmény-hivatkozás nélkül - keresd meg az eredetit."
        )


def _tig_cimke(cert: PerformanceCertificate) -> str:
    fel = cert.employee.full_name if cert.employee else (cert.vallalkozas.nev if cert.vallalkozas else "?")
    hova = ""
    if cert.project is not None:
        hova = cert.project.nev or ""
    return f"Külsős TIG #{cert.id} - {fel}{f' ({hova})' if hova else ''} - {cert.netto_osszeg or '?'} Ft"


def _kulsos_tig_jeloltek(
    db: Session, bejovo: BejovoSzamla, emp: Employee | None, vall: Vallalkozas | None
) -> list[tuple[PerformanceCertificate, str]]:
    """Számlára váró külsős TIG-ek a felismerspecifikus félhez - az összeg-egyezés
    a legerősebb jel (elöl áll)."""
    if emp is None and vall is None:
        return []
    felt = []
    if emp is not None:
        felt.append(PerformanceCertificate.employee_id == emp.id)
    if vall is not None:
        felt.append(PerformanceCertificate.vallalkozas_id == vall.id)
    from sqlalchemy import or_

    certek = db.scalars(
        select(PerformanceCertificate)
        .where(or_(*felt), PerformanceCertificate.szamla_kifizetve.is_(False))
        .order_by(PerformanceCertificate.id.desc())
        .limit(10)
    ).all()
    eredmeny: list[tuple[PerformanceCertificate, str]] = []
    for cert in certek:
        if cert.netto_osszeg is not None and bejovo.netto is not None and abs(
            float(cert.netto_osszeg) - float(bejovo.netto)
        ) < 1:
            eredmeny.insert(0, (cert, f"Összeg-egyezés ({cert.netto_osszeg} Ft) + a számlázó fél egyezik."))
        elif not cert.invoices:
            eredmeny.append((cert, "A számlázó fél egyezik, a TIG-hez még nincs számla feltöltve."))
    return eredmeny[:5]


def _belsos_tig_jelolt(
    db: Session, bejovo: BejovoSzamla, emp: Employee | None
) -> tuple[InternalPerformanceCertificate, str] | None:
    if emp is None or emp.tipus != EmployeeType.BELSOS:
        return None
    alap = bejovo.teljesites_datuma or bejovo.kiallitas_datuma
    if alap is None:
        return None
    cert = db.scalar(
        select(InternalPerformanceCertificate).where(
            InternalPerformanceCertificate.employee_id == emp.id,
            InternalPerformanceCertificate.ev == alap.year,
            InternalPerformanceCertificate.honap == alap.month,
        )
    )
    if cert is None:
        return None
    return cert, f"{emp.full_name} belsős TIG-je a számla időszakának hónapjára ({alap.year}.{alap.month:02d})."


def _kiadas_jeloltek(db: Session, bejovo: BejovoSzamla, emp: Employee | None) -> list[tuple[Expense, str]]:
    """Meglévő, számlára váró kiadások: a félhez kötött vagy név-egyező sorok,
    amelyeknek még nincs számla-csatolmánya."""
    from sqlalchemy import or_

    felt = []
    if emp is not None:
        felt.append(Expense.employee_id == emp.id)
    if bejovo.kibocsato_nev:
        felt.append(func.lower(Expense.megnevezes) == _norm(bejovo.kibocsato_nev))
    if not felt:
        return []
    hatar = date.today() - timedelta(days=180)
    sorok = db.scalars(
        select(Expense)
        .where(
            or_(*felt),
            Expense.nincs_szamla.is_(False),
            (Expense.kiadas_datuma.is_(None)) | (Expense.kiadas_datuma >= hatar),
        )
        .order_by(Expense.id.desc())
        .limit(20)
    ).all()
    if not sorok:
        return []
    csatolt = {
        a.entity_id
        for a in db.scalars(
            select(DocumentAttachment).where(
                DocumentAttachment.entity_type == "expense",
                DocumentAttachment.kategoria == "szamla",
                DocumentAttachment.entity_id.in_([s.id for s in sorok]),
            )
        )
    }
    eredmeny: list[tuple[Expense, str]] = []
    for s in sorok:
        if s.id in csatolt:
            continue
        if s.netto is not None and bejovo.netto is not None and abs(float(s.netto) - float(bejovo.netto)) < 1:
            eredmeny.insert(0, (s, f"#{s.id} - összeg-egyezés ({s.netto} Ft), számla még nincs hozzá."))
        else:
            eredmeny.append((s, f"#{s.id} - a partner egyezik, számla még nincs hozzá."))
    return eredmeny[:5]


def _erezsi_jelolt(db: Session, bejovo: BejovoSzamla) -> tuple[KotelezettsegIdoszak, str] | None:
    """E-Rezsi: a kibocsátó nevéhez illő AKTÍV előfizetés adott hónapja."""
    nev = _norm(bejovo.kibocsato_nev)
    if not nev:
        return None
    elofizetesek = db.scalars(
        select(Kotelezettseg).where(
            Kotelezettseg.aktiv.is_(True), Kotelezettseg.tipus == KotelezettsegTipus.ELOFIZETES
        )
    ).all()
    talalat = None
    for k in elofizetesek:
        kn = _norm(k.nev)
        if kn and (kn in nev or nev in kn):
            talalat = k
            break
    if talalat is None:
        return None
    alap = bejovo.teljesites_datuma or bejovo.kiallitas_datuma or date.today()
    idoszak = db.scalar(
        select(KotelezettsegIdoszak)
        .where(
            KotelezettsegIdoszak.kotelezettseg_id == talalat.id,
            func.extract("year", KotelezettsegIdoszak.esedekesseg) == alap.year,
            func.extract("month", KotelezettsegIdoszak.esedekesseg) == alap.month,
        )
        .order_by(KotelezettsegIdoszak.esedekesseg)
    )
    if idoszak is None:
        return None
    return idoszak, (
        f"A(z) „{talalat.nev}” előfizetés {alap.year}.{alap.month:02d}. havi időszaka - a számla tényleges "
        "összege az időszakra kerül, a tervezett költséget nem számoljuk kétszer."
    )


def _auto_jelolt(db: Session, szoveg: str) -> tuple[Auto, str] | None:
    for betuk, szamok in RENDSZAM_MINTA.findall(szoveg.upper()):
        for valtozat in (f"{betuk}-{szamok}", f"{betuk}{szamok}", f"{betuk} {szamok}"):
            auto = db.scalar(select(Auto).where(func.upper(Auto.rendszam) == valtozat))
            if auto is not None:
                return auto, f"A(z) {auto.rendszam} rendszám szerepel a dokumentumban/utasításban."
    return None


# ── JÓVÁHAGYÁS (végleges rögzítés) ──────────────────────────────────────────


def jovahagy(db: Session, bejovo: BejovoSzamla, user: Employee, dontes: dict) -> dict:
    """A piszkozat VÉGLEGES rögzítése - egyetlen tranzakcióban, ismételt
    végrehajtás elleni védelemmel (a hívó sorzárral olvasta a piszkozatot).

    A `dontes` a felülvizsgált cél: {"cel_tipus": ..., "cel_..._id": ...,
    "netto"/"brutto"/"arfolyam"/"tipus"/"kifizetes_modja"/"kiadas_leiras",
    "felosztas": [{"project_code_id", "netto"}...]}. Vissza: rögzítési napló."""
    if bejovo.allapot == ALLAPOT_JOVAHAGYVA:
        # Dupla kattintás / párhuzamos jóváhagyás: a második hívás NEM rögzít
        # újra - a már megtörtént eredményt kapja vissza.
        return {**(bejovo.rogzites_naplo or {}), "mar_jovahagyva": True}
    if bejovo.allapot not in (ALLAPOT_ELLENORZENDO, ALLAPOT_PONTOSITAS, ALLAPOT_DUPLIKATUM):
        raise ErkeztetesHiba(f"Ebből az állapotból nem hagyható jóvá: {bejovo.allapot}.")

    cel_tipus = dontes.get("cel_tipus") or bejovo.cel_tipus
    if cel_tipus not in CEL_TIPUSOK:
        raise ErkeztetesHiba("Válaszd ki, hová kerüljön a számla (cél típus).")
    if cel_tipus == "kimeno":
        raise ErkeztetesHiba(
            "Kimenő (általunk kiállított) számla nem rögzíthető kiadásként - a megrendelői folyamatban a helye."
        )
    if bejovo.dokumentum_tipus == "dijbekero" and cel_tipus in ("kiadas_uj", "mukodesi", "auto"):
        raise ErkeztetesHiba("Díjbekérő nem rögzíthető végleges kiadásként - várd meg a számlát.")

    fajl = None
    if bejovo.storage_key:
        fajl = document_storage.download_bytes(bejovo.storage_key)

    naplo: dict = {"cel_tipus": cel_tipus, "letrejott": [], "csatolt": []}

    if cel_tipus in ("kiadas_uj", "mukodesi", "auto"):
        naplo = _rogzit_kiadaskent(db, bejovo, dontes, fajl, naplo, cel_tipus)
    elif cel_tipus == "kiadas_csatolas":
        exp = db.get(Expense, dontes.get("cel_expense_id") or bejovo.cel_expense_id or 0)
        if exp is None:
            raise ErkeztetesHiba("A kiválasztott kiadás nem található.")
        _csatol_fajl(db, "expense", exp.id, bejovo, fajl, naplo)
        bejovo.rogzitett_expense_id = exp.id
        naplo["csatolt"].append({"tipus": "expense", "id": exp.id})
    elif cel_tipus == "kulsos_tig":
        cert = db.get(PerformanceCertificate, dontes.get("cel_certificate_id") or bejovo.cel_certificate_id or 0)
        if cert is None:
            raise ErkeztetesHiba("A kiválasztott külsős TIG nem található.")
        if fajl is None:
            raise ErkeztetesHiba("Ehhez a művelethez kell a számla fájlja.")
        sor = PerformanceCertificateInvoice(
            certificate_id=cert.id,
            filename=bejovo.fajl_nev or "szamla.pdf",
            storage_key="",
            url="",
            content_type=bejovo.content_type,
        )
        db.add(sor)
        db.flush()
        kulcs = f"tig-szamla/{cert.id}/{sor.id}-{re.sub(r'[^A-Za-z0-9._-]+', '_', sor.filename)[:80]}"
        sor.url = document_storage.upload_bytes(fajl, kulcs, bejovo.content_type or "application/pdf")
        sor.storage_key = kulcs
        # A TIG kifizetési állapotához NEM nyúlunk: a számla feltöltése nem
        # kifizetés, és nem is aláírt TIG (a felhasználó előírása).
        naplo["csatolt"].append({"tipus": "performanceCertificate", "id": cert.id, "szamla_sor": sor.id})
    elif cel_tipus == "belsos_tig":
        cert = db.get(
            InternalPerformanceCertificate,
            dontes.get("cel_internal_certificate_id") or bejovo.cel_internal_certificate_id or 0,
        )
        if cert is None:
            raise ErkeztetesHiba("A kiválasztott belsős TIG nem található.")
        if fajl is None:
            raise ErkeztetesHiba("Ehhez a művelethez kell a számla fájlja.")
        sor = InternalPerformanceCertificateInvoice(
            certificate_id=cert.id,
            filename=bejovo.fajl_nev or "szamla.pdf",
            storage_key="",
            url="",
            content_type=bejovo.content_type,
        )
        db.add(sor)
        db.flush()
        kulcs = f"belsos-tig-szamla/{cert.employee_id}/{cert.ev}-{cert.honap:02d}-{sor.id}"
        sor.url = document_storage.upload_bytes(fajl, kulcs, bejovo.content_type or "application/pdf")
        sor.storage_key = kulcs
        naplo["csatolt"].append({"tipus": "internalPerformanceCertificate", "id": cert.id, "szamla_sor": sor.id})
    elif cel_tipus == "erezsi":
        idoszak = db.get(
            KotelezettsegIdoszak,
            dontes.get("cel_kotelezettseg_idoszak_id") or bejovo.cel_kotelezettseg_idoszak_id or 0,
        )
        if idoszak is None:
            raise ErkeztetesHiba("A kiválasztott E-Rezsi időszak nem található.")
        # A TÉNYLEGES terhelés az időszakra kerül - a `fizetve` jelzőhöz nem
        # nyúlunk (a számla megérkezése nem kifizetés).
        if idoszak.osszeg is None and bejovo.netto is not None:
            idoszak.osszeg = bejovo.netto
            idoszak.plusz_afa = bool(bejovo.afa_osszeg)
            idoszak.penznem = bejovo.penznem
        _csatol_fajl(db, "kotelezettseg", idoszak.kotelezettseg_id, bejovo, fajl, naplo)
        naplo["csatolt"].append({"tipus": "kotelezettsegIdoszak", "id": idoszak.id})
    elif cel_tipus == "kp":
        kp = db.get(KpForgalom, dontes.get("cel_kp_forgalom_id") or bejovo.cel_kp_forgalom_id or 0)
        if kp is None:
            raise ErkeztetesHiba("A kiválasztott KP-tétel nem található.")
        # Bizonylat-pótlás: NEM új pénzmozgás - csak a papír kerül a tételhez.
        _csatol_fajl(db, "kpForgalom", kp.id, bejovo, fajl, naplo)
        naplo["csatolt"].append({"tipus": "kpForgalom", "id": kp.id})
    else:  # "egyeb"
        raise ErkeztetesHiba("Tisztázandó tétel - válassz konkrét célt, vagy jelöld Nem számla-ként.")

    bejovo.cel_tipus = cel_tipus
    bejovo.allapot = ALLAPOT_JOVAHAGYVA
    bejovo.jovahagyo_employee_id = user.id
    bejovo.jovahagyva_at = datetime.now(timezone.utc)
    bejovo.rogzites_naplo = naplo
    return naplo


def _rogzit_kiadaskent(
    db: Session, bejovo: BejovoSzamla, dontes: dict, fajl: bytes | None, naplo: dict, cel_tipus: str
) -> dict:
    """Új kiadás(ok) létrehozása - kesz=False (NEM kifizetett!), a meglévő
    deviza-szabállyal (lásd services/penznem.py). Felosztásnál a rész-összegeknek
    pontosan ki kell adniuk a számla összegét."""
    netto = _szam(dontes.get("netto")) if dontes.get("netto") is not None else (
        float(bejovo.netto) if bejovo.netto is not None else None
    )
    if netto is None:
        raise ErkeztetesHiba("Hiányzik a nettó összeg - add meg az ellenőrzőben (nem találunk ki értéket).")
    plusz_afa = bool(bejovo.afa_osszeg) or bool((bejovo.kinyert or {}).get("mezok", {}).get("afa_kulcsok"))
    afa_szazalek = None
    kulcsok = (bejovo.kinyert or {}).get("mezok", {}).get("afa_kulcsok") or []
    if len(kulcsok) == 1 and _szam(kulcsok[0]):
        afa_szazalek = _szam(kulcsok[0])
    elif len(kulcsok) > 1:
        naplo.setdefault("megjegyzesek", []).append(
            "Több áfakulcs szerepel a számlán - a bruttó a számláról jön, nem kulcsból számolt."
        )

    arfolyam = _szam(dontes.get("arfolyam"))
    if penznem.devizas(bejovo.penznem) and arfolyam is None:
        raise ErkeztetesHiba(
            f"A számla {bejovo.penznem}-ben szól - add meg az árfolyamot (forrással/dátummal), "
            "önkényes árfolyamot nem használunk."
        )

    felosztas = dontes.get("felosztas") or []
    if felosztas:
        osszesen = sum(_szam(f.get("netto")) or 0 for f in felosztas)
        if abs(osszesen - netto) > 0.01:
            raise ErkeztetesHiba(
                f"A felosztott összegek ({osszesen}) nem adják ki a számla nettóját ({netto}) - javítsd az arányokat."
            )
        reszek = felosztas
    else:
        reszek = [
            {
                "project_code_id": dontes.get("cel_project_code_id") or bejovo.cel_project_code_id,
                "netto": netto,
            }
        ]

    elso_expense: Expense | None = None
    for i, resz in enumerate(reszek):
        resz_netto = float(_szam(resz.get("netto")) or 0)
        huf_netto = resz_netto
        eredeti_penznem = None
        if penznem.devizas(bejovo.penznem):
            eredeti_penznem = bejovo.penznem
            huf_netto = penznem.forintra(resz_netto, arfolyam) or 0
        brutto = round(huf_netto * (1 + (afa_szazalek or 27) / 100), 2) if plusz_afa else huf_netto
        pc_id = resz.get("project_code_id")
        if pc_id is not None and db.get(ProjectCode, pc_id) is None:
            raise ErkeztetesHiba(f"A megadott projektkód (#{pc_id}) nem található.")
        exp = Expense(
            megnevezes=(dontes.get("megnevezes") or bejovo.kibocsato_nev or "Ismeretlen partner")[:255],
            kiadas_leiras=(
                (dontes.get("kiadas_leiras") or _alap_leiras(bejovo))
                + (f" – felosztott számla {i + 1}/{len(reszek)}" if len(reszek) > 1 else "")
            ),
            netto=huf_netto,
            brutto=brutto,
            plusz_afa="igen" if plusz_afa else None,
            afa_szazalek=afa_szazalek,
            penznem="HUF",
            eredeti_penznem=eredeti_penznem,
            eredeti_netto=resz_netto if eredeti_penznem else None,
            eredeti_brutto=(
                round(resz_netto * (1 + (afa_szazalek or 27) / 100), 2) if eredeti_penznem and plusz_afa else (resz_netto if eredeti_penznem else None)
            ),
            arfolyam=arfolyam,
            kiadas_datuma=bejovo.teljesites_datuma or bejovo.kiallitas_datuma,
            fizetes_hatarideje=bejovo.fizetesi_hatarido,
            project_code_id=None if cel_tipus == "mukodesi" else pc_id,
            employee_id=dontes.get("cel_employee_id") or bejovo.cel_employee_id,
            auto_id=(dontes.get("cel_auto_id") or bejovo.cel_auto_id) if cel_tipus == "auto" else None,
            tipus=dontes.get("tipus") or ("kulsos" if (dontes.get("cel_employee_id") or bejovo.cel_employee_id) else "egyeb"),
            kifizetes_modja=dontes.get("kifizetes_modja")
            or ((bejovo.kinyert or {}).get("mezok", {}).get("fizetesi_mod") or None),
            # A SZÁMLA MEGÉRKEZÉSE NEM KIFIZETÉS: a tétel nyitottként születik.
            kesz=False,
        )
        db.add(exp)
        db.flush()
        naplo["letrejott"].append({"tipus": "expense", "id": exp.id, "netto": huf_netto})
        if elso_expense is None:
            elso_expense = exp

    # A dokumentum EGY példányban, az első kiadáshoz kerül - felosztásnál a
    # többi sor naplója hivatkozik rá (a számla egyetlen dokumentum marad).
    if elso_expense is not None:
        _csatol_fajl(db, "expense", elso_expense.id, bejovo, fajl, naplo)
        bejovo.rogzitett_expense_id = elso_expense.id
        if len(reszek) > 1:
            naplo.setdefault("megjegyzesek", []).append(
                f"A számla fájlja a(z) #{elso_expense.id} kiadásnál van - a többi felosztott sor erre hivatkozik."
            )
    return naplo


def _alap_leiras(bejovo: BejovoSzamla) -> str:
    mezok = (bejovo.kinyert or {}).get("mezok") or {}
    tetelek = mezok.get("tetelek") or []
    if tetelek and tetelek[0].get("megnevezes"):
        return str(tetelek[0]["megnevezes"])[:250]
    return (bejovo.email_targy or f"Számla {bejovo.szamlaszam or ''}").strip()[:250]


def _csatol_fajl(
    db: Session, entity_type: str, entity_id: int, bejovo: BejovoSzamla, fajl: bytes | None, naplo: dict
) -> None:
    if fajl is None:
        naplo.setdefault("megjegyzesek", []).append("A piszkozathoz nem tartozik fájl - csatolmány nem készült.")
        return
    rekord = attachments.save(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        kategoria="szamla",
        filename=bejovo.fajl_nev or "szamla.pdf",
        data=fajl,
        content_type=bejovo.content_type,
    )
    if bejovo.fizetesi_hatarido and rekord.fizetesi_hatarido is None:
        rekord.fizetesi_hatarido = bejovo.fizetesi_hatarido
    naplo["csatolt"].append({"tipus": f"attachment:{entity_type}", "id": rekord.id})
