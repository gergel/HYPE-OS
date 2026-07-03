"""Minimális Notion API kliens az egyszeri (nem folyamatos) import-szkriptekhez.

Csak azt tudja, amire a Fázis 2 importhoz szükség van: adatbázisok listázása
(amiket megosztottak az integrációval), egy adatbázis összes oldalának lapozott
lekérése, és a Notion property-értékek generikus, típus szerinti kiolvasása.

A HYPE OS futása közben ezt SOHA nem hívja senki élőben - lásd
docs/hype_os_build_roadmap.md Fázis 2: a rendszer Notion-független, ez a kliens
kizárólag a scripts/notion_discover.py és scripts/notion_import.py egyszeri
futtatásaihoz kell.
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
            timeout=30.0,
        )

    def _post(self, path: str, json: dict | None = None) -> dict:
        for attempt in range(5):
            resp = self._client.post(path, json=json or {})
            if resp.status_code == 429:
                wait = float(resp.headers.get("Retry-After", "1"))
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        resp.raise_for_status()
        return resp.json()

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
        return {"start": value.get("start"), "end": value.get("end")}
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
        return value.get(rollup_type)
    if prop_type in ("created_time", "last_edited_time"):
        return value
    if prop_type == "button":
        return None
    return value


def extract_properties(page: dict) -> dict[str, Any]:
    """Egy Notion page összes property-jét kiolvassa egy sima {mezőnév: érték} dict-be."""
    return {name: extract_property(prop) for name, prop in page.get("properties", {}).items()}


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
