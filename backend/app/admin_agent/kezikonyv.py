"""Lara rendszerkézikönyve (2026-09, B fázis) — verziózott, jóváhagyott tudás.

Mire jó: Lara a kérdésekre és a javaslataira ne a teljes kódbázisból, hanem a
RELEVÁNS, JÓVÁHAGYOTT szakaszokból dolgozzon (fogalmak, kapcsolatok, mezők,
állapotok, folyamatok, kivételek).

A szakaszok az `aa_memory_chunks` táblában élnek (nincs új tábla):

- `hatokor = "kezikonyv"`;
- `tudas_fajta`:
  - `kezikonyv_technikai`: a rendszer TECHNIKAI leírása — gépi tervezet a
    kódból (adatmodellek docstringje és mező-megjegyzései) és a
    `docs/kezikonyv` fájlokból;
  - `kezikonyv_uzleti`: JÓVÁHAGYOTT ÜZLETI ELJÁRÁS — csak ember írhatja; a
    technikai leírásból sosem lesz magától üzleti szabály;
- `hatokor_reszletek`: `{szakasz_kulcs, cim, forras_tipus, oldal}` — az
  `oldal` a jogosultsági oldal-kulcs, amelyhez a szakasz olvasása kötött.

Életút:

1. A generált tartalom TERVEZET (`minosites="tervezet"`, `ervenyes=False`),
   és így sehol nem használható.
2. Jóváhagyásra (`jovahagy`) válik használhatóvá. Ekkor a szakasz korábbi
   jóváhagyott verziójának érvényessége lezárul (`ervenyes_ig`), de a régi
   verzió NEM törlődik.
3. Ha a forrás megváltozik, az új generálás ÚJ VERZIÓT hoz létre tervezetként
   (`elozo_verzio_id` az előzőre mutat); addig a régi jóváhagyott marad
   érvényben.

A kézikönyv nem ad jogot semmire: csak leírás. Szabályt nem aktivál,
jogosultságot és policyt nem változtat.
"""

from __future__ import annotations

import hashlib
import inspect
import re
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.admin_agent import MemoryChunk

HATOKOR = "kezikonyv"
TECHNIKAI = "kezikonyv_technikai"
UZLETI = "kezikonyv_uzleti"
TERVEZET = "tervezet"

#: Egy szakasz legfeljebb ennyi karakter (a modell elé ennél is rövidebb megy).
MAX_SZAKASZ = 6000
#: A kereséskor a modell elé kerülő részlet hossza.
KIVONAT = 1500

#: Pénzügyi tartalom: csak a /penzugyek oldalt látó felhasználó kapja meg.
_PENZUGYI_MODELLEK = frozenset({"finance", "bejovo_szamla", "utalas_felvezetes", "project_szamlazo", "kotelezettseg"})
_DOKUMENTUM_OLDAL = {"07-penzugyek": "/penzugyek"}


def _docs_mappa() -> Path | None:
    """A `docs/kezikonyv` mappa, ha a futtatókörnyezetben elérhető (a backend
    konténerbe nem feltétlenül kerül bele — akkor csak a modellekből dolgozunk)."""
    for szulo in Path(__file__).resolve().parents:
        jelolt = szulo / "docs" / "kezikonyv"
        if jelolt.is_dir():
            return jelolt
    return None


def _hash(szoveg: str) -> str:
    return hashlib.sha256(szoveg.encode("utf-8")).hexdigest()[:16]


# ── Forrás-szakaszok ──────────────────────────────────────────────────────────


_MEZO_SOR = re.compile(r"^\s+(\w+): Mapped\[")


