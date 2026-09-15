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
    ALLAPOT_EGYEB_DOKUMENTUM,
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
from app.services import attachments, document_storage, excel_szoveg, kiadas_kiolvasas, penznem

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
        if mime not in ENGEDETT_MIME | XML_MIME and not excel_szoveg.excelnek_tunik(mime, fajl_nev):
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
        if excel_szoveg.excelnek_tunik(bejovo.content_type, bejovo.fajl_nev):
            # Excel/CSV melléklet: költség-részletező (projektbontás), nem
            # önálló számla - a társ-számlájához bontás-javaslatot készít.
            _reszletezo_feldolgozas(db, bejovo, adat)
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

        # A kiolvasás (AI-hívás) másodpercekig-percekig tarthat - előtte
        # lezárjuk a nyitott tranzakciót, hogy a piszkozat friss INSERT-je ne
        # tartson zárat a hívás teljes ideje alatt: egy deploy közbeni
        # ALTER TABLE (és az összes mögé beálló lekérdezés) pontosan ezen
        # várt, és a migráció lock_timeout-tal elhasalva a deployt is
        # elbuktatta.
        db.commit()
        kinyert = kiadas_kiolvasas.szamla_olvasd_ki(adat, bejovo.content_type or "application/pdf")
        _kinyert_mentese(bejovo, kinyert)

        if bejovo.dokumentum_tipus == "ertesito":
            # Számlaértesítő/fizetési emlékeztető: nem maga a számla. Ha a
            # hivatkozott számla már beérkezett, ahhoz kapcsoljuk; különben
            # a számlafájlra vár.
            _ertesito_kezeles(db, bejovo)
            return
        if (
            (bejovo.dokumentum_tipus or "egyeb") == "egyeb"
            and not bejovo.szamlaszam
            and bejovo.netto is None
            and bejovo.brutto is None
        ):
            # Nem számla jellegű melléklet (aláíráskép, képernyőkép, egyéb
            # dokumentum): külön listába kerül, nem az elbírálandók közé -
            # de nem is vész el, kézzel visszaminősíthető (reset).
            bejovo.allapot = ALLAPOT_EGYEB_DOKUMENTUM
            bejovo.javaslat = {
                "tipus": None,
                "indoklas": (
                    "Nem számla jellegű melléklet: nincs rajta számlaszám és összeg sem. "
                    "Külön listába került - ha mégis számla, az újraindítással visszaminősítheted."
                ),
                "alternativak": [],
                "figyelmeztetesek": [],
            }
            return

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
        # Ha ugyanabban a levélben MÁR feldolgozott költség-részletező van
        # (az Excel a számla előtt került sorra), a bontás-javaslata most
        # kerül erre a számlára.
        _tars_reszletezo_alkalmazasa(db, bejovo)
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


def _reszletezo_feldolgozas(db: Session, bejovo: BejovoSzamla, adat: bytes | None) -> None:
    """Excel/CSV KÖLTSÉG-RÉSZLETEZŐ feldolgozása: a cellák szöveggé, a sorok
    kiolvasva, majd a bontás-javaslat az azonos levélben érkezett EGYETLEN
    társ-számlára kerül. Több társ-számlánál (vagy ha a táblázat láthatóan
    több számlát bont) NEM alkalmazzuk automatikusan - pontosításra vár."""
    bejovo.dokumentum_tipus = "reszletezo"
    if adat is None and bejovo.storage_key:
        adat = document_storage.download_bytes(bejovo.storage_key)
    if adat is None:
        bejovo.allapot = ALLAPOT_PONTOSITAS
        bejovo.javaslat = {
            "tipus": None,
            "indoklas": "A részletezőhöz nem tartozik fájl - kézi ellenőrzés kell.",
            "alternativak": [],
            "figyelmeztetesek": [],
        }
        return

    szoveg = excel_szoveg.szovegge(adat, bejovo.fajl_nev)
    # Lásd feldolgoz(): az AI-hívás előtt tranzakció-zárás, hogy a hívás
    # alatt ne maradjon zár a bejovo_szamlak tábla sorain.
    db.commit()
    kinyert = kiadas_kiolvasas.reszletezo_olvasd_ki(szoveg)
    sorok = [s for s in (kinyert.get("sorok") or []) if isinstance(s, dict)]
    bejovo.kinyert = {"reszletezo": kinyert}

    tarsak: list[BejovoSzamla] = []
    if bejovo.email_uzenet_id:
        tarsak = list(
            db.scalars(
                select(BejovoSzamla)
                .where(
                    BejovoSzamla.email_uzenet_id == bejovo.email_uzenet_id,
                    BejovoSzamla.id != bejovo.id,
                    BejovoSzamla.content_type.in_(sorted(ENGEDETT_MIME)),
                )
                .order_by(BejovoSzamla.id)
            ).all()
        )

    if not sorok:
        bejovo.allapot = ALLAPOT_PONTOSITAS
        bejovo.javaslat = {
            "tipus": None,
            "indoklas": "A táblázatból nem sikerült bontás-sorokat kiolvasni - nézd meg kézzel.",
            "alternativak": [],
            "figyelmeztetesek": [],
        }
        return
    if kinyert.get("tobb_szamlat_reszletez") or len(tarsak) > 1:
        bejovo.allapot = ALLAPOT_PONTOSITAS
        bejovo.javaslat = {
            "tipus": None,
            "indoklas": (
                "A részletező több számlához tartozhat "
                f"({len(tarsak)} számla érkezett a levélben) - a bontást nem alkalmazzuk automatikusan, "
                "nyisd meg az érintett számlát és ott vedd át a sorokat."
            ),
            "alternativak": [],
            "figyelmeztetesek": ["Több számlás részletező - automatikus hozzárendelés nincs."],
        }
        return
    if len(tarsak) == 1:
        tars = tarsak[0]
        bejovo.valtozat_szamla_id = tars.id
        bejovo.allapot = ALLAPOT_JOVAHAGYVA  # a részletező nem önálló teendő
        bejovo.javaslat = {
            "tipus": None,
            "indoklas": f"A #{tars.id} számla költség-részletezője - a bontás javaslata a számlán jelenik meg.",
            "alternativak": [],
            "figyelmeztetesek": [],
        }
        _bontas_javaslat_keszites(db, tars, bejovo, kinyert)
        return
    bejovo.allapot = ALLAPOT_PONTOSITAS
    bejovo.javaslat = {
        "tipus": None,
        "indoklas": "Önállóan érkezett költség-részletező - a hozzá tartozó számla még nincs meg.",
        "alternativak": [],
        "figyelmeztetesek": [],
    }


