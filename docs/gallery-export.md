# Galéria ZIP64 export - akár 50 GB egyetlen fájlként

Branch: `claude/gallery-download-zip64-fxvjy5`. Ez a dokumentum a megvalósítás
gyökérokát, architektúráját, konfigurációját, üzemeltetését és a **ténylegesen
lefuttatott** ellenőrzéseket rögzíti. A logok és jegyzőkönyvek a
`docs/gallery-export-evidence/` mappában vannak (titkok nélkül).

---

## 1. Kiindulási állapot és gyökérok

### Mit találtam a repóban (a feladat első lépése)

| Terület | Tényleges állapot a `main`-en |
|---|---|
| **Képtárolás** | A `Media` sor csak egy `storage_key` sztringet tárol. **Nincs semmilyen tárkliens** a kódban: a `boto3` és a `redis` deklarált függőség, de egyetlen sor sem használja. A "Cloudflare R2" csak a dokumentációban és a `.env.example`-ben létezik. Feltöltő/letöltő végpont nincs. |
| **Galéria-jogosultság** | A generikus CRUD router (`build_crud_router`) **minden GET végpontot hitelesítés nélkül** szolgál ki. Így a `/api/v1/media`, `/api/v1/folders` és a `/api/v1/portal` (benne a `share_token`) **bárki számára olvasható** volt. A `SystemRole.UGYFEL` szerepkörhöz nem tartozott bérlő-kulcs (nem lehetett megmondani, melyik ügyfélé a felhasználó). |
| **Letöltési folyamat** | **Nem létezik.** Nincs ZIP-csomagolás, nincs háttérfeladat, nincs letöltési végpont, nincs Range-támogatás. Frontend oldalon a `media-portal` egy placeholder. |
| **Hosting** | `docker-compose.yml`: Postgres 16 + Redis 7 + FastAPI (uvicorn) + Next.js. Nincs worker-processz. A tervezett éles környezet Railway (a `docs/hype_os_railway_integracio.md` szerint). |

### Elsődleges gyökérok

**Nincs szerveroldali csomagolási és letöltési útvonal.** Egy 50 GB-os galéria
letöltése csak úgy lett volna megkísérelhető, hogy vagy a böngésző rak össze
egy Blob-ot (a memóriakorlát miatt lehetetlen), vagy egy web/serverless kérés
tart órákig (Railway és minden proxy időtúllépéssel megszakítja, és
újrapróbálás után elölről kezdi). Ezért kellett egy **tartós háttérfeladat +
privát objektumtár + Range-képes, jogosultság-ellenőrzött letöltés** hármas.

### Másodlagos, önálló hibák (bizonyítékkal)

1. **`media_items.size_bytes` 32 bites `INTEGER`** - egyetlen 2 147 483 647
   bájtnál nagyobb fájl (pl. 4K/ProRes master) mérete sem tárolható:
   `ERROR: integer out of range`. **Pontosítás:** ez *nem* az 50 GB-os galéria
   letöltés oka - sok kisebb képnél a `SUM(integer)` PostgreSQL-en `bigint`, az
   összméret tehát helyesen kijön. Bizonyíték valódi PostgreSQL 16-on:
   `docs/gallery-export-evidence/rootcause-size-bytes-overflow.log`.
2. **Nyilvános olvasás a média/portál CRUD-on** (`share_token` szivárgás) - a
   tesztkészlet `test_media_and_portal_crud_reads_now_require_auth` esete a
   javítás után 401/403-at vár és kap.

---

## 2. Célarchitektúra (megvalósítva)

```
Böngésző (Next.js)                FastAPI (web)                       Worker (python -m app.worker)
─────────────────                 ──────────────                      ────────────────────────────
POST /projects/{id}/gallery-export ─► terv + ujjlenyomat ─► gallery_export_jobs (queued)
GET  /projects/{id}/gallery-export ─► aktuális verzió jobja                    │ atomikus UPDATE-elvétel
GET  /gallery-exports/{uuid}       ─► állapot + valós haladás  ◄── heartbeat ──┤ streamelt ZIP64 (STORE)
POST /gallery-exports/{uuid}/download-url ─► aláírt/presigned URL             │ forrás: objektumtár (stream)
GET  /gallery-exports/{uuid}/download?token= ─► Range/ETag/Content-Length      ▼ cél: objektumtár (multipart)
                                                            privát objektumtár:  media/...  (eredetik, soha nem törli)
                                                                                 exports/... (csomagok, TTL 48 h)
```

