"""Egy Portal megjelenítendő cím/ügyfélnév/dátum mezői - mivel a Portal 1:1 egy
valódi HYPE OS Project-hez kötött (nincs kettőzött adatbevitel), ezek alapból
a Project saját mezőire esnek vissza, és csak akkor jön a Portal saját
title_override/client_name_override/project_date_override mezője, ha az admin
kifejezetten felülírta (pl. mert az ügyfélnek szánt megnevezés más, mint a
belső projektnév)."""

from __future__ import annotations

from app.models.portal import Portal


def resolve_title(portal: Portal) -> str:
    return portal.title_override or (portal.project.nev if portal.project else "") or ""


def resolve_client_name(portal: Portal) -> str:
    if portal.client_name_override:
        return portal.client_name_override
    project = portal.project
    if project and project.project_code and project.project_code.client:
        return project.project_code.client.nev
    return ""


def resolve_project_date(portal: Portal) -> str:
    if portal.project_date_override:
        return portal.project_date_override
    project = portal.project
    if not project or not project.forgatas_datuma:
        return ""
    start = project.forgatas_datuma.strftime("%Y.%m.%d")
    if project.forgatas_datuma_vege and project.forgatas_datuma_vege != project.forgatas_datuma:
        return f"{start} – {project.forgatas_datuma_vege.strftime('%Y.%m.%d')}"
    return start
