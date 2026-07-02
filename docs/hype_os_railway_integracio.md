# HYPE OS – Railway/GitHub háttérrendszerek integrációja

*Mind a 17 repó feltöltve és átnézve.*

---

## 1. A legfontosabb felismerés

A 17 repó **6 jól elkülönülő kategóriába** esik. Ez alapjaiban megerősíti (és pontosítja) az eddigi Notion-elemzést: **a Railway-oldal ugyanazt a duplikációs mintát hordozza, mint a Notion-oldal** – csak itt "klónozott kódbázis", ott "klónozott adatbázis" formában. Ugyanakkor a két utoljára feltöltött repó (**Hype-repo**, **inventory-audit-system**) jelentősen árnyalja a képet: a **Hype-repo egy komplett, production-grade Portal rendszer**, ami már jóval túlmutat azon, amit a projektindító doksi Migration fejezete elképzelt "első lépésként".

| Kategória | Repók száma | Mi ez valójában |
|---|---|---|
| A) Stateless Notion↔Notion relation-sync workerek | 6 | "Szegény ember JOIN-ja" – mivel a Notion natív relation mezői nem tudnak automatikusan párosítani, ezek a szkriptek 5 percenként lefutva, **név vagy kód alapján String-matchelve** kötik össze a táblákat |
| B) XP/gamifikáció motor | 1 | A Vágók tábla összes XP/Level/pontszám mezőjét ez táplálja |
| C) Dokumentum-generáló & küldő klónok | 7 | Ugyanaz a "Notion → sablon → PDF → Drive → Gmail → Notion vissza" pipeline, 7-szer lemásolva, csak más Notion DB-re és más szövegre |
| D) Valódi, stateful háttérrendszerek (Notion-adatra épülő workerek) | 2 | **HYPE_Technika** és **diszpo-kuldes** – saját Railway Postgres-szel dolgoznak, de a Notion még mindig a "forrás igazság" |
| E) Teljes, önálló full-stack alkalmazás | 1 | **Hype-repo** – ez már **nem Notion-kiegészítő**, hanem egy önálló, Notiontól majdnem független termék: ügyfélportál videó-streaminggel, fizetéssel, saját adatbázissal |
| F) Egyszeri célú admin endpoint | 1 | **inventory-audit-system** – leltárellenőrzés indítása egy API-hívással |

---

## 2. A) Stateless relation-sync workerek – "szegény ember JOIN-ja"

Mind a 6 repó **ugyanazt a mintát** követi: `while True: lekérdez → nevet/kódot normalizál → matchel → PATCH-eli a relation mezőt → alszik 60-300 mp-et`.

| Repó | Forrás DB | Cél DB | Matching alapja | Frissített mező |
|---|---|---|---|---|
| **ADMIN_projektkod** | HYPE ADMIN projektkódok | Main Database | `PROJEKTKÓD` (teljes egyezés) | `Forgatások` relation |
| **ADMIN_utomunka** | HYPE ADMIN projektkódok | Utómunka | `PROJEKTKÓD` (**csak az első 11 karakter!**) | `Utómunka` relation |
| **oraber-timesheet-private** | Timesheet Public | Timesheet Private | Name → "Full Name" | `Vágó` relation |
| **oraber_vagas_private** | Timesheet Private | Külsős és belsős (Employee) | Name → "Full Name" | `Vágó` relation |
| **timesheet-public-vago** | Timesheet Public | Külsős és belsős (Employee) | Name → "Full Name" | `Vágó` relation |
| **time_xp** (main.py) | egy Timer/Timesheet DB | Vágók | `Person` (people mező) neve | `Vágók` relation |

**Kockázat, amit érdemes tudni:** a névalapú matchelés (`normalize_main_name`: "Diána Dombi" → "Dombi Dia" kézzel bekódolt kivétel, "Steiner Imre Manó" ugyanígy) **rendkívül törékeny** – minden névütközés, elgépelés vagy becenév-eltérés miatt kézzel bekódolt speciális eset kerül a szkriptbe. Ez pontosan az a probléma, amit egy valódi relációs adatbázis (PostgreSQL, `employee_id` foreign key) egy csapásra megszüntet – nem kell név-normalizáló Python kód, mert a kapcsolat sosem szakad el.

