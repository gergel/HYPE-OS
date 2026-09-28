"""Lara javaslatának EMBERI NYELVŰ leírása: mi fog történni jóváhagyáskor.

A jóváhagyó ne nyers mezőket (`cel_project_code_id: 796`) lásson, hanem azt,
ami ténylegesen történik:
- kinek a számlája, mekkora összeggel;
- hová kerül, mi jön létre, mihez csatolódik;
- mi NEM történik (pl. nem lesz kifizetve, utalás nem indul).

A leírás a végrehajtó tényleges viselkedését követi (lásd
`services/szamla_erkeztetes.jovahagy` és `executor.TOOL_REGISTRY`).

A leírás CSAK OLVAS: az azonosítókat nevekre fordítja, semmit nem ír. A
hiányzó célt / adatot figyelmeztetésként jelzi — ilyenkor a végrehajtás
hibára futna, és ezt a jóváhagyó előre látja.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.admin_agent import ActionProposal, AdminTask

_HONAPOK = ("január", "február", "március", "április", "május", "június", "július", "augusztus", "szeptember",
            "október", "november", "december")


def _ft(ertek, penznem: str | None = "HUF") -> str:
    if ertek is None or ertek == "":
        return "—"
    try:
        v = float(ertek)
    except (TypeError, ValueError):
        return str(ertek)
    egesz = f"{abs(v):,.0f}".replace(",", " ")
    jel = "−" if v < 0 else ""
    p = (penznem or "HUF").upper()
    return f"{jel}{egesz} Ft" if p == "HUF" else f"{jel}{egesz} {p}"


def _projektkod(db: Session, pc_id) -> str | None:
    if not pc_id:
        return None
    from app.models.project_code import ProjectCode

    from sqlalchemy import select

    from app.models.project import Project

    pc = db.get(ProjectCode, int(pc_id))
    if pc is None:
        return None
    # A projektkódnak nincs saját neve: a hozzá tartozó projekté, vagy a megrendelőé.
    nev = db.scalar(select(Project.nev).where(Project.project_code_id == pc.id).order_by(Project.id).limit(1))
    if not nev and pc.client_id:
        from app.models.client import Client

        c = db.get(Client, pc.client_id)
        nev = getattr(c, "nev", None) or getattr(c, "name", None) if c is not None else None
    return f"{pc.projektkod}" + (f" ({nev})" if nev else "")


def _szemely_vagy_ceg(db: Session, employee_id, vallalkozas_id, alap: str | None = None) -> str | None:
    if employee_id:
        from app.models.employee import Employee

        e = db.get(Employee, int(employee_id))
        if e is not None:
            return e.full_name
    if vallalkozas_id:
        from app.models.vallalkozas import Vallalkozas

        v = db.get(Vallalkozas, int(vallalkozas_id))
        if v is not None:
            return getattr(v, "nev", None) or getattr(v, "cegnev", None) or alap
    return alap


def _kulsos_tig(db: Session, cert_id) -> tuple[str, list[str]] | None:
    """(ki a TIG számlázója, a TIG részletei soronként)."""
    if not cert_id:
        return None
    from app.models.performance_certificate import PerformanceCertificate

    c = db.get(PerformanceCertificate, int(cert_id))
    if c is None:
        return None
    ki = _szemely_vagy_ceg(db, c.employee_id, c.vallalkozas_id, c.ceg_neve) or "ismeretlen számlázó"
    reszek: list[str] = []
    kod = _projektkod(db, c.project_code_id)
    if not kod and c.project_id:
        from app.models.project import Project

        p = db.get(Project, c.project_id)
        if p is not None:
            kod = _projektkod(db, getattr(p, "project_code_id", None)) or getattr(p, "nev", None)
    if kod:
        reszek.append(f"Projekt: {kod}")
    if c.teljesites_szoveg:
        reszek.append(f"Teljesítés: {c.teljesites_szoveg}")
    if c.netto_osszeg is not None:
        reszek.append(f"A TIG nettó összege: {_ft(c.netto_osszeg)}")
    return ki, reszek


def _belsos_tig(db: Session, cert_id) -> str | None:
    if not cert_id:
        return None
    from app.models.internal_performance_certificate import InternalPerformanceCertificate

    c = db.get(InternalPerformanceCertificate, int(cert_id))
    if c is None:
        return None
    ki = _szemely_vagy_ceg(db, c.employee_id, None) or "ismeretlen munkatárs"
    honap = _HONAPOK[c.honap - 1] if 1 <= (c.honap or 0) <= 12 else str(c.honap)
    return f"{ki} {c.ev}. {honap}i belsős TIG-je"


def _kiadas(db: Session, exp_id) -> str | None:
    if not exp_id:
        return None
    from app.models.finance import Expense

    e = db.get(Expense, int(exp_id))
    if e is None:
        return None
    osszeg = getattr(e, "brutto", None) or getattr(e, "netto", None)
    kod = _projektkod(db, getattr(e, "project_code_id", None))
    return f"a meglévő „{e.megnevezes}” kiadás ({_ft(osszeg)}{', ' + kod if kod else ''})"


def _erezsi(db: Session, idoszak_id) -> str | None:
    if not idoszak_id:
        return None
    from app.models.kotelezettseg import Kotelezettseg, KotelezettsegIdoszak

    i = db.get(KotelezettsegIdoszak, int(idoszak_id))
    if i is None:
        return None
    k = db.get(Kotelezettseg, i.kotelezettseg_id)
    return f"az E-Rezsi „{k.nev if k else '?'}” {i.esedekesseg.isoformat()} esedékességű időszaka"


def szamla_leiras(db: Session, payload: dict, task: AdminTask) -> dict:
    """Számla-felvezetés (`szamla_erkeztetes.jovahagy`) leírása."""
    from app.models.bejovo_szamla import BejovoSzamla

    ref = (task.forras_referenciak or {}).get("bejovo_szamla_id")
    b = db.get(BejovoSzamla, int(ref)) if ref else None
    p = dict(payload or {})
    figy: list[str] = []
    penznem = p.get("penznem") or (b.penznem if b else "HUF")
    partner = (b.kibocsato_nev if b else None) or task.partner_nev or "ismeretlen kibocsátó"
    netto = p.get("netto") if p.get("netto") is not None else (b.netto if b else None)
    brutto = p.get("brutto") if p.get("brutto") is not None else (b.brutto if b else None)

    fej = f"A(z) {partner} számlája"
    if b and b.szamlaszam:
        fej += f" ({b.szamlaszam})"
    osszeg = f"nettó {_ft(netto, penznem)}" + (f", bruttó {_ft(brutto, penznem)}" if brutto is not None else "")
    reszletek = [f"Összeg: {osszeg}."]
    if b and b.teljesites_datuma:
        reszletek.append(f"Teljesítés: {b.teljesites_datuma.isoformat()}.")
    if b and b.fizetesi_hatarido:
        reszletek.append(f"Fizetési határidő: {b.fizetesi_hatarido.isoformat()}.")

    cel = p.get("cel_tipus") or (b.cel_tipus if b else None)
    kod = _projektkod(db, p.get("cel_project_code_id") or (b.cel_project_code_id if b else None))
    lepesek: list[str] = []
    if cel in ("kiadas_uj", "mukodesi", "auto"):
        felosztas = p.get("felosztas") or []
        if felosztas:
            lepesek.append(f"{len(felosztas)} új kiadás jön létre a Pénzügyekben, a számla összegét felosztva:")
            for f in felosztas:
                lepesek.append(f"  – {_projektkod(db, f.get('project_code_id')) or 'projektkód nélkül'}: "
                               f"nettó {_ft(f.get('netto'), penznem)}")
        elif cel == "mukodesi":
            lepesek.append("Új kiadás jön létre a Pénzügyekben általános működési költségként (projektkód nélkül).")
        elif cel == "auto":
            lepesek.append("Új kiadás jön létre a Pénzügyekben az autó költségeként.")
        else:
            lepesek.append("Új kiadás jön létre a Pénzügyekben"
                           + (f" a(z) {kod} projektkódon." if kod else " — projektkód nélkül."))
            if not kod:
                figy.append("Nincs projektkód megadva: a kiadás projektkód nélkül jönne létre.")
        lepesek.append("A kiadás NEM kifizetettként rögzül: a kifizetést a Pénzügyekben kell külön jelölni.")
        lepesek.append("A számla PDF-je a kiadáshoz csatolódik.")
    elif cel == "kiadas_csatolas":
        exp_id = p.get("cel_expense_id") or (b.cel_expense_id if b else None)
        kiadas = _kiadas(db, exp_id)
        if kiadas:
            lepesek.append(f"A számla PDF-je {kiadas} mellé csatolódik. Új kiadás NEM jön létre.")
            lepesek.append("A kiadás fizetési határideje a számláéhoz igazodik, ha ott még nincs megadva.")
        else:
            lepesek.append("A számla egy meglévő kiadáshoz csatolódna.")
            figy.append("Nincs kiválasztva (vagy nem található) a kiadás, amihez csatolni kell — a végrehajtás hibára futna.")
    elif cel == "kulsos_tig":
        cert_id = p.get("cel_certificate_id") or (b.cel_certificate_id if b else None)
        tig = _kulsos_tig(db, cert_id)
        if tig:
            ki, tig_reszek = tig
            lepesek.append(f"A számla {ki} külsős TIG-jéhez kerül, a TIG számlái közé:")
            lepesek += [f"  {r}" for r in tig_reszek]
            lepesek.append("A TIG fizetési határideje a számláéhoz igazodik, ha ott még nincs megadva.")
            lepesek.append("Új kiadás NEM jön létre (a költség a TIG-en már szerepel).")
        else:
            lepesek.append("A számla egy külsős TIG-hez kerülne.")
            figy.append("Nincs kiválasztva (vagy nem található) a külsős TIG — a végrehajtás hibára futna.")
    elif cel == "belsos_tig":
        cert_id = p.get("cel_internal_certificate_id") or (b.cel_internal_certificate_id if b else None)
        tig = _belsos_tig(db, cert_id)
        if tig:
            lepesek.append(f"A számla {tig} mellé kerül. Új kiadás NEM jön létre.")
        else:
            lepesek.append("A számla egy belsős TIG-hez kerülne.")
            figy.append("Nincs kiválasztva (vagy nem található) a belsős TIG — a végrehajtás hibára futna.")
    elif cel == "erezsi":
        idoszak = _erezsi(db, p.get("cel_kotelezettseg_idoszak_id") or (b.cel_kotelezettseg_idoszak_id if b else None))
        if idoszak:
            lepesek.append(f"A számla {idoszak} mellé kerül; ha az időszaknak még nincs összege, a számla "
                           f"nettó összege ({_ft(netto, penznem)}) lesz az.")
            lepesek.append("A „fizetve” jelölés nem változik — a számla megérkezése nem kifizetés.")
        else:
            figy.append("Nincs kiválasztva (vagy nem található) az E-Rezsi időszak — a végrehajtás hibára futna.")
    elif cel == "kp":
        lepesek.append("A számla egy házipénztár-tétel bizonylataként csatolódik. Új pénzmozgás NEM keletkezik.")
    elif cel == "bontas":
        sorok = p.get("bontas") or (b.bontas if b else None) or []
        lepesek.append(f"A számla {len(sorok)} célra bontva kerül rögzítésre (a részleteket a számla adatlapja mutatja).")
    else:
        figy.append("A számla célja tisztázandó — konkrét cél nélkül a végrehajtás nem fut le.")

    lepesek.append("A beérkező számla „jóváhagyva” állapotba kerül (a Beérkező számlák között).")
    nem = ["Utalás nem indul, és utalás sem készül elő.", "Senkinek nem megy ki levél."]
    return {
        "cim": fej,
        "reszletek": reszletek,
        "lepesek": lepesek,
        "nem_tortenik": nem,
        "figyelmeztetesek": figy,
        "link": f"/penzugyek/bejovo-szamlak?id={b.id}" if b else None,
    }


def email_leiras(payload: dict) -> dict:
    p = dict(payload or {})
    cimzett = p.get("to") or []
    if isinstance(cimzett, str):
        cimzett = [cimzett]
    torzs = str(p.get("body") or "")
    if not torzs and p.get("html_body"):
        import re

        torzs = re.sub(r"<[^>]+>", " ", str(p["html_body"]))
    torzs = " ".join(torzs.split())
    return {
        "cim": f"E-mail kiküldése: {', '.join(cimzett) or 'nincs címzett'}",
        "reszletek": [f"Tárgy: {p.get('subject') or '—'}.",
                      *([f"Másolat: {', '.join(p['cc'])}."] if p.get("cc") else [])],
        "lepesek": ["A levél a HYPE Gmail-fiókjából megy ki" + (" válaszként a meglévő szálba." if p.get("thread_id") else "."),
                    f"Szöveg eleje: „{torzs[:240]}{'…' if len(torzs) > 240 else ''}”"],
        "nem_tortenik": ["Más címzett nem kapja meg.", "A levél a jóváhagyás után nem vonható vissza."],
        "figyelmeztetesek": [] if cimzett else ["Nincs címzett — a végrehajtás hibára futna."],
        "link": None,
    }


def leiras(db: Session, proposal: ActionProposal, task: AdminTask) -> dict:
    """A javaslat leírása eszköz szerint; ismeretlen eszköznél általános."""
    try:
        if proposal.eszkoz == "szamla_erkeztetes.jovahagy":
            return szamla_leiras(db, proposal.payload, task)
        if proposal.eszkoz == "email.valasz_kuldes":
            return email_leiras(proposal.payload)
    except Exception:  # noqa: BLE001 — a leírás hibája ne akassza el a listát
        pass
    from app.admin_agent.executor import TOOL_REGISTRY

    spec = TOOL_REGISTRY.get(proposal.eszkoz)
    return {
        "cim": spec.cim if spec else proposal.eszkoz,
        "reszletek": [],
        "lepesek": [f"{spec.cim if spec else proposal.eszkoz} — a részletek a technikai adatok között."],
        "nem_tortenik": ["Utalás nem indul."],
        "figyelmeztetesek": [],
        "link": None,
    }
