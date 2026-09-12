"""TISZTA ÚJRAINDÍTÁS: az eddigi számla-érkeztetési beérkezések kitakarítása.

A felhasználó kérése: az új érkeztető EDDIGI beérkezései (e-mailből és az
asszisztensből) tűnjenek el, és induljon tisztán - a teljes pénzügyi
adatbázishoz és a Notion-importhoz NEM nyúlunk.

A takarítás elvei:

- MENTÉS ELŐBB: minden törlendő sor teljes tartalma egy visszaállítási
  jegyzékbe kerül (a válaszban + ha van tárhely, az R2-re is);
- BIZONYÍTHATÓ EREDET: kizárólag azt vonjuk vissza, amit a piszkozat
  rögzítés-naplója (rogzites_naplo) tételesen megnevez - találgatás nincs;
- a jóváhagyáskor létrejött ÚJ kiadást csak akkor töröljük, ha azóta
  bizonyíthatóan nem nyúltak hozzá (nem kifizetett, nem módosították) -
  különben RENDEZENDŐ KIVÉTELKÉNT jelöljük és békén hagyjuk;
- a meglévő rekordhoz CSATOLT fájl-kapcsolatot (csatolmány, TIG-számla sor)
  eltávolítjuk, magát a kiadást/TIG-et nem bántjuk; a csatolmányok fájljai
  saját másolatok (a mentéskor mindig új tárhely-kulcsra másolunk), tehát a
  törlésük más rekordot nem érint;
- az E-Rezsi időszak összegét csak a naplózott előző érték alapján állítjuk
  vissza, és csak ha a mező még a számláról írt értéken áll;
- a KIZÁRÁSI NAPLÓ MEGMARAD: a bejovo_emailek sorok nem törlődnek, csak
  "reset_kizart" jelölést kapnak - így a kitakarított levelek a következő
  lehúzáskor akkor sem jönnek vissza, ha a postafiókban olvasatlanok. Az
  eredeti levelekhez nem nyúlunk (nem törlünk, olvasottságot nem állítunk)."""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.bejovo_szamla import ALLAPOT_JOVAHAGYVA, BejovoEmail, BejovoSzamla
from app.models.document_attachment import DocumentAttachment
from app.models.employee import Employee
from app.models.finance import Expense
from app.models.internal_performance_certificate import (
    InternalPerformanceCertificate,
    InternalPerformanceCertificateInvoice,
)
from app.models.kotelezettseg import KotelezettsegIdoszak
from app.models.performance_certificate import PerformanceCertificate, PerformanceCertificateInvoice
from app.services import document_storage

logger = logging.getLogger(__name__)


def _sor_mentese(obj) -> dict:
    adat = {}
    for oszlop in obj.__table__.columns:
        ertek = getattr(obj, oszlop.name)
        if hasattr(ertek, "isoformat"):
            adat[oszlop.name] = ertek.isoformat()
        elif hasattr(ertek, "quantize"):  # Decimal
            adat[oszlop.name] = float(ertek)
        else:
            adat[oszlop.name] = ertek
    return adat