* **Objektumtár-absztrakció** (`app/services/storage/`): `local` (privát
  könyvtár; fejlesztés, CI, ez a repó eddig ezt sem tudta) és `s3` (Cloudflare
  R2 / S3-kompatibilis privát bucket, multipart feltöltés). Nem feltételezi,
  hogy a fájlok S3-ban vannak - a backend a `STORAGE_BACKEND` beállítással
  választható.
* **ZIP64 STORE író** (`app/services/zip64.py`): saját, seek nélküli, egy
  menetes író. Konstans memória, **bájtra pontosan előre számított méret**
  (`predict_archive_size`), determinisztikus kimenet (stabil sha256/ETag), UTF-8
  nevek, ZIP64 EOCD + locator mindig, ZIP64 extra mezők a spec szerint (>= 4 GiB
  méret/offszet), data descriptor (8 bájtos) alapból; opcionális
  `CRC_IN_HEADER` mód legacy kliensekhez (kétszeres olvasás árán).
* **Tartós job** (`gallery_export_jobs`): állapotok `queued / running / ready /
  failed / expired`; `bytes_done`, `files_done`, `expected_archive_bytes` a valós
  haladáshoz; `attempts/max_attempts`, `lease_expires_at` (stale), `next_attempt_at`
  (exponenciális backoff), `expires_at` (TTL), `object_key/size/etag/sha256`.
* **Idempotencia / újrahasznosítás**: `UNIQUE (project_id, source_fingerprint)`.
  Az ujjlenyomat a galéria tartalmából (fájl-id, kulcs, méret, sha256, név, mappa,
  létrehozás ideje) számolt sha256. Dupla kattintás -> ugyanaz a job (200); kész
  export ugyanarra a verzióra -> újrahasznosítva; változott galéria -> új
  ujjlenyomat -> új job; hibás/lejárt -> ugyanaz a sor újraindul.
* **Nem fed el hibát sikerrel**: a worker minden fájlnál `stat`-tal ellenőrzi a
  létezést és a méretet; írás közben a bájtszámot és a CRC-t; a végén a kiírt
  méretet a tervezett mérethez és az **újraszámolt ujjlenyomatot** az eredetihez.
  Bármely eltérés -> `failed` (`source_missing` / `source_changed`), a fél csomag
  törölve.
* **Jogosultság három ponton**: létrehozás, lekérdezés, link kiadása - és a link
  beváltásakor negyedszer is (DB-ből, visszavont felhasználó esetén a régi link
  is 403). Belsős szerepkörök (`admin/operator/vago`) mindent látnak; az `ugyfel`
  csak a saját `employees.client_id` bérlőjének projektjeit. **Idegen bérlő:
  404**, nem 403 (a létezés sem szivárog). A job sor `client_id`-t is tárol, a
  lista ezzel szűr.
* **Letöltés**: `s3` backendnél presigned R2 URL (`response-content-disposition`
  fejléccel), `local` backendnél saját végpont **HTTP Range** (206/416),
  `If-Range`, `ETag` (= archívum sha256), `Accept-Ranges`, pontos
  `Content-Length`, RFC 5987 `Content-Disposition` (Unicode fájlnév). A link
  lejár (`EXPORT_DOWNLOAD_URL_TTL_SECONDS`), de **ugyanarra a változatlan
  objektumra** újítható: a félbeszakadt letöltés folytatható.
* **Fájlnevek**: NFC-normalizálás, path traversal / elválasztók / Windows-tiltott
  és vezérlőkarakterek / Unicode formátumkarakterek (pl. RTL override)
  semlegesítése, Windows-foglalt nevek (`CON`, `LPT1`...), záró pont/szóköz,
  200 bájtos UTF-8 korlát a kiterjesztés megtartásával, **kis/nagybetű-független
  egyediség** `név (2).kit` alakban.
