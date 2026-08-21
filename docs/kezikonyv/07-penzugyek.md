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

Néhány dolog a listákon szándékosan van így:

- **Egyik táblán sincs állapot-oszlop.** Sem a Kiadásokon ("Kifizetve /
  Nyitott"), sem a Bevételeken (a régi "Számla kiállítása → Kifizetve"
  léptető): ami ezekbe a listákba kerül, az azért kerül oda, mert a pénz
  rendezve van, tehát a jelző minden soron ugyanazt mondaná. Ami tényleg
  utalásra vár, azt az "Utalásra váró számlák" kártya hozza elő; a bevétel
  kifizetése a projektkód "3. Számla" kártyáján zárul le (határidő →
  kifizetve), ott jön létre és kap dátumot a bevétel-sor. Az `Expense.kesz`,
  a `Revenue.fizetes_datuma` és a `szamla_kiallitva_datuma` mezők megvannak,
  a tétel saját lapján szerkeszthetők.
- **A Bevételek "Honnan" oszlopa a MUNKA nevét írja ki**, alatta a
  projektkóddal - nem az ügyfelet. A régi, Notionból importált kódok
  többségénél az ügyfél "Ismeretlen ügyfél (Notion import)", vagyis az egész
  oszlop ugyanazt a semmit ismételte minden soron. Ugyanezért mutat a
  kintlévőség-táblázat is projektnevet.

### Mi számít bele az ÉVES bevételbe

Nem minden bevétel-sor pénz, ami ezen az úton folyt be hozzánk. Kétféle van,
aminek **látszania kell**, de az éves bevételbe nem való
(`services/elszamolas.bevetel_beleszamit`):

1. **"Nem volt tranzakció"** - a Notionból örökölt `bevetel_formaja` érték: a
   munka megvolt, pénzmozgás nem történt.
2. **Amit a számla-lépésnél kifejezetten kihagytunk** a bevételekből
   (beszámítás, csere, másik cégen át rendezve) - a `Revenue.
   beleszamit_a_bevetelekbe` mező `false` értéke.

A jelölő mező a kiadás-oldali `hozzaadas_a_kiadasokhoz` párja, ugyanazzal a
szabállyal: **NULL = beleszámít**, hogy a mező bevezetése ne tüntessen el némán
történeti sorokat az összesítőkből.

**A projekt saját bevétele (`ProjectCode.bevetel`) ettől független: ott MINDEN
sor számít**, mert a profithoz kell - ha nem így lenne, ezeknél a munkáknál
nulla bevétel és csupa veszteség látszana. Ez a szűrés csak az éves
összesítőket érinti: a Pénzügyek YTD-kártyáit, a 12 havi trendet, a
kintlévőséget és a Dashboard havi bevételét.

**A kihagyott tételről is keletkezik bevétel-sor.** Korábban nem: a Pénzügyek
listáján nyoma sem maradt annak, hogy az a munka rendezve van, csak a
projektkód adatlapján. Most ott a sor, a "Beleszámít" oszlopban látható
indokkal ("Nem volt tranzakció" / "Nem kerül a bevételek közé"). A kifizetés
visszavonásakor a jelölés is visszaáll.

### Mi kerül az "Utalásra váró számlák" listára

Három forrásból áll össze (`routes/finance._utalasra_varo_tetelek`):

| Forrás | Feltétel |
|---|---|
| Kiadás | nincs késznek jelölve, nincs fizetési dátuma, és **van feltöltött számlája** (enélkül utalni sem tudnánk mi alapján) |
| Külsős TIG | van számlája, de nincs kifizetettként jelölve |
| Belsős TIG | **le van zárva** (a TIG legenerálva és kiküldve a munkatársnak), van összege, és nem kihagyott hónap |

**A belsős TIG-nél nem elég, hogy nincs kifizetve.** Amíg a hónap TIG-je nincs
legenerálva és kiküldve, az elszámolás még alakulhat - az összeg is -, és egy
ilyet nem szabad utalásra kínálni. A "Kifizetve" gomb amúgy is csak lezárt
(kiküldött) TIG-et enged jelölni
(`routes/internal_performance_certificates._get_finalized_or_404`), tehát a
lista különben olyat ajánlana, amit a rendszer maga sem engedne lezárni. Lezárt
= `Kiküldve` vagy a régi `Kész` állapot (`LEZART_ALLAPOTOK`); az állapot nélküli
(importált) sor ide **nem** tartozik.

