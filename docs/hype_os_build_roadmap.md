# HYPE OS → HYPE Brain – Build Roadmap

*Hogyan jutunk el a mai állapotból (43 Notion DB + 17 Railway szolgáltatás) a csatolt vízió-dokumentumban látható egységes rendszerig – Notiontól teljesen független fejlesztéssel, egyszeri teszt-adat importtal, és a végén egy tudatos, végleges átköltöztetéssel (nem folyamatos oda-vissza szinkronnal).*

---

## 1. A legfontosabb stratégiai döntés: teljesen új, önálló repó

A HYPE OS **egy vadonatúj GitHub repóban épül, nullától** – nem a meglévő `Hype-repo` vagy bármelyik másik 16 Railway repó bővítéseként. A korábban feltérképezett rendszerek (Notion + 17 Railway szolgáltatás) kizárólag **tervezési referenciaként** szolgálnak – a `hype_os_kapcsolati_abra.mermaid` séma és a `hype_os_migration_map.md` üzleti logikája adja a tartalmi alapot, de a kód maga teljesen új.

A csatolt vízió-dokumentum "7. Backend architektúra" szekciója (FastAPI + PostgreSQL + Redis + Cloudflare R2 + Next.js) jó referencia-stack egy ilyen új rendszerhez – ezt a technológiai irányt érdemes követni, de a kódbázis maga a nulláról induló, új repóban jön létre.

**Gyakorlati lépés:** hozz létre egy új, üres GitHub repót (pl. `hype-os`), és ez legyen az egyetlen hely, ahol a HYPE OS fejlesztése folyik.

---

## 2. A kép adatbázis-terve (8. szekció) vs. amink már van

A képen látható séma (`users`, `projects`, `tasks`, `equipment`, `bookings`, `media_files`, `invoices`) egy **jó, de leegyszerűsített MVP-váz** – 7 tábla. A mi `hype_os_kapcsolati_abra.mermaid` fájlunk **18 entitást** ír le, a tényleges HYPE üzleti logika alapján (pl. Project Code ≠ Project, Client → Project Code → Project hierarchia, Rate/Timesheet önköltség-számítás, Contract altípusok, stock vs. asset equipment).

**Ez a különbség fontos:** ha a fejlesztés a kép egyszerű 7-táblás sémájából indulna, hiányozna belőle a cég működésének fél éve feltérképezett logikája. **A saját `kapcsolati_abra.mermaid`-ot kell séma-alapnak használni, nem a képen lévőt** – az utóbbi jó kiindulás egy generikus projekt-management app-hoz, de nem HYPE-specifikus.

---

## 3. Konkrét fázisterv

### Fázis 0 – Döntés + előkészítés (most)
- [ ] Új, üres GitHub repó létrehozása (pl. `hype-os`) – ez lesz az egyetlen hely, ahol a fejlesztés folyik.
- [ ] Alap projektváz felállítása benne (FastAPI backend + Next.js frontend + PostgreSQL, a vízió-dokumentum stackje szerint) – nulláról, semmilyen meglévő repó kódját nem másolva át.
- [ ] A `hype_os_kapcsolati_abra.mermaid` 18 entitását SQLAlchemy modellekre fordítani, Alembic migrációval.
- [ ] Eldönteni a nyitott kérdéseket, amik a sémát érintik: Payment/brand kezelés, Portal-koncepció (ha kell egyáltalán – ezt is nulláról érdemes újragondolni, nem a Hype-repo Portal-jából kiindulva).

### Fázis 1 – Alapok (a projektindító doksi saját sorrendje szerint)
1. Authentication (a Hype-repo `core/security.py`-ja már ad admin auth-ot – bővíteni kell szerepkörökkel: admin / operatőr / vágó / ügyfél)
2. Dashboard (üres váz, adat még Notionból jön)
3. Clients (**új entitás** – jelenleg nincs önálló Notion tábla rá, ki kell emelni a Contact/Project Code mezőkből)
4. Project Codes
5. Projects
6. Crew (Employee + Rate)
7. Equipment (a `HYPE_Technika` ütközés-detektáló logikáját át kell hozni natív Postgres táblákra)
8. Timeline
9. Storage (ez már megvan a Hype-repóban, R2-vel)
10. Automation (ez váltja ki a 7 dokumentum-generáló klónt + a diszpó automatizációt)

### Fázis 2 – Teszt-adat a Notionból, a rendszer különben teljesen független
Itt egy egyszerűbb, kevésbé kockázatos utat választottatok, mint a klasszikus "élő híd" megközelítés – **ez rendben van, és sok szempontból biztonságosabb is**, mert nem kell egy törékeny, kétirányú szinkron-réteget építeni és karbantartani a régi és az új rendszer közt.

