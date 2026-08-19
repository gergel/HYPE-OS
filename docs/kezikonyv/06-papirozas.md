# 06 - Papírozás: szerződések és teljesítési igazolások

Ez a rendszer legsűrűbb doménje. Ha egyetlen dolgot jegyzel meg róla, ez legyen:

> **A papír nem emberhez tartozik, hanem SZÁMLÁZÓ FÉLHEZ.**
> Ha egy projekten több stábtag munkáját ugyanaz a fél számlázza (egy másik
> ember vagy egy cég), akkor **egy** szerződés és **egy** TIG kell mindannyiukra.
> A csoportosítás egy helyen dől el: `services/szamlazo.py` (`SzamlazoFel`,
> `SzamlazoCsoport`).
>
> Ebből következik: ha a félnek **már van kiküldött TIG-je** ezen a projekten, a
> rendszer nem kér tőle újat akkor sem, ha utólag kerül alá egy másik ember.
> Ilyenkor a hiányzó tételt a meglévő TIG-en kell rendezni (állapot vissza
> „Készítés alatt”-ra, tétel hozzáadása) - egy megbízott ne kapjon két
> igazolást ugyanarról a projektről.

## Ami kimarad: a HYPE24-es sorozat

A HYPE24 projektkódú munkák papírjai a HYPE OS bevezetése **előtt**, egy másik
rendszerben készültek el - nincs velük teendő. Ezért kimaradnak mindenhonnan,
ahol a rendszer hiányzó papírt számol vagy feladatot gyárt: az alvállalkozói
szerződésből, a külsős TIG-ből, az utókövetésből, a megrendelői szerződésből és
TIG-ből, és az automatikus papírozás-feladatokból.

A szabály egy helyen áll: `services/papirozas_hatokor.py`. Előtag-alapú (a
sorozat minden tagját érinti), és környezeti változóval bővíthető vagy
kikapcsolható a kódhoz nyúlás nélkül:

```
PAPIROZAS_KIVETT_PROJEKTKODOK=HYPE24,HYPE23
```

Üres értékkel a kizárás teljesen kikapcsol. A projektkódot két helyen keressük -
a kapcsolt Project Code-on és a Notionból örökölt `projektkod_szoveg` mezőn -,
mert a párját nem találó importált soroknál csak az utóbbiban maradt meg az
eredeti kód.

## Áttekintés

| Papír | API prefix | Kinek |
|---|---|---|
| Alvállalkozói **keretszerződés** (álló) | `/api/v1/contracts` | Külsős, tartós együttműködés |
| **Eseti** alvállalkozói szerződés | `/api/v1/alvallalkozoi-szerzodesek`, lista: `/api/v1/eseti-szerzodesek` | Külsős, projekthez kötve |
| Megrendelői **keretszerződés** (álló) | `/api/v1/megrendeloi-keretszerzodesek` | Ügyfél felé, tartós együttműködés |
| **Megrendelői** eseti szerződés és TIG | `/api/v1/megrendeloi-papirok/{szerzodes\|tig}` | Ügyfél felé, Project Code-onként |
| **Külsős TIG** | `/api/v1/teljesitesi-igazolasok` | Nem belsős stábtag, projektenként |
| **Belsős TIG** | `/api/v1/belsos-tig` | Belsős munkatárs, havonta |
| Céges keretszerződés | `/api/v1/vallalkozasok` | Számlázó cégek |

Összefoglaló nézet mindegyikről: **Utókövetés** (`/utokovetes`) - ott
projektenként látszik, mi hiányzik.

Négy **gyűjtő lista** van, amelyik nem projektenként, hanem papíronként néz rá
ugyanerre, és a **kihagyottakat is mutatja az indokukkal**:

| Oldal | Mit sorol fel |
|---|---|
| `/penzugyek/eseti-szerzodesek` | Minden eseti alvállalkozói szerződés |
| `/utokovetes/kulsos-tigek` | Minden külsős TIG |
| `/projektek/megrendeloi-szerzodesek` | Minden megrendelői eseti szerződés |
| `/projektek/megrendeloi-tigek` | Minden megrendelői TIG |

A kihagyottak azért vannak bennük, mert egy kihagyott papír ugyanúgy elszámolás,
mint egy kiküldött, csak dokumentum nélkül - és pont az a néhány tétel, amit
később a legvalószínűbben számon kérnek. Az Utókövetés ezeket már nem mutatja
(lezártnak számítanak), tehát nélkülük nem lenne hol utánanézni.

A külsős TIG-ek listáján egy sorra kattintva **magának a TIG-nek az adatlapja**
nyílik meg felugró ablakban (`GET /kulsos-tigek/{id}`), nem a projekt teljes
utókövetése: ott a projekt összes papírja van, itt viszont pont az a kérdés,
hogy ennek az egy embernek erre az egy projektre mi van a papírján. Az ablak
**olvasó** - a szerkesztés az utókövetés-oldalon marad, ahová egy gomb visz.
Kettőzött szerkesztő-felületből előbb-utóbb két, egymástól elcsúszó igazság lenne.

## Hol papírozunk: az Utókövetésben, nem a Projekt oldalon

Az alvállalkozói papírozás (ki számláz kiért → szerződés → TIG → kifizetés)
**egy helyen él: az Utókövetés projekt-oldalán** (`/utokovetes/{id}`). A Projekt
adatlapja a diszponálásé - forgatás, stáb, technika, diszpó -, ott ezek a
kártyák szándékosan nincsenek kint; helyettük egy link vezet az utókövetéshez.

Miért: a két dolgot más ember csinálja, más időben. A diszpó a forgatás előtti
napon készül, a papírozás hetekkel később, és akkor egyszerre több projektre.
Amíg mindkét oldalon ott volt ugyanaz a felület, a diszpót író ember is
beleakadt egy fél-kész papírozásba, ami nem az ő dolga volt.

## Az alvállalkozói folyamat sorrendje

