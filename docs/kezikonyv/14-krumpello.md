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

### Számla feltöltése - lehetőség, nem kötelezettség

Minden kiadás-tételhez és minden napi kassza-záráshoz **feltölthető számla,
blokk vagy napi jelentés** (Kiadás és Bevétel oldal, "Számla / blokk" és
"Számla / bizonylat" oszlop). A generikus csatolmány-rendszert használja
(`services/attachments.py`, entitás-kulcsok: `krumpelloKiadas` és
`krumpelloNap`), a `/krumpello` oldal jogosultságával - a bolt bizonylataihoz
ne kelljen hozzáférés a cég teljes pénzügyéhez.

**Sehol nem kötelező.** Az "extra" tételnek épp az a definíciója, hogy nincs
mögötte papír; a napi zárás pedig a számoktól kerek, a bizonylat csak
alátámasztja. A feltöltés attól még kell: a másik két forrásnál általában VAN
blokk vagy számla, és eddig nem volt hova tenni - a fájl a könyvelő mappájában
kötött ki, a tételtől külön.

A lista **egyetlen lekérdezéssel** hozza a fájlokat az összes sorhoz
(`_csatolmanyok`), nem soronként: egy hónapnyi kassza megnyitása különben
több tucat kérést indítana olyan sorokhoz is, ahol nincs is fájl. A
`PapirFeltoltes` komponens ezért kap `kezdeti` listát - feltöltés vagy törlés
után onnantól magától frissít.

A tétel törlése a **fájljait is elviszi** (a tárhelyről is): különben a
feltöltött blokk örökre ott maradna egy már nem létező tételre hivatkozva -
senki nem látná, és senki nem tudná törölni.

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

## Bejelentés: mennyi megy utalással, mennyi készpénzben

Ugyanaz az ember év közben többféleképpen dolgozik: nyáron **EFO**-val, ősztől
**határozott idejű munkaszerződéssel**, közben pedig van nap, amire egyáltalán
**nincs bejelentve**. Ez nem adminisztratív címke, hanem a kifizetés módját
dönti el:

> **készpénz = óra × órabér − bejelentett napi bér**

A bejelentett napi bér **utalással** megy (az szerepel a bérszámfejtésben), a
fölötte lévő rész **készpénzben**. Bejelentés nélkül az egész nap készpénz.

### Foglalkoztatási időszak

A bejelentés az **időszakhoz** tartozik (`KrumpelloIdoszak`: dolgozó, mettől
meddig, milyen bejelentéssel, mennyi a napi bér), nem az emberhez - egy közös
mező a dolgozón visszamenőleg átírná a korábbi hetek elszámolását. A nyitott
vég (`veg IS NULL`) azt jelenti: "azóta is tart".

A napokat **nem idegen kulcs** köti az időszakhoz, hanem a **dátum**: a
(dolgozó, kezdet..vég) intervallumba eső munkaóra-sorok tartoznak oda. Így egy
utólag felvitt nap magától a helyére kerül, és nem maradhat ki az
elszámolásból, mert elfelejtették hozzákötni. Cserébe egy emberre az időszakok
**nem fedhetik egymást** - ezt a mentés ellenőrzi, mert két egymást fedő
időszakból nem lehetne eldönteni, melyik szerint kell elszámolni azt a napot.

A napon **felülírható** a bejelentés és a napi bér (`bejelentes`,
`bejelentett_napi_ber`): a valóságban van kivétel - egy beugrás a szerződéses
időszak közepén, amire aznap nem jelentették be. A felület jelzi, ha egy érték
napra van megadva, nem örökölt.

Az időszak törlése a **munkanapokat nem viszi el**: csak a bejelentés esik le
róluk (visszaesnek "nem volt bejelentve"-re), a ledolgozott óra és a bér
megmarad.

### Elszámolás

Az időszak egyben az **elszámolás egysége**: a Munkabér oldalon kijelölhető
egy vagy több időszak, és egyben elszámolható. A visszajelzés a két szám,
amivel a felhasználó a bankhoz és a kasszához megy: **mennyit kell utalni** és
**mennyit készpénzben odaadni**.

Több időszak azért kell egyszerre, mert ha valakinél egy EFO-s és egy
szerződéses szakasz is nyitva maradt, egyszerre rendezik őket - és egy összeget
adnak oda, nem kettőt.

**Rövid nap:** ha a bejelentett napi bér többet fizet, mint amennyi aznap járt
(4 óra × 2500 = 10 000, de a bejelentett napi bér 15 000), a nap készpénze
**negatív** - az utalás előre fizetett. Ezt nem vágjuk nullára, mert az
időszak szintjén kiegyenlítődik, épp úgy, ahogy a valóságban; a felület
viszont kiemeli, hogy látszódjon.

