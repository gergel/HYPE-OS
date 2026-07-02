# HYPE – A JELENLEGI RENDSZER (AS-IS), végponttól végpontig

*Ez a dokumentum a projektindító doksi eredeti "Jelenlegi működés" láncát (Megkeresés → ... → Archiválás) egészíti ki azzal, hogy pontosan melyik Notion adatbázis és melyik Railway szolgáltatás dolgozik az egyes lépéseknél. Ez a válasz arra: "össze van-e kötve logikailag minden, és ez ma egy működő rendszer-e?"*

**Rövid válasz: igen, ez ma egy ténylegesen működő, élesben futó rendszer** – csak nem egyben lett megtervezve, hanem 43 Notion adatbázis + 17 Railway szolgáltatás szükségből összeillesztve. A logika összeér, de vannak benne törésvonalak (lásd 3. fejezet), amik miatt ez inkább "működik, de törékeny", mint "megtervezett architektúra".

---

## 1. A teljes lánc, automatizációkkal annotálva

```
 1. MEGKERESÉS / INQUIRY
    Notion: HYPE ADMIN projektkódok (új Projektkód létrehozása)
                          │
 2. NAPTÁR / PROJEKT LÉTREHOZÁSA
    Notion: Main Database (144 mezős monolit) – itt jön létre a konkrét Forgatás
                          │
    ⚙️  ADMIN_projektkod (Railway, 5 percenként)
        HYPE ADMIN projektkódok ←→ Main Database
        Projektkód alapján összeköti a Project Code-ot a Forgatással
                          │
 3. OPERATŐRÖK / STÁB KIOSZTÁS
    Notion: Vágók, Külsős és belsős, Hype Stáb, Kreatív team database
                          │
    ⚙️  time_xp/main.py, timesheet-public-vago, oraber_vagas_private,
        oraber-timesheet-private (Railway, 5 percenként)
        Név-alapú matching köti össze a Timesheet/Timer bejegyzéseket
        a konkrét Vágó/Employee rekorddal
                          │
 4. TECHNIKA / EQUIPMENT KIOSZTÁS
    Notion: Leltár, Stock igények, Eszközkivitel
                          │
    ⚙️  HYPE_Technika (Railway, saját Postgres cache)
        Napi lebontású foglaltság-naptár + ÜTKÖZÉS-DETEKTÁLÁS
        (ha 2 forgatás ugyanazt az egyedi eszközt akarja,
        automatikusan alternatívát ajánl – pl. optikánál)
        Visszaírja a kategorizált technika-listát a Main Database-be
                          │
    ⚙️  inventory-audit-system (Railway, manuális trigger)
        Fizikai leltárellenőrzés indítása: Leltár → Leltárak → Leltár tételek
                          │
 5. DISZPÓ
    Notion: Main Database (Diszpó mezők), Operatőri diszpó
                          │
    ⚙️  diszpo-kuldes (Railway, saját Postgres, 1 percenként poll)
        Előzetes diszpó → (email thread) → Teljes diszpó (reply ugyanabba
        a szálba) → PDF generálás → Google Drive feltöltés →
        Gmail küldés a "Résztvevők email" relation alapján →
        Notion vissza: Diszpó=Kiküldve, Drive link, Gmail Thread ID
                          │
 6. FORGATÁS
    (nincs automatizáció – ez fizikailag történik)
                          │
 7. UTÓMUNKA
    Notion: Utómunka, Timesheet Public, Timesheet Private
                          │
    ⚙️  ADMIN_utomunka (Railway, 5 percenként)
        HYPE ADMIN projektkódok ←→ Utómunka (Projektkód első 11 karaktere)
                          │
    ⚙️  time_xp/pont_adder.py (Railway, 1 percenként)
        Jóváhagyott utómunka → XP/pontszám jóváírás a vágónak
                          │
    Visszajelzés: a vágó egy gombbal (button) küldi át
    Notion: Visszajelzéssek DB
                          │
 8. PORTAL
    ⚙️  Hype-repo (Railway: api + worker + web, saját Postgres + Redis + R2)
        Videó feltöltés → FFmpeg (thumbnail + HLS) → Cloudflare R2 →
        Ügyfél jelszóval/share linkkel megnézi a /p/{slug} oldalon →
        Opcionális: Barion fizetés, ha payment_mode = "paid"
                          │
 9. SZÁMLÁZÁS
    Notion: Kiadások, Projekt kiadások, Bevételek, Belsős, Külsős
                          │
    ⚙️  TIG-alvalalkozo, belsos-TIG, TIG-megrendel-email (Railway, 5 percenként)
        TIG (teljesítésigazolás) generálás → PDF → Drive → Gmail →
        Notion: TIG aláírva link, státusz frissítés
                          │
    ⚙️  kulsos-eseti-szerzodes, alvallalkozo-keret,
        megregdelo-eseti, megregdelo-keretszerzodes (Railway, 5 percenként)
        Szerződés generálás/küldés (keret vagy eseti, alvállalkozói vagy
        megrendelői oldalra) → ugyanaz a PDF→Drive→Gmail pipeline
                          │
    ⚙️  (Hype-repo) Barion callback – ha volt portál-fizetés, itt landol
        a fizetési visszaigazolás
                          │
10. ARCHIVÁLÁS
    Notion: Archive technika, Archive feladatok, Törölt anyagok
    (jelenleg külön táblák egy "archivált" státusz helyett)
```

