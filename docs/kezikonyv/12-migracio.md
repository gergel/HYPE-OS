# 12 - Migráció a régi rendszerből

A régi rendszerből **három, egymástól független dolgot** kell áthozni, és
mindhez más eszköz való. A leggyakoribb hiba az, hogy valaki mindet a gitre
bízza.

| Mit | Mivel | Hova |
|---|---|---|
| Kód, logika | git | ez a repó |
| Adat (projektek, emberek, papírok) | Notion-import (`app/notion_import/`) | Postgres |
| Média (kép, videó, PDF) | tárhely-másolás (rclone / S3 API) | R2 bucket |

## Miért nem mennek a videók a gitbe

Nem stílus kérdése:

- A git **minden verziót örökre megőriz**. Egy 2 GB-nyi videó akkor is a
  history-ban marad, ha holnap törlöd - csak history-átírással lehet kiszedni,
  ami mindenki klónját érvényteleníti.
- A GitHubon **100 MB a kemény fájlméret-korlát**, és 1 GB alatt ajánlott
  tartani az egész repót.
- Utána minden klón és minden CI-futás letölti az egészet.

A rendszer eleve nem is így működik: a média R2-n van, a DB pedig csak a
**kulcsot** tárolja (`PortalVideo.source_key`, `PortalImage.key`). Ebből
következik egy hasznos dolog is - lásd lentebb: **a kulcsnak nem kötelező
követnie semmilyen konvenciót**, mert explicit oszlopban áll.

## A média átemelése (S3/R2 → R2)

A bájtok mozgatása a hosszú lépés, ezért ezt külön, előre, `rclone`-nal érdemes
csinálni - **szerveren futtatva, nem laptopról**. R2-nél nincs egress díj, tehát
a másolás sávszélessége nem kerül pénzbe; ami számít, az az idő.

Kétfázisú, mert így a nagy adatmozgás egyszer fut le, utána már csak olcsó,
bucketen belüli másolások vannak:

**1. fázis - tömeges átmásolás egy átmeneti (staging) előtag alá.**

```bash
# rclone remote-ok (mindkettő: type=s3, provider=Cloudflare, region=auto,
# endpoint=https://<account-id>.r2.cloudflarestorage.com)
rclone copy regi:regi-bucket uj:hype-os-storage/media-portal/legacy/ \
  --progress --transfers 16 --checkers 32 --retries 5
```

Újrafuttatható: az `rclone copy` a már meglévő, azonos méretű objektumokat
kihagyja, tehát egy megszakadt átvitel egyszerűen folytatható.

**2. fázis - ellenőrzés.**

```bash
rclone check regi:regi-bucket uj:hype-os-storage/media-portal/legacy/ --size-only
rclone size regi:regi-bucket
rclone size uj:hype-os-storage/media-portal/legacy/
```

A darabszámnak és az összméretnek egyeznie kell. Ez a lépés nem opcionális: egy
hiányzó videóra jellemzően csak hetekkel később, egy ügyfél jelzéséből derül fény.

**3. fázis - a DB-sorok átemelése**, és közben a fájlok végleges helyükre
mozgatása bucketen belüli másolással (`CopyObject`) - ez nem tölti át újra az
adatot, csak a szerveren belül másol.

Miért érdemes a végleges kulcs-konvencióra átmozgatni: a takarító végpont
(`POST /portal-admin/maintenance/{portal_id}/purge-files`) a
`videos/{id}` és `images/{id}` előtagot törli. Ha a legacy fájlok más előtag
alatt maradnának, a portál törlése után **árván maradnának** az R2-n, és
fizetnénk a tárolásukat.

Ha a régi rendszerben már van **HLS** változat, azt is hozd át: akkor nincs
újrakódolás, csak az `hls_url`-t kell beállítani. Ha csak az eredeti MP4 jön át,
a HLS-t és a thumbnailt a worker újragenerálja (`status="processing"` →
`workers/portal_tasks.process_video_task`) - sok videónál ez órákat jelent.

## A régi adatbázis felderítése

A HYPE OS portál-modellje a régi projekt portja, de a séma ettől még eltérhet.
Mielőtt bármit átemelnél, nézd meg, mi van ott - **csak olvasó** szkript:

```bash
LEGACY_DATABASE_URL=postgresql+psycopg://user:pass@host:5432/db \
    python scripts/legacy_portal_inspect.py
```

