# Strukturált bejövő számla-piszkozat, hiányzó alvállalkozói dokumentumok, audit-napló

A 2026-09-28-i fejlesztés backend-leírása. A cél: a gépi (AI / Lara / szabály)
számlafeldolgozás strukturált eredménye a meglévő érkeztetőbe kerüljön. A
rendszer ott összeveti a törzsadattal, és a hiányzó TIG-eket és
keretszerződéseket előkészítési opcióként jelzi. A lezajlott forgatások
alvállalkozói dokumentumai követhetők, emlékeztető-számlálással. Pénzügyi
állapot csak explicit, megerősített hívással változhat.

## Rétegek

| Réteg | Fájl |
| --- | --- |
| Migráció | `backend/alembic/versions/r1m8j29g6h40_szamla_draft_hianyok_audit.py` |
| Modellek | `app/models/bejovo_szamla.py` (új mezők, új állapot), `app/models/automatizalas.py` |
| Bemeneti szabályok | `app/schemas/szamla_draft.py` |
| Szolgáltatások | `app/services/szamla_draft.py`, `app/services/utokovetes_hianyok.py`, `app/services/automatizalas_audit.py` |
| Vezérlők | `app/api/routes/bejovo_szamlak.py`, `app/api/routes/utokovetes_hianyok.py` |
| Tesztek | `backend/tests/test_szamla_draft_hianyok.py` |

## Migráció (`r1m8j29g6h40`, csak additív)

A migráció visszafordítható, és meglévő adatot nem ír át.

**`bejovo_szamlak`**
- Az `allapot` oszlop 20-ról 30 karakterre bővül, mert az új állapotnév
  hosszabb. Postgresben ez csak metaadat-változás.
- Új, üres mezők:
  - `hivatkozott_projektkod`, `hivatkozott_forgatas_datuma`;
  - `partner_vallalkozas_id`, `partner_employee_id`, `szerzodes_id` (FK,
    `SET NULL`);
  - `validacio` (JSON).

**`automatizalas_audit`** (új tábla)
- Hozzáfűzhető napló: ki (rendszer / ai / felhasználó), mit, melyik
  erőforráson, milyen eredménnyel, milyen részletekkel.
- Nincs rá módosító vagy törlő végpont.

**`utokovetes_dokumentumok`** (új tábla)
- A mátrix tárolt része: projekt × számlázó fél × dokumentum.
- Mezők: emlékeztetők száma, utolsó értesítés ideje és csatornája, a
  dokumentum állapota az értesítéskor.

## Bejövő számla-piszkozat

### `POST /api/v1/bejovo-szamlak/draft`

Jogosultság: `/penzugyek` oldal, `create` (mint a számlafeltöltésnél).

Bemenet:
- `partner_adoszam`, `partner_nev`, `szamlaszam`;
- `netto` / `afa_osszeg` / `brutto` (legalább kettő), `penznem`;
- `fizetesi_hatarido`, `kiallitas_datuma`, `teljesites_datuma`;
- `projektkod`, `forgatas_datuma`;
- `kinyero` (`ai` | `lara` | `szabaly` | `kezi`), `mezo_bizonyossag`,
  `megjegyzes`.

**Érvényesítési szabályok (422)**
- Adószám:
  - elfogadott alak: 8 jegyű törzsszám, 11 jegyű `xxxxxxxx-y-zz` (ÁFA-kód
    1–5), vagy `HU` + 8 jegy;
  - kanonikus alakra hozzuk.
- Szöveg: a név és a számlaszám nem lehet üres, és nem tartalmazhat
  vezérlőkaraktert.
- Összegek:
  - nem negatívak (sztornó az érkeztetőben kezelendő) és 1 milliárd alattiak;
  - a harmadik hiányzó összeg kiszámolódik;
  - nettó + ÁFA = bruttó, 1 Ft tűréssel.
- Dátumok:
  - a fizetési határidő nem lehet korábbi a kiállításnál;
  - a teljesítés legfeljebb egy évvel előzheti meg a kiállítást.
- Pénznem: háromjegyű ISO-kód.
- Projektkód: csak betű, szám, szóköz és `- _ / .` jel lehet benne;
  nagybetűsítjük.
- `mezo_bizonyossag`: 0 és 1 közötti értékek.

**Érvényesítés a törzsadattal** (`services/szamla_draft.validal`, a
beküldéskor automatikusan fut):

1. **Partner.**
   - Adószám alapján keressük a vállalkozások és a munkatársak vállalkozói
     adószáma között.
   - A teljes 11 jegyű egyezés erősebb, mint a törzsszám-egyezés.
   - Figyelmeztetést adunk, ha a név eltér, csak a törzsszám egyezik, vagy
     több rekord is illeszkedik.