- A HYPE OS **teljesen függetlenül épül** – nincs Notion API-hívás a normál működésben, nincs írás vissza Notionba.
- A fejlesztés/tesztelés alatt **egyszeri (vagy alkalmankénti) exportot** hoztok át a Notionból a teszt-Postgres adatbázisba – ez egy egyszerű, egyirányú import-szkript (Notion API → olvasás → Postgres insert), ami **nem fut folyamatosan**, csak amikor kell egy friss adatszelet a teszteléshez.
- A csapat eközben **továbbra is a Notionban dolgozik élesben** – a két rendszer nem "látja" egymást, teljesen párhuzamosan futnak.
- Amikor a HYPE OS készen áll és minden modul működik: **egyszeri, végleges migráció** ("cutover") – utolsó teljes export a Notionból, betöltés a HYPE OS Postgres-ébe, majd a csapat egyik napról a másikra átáll az új rendszerre. Ettől a naptól a Notion írásvédetté válik / archívummá lesz.

**Amit ez egyszerűsít:** nem kell a korábban tervezett kétirányú szinkron-szolgáltatást megépíteni, ami a legkockázatosabb és legtöbb karbantartást igénylő rész lett volna.

**Amire ez miatt oda kell figyelni:**
- A cutover napján **adatzárlat** kell a Notion oldalon (senki ne vigyen fel új adatot a régi rendszerbe az exportálás közben/után), különben elveszik valami a végleges migrációnál.
- Az egyszeri import-szkriptet érdemes **idempotensre** írni (újra lehessen futtatni anélkül, hogy duplikálná az adatot) – így a teszt-import többször is lefuttatható fejlesztés közben, és a végső cutover-import ugyanaz a szkript, csak élesben.
- Mivel nincs élő szinkron, a HYPE OS fejlesztése alatt keletkező Notion-változásokat (amíg a csapat ott dolgozik) **csak akkor látjátok, amikor újra lefuttatjátok az import-szkriptet** – ez tesztelésre tökéletes, de azt jelenti, hogy a cutover előtt egy utolsó, friss importot mindenképp kell futtatni.

### Fázis 3 – A meglévő "jó" Railway logika mintaként újraírva
A cél nem a kód másolása, hanem az **üzleti logika** újraépítése az új repóban, nulláról, natív adatbázis-kapcsolatokkal:
- Equipment ütközés-detektáló + alternatíva-ajánló logika (a `HYPE_Technika` mintája alapján, de új kóddal) → Equipment modul
- Diszpó email-szál kezelés + gating (a `diszpo-kuldes` mintája alapján) → Automation modul
- XP/gamifikáció (a `time_xp` mintája alapján) → Employee/Timesheet modul, event-driven megközelítéssel

### Fázis 4 – A cutover nap
Amikor minden modul kész és a teszt-importokkal validáltátok, hogy minden adat helyesen jön át:
- Adatzárlat a Notionban (lásd fent).
- Utolsó, végleges import a Notionból a HYPE OS Postgres-ébe.
- Csapat átáll az új felületre.
- A 17 Railway repó (a 13 stateless szinkron/dokumentum-szolgáltatás + a 2 stateful, amit már átemeltetek + Hype-repo, ami már az új rendszer része) leállítása/archiválása.
- Notion írásvédetté válik, és egy darabig csak referenciaként/archívumként marad meg, mielőtt véglegesen törölnétek.

### Fázis 5 – AI réteg (HYPE Brain)
A kép 9. szekciója (RAG pipeline: adatforrások → ingestion → vector DB → LLM + tool calling) **csak ez után** van értelme, mert az AI asszisztensnek megbízható, strukturált adatra van szüksége a Postgres-ből – ha ez korábban épül, félkész/inkonzisztens adaton fog "okoskodni".

---

## 4. Hol érdemes ezt ténylegesen megépíteni?

Ez a fejlesztés innentől **valódi, sokfájlos, iteratív szoftverfejlesztési munka** – migrációk futtatása, tesztelés, Railway deploy, git commitok. Ez már túlnő azon, amit chat-ben, fájlonként érdemes csinálni.

**Javaslat:** a Claude Code desktop appban érdemes folytatni – ott tudok közvetlenül az új, üres `hype-os` repó fájlrendszerén dolgozni, felállítani a projektvázat, futtatni az Alembic migrációkat, tesztelni, és iteratívan építeni a modulokat a fenti fázisterv szerint, míg itt a chatben inkább a nagyobb döntéseket, terveket és a dokumentációt érdemes vezetni.

