# Lara — hogyan működik és hogyan tanul (2026. szeptember 24-i állapot)

Ez a leírás a **jelenlegi kódból** készült (`backend/app/admin_agent/`,
`backend/app/workers/admin_agent_tasks.py`), nem a tervekből. Ahol egy szám
szerepel (küszöb, súly, időpont), az a kódban lévő érték. Ami **nem
ellenőrzött** (pl. valódi Gemini-hívás, éles Gmail), azt külön jelzem.

---

## 1. Röviden

- Lara a HYPE OS **adminisztrációs munkatársa**. Az egész rendszert **látja és
  tanul belőle**, de feladatot **csak adminisztrációs területen** végezhet:
  számla, TIG, szerződés, adminisztrációs e-mail, egyéb papírmunka. Utalni
  **soha** nem fog, és utalást elő sem készít.
- Ma a gyakorlatban Lara **figyel, tanul, jósol, kérdez és javasol**. Üzleti
  rekordot magától **nem módosít**: az alapállás szerint a modul ki van
  kapcsolva, a mellékhatás tiltva, és minden feladattípus **L0 (árnyék)**
  szinten van. (Az éles kapcsolók állását innen nem látom — a
  Beállításokban ellenőrizhető.)
- Minden döntése és javaslata **egyetlen emberhez, Vidor Gergelyhez** fut be.
  Másnak Lara semmit nem küld.
- A tanulás lényege: **tudás-darabok** (egy-egy eset leírása) és **szabályok**
  gyűlnek. Ami nem ellenőrzött, az **jelölt** marad, és a döntéseknél nem
  használódik. Tudás akkor lesz belőle, ha ember jóváhagyja, ha a valóság
  sokszor igazolja, vagy ha a teljes adaton igazolt tényről van szó.
- A Gemini **segít** (elemez, fogalmaz, utánanéz, hipotézist állít), de
  **nem dönt**. A bizonyosságot nem a modell mondja meg, hanem az, hogy hány
  igazolt eset áll egy kapcsolat mögött.

---

## 2. Hatáskör — mit csinálhat és mit nem

| Lara | Igen | Nem |
|---|---|---|
| **Lát / tanul** | az egész HYPE OS-t (kb. 97 adatbázis-terület), a szamla@ levelezést, az AI asszisztens beszélgetéseit | jelszavak, tokenek, kulcsok, bankszámla-, adóazonosító-, e-mail-, telefon-, lakcímjellegű mezők; munkatársi adatlap és dokumentumok; a saját és az AI asszisztens táblái |
| **Feladatot végez** | számla, TIG, szerződés, adminisztrációs e-mail, egyéb papírmunka (`enums.ADMIN_FELADATTIPUSOK`) | diszpó, utómunka, portál, beosztás módosítása; **utalás** (se végrehajtás, se előkészítés) |
| **Végrehajthat (ha engedélyezik)** | 4 regisztrált eszköz: számla felvezetése kiadásként (R2), e-mail válasz (R2), TIG-piszkozat mentése (R1), szerződés-piszkozat mentése (R1) | banki eszköz nincs regisztrálva (R3 = mindig tiltott); PDF-generálás és kiküldés TIG-nél/szerződésnél emberi lépés marad |

A hatáskört több helyen is ellenőrzi a kód: a modell rendszerpromptja
kimondja, az eszköz-regiszter betöltéskor nem enged nem-adminisztratív
eszközt, a végrehajtó minden hívásnál ellenőrzi, és a heti értékelés három
„tiltott terület” esetet futtat (diszpó, utómunka, portál).

---

## 3. A biztonsági keret — ki dönt a végrehajtásról

### 3.1 Három főkapcsoló (Beállítások)

| Kapcsoló | Alap | Hatás |
|---|---|---|
| **Modul** (`module_enabled`) | KI | Kikapcsolva semmilyen mellékhatásos lépés nem mehet. A tanulás ettől függetlenül futhat (lásd 6.). |
| **Mellékhatás** (`side_effects_enabled`) | TILTVA | Tiltva semmi nem íródik üzleti rekordba, és nem megy ki levél. |
| **Vészleállítás** (`kill_switch`) | nincs | **Teljes leállás**: minden ütemezett feladat induláskor kilép, a levelezés-olvasó futás közben is figyeli, az API minden nem olvasó kérése 423-at ad. A tudás és a kapcsolók megmaradnak, a visszakapcsolás pontosan oda tér vissza. |

