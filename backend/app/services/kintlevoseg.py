"""PROJEKT-KINTLÉVŐSÉGEK a Pénzügyek oldalra: minden projektkód, amiért még
nem jött meg a pénz.

A pénzügyesnek két kérdésre kell innen választ kapnia:

1. **Hová kell még számlát kiállítani?** (``szamlazando``) - a munkáért még
   nem jött pénz, és számla sincs róla (se feltöltött számla-fájl, se a
   Notionból örökölt számla-link, se kiállítási dátum a bevétel-soron).
2. **Hol van kint a számla, de még nem fizettek?** (``szamla_kint``) - van
   számla, a pénz még nem érkezett meg; a fizetési határidő mutatja, mi késik.

Harmadik, kisebb csoport (``szamla_nelkul``): ahol kimondtuk, hogy számla nem
lesz (kihagyott számla / papír nélküli munka), de azt sem, hogy a pénz megjött
vagy tranzakció nélkül rendeződött. Ez sem maradhat ki csendben - vagy meg kell
érkeznie a pénznek, vagy le kell zárni indokkal.

KI NEM KERÜL BE - csak az, amiről KIMONDTUK, hogy rendezve van:

- ki van fizetve (``ProjectCode.bevetel_kifizetve``: a bevétel-sorok / a
  feltöltött számlák kifizetve, a Notion-állapot „kifizetve", tranzakció
  nélkül lezárva, vagy „kifizetve, de nem kerül a bevételek közé");
- az esemény elmaradt;
- 0 Ft-os vállalási ár MEGINDOKOLVA (``vallalasi_ar_magyarazat``, pl.
  „beszámítva egy fizetésbe") - nincs mit beszedni;
- a papírozásból kivett sorozat (HYPE24 - lásd services/papirozas_hatokor).

Minden más bekerül: összeg nélkül is (az is teendő, hogy az összeg hiányzik),
és a még meg nem tartott eseményekkel is (ott a számlázás később jön - a
lista a végén, külön jelölve mutatja őket). Csak olvas.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.project_code import ProjectCode
from app.services import elszamolas, papirozas_hatokor, projektkod_osszeg

SZAMLAZANDO = "szamlazando"
SZAMLA_KINT = "szamla_kint"
SZAMLA_NELKUL = "szamla_nelkul"
CSOPORTOK = (SZAMLAZANDO, SZAMLA_KINT, SZAMLA_NELKUL)

_ISMERETLEN_UGYFEL = "ismeretlen ügyfél"


def _megrendelo(pc: ProjectCode) -> str | None:
    nev = getattr(pc.client, "nev", None) if pc.client is not None else None
    if nev and _ISMERETLEN_UGYFEL not in nev.lower():
        return nev
    return (pc.megrendelo_neve or "").strip() or nev or None


def _rendezve_indokkal(pc: ProjectCode) -> bool:
    """0 Ft-os vállalási ár, megindokolva - nincs mit beszedni."""
    netto, _ = projektkod_osszeg.forintban(pc)
    return netto == 0 and bool((pc.vallalasi_ar_magyarazat or "").strip()) and not list(pc.revenues or [])


def _papir_allas(pc: ProjectCode) -> str:
    if not pc.papir_kell:
        return "nem_kell"
    if pc.tig_kesz:
        return "tig_kesz"
    if pc.szerzodes_kell and not pc.szerzodes_kesz:
        return "szerzodes_hianyzik"
    return "tig_hianyzik"


def projekt_kintlevosegek(db: Session, *, ma: date | None = None) -> list[dict]:
    """Minden ki nem fizetett projektkód, csoportba sorolva és rendezve."""
    ma = ma or date.today()
    sorok: list[dict] = []
    for pc in db.scalars(
        select(ProjectCode).options(
            selectinload(ProjectCode.revenues),
            selectinload(ProjectCode.client),
            selectinload(ProjectCode.megrendeloi_tigek),
            selectinload(ProjectCode.megrendeloi_szerzodesek),
        )
    ).all():
        if pc.bevetel_kifizetve or pc.elmaradt or papirozas_hatokor.projektkod_kivett(pc.projektkod):
            continue
        if _rendezve_indokkal(pc):
            continue

        szamlak = pc._szamlak()
        nyitott_szamlak = [s for s in szamlak if s.kifizetve_datuma is None and not s.tranzakcio_nelkul_lezarva]
        regi_szamla = bool(isinstance(pc.szamla_url, str) and pc.szamla_url) or any(
            r.szamla_kiallitva_datuma is not None or bool(r.szamla_file_url) for r in pc.revenues or []
        )
        if not pc.szamla_kell:
            csoport = SZAMLA_NELKUL
        elif szamlak or regi_szamla:
            csoport = SZAMLA_KINT
        else:
            csoport = SZAMLAZANDO

        # MENNYI van még kint: a projekt bevétele (bevétel-sorok, különben a
        # vállalási ár forintban) mínusz ami dátummal igazoltan megjött.
        teljes = float(pc.bevetel or 0)
        fizetett = float(sum(elszamolas.osszeg(r) for r in pc.revenues or [] if r.fizetes_datuma is not None))
        kintlevo = max(teljes - fizetett, 0.0) if teljes > 0 else None

        allas = pc.hatarido_allas
        nyitott_hatarido = allas if allas and allas.get("allapot") in ("var", "lejart", "ma_jar_le") else None
        megjegyzes = None
        if csoport == SZAMLA_NELKUL:
            megjegyzes = (pc.szamla_kihagyas_oka or pc.papir_nelkul_indoka or "").strip() or None
        esemeny = pc.datum
        sorok.append(
            {
                "project_code_id": pc.id,
                "projektkod": pc.projektkod,
                "projekt_nev": pc.project_nev or None,
                "megrendelo": _megrendelo(pc),
                "allapot": csoport,
                "kintlevo_osszeg": kintlevo,
                "esemeny_datuma": esemeny,
                "esemeny_jovobeli": bool(esemeny and esemeny > ma),
                "papir": _papir_allas(pc),
                "szamlak": [
                    {
                        "nev": s.filename,
                        "url": s.url,
                        "netto": float(s.netto) if s.netto is not None else None,
                        "fizetesi_hatarido": s.fizetesi_hatarido,
                    }
                    for s in nyitott_szamlak
                ],
                "regi_szamla_url": pc.szamla_url if (not szamlak and isinstance(pc.szamla_url, str) and pc.szamla_url) else None,
                "legkorabbi_hatarido": date.fromisoformat(nyitott_hatarido["hatarido"]) if nyitott_hatarido else None,
                "hatarido_napok": nyitott_hatarido["napok"] if nyitott_hatarido else None,
                "lejart": bool(nyitott_hatarido and nyitott_hatarido.get("allapot") == "lejart"),
                "hatarido_hianyzik": csoport == SZAMLA_KINT and nyitott_hatarido is None,
                "megjegyzes": megjegyzes,
            }
        )

    def kulcs(s: dict) -> tuple:
        csop = CSOPORTOK.index(s["allapot"])
        if s["allapot"] == SZAMLA_KINT:
            # Lejárt elöl (a legrégebben lejárt legelöl), aztán a legközelebbi
            # határidő, végül a határidő nélküliek.
            napok = s["hatarido_napok"]
            return (csop, 0 if s["lejart"] else 1 if napok is not None else 2, napok or 0, -(s["kintlevo_osszeg"] or 0))
        # Számlázandó: a rég lezajlott munka a legsürgetőbb; a jövőbeli
        # események a végére, dátum nélküliek közé.
        d = s["esemeny_datuma"]
        return (csop, 1 if s["esemeny_jovobeli"] else 0, d or date.max, s["projektkod"] or "")

    sorok.sort(key=kulcs)
    return sorok


def osszesito(sorok: list[dict]) -> dict:
    ki: dict = {}
    for csop in CSOPORTOK:
        cs = [s for s in sorok if s["allapot"] == csop]
        ki[f"{csop}_db"] = len(cs)
        ki[f"{csop}_osszeg"] = float(sum(s["kintlevo_osszeg"] or 0 for s in cs))
    ki["lejart_db"] = sum(1 for s in sorok if s["lejart"])
    ki["lejart_osszeg"] = float(sum(s["kintlevo_osszeg"] or 0 for s in sorok if s["lejart"]))
    ki["osszeg_nelkul_db"] = sum(1 for s in sorok if s["kintlevo_osszeg"] is None)
    return ki
