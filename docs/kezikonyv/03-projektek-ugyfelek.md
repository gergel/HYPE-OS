# 03 - Projektek és ügyfelek

Ez a rendszer gerince: minden más modul (papír, pénz, utómunka, portál) egy
projekthez vagy egy ügyfélhez kapcsolódik.

## Fogalmak

**Project Code** - a keret, amiben a munkák futnak: azonosítóval ellátott
munkacsomag, jellemzően egy ügyfélhez kötve (de ügyfél nélkül is felvehető -
lásd lentebb). Több projekt tartozhat alá.
API: `/api/v1/project-codes`, oldal: `/projektek/project-kodok`,
modell: `models/project_code.py`.

A listája nem csak azonosítókat sorol: a kód mellett ott a projekt NEVE (ez
váltotta le az ügyfél oszlopát - a kódról az ügyfél amúgy is kiderül az
adatlapon, a munkát viszont a neve azonosítja), a helyszín, a **dátum
megjegyzés** ("2 nap", "csúszik") és a jobb oldalon **bevétel, kiadás, profit** -
a puszta kódról ránézésre senki nem tudja, melyik munkáról van szó, és hogy
kijött-e.

A sorrend alapból a **legnagyobb kódtól a legkisebb felé** megy: a friss munkák
kapják a nagyobb sorszámot, és azokon dolgozik mindenki. A sorszámokat számként
hasonlítjuk (`localeCompare … {numeric: true}`), tehát a `HYPE26-9` a
`HYPE26-10` alatt van, nem fölötte. A fejlécre kattintva bármelyik oszlop
szerint átrendezhető.

### Új projektkód felvétele

A felvevő űrlap három mezőt kér, és mindössze egy kötelező:

- **Projektkód** - előre kitöltve a **következő szabad kóddal**
  (`HYPE26-0042`), nem csak az évszámos előtaggal: enélkül a felvevőnek végig
  kellett görgetnie a listát, hogy megnézze, hol tartunk. Az évszám a mai
  napból jön (2027-től magától `HYPE27-`), a sorszám pedig a meglévő kódok
  közül a legnagyobb + 1 - csak a tisztán számos sorszámokat nézve, mert a
  kézzel kitalált kódok (`HYPE26-KERET1`) nem a sorozat részei
  (`lib/projektkod.ts`).

  Az ajánlás JAVASLAT, nem kényszer: a mező szabadon átírható (régebbi évre
  szóló vagy más rendszerű kód is felvehető), és a kód az adatbázisban úgyis
  egyedi - az ütközést a mentés akkor is elkapja, ha közben más is felvett
  egyet.
- **Ügyfél** - nem kötelező. A kódot sokszor előbb foglalják le, mint ahogy
  eldőlne, kinek a munkája; ilyenkor korábban valaki beírt egy tetszőleges
  ügyfelet, amit utána senki nem javított ki. Ami az ügyfélre épül, kezeli a
  hiányát: ügyfél nélkül nincs keretszerződés-fedés, tehát eseti szerződés kell.