2. **Projekt.**
   - A projektkód forgatásai közül azok, amelyek a hivatkozott napot
     tartalmazzák.
3. **Fedező szerződés.**
   - Keretszerződés: érvényes alvállalkozói keretszerződés az adott napon
     (`models/contract.keretszerzodes_ervenyes`: kapcsoló és érvényességi
     időszakok).
   - Ennek hiányában elfogadott az erre a projektre szóló eseti szerződés
     is („Kiküldve” / „Van már szerződés”; a „Kihagyva” figyelmeztetéssel).
4. **Külsős TIG.**
   - A partner kiküldött TIG-je a projektkód és a forgatási nap szerint (a
     TIG tételein át is, mert egy TIG több projektet fedhet).
   - Projektkód nélkül: a partner TIG-jei, amelyek forgatása a napra esik.
   - Figyelmeztetést adunk, ha:
     - a TIG összege eltér a számláétól;
     - a TIG-hez már van számla, vagy már kifizetett;
     - a TIG-et kihagyták.

**Állapot**

| Eredmény | Állapot |
| --- | --- |
| Hiányzik a fedező szerződés vagy a kiküldött TIG | `hianyzo_dokumentumok` |
| Minden megvan, de több TIG jön szóba | `pontositas` |
| Minden megvan, egyértelmű | `ellenorzendo`, céllal: `kulsos_tig` + a TIG |

A `hianyzo_dokumentumok` állapotú számla nem hagyható jóvá.

**Előkészítési opciók** (`validacio.elokeszitesi_opciok`)
- Az opció csak javaslat: melyik MEGLÉVŐ végpont, milyen előtöltött
  adattal.
- `automatikusan_fut` mindig `false`: a rendszer maga nem hívja meg.
- Lehetséges opciók:
  - `partner_felvetele` → `POST /api/v1/vallalkozasok`;
  - `keretszerzodes_elokeszitese` → `POST /api/v1/contracts/keretszerzodes`;
  - `eseti_szerzodes_elokeszitese` →
    `POST /api/v1/alvallalkozoi-szerzodesek/{projekt}/{kulcs}/save` (csak
    mentés, küldés nélkül);
  - `tig_elokeszitese` / `tig_piszkozat_kiegeszitese` →
    `POST /api/v1/teljesitesi-igazolasok/{projekt}/{kulcs}/save`, a számla
    nettójával és a forgatás napjaival előtöltve;
  - `stab_ellenorzese`: a partner nincs a forgatás számlázó felei között;
  - `projektkod_pontositasa`, `forgatas_pontositasa`.

**Idempotencia**
- Ugyanaz a gépi beküldés még egyszer: a meglévő piszkozat jön vissza,
  `mar_letezett: true` jelöléssel.
- Ugyanaz a partner + számlaszám eltérő adattal vagy más forrásból: 409.

### További végpontok

- `POST /api/v1/bejovo-szamlak/{id}/draft/ujravalidalas`:
  - újraellenőrzés, pl. miután elkészült a hiányzó TIG;
  - jogosultság: `edit`.
- `GET /api/v1/bejovo-szamlak/{id}/audit`: a számla audit-naplója.
- `PATCH /api/v1/bejovo-szamlak/{id}`:
  - új mezőkkel bővült: `hivatkozott_projektkod`, `hivatkozott_forgatas_datuma`;
  - gépi piszkozatnál adatjavítás után az ellenőrzés fut újra, nem a
    fájl-alapú javaslattevő.
- `POST /api/v1/bejovo-szamlak/{id}/fajl`:
  - gépi piszkozatnál a fájl csatolása nem futtat AI-kiolvasást, tehát nem
    írja felül a strukturált adatot;
  - csak az ellenőrzés fut újra.

## Pénzügyi állapotváltozás csak explicit megerősítéssel

- A gépi piszkozat jóváhagyásához (`POST /{id}/jovahagyas`) ez kell:
  `"megerosites": {"megerositve": true, "ellenorzo_kod": "<kód>"}`.
  - Az `ellenorzo_kod` a részletes nézet `ellenorzo_kod` mezője.
  - A kód a pénzügyi adatok ujjlenyomata: partner, számlaszám, összegek,
    pénznem, cél és a csatolt fájl.
- Hibás megerősítés:
  - megerősítés nélkül vagy `false` értékkel: **428**;
  - elavult kóddal (az adat azóta változott): **409**;
  - az elutasított kísérlet is bekerül az audit-naplóba.
- A felület (Beérkező számlák) a jóváhagyás előtt frissen lekéri az
  adatot, megerősítő ablakot mutat, és ennek kódját küldi.
