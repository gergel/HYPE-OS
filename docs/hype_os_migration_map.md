# HYPE OS – Notion Migration Map

*A jelenlegi 43 Notion adatbázis és 163 kapcsolat elemzése, besorolva a HYPE OS domain modellbe.*

---

## 1. Vezetői összefoglaló

A jelenlegi Notion-struktúra **43 adatbázisból** áll, ~1000+ mezővel összesen. Ebből a valós, egyedi üzleti logikát hordozó "mag" jóval kisebb – a többi **duplikáció, klónozott séma vagy elavult one-off tábla**.

A legfontosabb felismerések:

| # | Probléma | Érintett DB-k | Súlyosság |
|---|---|---|---|
| 1 | **5 klónozott "személyes elszámolás" tábla** – ugyanaz a séma emberenként lemásolva | Geri elszámolás, Bükfa Kristóf adatbázis, Salamon Zalán adatbázis, Fábián Péter adatbázis, Nemes Attila adatbázis | 🔴 Kritikus → **döntés: a 4 névre szabott klón törlődik, a Geri elszámolás beolvad a Timesheet/Expense-be** |
| 2 | **Crew/Employee szétforgácsolva 6 táblába** | Vágók, Kreatív team database, Hype Stáb, Külsős, Belsős, Külsős és belsős | 🔴 Kritikus |
| 3 | **3+1 párhuzamos TODO-lista** | TEENDŐK, Ági to do list, HYPE TO-DO LIST, Archive feladatok | 🟠 Közepes |
| 4 | **Equipment/Leltár 5 táblára szórva** | Leltár, Leltárak, Leltár tételek, Archive technika, Eszközkivitel | 🟠 Közepes |
| 5 | **Timesheet duplikálva (public/private)** | Timesheet Public, Timesheet Private | 🟡 Kisebb |
| 6 | **Expense/Kiadás 4 táblára szórva** | Kiadások, Projekt kiadások, Belsős extra kiadások, KP forgalom | 🟠 Közepes |
| 7 | **Contract duplikálva** | Keretszerződés, Alvállakozó keretszerződés (külsős) | 🟡 Kisebb |
| 8 | **"Main Database" monolit, 144 mező** | Main Database | 🔴 Kritikus |
| 9 | **HYPE ADMIN projektkódok mellett egy "darabolás" segédtábla** | HYPE ADMIN projektkódok, HYPE ADMIN PROJEKTKÓDOK DARABOLÁS | 🟠 Közepes |
| 10 | **Egyedi, dátumhoz kötött projekttáblák, amik nem kellenének külön DB-nek** | 2025 CEU RecruiTECH Blue, 2025 beosztása | 🟡 Kisebb |
| 11 | **Nyilvánvaló teszt/felesleges tábla** | "New form" | 🟢 Törölhető |

A 43 adatbázis a HYPE OS-ben becslés szerint **~14-16 domain objektumra** vonható össze.

---

## 2. Teljes Migration Map (mind a 43 adatbázis)

Jelölések: **Megmarad** = önálló entitás marad · **Átalakul** = entitássá alakul, de más struktúrában · **Összeolvad** = beolvad egy másik/közös entitásba · **Megszűnik** = adat migrálva, a tábla eltűnik

