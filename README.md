# HYPE OS ("HYPE Brain")

Belső, videóprodukciós működésre szabott operatív rendszer, ami a jelenlegi Notion (43 adatbázis) +
17 Railway-szolgáltatás összeragasztott architektúráját váltja ki egyetlen, natív PostgreSQL-alapú
rendszerrel. Nem SaaS-termék, nem multi-tenant - kizárólag a HYPE (és a ContentBee márka) napi
működésére.

Ez a repó a **vadonatúj, önálló** HYPE OS kódbázisa - a `docs/` mappában lévő 6 dokumentum (termék-
specifikáció, AS-IS rendszertérkép, migration map, Railway-integráció, build roadmap, ER-diagram)
alapján épül, de semmilyen meglévő Notion/Railway kódra nem támaszkodik.

## Dokumentáció

**A rendszer működési leírása: [`docs/kezikonyv/`](docs/kezikonyv/README.md)** - témánként külön,
rövid fájlokban (architektúra, jogosultság, projektek, csapat, diszpó, papírozás, pénzügyek,
utómunka, portál, integrációk, üzemeltetés). Szándékosan nincs "egy nagy dokumentum": a rendszer
mérete mellett az kezelhetetlenné válik. A részletes indoklások a kód melletti docstringekben
élnek, a kézikönyv térkép hozzájuk.

A `docs/` gyökerében lévő 6 dokumentum a rendszer **megépítése előtti** tervezési anyag - az alábbi
modultábla is azt a Fázis 1 állapotot tükrözi. A jelenlegi működésre mindig a kézikönyv a hiteles.

## Architektúra

```
Next.js (frontend)  ──/api──▶  FastAPI (backend)  ──▶  PostgreSQL (single source of truth)
                                                    ──▶  Redis (cache/queue, előkészítve)
                                                    ──▶  Cloudflare R2 (storage, előkészítve)
```

- **Backend**: FastAPI + SQLAlchemy 2.0 + Alembic, `backend/`
- **Frontend**: Next.js 16 (App Router) + TypeScript + Tailwind CSS v4, sötét téma a mellékelt
  dashboard mockup alapján, `frontend/`
- **Adatbázis**: a `docs/hype_os_kapcsolati_abra.mermaid` 22 entitása (Client, Contact, Campaign,
  ProjectCode, Project, Contract, Employee, Rate, Timesheet, Deliverable, Feedback, Equipment,
  Assignment, Expense, Revenue, KpForgalom, Task, Callsheet, Portal, Payment, Media, Folder) +
  egy TimelineEvent entitás (a termékspecifikáció 8. modulja, esemény-napló minden entitáshoz)

## Gyors indítás

### Docker Compose-zal (ajánlott)

```bash
cp backend/.env.example backend/.env
docker compose up --build
```

- Backend: http://localhost:8000/docs
- Frontend: http://localhost:3000
- Postgres: localhost:5432 (`hype`/`hype`/`hype_os`)

Az első admin felhasználót közvetlenül a konténerben kell létrehozni (a `/api/v1/crew` végpont admin
jogot kér, tehát nincs API-s "első regisztráció"):

```bash
docker compose exec backend python scripts/create_admin.py admin@hype.hu jelszo123 "Admin Név"
```

### Manuálisan

Lásd `backend/README.md` és `frontend/README.md`.

## Modulok (Fázis 1, a termékspecifikáció sorrendje szerint)

| # | Modul | API prefix | Státusz |
|---|---|---|---|
| 1 | Auth | `/api/v1/auth` | kész (JWT, szerepkörök: admin/operator/vago/ugyfel) |
| 2 | Dashboard | `/api/v1/dashboard` | kész (élő összegzés API), UI kártyák a mockup alapján |
| 3 | Clients | `/api/v1/clients`, `/api/v1/contacts` | kész API, UI placeholder |
| 4 | Project Codes | `/api/v1/project-codes` | kész API, UI placeholder |
| 5 | Projects | `/api/v1/projects` | kész API, UI placeholder |
| 6 | Crew (Employee + Rate) | `/api/v1/crew`, `/api/v1/rates` | kész API, UI placeholder |
| 7 | Equipment | `/api/v1/equipment`, `/api/v1/assignments` | kész API **+ ütközés-detektálás** (409), UI placeholder |
| 8 | Timeline | `/api/v1/timeline` | kész API (esemény-napló), UI placeholder |
| 9 | Storage | `/api/v1/media`, `/api/v1/folders` | kész API (R2 kulcsokra épít), UI placeholder |
| 10 | Portal | `/api/v1/portal`, `/api/v1/payments` | kész API, UI placeholder |
| 11 | Automation | `/api/v1/automation/generate-document` | API-alak kész, PDF/Storage/Email Fázis 3 |
| 12 | Contracts | `/api/v1/contracts` | kész API, UI placeholder |
| 13 | Finance | `/api/v1/expenses`, `/api/v1/revenues`, `/api/v1/kp-forgalom` | kész API, UI placeholder |
| 14 | Campaign | `/api/v1/campaigns` | kész API, UI placeholder |
| 15 | AI Assistant | `/api/v1/ai-assistant/ask` | API-alak kész, RAG réteg Fázis 5 |

Utómunka (Deliverable/Timesheet/Feedback), Naptár/Diszpó (Callsheet) és Feladatok (Task) szintén
teljes CRUD API-val rendelkeznek, csak a termékspecifikáció IA-jában nem önálló számozott modulok.

## Miért nincs Notion-szinkron?

A `docs/hype_os_build_roadmap.md` Fázis 2 döntése szerint a HYPE OS **teljesen függetlenül** épül -
nincs élő Notion API-hívás. Fejlesztés/tesztelés alatt egy egyszeri, idempotens import-szkript hozza
át a Notion-adatot (ez még nincs megírva, Fázis 2 munka), a végén pedig egy tudatos, egyszeri cutover
váltja át a csapatot az új rendszerre.

## Dokumentáció

A `docs/` mappa a teljes tervezési alapot tartalmazza:

- `hype_os_termekspecifikacio.md` - termékvízió, modulok, IA, backend architektúra
- `hype_os_as_is_rendszerterkep.md` - a jelenlegi (Notion + Railway) rendszer végponttól végpontig
- `hype_os_migration_map.md` - a 43 Notion adatbázis → 22 domain entitás leképezése
- `hype_os_railway_integracio.md` - a 17 Railway-repó elemzése, mit kell átmenteni/kiváltani
- `hype_os_build_roadmap.md` - fázisterv (Fázis 0-5)
- `hype_os_kapcsolati_abra.mermaid` - a teljes ER-diagram (séma-forrás)
- `hype_os_dashboard_mockup.html` - a dashboard vizuális referenciája (sötét téma, üveg-hatású kártyák)

## Ismert nyitott pontok

Lásd `docs/hype_os_railway_integracio.md` 9. fejezetét: Payment/brand kezelés (HYPE + ContentBee),
a Hype-repo Notion-mezőinek tisztázása, és a Fázis 2 import-szkript még nincs megírva ebben a repóban.
