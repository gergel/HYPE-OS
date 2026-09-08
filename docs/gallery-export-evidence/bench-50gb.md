# Galéria-export mérési jegyzőkönyv - `50gb`

- Időpont (UTC): 2026-09-08T08:31:01+00:00
- **Eredmény: NEM TESZTELT**
- Cél összméret: **50,000,000,000 bájt** (50.00 GB), fájlok: 500, legnagyobb fájl: 4,500,000,000 bájt
- Parancs: `bench_gallery_export.py --total-bytes 50000000000 --file-count 500 --big-file-bytes 4500000000 --label 50gb --report-dir ../docs/gallery-export-evidence`

## Környezet és előellenőrzés
- Szabad lemezhely: 29,927,714,816 bájt (29.93 GB); szükséges: 101,000,000,000 bájt (101.00 GB)
- Memória: 16.86 GB összes, CPU: 4, Python 3.11.15, kernel 6.18.44-fc-v24

## Akadály

Nincs elég szabad lemezhely: 29927714816 bájt szabad, 101000000000 bájt szükséges (29.93 GB < 101.00 GB).

Ez a futás **NEM TESZTELT**: a fenti parancs elegendő lemezhellyel újrafuttatható.