def _mezo_megjegyzesek(cls) -> dict[str, str]:
    """A modell forrásában a mezők előtti `#:` sorok és a sor végi `# ...`
    megjegyzések — ezek a mezők hiteles, magyar leírásai."""
    try:
        sorok = inspect.getsource(cls).splitlines()
    except (OSError, TypeError):
        return {}
    ki: dict[str, str] = {}
    gyujto: list[str] = []
    for sor in sorok:
        s = sor.strip()
        if s.startswith("#:"):
            gyujto.append(s[2:].strip())
            continue
        m = _MEZO_SOR.match(sor)
        if m:
            reszek = list(gyujto)
            if "  # " in sor:
                reszek.append(sor.split("  # ", 1)[1].strip())
            if reszek:
                ki[m.group(1)] = " ".join(reszek)
        gyujto = []
    return ki


def _modell_szakaszok() -> list[dict]:
    from app.core.database import Base

    ki: list[dict] = []
    for mapper in sorted(Base.registry.mappers, key=lambda mp: mp.class_.__name__):
        cls = mapper.class_
        tabla = getattr(cls, "__tablename__", None)
        if not tabla:
            continue
        modul = cls.__module__.rsplit(".", 1)[-1]
        leiras = inspect.cleandoc(cls.__doc__ or "").strip()
        megj = _mezo_megjegyzesek(cls)
        mezok: list[str] = []
        for oszlop in mapper.columns:
            if oszlop.table.name != tabla:
                continue
            reszek = [str(oszlop.type).lower()]
            reszek.append("opcionális" if oszlop.nullable else "kötelező")
            for fk in oszlop.foreign_keys:
                reszek.append(f"→ {fk.column.table.name}")
            sor = f"- {oszlop.key} ({', '.join(reszek)})"
            if megj.get(oszlop.key):
                sor += f": {megj[oszlop.key]}"
            mezok.append(sor)
        tartalom = f"Adatmodell: {cls.__name__} (tábla: {tabla}, modul: {modul})\n"
        if leiras:
            tartalom += f"\n{leiras}\n"
        tartalom += "\nMezők:\n" + "\n".join(mezok)
        ki.append({
            "kulcs": f"modell:{cls.__name__}",
            "cim": f"{cls.__name__} ({tabla})",
            "tartalom": tartalom[:MAX_SZAKASZ],
            "forras_tipus": "modell",
            "oldal": "/penzugyek" if modul in _PENZUGYI_MODELLEK else None,
        })
    return ki


def _dokumentum_szakaszok() -> list[dict]:
    mappa = _docs_mappa()
    if mappa is None:
        return []
    ki: list[dict] = []
    for fajl in sorted(mappa.glob("*.md")):
        if fajl.name.lower() == "readme.md":
            continue
        szoveg = fajl.read_text(encoding="utf-8")
        cim_m = re.search(r"^# (.+)$", szoveg, re.M)
        fcim = cim_m.group(1).strip() if cim_m else fajl.stem
        # `## ` fejezetenként egy szakasz; a bevezető (az első ## előtt) külön.
        darabok = re.split(r"^## ", szoveg, flags=re.M)
        for i, darab in enumerate(darabok):
            darab = darab.strip()
            if not darab:
                continue
            if i == 0:
                fej, torzs = "Bevezető", re.sub(r"^# .+$", "", darab, count=1, flags=re.M).strip()
            else:
                fej, _, torzs = darab.partition("\n")
                fej, torzs = fej.strip(), torzs.strip()
            if len(torzs) < 40:
                continue
            ki.append({
                "kulcs": f"dok:{fajl.stem}#{fej}",
                "cim": f"{fcim} — {fej}",
                "tartalom": torzs[:MAX_SZAKASZ],
                "forras_tipus": "dokumentum",
                "oldal": _DOKUMENTUM_OLDAL.get(fajl.stem),
            })
    return ki


def forras_szakaszok() -> list[dict]:
    """Az összes gépi forrás-szakasz (a DB-t nem érinti)."""
    return _modell_szakaszok() + _dokumentum_szakaszok()


# ── Tervezet-generálás, jóváhagyás, verziók ───────────────────────────────────


def _kulcs(m: MemoryChunk) -> str | None:
    return (m.hatokor_reszletek or {}).get("szakasz_kulcs")


