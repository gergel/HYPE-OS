"""AZ AI ASSISTANT ESZKÖZRÉTEGE - a modell a rendszer SAJÁT REST-végpontjait
hívja, a bejelentkezett felhasználó nevében (a felhasználó előírása: a normál
felület és az AI ugyanazokat a szerveroldali üzleti műveleteket használja).

MIÉRT BELSŐ API-HÍVÁS, nem közvetlen DB-írás? Mert így garantáltan ugyanaz fut,
mint a felületről: ugyanaz a jogosultság-ellenőrzés (check_page_action,
fül-jogok, sor-szűrők), ugyanazok a before/after hookok (értesítések,
validációk), ugyanaz a visszavonás-pillanatkép törléskor, ugyanazok az üzleti
folyamatok (érkeztetés, TIG-kifizetés). A modell tetszőleges adatbázis-
parancsokkal nem tudja megkerülni az alkalmazás működését - kizárólag a
/api/v1 végpontokat éri el, a kezdeményező felhasználó tokenjével.

VÉDELMEK:
- TILTOTT útvonalak (auth, ai-assistant önhívás, realtime) egyáltalán nem
  hívhatók;
- a MEGERŐSÍTENDŐ műveletek (törlés, pénzügyi felvezetés/kifizetés, reset,
  hozzáférés-módosítás) nem futnak le azonnal: "fuggo" AiMuvelet készül, a
  felület kártyát mutat, és a végrehajtás CSAK a felhasználó kattintására,
  PONTOSAN a tárolt kéréssel történik;
- minden írás naplózott (AiMuvelet), és idempotencia-kulcsot igényel: az
  ismételt hívás a tárolt eredményt kapja, nem fut le még egyszer.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

import httpx
from fastapi.routing import APIRoute
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models.ai_beszelgetes import AiFajl, AiMuvelet
from app.models.employee import Employee

logger = logging.getLogger(__name__)

#: A belső hívás válaszából legfeljebb ennyi karakter megy vissza a modellnek -
#: egy több-száz soros lista JSON-ja token-tengerré válna.
MAX_VALASZ_HOSSZ = 14000

#: Ezekre az útvonalakra az asszisztens EGYÁLTALÁN nem hívhat rá.
TILTOTT_UTVONAL_ELOTAGOK = (
    "/api/v1/auth",          # bejelentkezés/jelszó - nem az asszisztens dolga
    "/api/v1/ai-assistant",  # önhívás (rekurzió) ellen
    "/api/v1/realtime",
)

#: Írásnál (POST/PATCH/PUT/DELETE) MEGERŐSÍTÉST igénylő minták: ami törlés,
#: pénzügyi felvezetés/kifizetés, tömeges takarítás vagy hozzáférés-módosítás,
#: az csak a felhasználó felületi jóváhagyása után fut le (a spec szerint a
#: kötelező üzleti jóváhagyások és a visszafordíthatatlan műveletek köre).
MEGEROSITENDO_RESZLETEK = (
    "/jovahagyas",
    "/rogzites",
    "kifizet",           # kifizetve, kifizetes...
    "fizetesi-allapot",
    "/reset",
    "osszes-torles",
    "/user-access",
    "/felhasznalok",
    # Munkafelajánlások: e-mailt kiküldő vagy döntést rögzítő lépések - az
    # asszisztens ezekhez is kifejezett emberi megerősítést kér.
    "/kikuldes",
    "/ujrakuldes",
    "/kivalasztas",
    "lezaras-nyertes-nelkul",
    "/visszavonas",
)


class EszkozHiba(ValueError):
    """A modellnek visszaadható, emberi szövegű eszköz-hiba."""


def _blokkolt(path: str) -> bool:
    return any(path.startswith(e) for e in TILTOTT_UTVONAL_ELOTAGOK)


def megerositendo(method: str, path: str) -> bool:
    """Kell-e felhasználói megerősítés ehhez az íráshoz."""
    if method.upper() == "DELETE":
        return True
    tiszta = path.split("?")[0].lower()
    return any(r in tiszta for r in MEGEROSITENDO_RESZLETEK)


# ── API-KATALÓGUS ────────────────────────────────────────────────────────────

_katalogus_cache: list[dict] | None = None


def _osszes_route() -> list:
    """Az app összes route-leírója. Az újabb FastAPI az include_router-t lusta
    _IncludedRouter-ként teszi az app.routes-ba - a tényleges végpontok abból
    az effective_route_contexts()-szel bonthatók ki (path/methods/endpoint/
    body_field ugyanúgy rajtuk van, mint egy APIRoute-on)."""
    from app.main import app

    eredmeny: list = []
    for route in app.routes:
        if isinstance(route, APIRoute):
            eredmeny.append(route)
        elif hasattr(route, "effective_route_contexts"):
            try:
                eredmeny.extend(route.effective_route_contexts())
            except Exception:  # noqa: BLE001 - egy hibás router ne vigye el a katalógust
                logger.exception("AI-katalógus: a beágyazott router nem bontható ki")
    return eredmeny


def _api_katalogus_epites() -> list[dict]:
    """A teljes /api/v1 végpont-katalógus az app route-jaiból - ez adja a
    modulonkénti lefedettséget: minden, a felületről elérhető szerveroldali
    művelet itt is megjelenik, kézi listázás nélkül."""
    elemek: list[dict] = []
    for route in _osszes_route():
        path = getattr(route, "path", "")
        if not path.startswith("/api/v1") or _blokkolt(path):
            continue
        endpoint = getattr(route, "endpoint", None)
        osszefoglalo = (((endpoint.__doc__ if endpoint else "") or "").strip().splitlines() or [""])[0][:180]
        body_mezok = None
        try:
            body_field = getattr(route, "body_field", None)
            tipus = getattr(body_field, "type_", None) if body_field is not None else None
            mezok = getattr(tipus, "model_fields", None)
            if mezok:
                body_mezok = {nev: str(mezo.annotation).replace("typing.", "") for nev, mezo in mezok.items()}
        except Exception:  # noqa: BLE001 - a katalógus enélkül is használható
            body_mezok = None
        for method in sorted((getattr(route, "methods", None) or set()) - {"HEAD", "OPTIONS"}):
            elemek.append(
                {
                    "method": method,
                    "path": path,
                    "leiras": osszefoglalo,
                    "body_mezok": body_mezok if method in ("POST", "PATCH", "PUT") else None,
                    "megerosites_kell": method != "GET" and megerositendo(method, path),
                }
            )
    elemek.sort(key=lambda e: (e["path"], e["method"]))
    return elemek


def api_katalogus(kulcsszo: str | None = None) -> dict:
    """Végpont-kereső a modellnek: útvonal/leírás részlet alapján szűrt lista."""
    global _katalogus_cache
    if _katalogus_cache is None:
        _katalogus_cache = _api_katalogus_epites()
    elemek = _katalogus_cache
    if kulcsszo:
        k = kulcsszo.strip().lower()
        elemek = [e for e in elemek if k in e["path"].lower() or k in e["leiras"].lower()]
    if len(elemek) > 60:
        return {
            "talalat": len(elemek),
            "vegpontok": elemek[:60],
            "megjegyzes": "Több mint 60 találat - szűkítsd a kulcsszót.",
        }
    return {"talalat": len(elemek), "vegpontok": elemek}


# ── BELSŐ API-HÍVÁS ──────────────────────────────────────────────────────────


def _belso_hivas(
    user: Employee,
    method: str,
    path: str,
    *,
    json_body: dict | list | None = None,
    files: list[tuple[str, tuple[str, bytes, str]]] | None = None,
    data: dict | None = None,
) -> tuple[int, object]:
    """Egy kérés az alkalmazás SAJÁT API-ján, a felhasználó nevében - ugyanazon
    az úton (middleware-ek, függőségek, jogosultság), mint a böngészőből."""
    from app.main import app

    token = create_access_token(subject=str(user.id), role=user.role.value)

    async def _fut() -> tuple[int, object]:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://belso", timeout=120) as klien:
            valasz = await klien.request(
                method,
                path,
                json=json_body if files is None and data is None else None,
                files=files,
                data=data,
                headers={"Authorization": f"Bearer {token}"},
            )
            try:
                tartalom: object = valasz.json()
            except ValueError:
                tartalom = valasz.text
            return valasz.status_code, tartalom

    # A hívó sync végpont a FastAPI threadpoolján fut, tehát ebben a szálban
    # nincs futó eseményhurok - az asyncio.run itt biztonságos.
    return asyncio.run(_fut())


def _valasz_roviditett(tartalom: object) -> object:
    szoveg = json.dumps(tartalom, ensure_ascii=False, default=str)
    if len(szoveg) <= MAX_VALASZ_HOSSZ:
        return tartalom
    return {
        "levagva": True,
        "megjegyzes": f"A válasz túl hosszú volt ({len(szoveg)} karakter) - az eleje jött vissza. Szűkítsd a lekérdezést.",
        "eleje": szoveg[:MAX_VALASZ_HOSSZ],
    }


def api_lekeres(user: Employee, path: str) -> dict:
    """CSAK OLVASÓ (GET) hívás - kereséshez, listázáshoz, részletekhez és a
    mentés utáni visszaellenőrzéshez."""
    if not path.startswith("/api/v1"):
        raise EszkozHiba("Csak /api/v1 kezdetű útvonal hívható.")
    if _blokkolt(path):
        raise EszkozHiba("Ez az útvonal nem érhető el az asszisztensből.")
    status, tartalom = _belso_hivas(user, "GET", path)
    return {"status": status, "valasz": _valasz_roviditett(tartalom)}


def api_muvelet(
    db: Session,
    user: Employee,
    beszelgetes_id: int,
    *,
    method: str,
    path: str,
    body: dict | list | None,
    idempotencia_kulcs: str,
    osszefoglalo: str,
) -> dict:
    """ÍRÓ művelet (POST/PATCH/PUT/DELETE) a rendszer saját API-ján.

    - naplózott (AiMuvelet: ki, mit, mivel, mi lett);
    - idempotens: azonos kulccsal a tárolt eredmény jön vissza, nem fut újra;
    - a megerősítendő műveletek NEM futnak le: függő műveletként várnak a
      felhasználó felületi jóváhagyására (lásd vegrehajt_fuggo_muveletet)."""
    method = (method or "").upper()
    if method not in ("POST", "PATCH", "PUT", "DELETE"):
        raise EszkozHiba("Írásra a POST/PATCH/PUT/DELETE módszerek használhatók (olvasásra api_lekeres).")
    if not path.startswith("/api/v1"):
        raise EszkozHiba("Csak /api/v1 kezdetű útvonal hívható.")
    if _blokkolt(path):
        raise EszkozHiba("Ez az útvonal nem érhető el az asszisztensből.")
    kulcs = (idempotencia_kulcs or "").strip()
    if not kulcs:
        raise EszkozHiba("Íráshoz kötelező az idempotencia_kulcs (rövid, stabil azonosító erre a műveletre).")

    meglevo = db.scalar(
        select(AiMuvelet).where(
            AiMuvelet.beszelgetes_id == beszelgetes_id, AiMuvelet.idempotencia_kulcs == kulcs
        )
    )
    if meglevo is not None:
        if meglevo.allapot == "vegrehajtva":
            return {
                "ismetles": True,
                "megjegyzes": "Ez a művelet ezzel a kulccsal már lefutott - a tárolt eredmény jön vissza, ÚJRA NEM futott le.",
                "status": meglevo.valasz_status,
                "valasz": _valasz_roviditett(meglevo.valasz),
            }
        if meglevo.allapot == "fuggo":
            return {
                "megerosites_szukseges": True,
                "muvelet_id": meglevo.id,
                "megjegyzes": "Ez a művelet már a felhasználó megerősítésére vár - ne hívd újra, jelezd a felhasználónak.",
            }
        # elutasitva/hiba: új kulccsal lehet újra próbálni - a régit nem írjuk át.
        return {
            "hiba": f"Ez a kulcs már {meglevo.allapot} állapotú művelethez tartozik - ha újra kell, használj új kulcsot.",
        }

    muvelet = AiMuvelet(
        beszelgetes_id=beszelgetes_id,
        employee_id=user.id,
        idempotencia_kulcs=kulcs,
        method=method,
        path=path,
        keres=body,
        osszefoglalo=(osszefoglalo or "").strip()[:1000] or None,
        allapot="fuggo",
    )
    db.add(muvelet)
    db.flush()

    if megerositendo(method, path):
        db.commit()
        return {
            "megerosites_szukseges": True,
            "muvelet_id": muvelet.id,
            "megjegyzes": (
                "Ez a művelet a felhasználó megerősítését igényli - a felületen kártya jelent meg. "
                "Foglald össze a felhasználónak, mi fog történni, és kérd meg, hogy a kártyán hagyja jóvá. "
                "NE hívd újra ezt a műveletet."
            ),
        }

    return _muvelet_futtatas(db, user, muvelet)


def _muvelet_futtatas(db: Session, user: Employee, muvelet: AiMuvelet) -> dict:
    status, tartalom = _belso_hivas(user, muvelet.method, muvelet.path, json_body=muvelet.keres)
    muvelet.valasz_status = status
    muvelet.valasz = tartalom if isinstance(tartalom, (dict, list)) else {"szoveg": str(tartalom)[:4000]}
    muvelet.allapot = "vegrehajtva" if status < 400 else "hiba"
    muvelet.vegrehajtva_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": status, "valasz": _valasz_roviditett(tartalom)}


def vegrehajt_fuggo_muveletet(db: Session, user: Employee, muvelet: AiMuvelet, jovahagyva: bool) -> dict:
    """A felhasználó felületi döntése egy függő műveletről. Végrehajtáskor
    PONTOSAN a tárolt kérés fut le - a modell utólag nem tud rajta változtatni."""
    if muvelet.allapot != "fuggo":
        return {
            "status": muvelet.valasz_status,
            "valasz": muvelet.valasz,
            "megjegyzes": f"Ez a művelet már {muvelet.allapot} állapotban van - nem futott le újra.",
            "allapot": muvelet.allapot,
        }
    if not jovahagyva:
        muvelet.allapot = "elutasitva"
        db.commit()
        return {"allapot": "elutasitva"}
    eredmeny = _muvelet_futtatas(db, user, muvelet)
    return {**eredmeny, "allapot": muvelet.allapot}


# ── FÁJL-ESZKÖZÖK ────────────────────────────────────────────────────────────


def _fajl_betoltes(db: Session, beszelgetes_id: int, fajl_id: int) -> tuple[AiFajl, bytes]:
    from app.services import document_storage

    fajl = db.get(AiFajl, fajl_id)
    if fajl is None or fajl.beszelgetes_id != beszelgetes_id:
        raise EszkozHiba(f"Nincs ilyen csatolt fájl ebben a beszélgetésben: #{fajl_id}")
    return fajl, document_storage.download_bytes(fajl.storage_key)


def _fajl_felhasznalva(db: Session, fajl: AiFajl, mint: str, rekord_id: int) -> None:
    fajl.felhasznalva = [
        *(fajl.felhasznalva or []),
        {"mint": mint, "id": rekord_id, "mikor": datetime.now(timezone.utc).isoformat()},
    ]


def szamla_feltoltes(
    db: Session,
    user: Employee,
    beszelgetes_id: int,
    *,
    fajl_id: int,
    utasitas: str | None,
    csoport: str | None,
) -> dict:
    """A csatolt fájl beadása a KÖZÖS számla-érkeztető folyamatba (Beérkező
    számlák) - kiolvasás, duplikáció-vizsgálat, besorolási javaslat, mentett
    piszkozat. A `csoport` az egyszerre feltöltött, összetartozó fájlokat
    (számla + Excel-részletező) köti össze, hogy a projektbontás-javaslat a
    számlára kerüljön."""
    fajl, adat = _fajl_betoltes(db, beszelgetes_id, fajl_id)
    data: dict = {"utasitas": utasitas or ""}
    if csoport:
        data["csoport"] = f"ai-{beszelgetes_id}-{csoport}"[:200]
    status, tartalom = _belso_hivas(
        user,
        "POST",
        "/api/v1/bejovo-szamlak/feltoltes",
        files=[("file", (fajl.fajl_nev, adat, fajl.content_type or "application/octet-stream"))],
        data=data,
    )
    if status < 400 and isinstance(tartalom, dict) and tartalom.get("id"):
        _fajl_felhasznalva(db, fajl, "bejovo_szamla", int(tartalom["id"]))
        db.commit()
    return {"status": status, "valasz": _valasz_roviditett(tartalom)}


def dokumentum_csatolas(
    db: Session,
    user: Employee,
    beszelgetes_id: int,
    *,
    fajl_id: int,
    entity_type: str,
    entity_id: int,
    kategoria: str,
) -> dict:
    """A csatolt fájl feltöltése egy rekordhoz a normál csatolmány-folyamaton
    (routes/attachments.py) - ugyanaz a jogosultság- és méret-ellenőrzés fut,
    mint a felületről."""
    fajl, adat = _fajl_betoltes(db, beszelgetes_id, fajl_id)
    status, tartalom = _belso_hivas(
        user,
        "POST",
        f"/api/v1/attachments/{entity_type}/{entity_id}?kategoria={kategoria or 'egyeb'}",
        files=[("file", (fajl.fajl_nev, adat, fajl.content_type or "application/octet-stream"))],
    )
    if status < 400 and isinstance(tartalom, dict) and tartalom.get("id"):
        _fajl_felhasznalva(db, fajl, "attachment", int(tartalom["id"]))
        db.commit()
    return {"status": status, "valasz": _valasz_roviditett(tartalom)}


def fajl_lista(db: Session, beszelgetes_id: int) -> dict:
    fajlok = db.scalars(
        select(AiFajl).where(AiFajl.beszelgetes_id == beszelgetes_id).order_by(AiFajl.id)
    ).all()
    return {
        "fajlok": [
            {
                "fajl_id": f.id,
                "nev": f.fajl_nev,
                "tipus": f.content_type,
                "meret_bajt": f.meret_bajt,
                "mar_felhasznalva": f.felhasznalva or [],
            }
            for f in fajlok
        ]
    }
