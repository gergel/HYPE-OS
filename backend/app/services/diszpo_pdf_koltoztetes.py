"""A RÉGI diszpó PDF-ek átköltöztetése a saját tárhelyre (R2).

A felhasználó kérése: a diszpó PDF ne a Drive-ról nyíljon. Az új kiküldések
már eleve az R2-re is felkerülnek (services/dispo.send_diszpo); ez a modul a
RÉGIEKET hozza át:

- `koltoztesd_at`: EGY projekt régi PDF-jét tölti le (Drive-fájl, Google Docs
  dokumentum PDF-exportja, vagy sima http-link) és teszi fel az R2-re - ezt
  hívja a megnyitási végpont is (routes/dashboard.sajat_diszpo_pdf_url).
- `inditsd_a_teljes_koltoztetest`: az ÖSSZES még át nem hozott régi diszpót
  költözteti háttérszálon, az app indulásakor (lásd main.py). Idempotens:
  aminek már van R2-linkje, azt kihagyja - így deploy-onként csak addig fut,
  amíg van mit áthozni, a sikertelenek pedig a következő indulásnál újra
  próbálkoznak."""

from __future__ import annotations

import logging
import re

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.project import Project
from app.services import document_storage

logger = logging.getLogger("hype_os")

#: A háttérfeladat neve a `hatter_feladatok` táblában (zár + napló).
FELADAT_NEV = "diszpo-pdf-r2-koltoztetes"

_DRIVE_ID_MINTAK = (
    re.compile(r"/d/([A-Za-z0-9_-]{10,})"),
    re.compile(r"[?&]id=([A-Za-z0-9_-]{10,})"),
)


def _letoltes(url: str) -> bytes:
    """A régi diszpó PDF letöltése a mentett linkről. Drive-os linknél a Drive
    API-n át megy (Google Docs dokumentumot PDF-ként exportálva - lásd
    gdoc_template.drive_fajl_letoltes); minden másnál sima http-letöltés."""
    for minta in _DRIVE_ID_MINTAK:
        talalat = minta.search(url)
        if talalat is not None:
            from app.services.gdoc_template import drive_fajl_letoltes

            return drive_fajl_letoltes(talalat.group(1))
    import httpx

    valasz = httpx.get(url, follow_redirects=True, timeout=30)
    valasz.raise_for_status()
    # Ha nem PDF jött (pl. egy bejelentkező/HTML oldal), azt nem mentjük el
    # "diszpo.pdf"-ként - marad a régi link tartaléknak.
    if not valasz.content.startswith(b"%PDF"):
        raise ValueError("A letöltött tartalom nem PDF")
    return valasz.content


def koltoztesd_at(db: Session, project: Project) -> str | None:
    """EGY projekt régi diszpó PDF-jének áthozása az R2-re. A kész (vagy már
    meglévő) R2-linkkel tér vissza; None, ha nincs mit/mivel költöztetni.
    Letöltési/feltöltési hibánál kivételt dob - a hívó dönt a tartalékról."""
    if project.diszpo_pdf_r2_url:
        return project.diszpo_pdf_r2_url
    forras = project.drive_diszpo_pdf_url or project.diszpo_pdf_url
    if not forras or not document_storage.is_configured():
        return None
    pdf_bytes = _letoltes(forras)
    key = f"diszpo-pdf/{project.id}/diszpo.pdf"
    url = document_storage.upload_bytes(pdf_bytes, key, "application/pdf")
    project.diszpo_pdf_r2_url = url
    project.diszpo_pdf_r2_key = key
    db.commit()
    return url


def _koltoztetendo_projekt_idk(db: Session) -> list[int]:
    return list(
        db.scalars(
            select(Project.id)
            .where(
                Project.diszpo_pdf_r2_url.is_(None),
                or_(Project.drive_diszpo_pdf_url.is_not(None), Project.diszpo_pdf_url.is_not(None)),
            )
            .order_by(Project.id)
        )
    )


def inditsd_a_teljes_koltoztetest() -> bool:
    """Az összes még át nem hozott régi diszpó PDF költöztetése háttérszálon.

    Visszatérés: True = elindult; False = nincs mit áthozni, nincs R2, vagy a
    feladat épp fut (a zárat a hatter_feladat adja). Projektenkénti hibánál a
    többi megy tovább - a sikertelen sor marad a régi linkjén (a megnyitás
    tartaléka azt használja), és a következő induláskor újra próbálkozunk."""
    if not document_storage.is_configured():
        return False
    db = SessionLocal()
    try:
        idk = _koltoztetendo_projekt_idk(db)
    finally:
        db.close()
    if not idk:
        return False

    from app.services import hatter_feladat

    def munka(naplo) -> dict:
        siker = 0
        hibas = 0
        naplo(f"Régi diszpó PDF-ek átköltöztetése az R2-re: {len(idk)} projekt.")
        for pid in idk:
            # Projektenként külön, rövid kapcsolat: egy hosszú futás ne tartson
            # fogva egy kapcsolatot a poolból, és egy hibás sor rollbackje ne
            # érintse a többit.
            mdb = SessionLocal()
            try:
                projekt = mdb.get(Project, pid)
                if projekt is None or projekt.diszpo_pdf_r2_url:
                    continue
                try:
                    if koltoztesd_at(mdb, projekt):
                        siker += 1
                        naplo(f"OK: #{pid} {projekt.nev or ''}")
                except Exception as exc:  # noqa: BLE001 - soronként megyünk tovább
                    hibas += 1
                    naplo(f"HIBA: #{pid} {projekt.nev or ''} - {exc}")
            finally:
                mdb.close()
        naplo(f"Kész: {siker} átköltöztetve, {hibas} sikertelen (azok a régi linken maradnak).")
        return {"atkoltoztetve": siker, "sikertelen": hibas}

    return hatter_feladat.inditas(FELADAT_NEV, munka, reszletek={"osszes": len(idk)})
