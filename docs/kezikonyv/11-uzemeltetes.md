# 11 - Üzemeltetés

## Indítás fejlesztéshez

```bash
cp backend/.env.example backend/.env
docker compose up --build
```

- Backend + API dokumentáció: http://localhost:8000/docs
- Frontend: http://localhost:3000
- Postgres: localhost:5432 (`hype` / `hype` / `hype_os`)

Az első admin nem API-ból jön létre:

```bash
docker compose exec backend python scripts/create_admin.py admin@hype.hu jelszo123 "Admin Név"
```

Backend külön, Docker nélkül: lásd `backend/README.md`
(venv → `alembic upgrade head` → `uvicorn app.main:app --reload`).

## Szolgáltatások

| Szolgáltatás | Mi |
|---|---|
| `postgres` | Az adatbázis - single source of truth |
| `redis` | Sor a háttérfeladatokhoz |
| `backend` | FastAPI |
| `media-worker` | Celery worker (portál videó-feldolgozás) |
| `frontend` | Next.js |

Railway-en a backend a `backend/railway.json`, a worker a
`backend/railway.worker.json` szerint indul - utóbbi `celery ... -B` kapcsolóval,
tehát a **Beat ütemező is ott fut** (percenkénti naptár-szinkron, utókövető email).

## Migrációk

Alembic, `backend/alembic/`. Új migráció:

```bash
docker compose exec backend alembic revision --autogenerate -m "rövid leírás"
docker compose exec backend alembic upgrade head
```

Az autogenerate javaslatát mindig nézd át - a nem triviális átalakításokat
(átnevezés, adatmigráció) kézzel kell megírni.

## Környezeti változók

A teljes, hiteles lista: `backend/app/core/config.py` (a `Settings` osztály mezői,
nagybetűs env-névvel). A `backend/.env.example` a fontosabbakat gyűjti egybe.

**Kötelező:**

| Név | Mire |
|---|---|
| `DATABASE_URL` | Postgres. `postgres://` / `postgresql://` URL-t a rendszer automatikusan átírja psycopg3 driverre, tehát a Railway által adott URL-t nem kell bütykölni |
| `SECRET_KEY` | JWT aláírás - élesben mindenképp cseréld |
| `VEDETT_ADMIN_EMAILEK` | A védett rendszergazda fiók(ok) címe, vesszővel. Sosem inaktív, mindig admin, nem korlátozható - lásd [02-auth-jogosultsag.md](02-auth-jogosultsag.md) |

**Fontos, de opcionális** (hiányukban az adott képesség jelez vissza, az app megy):

