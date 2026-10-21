"""Strukturált bejövő számla-piszkozat: létrehozás, érvényesítés a törzsadattal,
előkészítési opciók a hiányzó dokumentumokra, és a pénzügyi állapotváltozás
explicit megerősítésének ellenőrzése.

A piszkozat a MEGLÉVŐ érkeztető-sorba (BejovoSzamla) kerül, `forras="draft"`
jelöléssel - nem párhuzamos rendszer: ha minden dokumentum megvan, a
piszkozat "ellenorzendo" állapotba lép a megtalált külsős TIG-gel mint céllal,
és a szokásos jóváhagyással (POST /bejovo-szamlak/{id}/jovahagyas) rögzíthető.

Mit NEM csinál ez a modul (és ezt tesztek őrzik):
- nem rögzít kiadást, nem csatol számlát TIG-hez, nem jelöl kifizetettnek;
- nem hoz létre szerződést, TIG-et vagy vállalkozást - a hiányzókra csak
  ELŐKÉSZÍTÉSI OPCIÓT ad (melyik meglévő végpont, milyen előtöltött adattal),
  amit egy ember indíthat el;
- nem küld levelet senkinek.

Minden létrehozás, érvényesítés és gépi egyeztetés az automatizálási
audit-naplóba kerül (lásd services/automatizalas_audit.py)."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.bejovo_szamla import (
    ALLAPOT_DUPLIKATUM,
    ALLAPOT_EGYEB_DOKUMENTUM,
    ALLAPOT_ELLENORZENDO,
    ALLAPOT_FELDOLGOZAS,
    ALLAPOT_HIANYZO_DOKUMENTUMOK,
    ALLAPOT_HIBA,
    ALLAPOT_NEM_SZAMLA,
    ALLAPOT_PONTOSITAS,
    BejovoSzamla,
)
from app.models.contract import Contract, ContractType, keretszerzodes_ervenyes, megkotott_keretszerzodes
from app.models.employee import Employee
from app.models.performance_certificate import PerformanceCertificate, PerformanceCertificateTetel
from app.models.project import Project
from app.models.project_code import ProjectCode
from app.models.vallalkozas import Vallalkozas
from app.schemas.szamla_draft import OSSZEG_TURES, SzamlaDraftIn, adoszam_szamjegyei
from app.services import automatizalas_audit

FORRAS_DRAFT = "draft"

#: Ezekből az állapotokból érvényesíthető (újra) a piszkozat.
VALIDALHATO_ALLAPOTOK = (
    ALLAPOT_FELDOLGOZAS,
    ALLAPOT_ELLENORZENDO,
    ALLAPOT_PONTOSITAS,
    ALLAPOT_HIANYZO_DOKUMENTUMOK,
)
#: A duplikáció-vizsgálatnál nem számító (félretett) állapotok.
_FELRETETT = (ALLAPOT_DUPLIKATUM, ALLAPOT_NEM_SZAMLA, ALLAPOT_EGYEB_DOKUMENTUM, ALLAPOT_HIBA)

TIG_KIKULDVE = "Kiküldve"
TIG_KIHAGYVA = "Kihagyva"
#: Eseti szerződés ezekben az állapotokban fedezi a munkát.
SZERZODES_KESZ = {"Kiküldve", "Van már szerződés"}
SZERZODES_KIHAGYVA = "Kihagyva"

#: A szokásos magyar ÁFA-kulcsok (0 = AAM / fordított adózás / tárgyi mentes).
AFA_KULCSOK = (0, 5, 18, 27)

_SZEREPLO = {"ai": "ai", "lara": "ai", "szabaly": "rendszer", "kezi": "felhasznalo"}


class DraftHiba(ValueError):
    """Emberi hibaüzenet - a végpont 400-ként adja."""


class DraftUtkozes(DraftHiba):
    """Ugyanez a számla (partner + számlaszám) már bent van - 409."""

    def __init__(self, uzenet: str, meglevo_id: int):
        super().__init__(uzenet)
        self.meglevo_id = meglevo_id


class MegerositesHiba(DraftHiba):
    """Hiányzó (428) vagy elavult (409) pénzügyi megerősítés."""

    def __init__(self, uzenet: str, statusz: int):
        super().__init__(uzenet)
        self.statusz = statusz


# ── Ujjlenyomat és megerősítés ───────────────────────────────────────────────


def ellenorzo_kod(bejovo: BejovoSzamla) -> str:
    """A piszkozat PÉNZÜGYI adatainak ujjlenyomata: ha bármelyik változik
    (összeg, partner, számlaszám, cél, csatolt fájl), a kód is változik - így egy korábban
    látott állapotra adott megerősítés nem hagyhat jóvá mást."""
    adat = [
        bejovo.id,
        adoszam_szamjegyei(bejovo.kibocsato_adoszam),
        (bejovo.szamlaszam or "").strip().upper(),
        str(Decimal(str(bejovo.netto)).quantize(Decimal("0.01"))) if bejovo.netto is not None else None,
        str(Decimal(str(bejovo.afa_osszeg)).quantize(Decimal("0.01"))) if bejovo.afa_osszeg is not None else None,
        str(Decimal(str(bejovo.brutto)).quantize(Decimal("0.01"))) if bejovo.brutto is not None else None,
        bejovo.penznem,
        bejovo.cel_tipus,
        bejovo.cel_certificate_id,
        bejovo.cel_expense_id,
        bejovo.cel_project_code_id,
        bejovo.fajl_hash,
    ]
    return hashlib.sha256(json.dumps(adat, ensure_ascii=False).encode()).hexdigest()[:16]


def megerosites_kell(bejovo: BejovoSzamla) -> bool:
    """Kell-e explicit megerősítés a jóváhagyáshoz? A gépi (strukturált
    piszkozatból jött) számláknál mindig - ott az adatot nem ember olvasta ki."""
    return bejovo.forras == FORRAS_DRAFT


def megerosites_ellenorzes(bejovo: BejovoSzamla, megerosites: dict | None) -> None:
    """A jóváhagyás (számla elfogadása) előfeltétele a gépi piszkozatoknál:
    `{"megerositve": true, "ellenorzo_kod": <a piszkozat aktuális kódja>}`."""
    if not megerosites_kell(bejovo):
        return
    if not megerosites or megerosites.get("megerositve") is not True:
        raise MegerositesHiba(
            "Ez a számla gépi feldolgozásból jött: a jóváhagyáshoz kifejezett megerősítés kell "
            "(megerosites.megerositve = true és a piszkozat aktuális ellenőrző kódja).",
            428,
        )
    if megerosites.get("ellenorzo_kod") != ellenorzo_kod(bejovo):
        raise MegerositesHiba(
            "A számla pénzügyi adatai megváltoztak, mióta megnyitottad - töltsd újra, és ellenőrizd újra.",
            409,
        )


# ── Létrehozás ───────────────────────────────────────────────────────────────


def _meglevo(db: Session, adoszam: str, szamlaszam: str) -> BejovoSzamla | None:
    torzs = adoszam_szamjegyei(adoszam)[:8]
    jeloltek = db.scalars(
        select(BejovoSzamla).where(
            func.upper(func.trim(BejovoSzamla.szamlaszam)) == szamlaszam.strip().upper(),
            BejovoSzamla.allapot.not_in(_FELRETETT),
        )
    ).all()
    for b in jeloltek:
        if adoszam_szamjegyei(b.kibocsato_adoszam)[:8] == torzs:
            return b
    return None


def _azonos_osszegek(b: BejovoSzamla, adat: SzamlaDraftIn) -> bool:
    def egyezik(a, c) -> bool:
        if a is None or c is None:
            return a is None and c is None
        return abs(Decimal(str(a)) - Decimal(str(c))) <= OSSZEG_TURES

    return egyezik(b.netto, adat.netto) and egyezik(b.brutto, adat.brutto) and b.penznem == adat.penznem


def letrehoz(db: Session, adat: SzamlaDraftIn, user: Employee | None) -> tuple[BejovoSzamla, bool]:
    """Új piszkozat + azonnali érvényesítés. Vissza: (piszkozat, már létezett-e).

    Idempotens: ha ugyanez a gépi piszkozat (partner + számlaszám + összeg)
    már bent van, azt adja vissza változtatás nélkül. Ha ugyanezzel a
    partnerrel és számlaszámmal MÁS adat van bent (vagy nem gépi úton jött),
    az ütközés - nem írunk felül semmit."""
    meglevo = _meglevo(db, adat.partner_adoszam, adat.szamlaszam)
    if meglevo is not None:
        if meglevo.forras == FORRAS_DRAFT and _azonos_osszegek(meglevo, adat):
            return meglevo, True
        raise DraftUtkozes(
            f"Ez a számla (#{meglevo.id}: {meglevo.kibocsato_nev or '?'} / {meglevo.szamlaszam}) már bent van "
            "az érkeztetőben, eltérő adatokkal vagy más forrásból - nézd meg ott.",
            meglevo.id,
        )

    szereplo = _SZEREPLO[adat.kinyero]
    bejovo = BejovoSzamla(
        forras=FORRAS_DRAFT,
        allapot=ALLAPOT_FELDOLGOZAS,
        dokumentum_tipus="szamla",
        irany="bejovo",
        kibocsato_nev=adat.partner_nev,
        kibocsato_adoszam=adat.partner_adoszam,
        szamlaszam=adat.szamlaszam,
        netto=float(adat.netto),
        afa_osszeg=float(adat.afa_osszeg),
        brutto=float(adat.brutto),
        penznem=adat.penznem,
        fizetesi_hatarido=adat.fizetesi_hatarido,
        kiallitas_datuma=adat.kiallitas_datuma,
        teljesites_datuma=adat.teljesites_datuma,
        hivatkozott_projektkod=adat.projektkod,
        hivatkozott_forgatas_datuma=adat.forgatas_datuma,
        felhasznaloi_utasitas=adat.megjegyzes,
        letrehozo_employee_id=user.id if user is not None else None,
        kinyert={
            "forras": FORRAS_DRAFT,
            "kinyero": adat.kinyero,
            "mezo_bizonyossag": adat.mezo_bizonyossag or {},
            "mezok": {"projektkod_hivatkozasok": [adat.projektkod] if adat.projektkod else []},
        },
    )
    db.add(bejovo)
    db.flush()
    automatizalas_audit.naplo(
        db,
        muvelet="szamla_draft.letrehozas",
        eroforras_tipus="bejovo_szamla",
        eroforras_id=bejovo.id,
        szereplo=szereplo,
        employee_id=user.id if user is not None else None,
        reszletek={
            "kinyero": adat.kinyero,
            "partner_adoszam": adat.partner_adoszam,
            "szamlaszam": adat.szamlaszam,
            "netto": float(adat.netto),
            "afa_osszeg": float(adat.afa_osszeg),
            "brutto": float(adat.brutto),
            "penznem": adat.penznem,
            "projektkod": adat.projektkod,
            "forgatas_datuma": adat.forgatas_datuma.isoformat() if adat.forgatas_datuma else None,
            "mezo_bizonyossag": adat.mezo_bizonyossag,
        },
    )
    validal(db, bejovo, user=user)
    return bejovo, False


# ── Érvényesítés ─────────────────────────────────────────────────────────────


def _partner(db: Session, adoszam: str | None, nev: str | None) -> dict:
    """Partner azonosítása ADÓSZÁM alapján a törzsadatban (vállalkozások és a
    munkatársak vállalkozói adószáma). A teljes 11 jegyű egyezés erősebb, mint
    a törzsszám (első 8 jegy) egyezése - utóbbi akkor kell, ha az egyik
    oldalon csak a törzsszám van rögzítve, vagy az ÁFA-kód azóta változott."""
    jegyek = adoszam_szamjegyei(adoszam)
    torzs = jegyek[:8]
    eredmeny: dict = {
        "adoszam": adoszam,
        "vallalkozasok": [],
        "munkatarsak": [],
        "egyezes": None,
        "nev_egyezik": None,
    }
    if len(torzs) != 8:
        return eredmeny

    def illeszt(masik: str | None) -> str | None:
        m = adoszam_szamjegyei(masik)
        if not m:
            return None
        if len(jegyek) == 11 and m == jegyek:
            return "adoszam"
        if m[:8] == torzs:
            return "torzsszam"
        return None

    vall_talalat = []
    for v in db.scalars(select(Vallalkozas).where(Vallalkozas.adoszam.is_not(None))).all():
        mod = illeszt(v.adoszam)
        if mod:
            vall_talalat.append((v, mod))
    emp_talalat = []
    for e in db.scalars(select(Employee).where(Employee.vallalkozas_adoszama.is_not(None))).all():
        mod = illeszt(e.vallalkozas_adoszama)
        if mod:
            emp_talalat.append((e, mod))

    # Pontos (11 jegyű) egyezés van? Akkor a csak törzsszámon egyezők kiesnek.
    if any(m == "adoszam" for _, m in vall_talalat):
        vall_talalat = [(v, m) for v, m in vall_talalat if m == "adoszam"]
    if any(m == "adoszam" for _, m in emp_talalat):
        emp_talalat = [(e, m) for e, m in emp_talalat if m == "adoszam"]

    eredmeny["vallalkozasok"] = [{"id": v.id, "nev": v.nev, "aktiv": v.aktiv} for v, _ in vall_talalat]
    eredmeny["munkatarsak"] = [
        {"id": e.id, "nev": e.full_name, "ceg": e.vallakozas_neve} for e, _ in emp_talalat
    ]
    modok = {m for _, m in vall_talalat + emp_talalat}
    eredmeny["egyezes"] = "adoszam" if "adoszam" in modok else ("torzsszam" if modok else None)

    nevek = [v.nev for v, _ in vall_talalat] + [e.vallakozas_neve or e.full_name for e, _ in emp_talalat]
    if nevek and nev:
        n = " ".join(nev.lower().split())
        eredmeny["nev_egyezik"] = any(n in " ".join((x or "").lower().split()) or " ".join((x or "").lower().split()) in n for x in nevek)
    return eredmeny


def _fel_kulcsok(partner: dict) -> tuple[set[int], set[int]]:
    return {v["id"] for v in partner["vallalkozasok"]}, {e["id"] for e in partner["munkatarsak"]}


def _nap_a_projektben(p: Project, nap: date) -> bool:
    if p.forgatas_datuma is None:
        return False
    vege = p.forgatas_datuma_vege or p.forgatas_datuma
    return p.forgatas_datuma <= nap <= vege


def _projektek(db: Session, projektkod: str | None, nap: date | None) -> tuple[ProjectCode | None, list[Project]]:
    if not projektkod:
        return None, []
    pc = db.scalar(select(ProjectCode).where(func.upper(func.trim(ProjectCode.projektkod)) == projektkod))
    if pc is None:
        return None, []
    projektek = list(
        db.scalars(select(Project).where(Project.project_code_id == pc.id).order_by(Project.forgatas_datuma)).all()
    )
    if nap is not None:
        projektek = [p for p in projektek if _nap_a_projektben(p, nap)]
    return pc, projektek


def _szerzodesek(db: Session, vall_idk: set[int], emp_idk: set[int]) -> list[Contract]:
    if not vall_idk and not emp_idk:
        return []
    felt = []
    if vall_idk:
        felt.append(Contract.vallalkozas_id.in_(vall_idk))
    if emp_idk:
        felt.append(Contract.employee_id.in_(emp_idk))
    return list(
        db.scalars(
            select(Contract)
            .options(selectinload(Contract.idoszakok), selectinload(Contract.tetelek))
            .where(Contract.tipus == ContractType.ALVALLALKOZOI, or_(*felt))
        ).all()
    )


def _szerzodes_vizsgalat(
    szerzodesek: list[Contract], nap: date, pc: ProjectCode | None, projekt_idk: set[int]
) -> dict:
    """Van-e érvényes keretszerződés a napon - és ha nincs, fedezi-e a munkát
    egy erre a projektre szóló eseti szerződés (ami a keretszerződést
    helyettesíti, lásd subcontractor_contracts.py)."""
    keretek = [c for c in szerzodesek if megkotott_keretszerzodes(c)]
    ervenyes = [c for c in keretek if keretszerzodes_ervenyes(c, nap)]
    if ervenyes:
        c = ervenyes[0]
        return {"ok": True, "tipus": "keretszerzodes", "szerzodes_id": c.id, "nap": nap.isoformat(), "megjegyzes": None}

    eseti = []
    for c in szerzodesek:
        if megkotott_keretszerzodes(c):
            continue
        erintett = {t.project_id for t in c.tetelek} | ({c.project_id} if c.project_id else set())
        if (erintett & projekt_idk) or (pc is not None and c.project_code_id == pc.id):
            eseti.append(c)
    kesz = [c for c in eseti if c.szerzodes_allapota in SZERZODES_KESZ]
    if kesz:
        return {"ok": True, "tipus": "eseti", "szerzodes_id": kesz[0].id, "nap": nap.isoformat(), "megjegyzes": None}
    kihagyott = [c for c in eseti if c.szerzodes_allapota == SZERZODES_KIHAGYVA]
    if kihagyott:
        return {
            "ok": True,
            "tipus": "eseti_kihagyva",
            "szerzodes_id": kihagyott[0].id,
            "nap": nap.isoformat(),
            "megjegyzes": f"Az eseti szerződést tudatosan kihagyták: {kihagyott[0].kihagyas_oka or 'indoklás nélkül'}.",
        }
    megjegyzes = None
    if keretek:
        lejart = keretek[0]
        megjegyzes = (
            f"Van keretszerződés (#{lejart.id}), de {nap.isoformat()} napon nem érvényes "
            f"({'kikapcsolva' if not lejart.aktiv else 'az érvényességi időszakán kívül'})."
        )
    piszkozat = [c for c in eseti if c.szerzodes_allapota not in SZERZODES_KESZ]
    if piszkozat:
        megjegyzes = (megjegyzes + " " if megjegyzes else "") + (
            f"Eseti szerződés piszkozata van (#{piszkozat[0].id}, {piszkozat[0].szerzodes_allapota or 'állapot nélkül'})."
        )
    return {
        "ok": False,
        "tipus": None,
        "szerzodes_id": None,
        "piszkozat_id": piszkozat[0].id if piszkozat else None,
        "nap": nap.isoformat(),
        "megjegyzes": megjegyzes,
    }


def _tig_jeloltek(
    db: Session,
    vall_idk: set[int],
    emp_idk: set[int],
    adoszam: str | None,
    pc: ProjectCode | None,
    projektek: list[Project],
    nap: date | None,
) -> list[PerformanceCertificate]:
    """Külsős TIG-ek a partnertől a projektkód + forgatási nap szerinti
    projekteken (a TIG tételein át is: egy TIG több projektet fedhet).
    Projektkód nélkül a partner TIG-jei közül azok, amelyek valamelyik
    tételének forgatása a hivatkozott napra esik."""
    fel_felt = []
    if vall_idk:
        fel_felt.append(PerformanceCertificate.vallalkozas_id.in_(vall_idk))
    if emp_idk:
        fel_felt.append(PerformanceCertificate.employee_id.in_(emp_idk))
    torzs = adoszam_szamjegyei(adoszam)[:8]

    projekt_idk = {p.id for p in projektek}
    q = select(PerformanceCertificate).options(
        selectinload(PerformanceCertificate.tetelek).selectinload(PerformanceCertificateTetel.project),
        selectinload(PerformanceCertificate.invoices),
        selectinload(PerformanceCertificate.project),
    )
    if pc is not None:
        hely = [PerformanceCertificate.project_code_id == pc.id]
        if projekt_idk:
            hely.append(PerformanceCertificate.project_id.in_(projekt_idk))
            hely.append(
                PerformanceCertificate.tetelek.any(PerformanceCertificateTetel.project_id.in_(projekt_idk))
            )
        q = q.where(or_(*hely))
        # A projektkód-szintű TIG-nél a nap nem szűr (nincs forgatása); a
        # forgatáshoz kötöttnél a fenti projektlista már napra szűrt.
        if nap is not None and projekt_idk:
            q = q.where(
                or_(
                    PerformanceCertificate.project_id.in_(projekt_idk),
                    PerformanceCertificate.tetelek.any(PerformanceCertificateTetel.project_id.in_(projekt_idk)),
                    PerformanceCertificate.project_id.is_(None),
                )
            )
        elif nap is not None and not projekt_idk:
            q = q.where(PerformanceCertificate.project_id.is_(None))
    elif fel_felt:
        q = q.where(or_(*fel_felt))
    else:
        return []

    jeloltek = list(db.scalars(q.order_by(PerformanceCertificate.id.desc()).limit(50)).all())

    def a_partnere(c: PerformanceCertificate) -> bool:
        if c.vallalkozas_id is not None and c.vallalkozas_id in vall_idk:
            return True
        if c.employee_id is not None and c.employee_id in emp_idk:
            return True
        # Ismeretlen partnernél (vagy régi, fél nélküli TIG-nél) a TIG-re
        # írt adószám dönt.
        return bool(torzs) and adoszam_szamjegyei(c.adoszam)[:8] == torzs

    jeloltek = [c for c in jeloltek if a_partnere(c)]
    if pc is None and nap is not None:
        jeloltek = [
            c
            for c in jeloltek
            if any(t.project is not None and _nap_a_projektben(t.project, nap) for t in c.tetelek)
            or (c.project is not None and _nap_a_projektben(c.project, nap))
        ]
    return jeloltek


def _tig_dict(c: PerformanceCertificate, netto: float | None) -> dict:
    tig_netto = float(c.netto_osszeg) if c.netto_osszeg is not None else None
    return {
        "id": c.id,
        "allapot": c.allapot,
        "ceg_neve": c.ceg_neve,
        "project_id": c.project_id,
        "project_code_id": c.project_code_id,
        "netto": tig_netto,
        "osszeg_egyezik": (
            None if tig_netto is None or netto is None else abs(tig_netto - netto) <= float(OSSZEG_TURES)
        ),
        "szamlak_db": len(c.invoices),
        "szamla_kifizetve": bool(c.szamla_kifizetve),
    }


def _csoport_kulcs(project: Project, vall_idk: set[int], emp_idk: set[int]) -> str | None:
    """A partner számlázó-kulcsa a projekten, ha a TIG-populáció része
    (stábtag vagy alvállalkozói kiadás). None: nem szerepel a projekten."""
    from app.api.routes.performance_certificates import tig_csoportok
    from app.services import szamlazo

    felulirasok = szamlazo.load_felulirasok(Session.object_session(project), {project.id})
    for cs in tig_csoportok(project, felulirasok):
        if cs.fel.vallalkozas is not None and cs.fel.vallalkozas.id in vall_idk:
            return cs.kulcs
        if cs.fel.vallalkozas is None and cs.fel.employee is not None and cs.fel.employee.id in emp_idk:
            return cs.kulcs
    return None


def _opcio(kod: str, cim: str, leiras: str, *, vegpont: dict | None = None, link: str | None = None,
           kulso_hatas: bool = False) -> dict:
    """Előkészítési opció: MIT érdemes tenni, és melyik meglévő végponttal. A
    rendszer maga SOSEM hívja meg - egy ember indítja, a saját jogosultságával."""
    return {
        "kod": kod,
        "cim": cim,
        "leiras": leiras,
        "vegpont": vegpont,
        "link": link,
        "kulso_hatas": kulso_hatas,
        "automatikusan_fut": False,
    }


def validal(db: Session, bejovo: BejovoSzamla, *, user: Employee | None = None) -> dict:
    """A piszkozat összevetése a törzsadattal; beállítja az állapotot, a
    partnert, a fedező szerződést, a javasolt célt és a `validacio` mezőt.
    Újrafuttatható (pl. miután elkészült a hiányzó TIG). A hívó commitol."""
    if bejovo.allapot not in VALIDALHATO_ALLAPOTOK:
        raise DraftHiba(f"Ebben az állapotban már nem érvényesíthető újra: {bejovo.allapot}.")
    elotte = bejovo.allapot
    netto = float(bejovo.netto) if bejovo.netto is not None else None
    nap = (
        bejovo.hivatkozott_forgatas_datuma
        or bejovo.teljesites_datuma
        or bejovo.kiallitas_datuma
        or date.today()
    )

    figyelmeztetesek: list[str] = []
    hianyzo: list[dict] = []
    opciok: list[dict] = []
    ellenorzesek: dict = {}

    # ── 1) Partner (adószám -> törzsadat)
    partner = _partner(db, bejovo.kibocsato_adoszam, bejovo.kibocsato_nev)
    vall_idk, emp_idk = _fel_kulcsok(partner)
    partner_ok = bool(vall_idk or emp_idk)
    tobbes = len(partner["vallalkozasok"]) > 1 or (not vall_idk and len(partner["munkatarsak"]) > 1)
    ellenorzesek["partner"] = {**partner, "ok": partner_ok and not tobbes, "tobbes_talalat": tobbes}
    bejovo.partner_vallalkozas_id = partner["vallalkozasok"][0]["id"] if len(partner["vallalkozasok"]) == 1 else None
    bejovo.partner_employee_id = (
        partner["munkatarsak"][0]["id"] if not bejovo.partner_vallalkozas_id and len(partner["munkatarsak"]) == 1 else None
    )
    if not partner_ok:
        hianyzo.append({"dokumentum": "partner", "ok": "Az adószám nem szerepel a törzsadatban (vállalkozások, munkatársak)."})
        opciok.append(
            _opcio(
                "partner_felvetele",
                "Számlázó vállalkozás felvétele",
                f"A(z) {bejovo.kibocsato_nev} ({bejovo.kibocsato_adoszam}) nincs a törzsadatban. Vedd fel "
                "vállalkozásként - a székhely, képviselő és nyilvántartási szám kötelező, ezeket a számláról kell kitölteni.",
                vegpont={
                    "metodus": "POST",
                    "utvonal": "/api/v1/vallalkozasok",
                    "torzs": {"nev": bejovo.kibocsato_nev, "adoszam": bejovo.kibocsato_adoszam},
                },
                link="/penzugyek/vallalkozasok",
            )
        )
    elif tobbes:
        figyelmeztetesek.append(
            "Az adószám több törzsadat-rekordhoz is illeszkedik - a partner nem egyértelmű, a szerződés és a TIG "
            "keresése az összes egyezőre kiterjed."
        )
    if partner_ok and partner.get("nev_egyezik") is False:
        figyelmeztetesek.append(
            f"A számlán szereplő név ({bejovo.kibocsato_nev}) eltér a törzsadatban lévőtől - ellenőrizd a partnert."
        )
    if partner_ok and partner.get("egyezes") == "torzsszam":
        figyelmeztetesek.append("Az adószám csak a törzsszámon (első 8 jegy) egyezik a törzsadattal.")

    # ── 2) Projekt (projektkód + forgatási nap)
    pc, projektek = _projektek(db, bejovo.hivatkozott_projektkod, bejovo.hivatkozott_forgatas_datuma)
    ellenorzesek["projekt"] = {
        "projektkod": bejovo.hivatkozott_projektkod,
        "project_code_id": pc.id if pc else None,
        "forgatas_datuma": bejovo.hivatkozott_forgatas_datuma.isoformat() if bejovo.hivatkozott_forgatas_datuma else None,
        "projektek": [
            {"id": p.id, "nev": p.nev, "forgatas_datuma": p.forgatas_datuma.isoformat() if p.forgatas_datuma else None}
            for p in projektek
        ],
    }
    if bejovo.hivatkozott_projektkod and pc is None:
        figyelmeztetesek.append(f"A(z) {bejovo.hivatkozott_projektkod} projektkód nem létezik a rendszerben.")
        opciok.append(
            _opcio(
                "projektkod_pontositasa",
                "Projektkód pontosítása",
                "A hivatkozott projektkód ismeretlen - javítsd a piszkozaton (vagy kérdezd meg a partnert), "
                "aztán futtasd újra az ellenőrzést.",
                link=f"/penzugyek/bejovo-szamlak?id={bejovo.id}",
            )
        )
    elif pc is not None and bejovo.hivatkozott_forgatas_datuma and not projektek:
        figyelmeztetesek.append(
            f"A(z) {pc.projektkod} kódon nincs forgatás {bejovo.hivatkozott_forgatas_datuma.isoformat()} napon."
        )
    elif not bejovo.hivatkozott_projektkod:
        figyelmeztetesek.append("A számla nem hivatkozik projektkódra - a TIG-et csak partner és nap alapján kerestük.")

    # ── 3) Fedező szerződés (keretszerződés a napon, vagy eseti a projektre)
    projekt_idk = {p.id for p in projektek}
    szerzodes = _szerzodes_vizsgalat(_szerzodesek(db, vall_idk, emp_idk), nap, pc, projekt_idk)
    ellenorzesek["szerzodes"] = szerzodes
    bejovo.szerzodes_id = szerzodes.get("szerzodes_id")
    if szerzodes.get("megjegyzes") and szerzodes["ok"]:
        figyelmeztetesek.append(szerzodes["megjegyzes"])

    # A partner számlázó-kulcsa az (egyetlen) érintett projekten - ettől
    # lesz a TIG/eseti szerződés előkészítése egy konkrét, meglévő végpont.
    celprojekt = projektek[0] if len(projektek) == 1 else None
    kulcs = _csoport_kulcs(celprojekt, vall_idk, emp_idk) if (celprojekt is not None and partner_ok) else None

    if not szerzodes["ok"]:
        hianyzo.append(
            {
                "dokumentum": "keretszerzodes",
                "ok": szerzodes.get("megjegyzes") or f"Nincs érvényes alvállalkozói keretszerződés {nap.isoformat()} napra.",
            }
        )
        if partner_ok and not tobbes:
            fel = (
                {"vallalkozas_id": bejovo.partner_vallalkozas_id}
                if bejovo.partner_vallalkozas_id
                else {"employee_id": bejovo.partner_employee_id}
            )
            opciok.append(
                _opcio(
                    "keretszerzodes_elokeszitese",
                    "Keretszerződés előkészítése",
                    f"Álló alvállalkozói keretszerződés felvétele {bejovo.kibocsato_nev} részére (a cégadatok a "
                    "törzsadatból másolódnak). Kiküldeni és aláíratni külön lépés.",
                    vegpont={"metodus": "POST", "utvonal": "/api/v1/contracts/keretszerzodes", "torzs": fel},
                    link="/penzugyek/keretszerzodesek",
                )
            )
        if celprojekt is not None and kulcs is not None:
            opciok.append(
                _opcio(
                    "eseti_szerzodes_elokeszitese",
                    "Eseti szerződés piszkozata erre a projektre",
                    f"Ha nem keretszerződés kell, eseti megbízási szerződés piszkozata a(z) {celprojekt.nev or celprojekt.id} "
                    "projektre - csak mentés, küldés nélkül.",
                    vegpont={
                        "metodus": "POST",
                        "utvonal": f"/api/v1/alvallalkozoi-szerzodesek/{celprojekt.id}/{kulcs}/save",
                        "torzs": {"netto_osszeg": netto, "plusz_afa": bool(bejovo.afa_osszeg)},
                    },
                    link=f"/utokovetes/{celprojekt.id}",
                )
            )

    # ── 4) Külsős TIG (projektkód + forgatási nap + partner)
    tigek = _tig_jeloltek(
        db, vall_idk, emp_idk, bejovo.kibocsato_adoszam, pc, projektek, bejovo.hivatkozott_forgatas_datuma
    )
    kikuldott = [c for c in tigek if c.allapot == TIG_KIKULDVE]
    kihagyott = [c for c in tigek if c.allapot == TIG_KIHAGYVA]
    piszkozatok = [c for c in tigek if c.allapot not in (TIG_KIKULDVE, TIG_KIHAGYVA)]
    valasztott: PerformanceCertificate | None = None
    if len(kikuldott) == 1:
        valasztott = kikuldott[0]
    elif len(kikuldott) > 1:
        egyezok = [c for c in kikuldott if c.netto_osszeg is not None and netto is not None
                   and abs(float(c.netto_osszeg) - netto) <= float(OSSZEG_TURES)]
        if len(egyezok) == 1:
            valasztott = egyezok[0]
    ellenorzesek["tig"] = {
        "ok": bool(kikuldott),
        "egyertelmu": valasztott is not None,
        "valasztott_id": valasztott.id if valasztott else None,
        "jeloltek": [_tig_dict(c, netto) for c in tigek[:10]],
    }
    if not kikuldott:
        ok = "Nincs kiküldött külsős TIG a partnertől"
        if pc is not None:
            ok += f" a(z) {pc.projektkod} kódon"
        if bejovo.hivatkozott_forgatas_datuma:
            ok += f" {bejovo.hivatkozott_forgatas_datuma.isoformat()} napra"
        ok += "."
        if piszkozatok:
            ok += f" Van piszkozat (#{piszkozatok[0].id}, {piszkozatok[0].allapot or 'állapot nélkül'})."
        hianyzo.append({"dokumentum": "tig", "ok": ok})
        if kihagyott:
            figyelmeztetesek.append(
                f"A partner TIG-jét ezen a munkán tudatosan kihagyták (#{kihagyott[0].id}) - "
                "a számla ennek ellentmond, egyeztesd."
            )
        if celprojekt is not None and kulcs is not None:
            opciok.append(
                _opcio(
                    "tig_elokeszitese" if not piszkozatok else "tig_piszkozat_kiegeszitese",
                    "Külsős TIG előkészítése" if not piszkozatok else "A meglévő TIG-piszkozat kiegészítése",
                    "TIG-piszkozat mentése a számla adataival előtöltve (csak mentés - a kiküldés a partnernek "
                    "külön, emberi lépés az Utókövetésben).",
                    vegpont={
                        "metodus": "POST",
                        "utvonal": f"/api/v1/teljesitesi-igazolasok/{celprojekt.id}/{kulcs}/save",
                        "torzs": {
                            "ceg_neve": bejovo.kibocsato_nev,
                            "adoszam": bejovo.kibocsato_adoszam,
                            "netto_osszeg": netto,
                            "plusz_afa": bool(bejovo.afa_osszeg),
                            "teljesites_kezdete": celprojekt.forgatas_datuma.isoformat() if celprojekt.forgatas_datuma else None,
                            "teljesites_vege": (celprojekt.forgatas_datuma_vege or celprojekt.forgatas_datuma).isoformat()
                            if celprojekt.forgatas_datuma
                            else None,
                        },
                    },
                    link=f"/utokovetes/{celprojekt.id}",
                )
            )
        elif celprojekt is not None and partner_ok:
            opciok.append(
                _opcio(
                    "stab_ellenorzese",
                    "A partner nincs a forgatás számlázó felei között",
                    f"{bejovo.kibocsato_nev} nem szerepel a(z) {celprojekt.nev or celprojekt.id} forgatás stáblistáján "
                    "és alvállalkozói kiadásai között, így TIG sem készülhet neki. Ellenőrizd a diszpót, a „Ki számláz "
                    "kiért” beállítást, vagy rögzíts alvállalkozói kiadást.",
                    link=f"/utokovetes/{celprojekt.id}",
                )
            )
        elif len(projektek) > 1:
            opciok.append(
                _opcio(
                    "forgatas_pontositasa",
                    "Forgatási nap pontosítása",
                    f"A kódon több forgatás is van ({len(projektek)}) - add meg a pontos forgatási napot, hogy "
                    "egyértelmű legyen, melyikhez kell a TIG.",
                )
            )
    elif valasztott is None:
        figyelmeztetesek.append(
            f"Több kiküldött TIG is szóba jön ({len(kikuldott)}) - válaszd ki, melyikhez tartozik a számla."
        )
    if valasztott is not None:
        tig = _tig_dict(valasztott, netto)
        if tig["osszeg_egyezik"] is False:
            figyelmeztetesek.append(
                f"A TIG nettó összege ({tig['netto']:,.0f} Ft) eltér a számláétól ({netto:,.0f} Ft).".replace(",", " ")
            )
        if valasztott.szamla_kifizetve:
            figyelmeztetesek.append(
                "A TIG-hez tartozó számla már KIFIZETETTKÉNT van jelölve - lehetséges duplikátum."
            )
        elif valasztott.invoices:
            figyelmeztetesek.append(f"A TIG-hez már {len(valasztott.invoices)} számlafájl tartozik.")

    # ── 5) ÁFA-kulcs józansági ellenőrzés (nem blokkol)
    if netto and bejovo.afa_osszeg is not None:
        kulcs_szazalek = float(bejovo.afa_osszeg) / netto * 100
        if not any(abs(kulcs_szazalek - k) <= 0.6 for k in AFA_KULCSOK):
            figyelmeztetesek.append(f"Szokatlan ÁFA-arány ({kulcs_szazalek:.1f}%) - ellenőrizd az összegeket.")
    if bejovo.fizetesi_hatarido and bejovo.fizetesi_hatarido < date.today():
        figyelmeztetesek.append(f"A fizetési határidő ({bejovo.fizetesi_hatarido.isoformat()}) már lejárt.")

    # ── 6) Állapot és javaslat (az érkeztető meglévő formátumában)
    dok_hiany = [h for h in hianyzo if h["dokumentum"] in ("keretszerzodes", "tig")]
    if dok_hiany:
        allapot = ALLAPOT_HIANYZO_DOKUMENTUMOK
        bejovo.cel_tipus = None
        bejovo.cel_certificate_id = None
        indoklas = "Hiányzó dokumentum: " + "; ".join(h["ok"] for h in dok_hiany)
    elif valasztott is None:
        allapot = ALLAPOT_PONTOSITAS
        bejovo.cel_tipus = None
        bejovo.cel_certificate_id = None
        indoklas = "A szerződés és a TIG megvan, de több TIG közül kell választani."
    else:
        allapot = ALLAPOT_ELLENORZENDO
        bejovo.cel_tipus = "kulsos_tig"
        bejovo.cel_certificate_id = valasztott.id
        indoklas = f"Érvényes szerződés ({szerzodes['tipus']}) és kiküldött külsős TIG (#{valasztott.id}) - rögzíthető a TIG számlájaként."
    bejovo.allapot = allapot
    bejovo.javaslat = {
        "tipus": bejovo.cel_tipus,
        "indoklas": indoklas,
        "alternativak": [
            {
                "tipus": "kulsos_tig",
                "cel_id": c.id,
                "cimke": f"Külsős TIG #{c.id} - {c.ceg_neve or '?'} ({c.allapot or '?'})",
                "indoklas": "A partner TIG-je a hivatkozott projekten/napon.",
            }
            for c in tigek[:8]
        ],
        "figyelmeztetesek": figyelmeztetesek,
        "erosseg": "biztos" if allapot == ALLAPOT_ELLENORZENDO and not figyelmeztetesek else (
            "tobb_lehetseges" if allapot == ALLAPOT_PONTOSITAS else "keves_info"
        ),
        "bizonyitek": [
            x
            for x in (
                f"Partner azonosítva adószám alapján ({partner['egyezes']})" if partner_ok else None,
                f"Szerződés: {szerzodes['tipus']} #{szerzodes['szerzodes_id']}" if szerzodes["ok"] else None,
                f"Kiküldött TIG: #{valasztott.id}" if valasztott else None,
            )
            if x
        ],
        "javasolt_cel": {"cel_certificate_id": valasztott.id} if valasztott else {},
    }
    eredmeny = {
        "allapot": allapot,
        "ellenorzesek": ellenorzesek,
        "hianyzo": hianyzo,
        "elokeszitesi_opciok": opciok,
        "figyelmeztetesek": figyelmeztetesek,
        "ellenorizve_at": datetime.now(timezone.utc).isoformat(),
        "ellenorzo_kod": ellenorzo_kod(bejovo),
    }
    bejovo.validacio = eredmeny
    db.flush()

    automatizalas_audit.naplo(
        db,
        muvelet="szamla_draft.validacio",
        eroforras_tipus="bejovo_szamla",
        eroforras_id=bejovo.id,
        szereplo="rendszer",
        employee_id=user.id if user is not None else None,
        reszletek={
            "allapot_elotte": elotte,
            "allapot_utana": allapot,
            "partner_vallalkozas_id": bejovo.partner_vallalkozas_id,
            "partner_employee_id": bejovo.partner_employee_id,
            "szerzodes": {k: szerzodes.get(k) for k in ("ok", "tipus", "szerzodes_id")},
            "javasolt_tig_id": valasztott.id if valasztott else None,
            "hianyzo": [h["dokumentum"] for h in hianyzo],
            "opciok": [o["kod"] for o in opciok],
            "figyelmeztetesek_db": len(figyelmeztetesek),
        },
    )
    return eredmeny
