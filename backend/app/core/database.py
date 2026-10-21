from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

# A pool mérete a WORKEREKKEL EGYÜTT értendő: processzenként legfeljebb
# pool_size + max_overflow kapcsolat, és a web (WEB_CONCURRENCY worker, lásd
# Dockerfile) MELLETT a worker service is ebből a Postgresből dolgozik. A
# Railway Postgres alapból ~100 kapcsolatot enged - a keretet úgy osztjuk,
# hogy 2 web-worker (2x20) + a háttér-service kényelmesen beleférjen, és
# maradjon hely az adminisztrációs kapcsolatoknak is.
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=15,
    pool_timeout=30,
    # A rég nyitva tartott kapcsolatokat frissítjük - a felhős Postgres a
    # csendes kapcsolatot egy idő után eldobja, és e nélkül az első kérés
    # egy "server closed the connection" hibába futna.
    pool_recycle=1800,
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
