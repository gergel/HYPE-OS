# 01 - Architektúra

```
Next.js 16 (App Router)  ──/api/v1──▶  FastAPI  ──▶  PostgreSQL
        │                                  ├──▶  Cloudflare R2 (média, dokumentumok)
        │                                  ├──▶  Google (Gmail, Docs, Drive, Calendar)
        └── publikus portál (/p/[slug])     ├──▶  Barion + Számlázz.hu (portál-fizetés)
            bejelentkezés nélkül            └──▶  Gemini (AI Assistant)
```

Egyetlen adatbázis, nincs multi-tenant réteg: a rendszer kizárólag a HYPE (és a
ContentBee márka) működésére készült.

## Mappaszerkezet

| Hol | Mi van benne |
|---|---|
| `backend/app/models/` | SQLAlchemy modellek (entitásonként egy fájl) |
| `backend/app/schemas/` | Pydantic sémák (be- és kimenő adat) |
| `backend/app/api/routes/` | Végpontok, modulonként egy fájl |
| `backend/app/api/crud_router.py` | A generikus CRUD-router gyár (lásd lent) |
| `backend/app/services/` | Üzleti logika, ami több route-ból is kell |
| `backend/alembic/` | Migrációk |
| `frontend/app/(app)/` | A bejelentkezés mögötti oldalak |
| `frontend/app/p/[slug]/` | A publikus Média Portál (nincs bejelentkezés) |
| `frontend/components/` | Újrahasznosított UI, almappák a nagyobb doménekhez |
| `frontend/lib/` | API-kliensek, formázók, jogosultság, navigáció |

## A CRUD-generátor

A legtöbb entitás listája/részletnézete ugyanazt a mintát követi: lista, szűrés,
egy rekord lekérése, létrehozás, mezőnkénti módosítás, törlés. Ezt nem írjuk meg
negyvenszer - a `backend/app/api/crud_router.py` `build_crud_router()` gyártja le
egy modellhez, és a route-fájl csak azt teszi hozzá, ami tényleg egyedi (pl. egy
"kiküldés" gomb végpontja).

Ebből következik két dolog, ami elsőre meglepő:

- Egy modul végpontjait nem mindig találod meg a route-fájlban - a CRUD rész a
  generátorból jön. A `/docs` (Swagger) mindig a teljes, valós listát mutatja.
- A **jogosultság** is itt kapcsolódik be: a `build_crud_router(..., page=...)`
  paramétere köti az adott entitást egy jogosultsági "oldalhoz" (lásd
  [02-auth-jogosultsag.md](02-auth-jogosultsag.md)).

## A rekord-részletnézet motorja

A részletnézetek (projekt, ügyfél, munkatárs, eszköz…) nem külön-külön megírt
oldalak: egy közös motor rajzolja őket, ami adatvezérelt.

- `entity_fields` (`/api/v1/entity-fields`) - **saját mezők** felvétele
  entitásonként, kód nélkül.
- `detail_tabs` (`/api/v1/detail-tabs`) - a részletnézet **fülei** és azok
  sorrendje, adminból szerkesztve.
- `field_visibility` (`/api/v1/field-visibility`) - melyik mező kinek látszik.
- Frontend oldal: `frontend/lib/detail.tsx`, `frontend/lib/detailTabs.tsx`,
  `frontend/components/DetailSections.tsx`, `EditableDetailGrid.tsx`.

Ha egy részletnézeten hiányzik vagy rossz helyen van egy mező, előbb ezeket a
beállításokat nézd meg, csak utána a kódot.

## Keresztmetszeti szolgáltatások

| Modul | API prefix | Mit ad |
|---|---|---|
| Timeline | `/api/v1/timeline` | Esemény-napló minden entitáshoz (ki, mit, mikor) |
| Search | `/api/v1/search` | Globális kereső (`GlobalSearch.tsx`) |
| Notifications | `/api/v1/notifications` | Értesítések, harang ikon |
| Realtime | `/api/v1/realtime` | Élő frissítés; kliensoldal: `frontend/lib/live.tsx` |
| Attachments | `/api/v1/csatolmanyok` | Dokumentum-csatolmányok bármelyik rekordhoz |
| Storage | `/api/v1/media`, `/api/v1/folders` | R2-alapú fájltár |
| Automation | `/api/v1/automation` | Dokumentum-generálás Google Docs sablonból |

## Legördülők és keresés