def teljes_reset(db: Session, vegrehajto: Employee) -> dict:
    """A teljes érkeztető kitakarítása - a visszaállítási jegyzékkel tér vissza.

    Idempotens: üres érkeztetőn lefuttatva semmit nem csinál."""
    most = datetime.now(timezone.utc)
    jegyzek: dict = {
        "idopont": most.isoformat(),
        "vegrehajto": vegrehajto.full_name,
        "torolt_piszkozatok": [],
        "visszavont_kiadasok": [],
        "eltavolitott_kapcsolatok": [],
        "visszaallitott_mezok": [],
        "kivetelek": [],
        "kizarasi_naplo_sorok": 0,
    }
    torlendo_r2: list[str] = []

    piszkozatok = db.scalars(select(BejovoSzamla).order_by(BejovoSzamla.id)).all()
    for b in piszkozatok:
        jegyzek["torolt_piszkozatok"].append(_sor_mentese(b))
        if b.storage_key:
            torlendo_r2.append(b.storage_key)

        if b.allapot == ALLAPOT_JOVAHAGYVA and b.rogzites_naplo:
            naplo = b.rogzites_naplo
            # 1) A jóváhagyás által LÉTREHOZOTT kiadások visszavonása.
            for tetel in naplo.get("letrejott") or []:
                if tetel.get("tipus") != "expense":
                    continue
                exp = db.get(Expense, tetel.get("id"))
                if exp is None:
                    continue  # már nincs meg - nincs mit visszavonni
                modositva = (
                    exp.updated_at is not None
                    and exp.created_at is not None
                    and (exp.updated_at - exp.created_at).total_seconds() > 10
                )
                # Az Utókövetés időközben TIG-piszkozatot köthetett ehhez a
                # kiadáshoz (performance_certificates.expense_id, ondelete
                # nélkül) - az ilyen kiadás törlése FK-hibát dobna, és üzleti
                # kapcsolat is: rendezendő kivétel, nem törlés.
                tig_hivatkozik = db.scalar(
                    select(PerformanceCertificate.id).where(PerformanceCertificate.expense_id == exp.id)
                )
                belso_hivatkozik = db.scalar(
                    select(InternalPerformanceCertificate.id).where(
                        InternalPerformanceCertificate.expense_id == exp.id
                    )
                )
                if exp.kesz or modositva or exp.kp_forgalmak or tig_hivatkozik or belso_hivatkozik:
                    # Azóta kifizették / kézzel módosították / más rekord épült
                    # rá: NEM töröljük találgatásra - rendezendő kivétel.
                    jegyzek["kivetelek"].append(
                        {
                            "tipus": "expense",
                            "id": exp.id,
                            "megnevezes": exp.megnevezes,
                            "ok": (
                                "kifizetett"
                                if exp.kesz
                                else "KP-tétel hivatkozik rá"
                                if exp.kp_forgalmak
                                else f"az Utókövetés TIG-je hivatkozik rá (#{tig_hivatkozik or belso_hivatkozik})"
                                if (tig_hivatkozik or belso_hivatkozik)
                                else "az import után kézzel módosították"
                            ),
                        }
                    )
                    continue
                # SAVEPOINT-os védőháló: ha bármilyen itt nem ismert rekord
                # hivatkozik a kiadásra, csak EZ az egy visszavonás marad el
                # (kivételként), nem az egész reset hasal el.
                exp_mentes = _sor_mentese(exp)
                att_mentesek: list[dict] = []
                att_kulcsok: list[str] = []
                try:
                    with db.begin_nested():
                        for att in db.scalars(
                            select(DocumentAttachment).where(
                                DocumentAttachment.entity_type == "expense",
                                DocumentAttachment.entity_id == exp.id,
                                DocumentAttachment.kategoria == "szamla",
                            )
                        ):
                            att_mentesek.append(_sor_mentese(att))
                            if att.storage_key:
                                att_kulcsok.append(att.storage_key)
                            db.delete(att)
                        db.delete(exp)
                        db.flush()
                except IntegrityError as exc:
                    jegyzek["kivetelek"].append(
                        {
                            "tipus": "expense",
                            "id": exp_mentes["id"],
                            "megnevezes": exp_mentes.get("megnevezes"),
                            "ok": f"más rekord hivatkozik rá, nem törölhető ({type(exc.orig).__name__})",
                        }
                    )
                    continue
                jegyzek["visszavont_kiadasok"].append(exp_mentes)
                jegyzek["eltavolitott_kapcsolatok"].extend(att_mentesek)
                torlendo_r2.extend(att_kulcsok)

            # 2) A meglévő rekordokhoz ADOTT kapcsolatok eltávolítása -
            # kizárólag a naplóban megnevezett azonosítók alapján.
            for cs in naplo.get("csatolt") or []:
                t = cs.get("tipus") or ""
                if t.startswith("attachment:"):
                    att = db.get(DocumentAttachment, cs.get("id"))
                    if att is not None:
                        jegyzek["eltavolitott_kapcsolatok"].append(_sor_mentese(att))
                        if att.storage_key:
                            torlendo_r2.append(att.storage_key)
                        db.delete(att)
                elif t == "performanceCertificate" and cs.get("szamla_sor"):
                    sor = db.get(PerformanceCertificateInvoice, cs["szamla_sor"])
                    if sor is not None:
                        jegyzek["eltavolitott_kapcsolatok"].append(_sor_mentese(sor))
                        if sor.storage_key:
                            torlendo_r2.append(sor.storage_key)
                        db.delete(sor)
                elif t == "internalPerformanceCertificate" and cs.get("szamla_sor"):
                    sor = db.get(InternalPerformanceCertificateInvoice, cs["szamla_sor"])
                    if sor is not None:
                        jegyzek["eltavolitott_kapcsolatok"].append(_sor_mentese(sor))
                        if sor.storage_key:
                            torlendo_r2.append(sor.storage_key)
                        db.delete(sor)
                elif t == "kotelezettsegIdoszak":
                    idoszak = db.get(KotelezettsegIdoszak, cs.get("id"))
                    if idoszak is None:
                        continue
                    elozo = (naplo.get("elozo_ertekek") or {}).get("kotelezettseg_idoszak")
                    szamlarol_irt = (
                        idoszak.osszeg is not None
                        and b.netto is not None
                        and abs(float(idoszak.osszeg) - float(b.netto)) < 0.01
                    )
                    if elozo and elozo.get("id") == idoszak.id and szamlarol_irt:
                        # Naplózott előző érték + a mező még a számláról írt
                        # állapoton áll: biztonságos visszaállítás.
                        jegyzek["visszaallitott_mezok"].append(
                            {"tipus": "kotelezettsegIdoszak", "id": idoszak.id, "mezo": "osszeg", "rol": float(idoszak.osszeg), "ra": elozo.get("osszeg")}
                        )
                        idoszak.osszeg = elozo.get("osszeg")
                        idoszak.plusz_afa = bool(elozo.get("plusz_afa"))
                        idoszak.penznem = elozo.get("penznem") or "HUF"
                    elif szamlarol_irt:
                        # Régi naplóformátum előző érték nélkül, de a mező még
                        # pontosan a számla értékén áll - az import írta, üres
                        # volt előtte (csak üres mezőbe írtunk): visszaállítás.
                        jegyzek["visszaallitott_mezok"].append(
                            {"tipus": "kotelezettsegIdoszak", "id": idoszak.id, "mezo": "osszeg", "rol": float(idoszak.osszeg), "ra": None}
                        )
                        idoszak.osszeg = None
                    elif idoszak.osszeg is not None:
                        jegyzek["kivetelek"].append(
                            {"tipus": "kotelezettsegIdoszak", "id": idoszak.id, "ok": "az összeget az import után kézzel átírták - nem nyúlunk hozzá"}
                        )

    # 3) A piszkozatok törlése (a self-FK ondelete=SET NULL, mehet egyben).
    for b in piszkozatok:
        db.delete(b)

    # 4) A KIZÁRÁSI NAPLÓ marad: a már látott üzenet-azonosítók jelölést
    # kapnak, hogy a kitakarított levelek ne jöjjenek vissza a következő
    # lehúzáskor - újrafeldolgozásuk csak tudatos külön művelettel lehetséges
    # (a bejovo_emailek sor kézi törlésével).
    for e in db.scalars(select(BejovoEmail)):
        if e.allapot != "reset_kizart":
            e.megjegyzes = f"reset ({most.date().isoformat()}): korábbi állapot: {e.allapot}"
            e.allapot = "reset_kizart"
        jegyzek["kizarasi_naplo_sorok"] += 1

    db.commit()

    # 5) A tárhely-objektumok törlése a sikeres commit UTÁN, HÁTTÉRSZÁLON:
    # több tucat objektum soros törlése a HTTP-kérésbe nem fér bele
    # (proxy-időtúllépést okozott volna) - a takarítás best-effort, egy árva
    # objektum nem hiba.
    def _r2_takaritas(kulcsok: list[str]) -> None:
        for kulcs in kulcsok:
            try:
                document_storage.delete_object(kulcs)
            except Exception:  # noqa: BLE001
                logger.warning("Reset: az R2 objektum törlése nem sikerült: %s", kulcs)

    if torlendo_r2:
        threading.Thread(target=_r2_takaritas, args=(list(torlendo_r2),), daemon=True).start()

    # 6) A visszaállítási jegyzék mentése a tárhelyre is (ha elérhető).
    jegyzek_kulcs = None
    try:
        jegyzek_kulcs = f"bejovo-reset/jegyzek-{most.strftime('%Y%m%d-%H%M%S')}.json"
        document_storage.upload_bytes(
            json.dumps(jegyzek, ensure_ascii=False, indent=1, default=str).encode(), jegyzek_kulcs, "application/json"
        )
    except Exception:  # noqa: BLE001
        jegyzek_kulcs = None

    return {
        "osszefoglalo": {
            "torolt_piszkozat": len(jegyzek["torolt_piszkozatok"]),
            "visszavont_kiadas": len(jegyzek["visszavont_kiadasok"]),
            "eltavolitott_kapcsolat": len(jegyzek["eltavolitott_kapcsolatok"]),
            "visszaallitott_mezo": len(jegyzek["visszaallitott_mezok"]),
            "rendezendo_kivetel": len(jegyzek["kivetelek"]),
            "kizarasi_naplo_sorok": jegyzek["kizarasi_naplo_sorok"],
        },
        "kivetelek": jegyzek["kivetelek"],
        "jegyzek_tarhely_kulcs": jegyzek_kulcs,
        "jegyzek": jegyzek,
    }
