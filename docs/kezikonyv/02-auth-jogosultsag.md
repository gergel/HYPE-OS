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

## A védett rendszergazda - a rendszer végső kiútja

Mind a három réteget ugyanazon a felületen állítjuk, amit azok védenek. Ebből
következik egy csapda: **egyetlen félrekattintás kizárhatja azt az embert, aki
egyedül tudná visszaadni a jogot** - elég inaktívra állítani, átírni a
szerepkörét, vagy rányomni a "Hozzáférés törlése" gombra. Adatbázis-hozzáférés
nélkül ez kívülről nem javítható.

Ezért van egy **védett rendszergazda** fiók (`core/security.vedett_rendszergazda`),
amit a `VEDETT_ADMIN_EMAILEK` beállítás jelöl ki (vesszővel több is lehet).
Erre a fiókra:

- **mindig aktív** - az `is_active = false` nem tartja kint, és a belépés vissza
  is állítja a rekordot (`routes/auth.py _vedett_fiok_helyreallitasa`), tehát a
  javítás útja: *jelentkezz be újra*;
- **mindig admin** - a `require_roles` átengedi akkor is, ha a tárolt szerepköre
  más lenne;
- **nincs korlátozás** - a `check_page_action`, a `check_tab_action`, a
  `/user-access/me` és a `/field-visibility/me/...` is "nincs szűrés"-t ad rá
  (utóbbi kettő azért fontos, mert a menü és a middleware azokból dolgozik: e
  nélkül a backend beengedné, a felület viszont mégis elrejtené az oldalakat);
- **nem is rontható el** - az `is_active`, a szerepkör, az e-mail és a jelszó
  módosítása, a fiók törlése, a jogosultság-korlátozás és a hozzáférés
  visszavonása mind hibát ad rá (a tömeges "mindenki más hozzáférésének
  visszavonása" pedig kihagyja).

A védettség **a címen múlik**, nem azonosítón: a rekord törölhető és újra
felvehető, importálás után más id-t kaphat, a cím viszont ugyanaz marad. Ebből
következik, hogy az **e-mail módosítása is tiltott** ezen a fiókon - átírni
annyi lenne, mint kikapcsolni a védelmet. Mivel a cím a rendszerben nem egyedi,
a beállításba **személyes címet** adj meg, közös postafiókot ne.

A meglévő, elrontott állapotot a `b7d3f1a90c24` adatmigráció teszi rendbe
(aktív + admin, a korlátozó sorok törlésével) - így nem kell megvárni a
következő belépést, és nem kell adatbázishoz nyúlni.

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
