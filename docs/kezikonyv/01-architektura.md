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

Hosszú listás választónál (munkatársak, cégek, oszlopok) `KeresosSelect` a
komponens, nem natív `<select>`: az utóbbi "keresése" a böngésző betű-ugrálása,
ami nem szűkíti a listát és pár száz ezredmásodperc után elfelejti a beírtat.
A `KeresosSelect` panelje tetején valódi, megmaradó keresőmező áll, és
**ékezet-független** (aki "arvai"-t ír, megtalálja Árvait).

Rövid listánál (állapot, típus, rendezés) marad a natív select - három elem közt
keresni csak zaj. Szöveges értékkészletű mezőknél a `SelectDropdown` a
megfelelő komponens (az új értéket is felvehet), azonosító-választásnál a
`KeresosSelect`.

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