| Terület | Változók |
|---|---|
| Storage | `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `R2_PUBLIC_URL` |
| Gmail | `GMAIL_SENDER`, `GMAIL_SENDER_NAME`, `DISPO_SENDER_NAME`, `MODOSITAS_SENDER`, `GMAIL_OAUTH_TOKEN_JSON` *vagy* `GMAIL_SERVICE_ACCOUNT_JSON` + `GMAIL_IMPERSONATE_USER`, `HYPE_CC` |
| Docs/Drive | `GOOGLE_DOCS_OAUTH_TOKEN_JSON`, `GDOC_DISPO_TEMPLATE_ID`, `GDOC_CONTRACT_TEMPLATE_ID`, `GDOC_ALVALLALKOZOI_SZERZODES_TEMPLATE_ID`, `GDOC_KERETSZERZODES_TEMPLATE_ID`, `GDOC_KULSOS_TIG_TEMPLATE_ID`, `GDOC_BELSOS_TIG_TEMPLATE_ID`, `GDOC_MEGRENDELOI_ESETI_TEMPLATE_ID`, `GDOC_MEGRENDELOI_TIG_TEMPLATE_ID`, `GDOC_MEGRENDELOI_KERET_TEMPLATE_ID`, `GDOC_KERET_MODOSITAS_TEMPLATE_ID`, `GDOC_KERET_MODOSITAS_FOLDER_ID`, `GDOC_OUTPUT_FOLDER_ID`, `DRIVE_FOLDER_ID`, `DRIVE_KULSOS_TIG`, `DRIVE_BELSOS_TIG`, `DRIVE_DISZPO_FOLDER_ID` |
| Naptár | `GOOGLE_CALENDAR_OAUTH_TOKEN_JSON` *vagy* `GOOGLE_CALENDAR_SERVICE_ACCOUNT_JSON` + `GOOGLE_CALENDAR_IMPERSONATE_USER`, `GOOGLE_CALENDAR_ID`, `GOOGLE_CALENDAR_NAME`, `NAPTAR_MEETING_SZINEK`, `GOOGLE_CALENDAR_OAUTH_CLIENT_ID/SECRET` |
| Portál/fizetés | `FRONTEND_BASE_URL` (admin domain), `PORTAL_BASE_URL` (portál domain), `API_BASE_URL`, `BARION_POS_KEY`, `BARION_ENV`, `BARION_PAYEE`, `SZAMLAZZ_AGENT_KEY`, `PORTAL_NOTION_API_KEY`, `PORTAL_NOTION_DATABASE_ID` |
| AI | `GEMINI_API_KEY`, `GEMINI_MODEL` |
| Notion import | `NOTION_API_KEY` |
| Frontend | `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_BARION_PIXEL_ID`, `NEXT_PUBLIC_PORTAL_HOST`, `NEXT_PUBLIC_PORTAL_BASE_URL` |

Örökölt nevek, amiket szándékosan elfogadunk (hogy a különálló belsős-TIG program
Railway-beállítása változtatás nélkül működjön): `GOOGLE_DRIVE_TEMPLATE_ID`,
`NOTION_FILE_FOLDER_ID`, `TIGTOKEN_JSON`.

### Visszaesési láncok

Ezeket érdemes ismerni, mert magyarázzák, miért "működik" valami látszólag
beállítás nélkül is:

- Belsős TIG sablon: `GDOC_BELSOS_TIG_TEMPLATE_ID` → `GOOGLE_DRIVE_TEMPLATE_ID`
- Belsős TIG mappa: `DRIVE_BELSOS_TIG` → `NOTION_FILE_FOLDER_ID` → `GDOC_OUTPUT_FOLDER_ID` → `DRIVE_FOLDER_ID`
- Diszpó mappa: `DRIVE_DISZPO_FOLDER_ID` → `GDOC_OUTPUT_FOLDER_ID` → `DRIVE_FOLDER_ID` → Drive gyökér
- Keretszerződés mappa: üresen a **sablon saját mappájába** kerül (szándékos, így nincs külön karbantartandó mappa)
- Szerződésmódosítás mappa: `GDOC_KERET_MODOSITAS_FOLDER_ID` → `GDOC_KERETSZERZODES_FOLDER_ID` → `GDOC_OUTPUT_FOLDER_ID` → a **sablon saját mappája**
- Naptár OAuth kliens: `GOOGLE_CALENDAR_OAUTH_CLIENT_ID/SECRET` → `GMAIL_OAUTH_CLIENT_ID/SECRET`

### CORS és munkamenet

- `CORS_ORIGINS` alapértéke `*`. Ez itt biztonságos, mert az API kizárólag Bearer
  tokennel hitelesít (nincs cookie → nincs CSRF). A korábbi szigorú alapérték
  éles deployon néma hálózati hibát okozott minden írásnál, ezért lett wildcard.
- Ha csak a **megrendelői keretszerződések** kellenek a Notionból, van rájuk
  célzott szkript - a katalógus "Keretszerződések" lépése ugyanis a másik két
  forrása miatt a több száz soros "Külsős és belsős" táblát is végigolvassa:

  ```
  python scripts/megrendeloi_keretek_atmentese.py --proba   # mit tenne
  python scripts/megrendeloi_keretek_atmentese.py           # áthozatal
  ```

  Soronként kiírja, mi lett az adott céggel (képviselő, nyilvántartási szám,
  ügyfél-kapcsolat, fájl, és `projekt=bekötött/hivatkozott`), és idempotens -
  újrafuttatva frissít, nem duplikál. A `projekt` oszlop a keret alá tartozó
  projektkódokat köti be a keretszerződés felől is - lásd
  [10-integraciok.md](10-integraciok.md).

- `ACCESS_TOKEN_EXPIRE_MINUTES` alapja 30 nap, gördülő megújítással - lásd
  [02-auth-jogosultsag.md](02-auth-jogosultsag.md).

## Hibakeresés - mit nézz először

| Tünet | Hol kezdd |
|---|---|
| Egy oldal 403-at ad | A `nav.ts` `permissionPage` értéke egyezik-e a backend `page=`/`PAGE` konstansával ([02](02-auth-jogosultsag.md)) |
| Nem megy ki levél | `GMAIL_*` hitelesítés; a route hibaüzenete megmondja, mi hiányzik |
| A szerződésmódosítás nem megy ki, a többi levél igen | A `MODOSITAS_SENDER` cím nincs felvéve a küldő fiókban álnévként (Gmail → Beállítások → Fiókok → Küldés mint) ([06](06-papirozas.md)) |
| A módosítás levelén nem a fiók aláírása van | A token nem tudta kiolvasni a Gmail-beállítást (`gmail.settings.basic`/`gmail.readonly`) - ilyenkor a beépített tartalék aláírás megy, a küldés nem hasal el |
| Nem generálódik PDF | `GOOGLE_DOCS_OAUTH_TOKEN_JSON` scope-jai (`drive` + `documents`), sablon-ID |
| Nem frissül a naptár | `/api/v1/admin/calendar-sync` állapot; fut-e a Celery Beat |
| Nem indul a fizetés | `BARION_POS_KEY`, `BARION_ENV`, `FRONTEND_BASE_URL`/`API_BASE_URL` (a redirect és callback URL-hez) |
| Fizetés megvolt, számla nincs | `SZAMLAZZ_AGENT_KEY` - a fizetés érvényes, csak a számlázás maradt el ([09](09-media-portal.md)) |
| Videó feltöltve, de nem játszható | Fut-e a `media-worker`; R2 beállítás; ffmpeg a konténerben |
| Egy papír "hiányzónak" látszik, pedig megvan | `services/papir_fedettseg.py` - tétel nélküli sor esete ([06](06-papirozas.md)) |
| Notion import megszakad | Ne `railway ssh`-ból indítsd, hanem az admin végponton ([10](10-integraciok.md)) |
| A frontend build elhasal `Module not found: @vercel/turbopack-next/internal/font/google/font`-tal | A Google 404-et ad egy kért betűtípus-fájlra. Változó (variable) fontnál NE sorolj fel konkrét súlyokat (`weight`) - a Google már nem vágja belőlük a statikus példányokat (lásd `app/layout.tsx`) |

## Ami nincs kész

- Az `/api/v1/automation/generate-document` csak a Timeline-eseményt rögzíti; a
  tényleges PDF/Storage/Email pipeline a dokumentum-generáló motoron
  (`services/gdoc_template.py`) keresztül a konkrét modulokban él, nem itt.
- A GET lista/részlet végpontok szerepkör-ellenőrzése lazább, mint az írásé - a
  per-oldal jogosultság (`page_permissions`) viszont ezekre is vonatkozik.
