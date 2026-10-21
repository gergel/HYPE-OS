"""Az 'extra' JSON catch-all mezőkben (Contract/Equipment/Campaign/Task/Expense/
Revenue/KpForgalom/Deliverable/Timesheet) jelenleg ülő, még saját oszlopot nem
kapott Notion mezőnevek kilistázása - DB-only, Notion API hívás NÉLKÜL.

Ez a sandbox környezet nem éri el az api.notion.com-ot, úgyhogy a hátralévő
"minden mező saját oszlopként" munkához (lásd Batch 2-5) ismerni kell a pontos
Notion property-neveket - ezeket viszont a korábbi import(ok) már berakták az
`extra` JSON-ba (a valós property névvel mint kulccsal), tehát innen, a már
Railway-en importált adatból ki lehet nyerni Notion hívás nélkül.

Használat (Railway-en, `railway ssh` után):

    python scripts/dump_extra_keys.py

A kimenetet (a mezőnevek listáját entitásonként) másold vissza a chatbe - abból
tudom a pontos oszlop-leképezést elkészíteni, ugyanúgy ahogy a ProjectCode/
Project/Contact/Employee/Rate esetében is."""

import sys
from collections import Counter
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.models.campaign import Campaign  # noqa: E402
from app.models.contract import Contract  # noqa: E402
from app.models.deliverable import Deliverable  # noqa: E402
from app.models.equipment import Assignment, Equipment  # noqa: E402
from app.models.finance import Expense, KpForgalom, Revenue  # noqa: E402
from app.models.task import Task  # noqa: E402
from app.models.timesheet import Timesheet  # noqa: E402

MODELS = [Contract, Equipment, Assignment, Campaign, Task, Expense, Revenue, KpForgalom, Deliverable, Timesheet]


def main() -> None:
    db = SessionLocal()
    try:
        for model in MODELS:
            rows = db.scalars(select(model)).all()
            key_counts: Counter[str] = Counter()
            sample_values: dict[str, object] = {}
            for row in rows:
                extra = getattr(row, "extra", None) or {}
                for key, value in extra.items():
                    key_counts[key] += 1
                    if key not in sample_values and value not in (None, "", [], {}):
                        sample_values[key] = value

            print(f"\n{model.__name__} ({len(rows)} sor) - {len(key_counts)} egyedi 'extra' mező")
            print("=" * 60)
            if not key_counts:
                print("  (nincs extra mező - vagy még nincs importált adat, vagy minden mező már saját oszlop)")
                continue
            for key, count in key_counts.most_common():
                sample = sample_values.get(key, "")
                sample_str = str(sample)[:60]
                print(f"  {key!r}: {count} sorban van érték, pl. {sample_str!r}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