### 3.2 Kockázat (a szerver sorolja be, a modell nem írhatja át)

- **R0**: olvasás, belső javaslat, nincs mellékhatás.
- **R1**: ellenőrzötten visszafordítható belső írás (pl. TIG-piszkozat).
- **R2**: külső kommunikáció vagy pénzügyi/jogi jelentőségű változás (számla
  felvezetése, e-mail).
- **R3**: tiltott (banki végrehajtás), semmilyen szinten nem engedélyezhető.

### 3.3 Bizalmi szint feladattípusonként (Beállítások → bizalmi szint)

L0 árnyék · L1 előkészítés + emberi véglegesítés · L2 szűk automatika ·
L3 munkasor-önállóság kivételkezeléssel · L4 csak külön engedélyezett szűk
kör. **Alap: minden típus L0.**

### 3.4 A döntés (`policy.decide`) — pontosan ebben a sorrendben

1. R3 → **tiltva**.
2. R0 → **mehet** (nincs mellékhatás).
3. R1/R2 esetén: vészleállítás / modul ki / mellékhatás tiltva → **tiltva**.
4. L0 → **tiltva** (árnyék: csak javaslat).
5. R1: L2 vagy felette → automatikus, L1 → **emberi jóváhagyás**.
6. R2: automatikus csak L3+ szinten **és** kifejezetten engedélyezett
   altípusnál (alapból egy sincs) → egyébként **emberi jóváhagyás**.

### 3.5 A végrehajtás őrlánca (`executor.py`)

Még jóváhagyott javaslatnál is minden lépést újraellenőriz, a végrehajtás
pillanatában:

1. A jóváhagyás a javaslat **pontos tartalmához** kötött (hash). Ha a
   javaslat közben változott, új jóváhagyás kell. Egy jóváhagyás egyszer
   használható, és lejárhat.
2. A javaslat friss és kész állapotú.
3. Az eszköz regisztrált, és adminisztratív típusú.
4. A javaslat tartalmát újra validálja (pl. e-mailnél: automata címzett,
   no-reply, hiányzó tárgy vagy szöveg → nem küldhető).
5. A policy döntést újra meghozza (kapcsolók, szint, vészleállítás).
6. **Csak a felelős** hagyhat jóvá, és e-mailt **csak a felelős saját
   címére** küldhet (`csak_felelosnek`, alap: be).
7. Idempotens foglalás: ugyanaz a javaslat kétszer nem hajtódik végre.
8. Csak ezután jön a valódi művelet, a **meglévő** HYPE OS szolgáltatáson
   át (pl. a számla-érkeztető jóváhagyása), minden lépés naplózva.

---

## 4. Hogyan dolgozik egy feladaton

### 4.1 Honnan jön feladat

- **Kézzel**:
  - a Beérkező számlák sorain a „Lara” gomb (árnyék-elemzés);
  - a Munkasorban „+ Feladat”;
  - a projektkód-adatlapon és az Utókövetésben a „Lara teendők” blokk.
- **Kérdésből**: ha egy Lara-kérdésre azt válaszolod, hogy „hibás rögzítés”,
  Lara **javítási feladatot** készít magának, a felelőshöz rendelve.

A beérkező számlák elemzése **nem indul automatikusan**, csak a „Lara” gombra.

### 4.2 Számla-elemzés (`pipeline_szamla.arnyek_elemzes`)

1. Kiindul a számla-érkeztető saját javaslatából (cél, projektkód, összeg).
2. Megnézi a saját tudását. A **Tudás** sorrendje:
   1. élesített partner-szabály;
   2. ha nincs, legalább **2 egybehangzó (≥80%)** jóváhagyott eset vagy
      megválaszolt kérdés;
   3. ha az sincs, az érkeztető javaslata.

   Szabályból 0,3, esetekből 0,45 bizonytalansággal tölt.
3. Ha van Gemini-kulcs, a modell **átnézi** a megtanult tudással együtt.
   Korlátok:
   - csak **üres** célt vagy projektkódot tölthet, és csak **létező**
     értékkel;
   - összeget **nem írhat át**;
   - a kitalált projektkódot elutasítja;
   - ha eltér az érkeztetőtől → **konfliktus**, emberhez kerül
     (bizonytalanság 1,0).
