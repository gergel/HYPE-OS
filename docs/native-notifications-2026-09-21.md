# Natív app: értesítések és táblázatmentés

Az Apple-app a saját profilban kilenc értesítési típust kapcsolhat be/ki. A GET/PUT `/api/v1/notifications/preferences` kizárólag a bejelentkezett ember beállításait éri el. A PUT részleges frissítés. A kapcsolók a telefonos pushra vonatkoznak; az app értesítési előzménye megmarad. Ismeretlen típus nem kerül automatikusan pushra. A jelenlegi kilenc típus alapból engedélyezett.

Az APNs-eszköz a bejelentkezett emberhez és a token érvényességéhez kapcsolódik. Az üzleti tranzakció részeként tartós küldési sor keletkezik. A küldő ellenőrzi a címzettet, az eszköztulajdonost, a lejáratot, az olvasottságot és az aktuális kapcsolókat. Átmeneti hiba esetén késleltetve újrapróbál; az érvénytelen eszközt leállítja. A küldéshez nem szükséges a telefonon futó app.

A táblázat opcionális `check_previous`, `expected_ertek`, `expected_szin`, valamint kötegelt mentésnél `expected_rows` / `expected_columns` mezőkkel védhető az időközbeni módosításoktól. A natív kliens ezeket elküldi. A munkalap zárolása együtt kezeli a cellamentést, a szerkezeti változásokat és a Sheet-importot. A régi webes kliens működése kompatibilis marad; ellenőrző mezők nélkül nem kap tartalomütközés-védelmet.

## Telepítés Railwayre

A módosítás alapja: `claude/hype-os-project-scaffold-8nlgej`, `f23ac481b93112e9bca29b53c13562fb1a333b04`. A `main` lényegesen régebbi scaffold, nem az app szerződésének megfelelő kód.

1. Az új kód indítása előtt `alembic upgrade head`. Új migrációk: `hype_push_20260920`, `hype_preferences_20260921`. Három új tábla, meglévő üzleti adatok átírása nélkül.
2. Railway titkos változók: `APNS_KEY_ID`, `APNS_TEAM_ID`, `APNS_PRIVATE_KEY`, `APNS_TOPIC`. A `.p8` kulcsot nem szabad a repóba tenni. Az app jelenlegi bundle ID-ja `com.hypeclient.apple.dev`; a topicnak a ténylegesen aláírt apphoz kell illeszkednie.
3. Apple Developer: Push Notifications capability és megfelelő provisioning profil. Debug sandbox APNs, terjesztett build production APNs.
4. Az API startup eseménye indítja a küldőt; a szolgáltatásnak folyamatosan futnia kell. A kulcsok hiányában a küldő kikapcsolva marad, az eszközregisztráció `enabled: false` választ ad.
5. Valós iPhone ellenőrzés: engedélyezés/tiltás, háttér/bezárt app, fiókváltás, több eszköz, értesítés megnyitása. A küldés Apple általi elfogadása nem garantál azonnali megjelenést: hálózat, Fókusz és rendszerbeállítások befolyásolják.

## Ellenőrzés

40 izolált szerverteszt: push sor, visszagörgetés, retry, eszköztulajdonos, lejárat, kategóriák, hitelesítés, részleges preferenciamentés, más fióktól elkülönítés, cella/szerkezet ütközés és teljes köteg visszagörgetése. Az APNs-helyettesítés nem küld valódi üzenetet. A migrációk PostgreSQL offline SQL-generálása sikeres. PostgreSQL többfolyamatos zárolási teszt, valódi APNs-kézbesítés és Railway-telepítés még nem történt.

A sor kézbesítése legalább egyszeri: APNs-elfogadás és DB-commit közötti leállás után ritkán ismétlődhet jelzés; a stabil collapse ID csökkenti az ismétlődést. Hálózat nélküli kijelentkezéskor a szerveres eszköztörlés csak a hálózat helyreállásakor lenne lehetséges; jelenleg a token lejárata korlátozza az érvényességet.