### Sor végösszege a naplóban

A naponkénti napló minden sorát egy **Összesen** oszlop zárja: amit az az ember
azon a napon összesen keresett (**bér + borravaló**), alatta pedig hogy ebből
**mennyit kap készpénzben** (készpénz + borravaló).

A borravaló azért van benne mindkettőben, mert az is a dolgozóé és készpénzben
megy - a kezébe adott összeg ez, nem a puszta bér. Az összesítés soronként van,
nem naponként: a kifizetés emberenként történik, tehát az a szám kell, amit
ennek az egy embernek ezen az egy napon oda kell adni.

## Mit fizettünk már ki

A munkanap-soron van egy `kifizetve` jelölés (+ `kifizetes_datuma`), és ebből
jön a Munkabér oldal két oszlopa: **Kifizetve** és **Még jár**. Az utóbbi a
gyakorlatban használt szám - ezt kell elutalni -, ezért a felső összesítő
sorban és az Áttekintésen is szerepel, figyelmeztető színnel, amíg nem nulla.

**Miért a napon van a jelölés, és nem egy külön "kifizetés" rekordon?** Mert a
kérdés, amire válaszolni kell, mindig egy napra vonatkozik: "ez a nap benne
volt már egy kifizetésben?" Kifizetés-rekordokból ezt csak összeadogatással
lehetne kitalálni, és egy utólag felvitt nap (amit egy már kifizetett
időszakba írtak be) némán beleolvadna egy korábbi összegbe.

A kifizetés viszont a gyakorlatban **időszakonként** történik (lásd a
kassza-táblázat "ZÁRÁS" sorait), ezért két út van rá:

| Hol | Mit csinál |
|---|---|
| A napló sorában | Egy nap ki/be kapcsolása. A gomb a MŰVELETET mondja ("Fizetve"), nem az állapotot - egy "Még jár" feliratú gombról nem derülne ki, mit csinál a kattintás. Nincs megerősítés: a téves kattintás ára egy újabb kattintás. |
| A nap szerkesztőjében | Ugyanez, de a kifizetés DÁTUMÁVAL együtt - a jelölés gyakran később készül el, mint maga az utalás. |
| Az emberenkénti táblában | `POST /munkaorak/kifizetes`: az adott ember **szűrt időszakának** összes jelöletlen napja egyben. |

A tömeges jelölés **csak a még jelöletlen napokat nyúlja** (visszavonásnál csak
a jelölteket): így egy tágabb intervallum megadása nem írja felül egy korábbi,
már elszámolt időszak kifizetési dátumát.

A **borravaló nincs a hátralékban**: az a vendégektől jön, jellemzően aznap a
kasszából kapják meg, nem a bérrel együtt utaljuk.

A betöltött történeti adat mind **jelöletlenül** indul. Ez szándékos: a
táblázatból nem derül ki, mit utaltak el ténylegesen - a "ZÁRÁS" sorok
összegeznek, de nem mondják meg, hogy meg is történt-e. A hamis "kifizetve"
rosszabb, mint a jelöletlen: az egyik miatt elmarad egy utalás, a másik miatt
csak egyszer rá kell nézni.

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

**A felugró ablakokra is vonatkozik**, és ehhez két dolog kell. A megerősítő
ablak és a toast a providerek saját JSX-ében renderelődik, a tartalom
TESTVÉREKÉNT - ezért a `.krumpello-root` a providereken KÍVÜL van, nem csak a
tartalom körül. A `ModalReteg` viszont a `<body>` végére portálozik, tehát
abból a dobozból is kilép: neki a `<body>`-ra tett osztály viszi át az
arculatot (`components/krumpello/KrumpelloTemaTest.tsx`). Böngésző-natív
`confirm()`/`alert()` ezért nincs a Krumpellóban - azok a gép ablakai, nem
lehet őket a felület arculatába hozni.

| Oldal | Mi van rajta |
|---|---|
| `/krumpello` | Összesítő: extra egyenleg elöl, majd bevétel/kiadás/egyenlegek/munkabér |
| `/krumpello/bevetel` | Napi kassza-zárások, felvitel és javítás, bizonylat-feltöltés |
| `/krumpello/kiadas` | Kiadások a három forrás szerint bontva, számla-feltöltés |
| `/krumpello/munkaber` | Foglalkoztatási időszakok elszámolása + emberenkénti összesítés + naponkénti napló |

Az időszak-szűrő **URL-ben** él (`?tol=&ig=`): így egy nézet linkelhető, a
frissítés nem dobja vissza, és a szerver is látja - nem kell a böngészőben
újraszűrni azt, amit az adatbázis egyszer már kiszámolt.
