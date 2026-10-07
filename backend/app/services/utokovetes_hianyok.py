"""Hiányzó alvállalkozói dokumentumok - a LEZAJLOTT forgatások számlázó
feleinek (stáb + alvállalkozói kiadások) összevetése a szerződésekkel, a
külsős TIG-ekkel és a beérkezett számlákkal.

Ugyanazokra az indexekre épül, mint az Utókövetés áttekintő (lásd
routes/utokovetes_admin.py): a sorok SZÁMLÁZÓ FELENKÉNT állnak (egy fél egy
projekten egy szerződést, egy TIG-et és egy számlát ad, akkor is, ha több
ember munkáját fedi), a belsősök kimaradnak (havi TIG-jük van).

A mátrix cellái az ÉLŐ állapotot mutatják (mindig a szerződés/TIG/számla
sorokból számolva), mellettük a tárolt emlékeztető-adatokkal (darabszám,
utolsó értesítés, állapot az értesítéskor) - lásd models/automatizalas.py
UtokovetesDokumentum.

Az emlékeztető RÖGZÍTÉSE (emlekezteto_rogzitese) nem küld levelet: azt a
tényt jegyzi fel, hogy valaki (vagy később egy külön kapcsolóval engedélyezett
automatizmus) szólt a partnernek."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.automatizalas import DOKUMENTUM_TIPUSOK, UtokovetesDokumentum
from app.models.bejovo_szamla import (
    ALLAPOT_DUPLIKATUM,
    ALLAPOT_EGYEB_DOKUMENTUM,
    ALLAPOT_HIBA,
    ALLAPOT_JOVAHAGYVA,
    ALLAPOT_NEM_SZAMLA,
    BejovoSzamla,
)
from app.models.employee import Employee
from app.models.finance import Expense
from app.models.performance_certificate import PerformanceCertificate
from app.models.project import Project
from app.services import automatizalas_audit, papirozas_hatokor

#: Élő állapotok és emberi címkéik - dokumentumonként.
SZERZODES_CIMKEK = {
    "keretszerzodes": "Keretszerződés fedi",
    # Belsős munkatárs (a forgatás napján): nem kell eseti szerződés, mint a
    # keretszerződésesnél - lásd subcontractor_contracts.belsos_fel_a_napon.
    "belsos": "Belsős – nem kell szerződés",
    "alairva": "Aláírva visszaérkezett",
    "van_mar": "Van már szerződés",
    "kihagyva": "Kihagyva",
    "alairasra_var": "Kiküldve, aláírásra vár",
    "piszkozat": "Piszkozat (nincs kiküldve)",
    "hianyzik": "Hiányzik",
}
TIG_CIMKEK = {
    "kikuldve": "Kiküldve",
    "kihagyva": "Kihagyva",
    "piszkozat": "Piszkozat (nincs kiküldve)",
    "hianyzik": "Hiányzik",
}
SZAMLA_CIMKEK = {
    "kifizetve": "Kifizetve",
    "beerkezett": "Beérkezett (a TIG-hez csatolva)",
    "erkeztetoben": "Beérkezett, érkeztetés alatt",
    "beerkezett_tig_nelkul": "Beérkezett, de a TIG hiányzik",
    "kihagyva": "Számla kihagyva",
    "nem_kell": "Nem kell (a TIG kihagyva)",
    "tig_utan": "A TIG kiküldése után esedékes",
    "hianyzik": "Hiányzik",
}
#: Ezek az állapotok jelentenek HIÁNYZÓ dokumentumot (teendőt).
HIANYZO = {
    "szerzodes": {"alairasra_var", "piszkozat", "hianyzik"},
    "tig": {"piszkozat", "hianyzik"},
    "szamla": {"hianyzik"},
}
_FELRETETT_SZAMLA = (ALLAPOT_DUPLIKATUM, ALLAPOT_NEM_SZAMLA, ALLAPOT_EGYEB_DOKUMENTUM, ALLAPOT_HIBA)
CSATORNAK = ("email", "telefon", "szemelyes", "egyeb")


class HianyHiba(ValueError):
    pass


def _vege(p: Project) -> date | None:
    return p.forgatas_datuma_vege or p.forgatas_datuma


def lezajlott_projektek(db: Session, *, ma: date, napok: int | None, project_id: int | None = None) -> list[Project]:
    """A papírozás hatókörébe tartozó, MÁR LEZAJLOTT (a forgatás utolsó napja
    ma előtt van) projektek, legfeljebb `napok` napra visszamenőleg. Dátum
    nélküli projekt nem "lezajlott" - kimarad."""
    q = (
        db.query(Project)
        .filter(
            papirozas_hatokor.utokovetes_projekt_feltetel(),
            Project.forgatas_datuma.is_not(None),
            Project.forgatas_datuma < ma,
        )
        .options(
            selectinload(Project.crew),
            selectinload(Project.alvallalkozo_kiadasok).selectinload(Expense.employee),
            selectinload(Project.project_code),
        )
    )
    if project_id is not None:
        q = q.filter(Project.id == project_id)
    if napok is not None:
        q = q.filter(Project.forgatas_datuma >= ma - timedelta(days=napok + 31))
    projektek = [p for p in papirozas_hatokor.papirozando_projektek(q.all()) if (_vege(p) or ma) < ma]
    if napok is not None:
        projektek = [p for p in projektek if _vege(p) >= ma - timedelta(days=napok)]
    projektek.sort(key=lambda p: (_vege(p), p.id), reverse=True)
    return projektek


def _szerzodes_allapot(
    project: Project, kulcs: str, keretszerzodesek, project_contracts, fel=None
) -> tuple[str, int | None]:
    from app.api.routes.subcontractor_contracts import (
        MAR_VAN_ALLAPOT,
        _mentesul_keretszerzodessel,
        belsos_fel_a_napon,
    )

    if belsos_fel_a_napon(fel, project.forgatas_datuma):
        return "belsos", None
    keretek = keretszerzodesek.get(kulcs, [])
    if _mentesul_keretszerzodessel(keretek, project.forgatas_datuma):
        return "keretszerzodes", keretek[0].id if keretek else None
    c = project_contracts.get((project.id, kulcs))
    if c is None:
        return "hianyzik", None
    allapot = c.szerzodes_allapota
    if allapot == "Kihagyva":
        return "kihagyva", c.id
    if allapot == MAR_VAN_ALLAPOT:
        return "van_mar", c.id
    if allapot == "Kiküldve":
        return ("alairva" if c.alairva else "alairasra_var"), c.id
    return "piszkozat", c.id


def _tig(project: Project, csoport, tig_lookup) -> PerformanceCertificate | None:
    ember_fedettseg, fel_tig = tig_lookup
    cert = fel_tig.get((project.id, csoport.kulcs))
    if cert is not None:
        return cert
    for tag in csoport.tagok:
        cert = ember_fedettseg.get((project.id, tag.id))
        if cert is not None:
            return cert
    return None


def _tig_allapot(cert: PerformanceCertificate | None) -> str:
    if cert is None:
        return "hianyzik"
    if cert.allapot == "Kiküldve":
        return "kikuldve"
    if cert.allapot == "Kihagyva":
        return "kihagyva"
    return "piszkozat"


def _erkeztetoben(db: Session, tig_idk: set[int]) -> dict[int, list[int]]:
    """TIG id -> a hozzá rendelt, még jóvá nem hagyott érkeztető-számlák."""
    if not tig_idk:
        return {}
    eredmeny: dict[int, list[int]] = {}
    for b in db.scalars(
        select(BejovoSzamla).where(
            BejovoSzamla.cel_certificate_id.in_(tig_idk),
            BejovoSzamla.allapot.not_in(_FELRETETT_SZAMLA + (ALLAPOT_JOVAHAGYVA,)),
        )
    ).all():
        eredmeny.setdefault(b.cel_certificate_id, []).append(b.id)
    return eredmeny


def _draft_szamlak(db: Session, projektek: list[Project]) -> dict[tuple[int, str], list[int]]:
    """(projekt, számlázó kulcs) -> a strukturált piszkozatok, amelyek erre a
    forgatásra hivatkoznak (projektkód + nap), de még nincs céljuk - tipikusan
    a `hianyzo_dokumentumok` állapotúak: a számla megjött, a TIG még nem."""
    kodok = {p.project_code.projektkod.upper(): p for p in projektek if p.project_code and p.project_code.projektkod}
    if not kodok:
        return {}
    eredmeny: dict[tuple[int, str], list[int]] = {}
    for b in db.scalars(
        select(BejovoSzamla).where(
            BejovoSzamla.forras == "draft",
            BejovoSzamla.hivatkozott_projektkod.in_(list(kodok)),
            BejovoSzamla.allapot.not_in(_FELRETETT_SZAMLA + (ALLAPOT_JOVAHAGYVA,)),
        )
    ).all():
        kulcs = f"v{b.partner_vallalkozas_id}" if b.partner_vallalkozas_id else (
            f"e{b.partner_employee_id}" if b.partner_employee_id else None
        )
        if kulcs is None:
            continue
        for p in projektek:
            if not (p.project_code and (p.project_code.projektkod or "").upper() == b.hivatkozott_projektkod):
                continue
            nap = b.hivatkozott_forgatas_datuma
            if nap is not None and not (p.forgatas_datuma <= nap <= _vege(p)):
                continue
            eredmeny.setdefault((p.id, kulcs), []).append(b.id)
    return eredmeny


def _szamla_allapot(cert: PerformanceCertificate | None, erkeztetoben: list[int], draftok: list[int]) -> str:
    if cert is None or cert.allapot != "Kiküldve":
        if cert is not None and cert.allapot == "Kihagyva":
            return "nem_kell"
        return "beerkezett_tig_nelkul" if draftok else "tig_utan"
    if cert.szamla_kihagyva:
        return "kihagyva"
    if cert.szamla_kifizetve:
        return "kifizetve"
    if cert.invoices:
        return "beerkezett"
    if erkeztetoben or draftok:
        return "erkeztetoben"
    return "hianyzik"


def _emlekeztetok(db: Session, project_ids: set[int]) -> dict[tuple[int, str, str], UtokovetesDokumentum]:
    if not project_ids:
        return {}
    return {
        (r.project_id, r.szamlazo_kulcs, r.dokumentum_tipus): r
        for r in db.scalars(select(UtokovetesDokumentum).where(UtokovetesDokumentum.project_id.in_(project_ids))).all()
    }


def _cella(tipus: str, allapot: str, cimkek: dict, emlek: UtokovetesDokumentum | None, hivatkozas: dict) -> dict:
    return {
        "allapot": allapot,
        "cimke": cimkek.get(allapot, allapot),
        "hianyzik": allapot in HIANYZO[tipus],
        **hivatkozas,
        "emlekezteto_db": emlek.emlekezteto_db if emlek else 0,
        "utolso_ertesites_at": emlek.utolso_ertesites_at.isoformat() if emlek and emlek.utolso_ertesites_at else None,
        "utolso_ertesites_csatorna": emlek.utolso_ertesites_csatorna if emlek else None,
        "allapot_ertesiteskor": emlek.allapot_ertesiteskor if emlek else None,
        "valtozott_ertesites_ota": bool(emlek and emlek.allapot_ertesiteskor and emlek.allapot_ertesiteskor != allapot),
    }


def matrix(
    db: Session,
    *,
    ma: date | None = None,
    napok: int | None = 120,
    csak_hianyos: bool = True,
    project_id: int | None = None,
) -> dict:
    """Az utókövetési mátrix a lezajlott forgatásokra: projekt × számlázó fél
    × (szerződés, TIG, számla), élő állapottal és emlékeztető-adatokkal."""
    from app.api.routes.performance_certificates import _load_tig_lookup, tig_csoportok
    from app.api.routes.subcontractor_contracts import load_szerzodes_kornyezet

    ma = ma or date.today()
    projektek = lezajlott_projektek(db, ma=ma, napok=napok, project_id=project_id)
    keretszerzodesek, project_contracts, felulirasok = load_szerzodes_kornyezet(db, projektek)
    tig_lookup = _load_tig_lookup(db, {p.id for p in projektek})
    # A TIG-ek számla-fájljai egyben (N+1 lekérdezés helyett).
    tig_idk = {c.id for c in tig_lookup[1].values()} | {c.id for c in tig_lookup[0].values()}
    if tig_idk:
        db.scalars(
            select(PerformanceCertificate)
            .options(selectinload(PerformanceCertificate.invoices))
            .where(PerformanceCertificate.id.in_(tig_idk))
        ).all()
    erkeztetoben = _erkeztetoben(db, tig_idk)
    draftok = _draft_szamlak(db, projektek)
    emlekeztetok = _emlekeztetok(db, {p.id for p in projektek})

    sorok: list[dict] = []
    osszesito = {"szerzodes": 0, "tig": 0, "szamla": 0}
    for p in projektek:
        for cs in tig_csoportok(p, felulirasok):
            sz_allapot, sz_id = _szerzodes_allapot(p, cs.kulcs, keretszerzodesek, project_contracts, cs.fel)
            cert = _tig(p, cs, tig_lookup)
            t_allapot = _tig_allapot(cert)
            p_draftok = draftok.get((p.id, cs.kulcs), [])
            s_allapot = _szamla_allapot(cert, erkeztetoben.get(cert.id, []) if cert else [], p_draftok)
            dokumentumok = {
                "szerzodes": _cella(
                    "szerzodes", sz_allapot, SZERZODES_CIMKEK, emlekeztetok.get((p.id, cs.kulcs, "szerzodes")),
                    {"szerzodes_id": sz_id},
                ),
                "tig": _cella(
                    "tig", t_allapot, TIG_CIMKEK, emlekeztetok.get((p.id, cs.kulcs, "tig")),
                    {"tig_id": cert.id if cert else None},
                ),
                "szamla": _cella(
                    "szamla", s_allapot, SZAMLA_CIMKEK, emlekeztetok.get((p.id, cs.kulcs, "szamla")),
                    {
                        "szamla_fajlok_db": len(cert.invoices) if cert else 0,
                        "erkeztetoben_idk": (erkeztetoben.get(cert.id, []) if cert else []) + p_draftok,
                    },
                ),
            }
            hianyzo = [t for t in DOKUMENTUM_TIPUSOK if dokumentumok[t]["hianyzik"]]
            if csak_hianyos and not hianyzo:
                continue
            for t in hianyzo:
                osszesito[t] += 1
            vege = _vege(p)
            sorok.append(
                {
                    "project_id": p.id,
                    "project_nev": p.nev,
                    "projektkod": p.projektkod_szoveg,
                    "forgatas_datuma": p.forgatas_datuma.isoformat() if p.forgatas_datuma else None,
                    "forgatas_datuma_vege": p.forgatas_datuma_vege.isoformat() if p.forgatas_datuma_vege else None,
                    "lezajlott_napja": (ma - vege).days if vege else None,
                    "szamlazo_kulcs": cs.kulcs,
                    "szamlazo_nev": cs.fel.nev,
                    "cimke": cs.cimke(),
                    "tagok": [t.full_name for t in cs.tagok],
                    "dokumentumok": dokumentumok,
                    "hianyzo": hianyzo,
                    "kesz": not hianyzo,
                }
            )
    return {
        "ma": ma.isoformat(),
        "napok": napok,
        "projekt_db": len(projektek),
        "sor_db": len(sorok),
        "hianyzo_osszesito": osszesito,
        "sorok": sorok,
    }


def emlekezteto_rogzitese(
    db: Session,
    *,
    project_id: int,
    szamlazo_kulcs: str,
    dokumentum_tipus: str,
    csatorna: str,
    megjegyzes: str | None,
    user: Employee,
) -> UtokovetesDokumentum:
    """Egy kiküldött emlékeztető RÖGZÍTÉSE (levelet nem küld). Csak olyan
    cellára, ahol a dokumentum ténylegesen hiányzik - egy kész dokumentumról
    szóló "emlékeztető" hamis képet adna."""
    if dokumentum_tipus not in DOKUMENTUM_TIPUSOK:
        raise HianyHiba(f"Ismeretlen dokumentum-típus: {dokumentum_tipus}")
    if csatorna not in CSATORNAK:
        raise HianyHiba(f"Ismeretlen csatorna: {csatorna} (lehet: {', '.join(CSATORNAK)})")
    if db.get(Project, project_id) is None:
        raise HianyHiba("A projekt nem található.")
    adat = matrix(db, napok=None, csak_hianyos=False, project_id=project_id)
    sor = next((s for s in adat["sorok"] if s["szamlazo_kulcs"] == szamlazo_kulcs), None)
    if sor is None:
        raise HianyHiba("Ez a számlázó fél nem szerepel a lezajlott forgatás papírozandó felei között.")
    cella = sor["dokumentumok"][dokumentum_tipus]
    if not cella["hianyzik"]:
        raise HianyHiba(f"Ez a dokumentum nem hiányzik ({cella['cimke']}) - nincs miről emlékeztetni.")

    rekord = db.scalar(
        select(UtokovetesDokumentum)
        .where(
            UtokovetesDokumentum.project_id == project_id,
            UtokovetesDokumentum.szamlazo_kulcs == szamlazo_kulcs,
            UtokovetesDokumentum.dokumentum_tipus == dokumentum_tipus,
        )
        .with_for_update()
    )
    if rekord is None:
        rekord = UtokovetesDokumentum(
            project_id=project_id, szamlazo_kulcs=szamlazo_kulcs, dokumentum_tipus=dokumentum_tipus, emlekezteto_db=0
        )
        db.add(rekord)
    rekord.emlekezteto_db = (rekord.emlekezteto_db or 0) + 1
    rekord.utolso_ertesites_at = datetime.now(timezone.utc)
    rekord.utolso_ertesites_csatorna = csatorna
    rekord.utolso_ertesites_megjegyzes = (megjegyzes or "").strip()[:2000] or None
    rekord.allapot_ertesiteskor = cella["allapot"]
    rekord.utolso_ertesito_employee_id = user.id
    db.flush()
    automatizalas_audit.naplo(
        db,
        muvelet="utokovetes.emlekezteto",
        eroforras_tipus="utokovetes_dokumentum",
        eroforras_id=rekord.id,
        szereplo="felhasznalo",
        employee_id=user.id,
        reszletek={
            "project_id": project_id,
            "szamlazo_kulcs": szamlazo_kulcs,
            "dokumentum_tipus": dokumentum_tipus,
            "csatorna": csatorna,
            "allapot": cella["allapot"],
            "emlekezteto_db": rekord.emlekezteto_db,
        },
    )
    return rekord