**HYPE OS-ben:** ez a 6 repó **megszűnik**. A `TIMESHEET`, `EMPLOYEE`, `PROJECT_CODE`, `PROJECT`, `DELIVERABLE` entitások között valódi foreign key-ek lesznek – nincs szükség külön szinkron-workerre, mert nem lehet szétcsúszni.

---

## 3. B) XP/gamifikáció motor (`time_xp/pont_adder.py`)

Ez magyarázza a Vágók táblában talált ~17 formula mezőt (Level, XP, Leggyorsabb vágó, stb.):

- Figyeli a Main Database-t: `jóváírva = False` ÉS `jóváírandó pont` nem üres ÉS `Aki ellenőrzésbe tette 1` ki van töltve.
- Ha talál ilyet, a hozzá tartozó vágó `projekt pont` mezőjéhez **hozzáadja** a pontot, majd `jóváírva = True`-ra állítja (hogy ne írja jóvá kétszer).
- 60 másodpercenként fut.

**HYPE OS-ben:** ez egy **jó minta**, amit érdemes megtartani (a csapat élvezi a gamifikációt) – de a `DELIVERABLE` → `Timesheet` → `EmployeePerformance` eseményláncba kell beépíteni, event-driven módon (`DeliverableApproved` esemény → pontszámítás), nem polling-gal.

---

## 4. C) Dokumentum-generáló & küldő klónok (7 repó)

Ez a **legnagyobb kódduplikáció** a Railway-oldalon. Mind a 7 repó ugyanazt a 4 fájlt tartalmazza (`main.py`, `notion.py`, `gdocs.py`, `gmail.py`), szinte karakterre ugyanazzal a logikával:

```
Notion DB lekérdezése (státusz + "Kiküldés" checkbox szerint szűrve)
  → Google Docs sablonból PDF generálás
  → PDF feltöltés Google Drive-ra
  → Email küldés Gmail API-n
  → Notion vissza: TIG/szerződés link + új státusz
  → 5 percenként loop
```

| Repó | Melyik Notion DB-n dolgozik | Dokumentum típusa | Státusz-váltás |
|---|---|---|---|
| **TIG-alvalalkozo** | Külsős (alvállalkozó) | TIG (teljesítésigazolás) | "Készíthető a TIG" → "Kész feltöltve" |
| **belsos-TIG** | Belsős | TIG (belsős) | "Nincs elkezdve" → "Kész feltöltve" |
| **TIG-megrendel-email** | HYPE ADMIN projektkódok | TIG a megrendelő felé | "Nincs elkezdve" → "Elkészült és kiküldve" |
| **kulsos-eseti-szerzodes** | Külsős | eseti (egyszeri) megbízási szerződés | "Nincs elkezdve" → "Elkészült és kiküldve" |
| **alvallalkozo-keret** | Alvállakozó keretszerződés | alvállalkozói keretszerződés | "Nincs feltöltve" → "Kiküldve/aláírásra vár" |
| **megregdelo-eseti** | HYPE ADMIN projektkódok (beágyazott "Szerződés*" mezők) | megrendelői eseti szerződés | "Nincs elkezdve" → "Kiküldve" |
| **megregdelo-keretszerzodes** | Keretszerződés | megrendelői keretszerződés | "Nincs elkezdve" → "Kiküldve" |

**Fontos technikai megfigyelés:** a `megregdelo-eseti` nem egy önálló "eseti szerződés" DB-n dolgozik, hanem a **HYPE ADMIN projektkódok**-ba beágyazott `Szerződés tárgya`, `Szerződés nettó összeg`, `Szerződés projekt név` stb. mezőkön – vagyis a Project Code rekord *saját magában* hordozza az eseti szerződés adatait, míg a keretszerződéshez külön DB (és külön repó) tartozik. Ez pontosan tükrözi a korábbi felismerést: a **CONTRACT entitásnak két altípusa van** (keret vs. eseti), és a HYPE OS-ben ezt egy `tipus` mezővel kell megkülönböztetni, nem 7 külön kódbázissal.

