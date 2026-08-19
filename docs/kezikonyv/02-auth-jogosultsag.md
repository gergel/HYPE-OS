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
- E-Rezsi → `/kotelezettsegek`

Ha itt eltér a frontend és a backend érték, az vagy **túl szigorú** (feleslegesen
kér külön jogot), vagy **túl megengedő** (egy másik oldal joga is beengedi). Új
oldal felvételekor mindig ellenőrizd, hogy a `nav.ts`-beli kulcs és a backend
`page=` ugyanaz.

A `resolvePermissionPage()` a leghosszabb egyező href alapján dönt, ezért kerül
pl. a `/projektek/project-kodok/123` helyesen a "Project Code-ok" jogához, nem a
"Projektek"-éhez.

### Oldal-aliaszok: a DISZPÓ joga a projekthez is beenged

Van egy eset, ahol két oldal joga összefügg: aki a **diszpókat** viszi, annak a
munkája a **projekten** van. Neki kell a gyártás és a technika adata, ő írja a
gyártás kommentet, ő tölti fel a diszpó levél mellékleteit, és ő nyomja meg az
előzetes és a teljes diszpó gombját. Egy "csak diszpó" hozzáférés emiatt
használhatatlan volt: a felület beengedte a naptárba, a projekt megnyitásakor
viszont visszadobta a Dashboardra.

Ezért a `/naptar` joga **átszáll** a `/projektek` oldalra - `view` és `edit`
műveletre, **create/delete NÉLKÜL**: projektet létrehozni és törölni nem a
diszpós dolga. Az alias sosem ad többet, mint amennyi a saját oldalán is
megvan: aki a diszpót csak nézheti, az a projektet is csak nézheti.

A szabály **két helyen, egyformán** van kimondva, és együtt kell módosítani
őket - különben a felület mást mutatna, mint amit a szerver enged:

| Hol | Mit csinál |
|---|---|
| `backend/app/core/security.py` → `OLDAL_ALIASZOK` | a `check_page_action` és a `check_tab_action` ezt nézi (a fül-szintű beállítás továbbra is csak SZŰKÍT) |
| `frontend/lib/permissions.ts` → `OLDAL_ALIASZOK` | a `canDoAction` és a `middleware.ts` navigáció-zára |

Két dolog **nem** változik ettől: az oldalsávban nem jelenik meg új menüpont (az
az `allowed_pages`-ből épül, a projekthez a naptárból jut el), és a **költségek**
továbbra is `/penzugyek`-jogosultsághoz kötöttek. A projekt oldalán az Utómunka
kártya el is tűnik a csak-diszpós felhasználónak: ott a létrehozás úgyis 403-at
adna (az `/utomunka` külön jogosultság), és egy működésképtelen gomb rosszabb,
mint a hiánya.

Ugyanez a szabály tette **szigorúbbá** a két diszpó-küldő végpontot: korábban
puszta szerepkört néztek (`require_roles(ADMIN, OPERATOR)`), tehát bármelyik
operátor kiküldhetett bármilyen diszpót akkor is, ha a Projektek oldalhoz nem is
volt joga. Most oldal+művelet alapúak (`require_page_action("/projektek",
"edit", ...)`).

## Mit hol állíts

| Amit akarsz | Hol |
|---|---|
| Valaki ne lásson egy oldalt | Beállítások → oldal-hozzáférés (admin) |
| Valaki lássa, de ne szerkeszthesse | ugyanott, művelet-checkboxok |
| Egy mező ne látszódjon | Beállítások → mező-láthatóság |
| Valaki más szerepkört kapjon | a munkatárs adatlapja (`system_role`) |
| Egy vágó csak bizonyos anyagokat lásson | Beállítások → látható deliverable-ök |