def _legutobbi_verziok(db: Session) -> dict[str, MemoryChunk]:
    """Szakasz-kulcsonként a legmagasabb verzió (a visszavontakat is beleértve:
    egy elvetett tervezet ugyanarra a forrásra nem jön újra)."""
    ki: dict[str, MemoryChunk] = {}
    for m in db.scalars(
        select(MemoryChunk).where(MemoryChunk.hatokor == HATOKOR).order_by(MemoryChunk.verzio.asc(), MemoryChunk.id.asc())
    ).all():
        k = _kulcs(m)
        if k:
            ki[k] = m
    return ki


def tervezet_generalas(db: Session, *, szakaszok: list[dict] | None = None) -> dict:
    """A forrásokból TERVEZET szakaszok. Csak az új vagy megváltozott forrásból
    lesz új sor (új verzió); a meglévő, jóváhagyott tudás érintetlen marad.
    Idempotens: változatlan forrásra másodszor nem jön semmi."""
    szakaszok = forras_szakaszok() if szakaszok is None else szakaszok
    legutobbi = _legutobbi_verziok(db)
    uj = frissult = valtozatlan = 0
    for sz in szakaszok:
        h = _hash(sz["tartalom"])
        elozo = legutobbi.get(sz["kulcs"])
        if elozo is not None and elozo.forras_verzio == h:
            valtozatlan += 1
            continue
        m = MemoryChunk(
            hatokor=HATOKOR,
            tartalom=sz["tartalom"],
            forras=f"kezikonyv:{sz['kulcs']}"[:120],
            forras_verzio=h,
            minosites=TERVEZET,
            tanulasi_halmaz="jovahagyott",
            ervenyes=False,
            visszavont=False,
            tudas_fajta=TECHNIKAI,
            bizonyitek_szint="forras",
            hatokor_reszletek={
                "szakasz_kulcs": sz["kulcs"], "cim": sz["cim"], "forras_tipus": sz["forras_tipus"],
                "oldal": sz.get("oldal"),
            },
            verzio=(elozo.verzio + 1) if elozo is not None else 1,
            elozo_verzio_id=elozo.id if elozo is not None else None,
        )
        db.add(m)
        if elozo is None:
            uj += 1
        else:
            frissult += 1
    db.flush()
    return {"uj": uj, "uj_verzio": frissult, "valtozatlan": valtozatlan}


class KezikonyvHiba(ValueError):
    pass


def _szakasz(db: Session, szakasz_id: int) -> MemoryChunk:
    m = db.get(MemoryChunk, szakasz_id)
    if m is None or m.hatokor != HATOKOR:
        raise KezikonyvHiba("A kézikönyv-szakasz nem található.")
    return m


def uzleti_tervezet(db: Session, *, cim: str, tartalom: str, oldal: str | None = None,
                    elozo_id: int | None = None) -> MemoryChunk:
    """ÜZLETI ELJÁRÁS tervezete, emberi szövegből. Ugyanúgy jóváhagyásra vár,
    mint a technikai tervezet; addig sehol nem használható."""
    cim, tartalom = (cim or "").strip(), (tartalom or "").strip()
    if not cim or not tartalom:
        raise KezikonyvHiba("A címet és a leírást is meg kell adni.")
    elozo = _szakasz(db, elozo_id) if elozo_id else None
    kulcs = _kulcs(elozo) if elozo is not None else f"uzleti:{_hash(cim + datetime.now(timezone.utc).isoformat())}"
    m = MemoryChunk(
        hatokor=HATOKOR,
        tartalom=tartalom[:MAX_SZAKASZ],
        forras=f"kezikonyv:{kulcs}"[:120],
        forras_verzio=_hash(tartalom),
        minosites=TERVEZET,
        tanulasi_halmaz="jovahagyott",
        ervenyes=False,
        visszavont=False,
        tudas_fajta=UZLETI,
        bizonyitek_szint="forras",
        hatokor_reszletek={"szakasz_kulcs": kulcs, "cim": cim[:200], "forras_tipus": "emberi", "oldal": oldal},
        verzio=(elozo.verzio + 1) if elozo is not None else 1,
        elozo_verzio_id=elozo.id if elozo is not None else None,
    )
    db.add(m)
    db.flush()
    return m