Kiírja a táblákat, oszlopokat, sorszámokat, és a fájlra mutató oszlopokból
(`key`, `url`, `path`, `file`, `src`, `thumb`, `cover`, `hls`, `mp4`) néhány valódi
mintaértéket. Ez utóbbi a lényeg: ebből derül ki, milyen kulcs-formátumban vannak
a fájlok a régi bucketben. A kimenet megosztható, jelszót nem ír ki; ha a
fájlnevek is érzékenyek, `--samples 0`.

### Amit a célséma vár

| Régi fogalom | Új tábla | Kulcs-oszlop |
|---|---|---|
| portál/projekt | `portals` | `slug` (egyedi), `notion_page_id` |
| mappa | `portal_folders` | `portal_id`, `sort_order` |
| videó | `portal_videos` | `source_key`, `mp4_url`, `hls_url`, `thumbnail_url` |
| kép | `portal_images` | `key`, `url`, `thumbnail_url` |

Egy eltérés, amire figyelni kell: a HYPE OS-ben **egy portál mindig egy meglévő
Projecthez van kötve** (1:1), a cím/ügyfélnév/dátum a Project mezőire esik vissza,
és csak felülírásként tárolódik (`title_override`, `client_name_override`,
`project_date_override`). A régi rendszerben ezek szabadon kitöltött mezők
voltak. Tehát az átemelésnek **projektet kell párosítania** minden portálhoz -
vagy `project_id`-vel, vagy `deliverable_id`-vel, vagy (ha nincs párja) az
override mezőkbe kell tenni az adatot.

## Sorrend és cutover

1. Séma: `alembic upgrade head`.
2. Törzsadat: Notion-import a katalógus sorrendjében (körökben, egymásra épülve),
   a böngészőből indítva - `/api/v1/admin/notion-import`. **Ne `railway ssh`-ból**:
   az a kapcsolat a több órás importok alatt rendszeresen elszáll (lásd
   [10-integraciok.md](10-integraciok.md)).
3. Média: a fenti rclone-fázisok.
4. Portál-sorok átemelése + kulcsok beállítása.
5. Ellenőrzés (lásd lent).
6. A régi rendszer **írásra tiltása** (read-only), hogy ne keletkezzen új adat,
   amit már senki nem hoz át.
7. Élesítés, majd a régi rendszer kikapcsolása - de a **régi bucketet és a régi
   DB-dumpot még hetekig tartsd meg**. Ez a visszaút, ha valami hiányzik.

Az importok idempotensek: a Notion-fájlok átemelése a forrás-URL útvonalára
(aláírás nélkül) azonosít, tehát egy újrafuttatás nem tölti le és nem duplikálja
ugyanazt (`app/notion_import/files.py`). Erre a migrációs szkriptekben is
támaszkodni kell - egy migráció, amit nem lehet kétszer lefuttatni, használhatatlan.

## Ellenőrzés élesítés előtt

- **Darabszám**: portál / videó / kép soronként a régi és az új DB-ben.
- **Méret**: `rclone size` a két oldalon.
- **Mintavétel**: 10-15 véletlen portált nyiss meg valóban - játszd le a videót,
  nyisd meg a képet, próbáld a letöltést. Az aláírt letöltő URL-ek külön úton
  mennek, mint a lejátszás, ezért mindkettőt nézd meg.
- **Lejáró portálok**: az `expires_at` átjött-e, és a lejárt portálok tényleg a
  lejárati képernyőt adják-e ([09-media-portal.md](09-media-portal.md)).
- **Jelszavas portálok**: a régi jelszó-hash formátuma egyezik-e. Ha nem, a
  jelszót újra kell adni - ez nem hiba, de az ügyfeleket értesíteni kell róla.

A konkrét, elvégzendő lépések listája (hozzáférések, parancsok, ellenőrzés):
[13-domain-es-atallas.md](13-domain-es-atallas.md).

## Amit ne csinálj

- **Ne töltsd le a médiát laptopra, és ne töltsd fel újra a felületen.** Sok
  videónál napokba telik, és garantáltan lesz belőle félbemaradt feltöltés meg
  duplikátum.
- **Ne commitold be a médiát**, még "ideiglenesen" sem.
- **Ne írj olyan migrációs szkriptet, ami csak egyszer futtatható.** Mindig
  legyen `--dry-run`, és mindig ismerje fel a már átemelt sorokat.
- **Ne kapcsold ki a régi rendszert az ellenőrzés előtt.**
