# 14 - Krumpello

Önálló pénzügyi felület a HYPE OS-en **belül**, de attól elválasztva.
Útvonal: `/krumpello`, jogosultság: `/krumpello`, backend:
`routes/krumpello.py`, modell: `models/krumpello.py`.

A Krumpello egy másik üzlet (utcai étel), másik logikával: **nincs projektkód,
nincs ügyfél, nincs TIG és nincs szerződés**. Ami itt van, az kizárólag pénz:
napi kassza, kifizetések, munkabér.

## Miért külön táblák

Ha ezek a HYPE `expenses`/`revenues` tábláiba kerülnének, minden HYPE-összesítő
(éves kiadás, havi trend, projekt-költség) hamis lenne - és fordítva: a
Krumpello képét elhomályosítanák a produkciós tételek. Egy közös tábla + egy
"melyik cég" oszlop csak látszatmegtakarítás: a két oldal MINDEN
lekérdezésében szűrni kellene rá, és egyetlen kifelejtett szűrő összekeverné a
két kasszát.

| Tábla | Mi |
|---|---|
| `krumpello_napok` | Napi kassza-zárás, naponta **pontosan egy** sor |
| `krumpello_kiadasok` | Kifizetések, `forras` = `utalas` / `keszpenz` / `extra` |
| `krumpello_dolgozok` | Aki órabérben dolgozik (nem HYPE `Employee`) |
| `krumpello_munkaorak` | Egy ember egy napja: óra, órabér, fizetés, borravaló |

## Az "extra": ami számla nélkül mozog

Ez a modul kulcsfogalma. **Extra** az a bevétel vagy kiadás, amihez *nincs
számla*, ami megmagyarázná, honnan jött vagy hova ment. Ezek nem hibák - a
valóságban léteznek -, de külön kell látszaniuk, mert csak együtt adják ki a
lényeget:

> **EXTRA EGYENLEG = extra bevétel − extra kiadás.**
> Negatív → több számlázatlan pénz ment ki, mint amennyi bejött.

Ezért kapja az Áttekintés oldalon a legfelső, egész széles kártyát: a többi
szám könyvelésből is kijön, ez csak itt látszik.

## A három egyenleg mást mér

`services/krumpello_osszesito.py`. Nem adhatók össze:

| Egyenleg | Mit mér |
|---|---|
| **Számla** | Kártyás bevétel − utalások. Ami a bankszámlán van. |
| **Készpénz** | Készpénzes bevétel − készpénzes kiadás. Ez **fizikailag megszámolható** a kasszában. |
| **Extra** | A számla nélküli mozgások. Lásd fent. |

A **borravaló** egyikben sincs benne: az a dolgozóké, nem a cég pénze - csak
fizikailag áthalad a kasszán.

> **Egy ponton szándékosan eltérünk a forrás-táblázattól.** Ott a
> készpénz-egyenleg NETTÓ sora a *kártyás* nettóra hivatkozik (`=AJ12-AJ26`,
> ugyanaz az `AJ12`, amit a számla-egyenleg is használ), tehát egy lehúzott
> képlet elgépelése. A bruttó sora (`=AJ8-AJ28`) helyesen a készpénzes
> bevételből indul. Itt a nettó is onnan számol, ezért ez az **egy** szám
> eltér a táblázatétól - és ez a helyes. A másik 11 összesítő-sor tételesen
> egyezik.

## Adat-áthozatal a táblázatból

A **kezdőadat már bent van**: a `c5b71e29d840` migráció betölti
(`app/data/krumpello_kezdoadat.json` - 25 kassza-nap, 122 kiadás, 7 dolgozó,
70 munkanap), tehát a deploy után az adat minden környezetben ott van. A
migráció idempotens, és a `downgrade` szándékosan nem töröl: pénzügyi sorokat
nem dobunk el egy séma-visszalépés mellékhatásaként.

A **későbbi** hónapokat a szkripttel lehet behúzni:

```bash
# a munkafüzet letöltése .xlsx-ként (Fájl -> Letöltés -> Excel), majd:
python scripts/krumpello_import.py penzugy.xlsx --szarazon   # csak jelentés
python scripts/krumpello_import.py penzugy.xlsx
```

Forrás: a "HYPE PRODUCTIONS KFT. 2026 - PÉNZÜGY" munkafüzet
**KRUMPELLO - KASSZA** és **KRUMPELLO - MUNKABÉR** lapja.

### Amit a munkabér-lapról tudni kell

Három olyan szerkezeti sajátosság van, ami nélkül némán veszne el adat:

