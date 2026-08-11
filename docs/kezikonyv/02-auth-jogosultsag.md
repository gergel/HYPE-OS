# 02 - Bejelentkezés és jogosultság

Kulcsfájlok: `backend/app/core/security.py`, `backend/app/api/routes/auth.py`,
`backend/app/api/routes/user_access.py`, `frontend/lib/permissions.ts`,
`frontend/lib/nav.ts`, `frontend/middleware.ts`.

## Bejelentkezés

- JWT Bearer token, `Authorization` header (**nem** cookie) - ezért nincs
  CSRF-kockázat, és ezért engedhető meg a wildcard CORS.
- A munkamenet **30 napos és gördülő**: minden oldalbetöltésnél megújul, ha már a
  felénél jár (`POST /auth/refresh` + `frontend/middleware.ts`). Aki használja a
  rendszert, sosem fut ki.
- Az első admin nem API-ból jön létre, hanem szkriptből:
  `docker compose exec backend python scripts/create_admin.py <email> <jelszó> "<Név>"`.

## Két, egymástól független dimenzió

Ezt a legfontosabb megérteni: egy munkatársnak van **üzleti típusa** és **rendszer-szerepköre**, és a kettő nem ugyanaz.

**Üzleti típus** (`EmployeeType`, `models/employee.py`) - ki ő a cég működésében:
`belsos`, `kulsos`, `vago`, `kreativ`, `stab`. Ebből következik, milyen papír kell
tőle. Belsősnél tovább bontja a `BelsosJogviszony`: `megbizas` (havonta számláz →
kell havi TIG) vagy `alkalmazott` (bérszámfejtés → nincs havi TIG, csak a fizetés
bekerül az adott hónapra).

**Rendszer-szerepkör** (`SystemRole`) - mit csinálhat a felületen:

| Szerepkör | Mit jelent |
|---|---|
| `admin` | Mindent, beleértve a Beállításokat és a jogosultság-kiosztást |
| `operator` | Napi operatív munka |
| `vago` | Vágói nézet, a rá bízott anyagokkal |
| `ugyfel` | Ügyfél-hozzáférés |
| `adminisztracio` | A projektek teljes papírozásáért felel; a dashboard "Teendőim" widgete neki külön kihozza a hiányzó papírokat |

## Három réteg védi az adatot

1. **Szerepkör** - `require_roles(Role.ADMIN)` és társai a durva szűrő.
2. **Per-oldal, per-művelet jogosultság** - `check_page_action()` /
   `require_page_action(page, action)`. Ez a szerepkör **mellett** fut, nem
   helyette. Adminban, a Beállítások oldalon állítható be egyénenként, oldalanként
   a megtekintés / szerkesztés / létrehozás / törlés (`PageAccessConfig.page_permissions`).
3. **Mező- és fül-szintű láthatóság** - `field_visibility`, `check_tab_action()`:
   egy oldalon belül is elrejthető mező vagy fül.

Ezenfelül a vágói anyag-hozzáférés külön korlátozható: `lathato_anyagok()` /
`ellenorizd_anyag_hozzaferest()` (`PageAccessConfig.lathato_deliverable_idk`).

## A "page" kulcs - ahol a leggyakoribb hiba születik

A jogosultsági "oldal" kulcsa a **frontend nav-elem href-je** (`frontend/lib/nav.ts`),
és pontosan ugyanaz az érték szerepel a backend `build_crud_router(..., page=...)`
és `require_page_action(PAGE, ...)` hívásaiban.

Több nav-elem oszthat egy kulcsot - ilyenkor a nav-elemen ott a `permissionPage`:

- Külsős / Vágók / Belsősök → mind `/csapat` (ugyanaz az Employee-router)
- Eszközök / Leltározás → `/felszereles`
- Ügyfelek / Megrendelői kontaktok → `/ugyfelek`
- Keretszerződések / Eseti szerződések / Számlázó cégek → `/penzugyek`
- E-Rezsi / Biztosítások → `/kotelezettsegek`

Ha itt eltér a frontend és a backend érték, az vagy **túl szigorú** (feleslegesen
kér külön jogot), vagy **túl megengedő** (egy másik oldal joga is beengedi). Új
oldal felvételekor mindig ellenőrizd, hogy a `nav.ts`-beli kulcs és a backend
`page=` ugyanaz.

A `resolvePermissionPage()` a leghosszabb egyező href alapján dönt, ezért kerül
pl. a `/projektek/project-kodok/123` helyesen a "Project Code-ok" jogához, nem a
"Projektek"-éhez.

## Mit hol állíts

| Amit akarsz | Hol |
|---|---|
| Valaki ne lásson egy oldalt | Beállítások → oldal-hozzáférés (admin) |
| Valaki lássa, de ne szerkeszthesse | ugyanott, művelet-checkboxok |
| Egy mező ne látszódjon | Beállítások → mező-láthatóság |
| Valaki más szerepkört kapjon | a munkatárs adatlapja (`system_role`) |
| Egy vágó csak bizonyos anyagokat lásson | Beállítások → látható deliverable-ök |
