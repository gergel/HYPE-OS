"""Feladat Larának a beszélgetésből.

Két út van:
1. FELISMERÉS: ha a kérdező a „Kérdezz Larától” beszélgetésben elvégzendő
   ADMINISZTRÁCIÓS munkát kér (pl. „intézd el…”, „készíts TIG-et…”, „küldd
   ki…”), Lara nem állítja, hogy megcsinálta. A válasz alatt MEGKÉRDEZI,
   készítsen-e belőle feladatot, és előtölti: típus, cím, leírás, partner,
   projektkód, határidő.
2. KÖZVETLEN: a „Feladat Larának” gombbal a beírt szövegből rögtön
   feladat-javaslat lesz (kérdés-válasz nélkül).

Mindkét esetben CSAK a felhasználó megerősítésére jön létre a feladat.
Ugyanaz, mint a Munkasor kézi feladat-felvétele:
- `create` jog a Lara oldalon;
- „csak a felelősnek” módban Lara felelőse a felelős;
- bizalmi szint L0, új állapot.

A feladat létrehozása belső munkaszervezés: üzleti rekordot nem ír, semmit
nem küld, semmit nem hajt végre. A feladaton Lara a meglévő, jóváhagyás-
köteles úton dolgozik tovább.

HATÁSKÖR:
- csak adminisztrációs feladattípus lehet (számla, e-mail, TIG, szerződés,
  egyéb papírmunka);
- utalás és nem adminisztratív terület (diszpó, utómunka, portál, beosztás)
  NEM lesz feladat — Lara ezt meg is mondja.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin_agent.enums import ADMIN_FELADATTIPUSOK, ActorKind, TaskState
from app.models.admin_agent import ActionTrace, AdminTask, LaraBeszelgetes, LaraBeszelgetesUzenet
from app.models.employee import Employee

TIPUS_CIMKE = {
    "szamla": "Számla", "email": "E-mail", "tig": "TIG", "szerzodes": "Szerződés",
    "diszpo": "Diszpó brief + technika", "osszefogo": "Összefogó adminisztrációs feladat",
    "egyeb": "Egyéb adminisztráció",
}

#: Kifejezett feladat-kérés („vedd fel feladatnak…”).
_KIFEJEZETT = re.compile(
    r"\b(vedd fel (feladatnak|feladatként)|legyen (ez )?(egy )?feladat|készíts (egy )?feladatot|feladat(ként|nak)?\s*:|"
    r"tedd (be )?a munkasorba|jegyezd fel feladatnak)",
    re.I,
)
#: Lara felé intézett, elvégzendő munkára utaló felszólítás / kérés.
_KERES = re.compile(
    r"\b(intézd|intézz|készítsd|készíts|csináld|csinálj|küldd|küldj|írd meg|írj|rögzítsd|vezesd fel|vegyél fel|"
    r"állítsd ki|kérd be|kérj be|egyeztesd|egyeztess|nézz utána és|ellenőrizd és|pótold|javítsd|töltsd ki|"
    r"szólj rá|jelezd|készítsen|kellene (egy|a)|meg kéne|meg kellene|zárd le|nézd át|tedd rendbe|rendezd|"
    r"vizsgáld meg|gyűjtsd össze|készítsd elő)\b",
    re.I,
)
_KERDES_ELEJE = re.compile(r"^\s*(mi|mennyi|mennyibe|hány|hol|mikor|miért|hogyan|ki|kinek|melyik|van|volt|kell)\b", re.I)
#: Hatáskörön kívül — ebből soha nem lesz feladat.
_UTALAS = re.compile(r"\b(utald|utalj|utalás|átutal|fizesd ki|fizess ki|kifizetni|bankba)\w*", re.I)
_NEM_ADMIN = re.compile(r"\b(utómunka|vágás|portál|beosztás|forgatási nap)\w*", re.I)
#: A diszpóból Lara a BRIEFET és a TECHNIKAI LISTÁT vállalja (2026-09-28 óta);
#: a kiküldést, az átütemezést és a beosztást továbbra sem.
_DISZPO = re.compile(r"\b(diszpó|diszpo)\w*", re.I)
_DISZPO_RESZ = re.compile(r"\b(brief|technik|eszközlist|eszközök|felszerelés)\w*", re.I)
#: Összefogó (több projektkódot / időszakot átfogó) feladatra utaló szavak.
_OSSZEFOGO = re.compile(
    r"\b(összes|mindegyik|minden|valamennyi|az egész|teljes körű|havi|heti|negyedév\w*|q[1-4]|"
    r"január\w*|február\w*|március\w*|április\w*|május\w*|június\w*|július\w*|augusztus\w*|"
    r"szeptember\w*|október\w*|november\w*|december\w*|lezárás\w*|zárd le|rendbe tenni|rendbe tedd|tedd rendbe)\b",
    re.I,
)
_TOBB_KOD = re.compile(r"\b[A-Z]{2,8}\d{2}-\d{3,5}\b")

#: A teendő (ige) előbb számít, mint a téma: „írj levelet a TIG-ről” e-mail.
_TIPUS_SZAVAK = (
    ("email", ("e-mail", "email", "levél", "levelet", "válaszolj", "írj", "írd meg")),
    ("tig", ("tig", "teljesítésigazolás")),
    ("szerzodes", ("szerződés", "keretszerződés")),
    ("szamla", ("számla", "számlá", "kiadás", "díjbekérő")),
)


class FeladatHiba(ValueError):
    pass


def osszefogo_e(szoveg: str) -> bool:
    """Több projektkódot / időszakot / partnert átfogó adminisztrációs feladat-e?"""
    if len(set(_TOBB_KOD.findall(szoveg or ""))) >= 2:
        return True
    return bool(_OSSZEFOGO.search(szoveg or ""))


def _tipus_tipp(szoveg: str) -> str:
    kis = szoveg.lower()
    if _DISZPO_RESZ.search(kis) and (_DISZPO.search(kis) or re.search(r"\b(brief|technikai lista)", kis)):
        return "diszpo"
    if osszefogo_e(szoveg) and not re.search(r"\b(írj|írd meg|levél|levelet|válaszolj)\b", kis):
        return "osszefogo"
    for t, szavak in _TIPUS_SZAVAK:
        if any(re.search(r"\b" + re.escape(s) + (r"\b" if len(s) <= 4 else ""), kis) for s in szavak):
            return t
    return "egyeb"


def _hatarido_tipp(szoveg: str, ma: date | None = None) -> str | None:
    kis = szoveg.lower()
    ma = ma or datetime.now(timezone.utc).date()
    m = re.search(r"\b(20\d\d)[.\-/ ]+(\d{1,2})[.\-/ ]+(\d{1,2})\b", kis)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        except ValueError:
            return None
    if re.search(r"\bholnapután\b", kis):
        return (ma + timedelta(days=2)).isoformat()
    if re.search(r"\bholnap", kis):
        return (ma + timedelta(days=1)).isoformat()
    if re.search(r"\bma\b|\bmég ma\b", kis):
        return ma.isoformat()
    napok = ("hétfő", "kedd", "szerd", "csütörtök", "péntek", "szombat", "vasárnap")
    for i, nap in enumerate(napok):
        if re.search(r"\b" + nap, kis):
            kul = (i - ma.weekday()) % 7 or 7
            return (ma + timedelta(days=kul)).isoformat()
    return None


_ROVIDITES = re.compile(r"\b(kft|bt|zrt|nyrt|kkt|ev|stb|pl|kb|ill|ú\.?n|dr|id|özv)\.$", re.I)


def _elso_mondat(szoveg: str) -> str:
    """Az első mondat — a rövidítések (Kft., Bt., stb., pl.) pontjánál nem vág."""
    darabok = re.split(r"(?<=[.!?])\s+|\n", szoveg.strip())
    ki = darabok[0] if darabok else ""
    for d in darabok[1:]:
        if not _ROVIDITES.search(ki):
            break
        ki = f"{ki} {d}"
    return ki


def _cim(szoveg: str) -> str:
    elso = _elso_mondat(szoveg)
    elso = re.sub(r"^(kérlek|légy szíves|légyszi|lara)[, ]+", "", elso, flags=re.I).strip()
    elso = _KIFEJEZETT.sub("", elso).strip(" :,-")
    elso = elso[:1].upper() + elso[1:] if elso else elso
    return (elso[:117] + "…") if len(elso) > 120 else elso


def hataskoron_kivul(szoveg: str) -> str | None:
    """Ha a kért munka Lara hatáskörén kívül esik, az ok (különben None)."""
    if _UTALAS.search(szoveg):
        return "Utalást Lara nem végez és nem készít elő — ebből nem lehet Lara-feladat."
    if _NEM_ADMIN.search(szoveg) and not re.search(r"\b(számla|tig|szerződés)", szoveg, re.I):
        return "Ez nem adminisztrációs terület (utómunka / portál / beosztás) — Lara ott nem vállal feladatot."
    if _DISZPO.search(szoveg) and not _DISZPO_RESZ.search(szoveg) and not re.search(r"\b(számla|tig|szerződés)", szoveg, re.I):
        return (
            "A diszpó kiküldése, átütemezése és a beosztás nem Lara dolga — a diszpóhoz a briefet és a "
            "technikai listát (az eszközök hozzárendelésével) tudja elkészíteni."
        )
    return None


def felismer(szoveg: str, *, kifejezett: bool = False) -> dict | None:
    """Feladat-javaslat a szövegből, ha abban elvégzendő munka áll (vagy
    kifejezetten feladatot kértek). None: nincs benne feladat."""
    s = (szoveg or "").strip()
    if not s:
        return None
    if not kifejezett:
        kifejezett = bool(_KIFEJEZETT.search(s))
    keres = bool(_KERES.search(s)) and not (_KERDES_ELEJE.search(s) and s.rstrip().endswith("?") and not kifejezett)
    if not (kifejezett or keres):
        return None
    return {
        "tipus": _tipus_tipp(s),
        "cim": _cim(s) or "Feladat a beszélgetésből",
        "leiras": s[:4000],
        "partner": None,
        "projektkod": None,
        "hatarido": _hatarido_tipp(s),
        "allapot": "javasolt",
        "kifejezett": kifejezett,
    }


def osszevon(heur: dict | None, modell: dict | None, kerdes: str) -> dict | None:
    """A modell javaslata (ha érvényes) + a szöveg-alapú felismerés. A
    hatáskörön kívüli kérésből nem lesz javaslat."""
    if hataskoron_kivul(kerdes):
        return None
    if isinstance(modell, dict) and (modell.get("cim") or "").strip():
        j = {
            "tipus": modell.get("tipus") if modell.get("tipus") in ADMIN_FELADATTIPUSOK else (heur or {}).get("tipus", "egyeb"),
            "cim": str(modell.get("cim")).strip()[:300],
            "leiras": str(modell.get("leiras") or kerdes).strip()[:4000],
            "partner": (str(modell.get("partner")).strip()[:255] or None) if modell.get("partner") else None,
            "projektkod": (str(modell.get("projektkod")).strip()[:50] or None) if modell.get("projektkod") else None,
            "hatarido": modell.get("hatarido") if isinstance(modell.get("hatarido"), str) else (heur or {}).get("hatarido"),
            "allapot": "javasolt",
            "kifejezett": bool((heur or {}).get("kifejezett")),
        }
        return j
    return heur


# ── Megerősítés / elvetés ────────────────────────────────────────────────────


def _uzenet(db: Session, user: Employee, uzenet_id: int) -> tuple[LaraBeszelgetesUzenet, LaraBeszelgetes]:
    u = db.get(LaraBeszelgetesUzenet, uzenet_id)
    if u is None or u.szerep != "lara" or not (u.adat or {}).get("feladat_javaslat"):
        raise LookupError("A feladat-javaslat nem található.")
    b = db.get(LaraBeszelgetes, u.beszelgetes_id)
    if b is None or b.employee_id != user.id:
        raise LookupError("A feladat-javaslat nem található.")
    return u, b


def letrehoz(db: Session, user: Employee, uzenet_id: int, modositott: dict | None = None) -> dict:
    """A (javított) javaslatból Lara-feladat. Idempotens: egy javaslatból
    egy feladat. A hívó commitál; a `create` jogot a hívó ellenőrzi."""
    from app.admin_agent.settings_service import csak_felelosnek, lara_felelos
    from app.models.project_code import ProjectCode

    u, b = _uzenet(db, user, uzenet_id)
    adat = dict(u.adat or {})
    j = dict(adat["feladat_javaslat"])
    if j.get("allapot") == "letrehozva" and j.get("task_id"):
        return j
    for k in ("tipus", "cim", "leiras", "partner", "projektkod", "hatarido", "project_id"):
        if modositott and k in modositott:
            j[k] = modositott[k]
    tipus = j.get("tipus") or "egyeb"
    if tipus not in ADMIN_FELADATTIPUSOK:
        raise FeladatHiba(
            "Lara csak a hatáskörébe tartozó feladatot vállalhat (számla, e-mail, TIG, szerződés, diszpó brief + "
            "technika, összefogó adminisztráció, egyéb)."
        )
    cim = str(j.get("cim") or "").strip()
    if len(cim) < 3:
        raise FeladatHiba("Adj a feladatnak címet.")
    ok = hataskoron_kivul(f"{cim} {j.get('leiras') or ''}")
    if ok:
        raise FeladatHiba(ok)
    pc_id = None
    if j.get("projektkod"):
        pc = db.scalar(select(ProjectCode).where(ProjectCode.projektkod.ilike(str(j["projektkod"]).strip())))
        if pc is None:
            raise FeladatHiba(f"Nincs ilyen projektkód: {j['projektkod']}")
        pc_id = pc.id
    project_id = None
    if tipus == "diszpo":
        from app.admin_agent.diszpo_tervezo import forgatas_kereses

        project_id = forgatas_kereses(db, project_id=j.get("project_id"), project_code_id=pc_id,
                                      szoveg=f"{cim} {j.get('leiras') or ''}")
    hatarido = None
    if j.get("hatarido"):
        try:
            d = date.fromisoformat(str(j["hatarido"])[:10])
        except ValueError as exc:
            raise FeladatHiba("Érvénytelen határidő.") from exc
        hatarido = datetime(d.year, d.month, d.day, 16, 0, tzinfo=timezone.utc)
    felelos = lara_felelos(db) if csak_felelosnek(db) else None
    t = AdminTask(
        tipus=tipus,
        cim=cim[:300],
        osszefoglalo=(str(j.get("leiras") or "").strip()
                      + f"\n\n(Forrás: „Kérdezz Larától” beszélgetés, {user.full_name}.)")[:8000],
        allapot=TaskState.NEW.value,
        prioritas=0,
        felelos_id=felelos.id if felelos is not None else user.id,
        hatarido=hatarido,
        project_code_id=pc_id,
        project_id=project_id,
        partner_nev=(str(j.get("partner") or "").strip() or None),
        trust_level="L0",
        forras_referenciak={"lara_chat": {"beszelgetes_id": b.id, "uzenet_id": u.id, "letrehozta_id": user.id}},
    )
    db.add(t)
    db.flush()
    db.add(ActionTrace(
        task_id=t.id, szereplo=ActorKind.HUMAN.value, muvelet="feladat_beszelgetesbol",
        eroforras=f"lara_chat:{b.id}:{u.id}", diff={"tipus": tipus, "cim": cim[:300], "letrehozta_id": user.id},
        eredmeny="letrehozva", tortent_at=datetime.now(timezone.utc),
    ))
    if tipus == "osszefogo":
        # A nagy feladat értelmezése (hatókör + terv) rögtön elkészül; a
        # részfeladatok csak külön, kifejezett lépésre jönnek létre.
        from app.admin_agent import osszefogo

        osszefogo.ertelmez(db, t)
    j.update({"tipus": tipus, "cim": cim[:300], "allapot": "letrehozva", "task_id": t.id,
              "project_code_id": pc_id, "project_id": project_id, "hatarido": hatarido.date().isoformat() if hatarido else None})
    adat["feladat_javaslat"] = j
    u.adat = adat
    db.add(LaraBeszelgetesUzenet(
        beszelgetes_id=b.id, szerep="lara",
        szoveg=(f"Felvettem a feladatot: **{cim}** ({TIPUS_CIMKE.get(tipus, tipus)}). A Munkasorban dolgozom rajta; "
                "amit javaslok, azt jóváhagyásra eléd teszem — magától semmi nem hajtódik végre."),
        adat={"tipus": "feladat_letrehozva", "task_id": t.id},
    ))
    b.updated_at = datetime.now(timezone.utc)
    db.flush()
    return j


def elvet(db: Session, user: Employee, uzenet_id: int) -> dict:
    u, _ = _uzenet(db, user, uzenet_id)
    adat = dict(u.adat or {})
    j = dict(adat["feladat_javaslat"])
    if j.get("allapot") == "javasolt":
        j["allapot"] = "elvetve"
        adat["feladat_javaslat"] = j
        u.adat = adat
        db.flush()
    return j


def kozvetlen(db: Session, user: Employee, b: LaraBeszelgetes, szoveg: str) -> tuple[LaraBeszelgetesUzenet, LaraBeszelgetesUzenet]:
    """„Feladat Larának” gomb: a szövegből rögtön feladat-javaslat (kérdés-
    válasz nélkül); a felhasználó javíthatja, és megerősítésre jön létre."""
    szoveg = (szoveg or "").strip()
    if not szoveg:
        raise FeladatHiba("Írd le a feladatot.")
    k = LaraBeszelgetesUzenet(beszelgetes_id=b.id, szerep="felhasznalo", szoveg=szoveg, adat={"tipus": "feladat_keres"})
    db.add(k)
    if b.cim == "Új beszélgetés":
        b.cim = ("Feladat: " + szoveg.splitlines()[0])[:80]
    ok = hataskoron_kivul(szoveg)
    if ok:
        v = LaraBeszelgetesUzenet(beszelgetes_id=b.id, szerep="lara", szoveg=ok, adat={"tipus": "feladat_elutasitva"})
    else:
        j = felismer(szoveg, kifejezett=True)
        v = LaraBeszelgetesUzenet(
            beszelgetes_id=b.id, szerep="lara",
            szoveg="Így venném fel feladatnak. Nézd át, javítsd, ha kell, és hagyd jóvá.",
            adat={"tipus": "feladat_javaslat", "feladat_javaslat": j},
        )
    db.add(v)
    b.updated_at = datetime.now(timezone.utc)
    db.flush()
    return k, v