---

## 2. Amit ez bizonyít: a rendszer logikailag tényleg összeér

Minden lépésnél van **legalább egy automatizáció, ami átadja a stafétát a következő lépésnek** – nincs "szakadás" a láncban:

- Projektkód → Forgatás: `ADMIN_projektkod`
- Forgatás → Utómunka: `ADMIN_utomunka`
- Timesheet → Vágó/Employee: `time_xp`, `timesheet-public-vago`, `oraber_vagas_private`, `oraber-timesheet-private`
- Eszköz → Forgatás (ütközés-mentesen): `HYPE_Technika`
- Forgatás → Diszpó email: `diszpo-kuldes`
- Utómunka → XP jóváírás: `time_xp/pont_adder.py`
- Munka → TIG/szerződés → Számlázás: a 7 dokumentum-generáló repó
- Kész anyag → Ügyfél → (opcionális) Fizetés: `Hype-repo`

Ez azt jelenti: **igen, amit eddig feltérképeztünk, az egy valóban működő, end-to-end rendszer** – az igény felmerülésétől a kifizetésig minden lépés automatizálva van valamilyen szinten.

---

## 3. Amit fontos látni: ez "működik", de nem "architektúra"

Három szerkezeti probléma van, ami miatt ez törékeny, még ha végig is fut:

1. **Nincs egyetlen "igazság-forrás"**: az adat 43 Notion táblában + 2 Railway Postgres adatbázisban (HYPE_Technika, diszpo-kuldes, Hype-repo) van szétszórva. Egy projekt teljes állapotát ma **senki nem tudja egy lekérdezéssel visszakapni** – össze kell rakni Notion API hívásokból és 3 különböző Postgres-ből.

2. **A láncszemek nagy része polling + string-matching, nem esemény-vezérelt kapcsolat**: 13 a 17 repóból `while True: ... sleep(60-300)` mintát követ, és 6 közülük **név alapján** (nem ID alapján) próbál összekötni rekordokat. Ez azt jelenti, hogy a rendszer **működik, amíg senki nem gépel el egy nevet, és amíg 5 percet lehet várni egy frissítésre** – ez pont az, amit egy relációs adatbázis (foreign key) egy csapásra kizárna.

3. **Van két nyitott varrás, ami még nincs bizonyítottan összekötve:**
   - A `Hype-repo` Notion-szinkronja olyan mezőket vár, amik nincsenek a feltérképezett 43 táblában (2. dokumentum, 6. fejezet) – ez vagy egy még nem látott Notion adatbázis, vagy egy soha be nem kötött funkció.
   - A `Stock igények` tábla ~~törlésre lett jelölve~~ **véglegesen megmarad** – kiderült, hogy ez a nem-egyedi, darabszám-alapú eszközök (pl. 5x egyforma HDMI kábel) igénylésének kulcs-mechanizmusa, amit a HYPE_Technika élesben használ.

---

## 4. Mi ez gyakorlatban a HYPE OS szempontjából?

Amit most csináltunk, az valójában a projektindító doksi **"Migration" fejezetének első, legfontosabb lépése**: egy teljes **AS-IS rendszertérkép**, ami nélkül nem lehetne felelősségteljesen nekiugrani a TO-BE (HYPE OS) építésének. Most már pontosan tudjuk:

- **mit kell újraépíteni** natívan (a 13 stateless workert – ezek a HYPE OS-ben egyszerűen megszűnnek, mert relációs FK-k és event bus váltja őket),
- **mit kell átmenteni és bővíteni** (HYPE_Technika ütközés-logikája, diszpo-kuldes email-szál kezelése, Hype-repo teljes Portal/Media/Payment rétege),
- **mit kell tisztázni, mielőtt bármit törlünk** (Portal Notion DB, Payment/brand kérdés – a Stock igények kérdés már lezárva).

Ezzel a 4 dokumentum (Migration Map, kapcsolati ábra, Railway integráció, ez a AS-IS térkép) együtt egy **teljes, konzisztens alapot ad** a HYPE OS tényleges backend-tervezéséhez – innen már konkrét adatbázis-séma és API-terv írható.

---

*Kapcsolódó dokumentumok: `hype_os_migration_map.md`, `hype_os_kapcsolati_abra.mermaid`, `hype_os_railway_integracio.md`.*