0. **Stáb összeáll** → a nem belsős stábtagoknál rögtön megkérdezzük, mennyiért
   vállalják azt a napot. Ez az összeg tölti elő a lenti 2. és 3. lépés
   piszkozatát - lásd
   [03-projektek-ugyfelek.md](03-projektek-ugyfelek.md#megbeszélt-díj-mennyiért-vállalja-azt-a-napot).
1. **Diszpó kimegy** → megvan, ki vett részt a projekten.
2. **Eseti szerződés**: azokra kell, akik *sem nem belsősök*, *sem nincs érvényes
   keretszerződésük*. Aki keretszerződéses, az itt mentesül.
3. **Külsős TIG**: minden nem belsős stábtagnak - **a keretszerződéseseknek is**.
   A TIG a konkrét munka elvégzését igazolja, nem azt, hogy van-e álló szerződés.

**A TIG felenként nyílik meg, nem projektenként.** Amint egy számlázó félnek
megvan a szerződése (kiküldve vagy kihagyva) - vagy keretszerződés mentesíti -,
róla **azonnal** készíthető TIG, akkor is, ha a projekt többi szereplője még
szerződésre vár. Korábban az egész projekt szerződés-fázisának le kellett
zárulnia, így egyetlen késlekedő stábtag megállította mindenki papírozását.
A szabály egy helyen áll: `subcontractor_contracts.csoport_szerzodes_kesz()`,
a TIG-oldali szűrő pedig `performance_certificates.tig_keszitheto_csoportok()`.

### Egy papír, több forgatási nap

Egy eseti szerződés (és ugyanígy egy TIG) **több projektre is szólhat** - három
nap forgatás egy szerződéssel, vagy több nap egy számlán. Ilyenkor a papír
`project_id`-je csak azt mondja meg, **melyik napról indítva készült**; hogy
mit FED, azt a tételei hordozzák (`services/papir_fedettseg.py`).

Ezt minden lekérdezésnek a **lefedettség** szerint kell néznie, nem a saját
`project_id` szerint. Ahol ez elmaradt, ott a papír a többi napon egyszerűen
nem látszott - a felhasználó azt látta, hogy "négy napra jelöltem, de csak
egyhez mentette el". A teendő-lista és a fázis-számítás mindig jól számolt (a
többi nap nem kért új szerződést), csak az *Elkészült szerződések* és az
*Elkészült TIG-ek* táblája hiányzott róluk, ami ugyanolyan riasztó.

Ezért a lefedettség szerint szűr:

- `alvallalkozoi-szerzodesek/{id}/all` és `teljesitesi-igazolasok/{id}/all`;
- a papír törlése is - egy négynapos szerződést arról a napról is le lehessen
  venni, ahonnan nem ő indult.

Ugyanezen az alapon a **lezáró műveletek** (`/skip`, `/mar-van` és a TIG
`/skip`) is átveszik a kipipált tételeket, nem csak a mentés és a kiküldés: ha
egy papír a hét mind a négy forgatását fedi, akkor a **kihagyása** és a "van
már szerződés" jelölése is mind a négyre szól. Enélkül a többi napon a fél újra
szerződésre várt volna - pedig épp azt mondtuk ki róla, hogy tőle nem lesz
papír. Üres kiválasztásnál a lezárás a bejegyzésen lévő tételeket hagyja
érintetlenül (a mentés viszont üres listára szándékosan hibázik).

A sor **kiírja, hány projektre szól** (`projektek`), és a törlés megerősítése
is figyelmeztet rá: a törlés a PAPÍRT viszi, tehát mind a négy napról eltűnik,
nem csak arról, ahol épp állunk.

### Az elkezdett papír eldobható

A projektkód adatlapján a megrendelői szerződés és a TIG **törölhető**
(`DELETE /megrendeloi-papirok/{fajta}/{id}`). Egy rossz adattal elindított
papírt nem elég átírni: ha már generálódott belőle dokumentum, tiszta lappal
kell tudni újrakezdeni.

A KIKÜLDÖTT papírnál is engedjük, de a megerősítés kimondja, hogy a dokumentum
már a megrendelőnél van - a törlés csak a nyilvántartásból veszi ki, a kiküldött
példányt nem vonja vissza.

### A TIG a szerződésből indul

A két papír UGYANARRÓL A MUNKÁRÓL szól, tehát a megbízás tárgya, az összeg és
a teljesítés ideje ugyanaz - amit az eseti szerződésbe egyszer beírtak, azt a
TIG-nél nem kell még egyszer begépelni. A TIG űrlapja ezért a fél **eseti
szerződéséből** töltődik elő (a tételenkénti összegekkel együtt), és a mentett
piszkozat is onnan indul, ha még nincs saját adata.

A sorrend, amiből az űrlap dolgozik:

1. a **mentett TIG-piszkozat** - ha van, azon dolgoztak, az az igazság;
2. a fél **eseti szerződése** ezen a projekten;
3. a fél saját adatai + a projekt forgatási dátumából képzett teljesítés-szöveg.

Ez **előtöltés, nem kényszer**: minden mező szerkeszthető marad, a TIG mentése
pedig a saját adatait írja - a szerződéshez nem nyúl. A felület ki is írja, ha
az adatok a szerződésből jöttek, hogy ne tűnjön varázslatnak.

A **kihagyott** szerződés kimarad a forrásból: ott épp az a lényeg, hogy nem
készült papír, tehát nincs is mit átemelni. Ha egy félnek több szerződése fedi
a projektet (egy elrontott és egy javított), a legutóbbit vesszük
(`subcontractor_contracts.eseti_szerzodesek_a_projekten`).

### A kétlépéses életciklus

Szerződésnél és TIG-nél azonos, a régi Notion-os "Adatok átemelése" →
"Szerződés készítése és küldése" gombpáros mintájára:

- **Mentés** - az adatok egy "Készítés alatt" állapotú sorba kerülnek. Nincs
  PDF, nincs email; bármikor be lehet zárni és később folytatni.
- **Generálás és küldés** - ugyanez elmentve, majd azonnal PDF + kiküldés
  (`services/gdoc_template.py` + `services/google_email.py`). Előtte felugró
  **áttekintő** mutatja, pontosan milyen adatokkal megy ki a papír, és kinek:
  a generálás és az e-mail egy lépésben fut, tehát egy elgépelt adószám már a
  megbízottnál landol, és csak új papírral javítható. A **hiányzó** mezők
  kiemelve látszanak - az üres hely a dokumentumon a legkésőbb észrevett hiba -,
  de a küldés attól még mehet: van, amit tényleg nem kell kitölteni.
- **Kihagyás** - lezárja az adott felet erre a projektre nézve, papír nélkül.
- **Saját, kész papír feltöltése** - ha a dokumentum máshol készült, fel lehet
  tölteni generálás helyett (`components/SajatPapirFeltoltes.tsx`).

### Aki kimarad a papírozásból

Két, egymástól független ok van rá:

- **Projekt kiadásként elszámolva** - valaki ott volt a forgatáson, de nem
  résztvevőként számoljuk el: technikát hozott, és a díja a bérleti árban már
  benne van. Tőle nincs mit szerződni és igazolni. A jelölő a (projekt, ember)
  páron él (`ProjectSzamlazo.kiadaskent_elszamolva`), a számlázó fél felülírása
  mellett - **stábtag marad**: kap diszpót, rajta van a projekten. Utólag is
  átjelölhető mindkét irányba, mert sokszor csak a számla megérkezésekor derül
  ki, hogy valakinek a díja már egy másik tételben szerepel. Ha már készült róla
  TIG, előbb azt kell rendezni.

  A jelöléshez **kötelező megadni, hova és miért került** a kiadásba
  (`kiadas_megjegyzes`) - enélkül a jelölés csak annyit mondana, hogy tőle nem
  kell papír, azt nem, hogy hol keressük a pénzt. A magyarázat külön mezőben él,
  nem a számlázó-megjegyzésben: azt a számlázó fél beállítása írja, és egy
  számlázó-módosítás elfújná.