| Jelenlegi Notion DB | Mező | Művelet | Cél domain objektum | Megjegyzés |
|---|---|---|---|---|
| Main Database | 144 | Átalakul | **Project** + **Project Code** + **Timeline Event** + **Deliverable** | A monolit szétbontása a legfontosabb egyedi feladat. 144 mező egyetlen táblában = anti-pattern. |
| HYPE ADMIN projektkódok | 81 | Átalakul | **Project Code** | Ez a pénzügyi mag (bevétel, profit, margin) – ez lesz a Project Code entitás gerince. |
| HYPE ADMIN PROJEKTKÓDOK DARABOLÁS | 23 | Megszűnik | **Project Code** (logika) | Valószínűleg a Notion formula-limitáció miatti workaround tábla. Backend logikává alakul, nem kell külön DB. |
| Külsős és belsős | 63 | Összeolvad | **Employee** | Ez már majdnem az egyesített Crew tábla – ez legyen a bázis, a többi (Vágók, Külsős, Belsős, Hype Stáb, Kreatív team) ebbe olvad be `type` mezővel (belsős/külsős/vágó/kreatív). |
| Vágók | 43 | Összeolvad | **Employee** (role=vágó) | |
| Külsős | 42 | Összeolvad | **Employee** (type=külsős) | Duplikátum a #Külsős és belsős-szel. |
| Leltár | 40 | Átalakul | **Equipment** | Fő equipment tábla. |
| Utómunka | 56 | Átalakul | **Deliverable** / **Task** (post-production fázis) | |
| Kreatív team database | 27 | Összeolvad | **Employee** (type=kreatív) | |
| Belsős | 25 | Összeolvad | **Employee** (type=belsős) | Duplikátum. |
| Timesheet Private | 24 | Összeolvad | **Timesheet** (visibility=private) | |
| Kiadások | 22 | Átalakul | **Expense** | Fő expense tábla. |
| Timesheet Public | 21 | Összeolvad | **Timesheet** (visibility=public) | Public/private legyen egy mező, ne két tábla. |
| Alvállakozó keretszerződés (külsős) | 20 | Összeolvad | **Contract** (type=alvállalkozói) | |
| Visszajelzéssek | 19 | Átalakul | **Feedback / Review modul** | A vágók az Utómunka oldalról, egy gomb (button-triggered action) segítségével küldik át ide a visszajelzést. Az event-driven architektúrában ez egy `UtómunkaFeedbackSubmitted` esemény, ami létrehoz egy Feedback rekordot – nem külön, kézzel táplált tábla. |
| Keretszerződés | 18 | Összeolvad | **Contract** | Fő contract tábla, a fentivel egyesítve `type` mezővel. |
| Leltár tételek | 18 | Összeolvad | **Equipment** (item szint) | |
| Geri elszámolás | 16 | Összeolvad | **Timesheet** / **Expense** (Person relation) | Ez marad, csak a séma-klón mintát nem visszük tovább – ez legyen az egyetlen, mindenkire vonatkozó Timesheet/Expense rekord Geri Person-relation sorával. |
| Projekt kiadások | 15 | Összeolvad | **Expense** (Project Code-hoz kötve) | |
| Megrendelői kontaktok | 14 | Átalakul | **Location/Contact** (Client-hez kötve) | |
| Kampányok | 13 | **Megmarad** | **Campaign** (önálló entitás) | Marketinges vezeti, content calendart és hasonlókat kezel innen. Egyelőre nem kapcsolódik a Project/Project Code maghoz – önálló modul marad. |
| Bevételek | 13 | Átalakul | **Project Code** pénzügyi mező | |
| Archive technika | 13 | Megszűnik | **Equipment** (status=archived) | Nem kell külön tábla egy státuszért. |
| Eszközkivitel | 11 | Átalakul | **Assignment** (Equipment checkout/return) | |
| HYPE TO-DO LIST | 11 | Összeolvad | **Task** | |
| Órabér/napibér | 10 | **Átalakul** | **Rate** entitás (Employee-hez kötve, nem sima mező) | Ez a HYPE önköltség-számításának a motorja – lásd 6. fejezet. Nem olvasztható egyszerű mezőbe, mert időben változhat és forgatásonként külön számol. |
| KP forgalom | 10 | **Megmarad** | **KP forgalom** (önálló entitás) | Marad ahogy jelenleg van, nem olvad be az Expense-be. |
| Bükfa Kristóf adatbázis | 10 | **Törlődik** | *(nincs cél entitás)* | Nem kell – a klónozott séma-minta miatt kiváltja az Employee + Timesheet/Expense modell. Adatmigráció nélkül törölhető. |
| Salamon Zalán adatbázis | 10 | **Törlődik** | *(nincs cél entitás)* | Nem kell – ua. |
| Fábián Péter adatbázis | 10 | **Törlődik** | *(nincs cél entitás)* | Nem kell – ua. |
| Nemes Attila adatbázis | 10 | **Törlődik** | *(nincs cél entitás)* | Nem kell – ua. |
| Stock igények | 8 | **Átalakul** | **EQUIPMENT** (stock-jellegű igénylés) | **Nem törlendő** – ez a mechanizmus kezeli a nem egyedi, darabszám-alapú eszközöket (pl. 5 db egyforma 30m HDMI kábel), ahol nem az egyedi példány számít, hanem hogy az 5-ből hány db megy ki egy adott projekthez. A `HYPE_Technika` Railway worker élesben erre épül (`track_mode: "asset" \| "stock"`). A HYPE OS-ben ez az `EQUIPMENT` entitás `track_mode` mezője + egy `ASSIGNMENT`-hez tartozó `qty` mező lesz, nem külön tábla – de a mögöttes logika megmarad. |
| Leltárak | 8 | Összeolvad | **Equipment** (batch/csoport szint) | |
| Operatőri diszpó | 8 | Összeolvad | **Call Sheet** (Diszpó modul) | |
| Hype Stáb | 7 | Összeolvad | **Employee** | |
| Ági to do list | 7 | Összeolvad | **Task** | |
| Belsős extra kiadások | 7 | Összeolvad | **Expense** | |
| New form | 7 | Megszűnik | Feedback/Review modul (ha egyáltalán kell) | Kinéz, mint egy egyszeri Notion form response tábla – teszt vagy elavult. |
| Timesheet Public *(fent már szerepel)* | | | | |
| 2025 CEU RecruiTECH Blue | 5 | **Törlődik** | *(nincs cél entitás)* | Nem kell – egyedi, dátumhoz kötött projekttábla, adatmigráció nélkül törölhető. |
| 2025 beosztása | 5 | **Törlődik** | *(nincs cél entitás)* | Nem kell – egyszeri beosztás-tábla, adatmigráció nélkül törölhető. |
| Törölt anyagok | 5 | Megszűnik | **Media** (deleted flag) vagy Timeline Event | Státusz, nem külön entitás. |
| TEENDŐK | 5 | Összeolvad | **Task** | |
| Archive feladatok | 4 | Megszűnik | **Task** (status=archived) | |

