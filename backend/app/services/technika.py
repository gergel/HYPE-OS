"""'Technika ready' ellenőrzés - a HYPE_Technika Railway program portolása.

Az eredeti rendszer Notion-t figyelt és a 'Technika ready' checkbox bepipálására
naponta lebontva ütközést keresett a lefoglalt eszközök között (két projekt ne
foglalja ugyanazt az egyedi ("asset") eszközt ugyanazon a napon, a darabszámos
("stock") eszközöknél pedig az egy napra lefoglalt összmennyiség ne haladja meg
a teljes készletet), optikáknál (kategória "Optika") azonos zoom-tartományú,
szabad alternatívát ajánlott, és visszaírta az eredményt a Notion oldalra.

Itt ugyanez, a mi Postgres-ünkön: az Assignment tábla (equipment_id, project_id,
qty) adja a foglalásokat - ez EGYBEN kezeli a korábbi Notion "Leltár" (egyedi
eszköz, qty=1) és "Stock igények" (darabszámos, qty=N) relation-öket, a
felhasználó kérése szerint összevonva. A projekt forgatási napjai a
Project.forgatas_datuma - forgatas_datuma_vege tartomány (ha nincs záró dátum,
egynapos forgatásnak vesszük)."""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.equipment import Assignment, Equipment, TrackMode
from app.models.project import Project

CATEGORY_ORDER = [
    "Kamera",
    "Akkumulátor",
    "Kártya",
    "Optika",
    "Hang",
    "Iroda (adatároló)",
    "Irodai",
    "Egyéb",
    "Mozgatók",
    "Statív",
    "Világítás",
    "Lámpa állvány",
    "220V",
    "Drón",
    "Táska",
]


def _normalize_cat(cat: str | None) -> str:
    return (cat or "").strip().lower()


def _days_inclusive(start: date, end: date) -> list[date]:
    days = []
    cur = start
    while cur <= end:
        days.append(cur)
        cur += timedelta(days=1)
    return days


def _project_range(project: Project) -> tuple[date, date] | None:
    if not project.forgatas_datuma:
        return None
    return project.forgatas_datuma, (project.forgatas_datuma_vege or project.forgatas_datuma)


def _ranges_overlap(a_start: date, a_end: date, b_start: date, b_end: date) -> bool:
    return a_start <= b_end and b_start <= a_end


def _format_tech_list(items: list[dict]) -> str:
    """Kategóriánként csoportosított, a CATEGORY_ORDER szerint rendezett szöveges lista."""
    grouped: dict[str, dict] = {}
    for it in items:
        raw_cat = (it.get("category") or "Egyéb").strip() or "Egyéb"
        key = _normalize_cat(raw_cat)
        name = (it.get("name") or "").strip()
        if not name:
            continue
        if it.get("track_mode") == TrackMode.STOCK.value:
            qty = int(it.get("qty") or 0)
            if qty <= 0:
                continue
            line = f"- {qty}db {name}"
        else:
            line = f"- {name}"
        grouped.setdefault(key, {"display": raw_cat, "lines": []})["lines"].append(line)

    ordered_keys = [_normalize_cat(c) for c in CATEGORY_ORDER if _normalize_cat(c) in grouped]
    remaining_keys = sorted(k for k in grouped if k not in ordered_keys)
    final_keys = ordered_keys + remaining_keys

    blocks = []
    for key in final_keys:
        display = grouped[key]["display"]
        lines = sorted(grouped[key]["lines"], key=str.lower)
        blocks.append(display + "\n" + "\n".join(lines))
    return "\n\n".join(blocks)


def _find_alternative_optics(
    db: Session, equipment: Equipment, shoot_start: date, shoot_end: date, current_project_id: int, limit: int = 3
) -> list[Equipment]:
    zoom = equipment.zoom_atfogas
    if not zoom:
        return []

    candidates = db.scalars(
        select(Equipment).where(
            Equipment.kategoria == equipment.kategoria,
            Equipment.id != equipment.id,
            Equipment.track_mode == TrackMode.ASSET,
        )
    ).all()

    alternatives: list[Equipment] = []
    for cand in candidates:
        if cand.zoom_atfogas != zoom:
            continue
        if cand.hasznalhato and cand.hasznalhato != "Használható":
            continue

        conflict = False
        for a in db.scalars(select(Assignment).where(Assignment.equipment_id == cand.id)):
            if a.project_id == current_project_id:
                continue
            other = db.get(Project, a.project_id)
            other_range = _project_range(other) if other else None
            if other_range and _ranges_overlap(shoot_start, shoot_end, *other_range):
                conflict = True
                break

        if not conflict:
            alternatives.append(cand)
        if len(alternatives) >= limit:
            break

    return alternatives