A belsős TIG ettől függetlenül **sosem vár fedezetre**: a bér nem a megrendelő
pénzéből megy, tehát nem nézzük, hogy a hónap tételeinek projektkódjaira
megérkezett-e a pénz. Számla sem kell hozzá - a belsős munkatárs nem számlázik,
a TIG maga a papír.

Az "Utalásra váró" lista összegei **bruttók**: ott a kérdés az, mennyit kell
ténylegesen elutalni (lásd lentebb, "A NETTÓ a mérvadó").

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
  átveszi (`POST …/szamla`), és **kötelező**: enélkül a feltöltés 400-zal
  elszáll, a felületen pedig elő sem jön a fájlválasztó, amíg a sor
  dátum-mezője üres. Azért kötelező, mert utólag már senki nem nyitja ki újra a
  fájlt érte, a tétel pedig határidő nélkül csak "valamikor utalandó"-ként lóg
  a Pénzügyben. Átírni bármikor lehet (`POST …/hatarido`), **kiüríteni** viszont
  csak addig, amíg nincs feltöltött számla - különben a kötelező megadást egy
  lépéssel meg lehetne kerülni. A második, harmadik (rész)számlánál nem kell
  újra megadni: a TIG-en már ott van. A belsős TIG-en ez a mező eddig is a papír
  űrlapján volt, alapértéke a következő hónap 20-a.
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
(ugyanaz a pénz lenne kétszer), a TIG **nettó** összege pedig ugyanannyi, mint a
belőle keletkezett Kiadás soré - a két úton számolt költség így nem tér el.

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

### A NETTÓ a mérvadó - bevételnél és kiadásnál egyaránt

Egyetlen szabály, egy helyen: `services/elszamolas.py`.

```
összeg = nettó, ha meg van adva; különben a bruttó (jobb híján)
```

**Miért nettó?** Az ÁFA átfolyó tétel: sem bevételként, sem költségként nem
marad a cégnél. Ha az egyik oldalt bruttóban, a másikat nettóban néznénk, a
kettő különbsége - amit "profitnak" hívunk - a két oldal ÁFA-tartalmának
különbségével csúszna el, annál nagyobbal, minél jobban eltér a két oldal
kulcsa (nem minden szállító áfás, és nem mindegyik 27%).

**Miért van mégis visszaesés a bruttóra?** Adathiány miatt, nem szemlélet
miatt. A Kiadások és a Bevételek felvitelekor csak a NETTÓ mezőt kérjük be, a
bruttó jellemzően a Notionból hozott soroknál van kitöltve - és van néhány régi
sor, amin CSAK bruttó van. Az még mindig közelebb van az igazsághoz, mint a
nulla. ÁFÁ-t viszont nem "számolunk vissza" belőle: a 27%-os osztás ugyanolyan
találgatás lenne, mint a felszorzás.

**Hol számít ez:** `ProjectCode._osszeg` (költség, bevétel, profit), a tételes
bontás (`services/projektkod_bontas.py`), a külsős TIG-ek
(`services/kulsos_koltseg.py`), a Pénzügyek összesítője (YTD bevétel/kiadás,
havi trend, fizetési mód szerinti bontás, kintlévőség), a Dashboard havi
bevétele és az autók eddigi költése.

**A bruttó nem tűnik el.** A Pénzügyek YTD-kártyái a nettó szám alatt halványan
kiírják a bruttót is (`ytd_bevetel_brutto`, `ytd_kiadas_brutto`), a Kiadás- és
Bevétel-táblákban külön oszlop a Nettó és a Bruttó, az autók listájában
mindkettő ott van, a számla-kártya pedig "1 000 000 Ft nettó (1 270 000 Ft
bruttó)" alakban mutatja. Ahol a kérdés a tényleges pénzmozgás - például az
"Utalásra váró" lista, hiszen annyit kell utalni -, ott továbbra is a bruttó
áll. Az ELSZÁMOLÁSBAN viszont mindenütt a nettó.

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

### Kassza: mennyi készpénz van épp

Minden kiadásnál és bevételnél megadható, **hogyan mozgott a pénz**:

| | Választható |
|---|---|
| Kiadás (`kifizetes_modja`) | Készpénz · Átutalás · Bankkártya · Nincs pénzmozgás |
| Bevétel (`fizetes_modja`) | Készpénz · Átutalás · Nincs pénzmozgás |

