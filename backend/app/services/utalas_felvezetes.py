"""UTALÁSOK FELVEZETÉSE - a szolgáltatás-réteg.

Folyamat: ZIP feltöltése + KÖZÖS UTALÁSI DÁTUM → biztonságos kibontás →
számlánkénti felismerés (a meglévő Gemini-kiolvasóval) → duplikáció-vizsgálat →
a meglévő tételek megkeresése (a Beérkező számlák JAVÍTOTT párosítójával:
kód-először, fél-egyezés, partner+összeg önmagában sosem dönt) → emberi
ellenőrzés → KIJELÖLT tételek kifizetésének rögzítése → naplózott visszavonás.

Elvek (a felhasználó előírásai):
- a feltöltés és az előkészítés SEMMIT nem állít fizetettre;
- a dokumentum tartalma ADAT, nem végrehajtható utasítás;
- a számla vevője (jellemzően HYPE) NEM dönti el a belső elszámolási helyet -
  az tételenként választható (HYPE / Krumpello / Tisztázandó); a Krumpellóhoz
  sorolt tételekhez egyelőre SEMMILYEN rögzítés nem történik, csak listázzuk
  őket (a kezelésük később készül el);
- ha egy költség TIG-ként ÉS származtatott kiadássorként is él, az EGY
  kötelezettség: a kifizetést mindig az eredeti TIG-folyamaton vezetjük fel;
- már kifizetett tételt nem írunk felül észrevétlenül; eltérő összegnél /
  részfizetésnél kifejezett megerősítés kell, és részfizetés nem zárja le a
  teljes kötelezettséget;
- tételenként tranzakciósan rögzítünk: részleges hiba esetén pontosan látszik,
  mi sikerült; az újrapróbálás csak a még nem teljesült műveleteket végzi el."""

from __future__ import annotations

import io
import logging
import re
import zipfile
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.bejovo_szamla import BejovoSzamla
from app.models.document_attachment import DocumentAttachment
from app.models.employee import Employee
from app.models.finance import Expense
from app.models.internal_performance_certificate import (
    LEZART_ALLAPOTOK,
    InternalPerformanceCertificate,
    InternalPerformanceCertificateInvoice,
)
from app.models.performance_certificate import PerformanceCertificate, PerformanceCertificateInvoice
from app.models.project_code import ProjectCode
from app.models.utalas_felvezetes import UtalasAdag, UtalasTetel
from app.services import attachments, document_storage, kiadas_kiolvasas, penznem, szamla_erkeztetes

logger = logging.getLogger(__name__)


class UtalasHiba(ValueError):
    """Emberi hibaüzenettel dobott hiba - a végpont 4xx-ként adja vissza."""


# ── ZIP-kibontás (biztonságos) ───────────────────────────────────────────────

MAX_FAJL_DARAB = 200
MAX_OSSZMERET = 300 * 1024 * 1024
MAX_FAJL_MERET = szamla_erkeztetes.MAX_MERET  # 20 MB - egyezik az érkeztetővel
ENGEDETT_KITERJESZTES = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".heic": "image/heic",
}


def _technikai_fajl(nev: str) -> bool:
    """A ZIP technikai bejegyzései (__MACOSX, .DS_Store, rejtett fájlok)."""
    reszek = nev.replace("\\", "/").split("/")
    return any(r == "__MACOSX" or r.startswith("._") or r == ".DS_Store" or (r.startswith(".") and r not in (".", "..")) for r in reszek if r)


