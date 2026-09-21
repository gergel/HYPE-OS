import asyncio
import json
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from starlette.requests import Request
from sqlalchemy import String, create_engine
from sqlalchemy.orm import Mapped, Session, mapped_column
from pydantic import BaseModel, ConfigDict
from app.core.database import Base
from app.services.offline_sync import check_precondition
from app.api.crud_router import build_crud_router


@pytest.mark.parametrize("metadata", [None, {}, {"version": 2, "expected": {}}, {"version": 1, "expected": []}, {"version": 1, "expected": {"other": 1}}])
def test_invalid_metadata_rejected(metadata):
    with pytest.raises(HTTPException) as error:
        check_precondition(metadata, {"title": "new"}, {"title": "old"})
    assert error.value.status_code == 422


def test_conflict_preserves_remote_change():
    with pytest.raises(HTTPException) as error:
        check_precondition({"version": 1, "expected": {"title": "old"}}, {"title": "local"}, {"title": "remote"})
    assert error.value.status_code == 409


def test_missing_and_null_are_distinct():
    with pytest.raises(HTTPException):
        check_precondition({"version": 1, "expected": {"hidden": None}}, {"hidden": "new"}, {})
    assert not check_precondition({"version": 1, "expected": {"title": None}}, {"title": "new"}, {"title": None})


def test_lost_reply_is_idempotent():
    assert check_precondition({"version": 1, "expected": {"title": "old"}}, {"title": "new"}, {"title": "new"})


class OfflineRecord(Base):
    __tablename__ = "test_offline_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String)


class RecordSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str


def request(body):
    async def receive():
        return {"type": "http.request", "body": json.dumps(body).encode(), "more_body": False}
    return Request({"type": "http", "method": "PATCH", "path": "/records/1", "headers": []}, receive)


def test_crud_replay_does_not_repeat_hooks_or_overwrite_conflict():
    calls = []
    router = build_crud_router(model=OfflineRecord, create_schema=RecordSchema, update_schema=RecordSchema,
        read_schema=RecordSchema, prefix="/test-offline-records", tags=["test"], page="/test", write_roles=(),
        after_update=lambda *args: calls.append("updated"))
    update = next(route.endpoint for route in router.routes if "PATCH" in route.methods)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[OfflineRecord.__table__])
    with Session(engine) as db:
        db.add(OfflineRecord(id=1, title="old")); db.commit()
        payload = {"title": "new", "_offline": {"version": 1, "expected": {"title": "old"}}}
        result = asyncio.run(update(1, request(payload), db, SimpleNamespace(id=1)))
        assert result["title"] == "new" and len(calls) == 1
        result = asyncio.run(update(1, request(payload), db, SimpleNamespace(id=1)))
        assert result["title"] == "new" and len(calls) == 1
        db.get(OfflineRecord, 1).title = "someone else"; db.commit()
        with pytest.raises(HTTPException) as error:
            asyncio.run(update(1, request(payload), db, SimpleNamespace(id=1)))
        assert error.value.status_code == 409
        db.rollback()
        assert db.get(OfflineRecord, 1).title == "someone else"
    engine.dispose()
