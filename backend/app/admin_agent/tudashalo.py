"""Lara — tudásháló: a megtanult tudás kapcsolati gráfja.

A Tudásháló oldal ebből rajzolja a „glóriát": minden pont egy dolog, amiről
Lara tud (partner, projektkód, számla-cél, szabály, témakör), minden vonal egy
kapcsolat közöttük. A gráf KIZÁRÓLAG valós, rögzített tudásból épül:

* megfigyelt emberi munka (szerződés, TIG, kiadás — a megfigyelő forrásai),
* a visszajátszott számlák végső emberi döntései,
* a szabályok (partner / cél / projektkód feltételekkel),
* az emberi javítások.

Egy kapcsolat BIZONYOSSÁGA a mögötte álló bizonyítékok súlyából jön: a
jóváhagyott példa és az élesített szabály erős, a még jóvá nem hagyott jelölt
gyenge, a régi (Notion-korszakbeli) tudás kisebb súlyú. Minden kapcsolatnak és
pontnak van „első megjelenése" — ebből játssza le a felület, hogyan nőtt a tudás.

Csak olvas. Nem állít semmit, ami nincs az adatban.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin_agent.memory import partner_kulcs
from app.admin_agent.observer import FELRETEVE, tanulas_kezdete
from app.admin_agent.visszajatszas import CEL_CIMKE
from app.models.admin_agent import AdminTask, Correction, MemoryChunk, PlaybookRule, SourceEvent
from app.models.project_code import ProjectCode

TEMAK = ("szamla", "tig", "szerzodes", "email", "asszisztens", "projekt")
TEMA_CIMKE = {
    "szamla": "Számlák",
    "tig": "TIG-ek",
    "szerzodes": "Szerződések",
    "email": "E-mailek",
    "asszisztens": "AI asszisztens",
    "projekt": "Projektek, rendszer",
}
#: A megfigyelő táblái → témakör. A bevétel (megrendelői fizetés) és az
#: utalás-felvezetés pénzügyi tanulság, ezért a Számlák témához tartozik; a
#: projektkód-komment és az árajánlat a Projektek témához.
_TABLA_TEMA = {
    "szerzodes": "szerzodes",
    "tig": "tig",
    "belsos_tig": "tig",
    "kiadas": "szamla",
    "megrendeloi_szerzodes": "szerzodes",
    "megrendeloi_tig": "tig",
    "bevetel": "szamla",
    "utalas": "szamla",
    "projektkod_komment": "projekt",
    "arajanlat": "projekt",
}
#: A törölt rekord feladattípusa (lásd observer.TOROLT_TABLAK) → témakör.
_HATOKOR_TEMA = {"szamla": "szamla", "kintlevoseg": "szamla", "tig": "tig", "szerzodes": "szerzodes", "projektkod": "projekt"}

#: Bizonyíték-súlyok.
S_JOVAHAGYOTT = 1.0
S_JELOLT = 0.25
S_MEGFIGYELES = 0.1  # lezáratlan munka: csak „látta", még nem tanulság
S_JAVITAS = 0.6
S_AKTIV_SZABALY = 3.0
S_SZABALY_JELOLT = 0.5
#: A rendszer-figyelés ténye (projektkód-életút): valós, de nem döntés.
S_RENDSZER = 0.5
REGI_SZORZO = 0.4

MAX_PARTNER = 220
MAX_KOD = 140
MAX_PELDA = 3


def bizonyossag(suly: float) -> float:
    """0..1: 1 jóváhagyott példa ≈ 0,39; 3 ≈ 0,78; egy élesített szabály ≈ 0,78."""
    return round(1 - math.exp(-suly / 2), 3)


def _iso(t: datetime | None) -> str | None:
    if t is None:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return t.isoformat()


@dataclass
class _El:
    suly: float = 0.0
    t: datetime | None = None
    jovahagyott: int = 0
    jelolt: int = 0
    egyeb: int = 0

    def hozzaad(self, suly: float, t: datetime | None, fajta: str) -> None:
        self.suly += suly
        if t is not None and (self.t is None or t < self.t):
            self.t = t
        if fajta == "jovahagyott":
            self.jovahagyott += 1
        elif fajta == "jelolt":
            self.jelolt += 1
        else:
            self.egyeb += 1


@dataclass
class _Pont:
    id: str
    fajta: str  # core | tema | partner | kod | cel | szabaly
    cimke: str
    tema: str | None = None
    tema_suly: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    peldak: list[str] = field(default_factory=list)
    allapot: str | None = None
    #: A ponthoz tartozó bizonyítékok száma (egy tétel egyszer számít).
    jovahagyott: int = 0
    jelolt: int = 0


class _Epito:
    def __init__(self) -> None:
        self.pontok: dict[str, _Pont] = {}
        self.elek: dict[tuple[str, str], _El] = defaultdict(_El)

    def pont(self, pid: str, fajta: str, cimke: str, tema: str | None = None) -> _Pont:
        p = self.pontok.get(pid)
        if p is None:
            p = self.pontok[pid] = _Pont(pid, fajta, cimke, tema)
        return p

    def el(self, a: str, b: str, suly: float, t: datetime | None, fajta: str) -> None:
        if a == b or suly <= 0:
            return
        kulcs = (a, b) if a < b else (b, a)
        self.elek[kulcs].hozzaad(suly, t, fajta)

    def tudas(
        self,
        *,
        tema: str,
        partner: str | None,
        kod_id: int | None,
        kod_cimke: str | None,
        cel: str | None,
        suly: float,
        t: datetime | None,
        fajta: str,
        szoveg: str | None,
    ) -> None:
        """Egy bizonyíték: partner ↔ téma, partner ↔ projektkód, partner ↔ cél."""
        if tema not in TEMAK:
            return
        tema_id = f"tema:{tema}"
        pk = partner_kulcs(partner)
        partner_id = f"partner:{pk}" if len(pk) >= 3 else None
        kod_pont = f"kod:{kod_id}" if kod_id else None
        if kod_pont:
            self.pont(kod_pont, "kod", kod_cimke or f"#{kod_id}")
        if cel:
            self.pont(f"cel:{cel}", "cel", CEL_CIMKE.get(cel, cel), "szamla")
        if kod_pont and fajta == "jovahagyott":
            self.pontok[kod_pont].jovahagyott += 1
        elif kod_pont and fajta == "jelolt":
            self.pontok[kod_pont].jelolt += 1
        if partner_id:
            p = self.pont(partner_id, "partner", (partner or pk).strip())
            p.tema_suly[tema] += suly
            if fajta == "jovahagyott":
                p.jovahagyott += 1
            elif fajta == "jelolt":
                p.jelolt += 1
            if szoveg and fajta == "jovahagyott" and len(p.peldak) < MAX_PELDA:
                p.peldak.append(szoveg[:240])
            self.el(tema_id, partner_id, suly, t, fajta)
            if kod_pont:
                self.el(partner_id, kod_pont, suly, t, fajta)
            if cel:
                self.el(partner_id, f"cel:{cel}", suly, t, fajta)
        elif kod_pont:
            self.el(tema_id, kod_pont, suly, t, fajta)
        if cel:
            self.el(tema_id, f"cel:{cel}", suly * 0.5, t, fajta)


def _pelda_allapot(m: MemoryChunk | None) -> tuple[float, str] | None:
    """(súly, fajta) egy példa állapotából; None = nem számít (elvetett / félretett)."""
    if m is None:
        return S_MEGFIGYELES, "egyeb"
    if m.visszavont or m.minosites == FELRETEVE:
        return None
    szorzo = REGI_SZORZO if m.regi_korszak else 1.0
    if m.ervenyes:
        return S_JOVAHAGYOTT * szorzo, "jovahagyott"
    return S_JELOLT * szorzo, "jelolt"


def _pelda_ido(m: MemoryChunk | None, alap: datetime | None) -> datetime | None:
    if m is not None and m.ervenyes and m.updated_at is not None:
        return m.updated_at  # a jóváhagyás (legutóbbi módosítás) ideje
    return (m.created_at if m is not None else None) or alap


def tudashalo(db: Session) -> dict:
    e = _Epito()
    e.pont("core", "core", "Lara")
    for t in TEMAK:
        e.pont(f"tema:{t}", "tema", TEMA_CIMKE[t], t)

    peldak = {
        m.forras: m
        for m in db.scalars(
            select(MemoryChunk).where(
                MemoryChunk.forras.like("megfigyeles:%")
                | MemoryChunk.forras.like("visszajatszas:%")
                | MemoryChunk.forras.like("levelezes:%")
                | MemoryChunk.forras.like("asszisztens:%")
            )
        ).all()
    }
    kod_sorok = db.scalars(select(ProjectCode)).all()
    kodok = {pc.id: pc.projektkod for pc in kod_sorok}
    megrendelok = {pc.id: pc.megrendelo_neve for pc in kod_sorok}

    # 0) A teljes rendszer figyelése: projektkód-életutak (TÉNY — a rendszer
    #    állapota; lásd admin_agent/rendszer.py). Megrendelő ↔ projektkód a
    #    „Projektek, rendszer" témában — a háló a rendszer ismeretével is nő.
    for m in db.scalars(
        select(MemoryChunk).where(MemoryChunk.forras.like("rendszer:projektkod:%"), MemoryChunk.visszavont.is_(False))
    ).all():
        azon = (m.forras or "").rsplit(":", 1)[-1]
        if not azon.isdigit():
            continue
        kod_id = int(azon)
        e.tudas(
            tema="projekt",
            partner=megrendelok.get(kod_id),
            kod_id=kod_id,
            kod_cimke=kodok.get(kod_id),
            cel=None,
            suly=S_RENDSZER * (REGI_SZORZO if m.regi_korszak else 1.0),
            t=m.created_at,
            fajta="jovahagyott",
            szoveg=None,
        )

    # 1) Megfigyelt emberi munka (rekordonként a legutóbbi esemény).
    utolso: dict[str, SourceEvent] = {}
    for se in db.scalars(
        select(SourceEvent).where(SourceEvent.forras == "megfigyeles").order_by(SourceEvent.id)
    ).all():
        utolso[se.forras_azonosito] = se
    for azon, se in utolso.items():
        m = se.metaadat or {}
        tabla = m.get("tabla") or azon.split(":")[0]
        tema = _HATOKOR_TEMA.get(m.get("tema_kulcs") or "") if tabla == "torles" else _TABLA_TEMA.get(tabla)
        allapot = _pelda_allapot(peldak.get(f"megfigyeles:{azon}"))
        if tema is None or allapot is None:
            continue
        pelda = peldak.get(f"megfigyeles:{azon}")
        kod_id = m.get("project_code_id")
        e.tudas(
            tema=tema,
            partner=m.get("partner"),
            kod_id=kod_id,
            kod_cimke=m.get("projektkod") or kodok.get(kod_id),
            cel=None,
            suly=allapot[0],
            t=_pelda_ido(pelda, se.created_at),
            fajta=allapot[1],
            szoveg=pelda.tartalom if pelda is not None else None,
        )

    # 2) Visszajátszott számlák (a végső emberi döntés).
    vj: dict[str, SourceEvent] = {}
    for se in db.scalars(
        select(SourceEvent).where(SourceEvent.forras == "visszajatszas").order_by(SourceEvent.id)
    ).all():
        vj[se.forras_azonosito] = se
    for azon, se in vj.items():
        m = se.metaadat or {}
        pelda = peldak.get(f"visszajatszas:{azon}")
        allapot = _pelda_allapot(pelda) if pelda is not None else (S_JELOLT, "jelolt")
        if allapot is None:
            continue
        vegso = m.get("vegso") or {}
        kod_idk = vegso.get("projektkod_idk") or [None]
        for kod_id in kod_idk:
            e.tudas(
                tema="szamla",
                partner=m.get("partner"),
                kod_id=kod_id,
                kod_cimke=kodok.get(kod_id),
                cel=vegso.get("tipus"),
                suly=allapot[0] / len(kod_idk),
                t=_pelda_ido(pelda, se.created_at),
                fajta=allapot[1],
                szoveg=pelda.tartalom if pelda is not None else None,
            )

    # 2b) Levelezés (szamla@ postafiók): szálanként a partner → e-mail téma.
    lv: dict[str, SourceEvent] = {}
    for se in db.scalars(
        select(SourceEvent).where(SourceEvent.forras == "levelezes").order_by(SourceEvent.id)
    ).all():
        lv[se.forras_azonosito] = se
    for azon, se in lv.items():
        m = se.metaadat or {}
        pelda = peldak.get(f"levelezes:{azon.split(':', 1)[-1]}")
        allapot = _pelda_allapot(pelda) if pelda is not None else None
        if allapot is None or m.get("automatikus"):
            continue
        e.tudas(
            tema="email",
            partner=m.get("partner"),
            kod_id=None,
            kod_cimke=None,
            cel=None,
            suly=allapot[0],
            t=_pelda_ido(pelda, se.created_at),
            fajta=allapot[1],
            szoveg=pelda.tartalom if pelda is not None else None,
        )

    # 2c) AI asszisztens: a lezárt kérés-körök a témájukhoz (partner nélkül —
    # a kérés maga a tudás; a partner a jelölt szövegéből kereshető).
    ak: dict[str, SourceEvent] = {}
    for se in db.scalars(
        select(SourceEvent).where(SourceEvent.forras == "asszisztens").order_by(SourceEvent.id)
    ).all():
        ak[se.forras_azonosito] = se
    for azon, se in ak.items():
        m = se.metaadat or {}
        pelda = peldak.get(f"asszisztens:{azon.split(':', 1)[-1]}")
        allapot = _pelda_allapot(pelda) if pelda is not None else None
        if allapot is None:
            continue
        e.tudas(
            tema=m.get("tema") if m.get("tema") in TEMAK else "asszisztens",
            partner=None,
            kod_id=None,
            kod_cimke=None,
            cel=None,
            suly=allapot[0],
            t=_pelda_ido(pelda, se.created_at),
            fajta=allapot[1],
            szoveg=pelda.tartalom if pelda is not None else None,
        )

    # 3) Emberi javítások (a feladat partnerével / projektkódjával).
    for c, t in db.execute(select(Correction, AdminTask).join(AdminTask, AdminTask.id == Correction.task_id)).all():
        e.tudas(
            tema=t.tipus,
            partner=t.partner_nev,
            kod_id=t.project_code_id,
            kod_cimke=kodok.get(t.project_code_id),
            cel=None,
            suly=S_JAVITAS,
            t=c.created_at,
            fajta="jelolt",
            szoveg=None,
        )

    # 4) Szabályok (a visszavontak nem tudás).
    for r in db.scalars(select(PlaybookRule).where(PlaybookRule.allapot != "retired")).all():
        tema = r.hatokor if r.hatokor in TEMAK else None
        if tema is None:
            continue
        aktiv = r.allapot == "active"
        suly = S_AKTIV_SZABALY if aktiv else S_SZABALY_JELOLT
        fajta = "jovahagyott" if aktiv else "jelolt"
        sid = f"szabaly:{r.id}"
        sp = e.pont(sid, "szabaly", r.cim, tema)
        sp.allapot = r.allapot
        sp.peldak = [r.tartalom[:240]]
        f = r.feltetelek or {}
        e.el(f"tema:{tema}", sid, suly, r.created_at, fajta)
        if f.get("partner"):
            pid = f"partner:{f['partner']}"
            e.pont(pid, "partner", f.get("partner_nev") or f["partner"]).tema_suly[tema] += suly
            e.el(sid, pid, suly, r.created_at, fajta)
        if f.get("cel_tipus"):
            e.pont(f"cel:{f['cel_tipus']}", "cel", CEL_CIMKE.get(f["cel_tipus"], f["cel_tipus"]), "szamla")
            e.el(sid, f"cel:{f['cel_tipus']}", suly, r.created_at, fajta)
        for kod_id in f.get("projektkod_idk") or []:
            e.pont(f"kod:{kod_id}", "kod", kodok.get(kod_id) or f"#{kod_id}")
            e.el(sid, f"kod:{kod_id}", suly, r.created_at, fajta)

    return _kimenet(db, e)


def _kimenet(db: Session, e: _Epito) -> dict:
    # A pontok súlya = a rájuk futó kapcsolatok súlyösszege.
    fok: dict[str, float] = defaultdict(float)
    for (a, b), el in e.elek.items():
        fok[a] += el.suly
        fok[b] += el.suly

    # Méretkorlát: a legerősebb partnerek / projektkódok maradnak.
    def legerosebb(fajta: str, n: int) -> set[str]:
        ids = [p.id for p in e.pontok.values() if p.fajta == fajta]
        return set(sorted(ids, key=lambda i: fok[i], reverse=True)[:n])

    marad = {p.id for p in e.pontok.values() if p.fajta in ("core", "tema", "cel", "szabaly")}
    marad |= legerosebb("partner", MAX_PARTNER) | legerosebb("kod", MAX_KOD)

    elek = []
    for (a, b), el in e.elek.items():
        if a in marad and b in marad:
            elek.append(
                {
                    "a": a,
                    "b": b,
                    "suly": round(el.suly, 3),
                    "bizonyossag": bizonyossag(el.suly),
                    "jovahagyott": el.jovahagyott,
                    "jelolt": el.jelolt,
                    "egyeb": el.egyeb,
                    "t": _iso(el.t),
                }
            )
    # Szerkezeti vázkapcsolat: a mag ↔ témakörök (a téma első tudásával jelenik meg).
    tema_ido: dict[str, datetime] = {}
    for (a, b), el in e.elek.items():
        for x in (a, b):
            if x.startswith("tema:") and el.t is not None and (x not in tema_ido or el.t < tema_ido[x]):
                tema_ido[x] = el.t
    for t in TEMAK:
        tid = f"tema:{t}"
        elek.append({"a": "core", "b": tid, "suly": 0, "bizonyossag": 1.0, "jovahagyott": 0, "jelolt": 0,
                     "egyeb": 0, "t": _iso(tema_ido.get(tid)), "vaz": True})

    elso: dict[str, str] = {}
    for el in elek:
        for x in (el["a"], el["b"]):
            if el["t"] and (x not in elso or el["t"] < elso[x]):
                elso[x] = el["t"]

    pontok = []
    for pid in marad:
        p = e.pontok[pid]
        tema = p.tema
        if p.fajta == "partner" and p.tema_suly:
            tema = max(p.tema_suly.items(), key=lambda kv: kv[1])[0]
        pontok.append(
            {
                "id": p.id,
                "fajta": p.fajta,
                "cimke": p.cimke,
                "tema": tema,
                "suly": round(fok[pid], 3),
                "t": elso.get(pid),
                "peldak": p.peldak,
                "allapot": p.allapot,
                "jovahagyott": p.jovahagyott,
                "jelolt": p.jelolt,
            }
        )

    valodi = [el for el in elek if not el.get("vaz")]
    idok = sorted(el["t"] for el in valodi if el["t"])
    return {
        "pontok": pontok,
        "elek": elek,
        "tanulas_kezdete": tanulas_kezdete(db).isoformat(),
        "elso_ido": idok[0] if idok else None,
        "utolso_ido": idok[-1] if idok else None,
        "osszesites": {
            "pontok": len([p for p in pontok if p["fajta"] not in ("core", "tema")]),
            "kapcsolatok": len(valodi),
            "eros_kapcsolatok": len([el for el in valodi if el["bizonyossag"] >= 0.6]),
            "jovahagyott_kapcsolatok": len([el for el in valodi if el["jovahagyott"] > 0]),
            "csak_jelolt_kapcsolatok": len([el for el in valodi if el["jovahagyott"] == 0]),
            "aktiv_szabalyok": len([p for p in pontok if p["fajta"] == "szabaly" and p["allapot"] == "active"]),
            "atlag_bizonyossag": round(sum(el["bizonyossag"] for el in valodi) / len(valodi), 3) if valodi else None,
        },
    }