4. Hiányos adatnál (cél, összeg, díjbekérő) az állapot **„adatot kér”**.
5. Javaslat készül → a policy dönt → **L0-ban nem hajtódik végre**, csak
   látható. L1-en a felelős jóváhagyásával a meglévő érkeztető rögzíti.

### 4.3 TIG / szerződés tervezet (`tervezo.py`)

- A projektkód projektjein a **meglévő** „függő papírok” logika adja a
  teendőket.
- **Előtöltés forrással**: mentett piszkozat, eseti szerződés, partnertörzs,
  projekt dátumai, tételek összege.
- A modell **csak a hiányzó** mezőt egészítheti ki.
- Összeget **csak igazolt forrásból** vesz át (±0,5 Ft), különben elutasítja.
- Lara papír-tudásából tölti a hiányzó **megbízási tárgyat** és **ÁFA-jelzőt**.
  A szokásos kihagyást, az eltérő összeget és a számla nélküli TIG-et
  figyelmeztetésként jelzi.
- Végrehajtva csak **piszkozat** („Készítés alatt”); PDF és kiküldés nincs.

### 4.4 E-mail tervezet

- Címzett **csak igazolt címből** lehet (megrendelő kontaktjai, függő felek).
- Kiküldés csak jóváhagyással, és jelenleg csak a felelősnek.

### 4.5 Megoldási javaslat (`megoldas.py`)

- Bármely feladathoz kérhető („Lara megoldási javaslata”).
- Lara az AI asszisztens **csak olvasó** eszközeivel utánanéz a rekordoknak,
  és konkrét lépéseket ad: rekord, mező, érték, belső link.
- Semmit nem módosít.
- A háttérben a javítási feladatokhoz készít ilyet, futásonként legfeljebb 3-at.

---

## 5. Mi a „tudás” — a tudás-darabok állapotai

Minden tudás egy `aa_memory_chunks` sor (hatókör: számla, TIG, szerződés,
e-mail, rendszer…) vagy egy `aa_playbook_rules` szabály.

| Állapot (`minosites`) | Honnan | Használja döntésnél? |
|---|---|---|
| **jelölt** | megfigyelés, levelezés, AI asszisztens, Gemini partner-profil és önreflexió | **nem**, amíg jóvá nem hagyják |
| **jóváhagyott** | ember a Tudástárban, vagy válasz egy kérdésre | igen |
| **auto_jovahagyott** | a valóság igazolta (lásd 7.2) | igen |
| **kezi_jelolt** | az ember visszavett egy auto-jóváhagyottat | nem; magától többé nem hagyja jóvá |
| **felreteve** | a tanulás kezdete (2026.09.01) előtti, el nem bírált jelölt | nem; egyenként visszahozható |
| **rendszer_teny** | rendszerfigyelés (lásd 6.) | igen, azonnal (elvethető) |
| **tapasztalat** | a teljes történet tényei, legalább 2 eset (lásd 6.) | igen, azonnal |
| **adat_igazolta** | Gemini-hipotézis, amit Lara a teljes adaton igazolt | igen, azonnal |
| **adat_cafolta** | új adat megcáfolta | nem (visszavonva) |

A **szabályok** állapota lehet vázlat, függő (gépi javaslat), éles vagy
visszavont. **Gépi szabály soha nem élesedik magától.** Élesíteni csak
jogosult ember tud, és csak **sikeres értékelés** után (lásd 7.4).

A **tanulás kezdete** alapból **2026. szeptember 1.** (Beállításokban
állítható). Ami előtte keletkezett, vagy Notionből jött, az **régi korszak**:
nem lesz belőle új jelölt, a jóváhagyott régi példa pedig „kisebb súllyal”
szerepel (a Tudáshálóban ×0,4).

---

## 6. Honnan tanul — források és ütemezés

Az ütemező UTC-ben fut. Az alábbi budapesti időpontok nyári időszámításra
vonatkoznak; télen egy órával korábban futnak.