---

## 3. A legfontosabb strukturális felismerés: klónozott séma-minta

Az alábbi 5 adatbázis **bit-pontosan ugyanazokat a mezőket** tartalmazza, csak külön-külön, emberenként lemásolva:

- Geri elszámolás
- Bükfa Kristóf adatbázis
- Salamon Zalán adatbázis
- Fábián Péter adatbázis
- Nemes Attila adatbázis

Közös mezők mindegyikben: `Projektkód`, `Projekt`, `Person`, `Date`, `Esemény időpontja`, `Túlóra`, `Egyéb kiadások`, `Egyéb kiadások megnevezése`, `Diszpó pdf`, `Megjegyzés`.

**Döntés:** a 4 névre szabott klón (Bükfa Kristóf, Salamon Zalán, Fábián Péter, Nemes Attila) **törlődik, adatmigráció nélkül** – nem kellenek a HYPE OS-ben. A **Geri elszámolás** marad, de nem külön táblaként: beolvad az egységes **Timesheet/Expense** entitásba egy `Person` (relation → Employee) mezővel, ahol Geri sora is csak egy a sok közül.

Ez a minta valószínűleg máshol is előfordulhat a jövőben, ha valaki új Notion adatbázist hoz létre "csak neki" – érdemes ezt architektúra-szabályként rögzíteni: **soha nem jön létre új adatbázis egy konkrét személy vagy dátum miatt.**

---

## 4. Crew/Employee konszolidáció (a legnagyobb egyszeri nyereség)

6 tábla → 1 entitás:

