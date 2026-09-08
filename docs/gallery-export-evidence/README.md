# Galéria-export bizonyítékok

Minden fájl a `claude/gallery-download-zip64-fxvjy5` branchen, ebben a környezetben
ténylegesen lefuttatott parancs kimenete (titkok nélkül; a tesztkulcsok
`*-not-for-production` szövegűek).

| Fájl | Tartalom |
|---|---|
| `rootcause-size-bytes-overflow.log` | PostgreSQL 16: `media_items.size_bytes` INTEGER túlcsordulás egyedi >2 GiB fájlnál; `SUM(integer)` bigint ellenpróba |
| `migration-postgres.log` | Alembic `upgrade -> downgrade -> upgrade` + `alembic check` valódi PostgreSQL 16-on, 8 GiB beszúrás a javított sémába |
| `pytest-sqlite.log` | 53 backend teszt, SQLite |
| `pytest-postgres.log` | ugyanaz a 53 teszt, PostgreSQL 16 |
| `ui-e2e.log` + `ui/*.png` | Playwright/Chromium UI végponttól-végpontig teszt (18 ellenőrzés, 8 képernyőkép) |
| `bench-5gb-zip64.md/.json/.console.log` | **5 000 000 000 bájt** valódi ZIP64 export + Range-folytatásos letöltés + 40/40 hash (SIKERES) |
| `bench-50gb.md/.json/.console.log` | **50 000 000 000 bájt** harness: **NEM TESZTELT** (29,93 GB szabad hely < 101 GB szükséges), a futtatási parancs a jegyzőkönyvben |