def tervezet_szerkesztes(db: Session, szakasz_id: int, tartalom: str) -> MemoryChunk:
    """Tervezet szövegének javítása jóváhagyás előtt. Jóváhagyott szakasz nem
    írható át helyben: annak új verziót kell írni (`uzleti_tervezet`)."""
    m = _szakasz(db, szakasz_id)
    if m.minosites != TERVEZET or m.ervenyes or m.visszavont:
        raise KezikonyvHiba("Csak jóváhagyásra váró tervezet szerkeszthető.")
    tartalom = (tartalom or "").strip()
    if not tartalom:
        raise KezikonyvHiba("A szöveg nem lehet üres.")
    m.tartalom = tartalom[:MAX_SZAKASZ]
    return m


def jovahagy(db: Session, szakasz_id: int, jovahagyo_id: int | None) -> MemoryChunk:
    """A tervezet jóváhagyása: használhatóvá válik, a szakasz korábbi
    jóváhagyott verziójának érvényessége lezárul (a régi sor megmarad)."""
    m = _szakasz(db, szakasz_id)
    if m.visszavont:
        raise KezikonyvHiba("Elvetett tervezet nem hagyható jóvá.")
    if m.ervenyes:
        return m
    most = datetime.now(timezone.utc)
    kulcs = _kulcs(m)
    for regi in db.scalars(
        select(MemoryChunk).where(
            MemoryChunk.hatokor == HATOKOR, MemoryChunk.ervenyes.is_(True), MemoryChunk.id != m.id,
        )
    ).all():
        if _kulcs(regi) == kulcs and regi.ervenyes_ig is None:
            regi.ervenyes_ig = most
    m.ervenyes = True
    m.minosites = "jovahagyott"
    m.jovahagyta_id = jovahagyo_id
    m.jovahagyva_at = most
    m.ervenyes_tol = m.ervenyes_tol or most
    return m


def elvet(db: Session, szakasz_id: int) -> MemoryChunk:
    """Tervezet elvetése VAGY jóváhagyott szakasz visszavonása: többé nem
    használható, de nem törlődik (a napló és a verziólánc megmarad)."""
    m = _szakasz(db, szakasz_id)
    m.visszavont = True
    m.ervenyes = False
    m.minosites = "elvetett"
    return m


# ── Keresés ──────────────────────────────────────────────────────────────────


def _hasznalhato_szakaszok(db: Session) -> list[MemoryChunk]:
    from app.admin_agent.memory import hasznalhato

    return list(db.scalars(
        select(MemoryChunk).where(MemoryChunk.hatokor == HATOKOR, *hasznalhato()).order_by(MemoryChunk.id.desc())
    ).all())


def szakasz_sor(m: MemoryChunk, *, kivonat: bool = False) -> dict:
    r = m.hatokor_reszletek or {}
    tartalom = m.tartalom
    if kivonat and len(tartalom) > KIVONAT:
        tartalom = tartalom[:KIVONAT].rstrip() + " …"
    return {
        "id": m.id,
        "fajta": m.tudas_fajta,
        "cim": r.get("cim"),
        "szakasz_kulcs": r.get("szakasz_kulcs"),
        "forras_tipus": r.get("forras_tipus"),
        "oldal": r.get("oldal"),
        "tartalom": tartalom,
        "verzio": m.verzio,
        "elozo_verzio_id": m.elozo_verzio_id,
        "allapot": "elvetve" if m.visszavont else ("jovahagyva" if m.ervenyes else "tervezet"),
        "ervenyes_ig": m.ervenyes_ig.isoformat() if m.ervenyes_ig else None,
        "jovahagyva_at": m.jovahagyva_at.isoformat() if m.jovahagyva_at else None,
        "letrehozva": m.created_at.isoformat() if m.created_at else None,
    }