| Jelenlegi tábla | Mező | Employee.type érték |
|---|---|---|
| Külsős és belsős | 63 | (bázis tábla, mindkét típus) |
| Vágók | 43 | vágó |
| Külsős | 42 | külsős |
| Kreatív team database | 27 | kreatív |
| Belsős | 25 | belsős |
| Hype Stáb | 7 | stáb |

Összesen **207 mező** 6 táblában – ebből jelentős átfedés (pl. Person, kapcsolattartás, órabér mezők ismétlődnek mindegyikben). Az egyesített `Employee` entitásban ezek egyszer szerepelnének, `role`/`type` és `skills` mezőkkel differenciálva.

---

## 5. Nyitott kérdések – státusz

1. ~~Kampányok – önálló entitás legyen?~~ → **Eldőlt: igen, önálló Campaign entitás**, a marketinges vezeti, egyelőre nem kapcsolódik a Project/Project Code maghoz.
2. ~~KP forgalom – beolvad az Expense-be?~~ → **Eldőlt: marad önálló, ahogy jelenleg van.**
3. **New form** – továbbra is nyitott: van-e még élő Notion form, ami ide ír? Ha nincs, archiválható, v1-ben nem kell modulként megépíteni.
4. **Automatizációk** – Geri később leírja, milyen automatizációkat használnak a fenti modulokhoz (pl. a Visszajelzéssek gombos átküldése). Az itt szereplő alap terv egy kiindulási váz, ami ezek alapján finomodik.

---

## 6. Önköltség-számítás logikája (Órabér/napibér → Rate entitás)

A 4. pontban jelzett igény alapján az **Órabér/napibér** tábla nem csak egy statikus szabálylista, hanem a HYPE OS **önköltség-számító motorjának** az alapja. Ez alapján számolja majd a rendszer:

- **kinek mennyi a bére** (Employee → Rate: órabér vagy napibér, típustól függően),
- **egy adott vágásnál** (Utómunka / Deliverable) **kinek mennyi óráját vitte el** a munka, és ez mennyibe került (Timesheet óra × Rate),
- **egy adott forgatásnál** (Project) **ki dolgozott rajta belsős alkalmazottként**, mennyi a napi bére, és ez alapján **mennyibe került az adott forgatás** (Project költség = Σ belsős napidíjak + Σ külsős díjak + egyéb kiadások).

Ez azt jelenti, hogy a **Rate** (Órabér/napibér) entitás két irányba is kapcsolódik:

- **Timesheet-hez** → vágási óraköltség számításhoz (Deliverable/Utómunka szinten),
- **Project-hez** (a napi beosztáson keresztül) → forgatási napi költség számításhoz (Project szinten, ami aztán a Project Code összesítésébe folyik be).

Ez a modul tehát nem egyszerű mezőként olvad be az Employee-be, hanem **önálló, számított logikát tartalmazó entitás/szolgáltatás**, ami a Timesheet és a Project Assignment adatokat kombinálja a Rate-tel. Ezt érdemes a backend Automation/Analytics rétegben, nem a UI-ban implementálni – így egyetlen helyen változik a számítási logika, ha a béres/napidíjas szabályok módosulnak.

---

## 7. Mezőtérkép a legfontosabb összevonásoknál (forrás → cél)

*A teljes kapcsolati ábra és az összes entitás mezőlistája a `hype_os_kapcsolati_abra.mermaid` fájlban van (ER diagram). Itt a legtöbb duplikációt tartalmazó 5 entitásnál mutatom, konkrétan melyik régi Notion mező hova kerül.*

### EMPLOYEE ← Külsős és belsős + Vágók + Külsős + Belsős + Kreatív team database + Hype Stáb