**HYPE OS-ben:** ez a 7 repó **egyetlen Automation/Document szolgáltatássá** olvad össze:

```
generate_document(entity_type, entity_id, document_kind)
  → sablon kiválasztása (document_kind alapján: TIG / eseti szerződés / keretszerződés)
  → PDF generálás
  → Storage feltöltés (a doksi Storage Provider rétege, nem közvetlen Drive-hívás)
  → Email (Notification modul)
  → Contract/Expense/Employee entitás frissítése
```

Ez pontosan a projektindító doksi **"Contracts" modulja** és **Event Driven működés** fejezete: `ProjectStatusChanged → Event Bus → Generate PDF → Upload Storage → Email → ... → Timeline`. A 7 klón helyett egy paraméterezett szolgáltatás kell, `document_kind` enum-mal (7 érték: tig_alvallalkozo, tig_belsos, tig_megrendelo, szerzodes_kulsos_eseti, szerzodes_alvallalkozo_keret, szerzodes_megrendelo_eseti, szerzodes_megrendelo_keret).

---

## 5. D) A két valódi, stateful háttérrendszer

Ez a két repó **jelentősen kifinomultabb**, mint a többi 13 – ezek már a HYPE OS-hez hasonló architektúrát követnek: FastAPI + saját Railway PostgreSQL + Notion csak mint adatforrás/céltábla, nem mint "adatbázis".

### 5.1 HYPE_Technika – Equipment foglaltság-figyelő és ütközés-detektáló motor

Fájlok: `main.py` (FastAPI), `worker.py` (a tényleges logika, ~530 sor), `models.py` (SQLAlchemy), `logic.py`, `notion_client.py`, `settings.py`.

Mit csinál:
1. **Preload**: induláskor a teljes Leltár DB-t betölti egy saját `inventory_cache` táblába (Postgres).
2. Figyeli a forgatásokat (Main Database, "kész" checkbox → feldolgozásra vár).
3. Minden forgatáshoz kiszámolja a **napi lebontású foglaltsági naptárat** (`BookingDay` tábla) – külön logikával kezelve az **egyedi eszközöket** ("asset", pl. 1 db konkrét kamera) és a **készlet-jellegű eszközöket** ("stock", pl. memóriakártya, aminek van darabszáma).
4. **Ütközés-detektálás**: ha egy eszközt két átfedő forgatáshoz is hozzárendeltek, hibát jelez, és **automatikusan alternatívát keres** (pl. optikánál azonos zoom-tartományú, szabad, "Használható" állapotú másik lencsét ajánl).
5. Visszaírja a Notionba a kategóriánként csoportosított technika-listát (formázott rich text).
6. `Stock igények` DB-t is olvassa (`NOTION_STOCK_REQUESTS_DB_ID`) az aggregált készlet-igényekhez.

**✅ Tisztázva:** a "Stock igények" tábla **nem redundáns, hanem a stock-jellegű (nem egyedi, darabszám-alapú) eszközök kezelésének kulcsa** – pl. 5 db egyforma 30m HDMI kábelből mennyi megy ki egy adott projekthez. Ez a HYPE_Technika `track_mode: "asset" | "stock"` megkülönböztetésének Notion-oldali adatforrása. **A tábla marad, nem törlődik** – a Migration Map frissítve.

**HYPE OS-ben:** ez a repó gyakorlatilag **a jövőbeli Equipment modul kész magja** – az ütközés-detektálás és az alternatíva-ajánlás pontosan az `ASSIGNMENT`/`EQUIPMENT` entitások közötti logika, amit a doksi "Equipment Assignment" életciklus-lépése elvár. Érdemes ezt **nem eldobni, hanem áttelepíteni** natív PostgreSQL táblákra (a `inventory_cache` és `BookingDay` modellek gyakorlatilag már a végleges `EQUIPMENT` és `ASSIGNMENT` táblák korai verziói).