def _bontas_javaslat_keszites(db: Session, szamla: BejovoSzamla, reszletezo: BejovoSzamla, kinyert: dict) -> None:
    """A részletezőből BONTÁS-JAVASLAT a számlára: soronként projektkód-
    feloldással és visszakereshető forrással (fájlnév + sorszám). Csak
    javaslat - a bontást a felhasználó hagyja jóvá az ellenőrzőben."""
    sorok_ki: list[dict] = []
    figyelmeztetesek: list[str] = []
    bizonytalan_brutto = False
    for i, sor in enumerate([s for s in (kinyert.get("sorok") or []) if isinstance(s, dict)], start=1):
        osszeg = _szam(sor.get("osszeg"))
        if osszeg is None:
            continue
        kod = (sor.get("projektkod") or "").strip().upper()
        pc = db.scalar(select(ProjectCode).where(func.upper(ProjectCode.projektkod) == kod)) if kod else None
        if sor.get("brutto_e") is None:
            bizonytalan_brutto = True
        sorok_ki.append(
            {
                "cel_tipus": "kiadas_uj" if pc is not None else None,
                "project_code_id": pc.id if pc is not None else None,
                "projektkod": kod or None,
                "projekt_nev": sor.get("projekt_nev"),
                "netto": osszeg,
                "brutto_e": sor.get("brutto_e"),
                "megjegyzes": sor.get("megnevezes"),
                "forras": f"{reszletezo.fajl_nev or 'részletező'} - {i}. sor",
            }
        )
    if not sorok_ki:
        return
    if bizonytalan_brutto:
        figyelmeztetesek.append(
            "A részletezőből nem derül ki egyértelműen, hogy a sorösszegek nettók vagy bruttók - "
            "ellenőrizd a rögzítés előtt."
        )
    osszesen = round(sum(float(s["netto"]) for s in sorok_ki), 2)
    if szamla.netto is not None and abs(osszesen - float(szamla.netto)) > 1:
        if szamla.brutto is not None and abs(osszesen - float(szamla.brutto)) <= 1:
            figyelmeztetesek.append(
                "A részletező sorai a számla BRUTTÓ összegét adják ki - a bontás rögzítése előtt nettósítsd a sorokat."
            )
        else:
            figyelmeztetesek.append(
                f"A részletező sorainak összege ({osszesen:,.0f}) nem egyezik a számla nettójával "
                f"({float(szamla.netto):,.0f}) - ellenőrizd, mi hiányzik.".replace(",", " ")
            )
    szamla.javaslat = {
        **(szamla.javaslat or {}),
        "bontas_javaslat": {
            "forras_bejovo_id": reszletezo.id,
            "forras_fajl": reszletezo.fajl_nev,
            "sorok": sorok_ki,
            "osszesen": osszesen,
            "penznem": kinyert.get("penznem"),
            "figyelmeztetesek": figyelmeztetesek,
        },
    }


def _tars_reszletezo_alkalmazasa(db: Session, bejovo: BejovoSzamla) -> None:
    """Fordított sorrend: ha a részletező HAMARABB került feldolgozásra, mint
    a számla (az Excel volt a levél első csatolmánya), a bontás-javaslatot a
    most feldolgozott számla kapja meg - de csak ha ez az EGYETLEN számla a
    levélben (több számlánál nincs automatikus hozzárendelés)."""
    if not bejovo.email_uzenet_id or (bejovo.javaslat or {}).get("bontas_javaslat"):
        return
    reszletezok = list(
        db.scalars(
            select(BejovoSzamla)
            .where(
                BejovoSzamla.email_uzenet_id == bejovo.email_uzenet_id,
                BejovoSzamla.id != bejovo.id,
                BejovoSzamla.dokumentum_tipus == "reszletezo",
            )
            .order_by(BejovoSzamla.id)
        ).all()
    )
    if len(reszletezok) != 1:
        return
    reszletezo = reszletezok[0]
    kinyert = (reszletezo.kinyert or {}).get("reszletezo") or {}
    if kinyert.get("tobb_szamlat_reszletez"):
        return
    masik_szamla = db.scalar(
        select(BejovoSzamla.id).where(
            BejovoSzamla.email_uzenet_id == bejovo.email_uzenet_id,
            BejovoSzamla.id.notin_([bejovo.id, reszletezo.id]),
            BejovoSzamla.content_type.in_(sorted(ENGEDETT_MIME)),
        )
    )
    if masik_szamla is not None:
        return
    reszletezo.valtozat_szamla_id = bejovo.id
    if reszletezo.allapot == ALLAPOT_PONTOSITAS:
        reszletezo.allapot = ALLAPOT_JOVAHAGYVA
        reszletezo.javaslat = {
            **(reszletezo.javaslat or {}),
            "indoklas": f"A #{bejovo.id} számla költség-részletezője - a bontás javaslata a számlán jelenik meg.",
        }
    _bontas_javaslat_keszites(db, bejovo, reszletezo, kinyert)


