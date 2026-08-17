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

### A számla két dátuma: határidő és utalás napja

Mindkét TIG-fajta papírján ott a **fizetési határidő** és a **tényleges utalás
napja** (`fizetesi_hatarido`, `utalas_datuma`) - a külsős oldalon is, nem csak a
belsősön.

- **Határidő**: a számlán szerepel, tehát akkor van a kezünkben, amikor
  feltöltjük - a külsős TIG számla-feltöltő végpontja ezért egy `Form` mezőben
  átveszi (`POST …/szamla`), és utólag is állítható (`POST …/hatarido`), mert a
  fájl gyakran előbb kerül fel, mint ahogy valaki megnézné, mi áll rajta. A
  belsős TIG-en ez már eddig is a papír űrlapjának a mezője volt.
- **Utalás napja**: a "Kifizetve jelölés" ablakában adható meg
  (`KifizetesIn.kifizetes_datuma`), alapból a mai nap. Azért kell tudni
  visszadátumozni, mert a jelölés rendszerint napokkal a tényleges utalás után
  történik meg - a mai nappal a tétel rossz napon (rosszabb esetben rossz
  hónapban) állna a kimutatásban.

Mindkét dátum átmegy a keletkező Kiadás sorra is (a határidő csak akkor, ha ott
még nincs kézzel beírva), így a Pénzügy "Utalandók" nézete és a papír ugyanazt
mondja.

### A projekt önköltsége ≠ a kiadás-lista

A projektkód "Összes költség" száma **négy** részből áll
(`models/project_code.py`) - az adatlap ki is írja mindegyiket ("Mibe került",
`components/KoltsegBontas.tsx`), mert egy összeg önmagában nem mondja meg, mire
ment el a pénz:

| Rész | Mi ez | Honnan |
|---|---|---|
| Külsős stáb | az ide tartozó forgatásokra szóló TIG-ek rá eső része + a TIG-en kívüli külsős kifizetések | `services/kulsos_koltseg.py` |
| Vágás (utómunka) | a vágások mért idejéből számolt ár | `Deliverable.koltseg` |
| Belsős munkanapok | a saját stáb napidíja | `services/belsos_koltseg.py` |
| Egyéb kiadás | minden más kiadás-sor (bérlés, utazás, kellék) | MARADÉK - így a négy rész összege pontosan az összes költség |

**A külsős munka ára a TIG-eken áll, nem a Kiadás sorokon.** A kifizetéskor a
TIG-ből ugyan keletkezik Kiadás sor, de a költség már a kifizetés ELŐTT is
valóságos: a számla be van adva, a pénz ki fog menni. Ha csak a kifizetett
sorokat néznénk, minden még nem rendezett projekt profitja hazudna - épp az,
amelyik friss. A TIG-ből származó Kiadás sort ezért kihagyjuk az összegzésből
(ugyanaz a pénz lenne kétszer), a TIG összegét pedig bruttóban számoljuk, ha a
megbízott ÁFÁ-s - annyi megy ki a házból.

**Több projektre szóló TIG-nél csak a rá eső rész számít.** Egy ember egy
számlán beküldheti az egész hetet (`PerformanceCertificateTetel`): ha a
tételeken van összeg, azok döntenek, ha nincs, a TIG összegét egyenlően
osztjuk el a tételei közt. Ez becslés, de közelebb van a valósághoz, mint az
egészet ide írni (a többi projekt költségét is idehúzná) vagy nullázni
(mintha ingyen lett volna). A TIG akkor is beleszámít ebbe a projektkódba, ha
egy MÁSIK projekt "otthonában" készült - a tételei kötik ide
(`Project.tig_tetelek`).

A TIG-en kívüli külsős kifizetéseket két jelről ismerjük fel, mert a Notionból
hozott soroknál a "Kiadás formája" szabad szöveg volt (bármi lehet benne), a
hozzájuk kötött EMBER típusa viszont megbízható: `Expense.tipus == "kulsos"`
vagy külsős a kiadáshoz kötött ember.

**Bruttó, ha van - különben nettó** (`ProjectCode._osszeg`). A Kiadások és a
Bevételek felvitelekor csak a NETTÓ mezőt kérjük be, a bruttó jellemzően csak a
Notionból hozott soroknál van kitöltve. Amíg csak a bruttót néztük, a kézzel
felvezetett tételek nullának számítottak, és a projekt költsége úgy nézett ki,
mintha fel se vitték volna őket. ÁFÁ-t nem tippelünk rá: a nettó legalább igaz,
egy kitalált 27% nem feltétlenül. A bruttó a listán utólag beírható.

A belsős napidíjnak nincs és nem is lesz Kiadás sora: a belsős alapbér a hónap
végén, egy tételben megy be (Belsős TIG). Ezért a projektkód költsége és a
Pénzügyek kiadás-listája nem ugyanaz a szám - és ez nem hiba: a projektnél azt
akarjuk látni, mibe került VALÓJÁBAN a munka, a kiadásoknál azt, mennyi pénz
ment ki.

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

Egy router szolgálja ki mindkét felületet, mert a viselkedésük azonos - van egy
forduló, arra készül egy időszak, abba be kell írni a ténylegesen levont összeget,
és fel kell tölteni a számlát:

| Menüpont | Mi | Jogosultság |
|---|---|---|
| E-Rezsi (`/e-rezsi`) | Előfizetések | `/kotelezettsegek` |
| Autók (`/autok`) | Járműpapírok lejárata (forgalmi, biztosítás) | `/autok` |

Csak a szűrés (`tipus`, `auto_id`) és a jogosultság tér el. A felület azért van
szétválasztva, hogy a havi szolgáltatások ne folyjanak össze az évente lejáró
papírokkal.

**Külön "Biztosítások" oldal nincs.** Volt, de fölöslegesnek bizonyult: a
biztosítás a gyakorlatban mindig egy autóhoz tartozik, és ott is kell kezelni -
két helyen ugyanaz a lista csak azt a kérdést szülte, melyikbe kell felvinni. A
`biztositas`/`berlet`/`egyeb` típus a modellben és az API-ban MEGMARADT (a régi
sorok is), csak nincs hozzá saját menüpont; az autóhoz kötött határidők a
jármű lapján élnek. A `/kotelezettsegek` jogosultság-kulcs is megmarad, mert az
E-Rezsi azon fut.

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