* **TTL és takarítás**: `EXPORT_TTL_HOURS` (alapból 48). A `cleanup` csak az
  `EXPORT_OBJECT_PREFIX` (`exports/`) alatti kulcsot törölheti - a törlő
  függvény prefixre ellenőriz, az eredeti `media/` objektumokhoz **soha** nem nyúl
  (tesztelve).
* **Galéria-véglegesítési horog**: `prepare_export_on_gallery_finalized(db,
  project_id)` - a Portal `live`-ra váltásához vagy a Deliverable
  `anyag_kikuldve` eseményéhez köthető; a csomag így már a letöltési igény előtt
  elkészül. Timeline-események: `GalleryExportReady / Failed / Expired`.
* **UI** (`/projektek/{id}/galeria`, `GalleryExportPanel`): öt állapot (Várakozó,
  Készülő, Kész, Hibás, Lejárt), valós százalék és bájtszám 2 mp-es lekérdezéssel,
  kliensoldali kettős-kattintás védelem, az oldal újranyitásakor a **szerver**
  adja vissza az aktuális jobot (nincs böngésző-állapot).

---

## 3. Konfiguráció

`backend/.env` (lásd `.env.example`):

| Változó | Alapérték | Jelentés |
|---|---|---|
| `STORAGE_BACKEND` | `local` | `local` vagy `s3` (R2) |
| `LOCAL_STORAGE_ROOT` | `./var/storage` | privát könyvtár `local` esetén (API + worker közös volume) |
| `MEDIA_OBJECT_PREFIX` | `media/` | az eredetik prefixe (a takarítás soha nem nyúl ide) |
| `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME` | - | R2 hozzáférés (`s3`) |
| `R2_ENDPOINT_URL`, `R2_REGION` | account-alapú, `auto` | opcionális felülírás |
| `EXPORT_OBJECT_PREFIX` | `exports/` | a csomagok prefixe (csak ez törölhető) |
| `EXPORT_TTL_HOURS` | `48` | kész csomag élettartama |
| `EXPORT_DOWNLOAD_URL_TTL_SECONDS` | `900` | letöltési link érvényessége (megújítható) |
| `EXPORT_WORKER_CONCURRENCY` | `2` | párhuzamos jobok egy worker-processzben |
| `EXPORT_MAX_ATTEMPTS` | `3` | próbálkozások (retry backoff: 30 s · 2^n, max 15 perc) |
| `EXPORT_LEASE_SECONDS` | `120` | heartbeat-bérlet; lejárta után a job stale -> újra sorba |
| `EXPORT_CHUNK_BYTES` | `8388608` | olvasási darab (a worker memóriájának fő tétele) |
| `EXPORT_S3_MULTIPART_PART_BYTES` | `67108864` | S3 part-méret (min. 5 MiB; max. 10 000 part -> 64 MiB-tal 640 GB) |
| `EXPORT_MAX_FILES` | `200000` | fájlszám-korlát (a központi könyvtár memóriában épül) |
| `EXPORT_ZIP_STREAMING_MODE` | `true` | `false` = CRC a fejlécben (kétszeres forrásolvasás) |

## 4. Migráció

```bash
cd backend && alembic upgrade head     # 55ae8901b9c5 -> 34d5969952c8
```

A `34d5969952c8_gallery_export_zip64.py` migráció: új `gallery_export_jobs`
tábla + `gallery_export_status` enum, `media_items.size_bytes` INTEGER -> BIGINT
(**PostgreSQL-en táblaújraírás**: nagy `media_items` táblánál karbantartási
ablakban), `media_items.checksum_sha256`, `employees.client_id` (FK
`fk_employees_client_id`). Az `upgrade -> downgrade -> upgrade` és az
`alembic check` valódi PostgreSQL 16-on ellenőrizve:
`docs/gallery-export-evidence/migration-postgres.log`.

**Adatfeltöltés a migráció után:** az `ugyfel` szerepkörű felhasználóknál töltsd
ki az `employees.client_id`-t, különben (biztonságos alapértelmezésként) semmit
nem látnak.

## 5. Worker indítása

