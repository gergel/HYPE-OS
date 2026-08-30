"""Minimális Notion API kliens az egyszeri (nem folyamatos) import-szkriptekhez.

Csak azt tudja, amire a Fázis 2 importhoz szükség van: adatbázisok listázása
(amiket megosztottak az integrációval), egy adatbázis összes oldalának lapozott
lekérése, és a Notion property-értékek generikus, típus szerinti kiolvasása.

A HYPE OS rendszer maga Notion-független - ezt a klienst kizárólag a
scripts/notion_discover.py és scripts/notion_import.py egyszeri futtatásai
használják, ÉS az admin-only /api/v1/admin/notion-import végpont (lásd
app/api/routes/admin_import.py), ami ugyanezt a futtatja egy háttérszálon, a
Railway-en éppen futó backend service processzében - hogy egy megszakadt
`railway ssh` kapcsolat ne szakítsa félbe a (több órás) importot.
"""

from __future__ import annotations

import os
import time
from typing import Any, Iterator

import httpx

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


class NotionClient:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("NOTION_API_KEY", "")
        if not self.api_key:
            raise RuntimeError(
                "NOTION_API_KEY nincs beállítva (env var). Railway-en: állítsd be a backend "
                "service Variables fülén, majd `railway ssh` és onnan futtasd a scriptet."
            )
        self._client = httpx.Client(
            base_url=NOTION_API_BASE,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Notion-Version": NOTION_VERSION,
                "Content-Type": "application/json",
            },
            # a property-item végpont (lapozott rich_text/relation mezők) néha lassan
            # válaszol nagy táblákon - a korábbi 30s-os globális timeout ReadTimeout-ot
            # dobott egy teljes importert (pl. Employee) elvitt élesben, ld. retry lent
            timeout=httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0),
        )

    def _request_with_retry(self, method: str, path: str, **kwargs) -> dict:
        """429 (rate limit) és átmeneti hálózati hibák (timeout, kapcsolat megszakadás)
        esetén is újrapróbálkozik, exponenciális backoff-fal - egy éles importban egy
        elszigetelt ReadTimeout ne vigye el az egész táblát (lásd run_importer)."""
        wait = 1.0
        last_exc: Exception | None = None
        for attempt in range(5):
            try:
                resp = self._client.request(method, path, **kwargs)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc
                if attempt == 4:
                    raise
                time.sleep(wait)
                wait *= 2
                continue
            if resp.status_code == 429:
                retry_after = float(resp.headers.get("Retry-After", str(wait)))
                time.sleep(retry_after)
                wait *= 2
                continue
            if resp.status_code >= 500:
                if attempt == 4:
                    resp.raise_for_status()
                time.sleep(wait)
                wait *= 2
                continue
            resp.raise_for_status()
            return resp.json()
        if last_exc:
            raise last_exc
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, json: dict | None = None) -> dict:
        return self._request_with_retry("POST", path, json=json or {})

    def _get(self, path: str, params: dict | None = None) -> dict:
        return self._request_with_retry("GET", path, params=params or {})

    def get_full_property(self, page_id: str, property_id: str) -> list[dict]:
        """A page-lekérdezés válaszában a rich_text/relation/people/title típusú
        property-k tömbje Notion-oldalon csonkolható (dokumentált API-korlát: kb.
        25 elem felett lapozni kell) - ez a végpont mindig a TELJES, lapozott
        értéket adja vissza. Csak akkor hívjuk, ha a query-válaszban kapott tömb
        gyanúsan a csonkolási határon van (lásd extract_properties)."""
        results: list[dict] = []
        cursor = None
        while True:
            params: dict[str, Any] = {"page_size": 100}
            if cursor:
                params["start_cursor"] = cursor
            data = self._get(f"/pages/{page_id}/properties/{property_id}", params=params)
            if data.get("object") == "list":
                results.extend(data.get("results", []))
                if not data.get("has_more"):
                    break
                cursor = data.get("next_cursor")
            else:
                # nem lapozott, egyetlen érték (pl. number/select/date/stb.) - nincs mit tenni
                return [data]
        return results

    def list_users(self) -> list[dict]:
        """Az egész workspace felhasználói, egyszer lekérve - a kommentek
        szerzőjének feloldásához kell (lásd importers_wave2.import_deliverables),
        és sokkal olcsóbb, mint felhasználónként/kommentenként külön hívni."""
        results: list[dict] = []
        params: dict[str, Any] = {"page_size": 100}
        while True:
            data = self._get("/users", params=params)
            results.extend(data.get("results", []))
            if not data.get("has_more"):
                break
            params["start_cursor"] = data["next_cursor"]
        return results

    def list_comments(self, page_id: str) -> list[dict]:
        """Egy Notion oldal (kártya) alján lévő kommentek időrendben, lapozva."""
        results: list[dict] = []
        params: dict[str, Any] = {"block_id": page_id, "page_size": 100}
        while True:
            data = self._get("/comments", params=params)
            results.extend(data.get("results", []))
            if not data.get("has_more"):
                break
            params["start_cursor"] = data["next_cursor"]
        return results

    def search_databases(self) -> list[dict]:
        """Az integrációval megosztott összes adatbázis (csak azok látszanak, amiket
        a Notionban kézzel megosztottak az integrációval - lásd a discovery script kimenetét)."""
        results: list[dict] = []
        payload: dict[str, Any] = {"filter": {"property": "object", "value": "database"}, "page_size": 100}
        while True:
            data = self._post("/search", json=payload)
            results.extend(data.get("results", []))
            if not data.get("has_more"):
                break
            payload["start_cursor"] = data["next_cursor"]
        return results

    def query_database(self, database_id: str) -> Iterator[dict]:
        """Egy adatbázis összes oldalát adja vissza, lapozva."""
        payload: dict[str, Any] = {"page_size": 100}
        while True:
            data = self._post(f"/databases/{database_id}/query", json=payload)
            yield from data.get("results", [])
            if not data.get("has_more"):
                break
            payload["start_cursor"] = data["next_cursor"]

    def close(self) -> None:
        self._client.close()


