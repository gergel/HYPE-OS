# Árajánlat-készítő modul (2026-09)

A specifikáció: `HYPE_OS_arajanlat_keszito_PROMPT.md` (a felhasználótól). Az
Árajánlatok oldal (`/arajanlatok`) erre épült át.

## Mit tud

- **Új árajánlat**: márka (HYPE / ContentBee), ügyfél (kereshető, új is
  felvehető), projekt neve, dátum, helyszín, végül sablon-kártya vagy „Üres ajánlat”.
  A sablon betölti az alap tételeket az alapárakkal. Az opcionális sorok
  opcióként kerülnek be.
- **Szerkesztő** (`/arajanlatok/[id]`):
  - táblázat: Tétel/Szolgáltatás | Alkalom | Mennyiség | Egységár | Teljes ár;
  - minden cella helyben szerkeszthető;
  - szekció-fejlécek átnevezhetők, a sorok fogd-és-vidd módszerrel rendezhetők;
  - sor menü: opcionális be/ki, duplikálás, sorkedvezmény, vissza a
    katalógusárra, csere variánsra (pl. LED fal P4.8 → P3.9), áthelyezés
    másik szekcióba, törlés;
  - jelzés, ha a sor ára eltér a mostani katalógusártól („Katalógusár: … – frissít?”);
  - élő összesítő: részösszeg, kedvezmény (% + Ft), nettó, ÁFA, bruttó;
    havidíjas módban havidíj is;
  - megjegyzés-blokk (sablonból betölthető);
  - státusz, verziók, „Duplikálás variánsként”, „Új verzió”, „Mentés sablonként”;
  - XLSX / PDF export;
  - automatikus mentés (késleltetve).
- **Katalógus-panel** a szerkesztő jobb oldalán:
  - keresés és kategória-szűrő;
  - egy kattintás egy új sort ad a kijelölt szekcióba;
  - az ársáv és az adott ügyfélnek legutóbb adott ár tippként látszik.
- **Katalógus** (`/arajanlatok/katalogus`):
  - helyben szerkeszthető név, leírás, egység, alapár, min és max;
  - ártörténet, archiválás, új tétel, új kategória;
  - „Alapadatok betöltése”.
- **Sablonok** (`/arajanlatok/sablonok`):
  - a sablon adatai (összesítő címke, alkalom-felirat, tipikus végösszeg, megjegyzés);
  - sorok katalógusból vagy egyedi sorként, alapértelmezett alkalom és
    mennyiség, árfelülírás, opcionális jelölő, sorrend;
  - „Új ajánlat ebből”.
- **Régi ajánlatok** (`/arajanlatok/regi`): a korábbi, JSON-alapú szerkesztő
  mentett ajánlatai változatlanul megnyithatók és szerkeszthetők.

## Szabályok

- A pénz egész forintban, nettóban szerepel (BIGINT). Az ÁFA csak kijelzés.
- Egy sor összege: alkalom × mennyiség × egységár × (1 − sorkedvezmény%),
  forintra kerekítve.
- A nettó végösszeg a nem opcionális sorok összege, mínusz a kedvezmény
  (a részösszeg százaléka + fix összeg, legfeljebb a részösszegig).
- **Ár-snapshot:** a katalógusár a hozzáadáskor bemásolódik. Átárazáskor a
  meglévő ajánlatok nem változnak, az ártörténet megmarad.
- **Számozás:** `HYPE-2026-0001`, `CB-2026-0001` – márkánként, évente újraindul.
  - A „Duplikálás variánsként” új számot ad.
  - Az „Új verzió” ugyanazt a számot adja, eggyel nagyobb verzióval.
  - Márkaváltáskor az ajánlat új számot kap, ha még nincs másik verziója.
- **Export:**
  - Fájlnév: `HYPE_ÁRAJÁNLAT_<ÜGYFÉL> - <PROJEKT NEVE>.xlsx`, illetve `CB_…`.
  - Az XLSX „Teljes ár” oszlopa képlet (`=B*C*D`), a végösszeg `=SUM(...)`.
  - Az opcionális tételek külön blokkba kerülnek, saját összeggel.
  - A cégadatok a beállításokból jönnek: `ARAJANLAT_CEG_NEV`, `ARAJANLAT_CEG_CIM`, `ARAJANLAT_CEG_ADOSZAM`.