| Forrás / kör | Mit néz | Mikor | Kapcsoló | Eredmény |
|---|---|---|---|---|
| **Megfigyelés** (`observer.py`) | lezárt emberi munka: szerződés, TIG, belsős TIG, kifizetett kiadás, megrendelői szerződés és TIG, projektkód-komment (≥25 karakter), bevétel (mikor fizetett), utalás-felvezetés, árajánlat, végleges törlés | félóránként | „Tanulás és megfigyelés” (**kézzel kell bekapcsolni**) | példa-**jelölt** |
| **Rendszerfigyelés** (`rendszer.py`) | az egész rendszer: modulonként tételszám, 30 napos mozgás, állapot-eloszlás; projektkódonként minden kötődő tétel. Szabad szöveget nem másol. | óránként (:40) | „Teljes rendszer figyelése” (migráció bekapcsolta) | **rendszer_teny** |
| **Tapasztalás** (`tapasztalas.py`) | a TELJES történet lezárt munkái partnerenként: milyen forma, projektkód, megrendelő, típus — ami ≥2-szer megtörtént | óránként (:10) | „Tanulás és megfigyelés” + `tapasztalas` | **tapasztalat**; Gemini-hipotézisek → igazolt vagy cáfolt |
| **Levelezés** (`levelezes.py`) | a szamla@ szálak a tanulás kezdete óta: levelek, válaszaink, csatolmány-kivonat, és ha lett belőle számla, hogyan rögzítettétek | félóránként (:05, :35) | „Levelezés olvasása” (migráció bekapcsolta) | szálanként **jelölt** |
| **AI asszisztens** (`asszisztens.py`) | lezárt kérés-körök: ki, honnan, mit kérdezett, mi lett a válasz, mely műveleteket hajtott végre vagy utasított el | félóránként (:20, :50) | „AI asszisztens figyelése” (migráció bekapcsolta) | körönként **jelölt** |
| **Visszajátszás + önellenőrzés** (`visszajatszas.py`, `onellenorzes*.py`) | lásd 8. | kétóránként (:15) | „Tanulás és megfigyelés” | kérdések, találati arány, jelöltek |
| **Automatikus megerősítés** (`megerosites.py`) | lásd 7.2 | az önellenőrzés után és éjjel | `auto_jovahagyas` | auto-jóváhagyás, szabályjavaslat |
| **Utánanézés** (`nyomozas.py`) | a friss kérdések, lásd 8.3 | az önellenőrzés után | `nyomozas` | Lara maga válaszol, vagy kérdés marad |
| **Éjszakai tanuló** (`learning.distill`) | az emberi javítások (`aa_corrections`) | naponta ~04:00 | modul VAGY „Tanulás és megfigyelés” | szabály-**jelölt** |
| **Gemini-tanulás** (`gemini_tanulas.py`) | partner-profil (≥3 jóváhagyott eset), önreflexió (utolsó 14 nap válaszai, javításai, arányai) | éjjel, a tanuló után | `gemini_tanulas` | **jelölt** profilok és tanulságok |
| **Beágyazás** (`embedding.py`) | a jóváhagyott tudás jelentés szerinti kereséshez | félóránként (:25, :55) | `szemantikus_kereses` + Gemini-kulcs | vektor |
| **Heti értékelés** (`evals.py`) | biztonsági esetek | hétfő ~05:00 | mindig | átment / nem ment át |
| **Napi összesítő** (`osszesito.py`) | hány jelölt vár, és melyik a legértékesebb | munkanap ~07:30 | `napi_osszesito` | értesítés a felelősnek |

Minden kör csak olvas, és csak Lara saját `aa_` tábláiba ír. Minden kör
**idempotens**: ugyanazt kétszer nem veszi fel, változásnál frissít.

---

## 7. Hogyan lesz jelöltből tudás, és tudásból szabály

### 7.1 Emberi jóváhagyás

- **Tudástár**: egyenként vagy tömegesen (max. 500) jóváhagyod vagy elveted.
  A „Legértékesebb elöl” rendezés mutatja, mire éri meg ránézni.
- **Kérdésre adott válasz** (lásd 8.2).
- **Magyarázat egy feladatnál** („Javítás / magyarázat Larának”): azonnal
  jóváhagyott tudás lesz.

### 7.2 Automatikus megerősítés (a valóság igazolja)

