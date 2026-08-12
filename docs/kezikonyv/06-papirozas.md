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

## Az alvállalkozói folyamat sorrendje

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
számlálója és a törlésvédelem.

### Sablonok

Mindhárom papírnak van Google Docs sablonja, és a placeholder-nevek a korábbi
Notion-programokéval **egyeznek**, tehát a meglévő sablonok változtatás nélkül
használhatók:

| Papír | Env változó | Placeholderek |
|---|---|---|
| Eseti szerződés | `GDOC_MEGRENDELOI_ESETI_TEMPLATE_ID` | `nev hely adoszam targy tido netto nettoki kelt afa nyilvszam kepvis projektnev napok` |
| TIG | `GDOC_MEGRENDELOI_TIG_TEMPLATE_ID` | ugyanaz `projektnev`/`napok` nélkül, plusz `projkod` |
| Keretszerződés | `GDOC_MEGRENDELOI_KERET_TEMPLATE_ID` | `nev hely adoszam targy kelt nyilvszam kepvis` |

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
