# 03 - Projektek és ügyfelek

Ez a rendszer gerince: minden más modul (papír, pénz, utómunka, portál) egy
projekthez vagy egy ügyfélhez kapcsolódik.

## Fogalmak

**Project Code** - a keret, amiben a munkák futnak: egy ügyfélhez tartozó,
azonosítóval ellátott munkacsomag. Több projekt tartozhat alá.
API: `/api/v1/project-codes`, oldal: `/projektek/project-kodok`,
modell: `models/project_code.py`.

A listája nem csak azonosítókat sorol: a kód alatt ott a projekt NEVE, mellette
a helyszín, a dátum alatt a dátum-megjegyzés, a jobb oldalon pedig **bevétel,
kiadás, profit** - a puszta kódról ránézésre senki nem tudja, melyik munkáról
van szó, és hogy kijött-e. A `bevetel` és az `osszes_koltseg` a backend
számítása (`models/project_code.py`); a "kiadás" itt a TELJES költség, tehát a
projektkiadások és az utómunka együtt - ugyanaz, amit az adatlap "Összes
költség (kiadások + utómunka)" néven mutat.

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