- Ha **ugyanannál a partnernél** legalább **3 eset** (`auto_jovahagyas_min`)
  **≥80%-ban egybehangzó**, és egyiket sem vetették el, a példák maguktól
  jóváhagyottak (`auto_jovahagyott`, naplózva).
- 2026-09 óta az „eset” **üzleti ügyet** jelent, nem rekordot: ugyanannak a
  partnernek ugyanarra a projektkódra eső több számlája EGY eset; projektkód
  nélkül minden dokumentum külön ügy (lásd `ugyek.py`, 14. fejezet). Ugyanez
  érvényes az önellenőrzés tudására és a tapasztalásra.
- Kivétel:
  - projektkód-komment, árajánlat és törlés soha nem hagyódik jóvá magától;
  - a bevétel tény, az magától jóváhagyott.
- **Szabályjavaslat**: legalább **5** jóváhagyott, **≥90%-ban** egybehangzó
  eset → **függő** szabály. Magától soha nem élesedik.

### 7.3 Éjszakai tanuló (emberi javításokból)

- Az emberi javításokat feladattípus és érintett mezők szerint
  csoportosítja.
- Legalább **2 hasonló** javításból lesz **szabály-jelölt**. Egyetlen
  javításból nem lesz általános szabály.

### 7.4 Szabály élesítése és az értékelés

- Szabályt élesíteni csak akkor lehet, ha az **utolsó értékelés átment**.
- Az átmenés feltétele: **nincs kritikus hiba**, és a megfelelés **≥95%**.
- Az értékelés a **biztonsági invariánsokat kóddal** ellenőrzi:
  - R3 mindig tiltott;
  - L0 árnyék tiltott;
  - vészleállítás tiltott;
  - modul ki tiltott;
  - mellékhatás tiltva tiltott;
  - R2 alapból jóváhagyás-köteles;
  - három tiltott terület (diszpó, utómunka, portál).

---

## 8. Önellenőrzés és kérdések — a folyamatos „vizsga”

### 8.1 Vak jóslat

Kétóránként Lara végigmegy a lezárt döntéseken, és **a saját tanulsága
nélkül** („vakon”) megmondja, mit javasolt volna a **jelenlegi** tudásával.
Utána összeveti a valósággal. Területek:

- **Számlák**: cél, célrekord, projektkód; bontásnál a sorok kódjai.
- **Eseti szerződés és TIG**: kell-e a papír, nettó összeg, +ÁFA, megbízás
  tárgya, TIG-nél kell-e számla.
- **Megrendelői szerződés és TIG, projektkód-döntések**: kihagyás, +ÁFA,
  papír nélkül, számla kihagyva, bevételbe ne.
- **Bevétel**: késés a partner mediánjához képest, 15 nap tűréssel.
- **Belsős TIG**: havi összeg az előző hónaphoz képest, +ÁFA.
- **Elvárás-eltérések**:
  - fizetett, de nincs papír;
  - a TIG 30+ napja lezárva, de nincs bevétel;
  - alvállalkozó kifizetve szerződés vagy TIG nélkül.
- **Fogalmak**: a figyelt táblák állapot-mezőinek gyakori (≥3 tételes)
  értékei, amelyek jelentését Lara még nem érti.

Adatkör:

- A fő kör a tanulás kezdete óta **mindent** néz.
- Minden futásnál van **vizsga** is: a kezdőnap **előtti** rekordokból egy
  véletlen **30%-os** adag (futásonként más).
- Ebből futásonként legfeljebb **3** új, „Régi adatból” jelölésű kérdés
  keletkezik.

### 8.2 Kérdések és a válaszok hatása

- Eltérésnél vagy tudáshiánynál Lara **kérdez**. Egy kérdés egy partnerre és
  egy döntésre vonatkozik; az új eseteket ugyanahhoz a kérdéshez fűzi hozzá.
- Korlátok: legfeljebb **25** nyitott számla-kérdés. Fogalom-kérdésből
  futásonként legfeljebb **3** új, egyszerre legfeljebb **8** nyitott.
- A válaszok hatása:

