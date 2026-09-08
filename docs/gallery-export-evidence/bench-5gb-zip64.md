# Galéria-export mérési jegyzőkönyv - `5gb-zip64`

- Időpont (UTC): 2026-09-08T08:30:54+00:00
- **Eredmény: SIKERES**
- Cél összméret: **5,000,000,000 bájt** (5.00 GB), fájlok: 40, legnagyobb fájl: 4,500,000,000 bájt
- Parancs: `bench_gallery_export.py --total-bytes 5000000000 --file-count 40 --big-file-bytes 4500000000 --label 5gb-zip64 --report-dir ../docs/gallery-export-evidence`

## Környezet és előellenőrzés
- Szabad lemezhely: 30,733,258,752 bájt (30.73 GB); szükséges: 11,000,000,000 bájt (11.00 GB)
- Memória: 16.86 GB összes, CPU: 4, Python 3.11.15, kernel 6.18.44-fc-v24

## Bemenet (valódi bájtok, nem sparse)
- Kiírt forrásbájt: **5,000,000,000** (5.00 GB), lefoglalt blokk: 5,000,163,328 bájt, idő: 39.111 s (127.84 MB/s)

## Export (külön worker-processz)
- Állapot: **ready**, fájlok: 40, csomag: **5,000,006,906 bájt** (5.00 GB), várt: 5,000,006,906 bájt (egyezik: True)
- Idő: **29.987 s** (166.74 MB/s)
- **Worker csúcsmemória (RSS high-water): 108,412,928 bájt (108.41 MB)**
- sha256: `7f6b9254e5af17eb0d3d0a3ecce60c22d29465c0d49079c5f1606a254f242fcf`

## Letöltés (valódi HTTP, Range-folytatás)
- Megszakítva 1,500,002,071 bájtnál, link megújítva (ETag változatlan: True), folytatva `Range`+`If-Range` fejléccel (206)
- Fogadott bájt: **5,000,006,906** / Content-Length 5,000,006,906, idő: 4.881 s (1.02 GB/s)
- Letöltött folyam sha256 == szerver archive_sha256: **True**
- API-processz csúcsmemória a letöltés alatt: 132,706,304 bájt (132.71 MB)
- Content-Disposition: `attachment; filename="BENCH-5GB-ZIP64-Bench-5gb-zip64-fea93ee0.zip"; filename*=UTF-8''BENCH-5GB-ZIP64-Bench-5gb-zip64-fea93ee0.zip`

## ZIP64 és integritás
- ZIP64 EOCD rekord: True, locator: True, ZIP64 EOCD bejegyzésszám: 40, CD offszet: 5000003720
- Klasszikus EOCD CD-offszet telített (0xFFFFFFFF): True
- >4 GiB bejegyzés: 1, >4 GiB offszetű bejegyzés: 39, zip64 extra ott, ahol kell: True
- Minden bejegyzés STORE: True
- `unzip -t` visszatérési kód: 0 (`No errors detected in compressed data of /home/user/HYPE-OS/backend/var/bench/5gb-zip64/storage/exports/1/fea93ee0565a98ddbb697d1313b034225eec8ae00ec7bd424bebe4e2462af4a3.zip.`)
- **Kicsomagolt bejegyzések sha256 == forrás sha256: 40/40** (eltérés: 0), idő: 29.731 s

Teljes futásidő: 105.902 s