def check_technika(db: Session, project: Project) -> dict:
    """Lefuttatja az ütközés-ellenőrzést a projekthez rendelt (Assignment) eszközökre,
    és visszaírja az eredményt a projektre (technika_lista, backend_statusz,
    backend_uzenet, technika_ready=False - egyszeri trigger, mint az eredetiben)."""
    project_range = _project_range(project)
    if project_range is None:
        project.backend_statusz = "ISSUE"
        project.backend_uzenet = "Hiányzik a forgatás dátuma."
        project.technika_ready = False
        db.commit()
        return {"status": project.backend_statusz, "message": project.backend_uzenet, "technika_lista": None}

    start, end = project_range
    assignments = db.scalars(select(Assignment).where(Assignment.project_id == project.id)).all()

    messages: list[str] = []
    ok = True
    all_items: list[dict] = []

    for a in assignments:
        equipment = db.get(Equipment, a.equipment_id)
        if equipment is None:
            continue

        all_items.append(
            {"name": equipment.nev, "category": equipment.kategoria, "track_mode": equipment.track_mode.value, "qty": a.qty}
        )

        if equipment.track_mode == TrackMode.ASSET:
            conflict_project_ids = {
                other_a.project_id
                for other_a in db.scalars(
                    select(Assignment).where(
                        Assignment.equipment_id == equipment.id,
                        Assignment.project_id != project.id,
                    )
                )
            }
            conflicting_projects = []
            for other_id in conflict_project_ids:
                other = db.get(Project, other_id)
                other_range = _project_range(other) if other else None
                if other_range and _ranges_overlap(start, end, *other_range):
                    conflicting_projects.append((other, other_range))

            if conflicting_projects:
                ok = False
                detail = ", ".join(
                    f"{p.nev} ({r[0].isoformat()}"
                    + (f" – {r[1].isoformat()}" if r[1] != r[0] else "")
                    + ")"
                    for p, r in conflicting_projects
                )
                msg = f"{equipment.nev} nem elérhető: {detail}"
                alternatives = _find_alternative_optics(db, equipment, start, end, project.id)
                if alternatives:
                    msg += f". Alternatívák: {', '.join(alt.nev for alt in alternatives)}"
                messages.append(msg)
        elif equipment.osszes_mennyiseg is not None:
            # Ha nincs megadva "Összes mennyiség", nem ismert a keret - ilyenkor
            # nem jelezzük túllépésnek (0-nak véve mindig hibát adna, holott
            # csak a Notion-import forrásadata hiányzik, nem a valós készlet).
            keret = equipment.osszes_mennyiseg
            same_item_assignments = db.scalars(select(Assignment).where(Assignment.equipment_id == equipment.id)).all()
            overbooked_day: date | None = None
            overbooked_total = 0
            for day in _days_inclusive(start, end):
                total = 0
                for other_a in same_item_assignments:
                    other = db.get(Project, other_a.project_id)
                    other_range = _project_range(other) if other else None
                    if other_range and other_range[0] <= day <= other_range[1]:
                        total += other_a.qty
                if total > keret:
                    ok = False
                    overbooked_day = day
                    overbooked_total = total
                    break
            if overbooked_day is not None:
                messages.append(f"{equipment.nev} készlet túllépve {overbooked_day.isoformat()}: {overbooked_total}/{keret} db")

    project.technika_lista = _format_tech_list(all_items)
    project.backend_statusz = "OK" if ok else "ISSUE"
    project.backend_uzenet = "\n".join(messages) if messages else "OK"
    project.technika_ready = False
    db.commit()

    return {"status": project.backend_statusz, "message": project.backend_uzenet, "technika_lista": project.technika_lista}