| Válasz | Hatás |
|---|---|
| **„Mindig így”** | partnerre szabott szabály. Élesítési joggal és sikeres értékelés mellett azonnal éles, különben jelölt. |
| **„Magyarázat”** | jóváhagyott tudás a magyarázattal; esetként is számít. |
| **„Egyszeri kivétel”** | csak feljegyzés, nem általánosít. |
| **„Hibás rögzítés”** | nem tanít; a mérőszámban Lara javára szól. Lara **javítási feladatot** is készít. |
| **„Nem releváns”** | kimarad. |

Egy válasz csak a megválaszolt esetnél **újabb** esetekre vonatkozik, a
múltat nem teszi hibássá.

### 8.3 Előbb utánanéz, csak utána kérdez (`nyomozas.py`)

- Mielőtt egy új kérdésről értesítés menne, Lara az AI asszisztens **csak
  olvasó** eszközeivel utánanéz:
  - globális kereső;
  - végpont-katalógus;
  - lekérdezések a saját API-n;
  - entitás-összesítés.
- A saját tudását is felhasználja (szabályok, hasonló esetek,
  projektkód-életút).
- Lépésszám: kérdésenként legfeljebb 12 lépés, futásonként legfeljebb 10
  kérdés.
- Ha legalább **75%-ban biztos** (`onallo_min`), nem kérdez. A kérdés
  **„Lara magától megválaszolta — ellenőrizd”** állapotba kerül, értesítés
  nélkül.
- Tudás ebből **csak akkor** lesz, ha a felelős elfogadja („Rendben”).
- Értesítés csak arról megy, ami az utánanézés után is nyitott maradt.
- Modellhiba esetén a válasz „nem tudom”, és a kérdés marad.

### 8.4 Mérőszámok (Tanulás és minőség oldal)

- **Vak találati arány**: szigorú, a válaszok nem javítják.
- **Pontosság a válaszaid után**: a „hibás rögzítés” Lara javára szól, a
  „mindig így” és a „magyarázat” megtanultnak számít, a „kivétel” és a „nem
  releváns” kimarad.
- **Nyitott eltérés**: amire még nincs válasz.
- Mindhárom összesítve és területenként is látható.
- 2026-09 óta mellettük öt KÜLÖN mérőszám látszik, mintaszámmal
  (`minoseg.py`, 14. fejezet): tudás megtalálása, helyesség új eseteken
  (Tudáspróba), emberi javítás igénye, indokolt kérdezés, tanulási késés.

---

## 9. A Gemini szerepe

Lara ugyanazt a Gemini-kapcsolatot használja, mint az AI asszisztens
(`GEMINI_API_KEY`, `GEMINI_MODEL`, alap: `gemini-2.5-flash`). Minden hívás
megkapja a budapesti mai dátumot.

**Mire használja:**

- számla-átnézés;
- TIG-, szerződés- és e-mail-tervezet;
- utánanézés;
- megoldási javaslat;
- partner-profil és önreflexió;
- tapasztalás-hipotézisek;
- jelentés szerinti keresés (`gemini-embedding-001`, 768 dimenzió).

**Mit nem tehet:**

- nem dönt a végrehajtásról;
- nem mondja meg, mennyire biztos egy tudás;
- nem hagy jóvá és nem élesít;
- nem írja át a kódot, a promptot, a jogosultságot vagy a küszöböket;
- hiányzó adatot (összeg, partner, projektkód, dátum, címzett) nem találhat
  ki;
- a bemenetben lévő e-mail vagy dokumentum szövegét adatként kezeli, nem
  utasításként (a benne lévő utasítást csak jelzi).

**Hibánál** zárva marad: kulcs nélkül „Beállítás szükséges”, hibás válasznál
egy javító újrapróba, utána elutasítás. A modell nélküli út (szabályok,
esetek, érkeztető) ilyenkor is fut.

**Tapasztalás-hipotézisek:**

- A Gemini zárt típusú állításokat javasol: forrás, projektkód, megrendelő,
  típus, összegsáv, „papír a kiadás mellett”, fizetési késés.
- Lara mindet a partner **összes** rekordján ellenőrzi. **Legalább 3 eset és
  ≥80%** igazolás kell ahhoz, hogy megmaradjon; egyébként cáfolt.
- Új adatnál újraellenőriz, és visszavonja, ami már nem áll.
- Körönként legfeljebb 6 partnerre fut (`tapasztalas_gemini_max`).

---