**Natív `<select>` nincs az alkalmazásban.** A böngésző beépített "keresése"
betű-ugrálás: nem szűkíti a listát, és pár száz ezredmásodperc után elfelejti a
beírtat. Helyette két komponens van, mindkettő kereshető:

| Komponens | Mikor |
|---|---|
| `KeresosSelect` | Azonosítót vagy rögzített értékkészletet választunk (emberek, cégek, oszlopok, típusok, rendezés) |
| `SelectDropdown` | Szöveges értékkészletű mező, ahol ÚJ érték is felvehető (pl. "megbízás tárgya") |

Mindkettő panelje tetején valódi, megmaradó keresőmező áll. A `KeresosSelect`
keresése **ékezet-független** (aki "arvai"-t ír, megtalálja Árvait), a névben és
a kiegészítésben (pl. e-mail) is keres, csoportokat (`optgroup` megfelelője) és
billentyűzetes választást is tud.

Rövid listánál sem térünk el ettől: két különböző viselkedésű legördülő egy
felületen zavaróbb, mint egy fölösleges keresőmező három elem fölött.

## Rétegek: mi kerül mi fölé

A felugró elemeknek **rögzített sorrendjük** van - enélkül minden új ablak
véletlenszerűen bújt volna a másik alá:

| Réteg | z-index | Mi |
|---|---|---|
| Modál | 120 | `ModalReteg` és a saját felugró ablakok |
| Panel | 200 | `AnchoredPanel` (legördülők) - modálon belül is látszania kell |
| Kérdés | 300 | `ConfirmProvider` megerősítő/figyelmeztető ablaka |
| Értesítés | 310 | `ToastProvider` |

A kérdés és az értesítés azért van a tetején, mert MINDEN más rétegből
indulhat. Amíg a megerősítő ablak 110-en volt, egy modálból indított törlés
kérdése a modál **alá** került: a gombjai nem látszottak, és csak az ablak
bezárásával lehetett válaszolni - vagyis a törlést nem lehetett befejezni.

Új felugró elemnél ne találj ki új számot: válaszd a fenti négy közül azt,
amelyik a szerepének megfelel.

**A portálozott panel DOM szerint mindig "kívül" van.** Az `AnchoredPanel` a
`<body>` végére renderel, tehát egy felugró panel, ami kívül-kattintásra
záródik, a SAJÁT legördülőjére kattintva is bezárult - a `pointerdown` a
`click` előtt fut, a gomb eltűnt, és a választás sosem ért célba. A panel
ezért `data-anchored-panel` jelölőt visel, a kívül-kattintást figyelő
komponensek pedig ezt kihagyják (lásd `TableFilterBuilder`). Ha új helyen
figyelsz kívül-kattintást, és lehet benne legördülő, ugyanezt kell tenned.

## Táblázat-szűrő: mire szűrünk

A mezőnkénti szűrő nem külön deklarált szűrőmezőkből dolgozik, hanem abból,
ami a cellában **látszik** (`DataTable` → `nodeToText`). A szöveget három
helyről szedjük ki: `children` → `label` (StatusBadge) → `value`/`placeholder`
(helyben szerkeszthető cellák). A harmadik nélkül a szűrő ott hallgatott, ahol
a legtöbb oszlop szerkeszthető - a Kiadások listáján a megnevezés, a nettó, a
fizetési mód és az állapot MIND ilyen, tehát az oszlop-szűrőnek se találata,
se értékkészlete nem volt.

A **szabadszavas kereső** ugyanerre a szövegre fut: arra, ami a táblázatban
látszik. Korábban a rekord ÖSSZES mezőjéből épült egy külön keresőszöveg -
ez egy 100 oszlopos táblánál (projektkódok) soronként kilobájtokat jelentett,
amit a szerver legyártott és a böngésző letöltött, miközben egy nem látszó
mezőben talált egyezés amúgy is értelmezhetetlen ("miért jött fel ez a sor?").

## Betöltés: mit lát az ember, amíg vár

Három szinten dolgozunk azon, hogy a felület AZONNAL válaszoljon, és a
tartalom utána érkezzen - nem fordítva:

1. **Oldal-váz minden oldalra** (`app/(app)/loading.tsx` → `components/OldalVaz.tsx`).
   A Next.js szerver-komponensei az adatok megérkezéséig nem rajzolnak semmit:
   egy menüpontra kattintva a RÉGI oldal állt a képernyőn mozdulatlanul, amíg a
   szerver végzett - kívülről ez "lefagyott". Ez a fájl Suspense-határt tesz az
   egész alkalmazásra, így a váz ~100 ms-on belül megjelenik, és a tartalom
   akkor váltja fel, amikor kész.
