# Gyártás-TV

A gyártási szobában egy TV-re kirakott, **élő** áttekintő. Larától független.

**Cím:** `/gyartas` (menü: *Gyártás (TV)*). Bejelentkezés kell; a jogosultsága
külön állítható a Beállításokban (*Gyártás (TV)* oldal, megtekintés).

## Mit mutat

- **A héten** (hétfőtől vasárnapig): a forgatások naponta: idő, név, projektkód,
  megrendelő, helyszín és a stáb (a munkatársak saját színével). A mai nap
  kiemelve, az elmúlt napok tömörítve. Felül: *Ma forgat*: aki ma forgatáson van.
- **Most vág**: aki épp futó időmérővel dolgozik valamin, és min.
- **Négy oszlop a vágásokról**:
  - *Épp vágják*: ki mit vág, a futó mérővel dolgozók elöl.
  - *Ellenőrzésen*: beérkező, ellenőrzés.
  - *Kiküldhető*: mehet a megrendelőnek.
  - *Gyártásra vár*: válasz kell tőlünk; aki a legrégebben vár, az elöl.

  A kártyán szerepel a lejárt határidő (piros), a prioritás (★) és az is, ki
  dolgozik rajta.

## Melyik állapot melyik oszlop

Az utómunka-állapotok szabad szövegek, ezért alapból a **nevük** dönt:

| Az állapot nevében | Oszlop |
| --- | --- |
| „kész … kiküld”, „archiv”, „töröl”, „lezár” | nem jelenik meg |
| „gyártás”, „kérdés”, „válasz”, „egyeztet”, „info” | Gyártásra vár |
| „kiküld” | Kiküldhető |
| „ellenőrz”, „beérkez” | Ellenőrzésen |
| minden más | Épp vágják |

Állapotonként felülírható: *Utómunka → Nézet beállítása → Gyártás-TV*.
Ha 120 napja nem mozdult egy anyag, nincs futó mérője, és nincs jövőbeli
határideje, akkor nem kerül ki.

## Élő működés

- 10 másodpercenként a háttérben újra lekéri az adatot. Nem villan, csak a változás látszik.
- Óránként újratölti az oldalt, így a bejelentkezés magától megújul, és az új verzió is felkerül.
- A képernyőt ébren tartja (Wake Lock), és mindig sötét témával jelenik meg.
- A túl hosszú oszlopok lassan maguktól görögnek.
- Egérmozgásra előjön a *Teljes képernyő* és a *Vissza* gomb.
- Hálózati hibánál a legutóbbi adat marad kint, és kiírja, hogy újrapróbálja. Lejárt bejelentkezésnél szól.

Backend: `backend/app/services/gyartas_tv.py`, `GET /api/v1/gyartas/tv`.
Frontend: `frontend/app/(tv)/gyartas`, `frontend/components/gyartas/GyartasTv.tsx`.