def zip_kibontas(zip_adat: bytes) -> tuple[list[tuple[str, str, bytes]], list[dict]]:
    """(útvonal, mime, tartalom) hármasok + a kihagyott fájlok jegyzéke.

    Zip-slip ellen védett: soha nem írunk lemezre, minden bejegyzést memóriába
    olvasunk, az útvonalat csak megjelenítésre őrizzük. Egy sérült bejegyzés
    nem állítja meg a többit."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_adat))
    except zipfile.BadZipFile as exc:
        raise UtalasHiba("A feltöltött fájl nem olvasható ZIP-ként.") from exc

    fajlok: list[tuple[str, str, bytes]] = []
    kihagyott: list[dict] = []
    osszmeret = 0
    for info in zf.infolist():
        if info.is_dir():
            continue
        nev = info.filename
        if _technikai_fajl(nev):
            continue  # a __MACOSX-féle zajt szó nélkül hagyjuk ki
        kiterjesztes = ("." + nev.rsplit(".", 1)[-1].lower()) if "." in nev else ""
        mime = ENGEDETT_KITERJESZTES.get(kiterjesztes)
        if mime is None:
            kihagyott.append({"nev": nev, "ok": f"nem támogatott fájltípus ({kiterjesztes or 'kiterjesztés nélkül'})"})
            continue
        if len(fajlok) >= MAX_FAJL_DARAB:
            kihagyott.append({"nev": nev, "ok": f"a fájlszám-korlát ({MAX_FAJL_DARAB}) betelt"})
            continue
        if info.file_size > MAX_FAJL_MERET:
            kihagyott.append({"nev": nev, "ok": f"túl nagy ({info.file_size / 1024 / 1024:.1f} MB, a határ 20 MB)"})
            continue
        if osszmeret + info.file_size > MAX_OSSZMERET:
            kihagyott.append({"nev": nev, "ok": "a kibontott összméret-korlát (300 MB) betelt"})
            continue
        try:
            adat = zf.read(info)
        except Exception as exc:  # noqa: BLE001 - egy sérült fájl ne állítsa meg a többit
            kihagyott.append({"nev": nev, "ok": f"nem olvasható ({type(exc).__name__})"})
            continue
        if not adat:
            kihagyott.append({"nev": nev, "ok": "üres fájl"})
            continue
        osszmeret += len(adat)
        fajlok.append((nev, mime, adat))
    return fajlok, kihagyott


# ── Adag létrehozása ─────────────────────────────────────────────────────────


def adag_letrehozas(
    db: Session,
    *,
    zip_adat: bytes,
    zip_nev: str | None,
    utalas_datum: date,
    nev: str | None,
    megjegyzes: str | None,
    letrehozo: Employee,
) -> tuple[UtalasAdag, list[tuple[int, str, str, bytes]]]:
    """Az adag + a tétel-sorok létrehozása és a fájlok tartós eltárolása.

    A kiolvasást NEM ez végzi (háttérben fut, lásd adag_feldolgozas) - a
    visszatérés második tagja a (tetel_id, nev, mime, adat) lista a
    háttérszálnak, hogy ne kelljen mindent azonnal visszatölteni az R2-ről."""
    fajlok, kihagyott = zip_kibontas(zip_adat)
    if not fajlok:
        raise UtalasHiba("A ZIP-ben nincs feldolgozható számla (PDF vagy számlafotó).")
    adag = UtalasAdag(
        nev=(nev or "").strip()[:200] or None,
        megjegyzes=(megjegyzes or "").strip() or None,
        utalas_datum=utalas_datum,
        zip_fajl_nev=(zip_nev or "szamlak.zip")[:255],
        allapot="feldolgozas",
        fajl_darab=len(fajlok),
        kihagyott_fajlok=kihagyott or None,
        letrehozo_employee_id=letrehozo.id,
    )
    db.add(adag)
    db.flush()
    hatteradat: list[tuple[int, str, str, bytes]] = []
    for utvonal, mime, adat in fajlok:
        alapnev = utvonal.replace("\\", "/").split("/")[-1]
        tetel = UtalasTetel(
            adag_id=adag.id,
            fajl_nev=alapnev[:255],
            fajl_utvonal=utvonal[:500],
            content_type=mime,
            meret_bajt=len(adat),
            fajl_hash=szamla_erkeztetes._hash(adat),
            allapot="feldolgozas",
        )
        db.add(tetel)
        db.flush()
        kulcs = f"utalas/{adag.id}/{tetel.id}-{re.sub(r'[^A-Za-z0-9._-]+', '_', alapnev)[:80]}"
        tetel.url = document_storage.upload_bytes(adat, kulcs, mime)
        tetel.storage_key = kulcs
        hatteradat.append((tetel.id, alapnev, mime, adat))
    db.commit()
    return adag, hatteradat


# ── Felismerés + párosítás (tételenként) ─────────────────────────────────────


def _atmeneti_bejovo(tetel: UtalasTetel, adag: UtalasAdag) -> BejovoSzamla:
    """ÁTMENETI (adatbázisba NEM kerülő) BejovoSzamla a meglévő kiolvasó- és
    párosító-függvényeknek: azok csak az attribútumokat olvassák és a db-ben
    keresnek, így a javított párosítási logika egy az egyben újrahasznosul."""
    b = BejovoSzamla(forras="utalas", penznem="HUF")
    b.fajl_nev = tetel.fajl_nev
    b.content_type = tetel.content_type
    b.fajl_hash = tetel.fajl_hash
    b.felhasznaloi_utasitas = None
    # Az adag megjegyzése segíthet a kód-felismerésben - ADATKÉNT, nem
    # utasításként kezeljük (csak projektkód-mintát keresünk benne).
    b.email_targy = adag.nev
    b.email_szoveg = adag.megjegyzes
    return b


def _masol_kinyert(tetel: UtalasTetel, b: BejovoSzamla) -> None:
    tetel.kinyert = b.kinyert
    tetel.dokumentum_tipus = b.dokumentum_tipus
    tetel.szamlaszam = b.szamlaszam
    tetel.kibocsato_nev = b.kibocsato_nev
    tetel.kibocsato_adoszam = b.kibocsato_adoszam
    tetel.vevo_nev = b.vevo_nev
    tetel.netto = b.netto
    tetel.brutto = b.brutto
    tetel.penznem = b.penznem
    tetel.kiallitas_datuma = b.kiallitas_datuma
    tetel.teljesites_datuma = b.teljesites_datuma
    tetel.fizetesi_hatarido = b.fizetesi_hatarido


def _adag_duplikatum(db: Session, tetel: UtalasTetel) -> UtalasTetel | None:
    """Ugyanaz a számla ugyanebben VAGY egy másik adagban - fájl-lenyomat,
    majd kibocsátó+számlaszám(+összeg+pénznem) alapján."""
    if tetel.fajl_hash:
        talalat = db.scalar(
            select(UtalasTetel)
            .where(
                UtalasTetel.fajl_hash == tetel.fajl_hash,
                UtalasTetel.id != tetel.id,
                UtalasTetel.allapot.notin_(["nem_feldolgozhato", "duplikatum"]),
            )
            .order_by(UtalasTetel.id)
        )
        if talalat is not None:
            return talalat
    if tetel.szamlaszam and (tetel.kibocsato_adoszam or tetel.kibocsato_nev):
        sajat_ado = szamla_erkeztetes._adoszam_szamjegyei(tetel.kibocsato_adoszam)
        for j in db.scalars(
            select(UtalasTetel)
            .where(
                func.lower(UtalasTetel.szamlaszam) == tetel.szamlaszam.lower(),
                UtalasTetel.id != tetel.id,
                UtalasTetel.allapot.notin_(["nem_feldolgozhato", "duplikatum"]),
            )
            .order_by(UtalasTetel.id)
        ):
            ado_egyezik = sajat_ado and szamla_erkeztetes._adoszam_szamjegyei(j.kibocsato_adoszam) == sajat_ado
            nev_egyezik = (
                bool(tetel.kibocsato_nev)
                and szamla_erkeztetes._norm(j.kibocsato_nev) == szamla_erkeztetes._norm(tetel.kibocsato_nev)
            )
            if not (ado_egyezik or nev_egyezik):
                continue
            if (
                j.netto is not None
                and tetel.netto is not None
                and abs(float(j.netto) - float(tetel.netto)) < 0.01
                and j.penznem == tetel.penznem
            ):
                return j
    return None


def _erkezteto_talalat(db: Session, tetel: UtalasTetel) -> BejovoSzamla | None:
    """Ugyanaz a dokumentum a Beérkező számlákban már JÓVÁHAGYVA - a célja
    készen mutatja, melyik meglévő tételhez tartozik (spec: "már csatolt
    azonos dokumentum" + "azonos számla")."""
    if tetel.fajl_hash:
        b = db.scalar(
            select(BejovoSzamla).where(
                BejovoSzamla.fajl_hash == tetel.fajl_hash,
                BejovoSzamla.allapot == "jovahagyva",
            )
        )
        if b is not None:
            return b
    if tetel.szamlaszam and (tetel.kibocsato_adoszam or tetel.kibocsato_nev):
        sajat_ado = szamla_erkeztetes._adoszam_szamjegyei(tetel.kibocsato_adoszam)
        for b in db.scalars(
            select(BejovoSzamla).where(
                func.lower(BejovoSzamla.szamlaszam) == tetel.szamlaszam.lower(),
                BejovoSzamla.allapot == "jovahagyva",
            )
        ):
            ado_egyezik = sajat_ado and szamla_erkeztetes._adoszam_szamjegyei(b.kibocsato_adoszam) == sajat_ado
            nev_egyezik = (
                bool(tetel.kibocsato_nev)
                and szamla_erkeztetes._norm(b.kibocsato_nev) == szamla_erkeztetes._norm(tetel.kibocsato_nev)
            )
            if (ado_egyezik or nev_egyezik) and (
                b.netto is None
                or tetel.netto is None
                or (abs(float(b.netto) - float(tetel.netto)) < 0.01 and b.penznem == tetel.penznem)
            ):
                return b
    return None


def _cel_fizetesi_allapot(db: Session, tetel: UtalasTetel) -> dict | None:
    """A kiválasztott cél JELENLEGI fizetési állapota - a felület mutatja, és
    a rögzítés előtti szerveroldali újraellenőrzés is ezt nézi."""
    if tetel.cel_tipus == "kiadas" and tetel.cel_expense_id:
        exp = db.get(Expense, tetel.cel_expense_id)
        if exp is None:
            return None
        return {
            "kifizetve": bool(exp.kesz),
            "datum": exp.fizetes_datuma.isoformat() if exp.fizetes_datuma else None,
            "netto": float(exp.netto) if exp.netto is not None else None,
            "cimke": f"Kiadás #{exp.id} – {exp.megnevezes}",
        }
    if tetel.cel_tipus == "kulsos_tig" and tetel.cel_certificate_id:
        cert = db.get(PerformanceCertificate, tetel.cel_certificate_id)
        if cert is None:
            return None
        return {
            "kifizetve": bool(cert.szamla_kifizetve),
            "datum": cert.utalas_datuma.isoformat() if cert.utalas_datuma else None,
            "netto": float(cert.netto_osszeg) if cert.netto_osszeg is not None else None,
            "cimke": f"Külsős TIG #{cert.id}",
        }
    if tetel.cel_tipus == "belsos_tig" and tetel.cel_internal_certificate_id:
        cert = db.get(InternalPerformanceCertificate, tetel.cel_internal_certificate_id)
        if cert is None:
            return None
        return {
            "kifizetve": bool(cert.szamla_kifizetve),
            "datum": cert.utalas_datuma.isoformat() if cert.utalas_datuma else None,
            "netto": float(cert.netto_osszeg) if cert.netto_osszeg is not None else None,
            "cimke": f"Belsős TIG {cert.ev}.{cert.honap:02d}",
        }
    return None


def allapot_ujraertekeles(db: Session, tetel: UtalasTetel) -> None:
    """A tétel állapotának megállapítása a cél és annak fizetési állapota
    alapján - a kézi cél-választás / mező-módosítás után is ez fut."""
    if tetel.allapot in ("rogzitve", "nem_feldolgozhato", "duplikatum"):
        return
    if tetel.cel_tipus == "uj_kiadas":
        tetel.allapot = "nincs_talalat"
        return
    if tetel.cel_tipus is None:
        alternativak = (tetel.javaslat or {}).get("alternativak") or []
        tetel.allapot = "valasztas" if alternativak else "nincs_talalat"
        return
    cel = _cel_fizetesi_allapot(db, tetel)
    if cel is None:
        tetel.allapot = "valasztas"
        tetel.hiba_uzenet = "A kiválasztott célrekord nem található - válassz újat."
        return
    if cel["kifizetve"]:
        tetel.allapot = "mar_kifizetve"
        return
    if (
        cel["netto"] is not None
        and tetel.netto is not None
        and abs(cel["netto"] - float(tetel.netto)) >= 1
        and not tetel.osszeg_elteres_elfogadva
    ):
        tetel.allapot = "osszeg_elter"
        return
    tetel.allapot = "rogzitheto"


def tetel_feldolgozas(db: Session, tetel: UtalasTetel, adat: bytes | None = None) -> None:
    """Egy tétel felismerése + párosítása. A hívó commitol. Hibánál a tétel
    'nem_feldolgozhato' lesz, a többi tételt nem érinti."""
    adag = tetel.adag
    try:
        if adat is None and tetel.storage_key:
            adat = document_storage.download_bytes(tetel.storage_key)
        if adat is None:
            raise UtalasHiba("A tétel fájlja nem érhető el.")

        kinyert = kiadas_kiolvasas.szamla_olvasd_ki(adat, tetel.content_type or "application/pdf")
        b = _atmeneti_bejovo(tetel, adag)
        szamla_erkeztetes._kinyert_mentese(b, kinyert)
        _masol_kinyert(tetel, b)

        figyelmeztetesek: list[str] = list(((b.kinyert or {}).get("osszeg_figyelmeztetesek")) or [])

        if b.irany == "kimeno":
            tetel.allapot = "nem_feldolgozhato"
            tetel.hiba_uzenet = "A számlát a saját cégünk állította ki (kimenő számla) - kifizetésként nem vezethető fel."
            return
        if tetel.dokumentum_tipus == "dijbekero":
            figyelmeztetesek.append("Díjbekérő (proforma) - ellenőrizd, hogy a végleges számla is megvan-e.")

        # 1) Duplikátum ezen a felületen (ugyanez vagy másik adag).
        dup = _adag_duplikatum(db, tetel)
        if dup is not None:
            tetel.duplikatum_tetel_id = dup.id
            if dup.allapot == "rogzitve":
                tetel.allapot = "mar_kifizetve"
                tetel.hiba_uzenet = (
                    f"Ugyanez a számla a(z) #{dup.adag_id} adagban már felvezetésre került (tétel #{dup.id})."
                )
            else:
                tetel.allapot = "duplikatum"
                tetel.hiba_uzenet = f"Ugyanez a számla már szerepel (tétel #{dup.id}, adag #{dup.adag_id})."
            return

        # 2) Már ismert dokumentum a Beérkező számlákból: a jóváhagyott cél
        # közvetlenül megmondja, melyik meglévő tételhez tartozik.
        ismert = _erkezteto_talalat(db, tetel)
        if ismert is not None:
            if ismert.cel_certificate_id:
                tetel.cel_tipus = "kulsos_tig"
                tetel.cel_certificate_id = ismert.cel_certificate_id
            elif ismert.cel_internal_certificate_id:
                tetel.cel_tipus = "belsos_tig"
                tetel.cel_internal_certificate_id = ismert.cel_internal_certificate_id
            elif ismert.rogzitett_expense_id or ismert.cel_expense_id:
                tetel.cel_tipus = "kiadas"
                tetel.cel_expense_id = ismert.rogzitett_expense_id or ismert.cel_expense_id
            if tetel.cel_tipus:
                tetel.elszamolas = "hype"
                tetel.javaslat = {
                    "indoklas": (
                        f"A dokumentum már ismert (Beérkező számlák #{ismert.id}, jóváhagyva) - "
                        "a számla ahhoz a tételhez tartozik, ahová ott csatolták."
                    ),
                    "alternativak": [],
                    "figyelmeztetesek": figyelmeztetesek,
                    "mar_csatolva": True,
                }
                _tig_kiadas_atiranyitas(db, tetel)
                allapot_ujraertekeles(db, tetel)
                return

        # 3) A meglévő (javított) párosító: kód-először, fél-egyezés,
        # partner+összeg többes találatnál sosem dönt.
        szamla_erkeztetes.javasol(db, b)
        javaslat = dict(b.javaslat or {})
        javaslat["figyelmeztetesek"] = list(javaslat.get("figyelmeztetesek") or []) + figyelmeztetesek
        # Az alternatívák cel-azonosítói átvihetők, az ORM-objektumok nem.
        javaslat["alternativak"] = [
            {k: v for k, v in a.items() if k != "cert"} for a in (javaslat.get("alternativak") or [])
        ]
        tetel.javaslat = javaslat

        if b.cel_tipus == "kulsos_tig" and b.cel_certificate_id:
            tetel.cel_tipus = "kulsos_tig"
            tetel.cel_certificate_id = b.cel_certificate_id
            tetel.elszamolas = "hype"
        elif b.cel_tipus == "belsos_tig" and b.cel_internal_certificate_id:
            tetel.cel_tipus = "belsos_tig"
            tetel.cel_internal_certificate_id = b.cel_internal_certificate_id
            tetel.elszamolas = "hype"
        elif b.cel_tipus == "kiadas_csatolas" and b.cel_expense_id:
            tetel.cel_tipus = "kiadas"
            tetel.cel_expense_id = b.cel_expense_id
            tetel.elszamolas = "hype"
        elif b.cel_tipus in ("kiadas_uj", "mukodesi", "auto"):
            # Nincs meglévő tétel: ÚJ kiadást csak külön jóváhagyással készítünk
            # elő - automatikusan semmi nem jön létre.
            tetel.cel_tipus = "uj_kiadas"
            tetel.uj_kiadas = {
                "project_code_id": b.cel_project_code_id,
                "employee_id": b.cel_employee_id,
                "auto_id": b.cel_auto_id if b.cel_tipus == "auto" else None,
                "mukodesi": b.cel_tipus == "mukodesi",
            }
            tetel.elszamolas = "tisztazando"
        else:
            tetel.cel_tipus = None
            tetel.elszamolas = "tisztazando"

        _tig_kiadas_atiranyitas(db, tetel)
        allapot_ujraertekeles(db, tetel)
    except (UtalasHiba, szamla_erkeztetes.ErkeztetesHiba, ValueError) as exc:
        tetel.allapot = "nem_feldolgozhato"
        tetel.hiba_uzenet = str(exc)
    except Exception as exc:  # noqa: BLE001 - egy hibás fájl ne állítsa meg az adagot
        logger.exception("Utalás-felvezetés: tétel-feldolgozási hiba (#%s)", tetel.id)
        tetel.allapot = "nem_feldolgozhato"
        tetel.hiba_uzenet = f"{type(exc).__name__}: {exc}"


def _tig_kiadas_atiranyitas(db: Session, tetel: UtalasTetel) -> None:
    """Ha a kiválasztott kiadás egy TIG-ből származik (cert.expense_id köti),
    a kifizetést az EREDETI TIG-folyamaton vezetjük fel - a kettő EGY üzleti
    kötelezettség, nem két kifizetendő tétel."""
    if tetel.cel_tipus != "kiadas" or not tetel.cel_expense_id:
        return
    cert = db.scalar(
        select(PerformanceCertificate).where(PerformanceCertificate.expense_id == tetel.cel_expense_id)
    )
    if cert is not None:
        tetel.cel_tipus = "kulsos_tig"
        tetel.cel_certificate_id = cert.id
        tetel.cel_expense_id = None
        javaslat = dict(tetel.javaslat or {})
        javaslat.setdefault("figyelmeztetesek", []).append(
            f"A megtalált kiadássor a #{cert.id} TIG-ből származik - a kifizetés az eredeti TIG-re kerül, "
            "hogy az Utókövetés, a TIG és a Pénzügyek együtt frissüljön (nem lesz dupla költség)."
        )
        tetel.javaslat = javaslat
        return
    belso = db.scalar(
        select(InternalPerformanceCertificate).where(
            InternalPerformanceCertificate.expense_id == tetel.cel_expense_id
        )
    )
    if belso is not None:
        tetel.cel_tipus = "belsos_tig"
        tetel.cel_internal_certificate_id = belso.id
        tetel.cel_expense_id = None


def adag_feldolgozas(adag_id: int, hatteradat: list[tuple[int, str, str, bytes]], naplo=lambda s: None) -> None:
    """A teljes adag felismerése - háttérszálban fut, SAJÁT session-nel,
    tételenként külön committal (megszakadásnál az addig kész tételek
    megmaradnak, az újraindítás csak a maradékot dolgozza fel)."""
    from app.core.database import SessionLocal

    adatok = {tid: adat for tid, _nev, _mime, adat in hatteradat}
    db = SessionLocal()
    try:
        tetel_idk = db.scalars(
            select(UtalasTetel.id).where(UtalasTetel.adag_id == adag_id, UtalasTetel.allapot == "feldolgozas")
        ).all()
        for i, tid in enumerate(tetel_idk, start=1):
            tetel = db.get(UtalasTetel, tid)
            if tetel is None or tetel.allapot != "feldolgozas":
                continue
            naplo(f"[{i}/{len(tetel_idk)}] {tetel.fajl_nev}")
            tetel_feldolgozas(db, tetel, adatok.get(tid))
            db.commit()
        adag = db.get(UtalasAdag, adag_id)
        if adag is not None:
            adag.allapot = "ellenorzes"
            db.commit()
        naplo("Kész - az adag ellenőrizhető.")
    except Exception as exc:  # noqa: BLE001 - a hiba az adagon látszódjon
        logger.exception("Utalás-adag feldolgozási hiba (#%s)", adag_id)
        db.rollback()
        adag = db.get(UtalasAdag, adag_id)
        if adag is not None:
            adag.allapot = "hiba"
            adag.hiba_uzenet = f"{type(exc).__name__}: {exc}"
            db.commit()
    finally:
        db.close()


# ── Kifizetés rögzítése (tételenként, tranzakciósan) ────────────────────────


def _szamla_mar_csatolva(db: Session, tetel: UtalasTetel, entity_type: str, entity_id: int) -> bool:
    """Van-e már számla-csatolmány a célon - kétszer nem csatoljuk ugyanazt."""
    return (
        db.scalar(
            select(DocumentAttachment.id).where(
                DocumentAttachment.entity_type == entity_type,
                DocumentAttachment.entity_id == entity_id,
                DocumentAttachment.kategoria == "szamla",
            )
        )
        is not None
    )


def _fajl_letoltes(tetel: UtalasTetel) -> bytes | None:
    if not tetel.storage_key:
        return None
    try:
        return document_storage.download_bytes(tetel.storage_key)
    except Exception:  # noqa: BLE001 - a csatolás elhagyható, a kifizetés-rögzítés nem
        logger.warning("Utalás: a tétel fájlja nem tölthető le (#%s)", tetel.id)
        return None


def tetel_rogzites(db: Session, tetel: UtalasTetel, user: Employee) -> dict:
    """EGY tétel kifizetésének végleges felvezetése. A hívó sorzárral olvasta
    a tételt és tételenként commitol.

    Szerveroldali újraellenőrzés (a felület állapota elavulhatott):
    - a célrekord létezik és NEM kifizetett (különben nem írunk felül semmit);
    - az összeg-eltérés csak kifejezett elfogadással mehet át;
    - a Krumpellóhoz sorolt tételhez itt semmi nem rögzíthető."""
    if tetel.allapot == "rogzitve":
        return {**(tetel.rogzites_naplo or {}), "mar_rogzitve": True}
    if tetel.elszamolas == "krumpello":
        raise UtalasHiba(
            "Ez a tétel a Krumpellóhoz van sorolva - ott egyelőre csak listázzuk, a felvezetése később készül el."
        )
    if tetel.elszamolas != "hype":
        raise UtalasHiba("Előbb válaszd ki az elszámolási helyet (HYPE / Krumpello).")
    if tetel.allapot in ("nem_feldolgozhato", "duplikatum"):
        raise UtalasHiba(f"Ebből az állapotból nem rögzíthető: {tetel.allapot}.")

    datum = tetel.utalas_datum or tetel.adag.utalas_datum
    naplo: dict = {
        "datum": datum.isoformat(),
        "cel_tipus": tetel.cel_tipus,
        "elozo_ertekek": {},
        "letrejott": [],
        "csatolt": [],
        "megjegyzesek": [],
    }

    # A TIG-ből származó kiadássor mindig az eredeti TIG-re megy át.
    _tig_kiadas_atiranyitas(db, tetel)

    if tetel.cel_tipus == "kiadas":
        _rogzit_kiadasra(db, tetel, datum, naplo)
    elif tetel.cel_tipus == "kulsos_tig":
        _rogzit_kulsos_tigre(db, tetel, datum, naplo)
    elif tetel.cel_tipus == "belsos_tig":
        _rogzit_belsos_tigre(db, tetel, datum, naplo)
    elif tetel.cel_tipus == "uj_kiadas":
        _rogzit_uj_kiadaskent(db, tetel, datum, naplo, user)
    else:
        raise UtalasHiba("Nincs kiválasztott cél - válaszd ki, melyik tételhez tartozik a számla.")

    tetel.allapot = "rogzitve"
    tetel.rogzitve_at = datetime.now(timezone.utc)
    tetel.rogzito_employee_id = user.id
    tetel.rogzites_naplo = naplo
    tetel.visszavonva_at = None
    tetel.visszavono_employee_id = None
    return naplo


def _osszeg_ellenorzes(tetel: UtalasTetel, cel_netto, cel_nev: str) -> None:
    if (
        cel_netto is not None
        and tetel.netto is not None
        and abs(float(cel_netto) - float(tetel.netto)) >= 1
        and not tetel.osszeg_elteres_elfogadva
    ):
        tetel.allapot = "osszeg_elter"
        raise UtalasHiba(
            f"A számla nettója ({float(tetel.netto):,.0f}) eltér a {cel_nev} összegétől "
            f"({float(cel_netto):,.0f}) - részfizetés/eltérés csak kifejezett elfogadással rögzíthető.".replace(
                ",", " "
            )
        )


def _rogzit_kiadasra(db: Session, tetel: UtalasTetel, datum: date, naplo: dict) -> None:
    # Sorzár a CÉLON is: párhuzamos jóváhagyás (két adag ugyanarra a
    # kiadásra) ne fusson át egyszerre a "még nincs kifizetve" ellenőrzésen.
    exp = db.get(Expense, tetel.cel_expense_id or 0, with_for_update=True)
    if exp is None:
        tetel.allapot = "valasztas"
        raise UtalasHiba("A kiválasztott kiadás már nem található - válassz újat.")
    if exp.kesz:
        # Már kifizetett: azonos dátumnál csendben "kész"-nek vesszük (nincs
        # újabb módosítás), eltérésnél nem írunk felül semmit.
        if exp.fizetes_datuma == datum:
            naplo["megjegyzesek"].append(
                f"A kiadás (#{exp.id}) már pontosan ezzel a dátummal kifizetett volt - nem módosítottunk semmit."
            )
            naplo["mar_igy_volt"] = True
            return
        tetel.allapot = "mar_kifizetve"
        raise UtalasHiba(
            f"A kiadás (#{exp.id}) már kifizetett, a felvezetett dátuma: {exp.fizetes_datuma or 'nincs'} - "
            "a korábbi fizetési adatot nem írjuk felül. Ellenőrizd, melyik az igaz."
        )
    _osszeg_ellenorzes(tetel, exp.netto, "kiadás")
    naplo["elozo_ertekek"]["expense"] = {
        "id": exp.id,
        "kesz": exp.kesz,
        "fizetes_datuma": exp.fizetes_datuma.isoformat() if exp.fizetes_datuma else None,
        "kifizetes_modja": exp.kifizetes_modja,
        "kiadas_datuma": exp.kiadas_datuma.isoformat() if exp.kiadas_datuma else None,
    }
    exp.kesz = True
    exp.fizetes_datuma = datum
    if not exp.kifizetes_modja:
        exp.kifizetes_modja = "Átutalás"
    if exp.kiadas_datuma is None:
        exp.kiadas_datuma = datum
    if not _szamla_mar_csatolva(db, tetel, "expense", exp.id):
        _csatolas(db, tetel, "expense", exp.id, naplo)
    else:
        naplo["megjegyzesek"].append("A kiadáson már van számla-csatolmány - nem csatoltunk másodikat.")


def _rogzit_kulsos_tigre(db: Session, tetel: UtalasTetel, datum: date, naplo: dict) -> None:
    cert = db.get(PerformanceCertificate, tetel.cel_certificate_id or 0, with_for_update=True)
    if cert is None:
        tetel.allapot = "valasztas"
        raise UtalasHiba("A kiválasztott külsős TIG már nem található - válassz újat.")
    if cert.szamla_kifizetve:
        if cert.utalas_datuma == datum:
            naplo["megjegyzesek"].append(f"A TIG (#{cert.id}) már ezzel a dátummal kifizetett volt - nem módosítottunk.")
            naplo["mar_igy_volt"] = True
            return
        tetel.allapot = "mar_kifizetve"
        raise UtalasHiba(
            f"A TIG (#{cert.id}) már kifizetettként van jelölve (utalás: {cert.utalas_datuma or 'nincs dátum'}) - "
            "nem írjuk felül. Ellenőrizd, melyik dátum az igaz."
        )
    _osszeg_ellenorzes(tetel, cert.netto_osszeg, "TIG")

    naplo["elozo_ertekek"]["performanceCertificate"] = {
        "id": cert.id,
        "szamla_kifizetve": cert.szamla_kifizetve,
        "utalas_datuma": cert.utalas_datuma.isoformat() if cert.utalas_datuma else None,
        "expense_id": cert.expense_id,
    }

    # Számla-sor a TIG-re, ha ez a dokumentum még nincs rajta.
    fajl = _fajl_letoltes(tetel)
    if fajl is not None and not cert.invoices:
        sor = PerformanceCertificateInvoice(
            certificate_id=cert.id,
            filename=tetel.fajl_nev or "szamla.pdf",
            storage_key="",
            url="",
            content_type=tetel.content_type,
        )
        db.add(sor)
        db.flush()
        kulcs = f"tig-szamla/{cert.id}/{sor.id}-{re.sub(r'[^A-Za-z0-9._-]+', '_', sor.filename)[:80]}"
        sor.url = document_storage.upload_bytes(fajl, kulcs, tetel.content_type or "application/pdf")
        sor.storage_key = kulcs
        naplo["csatolt"].append({"tipus": "performanceCertificate", "id": cert.id, "szamla_sor": sor.id})
    elif cert.invoices:
        naplo["megjegyzesek"].append("A TIG-en már van számla - nem töltöttünk fel másodikat.")

    # A kifizetés felvezetése - UGYANAZ a művelet, mint az Utókövetés
    # "Kifizetve" gombja (lásd routes/performance_certificates.mark_szamla_kifizetve):
    # a TIG kifizetett lesz, és a Pénzügyben létrejön/frissül a kiadás-sora.
    cert.utalas_datuma = datum
    brutto = (
        round(float(cert.netto_osszeg) * 1.27, 2) if (cert.plusz_afa and cert.netto_osszeg) else cert.netto_osszeg
    )
    expense = db.get(Expense, cert.expense_id) if cert.expense_id is not None else None
    if expense is None:
        from app.models.project import Project

        project = db.get(Project, cert.project_id) if cert.project_id is not None else None
        erintett_kodok = [
            t.project.projektkod_szoveg for t in cert.tetelek if t.project is not None and t.project.projektkod_szoveg
        ]
        kodok_szoveg = ", ".join(dict.fromkeys(erintett_kodok)) or (
            (project.projektkod_szoveg or project.nev) if project is not None else ""
        )
        pc_id = project.project_code_id if project is not None else cert.project_code_id
        expense = Expense(
            megnevezes=f"TIG - {cert.ceg_neve or ''} - {kodok_szoveg or ''}".strip(" -"),
            project_code_id=pc_id,
            employee_id=cert.employee_id,
            tipus="kulsos",
            netto=cert.netto_osszeg,
            brutto=brutto,
            hozzaadas_a_kiadasokhoz=True,
        )
        db.add(expense)
        db.flush()
        cert.expense_id = expense.id
        naplo["letrejott"].append({"tipus": "expense", "id": expense.id})
    else:
        naplo["elozo_ertekek"]["expense"] = {
            "id": expense.id,
            "kesz": expense.kesz,
            "fizetes_datuma": expense.fizetes_datuma.isoformat() if expense.fizetes_datuma else None,
            "kifizetes_modja": expense.kifizetes_modja,
        }
    expense.kesz = True
    expense.fizetes_datuma = datum
    if not expense.kifizetes_modja:
        expense.kifizetes_modja = "Átutalás"
    if expense.kiadas_datuma is None:
        expense.kiadas_datuma = datum
    if expense.fizetes_hatarideje is None and cert.fizetesi_hatarido is not None:
        expense.fizetes_hatarideje = cert.fizetesi_hatarido
    cert.szamla_kifizetve = True


def _rogzit_belsos_tigre(db: Session, tetel: UtalasTetel, datum: date, naplo: dict) -> None:
    cert = db.get(InternalPerformanceCertificate, tetel.cel_internal_certificate_id or 0, with_for_update=True)
    if cert is None:
        tetel.allapot = "valasztas"
        raise UtalasHiba("A kiválasztott belsős TIG már nem található - válassz újat.")
    if cert.szamla_kifizetve:
        if cert.utalas_datuma == datum:
            naplo["megjegyzesek"].append(
                f"A belsős TIG ({cert.ev}.{cert.honap:02d}) már ezzel a dátummal kifizetett volt - nem módosítottunk."
            )
            naplo["mar_igy_volt"] = True
            return
        tetel.allapot = "mar_kifizetve"
        raise UtalasHiba(
            f"A belsős TIG ({cert.ev}.{cert.honap:02d}) már kifizetett (utalás: {cert.utalas_datuma or 'nincs'}) - "
            "nem írjuk felül."
        )
    from app.services import belsos_idoszak as belsos_idoszak_szolgaltatas

    alkalmazott = not belsos_idoszak_szolgaltatas.kell_havi_tig(cert.employee, cert.ev, cert.honap)
    if not alkalmazott and cert.allapot not in LEZART_ALLAPOTOK:
        raise UtalasHiba("A belsős TIG még nincs véglegesítve/kiküldve - előbb azt zárd le.")
    _osszeg_ellenorzes(tetel, cert.netto_osszeg, "belsős TIG")

    naplo["elozo_ertekek"]["internalPerformanceCertificate"] = {
        "id": cert.id,
        "szamla_kifizetve": cert.szamla_kifizetve,
        "utalas_datuma": cert.utalas_datuma.isoformat() if cert.utalas_datuma else None,
        "expense_id": cert.expense_id,
    }
    fajl = _fajl_letoltes(tetel)
    if fajl is not None and not cert.invoices:
        sor = InternalPerformanceCertificateInvoice(
            certificate_id=cert.id,
            filename=tetel.fajl_nev or "szamla.pdf",
            storage_key="",
            url="",
            content_type=tetel.content_type,
        )
        db.add(sor)
        db.flush()
        kulcs = f"belsos-tig-szamla/{cert.employee_id}/{cert.ev}-{cert.honap:02d}-{sor.id}"
        sor.url = document_storage.upload_bytes(fajl, kulcs, tetel.content_type or "application/pdf")
        sor.storage_key = kulcs
        naplo["csatolt"].append({"tipus": "internalPerformanceCertificate", "id": cert.id, "szamla_sor": sor.id})

    cert.utalas_datuma = datum
    brutto = (
        round(float(cert.netto_osszeg) * 1.27, 2) if (cert.plusz_afa and cert.netto_osszeg) else cert.netto_osszeg
    )
    expense = db.get(Expense, cert.expense_id) if cert.expense_id is not None else None
    if expense is None:
        from app.services.hu_datum import belsos_tig_honapja, ev_honap_szoveg

        expense = Expense(
            megnevezes=(
                f"{'Belsős fizetés' if alkalmazott else 'Belsős TIG'} - {cert.employee.full_name} - "
                f"{ev_honap_szoveg(*belsos_tig_honapja(cert.ev, cert.honap, cert.teljesites_datuma, cert.fizetesi_hatarido, cert.utalas_datuma))}"
            ),
            employee_id=cert.employee_id,
            tipus="belsos",
            netto=cert.netto_osszeg,
            brutto=brutto,
            hozzaadas_a_kiadasokhoz=True,
        )
        db.add(expense)
        db.flush()
        cert.expense_id = expense.id
        naplo["letrejott"].append({"tipus": "expense", "id": expense.id})
    else:
        naplo["elozo_ertekek"]["expense"] = {
            "id": expense.id,
            "kesz": expense.kesz,
            "fizetes_datuma": expense.fizetes_datuma.isoformat() if expense.fizetes_datuma else None,
            "kifizetes_modja": expense.kifizetes_modja,
        }
    expense.kesz = True
    expense.fizetes_datuma = datum
    if not expense.kifizetes_modja:
        expense.kifizetes_modja = "Átutalás"
    if expense.fizetes_hatarideje is None and cert.fizetesi_hatarido is not None:
        expense.fizetes_hatarideje = cert.fizetesi_hatarido
    cert.szamla_kifizetve = True


def _rogzit_uj_kiadaskent(db: Session, tetel: UtalasTetel, datum: date, naplo: dict, user: Employee) -> None:
    """ÚJ kiadás létrehozása + számla csatolása + kifizetés felvezetése EGY
    következetes műveletként - kizárólag emberi jóváhagyással jutunk ide."""
    adatok = dict(tetel.uj_kiadas or {})
    netto = float(tetel.netto) if tetel.netto is not None else None
    if netto is None:
        raise UtalasHiba("Hiányzik a nettó összeg - add meg a tételen (nem találunk ki értéket).")
    arfolyam = adatok.get("arfolyam")
    huf_netto = netto
    huf_brutto = float(tetel.brutto) if tetel.brutto is not None else None
    eredeti_penznem = None
    if penznem.devizas(tetel.penznem):
        if not arfolyam:
            raise UtalasHiba(
                f"A számla {tetel.penznem}-ben szól - add meg az árfolyamot a tételen, önkényes árfolyamot nem használunk."
            )
        eredeti_penznem = tetel.penznem
        huf_netto = penznem.forintra(netto, float(arfolyam)) or 0
        huf_brutto = penznem.forintra(huf_brutto, float(arfolyam)) if huf_brutto is not None else None
    pc_id = adatok.get("project_code_id")
    if pc_id is not None and db.get(ProjectCode, pc_id) is None:
        raise UtalasHiba(f"A megadott projektkód (#{pc_id}) nem található.")
    exp = Expense(
        megnevezes=(tetel.kibocsato_nev or "Ismeretlen partner")[:255],
        kiadas_leiras=(adatok.get("kiadas_leiras") or f"Utalás-felvezetés: {tetel.szamlaszam or tetel.fajl_nev or ''}")[
            :500
        ],
        netto=huf_netto,
        brutto=huf_brutto if huf_brutto is not None else huf_netto,
        penznem="HUF",
        eredeti_penznem=eredeti_penznem,
        eredeti_netto=netto if eredeti_penznem else None,
        eredeti_brutto=float(tetel.brutto) if (eredeti_penznem and tetel.brutto is not None) else None,
        arfolyam=float(arfolyam) if arfolyam else None,
        kiadas_datuma=tetel.teljesites_datuma or tetel.kiallitas_datuma or datum,
        fizetes_hatarideje=tetel.fizetesi_hatarido,
        project_code_id=None if adatok.get("mukodesi") else pc_id,
        employee_id=adatok.get("employee_id"),
        auto_id=adatok.get("auto_id"),
        tipus=adatok.get("tipus") or ("kulsos" if adatok.get("employee_id") else "egyeb"),
        kifizetes_modja="Átutalás",
        kesz=True,
        fizetes_datuma=datum,
    )
    db.add(exp)
    db.flush()
    naplo["letrejott"].append({"tipus": "expense", "id": exp.id, "netto": huf_netto})
    tetel.cel_expense_id = exp.id
    _csatolas(db, tetel, "expense", exp.id, naplo)


def _csatolas(db: Session, tetel: UtalasTetel, entity_type: str, entity_id: int, naplo: dict) -> None:
    fajl = _fajl_letoltes(tetel)
    if fajl is None:
        naplo["megjegyzesek"].append("A tétel fájlja nem érhető el - csatolmány nem készült.")
        return
    rekord = attachments.save(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        kategoria="szamla",
        filename=tetel.fajl_nev or "szamla.pdf",
        data=fajl,
        content_type=tetel.content_type,
    )
    if tetel.fizetesi_hatarido and rekord.fizetesi_hatarido is None:
        rekord.fizetesi_hatarido = tetel.fizetesi_hatarido
    naplo["csatolt"].append({"tipus": f"attachment:{entity_type}", "id": rekord.id})


# ── Visszavonás (naplózott, csak a saját változásokat állítja vissza) ───────


def tetel_visszavonas(db: Session, tetel: UtalasTetel, user: Employee) -> dict:
    """A felvezetés ADMINISZTRÁCIÓJÁNAK visszavonása (a banki utalást nem
    érinti). KIZÁRÓLAG a rögzítési napló tételeiből dolgozik, és csak azt
    állítja vissza, ami még a felvezetéskor beírt értéken áll - a későbbi kézi
    módosításokat nem írja felül (azok kivételként a jegyzékbe kerülnek)."""
    if tetel.allapot != "rogzitve" or not tetel.rogzites_naplo:
        raise UtalasHiba("Ez a tétel nincs felvezetve - nincs mit visszavonni.")
    naplo = tetel.rogzites_naplo
    datum = date.fromisoformat(naplo["datum"])
    eredmeny: dict = {"visszaallitott": [], "torolt": [], "kivetel": []}

    # 1) A létrehozott rekordok törlése (csak ha érintetlenek).
    for t in naplo.get("letrejott") or []:
        if t.get("tipus") != "expense":
            continue
        exp = db.get(Expense, t.get("id"))
        if exp is None:
            continue
        cert_hiv = db.scalar(select(PerformanceCertificate.id).where(PerformanceCertificate.expense_id == exp.id))
        belso_hiv = db.scalar(
            select(InternalPerformanceCertificate.id).where(InternalPerformanceCertificate.expense_id == exp.id)
        )
        if cert_hiv or belso_hiv:
            # A TIG-hez kötött kiadás-sort nem töröljük: a TIG "kifizetve"
            # állapotát vonjuk vissza lentebb, a sora nyitottra áll.
            if exp.fizetes_datuma == datum:
                exp.kesz = False
                exp.fizetes_datuma = None
                eredmeny["visszaallitott"].append({"tipus": "expense", "id": exp.id, "mezo": "kifizetes"})
            else:
                eredmeny["kivetel"].append({"tipus": "expense", "id": exp.id, "ok": "a fizetési adatot azóta kézzel módosították"})
            continue
        if exp.fizetes_datuma != datum:
            eredmeny["kivetel"].append({"tipus": "expense", "id": exp.id, "ok": "a fizetési adatot azóta kézzel módosították"})
            continue
        for att in db.scalars(
            select(DocumentAttachment).where(
                DocumentAttachment.entity_type == "expense", DocumentAttachment.entity_id == exp.id
            )
        ):
            try:
                document_storage.delete_object(att.storage_key)
            except Exception:  # noqa: BLE001
                pass
            db.delete(att)
        db.delete(exp)
        eredmeny["torolt"].append({"tipus": "expense", "id": t.get("id")})

    # 2) A csatolt fájlok / TIG-számla sorok eltávolítása.
    for cs in naplo.get("csatolt") or []:
        t = cs.get("tipus") or ""
        if t.startswith("attachment:"):
            att = db.get(DocumentAttachment, cs.get("id"))
            if att is not None:
                try:
                    document_storage.delete_object(att.storage_key)
                except Exception:  # noqa: BLE001
                    pass
                db.delete(att)
                eredmeny["torolt"].append({"tipus": t, "id": cs.get("id")})
        elif t == "performanceCertificate" and cs.get("szamla_sor"):
            sor = db.get(PerformanceCertificateInvoice, cs["szamla_sor"])
            if sor is not None:
                try:
                    document_storage.delete_object(sor.storage_key)
                except Exception:  # noqa: BLE001
                    pass
                db.delete(sor)
                eredmeny["torolt"].append({"tipus": "tig_szamla_sor", "id": cs["szamla_sor"]})
        elif t == "internalPerformanceCertificate" and cs.get("szamla_sor"):
            sor = db.get(InternalPerformanceCertificateInvoice, cs["szamla_sor"])
            if sor is not None:
                try:
                    document_storage.delete_object(sor.storage_key)
                except Exception:  # noqa: BLE001
                    pass
                db.delete(sor)
                eredmeny["torolt"].append({"tipus": "belsos_tig_szamla_sor", "id": cs["szamla_sor"]})

    # 3) Az előző értékek visszaállítása - csak ha a mező még a felvezetéskor
    # beírt értéken áll (bizonyítható eredet, a kézi módosítás nem sérül).
    elozo = naplo.get("elozo_ertekek") or {}
    if "expense" in elozo:
        e = elozo["expense"]
        exp = db.get(Expense, e.get("id"))
        if exp is not None:
            if exp.kesz and exp.fizetes_datuma == datum:
                exp.kesz = bool(e.get("kesz"))
                exp.fizetes_datuma = date.fromisoformat(e["fizetes_datuma"]) if e.get("fizetes_datuma") else None
                exp.kifizetes_modja = e.get("kifizetes_modja")
                if "kiadas_datuma" in e:
                    exp.kiadas_datuma = date.fromisoformat(e["kiadas_datuma"]) if e.get("kiadas_datuma") else None
                eredmeny["visszaallitott"].append({"tipus": "expense", "id": exp.id})
            else:
                eredmeny["kivetel"].append(
                    {"tipus": "expense", "id": exp.id, "ok": "a fizetési adatot azóta kézzel módosították"}
                )
    if "performanceCertificate" in elozo:
        c = elozo["performanceCertificate"]
        cert = db.get(PerformanceCertificate, c.get("id"))
        if cert is not None:
            if cert.szamla_kifizetve and cert.utalas_datuma == datum:
                cert.szamla_kifizetve = bool(c.get("szamla_kifizetve"))
                cert.utalas_datuma = date.fromisoformat(c["utalas_datuma"]) if c.get("utalas_datuma") else None
                if c.get("expense_id") is None and not naplo.get("letrejott"):
                    cert.expense_id = None
                eredmeny["visszaallitott"].append({"tipus": "performanceCertificate", "id": cert.id})
            else:
                eredmeny["kivetel"].append(
                    {"tipus": "performanceCertificate", "id": cert.id, "ok": "az állapotot azóta kézzel módosították"}
                )
            if c.get("expense_id") is None and cert.expense_id is not None and not db.get(
                Expense, cert.expense_id
            ):
                cert.expense_id = None
    if "internalPerformanceCertificate" in elozo:
        c = elozo["internalPerformanceCertificate"]
        cert = db.get(InternalPerformanceCertificate, c.get("id"))
        if cert is not None:
            if cert.szamla_kifizetve and cert.utalas_datuma == datum:
                cert.szamla_kifizetve = bool(c.get("szamla_kifizetve"))
                cert.utalas_datuma = date.fromisoformat(c["utalas_datuma"]) if c.get("utalas_datuma") else None
                eredmeny["visszaallitott"].append({"tipus": "internalPerformanceCertificate", "id": cert.id})
            else:
                eredmeny["kivetel"].append(
                    {"tipus": "internalPerformanceCertificate", "id": cert.id, "ok": "az állapotot azóta kézzel módosították"}
                )
            if c.get("expense_id") is None and cert.expense_id is not None and not db.get(Expense, cert.expense_id):
                cert.expense_id = None

    tetel.visszavonva_at = datetime.now(timezone.utc)
    tetel.visszavono_employee_id = user.id
    tetel.rogzitve_at = None
    tetel.rogzito_employee_id = None
    naplo_uj = dict(naplo)
    naplo_uj["visszavonas"] = {"idopont": tetel.visszavonva_at.isoformat(), "eredmeny": eredmeny}
    tetel.rogzites_naplo = naplo_uj
    allapot_ujraertekeles_alap(db, tetel)
    return eredmeny


def allapot_ujraertekeles_alap(db: Session, tetel: UtalasTetel) -> None:
    """Visszavonás után a tétel újra rögzíthető állapotba kerül."""
    tetel.allapot = "rogzitheto" if tetel.cel_tipus else "valasztas"
    allapot_ujraertekeles(db, tetel)