- **A sorok dátum szerint igazodnak**: ugyanabban a sorban minden embernél
  ugyanaz a nap áll (ellenőrizve: egyetlen sorban sincs két különböző dátum).
  Ezért ha valakinél üresen maradt a dátum-cella, a sor dátuma a többiek
  oszlopából pótolható - enélkül az a munkanap kimaradna.
- **A borravaló oszlopba jegyzet is kerül** ("BÓNUSZ: 5000 FT",
  "8400 - Üzemorvos"). Az összeget kiolvassuk, a szöveget megjegyzésként
  megtartjuk. Van olyan nap, amikor nem dolgozott, csak kapott valamit
  (üzemorvos, tüdőszűrés) - az is kifizetés, tehát átjön.
- **A "ZÁRÁS" sorok egy IDŐSZAK kifizetését összegzik**, nem munkanapok - ezért
  nem jönnek át, különben a napi soraikkal együtt duplán számítanának. A
  feliratot jellemzően csak az első ember oszlopába írják be, ezért ezeket
  SORSZINTEN kell felismerni. Az importáló ki is listázza őket, hogy látszódjon,
  mi maradt ki és miért. *(Ellenőrizve: mind a 7 dolgozónál a napi sorok összege
  pontosan kiadja a zárás-sorát, tehát semmi nem vész el.)*

A csupa **nullás** nap is átjön: az "aznap nyitva voltunk és nem volt bevétel"
állítás információ, a hiányzó zárástól különbözik. A táblázatban előre
kirajzolt, teljesen üres évi sorokból viszont nem lesz bejegyzés.

**Idempotens**: kétszer lefuttatva sem duplikál (a nap a dátummal, a kiadás a
forrás+kedvezményezett+dátum+megnevezés+bruttó ötösével, a munkaóra a
dolgozó+dátum párral azonosít). A már felvitt adatot **nem írja felül** - az
importálás után a felületen javítanak, és egy újrafuttatás nem teheti tönkre
azt a munkát. Aki mégis a táblázatot tekinti igazságnak egy körre:
`--felulir` (csak a napi sorokra).

Az oszlopokat a **fejlécből** keresi ki, nem sorszám szerint: a táblázatba
idővel beszúrnak egy oszlopot, és egy elcsúszott indextől az összeg némán
rossz mezőbe kerülne.

## Hozzáférés

A `/krumpello` jogosultsági oldal megjelenik a Beállításokban
(`lib/nav.ts` `KULON_JOGOSULTSAGOK`), így egyénenként adható meg, ki lássa
egyáltalán a kapcsolót. Szándékosan **nem** a Pénzügyek joga: aki a produkciós
pénzügyeket viszi, nem feltétlenül tartozik rá a bolt kasszája - és fordítva.

**Az alapértelmezés a rendszer szokásos szabályát követi** (lásd
[02-auth-jogosultsag.md](02-auth-jogosultsag.md)): akinek admin nem állított be
oldal-korlátozást, az mindent lát, tehát a Krumpellót is. Aki korlátozva van,
annak a `/krumpello` kulcsot külön meg kell adni. Ha azt akarod, hogy *csak*
kijelölt emberek lássák, azoknak kell page_permissions-t adni, akiknek nem
szabad látniuk.

A kapcsoló elrejtése (`components/KrumpelloKapcsolo.tsx`) önmagában sosem
védelem: a middleware és a backend minden végponton külön is ellenőriz.

## Felület

Saját arculat: sötét éjkék + narancs (`app/krumpello-theme.css`,
`.krumpello-root`). Ez nem díszítés - **két kassza van egy rendszerben**: ha
ugyanúgy nézne ki, egy fáradt pillanatban bárki a rossz helyre vezetne be egy
tételt.

Műszakilag viszont nem új design-rendszer: ugyanazokat a tokeneket írja felül,
amiket a HYPE OS használ, ezért minden meglévő komponens változtatás nélkül
működik. A világos/sötét kapcsoló nem hat rá: a Krumpello mindig sötét, mert
ez a **márkája**, nem beállítás.

| Oldal | Mi van rajta |
|---|---|
| `/krumpello` | Összesítő: extra egyenleg elöl, majd bevétel/kiadás/egyenlegek/munkabér |
| `/krumpello/bevetel` | Napi kassza-zárások, felvitel és javítás |
| `/krumpello/kiadas` | Kiadások a három forrás szerint bontva |
| `/krumpello/munkaber` | Emberenkénti összesítés + naponkénti napló |

Az időszak-szűrő **URL-ben** él (`?tol=&ig=`): így egy nézet linkelhető, a
frissítés nem dobja vissza, és a szerver is látja - nem kell a böngészőben
újraszűrni azt, amit az adatbázis egyszer már kiszámolt.