- **Jogosultság:** minden az „/arajanlatok” oldal-jogán áll.
  - nézés = view;
  - új ajánlat, variáns, verzió, ügyfél = create;
  - minden szerkesztés (a katalógus és a sablonok is) = edit;
  - ajánlat törlése = delete.

## Alapadatok (seed)

98 katalógus-tétel, 10 sablon (T1–T9, T3b) és a standard megjegyzés.

- **Idempotens:** a már meglévőt és a felületen átírtat nem bántja.
- **Nem a migráció tölti be.** Három módon indítható:
  - az oldal sárga sávjának „Alapadatok betöltése” gombjával;
  - a Katalógus fülön;
  - a `python -m app.quotes.seed` paranccsal.

## Eltérések a specifikációtól (a repó konvenciói miatt)

| Specifikáció | Megvalósítás |
|---|---|
| `quotes` Postgres-séma | Egy séma van a repóban → `quote_*` táblák és `quotes` (migráció `u4p1m52j9k73`) |
| `pg_enum()` | Nincs ilyen segéd → szöveges oszlop + CHECK-kényszer |
| Firebase Auth | A repó saját JWT-auth-ja és oldal-jogai |
| `/api/quotes/...` | `/api/v1/quotes/...` |
| router → service → repository | router → service (a repóban nincs külön repository-réteg) |
| `client` tábla | A meglévő `clients` tábla |
| `python -m app.modules.quotes.seed` | `python -m app.quotes.seed` |
| `/quotes`, `/quotes/catalog`, `/quotes/templates` | `/arajanlatok`, `/arajanlatok/katalogus`, `/arajanlatok/sablonok` (a meglévő oldal-jog és menü miatt) |
| PDF: WeasyPrint | reportlab (tiszta Python wheel, rendszerkönyvtár nélkül) + beágyazott DejaVu betű az ékezetekhez |

Kiegészítések:

- `summary_label` (összesítő címke) és `occasions_label` (pl. LED falnál
  „Nap”) a sablonon és az ajánlaton;
- `typical_total` a sablon-kártyához;
- `variant:<csoport>` címkék a cserélhető tételekhez;
- `net_total` az ajánlaton a listához;
- `GET /quotes/{id}/client-prices`: az ügyfél legutóbbi árai egyben;
- `POST /quotes/{id}/items/{item_id}/duplicate`.

## Állapot

- **Tesztelve:**
  - 20 teszt (`tests/test_arajanlat_keszito.py`) lefedi az összegzést, a
    kedvezményt, az opcionális sorokat, a havidíjas módot, a számozást, a seed
    idempotenciáját, a sablonból létrehozást, az ár-snapshotot és az ártörténetet,
    a variánst, a verziót, a sablon mentését, a cserét, az XLSX-képletek
    kiértékelését és a PDF-et, valamint az API-t;
  - a teljes backend-csomag átment;
  - frontend: `tsc`, `eslint`, `next build` rendben.
- **Élőben megnézve (helyi adatbázis, demóadattal, utána takarítva):**
  - alapadatok betöltése, új ajánlat sablonból új ügyféllel, szerkesztés,
    katalógusból hozzáadás;
  - XLSX / PDF letöltés;
  - lista, katalógus, sablonok és mobil nézet.
  - Hiba és javítás: az új ajánlat ablakából indított navigáció eredetileg
    visszaugrott a listára (a felugró ablak vissza-védelme miatt).
- **Nem ellenőrzött:**
  - Excelben megnyitva (itt nincs Excel / LibreOffice); a képleteket teszt értékeli ki;
  - éles adatbázison.
- **Lara:** a megfigyelés továbbra is a régi `arajanlatok` táblát figyeli. Az
  új modul ajánlatait még nem tanulja.
