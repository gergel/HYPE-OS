"""Teszt-környezet: SQLite (alapértelmezés) vagy TEST_DATABASE_URL (pl. PostgreSQL),
lokális privát objektumtár egy ideiglenes könyvtárban, valós FastAPI TestClient.

A beállításokat környezeti változóként adjuk át, MIELŐTT az app importálódna.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from datetime import UTC, datetime

_TMP = tempfile.mkdtemp(prefix="hype-os-tests-")
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{_TMP}/test.db"
os.environ["STORAGE_BACKEND"] = "local"
os.environ["LOCAL_STORAGE_ROOT"] = f"{_TMP}/storage"
os.environ["SECRET_KEY"] = "test-secret-not-for-production"
os.environ["EXPORT_PROGRESS_INTERVAL_SECONDS"] = "0"
os.environ["EXPORT_CHUNK_BYTES"] = str(64 * 1024)
os.environ["EXPORT_TTL_HOURS"] = "48"
os.environ["EXPORT_DOWNLOAD_URL_TTL_SECONDS"] = "300"
os.environ["EXPORT_LEASE_SECONDS"] = "60"
os.environ["EXPORT_MAX_ATTEMPTS"] = "3"
os.environ["ENVIRONMENT"] = "test"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.core import database
from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models import Base
from app.models.client import Client
from app.models.employee import Employee, EmployeeType, SystemRole
from app.models.media import Folder, Media
from app.models.project import Project
from app.models.project_code import ProjectCode
from app.services.storage import LocalObjectStorage, reset_storage_cache

IS_SQLITE = database.engine.url.get_backend_name() == "sqlite"

if IS_SQLITE:
    @event.listens_for(database.engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.drop_all(database.engine)
    Base.metadata.create_all(database.engine)
    yield
    Base.metadata.drop_all(database.engine)
    shutil.rmtree(_TMP, ignore_errors=True)


@pytest.fixture(autouse=True)
def _clean_tables():
    """Minden teszt tiszta táblákkal és üres tárral indul."""
    yield
    with database.engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    shutil.rmtree(settings.local_storage_root, ignore_errors=True)
    os.makedirs(settings.local_storage_root, exist_ok=True)
    reset_storage_cache()


@pytest.fixture
def db() -> Session:
    session = database.SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def storage() -> LocalObjectStorage:
    reset_storage_cache()
    return LocalObjectStorage(settings.local_storage_root)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def auth(user: Employee) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user.id), user.role.value)}"}


class Seed:
    """Két bérlő (Client A, Client B), mindkettőnek egy projekt + galéria."""

    def __init__(self, db: Session, storage: LocalObjectStorage) -> None:
        self.db = db
        self.storage = storage
        self.client_a = Client(nev="Alfa Kft")
        self.client_b = Client(nev="Béta Zrt")
        db.add_all([self.client_a, self.client_b])
        db.flush()
        self.code_a = ProjectCode(projektkod="ALFA-001", client_id=self.client_a.id)
        self.code_b = ProjectCode(projektkod="BETA-001", client_id=self.client_b.id)
        db.add_all([self.code_a, self.code_b])
        db.flush()
        self.project_a = Project(nev="Alfa forgatás", project_code_id=self.code_a.id)
        self.project_b = Project(nev="Béta forgatás", project_code_id=self.code_b.id)
        db.add_all([self.project_a, self.project_b])
        db.flush()

        pw = hash_password("titok123")
        self.admin = Employee(full_name="Admin", tipus=EmployeeType.BELSOS, email="admin@hype.test",
                              role=SystemRole.ADMIN, hashed_password=pw)
        self.vago = Employee(full_name="Vágó", tipus=EmployeeType.VAGO, email="vago@hype.test",
                             role=SystemRole.VAGO, hashed_password=pw)
        self.ugyfel_a = Employee(full_name="Alfa ügyfél", tipus=EmployeeType.KULSOS, email="a@alfa.test",
                                 role=SystemRole.UGYFEL, hashed_password=pw, client_id=self.client_a.id)
        self.ugyfel_b = Employee(full_name="Béta ügyfél", tipus=EmployeeType.KULSOS, email="b@beta.test",
                                 role=SystemRole.UGYFEL, hashed_password=pw, client_id=self.client_b.id)
        self.ugyfel_orphan = Employee(full_name="Ügyfél bérlő nélkül", tipus=EmployeeType.KULSOS,
                                      email="orphan@x.test", role=SystemRole.UGYFEL, hashed_password=pw)
        db.add_all([self.admin, self.vago, self.ugyfel_a, self.ugyfel_b, self.ugyfel_orphan])
        db.commit()
        self.files: dict[int, dict[str, bytes]] = {}

    def add_media(self, project: Project, title: str, content: bytes, *, folder: Folder | None = None,
                  key: str | None = None, status: str = "ready", ext: str = "jpg") -> Media:
        key = key or f"{settings.media_object_prefix}{project.id}/{hashlib.md5(title.encode()).hexdigest()}.{ext}"
        with self.storage.open_write(key) as out:
            out.write(content)
        media = Media(
            title=title, project_id=project.id, folder_id=folder.id if folder else None,
            storage_key=key, size_bytes=len(content),
            checksum_sha256=hashlib.sha256(content).hexdigest(), status=status,
            created_at=datetime(2026, 9, 1, 12, 0, 0, tzinfo=UTC),
        )
        self.db.add(media)
        self.db.commit()
        self.db.refresh(media)
        self.files.setdefault(project.id, {})[key] = content
        return media

    def add_folder(self, project: Project, nev: str, sort_order: int = 0) -> Folder:
        folder = Folder(nev=nev, project_id=project.id, sort_order=sort_order)
        self.db.add(folder)
        self.db.commit()
        self.db.refresh(folder)
        return folder

    def small_gallery(self, project: Project, *, files: int = 5, size: int = 20_000) -> list[Media]:
        folder = self.add_folder(project, "Válogatás")
        items = []
        for index in range(files):
            content = os.urandom(size)
            items.append(self.add_media(project, f"kép {index:03d}", content,
                                        folder=folder if index % 2 else None))
        return items


@pytest.fixture
def seed(db: Session, storage: LocalObjectStorage) -> Seed:
    return Seed(db, storage)