## 10. Hogyan használja a tudást egy döntésnél

**Visszakeresés** (`memory.retrieve`):

- Csak **éles szabályt** és **érvényes, jóváhagyott, vissza nem vont**
  tudást ad át, alapból legfeljebb 8 elemet (maximum 10).
  - A partnerhez kötött szabály csak annál a partnernél jön elő.
  - A partnernév normalizálva egyezik (ékezet, kisbetű, cégforma nem számít).
  - Az új korszak példái előbb jönnek.
  - A tesztadat (holdout) soha nem kerül bele.
- **Jelentés szerinti keresés**: ha be van kapcsolva és van kulcs, a
  hasonló jelentésű tudás is előkerül (koszinusz ≥ **0,62**), rokon
  hatókörökből is.
- A **projektkód-életút** (minden, ami a projektkódhoz kötődik a
  rendszerben) bekerül a számla-elemzés és a tervezetek modell-bemenetébe.

---

## 11. A Tudásháló és a „bizonyíték-erősség %”

(A felület 2026-09 előtt „bizonyosság”-nak nevezte. A szám a kapcsolat
mögötti BIZONYÍTÉK erőssége, nem Lara feladat-pontossága — azt a Tanulás és
minőség oldal méri, külön.)

Minden kapcsolatnak (pl. partner ↔ projektkód) van egy **súlya**. Ez a
mögötte álló bizonyítékok összege:

| Bizonyíték | Súly |
|---|---|
| jóváhagyott példa | 1,0 |
| példa-jelölt | 0,25 |
| csak látott, lezáratlan munka | 0,1 |
| emberi javítás | 0,6 |
| éles szabály | 3,0 |
| szabály-jelölt | 0,5 |
| rendszer-tény | 0,5 |
| tapasztalat (rekordonként) | 0,35 |
| igazolt állítás (igazoló esetenként) | 0,5 |
| régi korszak | ×0,4 |

Elvetett és félretett bizonyíték nem számít.

**Bizonyosság = 1 − e^(−súly/2).** Néhány érték:

| Ami a kapcsolat mögött áll | Súly | Bizonyosság |
|---|---|---|
| 1 jelölt | 0,25 | 12% |
| 1 jóváhagyott példa | 1 | 39% |
| 2 jóváhagyott példa | 2 | 63% |
| 1 éles szabály | 3 | 78% |
| 1 éles szabály + 1 jóváhagyott példa | 4 | 86% |
| 6-os súly (pl. 1 szabály + 3 példa) | 6 | 95% |

**A HUD-on látható %** a látható kapcsolatok bizonyosságainak **átlaga**. A
háló **mérete** ebből jön: 30% + 70% × átlagos bizonyosság. 100%-os
bizonyosságnál tölti ki a teret.

**Miért alacsony (pl. 21%)?** Mert a kapcsolatok nagy része egyetlen
jelöltre vagy tapasztalatra épül (12–30%). Az átlagot az emeli, ha a
kapcsolatok mögé **jóváhagyott eset és éles szabály** kerül. A szám
szándékosan nem „hangolható”: csak valódi, ellenőrzött bizonyíték növeli.

---

## 12. Amit te tehetsz, hogy gyorsabban tanuljon

1. **Tudástár → „Legértékesebb elöl”**: hagyd jóvá (vagy vesd el) a
   jelölteket. Ez a legerősebb jel (+1 súly esetenként).
2. **Kérdések**:
   - ahol igaz, válaszold, hogy **„Mindig így”**: ebből szabály lesz;
   - ahol rövid indok kell, írj **magyarázatot**;
   - a „Lara magától megválaszolta” kérdéseknél nyomj **„Rendben”**-t.
3. **Szabályjavaslatok élesítése** a Tudástárban. Egy éles szabály 3-as
   súlyú, egyedül 78%-os bizonyosság.
4. **Feladatnál magyarázat** („Javítás / magyarázat Larának”), ha Lara
   rosszul javasolt valamit.
5. A **Gemini-kulcs** legyen beállítva. Nélküle kimarad az átnézés, az
   utánanézés, a hipotézisek és a jelentés szerinti keresés.
6. A **„Tanulás és megfigyelés”** forrás legyen bekapcsolva. Nélküle nem
   fut a megfigyelés, az önellenőrzés, a tapasztalás és az éjszakai tanuló.