### 5.2 diszpo-kuldes – Diszpó email/PDF automatizáció

Fájlok: `main.py` (FastAPI, 388 sor), `notion.py` (416 sor), `email_gmail.py` (328 sor), `gdoc_template.py`, `pdf.py`, `drive.py`, `db.py`.

Mit csinál:
1. Saját Postgres `dispatches` táblában követi a folyamat állapotát (`PREPARED → PRE_SENT → FULL_READY → FULL_REPLY → FULL_SENT`), Gmail thread ID-vel együtt.
2. Két fokozatot kezel: **előzetes diszpó** (early heads-up) és **teljes diszpó** – a teljes diszpó **ugyanabba az email-szálba válaszol**, mint az előzetes (`Gmail Thread ID` alapján).
3. "Gating" logika, hogy ne küldjön duplán: `Diszpó tesztelés` checkbox + `Diszpó != "Kiküldve"` feltétel.
4. Címzettek: `Résztvevők email` relation → ez pontosan az a mező, amit a memóriában is rögzítettünk korábban (a második Notion DB, ami a "Résztvevők email" formula mezőt táplálja) – **ez a repó a fogyasztója annak a résztvevő-email pipeline-nak**.
5. HTML sablonokból (`pre_dispo_email.html`, `full_dispo_email.html`, `dispo_pdf.html`) generál PDF-et és emailt.

**HYPE OS-ben:** ez pontosan a doksi **"Diszpó" fejezete** ("A Diszpó nem PDF. A Diszpó adat. A PDF csak export.") – csak itt a "strukturált objektum" state-je egy Postgres táblában van, nem a Notion oldalon. Ez a `CALLSHEET` entitás gyakorlatilag production-ready implementációja, csak a Notion-specifikus részeket kell PostgreSQL натив kapcsolatokra cserélni.

---

## 6. E) Hype-repo – teljes ügyfélportál rendszer (a legérettebb darab)

Ez **nem egy Notion-kiegészítő script**, hanem egy önálló, production-grade **full-stack alkalmazás**:

```
Next.js frontend (portál + admin)  ──/api──▶  FastAPI backend  ──enqueue──▶  Celery worker (FFmpeg)
                                                    │                              │
                                                Postgres                   Cloudflare R2 (video/kép storage)
                                                (projects/videos/          (HLS playlist + MP4 + thumbnail)
                                                 folders/images)
```

**Mit tud:**
- **Ügyfélportál** (`/p/{slug}`): jelszóval védett vagy share-token alapú, cinematic dark-theme oldal, ahol a kliens HLS-streamben nézheti meg a videóit (nem kell Google Drive-ot linkelgetni!) és MP4-et tölthet le.
- **Admin felület** (`/admin`): projekt CRUD, videó feltöltés (multipart, nagy fájlokhoz), automatikus thumbnail + HLS generálás FFmpeg-gel, drag-and-drop sorrendezés, mappák (Folder), képek (Image), jelszó kezelés, share-link generálás/regenerálás.
- **Fizetés (Barion)**: egy projekt lehet `payment_mode = "contact"` (csak kapcsolatfelvétel) vagy `"paid"` (Barion fizetési kapu, HUF, azonnali fizetés) – tehát bizonyos videó-anyagok **közvetlenül a portálon értékesíthetők**, fizetési visszaigazolással (`/barion/callback`).
- **Notion sync**: `notion_sync()` endpoint, ami Notionból projekteket húz be – de **fontos eltérés**, lásd lent.
- **Brand-váltás**: `Project.brand = "hype" | "contentbee"` – tehát ez a rendszer **két márkát (HYPE és ContentBee) egyszerre kezel**, ami eddig nem szerepelt sem a Notion-térképben, sem a projektindító doksiban.