def kereses(db: Session, szoveg: str, *, limit: int = 4, engedelyezett=None) -> list[dict]:
    """A kérdéshez RELEVÁNS jóváhagyott szakaszok (szó-egyezés a címben és a
    szövegben; a cím-egyezés többet ér). Soha nem a teljes kézikönyv.

    `engedelyezett`: függvény (oldal-kulcs -> bool); ha meg van adva, az
    oldalhoz kötött szakasz csak akkor jön, ha a felhasználó látja az oldalt.
    Az üzleti eljárás előrébb sorolódik az azonos pontszámú technikainál."""
    from app.admin_agent.memory import _jellegzetes, _tokenek, egyezes

    tokenek = _tokenek(szoveg)
    jell = _jellegzetes(szoveg)
    if not tokenek:
        return []
    pont: list[tuple[float, MemoryChunk]] = []
    for m in _hasznalhato_szakaszok(db):
        oldal = (m.hatokor_reszletek or {}).get("oldal")
        if oldal and engedelyezett is not None and not engedelyezett(oldal):
            continue
        cim_t = _tokenek((m.hatokor_reszletek or {}).get("cim"))
        alap = egyezes(tokenek, jell, cim_t | _tokenek(m.tartalom))
        t = alap + len(tokenek & cim_t) if alap else 0  # a cím-egyezés többet ér
        if t:
            pont.append((t + (0.5 if m.tudas_fajta == UZLETI else 0.0), m))
    pont.sort(key=lambda x: (-x[0], -x[1].id))
    return [szakasz_sor(m, kivonat=True) for _, m in pont[:limit]]


def lista(db: Session, *, allapot: str | None = None, fajta: str | None = None, q: str | None = None,
          limit: int = 200) -> dict:
    """A Tudástár kézikönyv-nézete: szakaszok állapot szerint + összesítő."""
    felt = [MemoryChunk.hatokor == HATOKOR]
    if allapot == "tervezet":
        felt += [MemoryChunk.ervenyes.is_(False), MemoryChunk.visszavont.is_(False)]
    elif allapot == "jovahagyva":
        felt += [MemoryChunk.ervenyes.is_(True)]
    elif allapot == "elvetve":
        felt += [MemoryChunk.visszavont.is_(True)]
    if fajta in (TECHNIKAI, UZLETI):
        felt.append(MemoryChunk.tudas_fajta == fajta)
    sorok = db.scalars(select(MemoryChunk).where(*felt).order_by(MemoryChunk.id.desc()).limit(2000)).all()
    if q and q.strip():
        from app.admin_agent.memory import partner_kulcs

        k = partner_kulcs(q)
        sorok = [m for m in sorok if k in partner_kulcs(((m.hatokor_reszletek or {}).get("cim") or "") + " " + m.tartalom)]
    osszes = db.execute(
        select(MemoryChunk.ervenyes, MemoryChunk.visszavont, func.count(MemoryChunk.id))
        .where(MemoryChunk.hatokor == HATOKOR)
        .group_by(MemoryChunk.ervenyes, MemoryChunk.visszavont)
    ).all()
    osszesito = {"tervezet": 0, "jovahagyva": 0, "elvetve": 0}
    for ervenyes, visszavont, db_ in osszes:
        osszesito["elvetve" if visszavont else ("jovahagyva" if ervenyes else "tervezet")] += db_
    return {"elemek": [szakasz_sor(m) for m in sorok[:limit]], "osszesito": osszesito}


def verziok(db: Session, szakasz_id: int) -> list[dict]:
    """A szakasz teljes verzióláncolata (legújabb elöl)."""
    m = _szakasz(db, szakasz_id)
    kulcs = _kulcs(m)
    sorok = [
        x for x in db.scalars(
            select(MemoryChunk).where(MemoryChunk.hatokor == HATOKOR).order_by(MemoryChunk.verzio.desc(), MemoryChunk.id.desc())
        ).all()
        if _kulcs(x) == kulcs
    ]
    return [szakasz_sor(x) for x in sorok]