---

## 13. Korlátok és nem ellenőrzött részek

- **Valódi Gemini-hívás**: hamis modellel tesztelve. Élesben a kulccsal még
  ellenőrizendő, hogy a hipotézis-, utánanézés- és beágyazás-körök
  ténylegesen futnak-e.
- **Szamla@ levelezés**: valódi postafiókon nem futott. A szamla@
  leveleknek a hitelesített Gmail-fiókban kell lenniük.
- **Éles adat**: a fejlesztői adatbázisban szinte nincs adat, ezért a
  bizonyosság tényleges emelkedése csak élesben mérhető.
- **Automatikus számla-elemzés**: alapból nincs, az elemzés a „Lara” gombra
  indul. 2026-09 óta bekapcsolható (`auto_szamla_elemzes`), de akkor is csak
  javaslatot készít (lásd 14.).
- **Autonómia**: amíg a modul ki van kapcsolva, a mellékhatás tiltva, és a
  típusok L0-n vannak, Lara semmit nem hajt végre, csak javasol. Magasabb
  szint beállítása emberi döntés a Beállításokban.

---

## 14. 2026. szeptemberi bővítés — beszélgetés, tanítás, tudáspróba

A részletes átadó (fájlok, migráció, tesztek, kézi ellenőrzés, visszaállítás):
`lara-fejlesztes-2026-09.md`. Röviden:

- **Kérdezz Larától** (`/admin-agent/beszelgetes`).
  - Lara CSAK OLVASVA válaszol: a jóváhagyott tudásából (szabály / kivétel /
    rendszerkézikönyv / hasonló eset, külön rovatban) és a rendszer
    csak-olvasó eszközeivel, a kérdező jogosultságával.
  - Minden válasznál „Honnan tudom”.
  - Modell nélkül tényszerűen csak a talált tudást idézi.
- **Személyiség.**
  - Közös, verziózott réteg (`szemelyiseg.py`, `lara_v1.md`).
  - Sorrend: biztonság > feladat > hiteles kontextus > személyiség.
  - A stílusőr törli az emojit; jelzi, ha Lara végrehajtást állítana.
  - Az ügyfél-profil elő van készítve, de **ki van kapcsolva**: Lara
    ügyfelekkel nem kommunikál.
- **Tanítsd Larát.**
  - Előnézet: fajta, állítás, hatókör, kivételek, érvényesség, tisztázó
    kérdés.
  - A mentés után lesz belőle tudás; általános szabályból csak
    szabály-PISZKOZAT.
- **Tudáspróba.**
  - Vak jóslat a vizsgaügyeken (számla).
  - Saját kérdés elvárt válasszal.
  - „Szennyezett” jelölés, ha a vizsgakészlet nincs elkülönítve.
- **Rendszerkézikönyv.**
  - Gépi technikai tervezet a kódból és a `docs/kezikonyv` fájlokból.
  - Üzleti eljárást csak ember ír.
  - Jóváhagyásig egyik sem használható; verziózott.
- **Üzleti ügy.** Egy ügy = egy eset (lásd 7.2).
- **Hipotézis.** A Gemini profilja és tanulsága „hipotézis” jelölést kap.
- **Új kapcsolók**, mind alapból KI:
  - gyors visszacsatolás (tartós sor, percenként);
  - automatikus, csak-javaslatos számla-elemzés;
  - elkülönített vizsgakészlet.
- **Tanulási folyamat.**
  - Forrásonkénti állapot (nincs adat / kikapcsolva / nincs jogosultság /
    feldolgozási hiba / jóváhagyásra vár) és futásnapló minden ütemezett
    feladatra.
  - Egy tudás-darab teljes útja lekérdezhető.
- **Szakmai szabálytesztek.** Szabályverzióhoz kötött pozitív / ellenpélda /
  hiányos esetek. Ha vannak, az élesítéshez mindnek át kell mennie.
- **Nem ellenőrzött.** Valódi Gemini-modellel sem a beszélgetést, sem a
  tanítás-előnézetet, sem a 20 kommunikációs forgatókönyvet nem futtattam:
  a fejlesztői környezetben nincs kulcs. Automata tesztek hamis modellel
  futnak.