**Adatmodell (`Project`, `Video`, `Folder`, `Image`) szinte 1:1 megegyezik a projektindító doksi "Videók" fejezetével** ("Az adatbázisban kizárólag: storage_key, thumbnail, duration, codec, resolution, size, created_at...") – ez a rész a doksiban **le van írva elméletben, itt pedig már kész, működő kódban létezik**. Ezt nem újra kell tervezni a HYPE OS-hez, hanem **át kell venni és bővíteni**.

**⚠️ Nyitott kérdés – Notion mezőnevek nem egyeznek:** a `services/notion.py` a következő Notion mezőket várja: `Project Name`, `Client Name`, `Portal Slug`, `Portal Cover Image`, `Portal Status`, `Portal URL`. **Egyik sem szerepel a korábban feltérképezett 43 Notion adatbázis egyikében sem.** Ez azt jelenti, hogy vagy:
- van egy **negyedik, eddig nem exportált Notion adatbázis** kifejezetten a Portalhoz (legvalószínűbb), vagy
- ez a szinkron még soha nem lett élesben bekötve, csak elő van készítve.
Ezt érdemes tisztázni – ha van külön "Portal" Notion adatbázis, azt is be kell vonni a Migration Map-be.

**HYPE OS-ben:** ez a repó gyakorlatilag **a Portal + Media + Storage Object entitások kész implementációja**, és emellett egy teljesen új entitást is behoz, amit eddig nem térképeztünk fel: **Payment** (Barion tranzakciók, `payment_mode`, projekt-szintű ár). Ezt be kell építeni a kapcsolati ábrába: `PROJECT ||--o| PAYMENT`, és a `REVENUE` entitáshoz is kapcsolódnia kell (ha valaki a portálon fizet, az bevétel, aminek meg kell jelennie a Project Code pénzügyi összesítésében).

---

## 7. F) inventory-audit-system – leltárellenőrzés indító

Ez egy **egyetlen endpointos** FastAPI app (`GET /create-audit`):
1. Létrehoz egy új rekordot a **Leltárak** (audit) DB-ben, `"Folyamatban"` állapottal.
2. Lekéri a **Leltár** DB-ből az összes `"Használható"` státuszú eszközt.
3. Minden eszközhöz létrehoz egy sort a **Leltár tételek** DB-ben: `Elvárt db` = a rendszerben nyilvántartott mennyiség, `Talált db` = 0 (ezt tölti majd ki valaki kézzel a fizikai leltározás során), `Státusz` = "Nincs ellenőrizve".

Ez pontosan a **Leltár → Leltárak → Leltár tételek** hármas kapcsolatot valósítja meg, amit már a kapcsolati ábrában is jelöltünk (`EQUIPMENT` batch/csoport szintű leltározása). Ez egy **egyszerű, de élesben használt automatizálás** – nem duplikáció, önálló funkció.

**HYPE OS-ben:** ez a logika egy `POST /equipment/audits` endpointtá alakul a végleges backendben, ugyanezzel a "snapshot minden használható eszközről, várt vs. talált darabszám" mintával – csak natív PostgreSQL-lel, Notion-hívások nélkül.

---

## 8. Frissített összkép – hogyan áll össze a teljes rendszer

```
                    ┌─────────────────────────────────────┐
                    │         NOTION (jelenlegi UI)         │
                    │   43 adatbázis, emberek innen dolgoznak│
                    └───────────────┬───────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                            │                            │
┌───────▼────────┐          ┌────────▼────────┐          ┌────────▼─────────┐
│ A) 6 relation-  │          │ C) 7 dokumentum- │          │ D) 2 stateful     │
│ sync worker     │          │ generáló klón    │          │ háttérrendszer    │
│ (stateless,     │          │ (stateless,      │          │ (saját Postgres)  │
│ név/kód matching)│         │ Drive+Gmail)     │          │                   │
│                 │          │                  │          │ HYPE_Technika     │
│ → megszűnik,    │          │ → 1 db paramé-   │          │ (equipment)       │
│ helyette valódi │          │ terezett Document│          │                   │
│ FK-k            │          │ Service          │          │ diszpo-kuldes     │
│                 │          │                  │          │ (callsheet)       │
│ + B) XP motor   │          │                  │          │ → ezek a "magok"  │
│ (event-driven-re│          │                  │          │ a végleges HYPE   │
│ átalakítva)     │          │                  │          │ OS-hez            │
└─────────────────┘          └──────────────────┘          └───────────────────┘
```

