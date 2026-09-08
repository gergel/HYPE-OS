# HYPE OS - Backend

FastAPI + SQLAlchemy 2.0 + Alembic + PostgreSQL. Lásd a repó gyökerében lévő `README.md`-t a teljes architektúráért.

## Fejlesztés

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # állítsd be a DATABASE_URL-t
alembic upgrade head
python scripts/create_admin.py admin@hype.hu jelszo123 "Admin Név"
uvicorn app.main:app --reload
```

API dokumentáció: `http://localhost:8000/docs`

## Struktúra

- `app/models/` - SQLAlchemy modellek, a `hype_os_kapcsolati_abra.mermaid` 22 entitása alapján
- `app/schemas/` - Pydantic Create/Update/Read sémák modulonként
- `app/api/routes/` - egy fájl modulonként (`hype_os_termekspecifikacio.md` 15 modulja szerint)
- `app/api/crud_router.py` - generikus CRUD router factory, hogy a 20+ entitáshoz ne kelljen ismételni a boilerplate-et
- `app/core/` - config, DB session, auth/JWT
- `alembic/` - migrációk

## Ismert korlátok (Fázis 0 scope)

- Az Automation modul (`/api/v1/automation/generate-document`) csak a Timeline Event-et rögzíti - a PDF/Storage/Email pipeline Fázis 3 munka.
- Az AI Assistant (`/api/v1/ai-assistant/ask`) API-alak kész, a RAG réteg Fázis 5 munka (lásd `hype_os_build_roadmap.md`).
- A GET lista/részlet végpontok egyelőre nincsenek szerepkörhöz kötve (csak írás), ezt élesítés előtt szigorítani kell.


## Galéria ZIP64 export worker

A teljes galéria letöltését **nem** az API-kérés és nem a böngésző csomagolja, hanem
egy tartós háttérfeladat (`gallery_export_jobs` tábla) és egy külön worker-processz:

```bash
alembic upgrade head                      # 34d5969952c8: gallery_export_jobs, BIGINT size_bytes, employees.client_id
python -m app.worker                      # folyamatos futás (EXPORT_WORKER_CONCURRENCY szál)
python -m app.worker --once               # a jelenlegi sor feldolgozása, majd kilépés (cron/teszt)
python -m app.worker cleanup              # lejárt csomagok törlése (csak EXPORT_OBJECT_PREFIX alatt)
python -m app.worker backfill-sizes       # hiányzó Media.size_bytes pótlása a tárból
```

Részletek, konfiguráció, tárhely/költség és a mérési jegyzőkönyvek: `docs/gallery-export.md`.

Tesztek:

```bash
pip install -r requirements-dev.txt
pytest tests -v                                                        # SQLite, társzerver nélkül
TEST_DATABASE_URL=postgresql+psycopg://hype:hype@localhost:5432/hype_os_test pytest tests -v
python scripts/bench_gallery_export.py --total-bytes 5000000000 --file-count 40 --label 5gb  # ZIP64 mérés
python scripts/ui_e2e_gallery_export.py                                # Playwright UI e2e (frontend build után)
```