def database_title(database_obj: dict) -> str:
    title_parts = database_obj.get("title", [])
    return "".join(t.get("plain_text", "") for t in title_parts) or "(névtelen)"


def extract_property(prop: dict) -> Any:
    """Egy Notion property-értéket olvas ki Python natív típusra, típus szerint.
    A `relation` típusnál a kapcsolódó Notion page ID-k listáját adja vissza -
    ezeket az import-szkript egy második körben oldja fel a mi FK-jainkra."""
    prop_type = prop.get("type")
    value = prop.get(prop_type)

    if prop_type == "title" or prop_type == "rich_text":
        return "".join(t.get("plain_text", "") for t in value) if value else None
    if prop_type == "number":
        return value
    if prop_type == "select":
        return value.get("name") if value else None
    if prop_type == "status":
        return value.get("name") if value else None
    if prop_type == "multi_select":
        return [o.get("name") for o in value] if value else []
    if prop_type == "date":
        if not value:
            return None
        start = value.get("start")
        end = value.get("end")
        # sima dátum-string-et adunk vissza (pontosan azt, amit Notionban látsz),
        # nem egy {'start':..,'end':..} JSON objektumot - egy dátum tartomány esetén
        # "kezdő – záró" alakban.
        if end and end != start:
            return f"{start} – {end}"
        return start
    if prop_type == "checkbox":
        return bool(value)
    if prop_type == "people":
        return [p.get("name") or p.get("id") for p in value] if value else []
    if prop_type in ("email", "phone_number", "url"):
        return value
    if prop_type == "relation":
        return [r.get("id") for r in value] if value else []
    if prop_type == "files":
        out = []
        for f in value or []:
            if f.get("type") == "external":
                out.append(f.get("external", {}).get("url"))
            else:
                out.append(f.get("file", {}).get("url"))
        return out
    if prop_type == "formula":
        return extract_property({"type": value.get("type"), value.get("type"): value.get(value.get("type"))})
    if prop_type == "rollup":
        rollup_type = value.get("type")
        if rollup_type == "array":
            return [extract_property(v) for v in value.get("array", [])]
        # a date/number/string altípusokat is a fenti, típus szerinti ágakon
        # keresztül normalizáljuk (pl. dátum -> sima string, nem beágyazott objektum)
        return extract_property({"type": rollup_type, rollup_type: value.get(rollup_type)})
    if prop_type in ("created_time", "last_edited_time"):
        return value
    if prop_type == "button":
        return None
    return value


