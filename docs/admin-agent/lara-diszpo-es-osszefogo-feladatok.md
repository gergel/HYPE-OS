# Lara: diszpó brief, technikai lista és összefogó feladatok

2026-09-28-i bővítés. Lara eddig csak adminisztrációs feladatot vállalt
(számla, TIG, szerződés, adminisztrációs e-mail). A felhasználó döntése
alapján ez két területtel bővült:

1. **Diszpó brief és technikai lista.** Lara a korábbi hasonló forgatások
   tapasztalatából megírja a briefet és összeállítja a technikát. A
   technikánál nem csak listát ír: jóváhagyás után az eszközöket
   ténylegesen hozzárendeli a projekthez, ugyanúgy, ahogy a rendszer máshol is.
2. **Összefogó adminisztrációs feladatok.** Lara nagy, több projektkódot,
   időszakot vagy partnert átfogó feladatot is értelmez és kezel, nem csak
   egyetlen projektkódhoz kötöttet.

**Továbbra sem Lara dolga:**
- a diszpó kiküldése vagy átütemezése;
- a beosztás, az utómunka és a portál;
- az utalás.

A végrehajtó ezeket továbbra is blokkolja. A biztonsági értékelés esetei is
így szólnak: a diszpó kiküldése és a beosztás tiltott; a brief és a technika
csak jóváhagyással mehet.

## Diszpó: brief + technika

### Honnan tanul Lara

A tapasztalatot két helyen gyűjti.

**Élőben, a tervezet készítésekor**
- Lara a korábbi forgatások közül a leginkább hasonlókat keresi.
- Hasonlóságot ad az azonos ügyfél, kampány és brief-típus, a hasonló név
  és helyszín, valamint a közös stábtagok.

**A teljes rendszer figyelésekor** (óránkénti futás, ha a „Teljes rendszer
figyelése” forrás be van kapcsolva)
- Ügyfelenként és brief-típusonként elmenti a szokásos technikai csomagot és
  a visszatérő brief-instrukciókat.
- Ezek tényként kerülnek a Tudástárba (hatókör: `diszpo`), ahol láthatók és
  elvethetők.
- Egy elvetett tudást Lara nem ír vissza.

A javaslat emberi szerkesztése javításként rögzül, és a hasonló eseteknél
Lara ebből dolgozik tovább. Ez ugyanaz a tanulási út, mint a TIG-nél.

### Technikai csomag

**Mi kerül a javaslatba**
- Ami a hasonló forgatások (súlyozott) legalább felén ott volt, és legalább
  két forgatáson előfordult.
- Egyetlen, nagyon hasonló forgatásnál annak a technikája is elég.
- Darabszámos eszköznél a szokásos, medián mennyiség kerül be.

**Foglalt vagy nem használható eszköz esetén**
- Lara szabad, azonos kategóriájú helyettesítőt keres; optikánál azonos
  zoom-tartományút.
- Ha nincs ilyen, figyelmeztet.

**Amit nem csinál**
- A projekten már meglévő eszközöket nem duplázza és nem törli.

**Ha van modell (Gemini)**
- A leírás alapján eltérhet a csomagtól.
- Eszközt csak a valós eszköztörzsből választhat; ismeretlen azonosítót a
  rendszer elutasít.

### Brief

- **Modell nélkül:** a projekt saját adataiból áll össze (név, időpont,
  helyszín, leírás, gyártási megjegyzés, kreatív doksi), kiegészítve a hasonló
  briefekben legalább kétszer visszatérő instrukciókkal.
  - A szám-, dátum-, e-mail- és link-tartalmú sorokat nem veszi át, mert azok
    projektfüggők.
- **Modellel:** a hasonló briefek hangnemében fogalmaz, de csak a bemenet
  tényeiből.
- A diszpó alap-emlékeztetője (SD-kártyák) mindig a végén marad.
- Ha a projektnek már van saját briefje, a javaslat figyelmeztet, hogy
  jóváhagyásra leváltja. A régi brief visszaállítható.

### Végrehajtás és visszavonás

A javaslat R1-es kockázatú: belső, visszafordítható írás. Jóváhagyás után egy
mentési ponton belül ez történik:

1. A brief mező íródik, de csak ha a tervezet óta nem módosult. Ha közben
   valaki átírta, a végrehajtás hibára fut, és semmi sem változik.
2. Az eszközök a közös foglalási úton kerülnek a projekthez
   (`services/eszkoz_foglalas.py`). Ez ugyanaz a kód, amit a felület
   „hozzáadás” gombja hív; a kivitel és a visszahozatal a forgatás napjai.
3. Lefut a „Technika ready” ellenőrzés (`services/technika.check_technika`).
   Ez a projektre írja a technikai lista szövegét és az ütközés-riportot.

A diszpót Lara nem küldi ki.

A **Visszavonás** gomb a feladat oldalán:
- törli a Lara által létrehozott foglalásokat;
- visszaállítja a megnövelt darabszámokat;
- visszaírja a korábbi briefet, ha azóta senki nem módosította.