| Cél mező | Forrás(ok) |
|---|---|
| `full_name` | Full Name / Name / Név (mind a 6 táblában) |
| `tipus` | levezetve: melyik forrás táblából jött (belsős / külsős / vágó / kreatív / stáb) |
| `email` | E-MAIL CÍM, Email (Külsős és belsős) |
| `telefon` | TELEFONSZÁM, Phone, Phone 2 (Külsős és belsős) |
| `orabler` / `napidij` | Órabér, Napidíj (formula, Külsős és belsős) → **RATE**-ből számolva |
| `contract_id` | Alvállakozó keretszerződés (külsős), Belsős TIG, Külsős TIG relationök |
| `munkaszerzodes` | Munkaszerződés (files, Külsős és belsős) |
| `ertekeles` | Értékelés (formula, Külsős és belsős) ← Visszajelzéssek átlagából |
| vágó-specifikus statok (XP, level, gyorsaság) | Vágók tábla ~17 formula mezője → külön `EmployeePerformance` al-nézet, nem alapmező |

### TIMESHEET ← Timesheet Public + Timesheet Private

| Cél mező | Forrás(ok) |
|---|---|
| `employee_id` | Person (mindkét táblában) |
| `deliverable_id` | Utómunka_1 / Utómunka_2 relationök |
| `start_date`, `end_date` | Start Date, End Date |
| `koltseg` | Költség (formula, Private) + Akkori órabér (Private) |
| `statusz` | Timesheet status (formula, mindkettő) |
| `visibility` mező (új) | ez különbözteti meg, ami eddig két külön táblát jelentett (public/private) |

### EXPENSE ← Kiadások + Projekt kiadások + Belsős extra kiadások

| Cél mező | Forrás(ok) |
|---|---|
| `project_code_id` | Projektkód (Belsős extra kiadások), Kiadás projektkódja |
| `employee_id` | Külsős / Belsős / Személy relationök mindhárom táblából |
| `netto` / `brutto` | Nettó, Bruttó (formula) |
| `kifizetes_modja` | Kifizetés módja (select, Kiadások) |
| `tipus` | levezetve: melyik forrás táblából jött (belsős / külsős / extra) |

### EQUIPMENT ← Leltár + Leltárak + Leltár tételek + Archive technika

| Cél mező | Forrás(ok) |
|---|---|
| `serial_number` | Serial number (Leltár, Archive technika) |
| `allapot` | Állapota (Leltár), Állapot (Leltárak, Archive technika) |
| `archive_statusz` | Archive státusz (Leltár) + a teljes Archive technika tábla → **egy mezővé** lesz, nem külön táblává |
| `kategoria` | Kategória (Leltár, Archive technika) |
| `projektek` (history) | Projektek relation (Leltár, Archive technika) |
| Leltár tételek → | ezek maradnak Equipment al-sorok (`EquipmentLineItem`), nem önálló top-level entitás |

### CONTRACT ← Keretszerződés + Alvállakozó keretszerződés (külsős)

| Cél mező | Forrás(ok) |
|---|---|
| `tipus` | levezetve: kereto (Client-tel) vagy alvállalkozói (Employee-vel) |
| `ceg_neve`, `szekhely`, `adoszam` | formula mezők mindkét táblából, azonos logika |
| `szerzodes_allapota` | Keretszerződés állapota / Állapot |
| `alairva` | Szerződés aláírva (files jelenlét) |

### TASK ← TEENDŐK + Ági to do list + HYPE TO-DO LIST + Archive feladatok

| Cél mező | Forrás(ok) |
|---|---|
| `feladat` | Feladat / Name (mind a 4 táblában) |
| `allapot` | Állapot / Checked |
| `felelos_employee_id` | Felelős / Assignee |
| `hatarido` | Határidő / Due date |
| `kategoria` | Kategória (HYPE TO-DO LIST) |

---

*Ez a dokumentum a HYPE OS projektindító doksi "Migration" fejezetéhez készült kiindulási alap – a végleges Migration Map-et érdemes ez alapján, de a nyitott kérdések eldöntése után lezárni.*

*A teljes entitás-kapcsolati ábra (mind a 18 megmaradó entitás, kapcsolatokkal és mezőkkel) a `hype_os_kapcsolati_abra.mermaid` fájlban található.*
