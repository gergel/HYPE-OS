from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    # Egyetlen lekérdezés se futhasson korlátlanul: egy beragadt vagy
    # zárolásra váró SQL 60 mp után hibával leáll, ahelyett hogy fogva
    # tartaná a kapcsolatot és sorban állítaná mögé az összes többi kérést
    # (ez történt, amikor "minden oldal csak töltött").
    connect_args={"options": "-c statement_timeout=60000 -c lock_timeout=15000"},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