_PAGINATED_TYPES = ("rich_text", "title", "relation", "people")
_TRUNCATION_THRESHOLD = 25  # Notion API: array-tipusú property-k a query/retrieve válaszban
# legfeljebb ennyi elemet adnak vissza egyben - efölött a property-item végponttal kell
# lapozni a teljes értékért (ez okozta, hogy 1000+ karakteres rich_text mezők nálunk
# üresen/null-ként jöttek át, ha sok formázási szegmensre voltak darabolva Notion-ban).


def extract_properties(page: dict, client: "NotionClient | None" = None) -> dict[str, Any]:
    """Egy Notion page összes property-jét kiolvassa egy sima {mezőnév: érték} dict-be.

    Ha kapunk egy NotionClient-et, és egy array-tipusú property pont a Notion
    csonkolási határán (25 elem) jön vissza, újra lekérjük a teljes, lapozott
    értéket a /pages/{id}/properties/{property_id} végponttal - enélkül a hosszú,
    sok formázási szegmensre bomló rich_text mezők (pl. hosszú megjegyzések)
    csendben null-ként/hiányosan érkeznének."""
    result = {}
    for name, prop in page.get("properties", {}).items():
        prop_type = prop.get("type")
        raw_value = prop.get(prop_type)
        if (
            client is not None
            and prop_type in _PAGINATED_TYPES
            and isinstance(raw_value, list)
            and len(raw_value) >= _TRUNCATION_THRESHOLD
        ):
            full_items = client.get_full_property(page["id"], prop["id"])
            prop = {"type": prop_type, prop_type: [item.get(prop_type) for item in full_items]}
        result[name] = extract_property(prop)
    return result


def remaining_properties(props: dict[str, Any], consumed: set[str]) -> dict[str, Any]:
    """Azokat a Notion mezőket adja vissza, amiket az importer NEM olvasott ki saját
    oszlopba - ez kerül az entitás `extra` JSON mezőjébe, hogy a HYPE ADMIN projektkódok-
    hoz hasonló, 60+ mezős táblák adata ne vesszen el, de a séma se dagadjon szét.
    Üres/None értékeket kihagyja, hogy az extra JSON kompakt maradjon."""
    result = {}
    for key, value in props.items():
        if key in consumed:
            continue
        if value is None or value == [] or value == "":
            continue
        result[key] = value
    return result


def as_date(value: dict | str | None):
    """A date property extract_property által visszaadott {'start':..,'end':..} alakját
    (vagy a rich_text-ként tárolt szabad dátum-szöveget, ami a HYPE Notionban gyakori)
    Python date-re alakítja, ha lehet."""
    from datetime import date, datetime

    if value is None:
        return None
    if isinstance(value, dict):
        raw = value.get("start")
    else:
        raw = value
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except (ValueError, AttributeError):
        try:
            return date.fromisoformat(raw[:10])
        except (ValueError, TypeError):
            return None


def as_datetime(value: dict | str | None):
    """Mint as_date, de a teljes időbélyeget (óra/perc) is megtartja - a created_time/
    last_edited_time property-k már eleve ISO-datetime string-ek."""
    from datetime import datetime

    if value is None:
        return None
    raw = value.get("start") if isinstance(value, dict) else value
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
