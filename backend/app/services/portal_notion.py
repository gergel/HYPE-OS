"""Külön Notion-szinkron a Média Portálhoz - a Hype-repo-main (különálló
client-portál projekt) notion.py logikája, adaptálva a HYPE OS 1:1
Portal<->Project modelljéhez: mivel egy Portál mindig egy MEGLÉVŐ HYPE OS
Project-hez tartozik (nem önálló, szabadon kitöltött cím/ügyfélnév), egy
Notion-sor csak akkor hoz létre ÚJ Portált, ha a "Project Name" pontosan
egyezik egy meglévő (még Portál nélküli) HYPE OS Project nevével - egyébként
csak a már korábban szinkronizált (notion_page_id alapján azonosított)
Portálokat frissíti."""

from __future__ import annotations

import httpx
from slugify import slugify
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.portal import Portal
from app.models.project import Project

NOTION_VERSION = "2022-06-28"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.portal_notion_api_key}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _plain(prop: dict) -> str:
    t = prop.get("type")
    if t in ("title", "rich_text"):
        arr = prop.get(t, [])
        return "".join(x.get("plain_text", "") for x in arr)
    if t == "url":
        return prop.get("url") or ""
    if t == "select":
        sel = prop.get("select")
        return sel.get("name", "") if sel else ""
    if t == "files":
        files = prop.get("files", [])
        if files:
            f = files[0]
            return f.get("file", {}).get("url") or f.get("external", {}).get("url", "")
    return ""


def sync_portals(db: Session) -> dict:
    """Notion "Portal Status" -> live/draft/archived szinkron.

    Expected Notion fields: Project Name, Portal Slug, Portal Cover Image, Portal Status."""
    if not (settings.portal_notion_api_key and settings.portal_notion_database_id):
        return {"synced": 0, "created": 0, "error": "Notion nincs beállítva (portal_notion_api_key/database_id)"}

    url = f"https://api.notion.com/v1/databases/{settings.portal_notion_database_id}/query"
    synced = 0
    created = 0
    skipped = 0
    cursor = None

    with httpx.Client(timeout=30) as client:
        while True:
            body: dict = {"page_size": 100}
            if cursor:
                body["start_cursor"] = cursor
            resp = client.post(url, headers=_headers(), json=body)
            resp.raise_for_status()
            data = resp.json()

            for page in data.get("results", []):
                props = page.get("properties", {})
                page_id = page["id"]
                title = _plain(props.get("Project Name", {})) or ""
                slug = _plain(props.get("Portal Slug", {})) or slugify(title)
                cover = _plain(props.get("Portal Cover Image", {}))
                status = _plain(props.get("Portal Status", {})).lower() or "draft"
                mapped_status = "live" if status in ("live", "published") else status

                portal = db.scalar(select(Portal).where(Portal.notion_page_id == page_id))
                if portal is None:
                    project = db.scalar(select(Project).where(Project.nev == title)) if title else None
                    if project is None or project.portal is not None:
                        skipped += 1
                        continue
                    portal = Portal(project_id=project.id, slug=slug or slugify(title))
                    db.add(portal)
                    created += 1

                portal.notion_page_id = page_id
                if slug:
                    portal.slug = slug
                if cover:
                    portal.cover_image_url = cover
                if mapped_status in ("draft", "live", "archived"):
                    portal.status = mapped_status
                synced += 1

            db.commit()
            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")

    return {"synced": synced, "created": created, "skipped": skipped}