2. **Sor-ablak a táblázatokban** (`InteractiveTableClient`, `ABLAK_MERET`).
   Egyszerre 80 sor kerül a képernyőre, a többi görgetve töltődik
   (IntersectionObserver). A rendezés és a szűrés viszont a TELJES listán fut -
   csak a megjelenítés lépeget. 800 sornál ez 7200 cella helyett 720-at jelent
   az első képernyőn, és a cellák nagy része önálló, kattintható komponens.
3. **Szűkebb lista-sémák a backenden** (`build_crud_router(list_read_schema=…)`).
   A projektkód-lista például a Notionből örökölt ~80 extra mező nélkül megy ki:
   1,6 MB helyett 0,49 MB 800 kódnál. Az adatlap (GET `/{id}`) továbbra is a
   teljes sémát adja.

Ha egy lista lassú, ebben a sorrendben érdemes nézni: mennyi adat megy ki
(séma), hány sor kerül a DOM-ba (ablak), és mennyi ideig tart a lekérdezés
(eager load, lásd `list_options`).

## Világos és sötét nézet

A felület minden színe **token** (`frontend/app/globals.css`) - a komponensek
sosem írnak be nyers hex-kódot. Ezért a világos nézet nem külön stíluslap: egy
`:root[data-theme="light"]` blokk írja felül ugyanazokat a tokeneket, a
SZEREPEK megtartásával (a `surface-1` ott is a váz - oldalsáv, fejléc -, a
`surface-2` a kártyák lapja). Új komponensnél tehát nincs teendő, ha tokeneket
használ.

Az állapotszínek nem ugyanazok az árnyalatok a két nézetben: a sötét nézet halk
tónusai fehér papíron olvashatatlanok lennének, ezért világosban sötétebb,
telítettebb párjuk áll. Ami nem tokenből él (görgetősáv, kijelölés,
`.btn-primary` hover), annak külön `[data-theme="light"]` szabálya van -
ezekből összesen hat darab van, és a `globals.css`-en kívül nincs több.

**A választás emberhez tartozik, nem géphez.** A beállítás a munkatárs
rekordján él (`employees.tema`, `PUT /api/v1/auth/me/tema`), tehát aki otthon
világosra állítja, az az irodai gépen is világosat kap - és egy közös gépen a
következő belépő nem örökli az előző ízlését. Kapcsoló: a fejlécben
(`components/TemaKapcsolo.tsx`), az érték a `TopBar` `getCurrentUser()`
hívásából jön.

Két apróság, ami nem magától értetődő (`frontend/lib/tema.ts`):

- **Süti + blokkoló inline script a `<head>`-ben.** A szerver a legelső
  festéskor még nem tudja, ki néz oda, a `data-theme`-nek viszont ott kell
  lennie, mielőtt bármi kirajzolódik - különben minden oldalbetöltés sötéten
  villanna fel. A süti csak GYORSÍTÓTÁR: ütközéskor a szerverről jövő érték
  nyer, azt a kapcsoló csendben javítja. Azért nem a gyökér-elrendezés olvassa
  a sütit, mert a `cookies()` ott minden oldalt kérésenként renderelővé tenne -
  a bejelentkezés és az adatvédelmi oldal ma statikus.
- **Nincs `prefers-color-scheme`-igazodás.** A HYPE OS sötét alapra tervezett
  felület; akinek az operációs rendszere világos, attól még nem biztos, hogy
  ezt is világosan akarja használni. Aki igen, egy kattintással megkapja.

## Konvenciók

- **Magyar domén-nyelv a kódban is.** Ahol a fogalomnak van bevett magyar neve
  (diszpó, TIG, kötelezettség, utókövetés), ott a modul, a mező és az URL is
  magyarul van. Nem keverjük: egy fogalom egy néven fut végig a stacken.
- **A "miért" a kódban van.** Hosszú docstringek magyaráznak minden nem
  nyilvánvaló döntést. Változtatás előtt olvasd el őket - sok szabály korábbi
  hibából született.
- **A hiányzó integráció nem hiba.** Ha egy külső szolgáltatás kulcsa nincs
  beállítva, az app elindul, és csak az adott képesség jelez vissza
  egyértelműen. Fejlesztéshez nem kell minden kulcs.