- Lara végrehajtója gépi piszkozatot nem rögzíthet
  (`admin_agent/executor._run_szamla_jovahagy`): ez csak a felületen,
  megerősítéssel mehet.
- A jóváhagyás a TIG-hez csatolja a számlát, de **nem jelöli
  kifizetettnek**.
- A kifizetés jelölése továbbra is a TIG / belsős TIG / utalás-felvezetés
  saját, kézi végpontjain történik. Ezek már ma is kifejezett emberi
  műveletek, dátumválasztó ablakkal; nem változtak.
- A draft- és hiány-szolgáltatás forrásszinten sem ír kifizetési vagy
  rögzítési állapotot. Ezt teszt őrzi.

## Audit-napló

| Művelet | Szereplő | Mikor |
| --- | --- | --- |
| `szamla_draft.letrehozas` | ai / rendszer / felhasználó (a `kinyero` szerint) | beküldés |
| `szamla_draft.validacio` | rendszer | minden ellenőrzés (előtte/utána állapot, hiányok, opciók) |
| `szamla.automatikus_besorolas` | ai | a fájl-alapú kiolvasás és javaslat (`szamla_erkeztetes.feldolgoz`) |
| `szamla.jovahagyas` | felhasználó | jóváhagyás: a gépi javaslat és az emberi döntés összevetése; az elutasított kísérletek is |
| `utokovetes.emlekezteto` | felhasználó | emlékeztető rögzítése |

A napló sosem tárol:
- bankszámlaszámot, IBAN-t;
- tokent, jelszót;
- e-mail-törzset vagy fájltartalmat.

A hosszú szövegeket csonkoljuk.

## Hiányzó alvállalkozói dokumentumok

### `GET /api/v1/utokovetes/hianyok`

Paraméterek: `napok` (alapból 120), `csak_hianyos` (alapból igen),
`project_id`, `ma`. Jogosultság: `/utokovetes` oldal, `view`.

**Mely forgatások kerülnek bele**
- A papírozás hatókörébe eső projektek (ugyanaz a szűrés, mint az
  Utókövetés listában).
- Csak a lezajlottak: a forgatás utolsó napja ma előtt volt.
- Dátum nélküli projekt kimarad.

**Soronként egy számlázó fél** (stábtag vagy alvállalkozói kiadás, a
belsősök nélkül), három dokumentummal:

| Dokumentum | Lehetséges állapotok |
| --- | --- |
| szerződés | keretszerződés fedi · aláírva · van már · kihagyva · **kiküldve, aláírásra vár** · **piszkozat** · **hiányzik** |
| TIG | kiküldve · kihagyva · **piszkozat** · **hiányzik** |
| számla | kifizetve · beérkezett · érkeztetés alatt · beérkezett, de a TIG hiányzik · kihagyva · nem kell · a TIG kiküldése után esedékes · **hiányzik** |

A félkövér állapotok számítanak hiánynak.

Cellánként ezek is szerepelnek:
- `emlekezteto_db`, `utolso_ertesites_at`, `utolso_ertesites_csatorna`;
- `allapot_ertesiteskor`;
- `valtozott_ertesites_ota`: változott-e az állapot az utolsó emlékeztető
  óta.

### `POST /api/v1/utokovetes/hianyok/emlekezteto`

Jogosultság: `/utokovetes`, `edit`.

Bemenet: `project_id`, `szamlazo_kulcs` (`e12` / `v3`), `dokumentum_tipus`,
`csatorna` (`email` | `telefon` | `szemelyes` | `egyeb`), `megjegyzes`.

Mit csinál:
- Egy kiküldött emlékeztető **tényét** rögzíti: a számláló +1, és
  eltárolja az időt.
- **Levelet nem küld.**
- Csak ténylegesen hiányzó dokumentumra fogad el emlékeztetőt.

## Ellenőrzöttség

**Tesztelve**
- A 13 új integrációs teszt (Postgres, rollback) átment.
- A teljes backend-csomag átment.
- A migráció oda-vissza lefutott; az új táblákra nincs modell–séma eltérés.
- A demó adatok nem maradtak az adatbázisban.

**Frontend**
- A `tsc` tiszta; az eslint-hibák száma nem nőtt.
- A felületet böngészőben nem jártuk végig.

**Nem ellenőrzött**
- Éles adaton nem futott.
- Valódi AI-kiolvasóból érkező beküldéssel nem próbáltuk.

**Nincs még**
- Automatikus emlékeztető-küldés. Ha lesz, külön, alapból kikapcsolt
  kapcsoló mögé kerül.
- Felület a `/utokovetes/hianyok` mátrixhoz. Most csak az API létezik.