- **Belsős munkatárs** - havi bérezésű, nála nincs projektenkénti papír.

### A lezárás három módja

Egy fél háromféleképp kerülhet le a teendő-listáról:

| Mód | Mit jelent | Indoklás |
|---|---|---|
| **Kiküldve** | Elkészült és kiment a papír | – |
| **Kihagyva** | Egyáltalán NINCS papír, szándékosan | **kötelező** |
| **Van már szerződés** | A papír létezik, csak nem itt készült | opcionális |

A harmadik a Notionból áthozott soroké: gyakran van már érvényes, aláírt
szerződés, a rendszer mégis kérné. A "Kihagyva" erre hazugság volna - az azt
jelenti, hogy nincs szerződés -, és a kettőt utólag nem lehetne szétválogatni.
Lezáró állapot, tehát a TIG-fázis megnyílik utána, de aláírt példányt nem várunk
vissza tőle: nem mi küldtük ki.

A **kihagyás indoklása kötelező** (szerződésnél és TIG-nél is): a puszta
"Kihagyva" jelölésről fél év múlva senki nem tudná megmondani, szándékos volt-e
vagy elfelejtődött. Az indok külön mezőbe kerül (`kihagyas_oka`), nem a
Notionból örökölt általános megjegyzésbe, és a listán a jelölés mellett látszik.

### A kiküldött szerződést aláírva visszavárjuk

A kiküldés nem zárja le az ügyet: a papírnak vissza is kell érkeznie aláírva.
Amíg az aláírt példány nincs feltöltve (`POST .../{szamlazo}/alairt-fajl`), a
projekt az utókövetésben az **„Aláírt szerződésre vár”** oszlopban áll, és nem
lehet „Kész”.

Két külön mező, és ez a különbség lényeges:

- `szerzodes_file_url` - a **mi** dokumentumunk (generált, vagy generálás
  helyett feltöltött saját papír),
- `alairt_file_url` + `alairva` - a **visszaérkező**, aláírt példány.

A kettő egyszerre is létezik, ezért az aláírt feltöltése nem nyúl a szerződés
állapotához: a „Kiküldve” attól még igaz marad.

Csak a **kiküldött** szerződéseket várjuk vissza: a „Kihagyva” jelölésnél nincs
papír, a keretszerződéssel mentesülőknél pedig eseti szerződés sem készült.

A fázis-sorrendben az aláírás-várás **a sor végén** áll (utalás után,
„Kész” előtt), nem a szerződés mellett. Ez tudatos: a kiküldött szerződés elég
ahhoz, hogy a TIG és a kifizetés elinduljon, tehát egy visszavárt aláírás nem
takarhatja el a sürgősebb teendőket - viszont megakadályozza, hogy egy projekt
lezártnak látsszon úgy, hogy a papír sosem jött vissza.

### A kész papír javítható és törölhető

Egy már kiküldött szerződés vagy TIG nem zárt le véglegesen - az Utókövetés
oldalról (és a projekt adatlapjáról) mindkettőnél két út van:

- **Állapot visszavétele "Készítés alatt"-ra** → a fél visszakerül a
  teendő-listára, az adatai újra szerkeszthetők, a papír újragenerálható.
  Végpontok: `POST .../{project_id}/{szamlazo}/allapot` - szerződésnél és
  TIG-nél azonos alakban.