### Hol érhető el

- **Projekt adatlap, Eszközök kártya:**
  - „Mit tanult Lara ehhez?”: előnézet a hasonló forgatásokról, a csomagról
    és a visszatérő instrukciókról;
  - „Kérem Larától”: Lara-feladat és tervezet.
- **Lara Munkasor, diszpó-feladat:** tervezet kérése (brief és/vagy technika),
  jóváhagyás, visszavonás.
- **„Kérdezz Larától” chat:** a „diszpó briefje / technikai lista” kérésből
  diszpó-feladat lesz. A „küldd ki a diszpót” kérésre Lara elmondja, hogy az
  nem az ő dolga.

## Összefogó adminisztrációs feladat

Példák:
- „Zárd le a szeptemberi forgatások papírjait.”
- „Nézd át az összes hiányzó TIG-et a Telekom projekteken.”
- „Készítsd elő a jövő heti forgatások briefjeit és technikáját.”

### 1. Értelmezés

A szövegből Lara kiolvassa a feladat hatókörét:

| Elem | Mit ismer fel |
| --- | --- |
| Időszak | hónapnév; „múlt / ez a hónap”; „ez / jövő hét”; Q1–Q4 vagy „harmadik negyedév”; dátumtartomány |
| Projektkódok | a szövegben szereplő kódok |
| Ügyfél | név szerint |
| Témák | szerződés, TIG, számla, e-mail, diszpó; a „papírozás” vagy „lezárás” a szerződés + TIG + számla hármast jelenti |

- Modellel a hatókör pontosítható, de csak létező kód vagy ügyfél kerülhet
  bele, érvényes dátummal.
- Az értelmezés a felületen látszik, és a „Hatókör javítása” gombbal
  módosítható.

### 2. Terv (mindig élő)

A hatókörbe eső konkrét teendők a teljes rendszerből:
- a lezajlott forgatások hiányzó szerződései, TIG-jei és számlái (az
  Utókövetés mátrixából). A hiányzó számla e-mailes bekérés lesz;
- az elakadt vagy ellenőrzésre váró beérkezett számlák;
- a közelgő (vagy a hatókörbe eső) forgatások hiányzó briefje és technikája.

Az elintézett tétel az újraszámoláskor magától kiesik.

### 3. Bontás részfeladatokra

A „Részfeladatok létrehozása” gomb bontja fel a tervet. Nem történik magától.

**Hogyan bont**
- TIG, szerződés és e-mail: projektkódonként és témánként egy részfeladat.
- Diszpó: forgatásonként egy.
- Számla: a meglévő számla-feladat bekötése, ha van.

**Garanciák**
- Idempotens: egy tételre nem lesz két részfeladat.
- A részfeladatok ugyanazon a tervezet → jóváhagyás → végrehajtás úton mennek
  tovább, mint bármely Lara-feladat.
- Az összefogó feladat maga semmit nem hajt végre.

### Előrehaladás

- Az adatlapon látszik:
  - a kész / összes részfeladat, folyamatjelzővel;
  - a még fel nem bontott tételek száma.
- „Előrehaladás frissítése”: ha minden részfeladat lezárult és a terv
  kiürült, az összefogó feladat kész.

## Biztonság

- **Bizalmi szint:** az új típusok (`diszpo`, `osszefogo`) L0-n (árnyék) indulnak
  (migráció `s2n9k30h7i51`). A javaslat így csak látszik; végrehajtásra
  jóváhagyás mellett is csak akkor kerül, ha a jogosult ember a
  Beállításokban L1-re emeli a szintet.
- **Kapcsolók:** a modul-, mellékhatás- és vészleállítás-kapcsolók és a
  meglévő bizalmi szintek nem változtak.
- **Jóváhagyó:** Lara javaslatairól továbbra is csak a felelőse dönthet.
- **Adatírás:**
  - a tanulás csak Lara saját tábláiba ír;
  - a tervezet üzleti rekordot nem ír;
  - üzleti rekord kizárólag jóváhagyott végrehajtással változik, visszavonhatóan.

## Fájlok

**Backend**
- `app/admin_agent/diszpo_tervezo.py`, `app/admin_agent/osszefogo.py`;
- `app/services/eszkoz_foglalas.py` (közös foglalási út);
- `app/services/technika.py` (`commit` paraméter);
- `app/admin_agent/{enums,executor,chat_feladat,beszelgetes,rendszer,evals,javaslat_leiras,megoldas}.py`;
- `app/api/routes/{admin_agent,equipment}.py`.

**Migráció:** `s2n9k30h7i51_lara_diszpo_osszefogo.py`.

**Frontend**
- `components/admin-agent/{LaraDiszpoGomb,LaraOsszefogo,AdminTaskActions,LaraBeszelgetes,allapotok}.tsx|ts`;
- `components/ProjectDetailContent.tsx`;
- `app/(app)/admin-agent/munkasor/[id]/page.tsx`.

**Tesztek:** `backend/tests/test_lara_diszpo_osszefogo.py`, 13 teszt.
