# 07 - Pénzügyek

Oldal: `/penzugyek`. Route: `routes/finance.py`, modell: `models/finance.py`.

## Alapadatok

| Mi | API prefix |
|---|---|
| Kiadás | `/api/v1/expenses` |
| Bevétel | `/api/v1/revenues` |
| KP-forgalom | `/api/v1/kp-forgalom` |
| Összesítő | `/api/v1/finance` |

Mindhárom alaptábla a CRUD-generátorral készül, a `/penzugyek` jogosultsággal.
Az összesítő végpont köti össze őket a Project Code-okkal és a papírokkal: a
külsős és belsős TIG-ekhez tartozó **számlák** (`PerformanceCertificateInvoice`,
`InternalPerformanceCertificateInvoice`) is ide futnak be, tehát a kifizetendő
tételek nem külön világ - amit a papírozás oldalon rögzítenek, az itt látszik.

Csatolmányok és számlaképek: `services/document_storage.py`; a kiadások mellé
feltöltött fájlok tömegesen letölthetők (ZIP-be csomagolva, `routes/finance.py`).

### A kifizetés és a Kiadás sor két külön dolog

Egy TIG-et kifizetettként jelölni alapból **Kiadás sort is létrehoz** - a kettő
általában együtt jár. De nem mindig: van olyan kifizetés, ami **máshol van
elszámolva** (a bankban vagy a könyvelőnél már szerepel), és ott egy itteni
Kiadás sor csak megkétszerezné az összeget a pénzügyi összesítőkben. Ezért a
"Kifizetve jelölés" ablakában kikapcsolható, hogy bekerüljön-e a Kiadásokba
(`schemas/finance.KifizetesIn` `kiadasba_kerul`; a mező elhagyása = bekerül,
tehát a régi hívások viselkedése változatlan). A papír állapota így is
"kifizetve" lesz, tehát nem marad teendőként a havi listán.

**Visszafelé is jár az út:** egy Kiadás sor akkor is törölhető, ha TIG (vagy
havi tétel, KP-forgalom) hivatkozik rá. A törlés leoldja a hivatkozásokat, és az
érintett TIG-et visszadobja "nincs kifizetve" állapotba - a kapcsolódó rekordok
maguk megmaradnak, csak újra teendővé válnak
(`services/kiadas_kapcsolatok.py`). Ez szándékosan ilyen irányú: a "ki van
fizetve" állítás bizonyítéka éppen az a Kiadás sor volt, tehát ha az nincs
többé, a papír állapota sem maradhat. Enélkül egy tévesen felvezetett kifizetés
visszavonhatatlan volt: a kiadást a TIG hivatkozása védte, a TIG-et pedig a
kifizetettsége.

Frontend: `components/finance/`, `RevenueInvoiceStatus.tsx`,
`TigInvoiceManager.tsx`, `TigAllapotSelect.tsx`.

## Számlázó cégek (Vállalkozások)

`/api/v1/vallalkozasok`, oldal: `/penzugyek/vallalkozasok`,
modell: `models/vallalkozas.py`.

Cégek, akik **embereket küldenek** a forgatásra, és ők számláznak a munkájukért.
A modul két dolgot ad: a cégek listáját/adatlapját (van-e velük élő
keretszerződés), és a tagság szerkesztését.

Új cég felvitelekor **hat mező kötelező**: cég neve, képviselő, székhely,
adószám, nyilvántartási szám, megbízás tárgya. Mind rákerül a cég nevére szóló
szerződésre és TIG-re - ha bármelyik hiányzik, a kiküldött dokumentumon üres
hely marad, amit utólag csak új papírral lehet javítani. Ezért a felvitelnél
kérjük be, nem a kiküldés pillanatában. Szerkesztéssel sem lehet kiüríteni őket
(`routes/vallalkozasok.py` `KOTELEZO_CEG_MEZOK`).

A már felvitt cég adatai a cég panelján **szerkeszthetők** (a hat kötelező mező
+ e-mail, `PATCH /api/v1/vallalkozasok/{id}`, csak a ténylegesen megváltozott
mezőkkel). Ez azért fontos, mert az elgépelt adószám vagy a közben megváltozott
székhely különben csak új cég felvételével lenne javítható - és akkor a régi
papírok gazdája kettévált volna. A **már kiküldött papírokat a szerkesztés nem
írja át**: azok a saját másolatukban őrzik az akkori adatokat.