- **Törlés** → a bejegyzés megszűnik, tiszta lappal lehet újrakezdeni.
  Két védelem van rajta: olyan TIG-et nem törlünk, amihez **Kiadás sor**
  tartozik a Pénzügyben (az pénzügyi tény - előbb ott kell törölni, lásd
  [07-penzugyek.md](07-penzugyek.md#a-kifizetés-és-a-kiadás-sor-két-külön-dolog)),
  és olyan szerződést sem, amihez a projekten már készült TIG - előbb a TIG-et
  kell törölni, hogy a fázisok ne csússzanak egymásba.

### A kiküldött TIG után: számla, határidő, kifizetés

A kiküldött TIG-hez tetszőleges számú **számla** tölthető fel
(`components/TigInvoiceManager.tsx`), de csak úgy, hogy közben megadják a
számlán szereplő **fizetési határidőt**: amíg a sor dátum-mezője üres, elő sem
jön a fájlválasztó (és a backend is elutasítja a feltöltést). Utólag ugyanott
átírható. A "Kifizetve jelölés" ablakában pedig az adható meg, **mikor ment el a
pénz** (alapból a mai nap, de visszadátumozható). A két dátum a papíron és a
belőle keletkező Kiadás soron is ott lesz - részletesen lásd
[07-penzugyek.md](07-penzugyek.md#a-számla-két-dátuma-határidő-és-utalás-napja).

**A számla is EGYBEN megy, ha a papír több forgatásra szól.** Ugyanaz a
szabály, mint fentebb a szerződésnél és a TIG-nél: a számla és a kifizetés a
PAPÍRHOZ tartozik, nem a projekthez. Ezért bármelyik érintett forgatás oldalán
ugyanaz az egy sor jelenik meg, egy feltöltés elég, és egy "kifizetve" jelölés
zárja le mindet - egyetlen Kiadás sorral, nem naponta eggyel. A sor a név alatt
ki is írja, mit fed ("3 forgatás egy számlán: …"), különben a másik nap oldalán
úgy tűnne, hogy oda külön számlát kell kérni, és valaki feltöltene egy
másodikat.

**A számla-lépés kihagyható**, ugyanúgy indoklással, mint a szerződés és a TIG
kihagyása. Van, amikor a papír elkészült, de a pénz útja itt nem folytatódik:
máshol számolták el, elengedték, beszámították egy másik tételbe. Enélkül az
ilyen munkák örökre "nincs kifizetve" állapotban lógtak az utókövetésben, és a
projekt sosem lett kész - pedig nem volt rajta teendő. A kihagyott TIG kiesik az
utókövetés kifizetés-fázisából (a nevezőből is), az indok pedig ott marad a
soron, és bármikor visszavonható ("Mégis kérünk számlát").

Amihez **már tartozik Kiadás sor** a Pénzügyben, azt nem lehet kihagyni: az
pénzügyi tény, amit előbb ott kell rendezni - a Kiadás törlése ezt a TIG-et is
visszadobja "nincs kifizetve" állapotba, és onnantól a kihagyás is megy.

### Kiküldés előtti áttekintő

Szerződésnél és TIG-nél (külsősnél és belsősnél egyaránt) a "Generálás és
kiküldés" nem indul azonnal: előbb felugrik, hogy **pontosan milyen adatokkal**
megy ki a papír, és kinek. A generálás egy Google Docs sablon kitöltése +
azonnali e-mail - ami egyszer elment, az már a megbízottnál van, és csak új
papírral javítható. Az üres mezőket az ablak kiemelve mutatja (azok üres helyként
kerülnének a dokumentumra), de a küldés attól még engedélyezett: van, amit
tényleg nem kell kitölteni - csak legyen tudatos döntés.

Komponens: `components/KuldesEllenorzo.tsx`. A soroknak PONTOSAN azt kell
tükrözniük, amit a backend a sablonba behelyettesít (`fields` szótár a
`generalas-es-kuldes` végpontokban) - ha ott új mező kerül a sablonba, ide is be
kell venni, különben az áttekintő hazudik.

### Tételek: több ember, több projekt egy papíron

Az eseti szerződés (`ContractTetel`) és a TIG (`PerformanceCertificateTetel`) is
**tételeken** keresztül mondja meg, kinek a munkáját melyik projekten fedi.
Segéd: `services/papir_tetelek.py`, frontend `components/PapirTetelValaszto.tsx`.

Egy visszafelé kompatibilis eset van, és ezt fontos tudni: a **tétel nélküli** sor
(Notion-importból, régi adatból, kézi adatbázis-javításból) pontosan azt fedi,
amiről a saját mezői szólnak - a saját projektjén a saját emberét. Ezt a szabályt
egy helyen tartja a `services/papir_fedettseg.py`, hogy a szerződés-oldal és a
TIG-oldal ugyanúgy lássa. Enélkül egy import után készült papír "nem létezőnek"
látszana, és a rendszer újra kérné.

## Belsős TIG - havi, nem projektenkénti

`/api/v1/belsos-tig`, oldal: `/belsos-tig`. Minden belsős embernek **pontosan egy**
TIG-je kell havonta, függetlenül attól, hány projekten dolgozott. Ezért a végpontok
nem projektre, hanem `(employee_id, év, hónap)` hármasra épülnek.

Amit tudni kell:

- **Visszafelé készül**: mindig az *előző* hónapé az aktuális feladat - júliusban a
  júniusi. Az admin oldal ezért alapból az előző hónapot mutatja, és felsorolja az
  **összes** belsős munkatársat: akinek még nincs TIG-je arra a hónapra, azt vagy
  létre kell hozni, vagy kihagyni (ha épp nem dolgozott).
- **A hónapot a teljesítés dátuma dönti el**, mégpedig az azt megelőző hónapot
  (2026.07.20-i teljesítés = a 2026. **júniusi** TIG). Ha az admin átírja a
  teljesítési dátumot másik hónapra, a bejegyzés átkerül oda
  (`_apply_teljesites_honap`).
- A teljesítés és a fizetési határidő alapértéke a **következő hónap 20-a**
  (`services/hu_datum.tig_hatarido`).
- Kinek kell egyáltalán: `services/belsos_idoszak.kell_havi_tig()` - az
  `alkalmazott` jogviszonyúaknak nem (nekik bérszámfejtés van), és csak arra a
  hónapra, amikor tényleg belsős volt (lásd [04-csapat-felszereles.md](04-csapat-felszereles.md)).
- Havi tételek (fizetés, bónusz, levonás): `models/employee_monthly_item.py`,
  előjeles összegzéssel. Frontend: `components/BelsosTigManager.tsx`,
  `BelsosTigHaviAttekintes.tsx`, `BelsosTigEmployeeList.tsx`, `TigInvoiceManager.tsx`.

## Megrendelői papírozás

### Keretszerződés alatt: a PROJEKTKÓD kötése számít, nem az ügyfélé

Egy munka akkor van keretszerződés alatt, ha ahhoz a **projektkódhoz** oda van
kötve egy élő megrendelői keret (`ProjectCode.contract_id`). Nem elég, hogy az
ügyféllel van valahol keretszerződésünk.

Korábban az utóbbi döntött, és ez tömegesen hazudott: egyetlen kerettől a
megrendelő ÖSSZES munkája "keretszerződés alatt"-nak látszott. Ez a jelölés
viszont TEENDŐT tüntet el (eseti szerződést nem kérünk tőle), tehát tévesen
állítva pont a hiányzó papírokat rejti el.

A kötés két helyről jöhet:

- a **Notion-import** hozza a projektkód "Keretszerződés" relationjéből
  (`notion_import/importers.py`) - a Notionban minden projektkód-sor magától
  mutatja, tartozik-e kerethez;
- a **projektkód adatlapján** mondja ki valaki: a szerződés-kártyán ki lehet
  választani a keretszerződést (`components/megrendeloi/KeretKotes.tsx`,
  `POST /megrendeloi-papirok/keret-kotes/{project_code_id}`). Ügyfelet megadva
  a szerver keresi meg az élő keretét; ha nincs neki, azt meg is mondja, hogy
  eseti szerződés kell.

Ha megvan a kötés, a szerződés-lépés kész, és már csak a TIG van hátra - a
keret ugyanis arról szól, milyen feltételekkel dolgozunk együtt, a TIG arról,
hogy egy konkrét munka elkészült.


Ugyanaz a folyamat, mint az alvállalkozói oldalon, csak a **másik irányba** - a
megrendelő felé. Ezért ugyanazok a lépések is:

```
piszkozat mentése -> generálás és kiküldés -> aláírt példány feltöltése
                  \-> kihagyás (indokkal)   \-> saját papír feltöltése
```

Backend: `routes/megrendeloi_papirok.py` (eseti szerződés + TIG, egy modul két
`fajta` úton: `szerzodes` / `tig`), `routes/megrendeloi_keretszerzodesek.py`,
a szabályok pedig `services/megrendeloi_papir.py`-ben.
Frontend: `components/megrendeloi/` (`MegrendeloiPapirKezelo`, `PapirKapcsolok`,
`KeretszerzodesKezelo`, `MegrendeloiPapirokOldal`).

### Mennyiért vállaltuk - egy hely, egy szabály

A projektkód adatlapján saját kártya kéri be, **mennyiért ment ez a munka**:
nettó összeg + "+ÁFA" jelölő (`components/projektkod/VallalasiAr.tsx`, a
projektkód `netto_osszeg` / `plusz_afa` mezői). Azért külön, jól látható
helyen, mert az összeget gyakran **más tudja**, mint aki a szerződést és a
TIG-et készíti - eddig viszont csak egy papír szerkesztő-űrlapján (vagy a
mezőrács mélyén) lehetett megadni.

Ugyanez a szám tölti elő a szerződést és a TIG-et, ebből számol a számla-lépés,
és ebből lesz a projekt bevétele ott, ahol nincs bevétel-sor. A sorrend egy
helyen él (`services/projektkod_osszeg.py`), hogy a három felület ne mondjon
hármat:

1. a **TIG** összege (azt igazoltuk, arról megy a számla),
2. az **eseti szerződés** összege,
3. a **projektkód** saját mezői.

A bruttót sehol nem tároljuk: a "+ÁFA" jelölőből számoljuk (×1,27) - és csak
kiírjuk. Az elszámolásban (bevétel, költség, profit) mindenütt a **nettó** a
mérvadó, lásd [07-penzugyek.md](07-penzugyek.md) "A NETTÓ a mérvadó".

### A harmadik lépés: a SZÁMLA (határidő → kifizetve → bevétel)

A szerződés és a TIG után jön a pénz. A projektkód adatlapján a "3. Számla"
kártya ezt viszi végig (`services/megrendeloi_szamla.py`,
`components/megrendeloi/MegrendeloiSzamla.tsx`):

1. **A számla PDF-je** feltölthető (vagy a Notionból örökölt címen nyitható).
2. **Fizetési határidő** - a számlán szereplő nap. A "Kifizetve" gomb addig
   nem aktív, amíg ez nincs meg: a határidő az EGYETLEN dolog, amiből látszik,
   hogy egy még ki nem fizetett számla késik-e. Ha csak a kifizetés napját
   rögzítenénk, a lejárt számlák pont addig lennének láthatatlanok, amíg
   számít.
3. **"Kifizetve"** - a párbeszéd bekéri, MIKOR érkezett meg a pénz (nem a mai
   napot feltételezzük: a jelölés rendszerint napokkal a beérkezés után
   történik, és egy rossz nap rossz hónapba viszi a bevételt).
4. **Bevétel-sor keletkezik** a Pénzügyekben - a dátumokkal, az összeggel (a
   TIG-ről, annak híján a szerződésről vagy a projektkódról) és a számla
   fájljával. Eddig ez két külön felület volt: a projektkódon ki volt pipálva
   a kifizetés, a bevételt viszont valakinek kézzel kellett felvezetnie - és
   ha elmaradt, a projekt profitja hazudott. Meglévő bevétel-sort nem
   duplázunk, csak kiegészítünk.

**"Kifizetve, de ne kerüljön a bevételek közé"**: van munka, ami ki van
fizetve, de a Pénzügyekbe nem való (beszámították, másik cégen át folyt be,
máshol el van könyvelve) - ott egy itteni sor megkétszerezné az összeget.
Ilyenkor a jelöléshez **indok kell** (`ProjectCode.bevetelbe_ne_keruljon` +
`bevetel_kihagyas_oka`), és a projektkód így is lezártnak számít
(`bevetel_kifizetve`), tehát nem áll örökre a teendők között.

**Az összeg ilyenkor is beleszámít a PROJEKT bevételébe.** A pénz megjött; csak
a Pénzügyek nyilvántartásába nem való, mert ott duplázna. Ha ezt nem
számolnánk, ezeknél a munkáknál nulla bevétel és csupa veszteség látszana -
vagyis pont a profit hazudna arról, amiért ez a szám van. Ezért a
`ProjectCode.bevetel` bevétel-sor híján a vállalási ár **nettóját** veszi (lásd
fent), a számla-kártya pedig ki is írja: *"A projekt bevételébe beleszámít: …
nettó – ez adja a fenti profitot, bevétel-sor nélkül."* A Pénzügyek összesítői
viszont változatlanul csak a valódi bevétel-sorokból dolgoznak.

A téves gombnyomás visszavonható: a kifizetés dátuma lekerül a projektkódról
és a bevétel-sorról is, de magát a sort nem töröljük (lehet, hogy máshonnan
való, és a törlés visszahozhatatlan).

### Ami nem a megszokott módon van elszámolva

Van munka, amiről **nem lesz papír**: nincs szerződés, nincs TIG, és számla
sem - a pénz mégis rendeződik (beszámítás, csere, egy másik cégen át). Erre
három, egymástól független jelölés van, mert három külön kérdésről van szó:

| Jelölés | Hol | Mit old fel |
|---|---|---|
| **"Nem lesz ilyen papír (kihagyás)"** | a szerződés és a TIG kártyáján, egy kattintás + indok | az adott papírt nem várjuk |
| **"Nincs számla erről a munkáról"** | a "3. Számla" kártyán, indokkal (`ProjectCode.szamla_kihagyva`) | nem kell fizetési határidő a kifizetés jelöléséhez |
| **"Papír nélkül elszámolt"** | a projektkód alján, indokkal (`papir_nelkul`) | az egészet: szerződés, TIG és a határidő sem kell |

A kihagyás **egy kattintás**: korábban a "nem lesz papír" döntéshez előbb meg
kellett nyitni a teljes szerkesztő-űrlapot (cégadatokkal, összeggel), hogy
aztán ne töltsük ki - pedig ez nem szerkesztés, hanem döntés.

Mindegyikhez **indok kell**, és mindegyik ott marad a kártyán: fél év múlva ez
az egyetlen dolog, amiből kiderül, mi történt. Ezekkel a jelölésekkel a
projektkód **lezártnak számít** (nem áll örökre a teendők között), akkor is,
ha soha nem keletkezett hozzá papír vagy bevétel-sor.

### Kell-e egyáltalán papír?

A projektkódon **két külön kapcsoló** dönti el, szándékosan nem egy:

| Kapcsoló | Mit jelent | Papír |
|---|---|---|
| `van_szerzodes` (alap: igen) | Van-e szerződés a projekt mögött | Ha igen: eseti szerződés **és** TIG jár hozzá |
| `papir_nelkul` + **kötelező indok** | Van ügylet, de nem pénzmozgással rendeződik | Nincs, mert értelmezhetetlen |

A `papir_nelkul` esete: a cégvezető be van jelentve a megrendelőhöz
vállalkozóként, és annyival kevesebb fizetést vesz fel onnan - a bevétel ilyenkor
**nem bejövő pénz, hanem el nem költött pénz**. A kettő azért nem egy mező, mert
az egyik azt mondja, hogy NINCS ügylet, a másik azt, hogy VAN, csak másképp
számolódik el; a pénzügyi képük is más.

Az indok a bekapcsoláshoz kötelező (`routes/project_codes.py`
`_papir_kapcsolok_ellenorzese`, a CRUD-generátor `before_update` horgán) -
enélkül fél év múlva csak annyi látszana, hogy erről az egy munkáról nincs papír,
és nem lehetne megkülönböztetni a döntést a mulasztástól. Kikapcsoláskor az indok
**megmarad**, hogy egy véletlen billentés ne törölje.

### Ki a szerződő fél?

A papír a cégadatokat **lemásolja** magának, nem hivatkozza - a kiküldött papíron
az van, ami a küldés pillanatában igaz volt. Az előtöltés
(`szerzodo_fel_adatai()`) a megbízhatóság sorrendjében keres:

1. kifejezetten megadott **keretszerződés** (ott a cégadatok már kimentek egy
   aláírt papíron),
2. kifejezetten megadott **ügyfél** (a megrendelői kontaktok cége),
3. a **projektkód ügyfele** - ez az alapeset,
4. a projektkódra Notionból örökölt megrendelő-mezők - csak ha máshonnan semmi
   nincs (lapos szövegek import-korból, nem tudni, mikor frissültek).

A **kontakt csak az e-mail címet adja**: a levél egy embernek megy, a cégadat a
cégé. A felületen utána minden mező szerkeszthető.

### Keretszerződés vs. TIG

Az **élő** megrendelői keretszerződés kiváltja az eseti szerződést, a TIG-et
**nem**: a keret arról szól, milyen feltételekkel dolgozunk együtt, a TIG arról,
hogy egy konkrét munka elkészült.

Ez a szabály egy helyen él (`PapirAllas.szerzodes_kell`), és MINDENHOL ez
számít: a dashboard teendői, a projektkód-lista papírozás-jelzői és a Teendők
oszlopai is innen tudják, hogy egy keretes megrendelőnél nem hiányzik az eseti
szerződés - csak a TIG. Korábban a felület a papír puszta hiányát nézte, ezért
a keret alatt futó munkákat is szerződés-teendőként hozta fel. Ugyanez a
szabály az alvállalkozói oldalon már megvolt (lásd fent).

Az érvényesség saját függvényt kapott (`megrendeloi_keret_ervenyes()`), mert a
`models/contract.keretszerzodes_ervenyes()` az alvállalkozói oldalé: ott a
`keretszerzodes` jelölő különbözteti meg a keretet az esetitől, ezért
`tipus == ALVALLALKOZOI`-t vár - egy megrendelői keret (`tipus =
KERETSZERZODES`) azon a szűrőn sosem menne át, és a "fedi-e a keret ezt a
projektet" kérdésre mindig némán nem lenne a válasz.

Az adat maga már megvolt: a Notion "Keretszerződés" adatbázisa a `Contract`
táblába importálódik - ez a modul a felületet és a kiküldést adja hozzá. Ha egy
papír keretszerződésre hivatkozik, a projektkód `contract_id`-ja is odaköt (ha
még üres) - ebből számol a keret-oldal "hány projektkódnál használjuk"
számlálója.

Ugyanez a kapcsolat a Notionban a **keretszerződés felől** is meg van adva
(`HYPE ADMIN projektkódok`), és az importnak azt is olvasnia kell: a projektkód
saját `Keretszerződés` mezője akkor oldódna fel, amikor a keretszerződések még
nincsenek bent, tehát üresen maradt. Emiatt jött be a 28 keret úgy, hogy
**egyikhez sem tartozott projekt** - a javítás a
[10-integraciok.md](10-integraciok.md) *"Kétirányú relation"* szakaszában.

### A keretszerződés adatlapja

A listasorból csak annyi látszott, hogy "3 projektkódnál használjuk" - hogy
melyik háromnál és mi a helyzet velük, sehol. A cégnévre (vagy a *Megnyitás*-ra)
kattintva ezért felugrik az adatlap (`GET /megrendeloi-keretszerzodesek/{id}`,
`components/megrendeloi/KeretszerzodesModal.tsx`): a keret saját adatai, és
alattuk **minden projekt, amit lefed** - projektenként azzal együtt, hol tart a
szerződése és a teljesítési igazolása, mennyi a nettó, és megnyitható-e a papír.

Az adatlap a **feltöltött fájlokat is felsorolja** - nem csak a két nevesített
mezőt (`file_url`, `alairt_file_url`). A Notion-import a lap ÖSSZES fájlját
áthozza a tárhelyünkre és a rekordhoz csatolja (lásd
`notion_import/files.atemel_mindent`), csak ezekre eddig nem volt hova ránézni:
az aláírt példány, a mellékletek és a korábbi verziók átjöttek, de a felületen
nem látszottak. Ugyanígy megjelenik a Notion "Name" mezője és a szerződés
megjegyzése is.

A **projektkódok papírjai** tekintetében a nézet olvasó: azokat a projektkód
adatlapján lehet szerkeszteni, ahová innen egy kattintással el lehet jutni.
Ugyanaz a papír két helyen szerkesztve előbb-utóbb két különböző viselkedést
jelentene. A szerződésmódosítás viszont itt intézhető (lásd lent) - az magához
a kerethez tartozik, nincs másik hely, ahol dolga lenne.

### Aláírva visszavárjuk - dokumentumonként

A keretszerződés és **minden módosítása külön papír, külön aláírással**. Ezért
nem egyetlen "aláírásra vár" jelölés van a szerződésen, hanem
**dokumentumonként** egy sor: abból sosem derülne ki, hogy magát a szerződést
várjuk-e még, vagy a tavaly kiküldött módosítást.

A **céges keretszerződéseknél** (`/penzugyek/keretszerzodesek`) ez külön
oszlop: kiírja, hány papírt várunk vissza, és fajtánként-dátumonként azt is,
melyiket (`GET /contracts/keretszerzodesek/alairas-allapot`). A sorból nyíló
kezelőben tölthető fel a hiányzó aláírt példány - a szerződésé és a
módosításoké külön-külön -, és ott vehető fel új módosító dokumentum is.

Mikor várunk vissza valamit? Ha a papír **kiment** (a rendszerből küldve, vagy
egyszerűen: van dokumentuma), és **nincs aláírt példánya**. Papír nélküli
sornál nem állítjuk, hogy várunk valamit - ott még nem ment ki semmi.

A **módosítás-végpontok közösek** a megrendelői és a céges oldal között
(`routes/keret_modositasok.py`), mert a folyamat is ugyanaz. Egy különbség
van: a céges oldalon **nincs sablonból generálás**. A meglévő sablon a
megrendelői viszonyra szól (ott mi vagyunk a megbízott), egy alvállalkozói
keret módosításán viszont a szerepek fordítottak - abból ott hibás papír
lenne. Ezen az oldalon a kész módosító dokumentum feltölthető, és onnantól
ugyanúgy aláírásra vár.

### Szerződésmódosítás

Egy keretszerződést az évek alatt **többször is módosítanak** (székhely,
cégjegyzékszám, díjazás), és mindegyik módosítás önálló papír: saját
keltezéssel, kiküldéssel és aláírt példánnyal. Ezért külön tábla
(`keret_modositasok`), nem néhány mező a `contracts`-on - egyetlen
`modositas_file_url` a másodiknál felülírná az elsőt, és pont az veszne el,
amit a szerződés mellé évekig meg kell őrizni.

A folyamat ugyanaz, mint a keretszerződésé (Google Docs sablon → PDF → Drive
mappa → e-mail), **három ponton** tér el:

1. **Más címről megy.** Ahogy maga a keretszerződés is: a levél az admin
   fiókból indul (`MODOSITAS_SENDER`,
   alapból `admin@hypest.hu`), az aláírása pedig az abban a fiókban **beállított
   Gmail-aláírás** - nem egy külön, itt karbantartott szöveg. Ha valaki a
   Gmailben átírja az aláírást, a HYPE OS-ből kimenő levél is azzal megy. Ha a
   beállítás nem olvasható (a token nem kapta meg a jogot), a levél attól még
   kimegy, csak a beépített tartalék aláírással: egy hiányzó aláírás nem ér
   annyit, hogy egy kiküldés elhasaljon rajta.
2. **Nem a kiküldés a végállomás.** A módosítás akkor ér valamit, ha **aláírva
   visszajött**, ezért az útja `Készítés alatt → Aláírásra vár → Kész`, és a
   folyamatot az aláírt példány feltöltése zárja le. (A többi papírnál a
   "Kiküldve" a végállapot, mert ott a kiküldés a lényeg.)
3. **Több is lehet belőle** ugyanazon a kereten - minden kiküldés új sort nyit.
4. **Három mezőt a kiküldés előtt bekérünk.** A sablon a cégadatokon felül a
   módosítás **keltezését**, a **megbízás tárgyát** és azt kéri, hogy **mikor
   jött létre az eredeti szerződés** - a szövege ezekre hivatkozik vissza
   ("… -án/én Megbízási Szerződést kötöttek … feladatok ellátása tárgyában").
   A keret adataiból előtöltjük (megbízás tárgya, illetve a keret keltezése),
   de módosításonként más lehet, ezért a küldő ablakban szerkeszthető - és ott
   is látszik, hogyan folytatódik velük a mondat. Mindhárom **pillanatképként**
   a módosítás sorára kerül, mint a többi papíradat: egy későbbi
   keret-szerkesztés nem írja át, ami már kiment.
5. **A kísérőlevelet a felhasználó írja.** A többi papír fix szöveggel megy; itt
   a levél maga is része az ügynek (mit módosítunk, mire hivatkozva), ezért a
   kiküldési ablakban szerkeszthető - alapszöveggel nyílik, hogy ne nulláról
   kelljen kezdeni. Amit kiküldtünk, azt el is tesszük (`level_szoveg`), és az
   adatlapon visszaolvasható: fél év múlva az a kérdés, hogy MIT írtunk nekik.
   A szöveget sima szövegként írjuk, a levéltörzs HTML-jét a backend állítja
   elő belőle - **escape-elve**, hogy egy `<` jel vagy beillesztett részlet ne
   tudja elrontani a levél szerkezetét. Az **aláírás** nincs a mezőben: azt
   mindig a küldő fiók Gmail-beállításából tesszük a végére.

A küldő cím a Gmailben legyen a fiók saját címe vagy **felvett álneve**
(Beállítások → Fiókok → Küldés mint); egyébként a Gmail elutasítja a levelet,
és a felület pontosan ezt írja ki.

Ahol nem itt készült a papír, ott **saját módosítás is feltölthető** a generálás
helyett - ilyenkor nem megy ki levél, a sor rögtön aláírásra vár.

A kész PDF a `GDOC_KERET_MODOSITAS_FOLDER_ID` Drive mappájába kerül (alapból a
módosításoknak kijelölt mappa, env-ből átirányítható).

A keretszerződés törlése a módosításait is elviszi (adatbázisban cascade, a
feltöltött fájlok a tárhelyről).

### Törlés: a projekteknek megint kell szerződés

A keretszerződés **akkor is törölhető, ha projektkódok tartoznak hozzá**.
Korábban ilyenkor elutasítottuk ("előbb oldd le a projektkódokat") - csakhogy
leoldani sehol nem lehetett, tehát a felhasználó zsákutcába futott.

Most a törlés maga oldja le őket, és pontosan azt az állapotot állítja helyre,
ami keretszerződés nélkül igaz:

1. a projektkódok `contract_id`-ja kiürül;
2. azok a megrendelői szerződések, amiket **ezért a keretért** hagytak ki,
   újranyílnak ("Készítés alatt") - a kihagyás oka megszűnt, tehát a papír
   megint hiányzik. A korábbi indok nem vész el: átkerül a megjegyzésbe.

A már **kiküldött** papírokhoz nem nyúlunk, csak a keretre mutató hivatkozásukat
töröljük: ami egyszer kiment, az kiment. A **TIG-et** sem nyitjuk újra - azt a
keretszerződés úgysem váltotta ki, tehát egy kihagyott TIG-nek más oka volt.

A válasz megmondja, mi történt (`leoldott_projektkod`, `ujranyitott_papir`), a
felület pedig a megerősítő kérdésben előre kiírja a következményt.

### Sablonok

Mindhárom papírnak van Google Docs sablonja, és a placeholder-nevek a korábbi
Notion-programokéval **egyeznek**, tehát a meglévő sablonok változtatás nélkül
használhatók:

| Papír | Env változó | Placeholderek |
|---|---|---|
| Eseti szerződés | `GDOC_MEGRENDELOI_ESETI_TEMPLATE_ID` | `nev hely adoszam targy tido netto nettoki kelt afa nyilvszam kepvis projektnev napok` |
| TIG | `GDOC_MEGRENDELOI_TIG_TEMPLATE_ID` | ugyanaz `projektnev`/`napok` nélkül, plusz `projkod` |
| Keretszerződés | `GDOC_MEGRENDELOI_KERET_TEMPLATE_ID` | `nev hely adoszam targy kelt nyilvszam kepvis` |
| Szerződésmódosítás | `GDOC_KERET_MODOSITAS_TEMPLATE_ID` | `nev hely nyilvszam adoszam kepvis keltezes megbizastargya szerzodesletrejotte` |

### A Notionból örökölt papírok átvétele

A HYPE ADMIN projektkódok Notion-táblában minden projektnél ott van, hogy
készült-e megrendelői szerződés és TIG - névvel, dátummal, összeggel -, és oda
vannak feltöltve maguk a papírok is. Ezt a ProjectCode import már áthozta, de
**lapos mezőkbe** (`szerzodes_statusza`, `tig_statusza`, `megrendelo_neve`, …)
és általános csatolmányokba, amikből a rendszer nem tud papírt csinálni.

A `services/megrendeloi_papir_atvetel.py` ebből készít valódi
`MegrendeloiSzerzodes` / `MegrendeloiTig` rekordot. **Két helyről fut, ugyanaz
a kód:** a `c9e4a71b2f08` adatmigrációból (így a deploykor azonnal megvan,
Notion-hozzáférés nélkül) és az import-katalógus *"Megrendelői papírok"*
lépéséből (így egy újraimportálás naprakészen tartja).

Mikor számít késznek egy papír? A sorrend a bizonyíték erőssége:

1. **van feltöltött fájl** - ez a legerősebb, a régi sorokon az állapot sokszor
   elmaradt a valóságtól;
2. **az állapot-szöveg** - a tagadó jelzőket (`Nincs elkezdve`, `Készíthető a
   TIG`, `Keretszerződése van`) **előbb** vizsgáljuk, mint a "kész" jelzőket,
   mert részstringként azok is késznek látszanának;
3. **egyéb jelölő** (`TIG kiküldve`, `Szerződés küldés`).

Az átvett papír állapota **"Van már papír"**, nem "Kiküldve": megvan, csak nem
innen ment ki. A fájl az **aláírt példány** mezőbe kerül, mert a Notionba a kész,
aláírt dokumentumot töltötték fel.

A cégadatoknál itt a **Notion-örökség az elsődleges**, nem az ügyfél mai
adatlapja - fordítva, mint az új papírok előtöltésénél. Egy már megírt papír azt
kell hogy őrizze, ami rajta van: ha a cég azóta székhelyet váltott, a mai adat
visszamenőleg átírná a történelmet.

Idempotens, és a **kézzel készített papírhoz nem nyúl**: az átvett sorokat a
megjegyzésük KEZDETE különbözteti meg (`Notionból átvéve…`), ahol pedig a
felületen már csináltak papírt, ott az import nem készít mellé másodpéldányt.

#### Amit a Notion nem egyféleképp ad

A régi sorok azért látszottak hiányosnak, mert ugyanaz az adat többféle alakban
áll a Notionban. Az átvétel ezért mindegyiket megpróbálja:

- **A PDF címe** lehet sima `url`, `files` lista, vagy beágyazott objektum
  (`{"file": {"url": …}}`). Korábban csak a stringet fogadtuk el, így a TIG
  PDF-je "megvolt", de sehol nem lehetett megnyitni - ez volt a leggyakoribb
  panasz. Most az `_url()` mindhárom alakból kiszedi a címet, és a
  projektkód-import a "TIG url" mezőhöz feltöltött fájlt is a saját tárhelyünkre
  menti (a Notion linkje egy óra múlva lejár).
- **Az összeg** fele FORMULA vagy ROLLUP (`Nettó`, `Összesen nettó`,
  `Vállalási ár`, `Forintban`) - ezek beágyazott szerkezetként jönnek, nem
  számként. Az `_szam()` ezekből (és a "1 200 000 Ft" alakú szövegből) is
  kihozza az értéket; a papír-specifikus mezők után ezek a tartalékok.
- **A teljesítés ideje és a keltezés** a szöveges mező → formázott dátum →
  valódi dátum sorrendben áll össze.
- **Ami nem fér a papír mezőibe** (szerződés helye, speciális eset, TIG
  speciális), az a papír **megjegyzésébe** kerül - ott marad annál a papírnál,
  amelyikről szól, nem vész el a projektkód nyers mezői közt.

Ha egy régi papírról hiányzik a PDF vagy az adat, a sorrend: előbb a
**Projektkódok** import (ez tölti le a fájlokat a Notionból), utána a
**Megrendelői papírok** lépés (ez nem hív Notiont, a saját adatunkból dolgozik).
Mindkettő az admin import-panelről indítható külön is.

Ugyanez a lépés **köti be a keretszerződéseket az ügyfelükhöz**, ahol a Notionban
üresen maradt az "Akivel szerződünk" reláció: a hivatkozó projektkódok ügyfelét
veszi át - de csak ha mind ugyanaz, mert egy rossz kapcsolat rosszabb, mint a
hiányzó (némán elhagyná az eseti szerződést egy olyan cégnél, amelyikkel
valójában nincs keretünk).

**Mindhárom helyen saját papír is feltölthető** a generálás helyett: van, amit a
megrendelő ad a saját sablonjával, és van, ami még a rendszer előtti. Ilyenkor
nincs mit generálni és nincs kinek kiküldeni, csak rögzíteni - a feltöltés a
papírt egyben kiküldött állapotba is teszi, mert a folyamat innentől ugyanott
tart. Az aláírva visszakapott példány külön mezőbe megy: amíg az nincs meg, a
papír "aláírásra vár".

## Utókövetés - az összefoglaló nézet

`/api/v1/utokovetes`, oldal: `/utokovetes`. Egy helyen mutatja egy diszpózott
projekt teljes adminisztrációs "utóéletét":

- az eseti szerződések állapota,
- a teljesítési igazolások állapota,
- a forgatás utáni kérdőívre beérkezett válaszok (lásd [05-naptar-diszpo.md](05-naptar-diszpo.md)).

A tényleges mentés/generálás/küldés/kihagyás továbbra is a saját végpontjain fut -
ez a nézet csak összegyűjt, hogy ne kelljen projektenként két oldalt végignézni.
**A sorok számlázó felenként állnak**, nem emberenként.

Egy projekt a listából **felugró ablakban** nyílik, nem új oldalként
(`components/UtokovetesDetailModal.tsx`): a tartalom iframe-ben, az
`/embed/utokovetes/[id]` útvonalról jön, tehát szó szerint ugyanaz a nézet
minden művelettel együtt - így aki tíz projekten megy végig, nem veszíti el a
szűrését és a helyét a listában. Az ablak bezárása frissíti a mögötte lévő
táblázatot, hogy ne a régi állapot maradjon ott.

Emiatt szűnt meg az "Alvállalkozók szerződése" és a "Teljesítési igazolások"
külön menüpont: a műveletek megmaradtak, csak a jogosultságuk az Utókövetés
oldaláé lett. Frontend: `components/UtokovetesLista.tsx`, `UtokovetesNezetek.tsx`,
`UtokovetesTabla.tsx`.

## Dokumentum-generálás

Közös motor: `services/gdoc_template.py` - Google Docs sablon kitöltése,
PDF-export, tárolás. Sablononként külön env változó tartozik hozzá (külsős TIG,
belsős TIG, alvállalkozói szerződés, keretszerződés, diszpó) - lásd
[11-uzemeltetes.md](11-uzemeltetes.md).

A nettó összeg szöveges kiírását (a szerződések kötelező eleme) a
`services/hu_number_words.py` adja.