def _ertesito_kezeles(db: Session, bejovo: BejovoSzamla) -> None:
    """Számlaértesítő / fizetési emlékeztető: NEM maga a számla. Ha a
    hivatkozott számla már beérkezett (számlaszám+kibocsátó+összeg vagy azonos
    fájl), az értesítő ahhoz kapcsolódik duplikátum-mintára; különben a
    számlafájlra vár - nem kerül az elbírálandó számlák közé."""
    talalat = _duplikacio(db, bejovo)
    if talalat is not None:
        bejovo.allapot = ALLAPOT_DUPLIKATUM
        bejovo.duplikatum_bejovo_id = talalat.id
        bejovo.duplikatum_megjegyzes = (
            f"Értesítő a #{talalat.id} beérkezett számláról "
            f"({talalat.kibocsato_nev or '?'} / {talalat.szamlaszam or 'azonos fájl'}) - önálló teendő nincs."
        )
        return
    bejovo.allapot = ALLAPOT_PONTOSITAS
    bejovo.javaslat = {
        "tipus": None,
        "indoklas": (
            "Számlaértesítő/fizetési emlékeztető - maga a számlafájl még nem érkezett meg. "
            "Számlafájlra vár: ha a számla később beérkezik, a duplikáció-vizsgálat összekapcsolja őket."
        ),
        "alternativak": [],
        "figyelmeztetesek": ["Értesítő számlafájl nélkül - végleges rögzítés előtt kell az igazi számla."],
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

    A DÖNTÉS SORRENDJE (a felhasználó előírása, a korábbi hiba javításával):

    1. a számla azonosítása (kibocsátó, vevő, időszak, pénznem, hivatkozások);
    2. duplikáció (a hívó már megnézte);
    3. a PONTOS PROJEKTKÓD SZŰKÍT: ha a dokumentum/levél/utasítás kódot mond,
       a TIG- és kiadás-keresés arra a kódra (és forgatásaira) szűkül - a
       kóddal ELLENTÉTES tétel automatikusan sosem lehet kiválasztott cél,
       legfeljebb megjelölt alternatíva;
    4. a szűkített körben a "Ki számláz kiért" (számlázó fél) kapcsolatok;
    5. csak EZUTÁN az összeg/pénznem/teljesítés összevetés;
    6. új kiadást csak akkor javaslunk, ha nincs megfelelő meglévő tétel.

    Partner + azonos összeg ÖNMAGÁBAN nem választ: ha több egyformán
    valószínű jelölt van, nem az első rekordot vesszük, hanem pontosítást
    kérünk, az összes jelölttel. Újrafuttatható: az utasítás módosítása után
    is ez fut, a már kinyert adatokon."""
    figyelmeztetesek: list[str] = list((bejovo.kinyert or {}).get("osszeg_figyelmeztetesek") or [])
    #: Egymásnak ELLENTMONDÓ jelek (kód vs. levél, számlaszám-ütközés, egyező
    #: összeg másik projekten) - a javaslat-erősség ebből lesz "ellentmondo".
    ellentmondas = False
    utkozes = _szamlaszam_utkozes(db, bejovo)
    if utkozes:
        figyelmeztetesek.append(utkozes)
        ellentmondas = True

    tipus: str | None = None
    indoklas = ""

    utasitas = _norm(bejovo.felhasznaloi_utasitas)
    mezok = (bejovo.kinyert or {}).get("mezok") or {}

    # ── 1) HIVATKOZÁSOK: kód a dokumentumban, a levélben és az utasításban -
    # KÜLÖN gyűjtve, hogy az ellentmondás (a dokumentum mást mond, mint a
    # levél/utasítás) látható legyen, ne csendben döntsünk.
    dok_szoveg = " ".join(filter(None, [" ".join(mezok.get("projektkod_hivatkozasok") or []), mezok.get("megjegyzes") or ""]))
    level_szoveg = " ".join(filter(None, [bejovo.email_targy or "", bejovo.email_szoveg or "", bejovo.felhasznaloi_utasitas or ""]))
    dok_kodok = list(dict.fromkeys(PROJEKTKOD_MINTA.findall(dok_szoveg.upper())))
    level_kodok = list(dict.fromkeys(PROJEKTKOD_MINTA.findall(level_szoveg.upper())))
    kodok = list(dict.fromkeys(dok_kodok + level_kodok))
    if dok_kodok and level_kodok and set(dok_kodok) != set(level_kodok):
        figyelmeztetesek.append(
            f"A dokumentum ({', '.join(dok_kodok)}) és a levél/utasítás ({', '.join(level_kodok)}) "
            "eltérő projektkódot mond - ellenőrizd, melyik az igaz."
        )
        ellentmondas = True
    projekt_kodok: list[ProjectCode] = []
    for kod in kodok[:5]:
        pc = db.scalar(select(ProjectCode).where(func.upper(ProjectCode.projektkod) == kod))
        if pc is not None:
            projekt_kodok.append(pc)
    kod_idk = {pc.id for pc in projekt_kodok}

    # ── A számlázó fél: adószám a legerősebb, aztán cégnév/név.
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

    # ── Jelöltek RÉSZLETEKKEL (projekt, dátum, fél, összeg, mi egyezik/tér el).
    tig_jeloltek = _kulsos_tig_jeloltek(db, bejovo, fel_employee, fel_vallalkozas, kod_idk)
    belsos_jelolt = _belsos_tig_jelolt(db, bejovo, fel_employee)
    kiadas_jeloltek = _kiadas_jeloltek(db, bejovo, fel_employee, kod_idk)
    erezsi_jelolt = _erezsi_jelolt(db, bejovo)
    auto_jelolt = _auto_jelolt(db, f"{dok_szoveg} {level_szoveg}")

    alternativak: list[dict] = []
    for j in tig_jeloltek:
        alternativak.append({"tipus": "kulsos_tig", "cel_id": j["cert"].id, "cimke": j["cimke"], "indoklas": j["indoklas"], "reszletek": j["reszletek"]})
    if belsos_jelolt is not None:
        cert, ok = belsos_jelolt
        alternativak.append({"tipus": "belsos_tig", "cel_id": cert.id, "cimke": f"Belsős TIG {cert.ev}. {cert.honap:02d}. hó", "indoklas": ok})
    for j in kiadas_jeloltek:
        alternativak.append({"tipus": j["tipus"], "cel_id": j["cel_id"], "cimke": j["cimke"], "indoklas": j["indoklas"], "reszletek": j.get("reszletek")})
    if erezsi_jelolt is not None:
        idoszak, ok = erezsi_jelolt
        alternativak.append({"tipus": "erezsi", "cel_id": idoszak.id, "cimke": f"E-Rezsi: {idoszak.kotelezettseg.nev} - {idoszak.esedekesseg}", "indoklas": ok})
    if auto_jelolt is not None:
        auto, ok = auto_jelolt
        alternativak.append({"tipus": "auto", "cel_id": auto.id, "cimke": f"Autó: {auto.rendszam}", "indoklas": ok})
    for pc in projekt_kodok:
        alternativak.append({"tipus": "kiadas_uj", "cel_id": pc.id, "cimke": f"Új kiadás a(z) {pc.projektkod} projektkódhoz", "indoklas": "A projektkód szerepel a dokumentumban/levélben/utasításban."})

    # A kóddal KOMPATIBILIS jelöltek (kód nélkül minden az).
    kod_tigek = [j for j in tig_jeloltek if not kod_idk or j["kod_egyezik"]] if kod_idk else tig_jeloltek
    if kod_idk:
        kod_tigek = [j for j in tig_jeloltek if j["kod_egyezik"]]
    kod_kiadasok = [j for j in kiadas_jeloltek if not kod_idk or j.get("kod_egyezik")]

    # ── DÖNTÉS. A felhasználó szava az első; kód a második; a puszta
    # partner+összeg egyezés többes találatnál sosem dönt.
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
    elif utasitas and ("belsős" in utasitas or "belsos" in utasitas) and belsos_jelolt is not None:
        tipus = "belsos_tig"
        bejovo.cel_internal_certificate_id = belsos_jelolt[0].id
        indoklas = f"A felhasználó belsős TIG-hez kérte ({belsos_jelolt[0].ev}. {belsos_jelolt[0].honap:02d}. hó - a számla teljesítési időszaka szerint)."
    elif utasitas and "tig" in utasitas and kod_tigek:
        tipus = "kulsos_tig"
        bejovo.cel_certificate_id = kod_tigek[0]["cert"].id
        indoklas = f"A felhasználó TIG-hez kérte; a kóddal/féllel egyező legjobb találat: {kod_tigek[0]['cimke']}."
    elif auto_jelolt is not None and utasitas and ("autó" in utasitas or "auto" in utasitas or "szerviz" in utasitas):
        tipus = "auto"
        bejovo.cel_auto_id = auto_jelolt[0].id
        indoklas = f"A felhasználó autóhoz kérte; az azonosított jármű: {auto_jelolt[0].rendszam}."
    elif kod_idk:
        # VAN PONTOS KÓD: azon belül keresünk. A kóddal ellentétes TIG-et
        # akkor sem választjuk, ha az összege egyezik - az alternatívák közt
        # marad, megjelölve.
        for j in tig_jeloltek:
            if not j["kod_egyezik"] and j["osszeg_egyezik"]:
                figyelmeztetesek.append(
                    f"A(z) {j['cimke']} összege egyezik, de MÁSIK projekthez tartozik, mint a megadott "
                    f"kód ({', '.join(kodok)}) - ezért nem ez lett kiválasztva."
                )
                ellentmondas = True
        # A kód projektjén lévő, MÁS FÉLHEZ tartozó TIG nem automatikus cél -
        # az alternatívák közt marad, az "Eltér: számlázó fél" jelöléssel.
        sajat_kod_tigek = [j for j in kod_tigek if j["fel_egyezik"]]
        eros_tigek = [j for j in sajat_kod_tigek if j["osszeg_egyezik"]] or sajat_kod_tigek
        if len(eros_tigek) == 1:
            tipus = "kulsos_tig"
            bejovo.cel_certificate_id = eros_tigek[0]["cert"].id
            indoklas = f"A megadott kód projektjén számlára váró külsős TIG: {eros_tigek[0]['cimke']}."
        elif len(eros_tigek) > 1:
            tipus = None
            indoklas = (
                f"A(z) {', '.join(kodok)} kódon több szóba jövő TIG/forgatás van - válaszd ki a listából, "
                "melyikhez tartozik a számla."
            )
        elif len(kod_kiadasok) == 1:
            tipus = kod_kiadasok[0]["tipus"]
            if tipus == "kulsos_tig":
                bejovo.cel_certificate_id = kod_kiadasok[0]["cel_id"]
            else:
                bejovo.cel_expense_id = kod_kiadasok[0]["cel_id"]
            indoklas = f"A megadott kódon számlára váró meglévő tétel: {kod_kiadasok[0]['cimke']}."
        elif len(projekt_kodok) == 1:
            tipus = "kiadas_uj"
            bejovo.cel_project_code_id = projekt_kodok[0].id
            indoklas = (
                f"A(z) {projekt_kodok[0].projektkod} kódon nincs számlára váró meglévő TIG/kiadás - "
                "ÚJ kiadás készül hozzá (nem kifizetettként)."
            )
            if fel_employee is not None:
                bejovo.cel_employee_id = fel_employee.id
        else:
            tipus = None
            indoklas = "Több projektkód is szerepel - válaszd ki, melyikhez tartozik (vagy oszd fel az ellenőrzőben)."
    elif erezsi_jelolt is not None:
        tipus = "erezsi"
        bejovo.cel_kotelezettseg_idoszak_id = erezsi_jelolt[0].id
        indoklas = erezsi_jelolt[1]
    elif tig_jeloltek:
        # NINCS KÓD: partner + összeg csak akkor dönt, ha PONTOSAN EGY
        # egyformán valószínű jelölt van - több találatnál nem az elsőt
        # választjuk, hanem pontosítást kérünk.
        osszeg_egyezok = [j for j in tig_jeloltek if j["osszeg_egyezik"]]
        if len(osszeg_egyezok) == 1 and len(tig_jeloltek) == 1:
            tipus = "kulsos_tig"
            bejovo.cel_certificate_id = osszeg_egyezok[0]["cert"].id
            indoklas = f"Egyetlen számlára váró külsős TIG a félnél, egyező összeggel: {osszeg_egyezok[0]['cimke']}."
        else:
            tipus = None
            indoklas = (
                "A partner és az összeg önmagában nem elég a biztos párosításhoz "
                f"({len(tig_jeloltek)} szóba jövő TIG) - válaszd ki a listából, vagy írd meg a projektkódot."
            )
    elif len(kiadas_jeloltek) == 1:
        tipus = kiadas_jeloltek[0]["tipus"]
        if tipus == "kulsos_tig":
            bejovo.cel_certificate_id = kiadas_jeloltek[0]["cel_id"]
        else:
            bejovo.cel_expense_id = kiadas_jeloltek[0]["cel_id"]
        indoklas = f"Meglévő, számlára váró tétel a félnél: {kiadas_jeloltek[0]['cimke']}"
    elif len(kiadas_jeloltek) > 1:
        tipus = None
        indoklas = f"Több számlára váró kiadás is szóba jön ({len(kiadas_jeloltek)}) - válaszd ki a listából."
    else:
        tipus = None
        indoklas = (
            "Nem dönthető el egyértelműen, hová tartozik - a feladó neve vagy hasonló összeg önmagában nem elég. "
            "Válassz célt az ellenőrzőben."
        )

    # ── JAVASLAT-ERŐSSÉG + BIZONYÍTÉK (a felhasználó kérése): a felület ne
    # csak a javaslatot mutassa, hanem azt is, MIRE épül és mennyire biztos -
    # "biztos" | "tobb_lehetseges" | "ellentmondo" | "keves_info".
    bizonyitek: list[str] = []
    if dok_kodok:
        bizonyitek.append(f"Projektkód a dokumentumban: {', '.join(dok_kodok)}")
    if level_kodok:
        bizonyitek.append(f"Projektkód a levélben/utasításban: {', '.join(level_kodok)}")
    if fel_employee is not None:
        bizonyitek.append(
            f"A kibocsátó azonosítva: {fel_employee.full_name} (adószám/név-egyezés a csapat-nyilvántartással)"
        )
    if fel_vallalkozas is not None:
        bizonyitek.append(f"A kibocsátó azonosítva: {fel_vallalkozas.nev} (számlázó vállalkozás)")
    if bejovo.felhasznaloi_utasitas:
        bizonyitek.append(f"Felhasználói utasítás: {bejovo.felhasznaloi_utasitas[:200]}")
    for j in tig_jeloltek:
        if j["osszeg_egyezik"]:
            bizonyitek.append(f"Összeg-egyezés: {j['cimke']}")
    if ellentmondas:
        erosseg = "ellentmondo"
    elif tipus:
        erosseg = "biztos"
    elif alternativak:
        erosseg = "tobb_lehetseges"
    else:
        erosseg = "keves_info"

    bejovo.cel_tipus = tipus
    bejovo.javaslat = {
        "tipus": tipus,
        "indoklas": indoklas,
        "alternativak": alternativak[:8],
        "figyelmeztetesek": figyelmeztetesek,
        "erosseg": erosseg,
        "bizonyitek": bizonyitek[:8],
    }
    bejovo.allapot = ALLAPOT_ELLENORZENDO if tipus else ALLAPOT_PONTOSITAS
    if bejovo.dokumentum_tipus in ("modosito", "storno") and not (bejovo.kinyert or {}).get("mezok", {}).get(
        "elozmeny_szamlaszam"
    ):
        bejovo.allapot = ALLAPOT_PONTOSITAS
        bejovo.javaslat["figyelmeztetesek"].append(
            "Módosító/sztornó számla előzmény-hivatkozás nélkül - keresd meg az eredetit."
        )


def _cert_projektkod_id(cert: PerformanceCertificate) -> int | None:
    """Melyik projektkódhoz tartozik a TIG - a forgatásán át vagy közvetlenül."""
    if cert.project_code_id is not None:
        return cert.project_code_id
    if cert.project is not None:
        return cert.project.project_code_id
    return None


def _tig_reszletek(
    db: Session, cert: PerformanceCertificate, bejovo: BejovoSzamla, kod_idk: set[int], fel_egyezik: bool
) -> dict:
    """Egy TIG-jelölt EMBERI részletei: projekt+kód, forgatás dátuma, számlázó
    fél és a lefedett személyek, összeg, meglévő számlák - és hogy mi egyezik
    / mi tér el a beérkezett számlához képest."""
    fel = cert.employee.full_name if cert.employee else (cert.vallalkozas.nev if cert.vallalkozas else "?")
    projekt_nev = cert.project.nev if cert.project else None
    datum = cert.project.forgatas_datuma.isoformat() if cert.project and cert.project.forgatas_datuma else None
    pc_id = _cert_projektkod_id(cert)
    kod = None
    if pc_id is not None:
        pc = db.get(ProjectCode, pc_id)
        kod = pc.projektkod if pc else None
    fedettek = sorted({t.employee.full_name for t in cert.tetelek if t.employee is not None}) if cert.tetelek else []
    kod_egyezik = bool(kod_idk) and pc_id in kod_idk
    osszeg_egyezik = (
        cert.netto_osszeg is not None
        and bejovo.netto is not None
        and abs(float(cert.netto_osszeg) - float(bejovo.netto)) < 1
    )
    egyezik: list[str] = ["számlázó fél"] if fel_egyezik else []
    elter: list[str] = [] if fel_egyezik else ["számlázó fél (a számla kibocsátója más)"]
    if kod_idk:
        (egyezik if kod_egyezik else elter).append("projektkód")
    if cert.netto_osszeg is not None and bejovo.netto is not None:
        (egyezik if osszeg_egyezik else elter).append(
            "összeg" if osszeg_egyezik else f"összeg (TIG: {float(cert.netto_osszeg):,.0f} Ft)".replace(",", " ")
        )
    cimke_reszek = [f"Külsős TIG - {fel}"]
    if projekt_nev:
        cimke_reszek.append(projekt_nev)
    if kod:
        cimke_reszek.append(kod)
    if datum:
        cimke_reszek.append(datum)
    return {
        "cert": cert,
        "kod_egyezik": kod_egyezik,
        "osszeg_egyezik": osszeg_egyezik,
        "fel_egyezik": fel_egyezik,
        "cimke": " – ".join(cimke_reszek),
        "indoklas": ("Egyezik: " + ", ".join(egyezik)) + (" · Eltér: " + ", ".join(elter) if elter else ""),
        "reszletek": {
            "projekt_nev": projekt_nev,
            "projektkod": kod,
            "forgatas_datuma": datum,
            "szamlazo_fel": fel,
            "fedett_szemelyek": fedettek,
            "netto": float(cert.netto_osszeg) if cert.netto_osszeg is not None else None,
            "meglevo_szamlak": len(cert.invoices),
            "egyezik": egyezik,
            "elter": elter,
        },
    }


def _kulsos_tig_jeloltek(
    db: Session,
    bejovo: BejovoSzamla,
    emp: Employee | None,
    vall: Vallalkozas | None,
    kod_idk: set[int],
) -> list[dict]:
    """Számlára váró külsős TIG-jelöltek. Ha van PONTOS KÓD, a kód projektjein
    lévő nyitott TIG-ek is jelöltek (akkor is, ha a fél nem ismert) - a kód
    SZŰKÍT, nem mellékes. Rendezés: kód-egyezés > összeg-egyezés > frissebb."""
    from sqlalchemy import or_

    felt = []
    if emp is not None:
        felt.append(PerformanceCertificate.employee_id == emp.id)
    if vall is not None:
        felt.append(PerformanceCertificate.vallalkozas_id == vall.id)
    jeloltek: dict[int, PerformanceCertificate] = {}
    fel_egyezok: set[int] = set()
    if felt:
        for cert in db.scalars(
            select(PerformanceCertificate)
            .where(or_(*felt), PerformanceCertificate.szamla_kifizetve.is_(False))
            .order_by(PerformanceCertificate.id.desc())
            .limit(15)
        ):
            jeloltek[cert.id] = cert
            fel_egyezok.add(cert.id)
    if kod_idk:
        # A kód projektjeinek nyitott TIG-jei - fél-egyezés nélkül is.
        from app.models.project import Project

        for cert in db.scalars(
            select(PerformanceCertificate)
            .outerjoin(Project, PerformanceCertificate.project_id == Project.id)
            .where(
                PerformanceCertificate.szamla_kifizetve.is_(False),
                or_(
                    PerformanceCertificate.project_code_id.in_(kod_idk),
                    Project.project_code_id.in_(kod_idk),
                ),
            )
            .order_by(PerformanceCertificate.id.desc())
            .limit(15)
        ):
            jeloltek[cert.id] = cert
    eredmeny = [_tig_reszletek(db, cert, bejovo, kod_idk, cert.id in fel_egyezok) for cert in jeloltek.values()]
    eredmeny.sort(key=lambda j: (not j["kod_egyezik"], not j["fel_egyezik"], not j["osszeg_egyezik"], -j["cert"].id))
    return eredmeny[:6]


def _belsos_tig_jelolt(
    db: Session, bejovo: BejovoSzamla, emp: Employee | None
) -> tuple[InternalPerformanceCertificate, str] | None:
    """A havi belsős TIG-et a SZÁMLA TELJESÍTÉSI IDŐSZAKA választja ki (annak
    híján a kiállítás kelte) - SOSEM a levél beérkezési hónapja."""
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
    return cert, (
        f"{emp.full_name} belsős TIG-je a számla teljesítési időszakának hónapjára ({alap.year}.{alap.month:02d})."
    )


def _kiadas_jeloltek(db: Session, bejovo: BejovoSzamla, emp: Employee | None, kod_idk: set[int]) -> list[dict]:
    """Meglévő, számlára váró kiadás-jelöltek.

    Ha a kiadás egy TIG-ből jött létre (a TIG kifizetésekor keletkező sor,
    PerformanceCertificate.expense_id köti), a jelölt maga a TIG lesz: a
    számlát az EREDETI TIG-folyamaton át kapcsoljuk, hogy az Utókövetés, a
    TIG és a Pénzügyek ugyanazt mutassa - a származtatott kiadássorra tett
    fájl a TIG-et "számla hiányzik" állapotban hagyná."""
    from sqlalchemy import or_

    felt = []
    if emp is not None:
        felt.append(Expense.employee_id == emp.id)
    if bejovo.kibocsato_nev:
        felt.append(func.lower(Expense.megnevezes) == _norm(bejovo.kibocsato_nev))
    if not felt:
        return []
    hatar = date.today() - timedelta(days=180)
    q = select(Expense).where(
        or_(*felt),
        Expense.nincs_szamla.is_(False),
        (Expense.kiadas_datuma.is_(None)) | (Expense.kiadas_datuma >= hatar),
    )
    if kod_idk:
        q = q.where(Expense.project_code_id.in_(kod_idk))
    sorok = db.scalars(q.order_by(Expense.id.desc()).limit(20)).all()
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
    # A TIG-ből származó kiadássorok: a hozzájuk tartozó TIG az igazi cél.
    tig_kotesek = {
        cert.expense_id: cert
        for cert in db.scalars(
            select(PerformanceCertificate).where(
                PerformanceCertificate.expense_id.in_([s.id for s in sorok])
            )
        )
    }
    eredmeny: list[dict] = []
    for s in sorok:
        if s.id in csatolt:
            continue
        osszeg_egyezik = s.netto is not None and bejovo.netto is not None and abs(float(s.netto) - float(bejovo.netto)) < 1
        kod_egyezik = bool(kod_idk) and s.project_code_id in kod_idk
        cert = tig_kotesek.get(s.id)
        if cert is not None:
            j = _tig_reszletek(db, cert, bejovo, kod_idk, True)
            eredmeny.append({
                "tipus": "kulsos_tig",
                "cel_id": cert.id,
                "cimke": j["cimke"] + " (a kiadássor ebből a TIG-ből származik)",
                "indoklas": "A meglévő kiadás egy TIG-ből jött létre - a számla az eredeti TIG-hez kerül, hogy minden nézet ugyanazt mutassa.",
                "kod_egyezik": j["kod_egyezik"],
                "osszeg_egyezik": j["osszeg_egyezik"],
                "reszletek": j["reszletek"],
            })
            continue
        pc = db.get(ProjectCode, s.project_code_id) if s.project_code_id else None
        eredmeny.append({
            "tipus": "kiadas_csatolas",
            "cel_id": s.id,
            "cimke": f"Kiadás: {s.megnevezes} – {s.kiadas_leiras or '-'}" + (f" – {pc.projektkod}" if pc else ""),
            "indoklas": ("Összeg-egyezés, " if osszeg_egyezik else "A partner egyezik, ") + "számla még nincs hozzá.",
            "kod_egyezik": kod_egyezik,
            "osszeg_egyezik": osszeg_egyezik,
            "reszletek": {
                "projektkod": pc.projektkod if pc else None,
                "netto": float(s.netto) if s.netto is not None else None,
                "egyezik": (["összeg"] if osszeg_egyezik else []) + (["projektkód"] if kod_egyezik else []),
                "elter": [] if osszeg_egyezik else ([f"összeg (kiadás: {float(s.netto):,.0f} Ft)".replace(",", " ")] if s.netto is not None else []),
            },
        })
    eredmeny.sort(key=lambda j: (not j.get("kod_egyezik"), not j.get("osszeg_egyezik")))
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


def _hatarido_atvitel(cel, mezo_nev: str, bejovo: BejovoSzamla, naplo: dict, cimke: str) -> None:
    """A SZÁMLA fizetési határidejének átvitele a célrekordra (a felhasználó
    kérése: felvezetéskor a határidő is menjen oda, különösen az utókövetési
    TIG-re). A számla a saját határidejének igazságforrása: kitöltjük az üres
    mezőt, az eltérőt pedig a számla szerintire frissítjük - az előző érték a
    naplóba kerül, hogy visszakereshető legyen."""
    uj = bejovo.fizetesi_hatarido
    if uj is None:
        return
    regi = getattr(cel, mezo_nev, None)
    if regi == uj:
        return
    if regi is not None:
        naplo.setdefault("elozo_ertekek", {}).setdefault("fizetesi_hataridok", []).append(
            {"cel": cimke, "elozo": regi.isoformat(), "uj": uj.isoformat()}
        )
    setattr(cel, mezo_nev, uj)
    naplo.setdefault("megjegyzesek", []).append(
        f"{cimke} fizetési határideje a számláról: {uj.isoformat()}"
        + (f" (előtte: {regi.isoformat()})" if regi is not None else "")
    )


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
    if bejovo.dokumentum_tipus == "dijbekero" and cel_tipus in ("kiadas_uj", "mukodesi", "auto", "bontas"):
        raise ErkeztetesHiba("Díjbekérő nem rögzíthető végleges kiadásként - várd meg a számlát.")
    if bejovo.dokumentum_tipus == "ertesito" and cel_tipus in ("kiadas_uj", "mukodesi", "auto", "bontas"):
        raise ErkeztetesHiba(
            "Ez számlaértesítő/emlékeztető, nem maga a számla - várd meg a számlafájlt, abból rögzíthető kiadás."
        )

    fajl = None
    if bejovo.storage_key:
        fajl = document_storage.download_bytes(bejovo.storage_key)

    naplo: dict = {"cel_tipus": cel_tipus, "letrejott": [], "csatolt": []}

    if cel_tipus in ("kiadas_uj", "mukodesi", "auto"):
        naplo = _rogzit_kiadaskent(db, bejovo, dontes, fajl, naplo, cel_tipus)
    elif cel_tipus == "bontas":
        naplo = _rogzit_bontaskent(db, bejovo, dontes, fajl, naplo)
    elif cel_tipus == "kiadas_csatolas":
        exp = db.get(Expense, dontes.get("cel_expense_id") or bejovo.cel_expense_id or 0)
        if exp is None:
            raise ErkeztetesHiba("A kiválasztott kiadás nem található.")
        # Ha ez a kiadássor egy TIG-ből származik (a TIG kifizetésekor jött
        # létre), a számla az EREDETI TIG-folyamatra kerül - különben a TIG
        # "számla hiányzik" maradna, miközben a fájl a származtatott soron ül.
        cert = db.scalar(select(PerformanceCertificate).where(PerformanceCertificate.expense_id == exp.id))
        if cert is not None and fajl is not None:
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
            bejovo.cel_certificate_id = cert.id
            _hatarido_atvitel(cert, "fizetesi_hatarido", bejovo, naplo, f"A(z) #{cert.id} külsős TIG")
            naplo["csatolt"].append({"tipus": "performanceCertificate", "id": cert.id, "szamla_sor": sor.id})
            naplo.setdefault("megjegyzesek", []).append(
                f"A kiválasztott kiadás a #{cert.id} TIG-ből származik - a számla az eredeti TIG-hez került, "
                "így az Utókövetés, a TIG és a Pénzügyek ugyanazt mutatja."
            )
        else:
            _csatol_fajl(db, "expense", exp.id, bejovo, fajl, naplo)
            _hatarido_atvitel(exp, "fizetes_hatarideje", bejovo, naplo, f"A(z) #{exp.id} kiadás")
            naplo["csatolt"].append({"tipus": "expense", "id": exp.id})
        bejovo.rogzitett_expense_id = exp.id
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
        # kifizetés, és nem is aláírt TIG (a felhasználó előírása). A számla
        # fizetési határideje viszont a TIG-re kerül (Utókövetés).
        _hatarido_atvitel(cert, "fizetesi_hatarido", bejovo, naplo, f"A(z) #{cert.id} külsős TIG")
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
        _hatarido_atvitel(cert, "fizetesi_hatarido", bejovo, naplo, f"A(z) {cert.ev}.{cert.honap:02d}. havi belsős TIG")
        naplo["csatolt"].append({"tipus": "internalPerformanceCertificate", "id": cert.id, "szamla_sor": sor.id})
    elif cel_tipus == "erezsi":
        idoszak = db.get(
            KotelezettsegIdoszak,
            dontes.get("cel_kotelezettseg_idoszak_id") or bejovo.cel_kotelezettseg_idoszak_id or 0,
        )
        if idoszak is None:
            raise ErkeztetesHiba("A kiválasztott E-Rezsi időszak nem található.")
        # A TÉNYLEGES terhelés az időszakra kerül - a `fizetve` jelzőhöz nem
        # nyúlunk (a számla megérkezése nem kifizetés). Az ELŐZŐ értéket a
        # naplóba tesszük, hogy egy visszavonás/reset bizonyítható alapról
        # állíthasson vissza.
        if idoszak.osszeg is None and bejovo.netto is not None:
            naplo.setdefault("elozo_ertekek", {})["kotelezettseg_idoszak"] = {
                "id": idoszak.id,
                "osszeg": None,
                "plusz_afa": idoszak.plusz_afa,
                "penznem": idoszak.penznem,
            }
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
    plusz_afa, afa_szazalek = _afa_adatok(bejovo, naplo)

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


def _afa_adatok(bejovo: BejovoSzamla, naplo: dict) -> tuple[bool, float | None]:
    """Van-e áfa a számlán és milyen kulccsal - a kiadás-rögzítés közös
    bemenete (az egy-célú és a bontásos rögzítés is ezt használja)."""
    plusz_afa = bool(bejovo.afa_osszeg) or bool((bejovo.kinyert or {}).get("mezok", {}).get("afa_kulcsok"))
    afa_szazalek = None
    kulcsok = (bejovo.kinyert or {}).get("mezok", {}).get("afa_kulcsok") or []
    if len(kulcsok) == 1 and _szam(kulcsok[0]):
        afa_szazalek = _szam(kulcsok[0])
    elif len(kulcsok) > 1:
        naplo.setdefault("megjegyzesek", []).append(
            "Több áfakulcs szerepel a számlán - a bruttó a számláról jön, nem kulcsból számolt."
        )
    return plusz_afa, afa_szazalek


#: A bontás-sorokban megengedett célok. Belsős TIG / E-Rezsi / KP szándékosan
#: nincs köztük: azok jellemzően teljes számlát fednek - ha mégis bontani
#: kellene rájuk, az egyedi eset, kézzel kezelendő.
BONTAS_CEL_TIPUSOK = ("kiadas_uj", "mukodesi", "kulsos_tig", "kiadas_csatolas")


def _rogzit_bontaskent(db: Session, bejovo: BejovoSzamla, dontes: dict, fajl: bytes | None, naplo: dict) -> dict:
    """TÖBB PROJEKT EGY SZÁMLÁN: a bontás-sorok vegyesen hozhatnak létre új
    kiadást (kesz=False), csatolhatnak meglévő kiadáshoz vagy külsős TIG-hez.

    A számla EGY pénzügyi dokumentum marad: a sorok nettói pontosan a számla
    nettóját adják ki (±1 Ft kerekítés az utolsó soron, LÁTHATÓ naplóbejegyzés-
    sel); a meglévő célok (TIG, kiadás) összegét NEM írjuk át - ott a sor-összeg
    a naplóba kerül. Hiányos bontással nem véglegesíthető."""
    sorok = dontes.get("bontas") if dontes.get("bontas") is not None else bejovo.bontas
    if isinstance(sorok, dict):
        sorok = sorok.get("sorok")
    sorok = [s for s in (sorok or []) if isinstance(s, dict)]
    if not sorok:
        raise ErkeztetesHiba("A bontáshoz legalább egy hozzárendelési sor kell - vedd fel a sorokat az ellenőrzőben.")

    netto = _szam(dontes.get("netto")) if dontes.get("netto") is not None else (
        float(bejovo.netto) if bejovo.netto is not None else None
    )
    if netto is None:
        raise ErkeztetesHiba("Hiányzik a számla nettó összege - bontás csak ismert végösszegre véglegesíthető.")

    reszek: list[dict] = []
    for i, sor in enumerate(sorok, start=1):
        ct = sor.get("cel_tipus")
        if ct not in BONTAS_CEL_TIPUSOK:
            raise ErkeztetesHiba(
                f"A bontás {i}. sorának célja hiányzik vagy nem támogatott ({ct or 'üres'}) - "
                "válassz projektet/tételt minden sorhoz."
            )
        resz_netto = _szam(sor.get("netto"))
        if not resz_netto:
            raise ErkeztetesHiba(f"A bontás {i}. sorából hiányzik az összeg.")
        if ct == "kiadas_uj" and not sor.get("project_code_id"):
            raise ErkeztetesHiba(
                f"A bontás {i}. sora új kiadás, de nincs projektkódja - válaszd ki, vagy jelöld működésinek."
            )
        if ct in ("kulsos_tig", "kiadas_csatolas") and not sor.get("cel_id"):
            raise ErkeztetesHiba(f"A bontás {i}. sorához nincs kiválasztva a meglévő tétel.")
        reszek.append({**sor, "netto": float(resz_netto)})

    osszesen = round(sum(r["netto"] for r in reszek), 2)
    elteres = round(netto - osszesen, 2)
    if abs(elteres) > 1:
        raise ErkeztetesHiba(
            f"A bontás sorai ({osszesen:,.2f}) nem adják ki a számla nettóját ({netto:,.2f}) - "
            f"az eltérés {elteres:+,.2f}. Hiányos bontással a számla nem véglegesíthető.".replace(",", " ")
        )
    if elteres:
        reszek[-1]["netto"] = round(reszek[-1]["netto"] + elteres, 2)
        naplo.setdefault("megjegyzesek", []).append(
            f"Kerekítési korrekció: az utolsó bontás-sor összege {elteres:+.2f} Ft-tal igazítva, "
            f"hogy a sorok pontosan a számla nettóját ({netto:,.2f}) adják ki.".replace(",", " ")
        )

    plusz_afa, afa_szazalek = _afa_adatok(bejovo, naplo)
    arfolyam = _szam(dontes.get("arfolyam"))
    if penznem.devizas(bejovo.penznem) and arfolyam is None and any(
        r["cel_tipus"] in ("kiadas_uj", "mukodesi") for r in reszek
    ):
        raise ErkeztetesHiba(
            f"A számla {bejovo.penznem}-ben szól - add meg az árfolyamot (forrással/dátummal), "
            "önkényes árfolyamot nem használunk."
        )

    elso_expense: Expense | None = None
    uj_kiadas_sorszam = 0
    uj_kiadasok_szama = sum(1 for r in reszek if r["cel_tipus"] in ("kiadas_uj", "mukodesi"))
    for i, resz in enumerate(reszek, start=1):
        ct = resz["cel_tipus"]
        resz_netto = resz["netto"]
        if ct in ("kiadas_uj", "mukodesi"):
            uj_kiadas_sorszam += 1
            huf_netto = resz_netto
            eredeti_penznem = None
            if penznem.devizas(bejovo.penznem):
                eredeti_penznem = bejovo.penznem
                huf_netto = penznem.forintra(resz_netto, arfolyam) or 0
            brutto = round(huf_netto * (1 + (afa_szazalek or 27) / 100), 2) if plusz_afa else huf_netto
            pc_id = resz.get("project_code_id")
            if ct == "kiadas_uj" and pc_id is not None and db.get(ProjectCode, pc_id) is None:
                raise ErkeztetesHiba(f"A bontás {i}. sorában megadott projektkód (#{pc_id}) nem található.")
            exp = Expense(
                megnevezes=(dontes.get("megnevezes") or bejovo.kibocsato_nev or "Ismeretlen partner")[:255],
                kiadas_leiras=(
                    str(resz.get("megjegyzes") or dontes.get("kiadas_leiras") or _alap_leiras(bejovo))[:200]
                    + f" – bontott számla {uj_kiadas_sorszam}/{uj_kiadasok_szama}"
                ),
                netto=huf_netto,
                brutto=brutto,
                plusz_afa="igen" if plusz_afa else None,
                afa_szazalek=afa_szazalek,
                penznem="HUF",
                eredeti_penznem=eredeti_penznem,
                eredeti_netto=resz_netto if eredeti_penznem else None,
                eredeti_brutto=(
                    round(resz_netto * (1 + (afa_szazalek or 27) / 100), 2)
                    if eredeti_penznem and plusz_afa
                    else (resz_netto if eredeti_penznem else None)
                ),
                arfolyam=arfolyam,
                kiadas_datuma=bejovo.teljesites_datuma or bejovo.kiallitas_datuma,
                fizetes_hatarideje=bejovo.fizetesi_hatarido,
                project_code_id=None if ct == "mukodesi" else pc_id,
                employee_id=dontes.get("cel_employee_id") or bejovo.cel_employee_id,
                tipus=dontes.get("tipus")
                or ("kulsos" if (dontes.get("cel_employee_id") or bejovo.cel_employee_id) else "egyeb"),
                kifizetes_modja=dontes.get("kifizetes_modja")
                or ((bejovo.kinyert or {}).get("mezok", {}).get("fizetesi_mod") or None),
                # A SZÁMLA MEGÉRKEZÉSE NEM KIFIZETÉS: a tétel nyitottként születik.
                kesz=False,
            )
            db.add(exp)
            db.flush()
            naplo["letrejott"].append({"tipus": "expense", "id": exp.id, "netto": huf_netto, "bontas_sor": i})
            if elso_expense is None:
                elso_expense = exp
        elif ct == "kulsos_tig":
            cert = db.get(PerformanceCertificate, resz.get("cel_id") or 0)
            if cert is None:
                raise ErkeztetesHiba(f"A bontás {i}. sorában hivatkozott külsős TIG nem található.")
            if fajl is None:
                raise ErkeztetesHiba("A TIG-hez kapcsoláshoz kell a számla fájlja.")
            inv = PerformanceCertificateInvoice(
                certificate_id=cert.id,
                filename=bejovo.fajl_nev or "szamla.pdf",
                storage_key="",
                url="",
                content_type=bejovo.content_type,
            )
            db.add(inv)
            db.flush()
            kulcs = f"tig-szamla/{cert.id}/{inv.id}-{re.sub(r'[^A-Za-z0-9._-]+', '_', inv.filename)[:80]}"
            inv.url = document_storage.upload_bytes(fajl, kulcs, bejovo.content_type or "application/pdf")
            inv.storage_key = kulcs
            _hatarido_atvitel(cert, "fizetesi_hatarido", bejovo, naplo, f"A(z) #{cert.id} külsős TIG")
            naplo["csatolt"].append(
                {"tipus": "performanceCertificate", "id": cert.id, "szamla_sor": inv.id, "bontas_netto": resz_netto}
            )
            # A TIG ÖSSZEGÉT NEM ÍRJUK ÁT - a bontás szerinti rész a naplóban.
            naplo.setdefault("megjegyzesek", []).append(
                f"A(z) #{cert.id} TIG-re a bontás szerint {resz_netto:,.0f} Ft esik - "
                "a TIG összegét nem módosítottuk (a számla-sor a bizonyíték).".replace(",", " ")
            )
        elif ct == "kiadas_csatolas":
            exp = db.get(Expense, resz.get("cel_id") or 0)
            if exp is None:
                raise ErkeztetesHiba(f"A bontás {i}. sorában hivatkozott kiadás nem található.")
            _csatol_fajl(db, "expense", exp.id, bejovo, fajl, naplo)
            _hatarido_atvitel(exp, "fizetes_hatarideje", bejovo, naplo, f"A(z) #{exp.id} kiadás")
            naplo["csatolt"].append({"tipus": "expense", "id": exp.id, "bontas_netto": resz_netto})
            # A MEGLÉVŐ kiadás összegéhez nem nyúlunk - a rész a naplóban.
            naplo.setdefault("megjegyzesek", []).append(
                f"A(z) #{exp.id} kiadásra a bontás szerint {resz_netto:,.0f} Ft esik - "
                "a kiadás összegét nem módosítottuk.".replace(",", " ")
            )

    # A dokumentum EGY példányban: az első ÚJ kiadáshoz kerül csatolmányként
    # (a TIG-sorok a saját számla-sorukat kapták); a többi sor a naplóban
    # hivatkozik rá - a számla nem sokszorozódik.
    if elso_expense is not None:
        _csatol_fajl(db, "expense", elso_expense.id, bejovo, fajl, naplo)
        bejovo.rogzitett_expense_id = elso_expense.id
        if uj_kiadasok_szama > 1:
            naplo.setdefault("megjegyzesek", []).append(
                f"A számla fájlja a(z) #{elso_expense.id} kiadásnál van - a többi bontott sor erre hivatkozik."
            )
    bejovo.bontas = reszek
    naplo["bontas"] = reszek
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