```bash
python -m app.worker                    # folyamatos, EXPORT_WORKER_CONCURRENCY szál
python -m app.worker --concurrency 4
python -m app.worker --once             # sor feldolgozása és kilépés (cron)
python -m app.worker cleanup            # TTL-lejárat + takarítás (a futó worker 30 mp-enként magától is)
python -m app.worker backfill-sizes [--project-id N]
```

Docker Compose: az `export-worker` szolgáltatás már benne van
(`docker compose up --build`; skálázás: `--scale export-worker=2`). Railway-en
külön service ugyanabból az image-ből, start command `python -m app.worker`,
ugyanazokkal az env-változókkal; `STORAGE_BACKEND=s3` kötelező, mert a Railway
fájlrendszer nem közös az API és a worker között.

Leállítás: SIGTERM -> a futó job befejeződik, új nem indul. Ha a processz
meghal, a job bérlete lejár (`EXPORT_LEASE_SECONDS`), a következő worker
visszateszi a sorba (max. `EXPORT_MAX_ATTEMPTS`, utána `failed/stale_timeout`).

## 6. Tárhely és költség

* **STORE mód**: a csomag mérete = a forrás mérete + ~90-130 bájt/fájl + ~100
  bájt. Egy 50 GB-os galéria csomagja ~50 GB **plusz** tárhely a TTL alatt.
* **Nincs staging lemez**: a worker közvetlenül az objektumtárba streamel;
  memória szálanként ~`EXPORT_CHUNK_BYTES` (+ S3-nál egy part-puffer,
  alapból 64 MiB) + Python alap (~100 MB mérve).
* **R2 költség (nagyságrend, saját árlista szerint ellenőrizendő)**: tárolás
  ~0,015 USD/GB/hó -> egy 50 GB-os csomag 48 órára ~0,05 USD; egress az
  internetre R2-nél díjmentes; műveletek: fájlonként 1 GET (Class B) +
  part-onként 1 PUT (Class A). Kétszer olvasás (`EXPORT_ZIP_STREAMING_MODE=false`)
  duplázza a GET-eket.
* **Lokális backend**: a `LOCAL_STORAGE_ROOT` alatt forrás + csomag; a TTL-es
  takarítás felszabadítja a csomagokat.

## 7. Lefuttatott ellenőrzések (pontos parancsok és eredmények)

| # | Mit | Parancs | Eredmény | Bizonyíték |
|---|---|---|---|---|
| 1 | Backend tesztek, SQLite | `cd backend && .venv/bin/python -m pytest tests -v -p no:warnings` | **53 passed** | `evidence/pytest-sqlite.log` |
| 2 | Backend tesztek, **PostgreSQL 16** | `TEST_DATABASE_URL=postgresql+psycopg://hype@127.0.0.1:5432/hype_os_test .venv/bin/python -m pytest tests -v -p no:warnings` | **53 passed** | `evidence/pytest-postgres.log` |
| 3 | Migráció up/down/up + `alembic check` (PostgreSQL 16) | `alembic upgrade head && alembic downgrade -1 && alembic upgrade head && alembic check` | OK, BIGINT, 8 GiB beszúrás OK | `evidence/migration-postgres.log` |
| 4 | Gyökérok-bizonyíték (INTEGER túlcsordulás vs. SUM bigint) | psql, lásd log | 8 GiB: `integer out of range`; SUM: bigint OK | `evidence/rootcause-size-bytes-overflow.log` |
| 5 | Ruff (új/módosított fájlok) | `.venv/bin/ruff check app/services app/worker.py app/api/routes/gallery_exports.py app/models/gallery_export.py app/models/types.py app/schemas/gallery_export.py app/api/crud_router.py app/core/config.py tests --ignore B008` | All checks passed | - |
| 6 | Frontend lint + typecheck + build | `cd frontend && npm ci && npm run lint && npx tsc --noEmit && npm run build` | OK, `/projektek/[projectId]/galeria` dinamikus route | - |
| 7 | **UI végponttól-végpontig** (Playwright/Chromium + uvicorn + `next start`) | `cd backend && .venv/bin/python scripts/ui_e2e_gallery_export.py` | 18/18 OK: login, terv, Várakozó, dupla kattintás -> 1 job, újranyitás, Készülő 40 %, Kész 100 %, letöltés sha256 egyezik, kibontás, Hibás, Lejárt | `evidence/ui-e2e.log`, `evidence/ui/*.png` |
| 8 | **5 GB valódi ZIP64 mérés** (1 db 4,5 GB fájl + 39 kisebb) | `cd backend && .venv/bin/python scripts/bench_gallery_export.py --total-bytes 5000000000 --file-count 40 --big-file-bytes 4500000000 --label 5gb-zip64` | **SIKERES** - lásd alább | `evidence/bench-5gb-zip64.md/.json/.console.log` |
| 9 | **50 GB mérés** | `cd backend && .venv/bin/python scripts/bench_gallery_export.py --total-bytes 50000000000 --file-count 500 --big-file-bytes 4500000000 --label 50gb` | **NEM TESZTELT** - lásd alább | `evidence/bench-50gb.md/.json/.console.log` |