Két szabály, ami itt dől el:

- **A tagság csak javaslat.** Hogy egy konkrét forgatáson kinek a munkáját ki
  számlázza, a **projekt-beosztás** dönti el (`models/project_szamlazo.py`).
  Ugyanaz az ember ma innen számláz, holnap saját névről, utána egy harmadik
  helyről - ezért nem lehet fix cég-mutatót az emberre akasztani.
- **Élő céges keretszerződés mentesít**: a cégtől jövő emberektől nem kérünk
  eseti szerződést azokon a projekteken, ahol a cég a számlázó fél.

### A számlázó fél feloldása

`services/szamlazo.py` - egy helyen tartja a szabályt, amire a szerződés-fázis, a
TIG-fázis és az utókövetés egyaránt épül:

> Egy (projekt, stábtag) párhoz tartozó számlázó fél alapból **maga az ember**,
> de a projekten felülírható másik emberre vagy egy vállalkozásra.

A kulcs rövid szöveges azonosító: `"e12"` = 12-es ember, `"v3"` = 3-as
vállalkozás. Azért szöveg, hogy ugyanaz az útvonal (`.../{szamlazo}/save`) embert
és céget is fogadjon - és mivel a puszta szám továbbra is embert jelent, a régi,
ember-azonosítós hívások változtatás nélkül működnek.

A "ki lehet számlázó fél" lista a **szerverről** jön
(`project_szamlazok._valaszthato_emberek`), mert a belsős státusz **időszakos**:
aki ma belsős, tavaly még külsősként dolgozhatott, és akkor simán ő számlázhatott
más helyett. Ezért nem a mai típus dönt, hanem az, hogy a **forgatás napján**
belsős volt-e (`belsos_idoszak.bizonyithatoan_nem_belsos`). Adat híján marad a
kizárás: a "nincs róla időszak, tehát biztosan nem volt belsős" következtetés
éppen a hibás irányba téved.

A számlázó fél **nem kell, hogy rajta legyen a projekten**: gyakori, hogy a
számlát olyan vállalkozó állítja ki, aki maga nem volt a forgatáson. A backend
ezt sosem kötötte stábtagsághoz, a választó pedig a javaslatokon felül minden
választható munkatársat és minden aktív céget felkínál.

Miért számít: a papírok **számlázó felenként** készülnek, nem emberenként. Három
ember munkáját ugyanaz a cég számlázza → egy szerződés és egy TIG, nem három.
Lásd [06-papirozas.md](06-papirozas.md).

## Visszatérő kötelezettségek

`/api/v1/kotelezettsegek`, modell: `models/kotelezettseg.py`, logika:
`services/kotelezettseg.py`.

Egy router szolgálja ki mindhárom felületet, mert a viselkedésük azonos - van egy
forduló, arra készül egy időszak, abba be kell írni a ténylegesen levont összeget,
és fel kell tölteni a számlát:

| Menüpont | Mi | Jogosultság |
|---|---|---|
| E-Rezsi (`/e-rezsi`) | Előfizetések | `/kotelezettsegek` |
| Biztosítások (`/kotelezettsegek`) | Biztosítások | `/kotelezettsegek` |
| Autók (`/autok`) | Járműpapírok lejárata | `/autok` |

Csak a szűrés (`tipus`, `auto_id`) és a jogosultság tér el. A felület azért van
szétválasztva, hogy a havi szolgáltatások ne folyjanak össze az évente lejáró
papírokkal.

**A lejárat-figyelmeztetés nem külön kapcsoló**: a lista lekérésekor fut le az
időszakok és feladatok "utolérése" - idempotensen, minden hívásnál. Nem ütemező
hajtja, tehát ha valaki nem nyitja meg az oldalt, az utolérés a következő
lekéréskor pótolja magát.

Notion-ból való áthozatal: `services/kotelezettseg_import.py`.
Frontend: `components/kotelezettseg/`.

## Autók

Lásd [04-csapat-felszereles.md](04-csapat-felszereles.md#céges-autók) - a
határidők kötelezettségek, a költségek pedig sima kiadások (`expenses.auto_id`),
ezért az autókra költött pénz automatikusan benne van a pénzügyi összesítőben.