Bevételnél azért nincs kártya, mert nem fogadunk kártyát - a terminálos bevétel
a Krumpellóé, annak saját napi kassza-zárása van (lásd
[14-krumpello.md](14-krumpello.md)).

A **„Nincs pénzmozgás"** nem út, hanem annak a hiánya: van összeg és számla, de
nem mozdult pénz (beszámítás, csere, másik cégen át rendezve - a Notionben ez a
„Nem volt tranzakció"). Miért kell rá külön érték, ha a kasszába úgysem számít
bele? Mert az **üres mező azt jelenti, „nem tudjuk"**, és a Pénzügyek ki is
írja, hány tétel nincs megjelölve. Enélkül ezek a sorok örökre ott állnának
abban a számban, mintha valaki elfelejtette volna kitölteni őket.

Ez nem könyvelési finomság: a **készpénz egy fizikai doboz**, aminek van
egyenlege, és azt csak akkor tudjuk, ha minden készpénzes tétel meg van jelölve.

```
kassza egyenleg = a készpénzes BEVÉTELEK - a készpénzes KIADÁSOK
```

A Pénzügyek oldalon a **„Készpénz a kasszában"** kártya mutatja: az egyenleget,
az idei be/ki forgalmat, és havi bontásban a mozgást + a hónap VÉGI egyenleget.

#### Három szám, három kérdés

A kártya tetején három külön doboz áll - ugyanaz a hármas, ami a Notionben
külön widgetekben volt:

| | Mit mond meg |
|---|---|
| **KP a kasszában** | mennyi készpénznek KELL most nálunk lennie |
| **Idei KP kiadás – van számla** | ennyit fizettünk ki készpénzben úgy, hogy a bizonylat megvan |
| **Idei KP kiadás – nincs számla** | és ennyit úgy, hogy nincs meg - darabszámmal |

A harmadik nem statisztika, hanem **teendő**: számla nélkül a készpénzes kiadás
a könyvelésben nem elszámolható költség. Ezért van rajta darabszám is (az
mondja meg, mennyi munka összeszedni a hiányzó bizonylatokat), és ezért van
kiemelve, amíg nem nulla.

#### A napló: `/penzugyek/kp-forgalom`

A kártya az EGYENLEGET mondja meg, a **KP forgalom** oldal pedig azt, hogy
miből jött össze: minden készpénz-mozgás egy listában, időrendben, futó
egyenleggel. Ez az a nézet, ahol egy eltérés megkereshető - ha a dobozban nem
annyi pénz van, mint amennyit a rendszer mond, itt kell végigmenni.

Ugyanaz a szerepe, mint a Notion **„KP forgalom"** adatbázisának, csak nem
külön kézzel vezetve: a sorok magukból a kiadásokból és a bevételekből állnak
össze, tehát nem tud elcsúszni attól, amit a Pénzügyeken felvezettek. Oszlopok:
dátum, megnevezés, típus, projektkód, be, ki, **egyenleg a sor után**, és a
számla megléte.

A Notionből örökölt `KpForgalom` tábla sorai **számla nélküli** mozgások: az a
készpénz, ami nem számlán jött be vagy ment ki. Egy kivétellel: ami egy
kiadáshoz kötődik (`expense_id`), az kimarad - ugyanaz a pénzmozgás már
szerepel a kiadás soraként, beszámítva kétszer vonódna le. Hány ilyen van, azt
a lista fölött kiírjuk.

**AZ IRÁNYT AZ ELŐJEL MONDJA MEG.** A Notion „Forintban" formulája NEGATÍV a
kiadásokra - az „Összeg" oszlop viszont előjel nélküli, tehát abból nem derül
ki, hogy egy 600 000 Ft-os sor kivétel volt-e a kasszából vagy betétel. Ez a
Notion-egyeztetésben **132 sornál** ütött ki: mindegyiknél stimmelt a szám,
csak nálunk bevételként állt, ami valójában kiadás (ATM-felvételek, munkabérek,
kellékek). A szabály sorrendje (`services/kassza.kp_forgalom_iranya`):

1. ha van előjeles forint-érték, **az előjel** dönt;
2. különben a **„Forgalom"** szöveges mező (`bevetel` / `kiadas`);
3. ha egyik sincs, **bevétel** - a tábla erre való, a kiadásoknak saját táblájuk
   van. A felület ilyenkor „(feltételezve)"-t ír a sorra, hogy látszódjon: ez
   nem adat, hanem alapértelmezés.

#### A KP forgalom tábla szerkesztése

A napló alatt ott a **„KP forgalom tételek"** tábla, ahol minden mező átírható
(dátum, megnevezés, irány, összeg, pénznem, legális), a sorok törölhetők és új
is felvehető. Ez a tábla eddig sehol nem volt szerkeszthető, pedig a Notionből
örökölt sorok javításra szorulnak.

**A kézzel beírt érték erősebb az importált előjelnél**
(`routes/finance._kp_forgalom_kezi_javitas`): ha az összeget vagy az irányt
átírják, az importált formula-értéket félretesszük - különben valaki átírná a
600 000-et 500 000-re, és a felületen nem történne semmi, mert a régi érték
tovább számolna. Az eddigi irányt viszont **rögzítjük** az irány-mezőbe, mert
az előjel a törléssel elveszne: egy puszta összeg-javítás nem fordíthat át egy
kiadást bevétellé.

#### Legális és fekete készpénz

A készpénznél nem csak az számít, mennyi mozdult, hanem az is, **van-e mögötte
számla**:

- a **számlás kiadás** elszámolható költség - ez a legális oldal;
- a **számla nélküli kiadás** nem számolható el: ez az, amit a cég
  szempontjából „feketének" hívunk;
- a **számla nélküli BEVÉTEL** viszont épp ezt fedezi: ami számla nélkül jött
  be készpénzben, az számla nélkül is elkölthető.

```
fekete egyenleg = számla nélküli KIADÁS - számla nélküli BEVÉTEL
kassza          = MINDEN készpénzes bevétel - MINDEN készpénzes kiadás
```

A két szám két külön kérdésre válaszol, és nem keverendő: a kassza az, aminek
egyeznie kell azzal, ami fizikailag a dobozban van; a fekete egyenleg az, ami
nincs lefedve bizonylattal. Negatív fekete egyenleg nem hiány, hanem tartalék -
több a számla nélküli bevétel, mint a költés.

Az oldal ezt négy kártyában (idei bevétel számlával / számla nélkül, idei
kiadás összesen / ebből fekete) és egy táblázatban mutatja, ahol minden sor
látszik **idei** és **összes** bontásban is.

**A bevételnél MÁS a bizonyíték, mint a kiadásnál**, és ez nem
következetlenség: a kiadásnál a számlát mi KAPJUK, tehát a bizonyíték a
feltöltött fájl; a bevételnél mi ÁLLÍTJUK KI (egy külső számlázó rendszerben),
ott a **kiállítás dátuma** vagy a feltöltött PDF is elég. A számla attól még
létezik, hogy a PDF-jét nem töltötte fel senki.

Backend: `services/kassza.py` (a teljes kép egy helyen, a kártya és a napló
KÖZÖS számítása - két külön implementáció előbb-utóbb két külön egyenleget
adna), `routes/finance.kp_naplo`. Frontend:
`app/(app)/penzugyek/kp-forgalom/page.tsx`.

#### Ha nem stimmel egy összeg: egyeztetés a Notionnel

```
# csak a mi oldalunk: darabszám, végösszeg, mezőértékek
python scripts/kp_forgalom_egyeztetes.py

# tételes összevetés a Notion "KP forgalom" adatbázisával
NOTION_API_KEY=... python scripts/kp_forgalom_egyeztetes.py --notion
```

Három különböző dolog állhat egy eltérés mögött, és mindhárom máshogy
javítandó: **hiányzik nálunk egy sor** (nem jött át az importtal, vagy azóta
született), **más az összeg** ugyanazon a soron (a Notionben javították
utólag), vagy **máshogy értelmezzük** (irány, pénznem, kiadáshoz kötés) -
ilyenkor a darabszám és a végösszeg is stimmelhet külön-külön, mégis mást mutat
a felület. A script mind a hármat kiírja, és megmutatja a `forgalom` /
`legalis` / `penznem` mezők tényleges értékeit is - abból derül ki, mit
jelentenek a Notion szabad szöveges mezői.

#### Ha a darabszám sem stimmel: tiszta újraimport

Az import **idempotens, de nem töröl**: ha egy Notion-sort azóta töröltek, vagy
egy elveszett leképezés miatt egy sor kétszer jött át, a mi táblánk több sorból
áll, mint a Notioné. Ilyenkor a legtisztább nulláról újraépíteni:

```
python scripts/kp_forgalom_ujraimport.py                            # csak megmutatja
NOTION_API_KEY=... python scripts/kp_forgalom_ujraimport.py --vegrehajt
python scripts/kp_forgalom_ujraimport.py --vegrehajt --csak-torles  # csak üríti
```

A `--csak-torles` nem importál újra (Notion-kulcs sem kell hozzá): akkor jó, ha
a tábla tartalma használhatatlan, és előbb tiszta lappal akarunk indulni. Az
importot bármikor le lehet futtatni utána
(`notion_import.py --only KpForgalom`).

**AMI ETTŐL MÉG LÁTSZIK a KP forgalom oldalon:** a készpénzesnek jelölt
KIADÁSOK és BEVÉTELEK. Azok nem ebben a táblában vannak, hanem a
Kiadások/Bevételek közt - a script nem nyúl hozzájuk, mert azok a rendszer élő
pénzügyi tételei. Ha az oldalt teljesen nullán akarod látni, a kiadásokról és
bevételekről a KÉSZPÉNZ fizetési módot kell levenni (vagy törölni a
tételeket) - az viszont már a Pénzügyek valódi adatait érinti.

Törli az összes `kp_forgalmak` sort **és a hozzájuk tartozó
Notion-leképezést** (`notion_import_map`) - az utóbbi nélkül az újraimport a már
nem létező rekordokra mutató leképezéseket próbálná újrahasznosítani -, majd
lefuttatja a KP forgalom importert, és kiírja az előtte/utána képet.

Alapból **próba**: a törlés visszavonhatatlan, ezért külön kapcsoló kell hozzá.
És mielőtt bármit törölne, kilistázza azt, ami **kézi eredetű vagy kézzel lett
javítva** (nincs Notion-leképezése, vagy be van állítva az iránya, de nincs
importált formula-értéke) - ezek is elvesznek, és utána nincs hova visszanyúlni.

> A próba-futás kiírja, HÁNY sorunk van - érdemes ezzel kezdeni. A KP forgalom
> oldal „fekete kiadás" darabszáma ugyanis NEM ezt számolja: abban a készpénzes
> KIADÁS-sorok vannak (a Kiadások táblából), nem a KP forgalom tétele.

**Egy ismert hibaforrás, ami már javítva van:** a `KpForgalom.forintban`
korábban `penznem == "HUF"` szigorú egyenlőséggel nézte a pénznemet. A
Notionben ez szabad szöveg volt, magyarul kitöltve, tehát a sorok nagy részén
**„Forint"** áll - azokat mind devizásnak látta, és `None`-t adott rájuk.
Vagyis a kassza összesítéséből annyi forint hiányzott, ahány ilyen sor van.
Mostantól a közös pénznem-szabály dönt (`services/penznem.py`), a valódi
devizás sornál pedig a Notion „Forintban" mezője.

**Mi számít számlának** (`services/bizonylat.py`)? Egy tényleges bizonylat, nem
egy szándék: a rendszerbe **feltöltött** számla-fájl (`DocumentAttachment`,
`kategoria="szamla"`), vagy a Notionből örökölt **„Számla pdf"** mező
(`Expense.szamla_pdf_urls`) - a régi sorokon ott van a fájl, csak nem
csatolmányként. A szöveges `szamla` mező szándékosan **nem** számít: abban
számlaszám, „igen", „nincs" és üres string egyaránt előfordul, tehát a
jelenléte nem bizonyít semmit. Az üres JSON-lista (`[]`) sem fájl - egy
`IS NOT NULL` szűrő ezt még „van"-nak látná, ezért fut a bontás Pythonban.

Néhány szabály, ami a számot használhatóvá teszi:

- **Bruttóban**, nem nettóban: a dobozban annyi pénz van, amennyit ténylegesen
  kifizettünk/megkaptunk, ÁFÁ-stól. (Az elszámolás máshol nettó - de egy doboz
  pénz nem tud nettó lenni.)
- Csak a **megtörtént** mozgás számít (van fizetés dátuma): egy jövő heti
  készpénzes kiadás még nem hiányzik a kasszából.
- A „nem számít bele" jelölésű sorok itt is kimaradnak: ami a Pénzügyek szerint
  nem történt meg, az a kasszát sem mozgatta.
- Az **üres fizetési mód nem „talán"**: nem számítjuk bele. A kártya viszont
  kiírja, hány kifizetett tételen hiányzik a jelölés - amíg ez nem nulla, az
  egyenleg csak közelítés. Egy találgatott egyenleg rosszabb, mint egy hiányos:
  az utóbbin legalább látszik, mennyi hiányzik.

A módok listája **zárt és egy helyen áll** (`services/fizetesi_mod.py`): ha
mindenki maga írja be („kp", „Készpénz", „KP"), az összesítés annyifelé
szakad, ahányféleképp leírták - és a kassza egyenlege pont annyival lesz hamis.
A felismerés ettől még türelmes a régi adatokkal („KP", „Kp.", ékezet nélkül is).

#### A régi sorok visszamenőleges megjelölése

A fizetési mód mezőt később vezettük be, ezért a Notionből örökölt sorokon üres
- a kassza egyenlege viszont épp ebből számol. Szerencsére a Notionben ott van
ugyanez, csak **más mezőben**:

| | Notion mező | nálunk | mit tartalmaz |
|---|---|---|---|
| Kiadás | „Kiadás formája" | `Expense.tipus` | keveri a kiadás fajtáját és a fizetés útját: van benne „Bérlés" és „Alap bér", de „Bankkártya" és „Előfizetés" is |
| Bevétel | „Bevétel formája" | `Revenue.bevetel_formaja` | ebben áll, hogy utalással vagy készpénzben jött-e a pénz (és az is, hogy „Nem volt tranzakció") |

Egy script viszi át mindkettőt a saját fizetési mód mezőjébe.

```
python scripts/fizetesi_mod_kitoltese.py              # csak megmutatja, mit tenne
python scripts/fizetesi_mod_kitoltese.py --vegrehajt  # ténylegesen ír
```

Alapból **próba**: kiírja, mit töltene ki és mi maradna üresen, de nem nyúl az
adatokhoz. Így a szabály előbb ellenőrizhető a valódi adaton, mint ahogy ír.

A felismerés szabályai (`services/fizetesi_mod.kikovetkeztetett_mod`):

- **Előfizetés → Bankkártya**, mindig: az előfizetéseket kártyáról vonják,
  nincs is hozzá utalás, amit indítani kellene. Az „Előfizetés – Adobe CC" is
  előfizetés, ezért ez a szó a szöveg BÁRMELY részén elfogadott.
- **Alap bér / Munkabér → Átutalás**, a munkabér a bankszámlára megy.
- A **„Bankkártya" / „Készpénz" / „Átutalás" típus** önmagát mondja meg.
- A **valódi adatból visszajelzett típusok**, mind átutalás: `belsos`, `extra`
  (a Kiadások tábla saját típusa), `Forgatás`, `elszámolásból levonva`,
  `Általános túlóra`, `Plusz napok`, `Starlink`, illetve az elgépelt
  `Előfizetls` (épp az elgépelés miatt nem illeszkedett az „előfizetés"
  kulcsszóra). Ezek egyikét sem lehetne a szóból kitalálni - azért állnak
  felsorolva, mert megmondták őket.
- **Ami nem egyértelmű, üresen marad**: a „Parkolás" vagy a „Bérlés" bármelyik
  úton fizethető, egy tippelt mód pedig a kassza egyenlegét hazudná meg -
  márpedig épp azért van ez a mező. A script a végén kilistázza, mi maradt
  üresen, hogy azok kézzel pótolhatók legyenek.
- Ami már meg van jelölve, azt **nem írja felül**: a kézzel beállított mód
  erősebb, mint egy név-alapú következtetés.

A rövid, kategória-szerű nevek (`alap ber`, `kartya`, `ber`) csak **teljes
egyezésre** illeszkednek, nem részletként: a „bér" benne van a
„Kamerabérlés"-ben is, ami épp nem munkabér, a „kártya" pedig az „SD kártya"
eszközben.

**A bevételnél két eltéréssel:**

1. Ott **nincs kártya** (`BEVETEL_MODOK`), ezért a kikövetkeztetés `engedett`
   listát kap. Ami nem fér bele, azon nem áll meg, hanem **továbblép** - hátha
   egy másik mező mond valami használhatót.
2. **A maradék is kap választ: átutalás** (`BEVETEL_ALAPERTELMEZES`). Ez az
   egyetlen hely, ahol nem „nem tudjuk"-ot mondunk a felismerhetetlenre. Két
   okból vállalható: a készpénzes bevételt a „Bevétel formája" mező megnevezi,
   tehát ami marad, az a számlára érkezett; és a **kassza egyenlegét nem
   érinti**, abba csak a készpénz számít bele. A jelentésben külön soron
   látszik, hány sor jött innen és nem a saját mezőjéből
   („→ Átutalás (alapértelmezés)").

   A kiadásoknál szándékosan **nincs** ilyen alapértelmezés: ott a bankkártya
   is játszik, és a „Parkolás"-ról tényleg nem tudjuk, hogyan fizették.

A **„Nem volt tranzakció"** nem marad üresen: abból „Nincs pénzmozgás" lesz -
az nem hiányzó adat, hanem maga a válasz.

### A projekt bevétele: a vállalási ár, amíg nincs kifizetés

`models/project_code.bevetel` - két forrásból, ebben a sorrendben:

1. a **tényleges bevétel-sorok**, ha vannak: az a rögzített valóság, azt nem
   írja felül egy papíron szereplő szám;
2. különben a **vállalási ár**: a TIG-ről, annak híján a szerződésről, annak
   híján a projektkód saját mezőjéből (`projektkod_osszeg.forintban()`).

Miért kell a második? Mert a bevétel-sor csak a **kifizetéskor** keletkezik
(lásd a számla-lépést). Addig a projekt nulla bevétellel és csupa veszteséggel
állt a listán, pedig az összeg rég ismert volt - ott áll a szerződésen és a
TIG-en. A profit épp arra való, hogy megmondja, megéri-e a munka; ehhez nem a
pénz beérkezésére kell várni, hanem tudni kell, mennyiért vállaltuk.

Ez a szám a **PROJEKT képe**, nem a cég éves bevétele: az utóbbi továbbra is
kizárólag a tényleges bevétel-sorokból számol (lásd fentebb, "Mi számít bele az
ÉVES bevételbe"), tehát egy még ki nem fizetett munka nem duzzasztja fel az
éves bevételt. A `becsult_profit` neve is ezért „becsült".

### A tételes bontás sorai törölhetők

A projektkód alján a három tábla (Forgatások · Utómunka · Egyéb projekt
kiadások) minden sora törölhető. Itt látszik, mi terheli a kódot, tehát itt
derül ki, ha valami tévedésből került rá - a javításhoz eddig három másik
oldalra kellett elnavigálni.

A törlés a rekord **saját végpontjára** megy, tehát ugyanazt a jogosultságot
kéri, mint a saját oldalán: a forgatás a Projektekét, az anyag az Utómunkáét, a
kiadás a Pénzügyekét. Ezért kap mindhárom tábla külön kapcsolót - a gomb csak
ott jelenik meg, ahol a szerver is engedné. A megerősítő párbeszéd ugyanaz,
mint máshol.

### Magyarázat az összeghez

A „Mennyiért vállaltuk" kártyán a szám mellett van egy szabad szöveges mező is
(`ProjectCode.vallalasi_ar_magyarazat`). Nem minden összeg magyarázza magát, és
a **0 Ft a legkevésbé**: lehet, hogy nem ingyen dolgoztunk, hanem beszámítottuk
valakinek a fizetésébe, egy korábbi munkát kompenzáltunk vele, vagy csere volt.

Ha az összeg 0 és nincs magyarázat, a kártya **figyelmeztet** - de nem tilt: a
nulla lehet valós, csak akkor is tartozik hozzá egy mondat. Enélkül fél év
múlva csak egy nulla áll ott, és nem lehet megkülönböztetni a „tényleg ennyi"
és az „elfelejtették beírni" esetet - a profit pedig ugyanezt a nullát viszi
tovább.

Külön mező, nem a `megjegyzes`: az a projektkód általános jegyzete, ez pedig
konkrétan az ÁRRÓL szól, és ott is jelenik meg, ahol az ár - a projektkód-lista
Bevétel oszlopa alatt is.

### Deviza: euróban/dollárban felvezetett tétel

Egyetlen szabály, egy helyen: `services/penznem.py`.

```
a tárolt összeg MINDIG forint
```

Kiadásnál, bevételnél és a projektkód vállalási áránál is megadható **EUR** és
**USD**. Ha nem forint, az **árfolyam kötelező** - enélkül a beírt szám nem is
értelmezhető: az „1500" lehet 1 500 Ft és 592 500 Ft is. A szerver átváltja, és
a `netto`/`brutto` mezőbe **már a forint kerül**, a sor `penznem`-e pedig
"HUF".

**Miért nem marad az "EUR" a `penznem` mezőben?** Mert az azt mondaná, hogy a
sor összege euró - és minden összesítő (éves kiadás, projekt-profit,
autó-költség) vagy hamisan adna hozzá 1500-at a forintokhoz, vagy némán
kihagyná a nem forintos sorokat. (Az autók oldala pontosan ezt tette:
`penznem == "HUF"` szűrővel számolt, tehát egy euróban fizetett szerviz úgy
tűnt el a költségből, mintha nem is lett volna. Ez a szűrő ezzel együtt el is
tűnt.)

**„Forint" is forint.** A pénznem a Notionben szabad select volt, magyarul
kitöltve: a régi projektkódokon „Forint" áll, nem „HUF". A
`penznem.normalizald()` ezért aliasz-táblából dolgozik („Forint", „Ft", „Euró",
„€", „Dollár", …), ékezet- és kisbetű-tűrően. Enélkül a felület *ismeretlen
pénznemet* kiabált egy teljesen szokásos forintos munkára, és árfolyamot kért
hozzá. Amit nem ismer fel, azt nem nyeli le: nagybetűsítve továbbadja, és a
szerver beszédesen elutasítja. A táblát a `lib/penz.penznemKod()` tükrözi -
a kettőt együtt kell módosítani.

**Az eredeti adat megmarad**: `eredeti_penznem`, `eredeti_netto`,
`eredeti_brutto`, `arfolyam`. Fél év múlva egy 592 500 Ft-os sor mögött
enélkül senki nem tudná, hogy az 1 500 EUR volt 395-ös árfolyamon - pedig a
számlán az áll. A lista ezért ki is írja a nettó alá: „1 500 EUR × 395".

Az átváltás **akkor fut le, ha a kérés hozza a `penznem` mezőt** - vagyis
amikor a felhasználó most mondja meg, milyen pénznemben érti a beírt összeget.
Egy önmagában álló összeg-javítás (a listában a nettó cella átírása) tehát
forintos javítás marad, és nem írja felül azt, HOGYAN vezették fel a tételt.

**A projektkódon** a vállalási ár abban a pénznemben marad, amiben
megállapodtunk (a szerződésen és a TIG-en is az áll) - a **bevétel** viszont
forintban keletkezik belőle, a projektkód `penznem` + `arfolyam` mezője
szerint (`projektkod_osszeg.forintban()`). A „Mennyiért vállaltuk" kártya és a
„3. Számla" kártya is kiírja, mennyi kerül ebből a Pénzügyekbe.

Az **árfolyam mező csak devizánál jelenik meg** (`QuickCreateForm` →
`FieldSpec.showIf`): forintnál nincs mit átváltani, és egy mindig ott álló,
üresen hagyott mező azt sugallná, hogy kellene kitölteni. A feltétel
SZÁNDÉKOSAN adat (`{ field, oneOf, noneOf }`), nem függvény: az űrlapot
szerver-komponensek állítják össze, és függvényt nem lehet kliens-komponensnek
átadni.

**A papírokon a megállapodás pénzneme áll.** Ha a projektkód euró, akkor a
szerződésen és a TIG-en is euró - nem forint. A papír a megbízásról szól, az
összege az, amiben megállapodtunk; a **bevétel** ettől még forintban keletkezik
belőle. A papír-listák (Megrendelői szerződések / TIG-ek) ezért soronként a
saját pénznemükben mutatják az összeget, és az **összesítés csak a forintos
tételekből** megy: különböző pénznemű összegeket összeadni nem szám, hanem hiba
(5 000 EUR nem 5 000 Ft).

A generált Google Docs papírra a `{{penznem}}` ("Ft" / "EUR" / "USD") és a
`{{penznem_szoveg}}` ("forint" / "euró" / "dollár") helyőrző viszi ki a
pénznemet. **A régi sablonokban az „Ft" fixen a szövegben áll** - ahhoz, hogy a
devizás papír a nyomtatott példányon is helyes legyen, a sablonban kell
kicserélni ezekre a helyőrzőkre (a sablon Google Docsban él, nem a
rendszerben).

Frontend: `lib/penz.ts` (`PENZNEMEK`, `devizaNyom`, `penzzel`, `devizas`),
`components/projektkod/VallalasiAr.tsx`.

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