A tesztkészlet lefedi (pytest): kis csomag e2e + kibontás + minden fájl hash;
veszélyes/ismétlődő/Unicode nevek; dupla kattintás; oldal újranyitása; forrás
változása -> új export; jogosulatlan (401); idegen bérlő (404 létrehozásnál,
lekérdezésnél, listánál, link kiadásánál és **hamisított jeggyel** is); bérlő
nélküli ügyfél; manipulált/lejárt jegy; visszavont felhasználó; worker hiba ->
retry -> siker; max. próbálkozás -> failed; stale job visszaküldése / stale
timeout; hiányzó forrás; forrás rövidülése csomagolás közben; galéria bővülése
csomagolás közben (végső ujjlenyomat); TTL-takarítás csak a csomagot törli;
párhuzamos elvételnél egy nyer; darabméret-korlát (memória); Range 206/416/
If-Range/több tartomány; lejárt link -> 410 -> megújítás -> Range-folytatás ->
végső sha256; >65535 bejegyzés ZIP64-számláló; `unzip -t` és Python `zipfile`
független olvasók; determinisztikus kimenet.

### 5 GB mérés eredménye (valódi bájtok, `evidence/bench-5gb-zip64.md`)

| Mérőszám | Érték |
|---|---|
| Forrás | **5 000 000 000 bájt**, 40 fájl (1 × 4 500 000 000 + 39 × ~12,8 MB), `os.urandom`, lefoglalt blokk 5 000 163 328 bájt (nem sparse) |
| Csomag | **5 000 006 906 bájt**, pontosan a tervezett méret; sha256 `7f6b9254…f242fcf` |
| Export idő | **29,99 s** (166,7 MB/s), külön worker-processz |
| **Worker csúcsmemória (RSS high-water)** | **108 412 928 bájt (108,4 MB)** |
| Letöltés | megszakítva 1 500 002 071 bájtnál, link megújítva (ETag változatlan), `Range`+`If-Range` -> 206, **5 000 006 906 / 5 000 006 906 bájt**, 4,88 s; letöltött folyam sha256 == `archive_sha256` |
| API csúcsmemória letöltés alatt | 132,7 MB |
| ZIP64 | ZIP64 EOCD + locator jelen, klasszikus EOCD CD-offszet telített (0xFFFFFFFF), 1 bejegyzés > 4 GiB, 39 bejegyzés offszete > 4 GiB, zip64 extra mindenhol, ahol a spec kéri |
| Integritás | `unzip -t` rc=0; **40/40 bejegyzés kicsomagolt sha256 == forrás sha256** |
| Teljes futás | 105,9 s |

### 50 GB mérés: NEM TESZTELT

* **Akadály:** a környezetben 29,93 GB szabad lemezhely van; a harness
  előellenőrzése 101 GB-ot kér (50 GB forrás + 50 GB csomag + 1 GB sáv), ezért
  a futás a bemenet generálása előtt, `NEM TESZTELT` eredménnyel leállt
  (exit 3). Külső (R2) tárhelyes teszt hitelesítő adat hiányában és a "fizetős
  erőforrást ne hozz létre" kikötés miatt szintén **nem futott**.