**Kulcskövetkeztetés:** a 17 repóból **13 stateless, "Notion mint adatbázis" korlátait kompenzáló segédszolgáltatás** – ezek a végleges HYPE OS-ben (ahol a Postgres a "single source of truth", nem a Notion) **egyszerűen nem lesznek szükségesek**, mert amit ezek megoldanak (relation-szinkron, dokumentum-generálás típusonként lemásolva), azt egy valódi relációs adatbázis + egy paraméterezett document/automation service natívan tudja. A **HYPE_Technika és diszpo-kuldes** viszont **érdemi üzleti logikát** hordoz, amit át kell menteni. A **Hype-repo pedig nem is "kiegészítő"** – ez már majdnem egy önálló HYPE OS-szelet (Portal + Media + Storage + Payment), amit a végleges rendszerbe be kell olvasztani, nem újraírni.

---

## 9. Nyitott pontok, mielőtt lezárjuk

1. ~~Stock igények tábla~~ → **Tisztázva**: nem törlődik, a HYPE OS-ben az `EQUIPMENT.track_mode = "stock"` logika Notion-oldali forrása marad, amíg át nem áll natív PostgreSQL-re.
2. **Hype-repo Notion-mezői nem egyeznek** – lásd 6. fejezet: `Project Name`, `Client Name`, `Portal Slug`, `Portal Cover Image`, `Portal Status`, `Portal URL` egyike sem szerepel a feltérképezett 43 Notion DB-ben. Van-e egy negyedik, eddig nem exportált "Portal" Notion adatbázis?
3. **Payment/Barion entitás** – ez egy teljesen új, eddig sehol nem szereplő üzleti funkció (közvetlen fizetés a portálon). Be kell építeni a kapcsolati ábrába és tisztázni kell a Bevételek/Project Code viszonyát hozzá.
4. **HYPE + ContentBee két márka** – a Hype-repo `brand` mezője jelzi, hogy legalább két márka fut ugyanazon a rendszeren. Ez eddig nem szerepelt sem a Notion-térképben, sem a projektindító doksiban – tisztázni kell, hogy ez hogyan hat a Client/Project Code modellre (van-e átfedés ügyfelekben, számlázásban, stb.).
5. **credentials.json / tigtoken.json fájlok** – ezek OAuth hitelesítési fájlok, amik jelenleg a repókban vannak commitolva (7 repóban ismétlődik ugyanaz a 2 fájl). Ezeket nem néztem bele tartalmilag, de érdemes ellenőrizni, hogy nincsenek-e éles titkok verzió alatt – a HYPE OS-ben ezek Railway/Storage secret-ként kezelendők, nem repóba commitolva.
6. **Polling-alapú architektúra** – szinte minden repó `while True: ... sleep()` mintát követ (60-300 mp), kivéve a Hype-repót, ami már rendes API+worker (Celery) architektúra. Ez pontosan az, amit a projektindító doksi "Event Driven működés" fejezete el akar érni a teljes rendszerre.

---

*Ez a dokumentum a `hype_os_migration_map.md` és a `hype_os_kapcsolati_abra.mermaid` kiegészítője – a Railway-oldal teljes feltérképezése után. A 9. pontban felsorolt nyitott kérdések megválaszolása után érdemes egy kört tenni a Migration Map-en és a kapcsolati ábrán is, mert a Payment/brand entitások módosíthatják.*
