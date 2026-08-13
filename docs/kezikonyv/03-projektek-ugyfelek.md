# 03 - Projektek és ügyfelek

Ez a rendszer gerince: minden más modul (papír, pénz, utómunka, portál) egy
projekthez vagy egy ügyfélhez kapcsolódik.

## Fogalmak

**Project Code** - a keret, amiben a munkák futnak: egy ügyfélhez tartozó,
azonosítóval ellátott munkacsomag. Több projekt tartozhat alá.
API: `/api/v1/project-codes`, oldal: `/projektek/project-kodok`,
modell: `models/project_code.py`.

A listája nem csak azonosítókat sorol: a kód mellett ott a projekt NEVE (ez
váltotta le az ügyfél oszlopát - a kódról az ügyfél amúgy is kiderül az
adatlapon, a munkát viszont a neve azonosítja), a helyszín, a **dátum
megjegyzés** ("2 nap", "csúszik") és a jobb oldalon **bevétel, kiadás, profit** -
a puszta kódról ránézésre senki nem tudja, melyik munkáról van szó, és hogy
kijött-e.

A lista **évekre bontva** nyílik: 2025 / 2026 / Összes
(`components/ProjektkodEvValto.tsx`). Az évet a kód ELŐTAGJA adja
(`HYPE25-…`, `HYPE26-…`), nem a `datum` mező - az sokszor üres vagy a
szerződés keltezése, a kód viszont mindig az adott év sorozatából jön. A nézet
a címben van (`?ev=2025`), tehát megosztható és könyvjelzőzhető, a fejlécben
látszó darabszám pedig a ténylegesen mutatott sorokat számolja. Az "Összes"
azért kell, mert a régebbi (HYPE24-es) és a más kódrendszerű munkák egyik
évhez sem tartoznak - nélküle láthatatlanok lennének.

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

A felületek emellett védekeznek is: a Diszpó lista és a dashboard teendői
kihagyják a szülőt, ha ugyanarra a napra van leválasztott gyereke - a régi,
darabolás előtti adatok miatt.

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
