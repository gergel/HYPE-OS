"""Lara API — beszélgetés, tanítás, Tudáspróba, kézikönyv, tanulási folyamat,
minőségmérés, szakmai szabálytesztek (2026-09).

Ugyanaz az `/admin-agent` oldal-jogosultság és vészleállítás-őr, mint a
többi Lara-végpontnál (leállított Laránál minden nem-olvasó kérés 423).

Jogosultság:
- beszélgetés, Tudáspróba-eredmények, kézikönyv és folyamat olvasása:
  `view`;
- tanítás mentése, kézikönyv-tervezet, Tudáspróba futtatása, szakmai eset:
  `edit`;
- tudás AZONNALI használhatóvá tétele (a tanításnál), kézikönyv-jóváhagyás:
  `delete` (a Tudástár meglévő tudás-aktiválási joga).
A beszélgetés csak a gazdájáé.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.routes.admin_agent import PAGE, _MINDEN_SZEREPKOR, _nem_leallitva
from app.core.database import get_db
from app.core.security import check_page_action, lathatja_e_az_oldalt, require_page_action
from app.models.admin_agent import PlaybookRule
from app.models.employee import Employee

router = APIRouter(prefix="/admin-agent", tags=["admin-agent"], dependencies=[Depends(_nem_leallitva)])

_view = require_page_action(PAGE, "view", *_MINDEN_SZEREPKOR)
_edit = require_page_action(PAGE, "edit", *_MINDEN_SZEREPKOR)
_delete = require_page_action(PAGE, "delete", *_MINDEN_SZEREPKOR)


def _van_joga(db: Session, user: Employee, muvelet: str) -> bool:
    try:
        check_page_action(db, user, PAGE, muvelet)
    except HTTPException:
        return False
    return True


def _jogok(db: Session, user: Employee) -> list[str]:
    return [m for m in ("view", "edit", "delete") if _van_joga(db, user, m)]


def _besz(db: Session, user: Employee, beszelgetes_id: int):
    from app.admin_agent.beszelgetes import sajat

    try:
        return sajat(db, user, beszelgetes_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ── Beszélgetés ──────────────────────────────────────────────────────────────


class PreferenciaIn(BaseModel):
    #: Hogyan szólítson Lara (üres = ne szólítson néven). Csak a saját.
    megszolitas: str | None = Field(default=None, max_length=40)


@router.patch("/chat/preferences")
def chat_preferencia(body: PreferenciaIn, db: Session = Depends(get_db), user: Employee = Depends(_view)):
    from app.admin_agent.beszelgetes import megszolitas_beallit

    nev = megszolitas_beallit(db, user, body.megszolitas)
    db.commit()
    return {"megszolitas": nev}


@router.get("/chat")
def chat_lista(
    db: Session = Depends(get_db), user: Employee = Depends(_view), mod: str | None = Query(default=None),
):
    from app.admin_agent import nyomozas, szemelyiseg
    from app.admin_agent.beszelgetes import lista

    return {
        "beszelgetesek": lista(db, user, mod=mod),
        "megszolitas": szemelyiseg.megszolitas(db, user.id),
        "modell_elerheto": nyomozas.elerheto(),
        "szemelyiseg_verzio": szemelyiseg.aktiv_verzio(db),
        "jogok": _jogok(db, user),
    }


class UjBeszelgetesIn(BaseModel):
    mod: str = "kerdez"


@router.post("/chat")
def chat_uj(body: UjBeszelgetesIn, db: Session = Depends(get_db), user: Employee = Depends(_view)):
    from app.admin_agent.beszelgetes import BeszelgetesHiba, uj

    try:
        b = uj(db, user, body.mod)
    except BeszelgetesHiba as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return {"id": b.id, "cim": b.cim, "mod": b.mod}


@router.get("/chat/{beszelgetes_id}")
def chat_uzenetek(beszelgetes_id: int, db: Session = Depends(get_db), user: Employee = Depends(_view)):
    from app.admin_agent.beszelgetes import uzenetek

    b = _besz(db, user, beszelgetes_id)
    return {"id": b.id, "cim": b.cim, "mod": b.mod, "uzenetek": uzenetek(db, b)}


class KerdesIn(BaseModel):
    szoveg: str = Field(min_length=1, max_length=4000)
    #: Tudáspróba: az elvárt válasz (Lara NEM látja; csak az összevetéshez).
    elvart: str | None = Field(default=None, max_length=4000)


@router.post("/chat/{beszelgetes_id}/uzenet")
def chat_kerdes(beszelgetes_id: int, body: KerdesIn, db: Session = Depends(get_db), user: Employee = Depends(_view)):
    """Kérdés Larához. CSAK OLVAS: a válasz a jóváhagyott tudásból és a
    kérdező jogosultságával futó olvasó eszközökből készül."""
    from app.admin_agent.beszelgetes import BeszelgetesHiba, uzenet_sor, valaszol

    b = _besz(db, user, beszelgetes_id)
    extra = {"proba": True, "elvart": body.elvart.strip()} if (b.mod == "proba" and body.elvart) else None
    try:
        k, v = valaszol(
            db, user, b, body.szoveg, jogosultsagok=_jogok(db, user),
            engedelyezett=lambda oldal: lathatja_e_az_oldalt(db, user, oldal), extra_adat=extra,
        )
    except BeszelgetesHiba as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return {"kerdes": uzenet_sor(k), "valasz": uzenet_sor(v), "cim": b.cim}


@router.post("/chat/{beszelgetes_id}/archive")
def chat_archival(beszelgetes_id: int, db: Session = Depends(get_db), user: Employee = Depends(_view)):
    from app.admin_agent.beszelgetes import archival

    archival(db, _besz(db, user, beszelgetes_id))
    db.commit()
    return {"ok": True}


class ErtekelesIn(BaseModel):
    ertekeles: str
    megjegyzes: str | None = Field(default=None, max_length=2000)


@router.post("/chat/uzenet/{uzenet_id}/ertekeles")
def chat_ertekeles(uzenet_id: int, body: ErtekelesIn, db: Session = Depends(get_db), user: Employee = Depends(_view)):
    from app.admin_agent.beszelgetes import BeszelgetesHiba, ertekel, uzenet_sor

    try:
        u = ertekel(db, user, uzenet_id, body.ertekeles, body.megjegyzes)
    except BeszelgetesHiba as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return uzenet_sor(u)


# ── Tanítás ──────────────────────────────────────────────────────────────────


class TanitasIn(BaseModel):
    szoveg: str = Field(min_length=1, max_length=3000)
    hatokor: str | None = None
    partner: str | None = Field(default=None, max_length=300)
    #: Ha egy (hibásnak értékelt) Lara-válaszból indul.
    kapcsolodo_uzenet_id: int | None = None


@router.post("/chat/{beszelgetes_id}/tanitas")
def tanitas_elonezet(beszelgetes_id: int, body: TanitasIn, db: Session = Depends(get_db),
                     user: Employee = Depends(_edit)):
    """Mit tanulna meg Lara? Csak ELŐNÉZET — a tudásba még semmi nem kerül."""
    from app.admin_agent.beszelgetes import uzenet_sor
    from app.admin_agent.tanitas import TanitasHiba, elonezet_uzenet

    b = _besz(db, user, beszelgetes_id)
    try:
        u1, u2 = elonezet_uzenet(db, user, b, body.szoveg, joga=_van_joga(db, user, "delete"), hatokor=body.hatokor,
                                 partner=body.partner, kapcsolodo_uzenet_id=body.kapcsolodo_uzenet_id)
    except TanitasHiba as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return {"kerdes": uzenet_sor(u1), "valasz": uzenet_sor(u2), "cim": b.cim}


class TanitasMentesIn(BaseModel):
    #: A felhasználó javításai az előnézeten (fajta, allitas, hatokor, partner,
    #: projektkod, kivetelek, ervenyes_tol, ervenyes_ig).
    modositott: dict = Field(default_factory=dict)


@router.post("/chat/{beszelgetes_id}/tanitas/{uzenet_id}/mentes")
def tanitas_mentes(beszelgetes_id: int, uzenet_id: int, body: TanitasMentesIn, db: Session = Depends(get_db),
                   user: Employee = Depends(_edit)):
    """Az előnézet mentése. Tudás-aktiválási joggal azonnal használható,
    anélkül jelölt. Az általános szabályból csak PISZKOZAT lesz."""
    from app.admin_agent.tanitas import TanitasHiba, megerosit_uzenet

    b = _besz(db, user, beszelgetes_id)
    try:
        e = megerosit_uzenet(db, user, b, uzenet_id, body.modositott, joga=_van_joga(db, user, "delete"))
    except TanitasHiba as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return e


# ── Tudáspróba ───────────────────────────────────────────────────────────────


@router.get("/tudasproba")
def tudasproba_allapot(db: Session = Depends(get_db), _user: Employee = Depends(_view)):
    from app.admin_agent.tudasproba import korabbi_futasok
    from app.admin_agent.ugyek import vizsga_arany, vizsgakeszlet_be

    return {"futasok": korabbi_futasok(db), "vizsgakeszlet": vizsgakeszlet_be(db), "vizsga_arany": vizsga_arany(db)}


class ProbaIn(BaseModel):
    esetszam: int = Field(default=20, ge=1, le=200)


@router.post("/tudasproba/szamla")
def tudasproba_szamla(body: ProbaIn, db: Session = Depends(get_db), user: Employee = Depends(_edit)):
    from app.admin_agent.tudasproba import szamla_vizsga

    e = szamla_vizsga(db, esetszam=body.esetszam, inditotta_id=user.id)
    db.commit()
    return e


# ── Kézikönyv ────────────────────────────────────────────────────────────────


@router.get("/kezikonyv")
def kezikonyv_lista(
    db: Session = Depends(get_db), user: Employee = Depends(_view),
    allapot: str | None = Query(default=None), fajta: str | None = Query(default=None),
    q: str | None = Query(default=None, max_length=200),
):
    from app.admin_agent.kezikonyv import lista

    e = lista(db, allapot=allapot, fajta=fajta, q=q)
    # Az oldalhoz kötött (pl. pénzügyi) szakasz csak annak látszik, aki látja az oldalt.
    e["elemek"] = [x for x in e["elemek"] if not x.get("oldal") or lathatja_e_az_oldalt(db, user, x["oldal"])]
    return e


@router.post("/kezikonyv/generalas")
def kezikonyv_generalas(db: Session = Depends(get_db), _user: Employee = Depends(_edit)):
    """Technikai TERVEZETEK a kódból és a docs/kezikonyv fájlokból. Új vagy
    megváltozott forrásból új verzió (tervezet); a jóváhagyott marad érvényben."""
    from app.admin_agent.kezikonyv import tervezet_generalas

    e = tervezet_generalas(db)
    db.commit()
    return e


class UzletiIn(BaseModel):
    cim: str = Field(min_length=1, max_length=200)
    tartalom: str = Field(min_length=1, max_length=6000)
    oldal: str | None = Field(default=None, max_length=100)
    elozo_id: int | None = None


@router.post("/kezikonyv")
def kezikonyv_uzleti(body: UzletiIn, db: Session = Depends(get_db), _user: Employee = Depends(_edit)):
    from app.admin_agent.kezikonyv import KezikonyvHiba, szakasz_sor, uzleti_tervezet

    try:
        m = uzleti_tervezet(db, cim=body.cim, tartalom=body.tartalom, oldal=body.oldal, elozo_id=body.elozo_id)
    except KezikonyvHiba as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return szakasz_sor(m)


class SzakaszPatchIn(BaseModel):
    tartalom: str = Field(min_length=1, max_length=6000)


@router.patch("/kezikonyv/{szakasz_id}")
def kezikonyv_szerkesztes(szakasz_id: int, body: SzakaszPatchIn, db: Session = Depends(get_db),
                          _user: Employee = Depends(_edit)):
    from app.admin_agent.kezikonyv import KezikonyvHiba, szakasz_sor, tervezet_szerkesztes

    try:
        m = tervezet_szerkesztes(db, szakasz_id, body.tartalom)
    except KezikonyvHiba as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return szakasz_sor(m)


@router.post("/kezikonyv/{szakasz_id}/jovahagyas")
def kezikonyv_jovahagyas(szakasz_id: int, db: Session = Depends(get_db), user: Employee = Depends(_delete)):
    from app.admin_agent.kezikonyv import KezikonyvHiba, jovahagy, szakasz_sor

    try:
        m = jovahagy(db, szakasz_id, user.id)
    except KezikonyvHiba as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return szakasz_sor(m)


@router.post("/kezikonyv/{szakasz_id}/elvetes")
def kezikonyv_elvetes(szakasz_id: int, db: Session = Depends(get_db), _user: Employee = Depends(_edit)):
    from app.admin_agent.kezikonyv import KezikonyvHiba, elvet, szakasz_sor

    try:
        m = elvet(db, szakasz_id)
    except KezikonyvHiba as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return szakasz_sor(m)


@router.get("/kezikonyv/{szakasz_id}/verziok")
def kezikonyv_verziok(szakasz_id: int, db: Session = Depends(get_db), _user: Employee = Depends(_view)):
    from app.admin_agent.kezikonyv import KezikonyvHiba, verziok

    try:
        return {"verziok": verziok(db, szakasz_id)}
    except KezikonyvHiba as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ── Tanulási folyamat + minőség ──────────────────────────────────────────────


@router.get("/folyamat")
def folyamat_allapot(db: Session = Depends(get_db), _user: Employee = Depends(_view)):
    from app.admin_agent import folyamat, visszacsatolas

    return {**folyamat.allapot(db), "visszacsatolas": visszacsatolas.allapot(db)}


@router.get("/memory/{memory_id}/trace")
def memory_nyomvonal(memory_id: int, db: Session = Depends(get_db), _user: Employee = Depends(_view)):
    from app.admin_agent.folyamat import nyomvonal

    n = nyomvonal(db, memory_id)
    if n is None:
        raise HTTPException(status_code=404, detail="A tudás-darab nem található.")
    return n


@router.get("/minoseg")
def minoseg_meres(db: Session = Depends(get_db), _user: Employee = Depends(_view)):
    from app.admin_agent.minoseg import meres

    return meres(db)


# ── Szakmai szabálytesztek ───────────────────────────────────────────────────


def _szabaly(db: Session, rule_id: int) -> PlaybookRule:
    r = db.get(PlaybookRule, rule_id)
    if r is None:
        raise HTTPException(status_code=404, detail="A szabály nem található.")
    return r


@router.get("/rules/{rule_id}/szakmai")
def szakmai_lista(rule_id: int, db: Session = Depends(get_db), _user: Employee = Depends(_view)):
    from app.admin_agent.szakmai_eval import futtat

    return futtat(db, _szabaly(db, rule_id))


@router.post("/rules/{rule_id}/szakmai/generalas")
def szakmai_generalas(rule_id: int, db: Session = Depends(get_db), _user: Employee = Depends(_edit)):
    from app.admin_agent.szakmai_eval import SzakmaiHiba, esetek_generalasa

    try:
        e = esetek_generalasa(db, _szabaly(db, rule_id))
    except SzakmaiHiba as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return e


class SzakmaiEsetIn(BaseModel):
    fajta: str
    bemenet: dict
    elvart: dict | None = None
    nev: str | None = Field(default=None, max_length=200)


@router.post("/rules/{rule_id}/szakmai")
def szakmai_uj(rule_id: int, body: SzakmaiEsetIn, db: Session = Depends(get_db), _user: Employee = Depends(_edit)):
    from app.admin_agent.szakmai_eval import SzakmaiHiba, futtat, uj_eset

    r = _szabaly(db, rule_id)
    try:
        uj_eset(db, r, fajta=body.fajta, bemenet=body.bemenet, elvart=body.elvart, nev=body.nev)
    except SzakmaiHiba as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return futtat(db, r)