- **Dátum megjegyzés** - SZÖVEG, nem naptári dátum ("2026. május", "két
  hétvégén"). Egy projektkód alatt több forgatás fut, a pontos napokat úgyis a
  projektek hordozzák.

A lista **évekre bontva** nyílik: 2025 / 2026 / Összes
(`components/ProjektkodEvValto.tsx`). Az évet a kód ELŐTAGJA adja
(`HYPE25-…`, `HYPE26-…`), nem a `datum` mező - az sokszor üres vagy a
szerződés keltezése, a kód viszont mindig az adott év sorozatából jön. A nézet
a címben van (`?ev=2025`), tehát megosztható és könyvjelzőzhető, a fejlécben
látszó darabszám pedig a ténylegesen mutatott sorokat számolja. Az "Összes"
azért kell, mert a régebbi (HYPE24-es) és a más kódrendszerű munkák egyik
évhez sem tartoznak - nélküle láthatatlanok lennének.

A **Papírozás** oszlop három jelzőt mutat, mindig ugyanabban a sorrendben:
szerződés → TIG → kifizetés (`papir_kell`, `szerzodes_kesz`, `tig_kesz`,
`bevetel_kifizetve` a `models/project_code.py`-ban). A sorrend maga az
információ, ezért a jelzők akkor is kint vannak, ha az adott lépés még nem
aktuális - így egy pillantásból látszik, hol áll a munka. Ahol nincs mit
papírozni (nem szerződéses munka, vagy papír nélkül elszámolt), ott egyetlen
jelző áll: a hiányzó papír nem elmaradás. A "kész-e egy papír" szabálya közös
a papír-oldalakéval (`LEZART_ALLAPOTOK`), hogy a lista ne mondhasson mást,
mint az adatlap.

A negyedik nézet, a **Teendők**, nem évre szűr, hanem FÁZIS-OSZLOPOKRA bontja
a projektkódokat - ugyanaz a tábla, mint az Utókövetésen
([08-utomunka-utokovetes.md](08-utomunka-utokovetes.md)), csak a másik
oldalról: ott a mi fizetéseink útját követi, itt a megrendelő felé menő
papírokét és a beérkező pénzét. Négy oszlop: *nincs még szerződés* → *már csak
a TIG kell* → *nincs kifizetve* → *kész*
(`lib/projektkodFazis.ts`, `components/ProjektkodTeendoTabla.tsx`).

Egy projektkód PONTOSAN EGY oszlopban áll, a legkorábbi hiányzó lépésnél: így
balról jobbra haladva az látszik, mi a következő teendő rajta, és nem kell
ugyanazt a sort több helyen átfutni. Ahol nincs mit papírozni, ott a
papír-lépések kimaradnak - a pénz viszont ott is megérkezhet. A "nincs
kifizetve" ott is igaz, ahol egyáltalán nincs bevétel felvezetve: bevétel-sor
nélkül nem mondhatjuk, hogy megjött a pénz. A kártyán ott a bevétel és a
profit is, mert a teendő súlyát ez adja: egy hárommilliós kintlévőség máshogy
sürgős, mint egy harmincezres.

A dátum oszlopában szándékosan nem a naptári dátum áll: egy projektkód alatt
több forgatás fut, egyetlen dátum úgysem mondaná meg, mikor volt a munka - a
megjegyzés viszont igen. A pontos dátum az adatlapon van.

Az összes SAJÁT mező helyben szerkeszthető a listán (projektkód, projekt neve,
helyszín, dátum megjegyzés, státusz) - `EditableTableCell` /
`EditableStatusBadge`, ami a rekord PATCH végpontját hívja. A három pénz-oszlop
nem: az `bevetel` és az `osszes_koltseg` a backend SZÁMÍTÁSA
(`models/project_code.py`), a "kiadás" itt a TELJES költség - külsős stáb,
vágás, belsős munkanapok és egyéb kiadás együtt. A négy rész az adatlapon
külön-külön is látszik ("Mibe került"), a listán az egérrel rámutatva (lásd
[07-penzugyek.md](07-penzugyek.md#a-projekt-önköltsége--a-kiadás-lista)).
Ezeket a listán átírni annyit tenne, hogy a szám mást mond, mint a mögötte álló
tételek; javítani a bevétel-/kiadás-soroknál kell.

### A projektkód ADATLAPJA: mibe került és hol tart a papír

Az adatlap szándékosan KEVÉS dolgot mutat, mert két kérdésre kell válaszolnia:
*mennyi maradt belőle* és *mi van még hátra*. A generikus mezőrács (a ~140
Notion-mező) itt nem szerepel - az adat megvan, csak nem ezen az oldalon.

Felülről lefelé:

1. **Fejléc**: a kód, a projekt neve, a dátum megjegyzés.
2. **Bevétel / Összes költség / Becsült profit**, alatta a költség négy része
   (`components/KoltsegBontas.tsx`).
3. **Megrendelői papírozás három lépésben**: szerződés → TIG → **számla**.
   Ugyanaz a sorrend, mint az alvállalkozói oldalon, és a sorrend maga az
   információ: a számla addig nem nyílik meg, amíg az első kettő nincs meg
   (keretszerződés alatt a szerződés-lépés magától teljesül). Ha korábbról már
   van feltöltött számla, azt sorrendtől függetlenül mutatjuk - a lépések nem
   tehetnek láthatatlanná meglévő adatot.
4. **Tételes bontás** (`GET /project-codes/{id}/bontas`,
   `services/projektkod_bontas.py`, `components/projektkod/ProjektkodBontasTablak.tsx`):

   | Tábla | Mit mutat |
   |---|---|
   | Forgatások | forgatásonként külsős stáb + belsős napidíj + vágás, és a soruk összege |
   | Utómunka | anyagonként ki vágta, **mennyi ideig** (a munkaidő-sorokból) és mennyibe került |
   | Egyéb projekt kiadások | minden kiadás-sor, besorolással (Külsős / Egyéb) |

   A számok UGYANONNAN jönnek, mint a fejléc összegei, tehát a tételek összege
   a fejléc-számot adja ki. Két dolog magyarázatra szorul, ezért ki is írjuk:
   a **TIG-ekből keletkezett** kiadás-sorok nincsenek a kiadás-táblában (azok a
   forgatások "Külsős stáb" oszlopában vannak, ugyanaz a pénz lenne kétszer), és
   a **több napra szóló TIG** összege a napok közt fel van osztva.

#### A vágás ára a MÉRT munkaidőből jön

A projekt vágási költsége a munkaidő-sorokból (`Timesheet`) áll össze - pontosan
az a szám, ami az anyag oldalán a "Munkaidő-elszámolások" tábla alján is
látszik. A szabály egy helyen él:
`services/deliverable_actions.anyag_osszesitok()`.

A `Deliverable.koltseg` mező SZÁNDÉKOSAN nem forrás: azt semmi nem frissíti a
mérésekből, tehát egy utólag rögzített (vagy törölt) munkaidő-sor után elavult
szám marad benne - és a projekt költsége azzal hazudna.

Egyetlen kivétel: ha egy anyagon **egyáltalán nincs mérés** (régi, Notionból
hozott sorok), marad a rögzített mező. Ott az az egyetlen ismert összeg, és a
nulla rosszabb hazugság lenne, mint egy régi szám
(`deliverable_actions.anyag_koltsege`).

A még FUTÓ mérés nem számít bele: annak nincs végleges ideje. A felület a futó
mérést másodpercenként külön mutatja, a rögzített költségbe csak a leállított
sorok kerülnek.

A "nem kell ide papír" jelölés (nem szerződéses munka, vagy máshol elszámolt)
összecsukva, a papírozás alatt maradt: a legtöbb munkánál nincs vele dolgunk,
de valahonnan állíthatónak kell lennie - enélkül az ilyen kódok örökre a
teendők közt maradnának.

### A projektkód KÖTÉSE: mi tartozik egy kód alá

A projektkód két helyen élt: **szövegként** a projekten és a vágáson
(`projektkod_szoveg` - a Notionból és a naptárból így érkezett), és önálló
rekordként a Project Code táblában. Amíg a kettő nem volt összekötve, a
projektkód adatlapja nem tudta megmondani, hány forgatás és hány vágás tartozik
alá - pedig épp ez a nyomon követhetőség a lényege.

A szabály egy helyen él: `services/projektkod_kotes.py`. Ugyanaz fut a
mindennapi mentéseknél és a visszamenőleges összekötésnél (migráció:
`b5e1a94c7d20`), ezért a kettő nem csúszhat el egymástól.

- **Összehasonlítás** (`kulcs`): kis/nagybetűtől és szóköztől független. Ennél
  szigorúbb szándékosan nem: a megszokottól eltérő alak is lehet valódi kód.
- **Valódi kód** (`valodi`): bármi, ami nem üres és nem import-**gyűjtő**. Két
  gyűjtő volt (`NAPTAR-IMPORT`, `ISMERETLEN-NOTION-IMPORT`) - kényszerből, mert
  a projekt kódja NOT NULL volt, és a kód nélkül érkező naptár/Notion soroknak
  kellett valami. A kód mostantól **üres is lehet**, így a gyűjtőkre nincs
  szükség: amihez nincs valódi kód, az maradjon kötetlen, és akkor kerüljön a
  helyére, amikor tényleg megkapja a kódját. Egy gyűjtőbe söpört projekt
  ugyanis úgy néz ki, mintha elintéztük volna - pedig épp ellenkezőleg.
- A migráció be is köt mindent, leold mindent a gyűjtőkről, és az így üressé
  vált gyűjtő kódot ki is veszi a projektkódok közül (amelyikre még mutat
  bármi - kiadás, bevétel, papír -, az marad: azt előbb rendezni kell).

Hol kötelező a kód, és hol nem:

| Hol | Kötelező? |
|---|---|
| **Vágás** (utómunka) létrehozása | IGEN. Projekthez felvezetve nem kell beírni: a projekt kódját örökli (`routes/postproduction.py`). |
| **Diszpó kiküldése** | IGEN, de szabad formátumban - nem kell a megszokott alakot követnie (`services/dispo._require_projektkod`). |
| **Projekt** felvétele | Nem: a naptárból kód nélkül érkezik. Ha megadják (akár utólag), rögtön a helyére kerül. |

**Projekt** - egy konkrét forgatás/munka. Ehhez tartozik a stáb, a technika, a
diszpó, a papírok, a költségek és a leszállított anyag.
API: `/api/v1/projects`, oldal: `/projektek`, modell: `models/project.py`,
route: `routes/projects.py`, üzleti logika: `services/project_actions.py`.

A `/projektek` oldal alapértelmezett nézete a **naptár**
(`components/ProjektekContent.tsx`): a projekt itt egy forgatási NAP, és a napi
munka (mi van ma, mi jön holnap) naptárban olvasható, nem egy több száz soros
táblázatban. A táblázat egy kattintással elérhető marad, a szűrőmező pedig
mindkét nézetre érvényes (szülő szinten fut, nem a táblázatban).

### Gyártás komment: a gyártásvezető jegyzettömbje

A projekt adatlapján saját dobozt kapott (`components/GyartasKomment.tsx`), nem
a mezőrácsban él - ott egysoros beviteli mező lenne belőle, ami épp azt venné
el, amiért ez a mező van. Amit tud:

- **több sor**: a bekezdések és a felsorolások úgy maradnak, ahogy beírták;
- **kattintható linkek**: a szövegbe illesztett címeket (a `www.`-vel kezdődőket
  is) megnyithatóvá tesszük. A szöveget darabokra vágva rendereljük, nem
  HTML-ként - így a beírt tartalom soha nem tud jelölésként viselkedni. A mondat
  végi írásjel nem kerül a linkbe;
- **fájlok**: a kommenthez tartozó forgatókönyv, helyszínrajz, brief ugyanide
  tölthető fel. Külön (`gyartas`) kategóriával, hogy ne keveredjen a **diszpó
  levél mellékleteivel** - azok külön dobozban vannak, és tényleg kimennek a
  stábnak.

A szerkesztés UGYANÚGY működik, mint a brief mezőnél: rá kell kattintani a
szövegre (üresen a szaggatott keretes felhívásra), és már lehet írni - az Enter
új sort kezd, a mentés az elkattintás, az Esc elvet. Korábban itt egy külön
"Szerkesztés", majd egy "Mentés" gomb kellett: két kattintás ugyanarra, két
különböző szokással ugyanabban a nézetben.

### Hosszú szöveg mezők (brief, diszpó szövege, technika lista)

Ezek a mezők a mezőrácsban élnek, de MINDIG több sorosan nyílnak meg
(textarea), akkor is, ha épp üresek: az Enter új sort kezd, a mentés az
elkattintás. Korábban a felület az ÉRTÉKBŐL találgatta, mi hosszú szöveg
(sortörés vagy 120 karakter fölött), így egy üres brief egysoros mező volt,
amiben az Enter mentett - vagyis pont az első bekezdést nem lehetett megírni.
Most a séma dönt: a `Text` oszlopok `multiline` típussal jönnek vissza
(`services/entity_registry._szoveg_tipus` → `lib/detail.tsx`). Megjelenítéskor a
sortörések megmaradnak, a beírt linkek kattinthatók.

### Csatolni való a diszpó levélhez: mérethatár a feltöltésnél

A "Csatolni való (a diszpó levélhez)" doboz fájljai a diszpó kiküldésekor a
levél mellékletei lesznek, ezért **együtt** legfeljebb 15 MB-osak lehetnek
(Gmail 25 MB + base64 ~33% + a diszpó PDF; `attachments.DISZPO_MAX_BAJT`, amit a
küldés oldali ellenőrzés is használ). A határt a **feltöltésnél** kérjük számon,
nem csak küldéskor: enélkül a fájl szépen felmegy, és csak napokkal később, a
kiküldéskor derül ki, hogy nem fér a levélbe - amikor már nincs idő intézkedni.

Ami nem fér bele, annak a helye a Drive, a linkjéé pedig a **brief**: a brief
szövege a diszpóval generált PDF-be is bekerül (`services/dispo.py`), tehát a
link így is eljut a stábhoz. A hibaüzenet is ezt mondja, mind a böngészőben
(előre, feltöltés nélkül), mind a backenden.

**Ügyfél és kontakt** - a megrendelő cég és a nála dolgozó emberek. A kontaktok
adata a `/contacts` CRUD-é, de kaptak önálló listát is
(`/megrendeloi-kontaktok`), hogy rá lehessen keresni valakire anélkül, hogy
tudnánk, melyik cégnél van. Jogosultság szempontjából mindkettő `/ugyfelek`.
API: `/api/v1/clients`, `/api/v1/contacts`, `/api/v1/megrendeloi-kontaktok`.

**Kampány** - több projektet átfogó marketing-kampány.
API: `/api/v1/campaigns`, oldal: `/kampanyok`.

## Feldarabolás: egy nap leválasztása

Egy több napos forgatásból ki lehet emelni EGY napot önálló projektté
(`services/project_actions.create_feldarabolas`): a leválasztott nap átveszi a
nevet, a projektkódot, a stábot és a **számlázási felállást** is, és megjegyzi,
honnan származik (`feldarabolas_szulo_id`).

A lényeg, amit könnyű elrontani: a leválasztott napot **ki kell venni az
eredetiből**. Ha az eredeti tartománya érintetlen marad, ugyanarra a napra az
"egész" forgatás is ott áll a diszponálandók közt a leválasztott nap mellett -
pont az, amit a darabolásnak meg kellene szüntetnie. Három eset van:

| A leválasztott nap | Az eredetivel mi történik |
|---|---|
| az ELSŐ nap | a következő naptól él tovább |
| a tartományon belül | az előtte lévő napig tart |
| a záró nap UTÁN | érintetlen - ez a "vegyünk fel még egy napot" eset |

Egynapos forgatást a SAJÁT napjára nem lehet darabolni: abból nem két forgatás
lenne, hanem ugyanaz kétszer - a végpont ilyenkor érthető hibaüzenettel
elutasít.

A felületek emellett védekeznek is: a Diszpó lista és a dashboard teendői nem
kérnek diszpót a szülőre, ha ugyanarra a napra van leválasztott gyereke - a
régi, darabolás előtti adatok miatt.

A Diszpó LISTÁN a szülő ilyenkor nem tűnik el, hanem **"Már feldarabolva"**
jelölést kap ("a diszpó a leválasztott naphoz megy, ide nem kell"), és egyik
számlálóba sem számít bele. A korábbi néma kihagyás félrevezető volt: aki
kereste a forgatást, azt hitte, elveszett. A naptár nézetben viszont továbbra
sem jelenik meg - ott a nap egy csempe, és az "egész" csak ugyanannak a
forgatásnak a duplikátuma lenne.

## Stáb a projekten

A projekt–munkatárs kapcsolat **nem** egyszerű many-to-many, hanem saját
társítási objektum (`project_crew`), mert a kapcsolatnak magának is van adata -
mindenekelőtt az, hogy **ki számláz** az adott ember munkájáért:

- maga a munkatárs (saját vállalkozóként), vagy
- egy **számlázó cég** (`Vallalkozas`), aki embereket küld a forgatásra és ő
  állítja ki a számlát.

Ez határozza meg, milyen szerződés és milyen TIG kell - lásd
[06-papirozas.md](06-papirozas.md) és `services/szamlazo.py`.

## Számlázók a projekten

`/api/v1/projekt-szamlazok` (`routes/project_szamlazok.py`,
`models/project_szamlazo.py`) - projektenként tartja nyilván, ki a számlázó fél.
Frontend: `components/SzamlazoFelSzerkeszto.tsx`, `SearchableIdPicker.tsx`.

Ugyanezen a (projekt, ember) soron él két másik, egymástól független beállítás
is: a "projekt kiadásként elszámolva" jelölő (lásd
[06-papirozas.md](06-papirozas.md)) és a **megbeszélt díj**. Egyik visszavonása
sem törli a másikat; ha a sor már semmit nem hordoz, magától eltűnik.

### Megbeszélt díj: mennyiért vállalja azt a napot

A **stábtag felvételekor** (a diszpó írásakor) felugrik a kérdés, mennyiért
vállalja az illető azt a forgatást - plusz egy magyarázat mező (mi van benne:
saját kamerával? utazás nélkül?). Belsősnél nem jön elő a kérdés: ők havi
bérezésűek, a backend is elutasítja náluk. A kérdés **kihagyható** - nem minden
stábtaggal beszélnek le előre fix díjat -, és utólag is megadható vagy javítható
a "Ki számláz kiért" táblázatban.

Miért ott kérdezzük? Mert ott dől el: aki beosztja az embert, az beszéli meg
vele a díjat. A szerződést és a TIG-et viszont hetekkel később, **más ember**
adminisztrálja, akinek pont ez az összeg kell a papírra - enélkül vagy
visszakeresi valaki egy üzenetváltásból, vagy tippel.

Ezért a díj **előtölti mindkét papír piszkozatát**
(`services/megbeszelt_dij.py`):

| Papír | Fejösszeg | Tételek |
|---|---|---|
| Eseti szerződés | a rá tartozó emberek díjainak összege | fejenként a saját díja |
| TIG | a szerződésről örökölt összeg, annak hiányában a díjakból | ugyanígy |

A TIG-nél a "szerződés hiányában" eset nem ritka kivétel: a **keretszerződéses**
feleknél nincs eseti szerződés, tehát ott csak ez az adat mondja meg, mennyiről
szól a papír. Az előtöltés csak KIINDULÁS - a piszkozatban bármi átírható, és a
mentett papír utána a saját összegével él tovább.

A megbeszélt díj **megállapodás, nem kifizetés**: a projekt költségébe semmi nem
kerül belőle (az továbbra is a TIG-eken és a Kiadás sorokon áll, lásd
[07-penzugyek.md](07-penzugyek.md)).

## Projekt-párosítás

`services/project_matching.py` - beérkező adatot (naptár-esemény, Notion-import,
levél) párosít meglévő projekthez. Ha valami "magától" a rossz projektre kerül,
itt kezdd a keresést.

## Feladatok és időzóna

- Feladatok: `/api/v1/tasks`, oldal: `/feladatok`.
- Minden dátumformázás magyar konvenció szerint megy:
  backend `services/hu_datum.py`, `services/hu_number_words.py` (számok betűvel a
  szerződésekhez), `services/hu_szoveg.py`; frontend `lib/huDate.ts`, `lib/ido.ts`,
  `lib/penz.ts`. Ne írj saját formázót, ezeket használd.

## Részletnézet

A projekt (és minden más entitás) részletnézete adatvezérelt: a fülek, a mezők és
a sorrendjük adminból állítható - lásd
[01-architektura.md](01-architektura.md#a-rekord-részletnézet-motorja).
Frontend: `components/ProjectDetailContent.tsx`, `ProjectDetailModal.tsx`,
`RecordDetailModal.tsx`, `RelatedTable.tsx`.

### A PROJEKTKÓD is felugró ablakban nyílik

A projektkódok listájáról, a Teendők nézet kártyáiról és a megrendelői
papír-oldalakról a projektkód **felugró ablakban** nyílik meg, nem teljes
oldalként (`DataTable openInModal` → `RecordDetailModal`). Ugyanaz a nézet
jelenik meg, minden művelettel: a tartalom az `/embed/projektek/project-kodok/[id]`
útvonalról jön, ami szó szerint ugyanazt a komponenst exportálja - nem egy
kliens oldalon újraépített, előbb-utóbb elcsúszó változat.

Miért? Mert ezeken a felületeken ritkán EGY kódot keresünk: végigmegyünk többön
(mi hiányzik róla, mennyi a profitja, lejárt-e a határideje), és minden
megnyitás után vissza kellene navigálni - elveszítve a szűrést, a keresést és a
görgetést. Az ablak fejlécében ott a **"Megnyitás új oldalon"**, ha valaki
mégis a teljes oldalt akarja, és bezáráskor a mögöttes lista frissül, hogy az
ablakban végzett szerkesztés ott is látszódjon.
