# Lara — üzemeltetés (operations)

Ez a dokumentum Lara modul futtatását, indítását és felügyeletét írja
le a HYPE OS meglévő infrastruktúráján. Nincs benne kitalált telepítés: csak a
repóban ténylegesen meglévő szolgáltatásokra és parancsokra épít.

## Komponensek

| Komponens | Mi az | Indítás |
|---|---|---|
| API | FastAPI (`app.main:app`) — az `/api/v1/admin-agent/*` végpontok | `uvicorn app.main:app` (meglévő `railway.json`) |
| Worker + Beat | Celery a megosztott `celery_app`-on (`app/workers/portal_tasks.py`); a beat embedded (`-B`) | `celery -A app.workers.portal_tasks worker -B` (meglévő `railway.worker.json`) |
| Adatbázis | PostgreSQL, Alembic migrációk | `alembic upgrade head` |
| Redis | Celery broker/result backend | meglévő env (`REDIS_URL` / `CELERY_*`) |

Lara NEM igényel külön Railway service-t: a meglévő worker betölti az
`app/workers/admin_agent_tasks.py`-t (lásd a `portal_tasks.py` alján az importot),
így az éjszakai tanulás és a heti eval a meglévő beaten fut.

## Indító parancsok (a tényleges repó alapján)

```bash
# Migráció (additív; a második Lara migráció: h1b8y29v6w50)
cd backend && alembic upgrade head

# API (fejlesztés)
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000

# Worker + embedded beat (éjszakai distill 02:00, heti eval hétfő 03:00)
cd backend && celery -A app.workers.portal_tasks worker -B --loglevel=info

# Tesztek (Lara rész)
cd backend && python -m pytest tests/test_admin_agent_*.py -q

# Frontend build
cd frontend && npm run build
```

## Ütemezett feladatok

Az `app/workers/admin_agent_tasks.py` a megosztott `celery_app.conf.beat_schedule`-be
regisztrál (a `calendar_tasks.py` mintájára):

- `admin_agent.nightly_distill` — `crontab(hour=2, minute=0)`. A háttér-tanuló
  (distill). Csak akkor dolgozik, ha a modul engedélyezett; egyébként kihagyja.
- `admin_agent.weekly_eval` — `crontab(hour=3, minute=0, day_of_week=1)`. A heti
  értékelés; a beépített biztonsági eseteket a modul állapotától függetlenül futtatja.

A crontab a Celery beat időzónáját használja. Ha a rendszer UTC-ben jár, a fenti
időpontok UTC szerintiek — az `ADMIN_AGENT_TIMEZONE=Europe/Budapest` a
megjelenítést és a szándékolt helyi időt dokumentálja; a nyári/téli időszámítás
pontos kezeléséhez a beat `timezone` beállítását kell ehhez igazítani.

## Vészleállítás (kill switch)

- A felületről: **Beállítások → Vészleállítás**, vagy `POST /api/v1/admin-agent/pause`.
- Feloldás: `POST /api/v1/admin-agent/resume`.
- A vészleállítást a policy engine MINDEN mellékhatásos lépés előtt ellenőrzi
  (nem csak a futás elején). A már elindult, nem megszakítható külső műveleteket
  ez NEM vonja vissza — ezeket a napló és a végrehajtási rekord mutatja.

## Egészség és felügyelet

- Feladatállapotok: `GET /api/v1/admin-agent/overview` (nyitott/lejárt/várakozó),
  `.../audit` (append-only napló).
- Integrációk: az overview és a Beállítások `integraciok` mezője „Kész / Beállítás
  szükséges" állapotot mutat (Gmail, modell, tároló). A titkok értéke sosem kerül
  a böngészőbe.
- Az API elérhetősége önmagában NEM jelenti, hogy a worker egészséges — a
  háttérfutások eredményét a Tanulás és minőség aloldal, illetve a
  `learning-runs` / `evaluations` végpontok mutatják.

## Migráció és visszaállás

- A változtatások additívak; a downgrade a két Lara migrációt fordított
  sorrendben bontja (kézzel: `alembic downgrade -1`). Éles adaton destruktív
  downgrade-et NE futtass automatikusan — előbb mentés.
- Alkalmazásverzió-visszalépés a kódot állítja vissza; a MÁR MEGTÖRTÉNT külső
  üzleti mellékhatást (pl. elküldött e-mail, rögzített kiadás) az alkalmazás-
  rollback NEM vonja vissza — ezekhez a külön, jóváhagyásos helyesbítési folyamat
  való.

## Első indulás (ajánlott sorrend)

1. Migráció (`alembic upgrade head`), majd az API és a worker indítása.
2. Integrációk ellenőrzése a Beállítások oldalon (Gmail/modell/tároló).
3. A modul KIKAPCSOLVA marad; L0-ban figyeld az elemzéseket és a javaslatokat.
4. Kijelölt, szűk bemeneti kör (nem a teljes régi postaláda).
5. Eredmények/javítások átnézése; ezekből a háttér-tanuló szabály-JELÖLTEKET készít.
6. L1 (jóváhagyásos) használat: a mellékhatás bekapcsolása + típusonként L1 trust.
7. L2 KIZÁRÓLAG később, mérés és emberi engedély után, szűk, alacsony kockázatú körre.
