# Gyártás-TV

A gyártási szobában egy TV-re kirakott, **élő** áttekintő. Larától független.

**Cím:** `/gyartas` (menü: *Gyártás (TV)*). Bejelentkezés kell; a jogosultsága
külön állítható a Beállításokban (*Gyártás (TV)* oldal, megtekintés).

## Mit mutat

- **A héten forgatunk** (hétfőtől vasárnapig; a képernyő bal fele, nagy
  betűkkel): a forgatások naponta: idő, név, projektkód, megrendelő, helyszín és
  a stáb (a munkatársak saját színével). A mai nap kiemelve, az elmúlt napok
  tömörítve. Felül: *Ma forgat*: aki ma forgatáson van.
- **Négy oszlop a vágásokról**:
  - *Épp vágják*: amin **most fut valakinek az időmérője**, az állapotától
    függetlenül. A kártya azt is mutatja, ki vágja és mióta; a legrégebben
    futó mérő van elöl.
  - *Ellenőrzésen*: beérkező, ellenőrzés.
  - *Kiküldhető*: mehet a megrendelőnek.
  - *Gyártástól kérdés*: azok az utómunkák, amelyeknek az állapota
    „Gyártástól kérdés”. Aki a legrégebben vár, az elöl.

  A kártyán szerepel a lejárt határidő (piros), a prioritás (★) és az is, ki
  dolgozik rajta.

## Melyik állapot melyik oszlop

Ha egy anyagon fut valakinek az időmérője, akkor az *Épp vágják* oszlopba
kerül, bármi is az állapota. Ha nem fut rajta mérő, az állapot **neve** dönt
(kis- és nagybetű, ékezet és dupla szóköz nem számít):

| Állapot | Oszlop |
| --- | --- |
| „kész … kiküld”, „archiv”, „töröl”, „lezár” | nem jelenik meg |
| pontosan „Gyártástól kérdés” | Gyártástól kérdés |
| „kiküld” a nevében | Kiküldhető |
| „ellenőrz”, „beérkez” a nevében | Ellenőrzésen |
| minden más (pl. Aktuális, Javítás) mérő nélkül | nem jelenik meg |

Állapotonként felülírható: *Utómunka → Nézet beállítása → Gyártás-TV*
(Ellenőrzésen / Kiküldhető / Gyártástól kérdés / Ne jelenjen meg). Az
*Épp vágják* oszlopot nem lehet állapothoz rendelni, azt mindig a futó mérő
adja.
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