* **A fenti 5 GB-os futás nem 50 GB-os bizonyíték.** Azt bizonyítja, hogy a
  ZIP64-útvonal (4 GiB feletti méret és offszet, ZIP64 EOCD) és a
  memória-korlátos streamelés helyes; a memóriahasználat a méret függvényében
  nem nő (a csúcs-RSS 200 MB-nál és 5 GB-nál is ~110 MB).
* **Futtatási parancs elegendő (≥ 101 GB) szabad hellyel:**

  ```bash
  cd backend && .venv/bin/python scripts/bench_gallery_export.py \
      --total-bytes 50000000000 --file-count 500 --big-file-bytes 4500000000 \
      --work-dir /mnt/bench --report-dir ../docs/gallery-export-evidence --label 50gb
  ```

  Várható idő a mért sebességekből: ~7 perc generálás (~128 MB/s), ~5 perc export
  (~167 MB/s), ~1 perc letöltés, ~5 perc hash-ellenőrzés; a jegyzőkönyv
  `docs/gallery-export-evidence/bench-50gb.md` néven íródik felül.
* **R2/S3 backend valódi bucket ellen:** `STORAGE_BACKEND=s3` + R2 kulcsok
  beállítása után ugyanez a pytest készlet és a harness az `S3ObjectStorage`
  osztályt használja; ez a repóban **NEM TESZTELT** (nincs hitelesítő adat, és
  nem hozok létre fizetős erőforrást). A boto3 hívások (`create_multipart_upload`
  / `upload_part` / `complete` / `abort`, `generate_presigned_url` a
  `ResponseContentDisposition` paraméterrel) a standard S3 API-t követik.

## 8. Mi működik már, és mihez kell infrastruktúra/hozzáférés

**Működik (ebben a repóban, lokálisan bizonyítva):** teljes háttérfeladatos
ZIP64 export, valós haladás, öt UI-állapot, idempotens létrehozás, retry/stale
kezelés, bérlő-elkülönítés, biztonságos nevek, TTL-takarítás, Range-folytatás
link-megújítással, 5 GB-os valódi ZIP64 csomag, 53 automatizált teszt SQLite-on
és PostgreSQL-en, Playwright UI e2e.

**Infrastruktúra / hozzáférés kell hozzá:**

1. **R2 bucket + kulcsok** (privát bucket, CORS a presigned letöltéshez nem
   szükséges, mert navigációs letöltés) - és utána egy éles-szerű R2-teszt.
2. **Worker service** a hostingon (Railway: külön service, `python -m app.worker`).
3. **≥ 101 GB szabad lemez** a 50 GB-os harnesshez (vagy R2-vel: 50 GB forrás
   helyben + a csomag a bucketben).
4. **Adatfeltöltés**: `employees.client_id` az ügyfél-felhasználóknál;
   `Media.size_bytes` (és lehetőleg `checksum_sha256`) a feltöltési folyamatból -
   addig a `backfill-sizes` parancs pótolja.
5. **Feltöltési útvonal**: ez a PR a letöltést oldja meg; a médiafeltöltés
   (amely a `storage_key`-t és a méretet írja) továbbra is a Fázis 1 storage-munka.

## 9. Ismert korlátok, nyitott döntések

* A központi könyvtár a memóriában épül (fájlonként ~100-200 bájt); 200 000 fájl
  felett (`EXPORT_MAX_FILES`) a job elutasítja - ez tudatos védőkorlát.
* A többi CRUD router GET végpontja továbbra is nyilvános (a dashboard UI
  hitelesítés nélkül hívja őket); ezt itt szándékosan nem változtattam meg, csak a
  galéria-doménhez tartozókat (media, folders, portal, payments) zártam le.
* A `ready` exportot a galéria változása **nem** törli azonnal (TTL-ig letölthető
  marad); ha ez üzletileg nem kívánatos, a `current_job_for_project` helyén egy
  "régi verziók lejáratása" lépés beilleszthető.
* Windows Explorer beépített ZIP-kezelője nagy ZIP64 archívumoknál nem megbízható
  - 7-Zip / WinRAR / macOS Archive Utility / `unzip` javasolt; a data descriptoros
  módot mind kezeli (Python `zipfile` és Info-ZIP `unzip` ellenőrizve).
