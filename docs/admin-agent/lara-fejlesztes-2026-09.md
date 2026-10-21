# Lara — 2026. szeptemberi bővítés: beszélgetés, tanítás, tudáspróba, tanulás-javítás

Átadó dokumentum. A `lara-mukodese-es-tanulasa.md` írja le, hogyan működik
Lara; ez a dokumentum azt, hogy **mi változott**. Fázisonként megadja:

- a fájlokat, a migrációt és a kapcsolókat;
- a ténylegesen lefuttatott teszteket;
- a kézi ellenőrzés lépéseit;
- a visszaállítás útját.

Jelölések:

- **KÉSZ + TESZTELT**: automata teszt fedi, és lefutott;
- **KÉSZ, ÉLŐBEN MEGNÉZVE**: böngészőben, demóadattal végigkattintva;
- **NEM ELLENŐRZÖTT**: megírva, de valódi külső szolgáltatással (Gemini,
  Gmail) nem próbáltam;
- **KÜLSŐ BEÁLLÍTÁS KELL**: kulcs vagy kapcsoló nélkül nem működik.

---

## 0. Kódellenőrzés — megfeleltetés és eltérések

A dokumentációt kiindulópontnak vettem, nem bizonyítéknak. Ahol a kód és a
leírás eltért, itt szerepel, mit csinál a kód, mit állított a leírás, és mi
lett a változás.

### 0.1 Mi volt meg, mit bővítettem, mi új

| Terület | Állapot a bővítés előtt | Mi lett |
|---|---|---|
| Tudás-darab (`aa_memory_chunks`) | volt: hatókör, minősítés, érvényes / visszavont | **bővítve**: fajta, bizonyíték-szint, hatókör-részletek, érvényességi ablak, verzió + előző verzió, jóváhagyó és ideje, üzleti ügy, felhasználás száma és ideje, használhatóvá válás ideje |
| Visszakeresés (`memory.py`, `embedding.py`) | volt: szabályok + hasonló esetek | **bővítve**: rovatok (szabály / kivétel / rendszerismeret / hasonló eset), hipotézis-jelölés, érvényességi ablak, felhasználás rögzítése, magyar szótő-egyezés, jogosultság-szűrés a kézikönyvre |
| Tartós sor (`aa_outbox`) | **volt, de semmi nem használta** | az E fázis sora lett |
| Csak-olvasó eszközhurok (`nyomozas.eszkozhurok`) | volt (utánanézés, megoldás) | a beszélgetés **ugyanezt** használja |
| AI asszisztens (`services/ai_assistant.py`) | külön rendszer, műveleteket is végez (megerősítéssel) | **nem változott**; Lara beszélgetése külön, CSAK OLVAS |
| Személyiség | nem volt | **új**: `szemelyiseg.py` + `szemelyiseg_forras/lara_v1.md` |
| Beszélgetés, tanítás, tudáspróba | nem volt | **új**: `beszelgetes.py`, `tanitas.py`, `tudasproba.py` + felület |
| Rendszerkézikönyv | csak a `docs/kezikonyv` fájlok, Lara nem használta | **új**: `kezikonyv.py` (tervezet → jóváhagyás, verziók) |
| Üzleti ügy / vizsgakészlet | nem volt; rekordokat számolt | **új**: `ugyek.py`; a számolás ügyekre állt át |
| Futásnapló, folyamat-állapot | a Celery-hibák csak a logba mentek | **új**: `folyamat.py` + futásnapló minden ütemezett feladatra |
| Minőségmérés | találati arány + Tudásháló-% | **új**: `minoseg.py`, öt külön mérőszám |
| Szakmai szabálytesztek | csak biztonsági eval | **új**: `szakmai_eval.py` + élesítési kapu |

### 0.2 Eltérések kód és leírás között

1. **Esetszám.**
   - A kód: a megerősítés, az önellenőrzés (`Tudas`) és a tapasztalás
     **rekordokat / tudás-darabokat** számolt.
   - A leírás: „esetekről” beszélt.
   - Hatás: öt számla ugyanarra a projektkódra öt „egybehangzó esetnek”
     számított.
   - Változás: **üzleti ügyeket** számol (D fázis).
2. **`tanulasi_halmaz = "jovahagyott"`.**
   - A kód: a jelöltekre is ezt írja.
   - A név alapján jóváhagyást sugall, de valójában a TANÍTÓ halmaz jelölése
     (szemben a `holdout`-tal).
   - Változás: nincs átnevezés (az adatbázis és a meglévő kód hivatkozik rá).
     A használhatóságot az `ervenyes` + `visszavont` + érvényességi ablak
     dönti el (`memory.hasznalhato()`).
3. **Ütemezett feladatok hibái.**
   - A kód: csak a logba írta őket.
   - A felületen nem látszott, hogy egy forrás áll-e.
   - Változás: futásnapló és forrásonkénti állapot (A fázis).
4. **Számla-elemzés.**
   - A kód: csak kézzel indult (Munkasor / feladat).
   - Változás: kapcsolható automatikus elemzés, **alapból KI**, és akkor is
     csak javaslat (E fázis).
5. **Tudásháló-%.**
   - A felület „bizonyosság”-nak nevezte, ami feladat-pontosságnak
     olvasható.
   - Valójában a kapcsolat mögötti bizonyíték erőssége.
   - Változás: felirat „bizonyíték-erősség”; a pontosságot a minőségmérés
     méri, külön.
6. **„Tanulás és megfigyelés” forrás.**
   - Egyik migráció sem kapcsolja be; kézzel kell.
   - A leírás ezt helyesen írta. Nem változott.
7. **Utánanézés és megoldási javaslat.**
   - Strukturált (JSON) kimenetet adnak belső használatra.
   - A személyiség-réteg **szándékosan nem** került beléjük: a személyiség-
     dokumentum szerint strukturált kimenetbe nem kerül társalgási réteg.
   - A személyiség az ember felé szóló beszélgetésben él.

Üzleti szabályt egyik eltérés feloldásához sem találtam ki.

---

## P. Személyiség-réteg

- **Mi készült.**
  - Közös, verziózott személyiség: `app/admin_agent/szemelyiseg_forras/lara_v1.md`.
    Ez a személyiség-dokumentum B része, változtatás nélkül.
  - `szemelyiseg.py`:
    - aktív verzió (`limitek.szemelyiseg_verzio`, alap `v1`; ismeretlen
      érték → `v1`);
    - profilok: `belso` **élő**, `ugyfel` **előkészítve, KIKAPCSOLVA**;
    - szerveroldali kommunikációs kontextus;
    - prompt-sorrend: **biztonság > feladat > hiteles kontextus > profil >
      személyiség**, amit a prompt ki is mond;
    - állapothoz kötött mondatok („Elkészítettem a piszkozatot… Még nem
      küldtem el.”);
    - determinisztikus stílusőr: emoji és sablonos nyitás törlése; tiltott
      fordulat, hamis végrehajtás-állítás és tiltott név jelzése;
    - modell nélküli, tényszerű tartalék-válasz.
  - Megszólítás: csak a felhasználó SAJÁT, mentett preferenciája
    (`limitek.megszolitasok`). A beállítás-mentés nem írja felül.
  - A 20 kötelező kommunikációs teszt:
    - `szemelyiseg_forras/kommunikacios_tesztek_v1.json`: forgatókönyvek,
      kemény feltételek, rubrika;
    - `kommunikacios_teszt.py`: prompt és kiértékelő;
    - `scripts/lara_kommunikacios_teszt.py`: élő futtató.
- **Bekötési pont.** Jelenleg egy: a „Kérdezz Larától” beszélgetés
  (`beszelgetes.valaszol`). Az utánanézés és a megoldás strukturált kimenet —
  lásd 0.2 / 7.
- **Tesztek.**
  - `tests/test_lara_szemelyiseg.py`: 8 teszt.
  - `tests/test_lara_kommunikacio.py`: 12 teszt, a 20 forgatókönyv
    megléte + a kiértékelő jó / rossz válaszokon.
  - **KÉSZ + TESZTELT.**
- **NEM ELLENŐRZÖTT.** A 20 forgatókönyv élő modellen. Nincs Gemini-kulcs a
  fejlesztői környezetben; a futtató ilyenkor kilép, és eredményt nem állít.
- **Kézi ellenőrzés.**
  1. Futtasd: `cd backend && python -m scripts.lara_kommunikacios_teszt --kimenet jelentes.json`.
  2. A kemény feltételek eredménye kiíródik.
  3. A rubrikát (természetesség, tömörség, kedvesség, humor, pontosság-érzet)
     ember töltse ki mintavétellel.
- **Visszaállítás.**
  - Új verzió: új fájl (`lara_v2.md`) + sor a `VERZIOK`-ban, majd
    `limitek.szemelyiseg_verzio = "v2"`.
  - Vissza: `"v1"`.
  - A személyiség cseréje a kommunikációs teszt lefutása és jóváhagyás után
    történjen.
- **Az ügyfél-chat bekapcsolásának feltételei** (ma NINCS bekapcsolva — Lara
  ügyfelekkel NEM kommunikál):
  1. adattakarékos ügyfél-nézet (belső megjegyzés, önköltség, árrés, más
     ügyfél adata nélkül);
  2. ügyfél-azonosítás és projekt-hatókör;
  3. a 20 teszt élő futtatása és emberi rubrika-pontozás, kritikus hiba
     nélkül;
  4. csendes időszak és aláírás beállítása;
  5. emberi átadás útja;
  6. a tulajdonos kifejezett döntése — csak ezután állhat a
     `PROFILOK["ugyfel"].engedelyezve` True-ra.

## Q. „Kérdezz Larától” felület (`/admin-agent/beszelgetes`)

- **Kérdezz.**
  - Lara a jóváhagyott tudásából (rovatonként címkézve) és a rendszer
    csak-olvasó eszközeivel válaszol, **a kérdező jogosultságával**.
  - Csak a kapott címkékre hivatkozhat; ismeretlen hivatkozást eldob, és
    ezt jelzi.
  - Linket csak belső útvonalra ad.
  - „Honnan tudom”: a hivatkozott és a megkapott, de nem használt tudás, az
    eszköz-lépések, a bizonyítékok és a stílusőr-jelzések.
  - Értékelés: helyes / részben / hibás, megjegyzéssel. Hibás válaszból egy
    kattintás a tanítás.
- **Tanítsd:** lásd a C fázist.
- **Tudáspróba.**
  - Számla-vizsga: vak jóslat a vizsgaügyeken (D fázis).
  - Saját kérdés elvárt válasszal: Lara nem látja az elvárt választ; a két
    válasz egymás mellett látszik, és te értékeled.
- A beszélgetés **csak a gazdájáé** (más 404-et kap). Vészleállításnál nem
  válaszol (423), olvasni lehet.
- **Fájlok.**
  - Backend: `beszelgetes.py`, `api/routes/lara_beszelgetes.py`.
  - Frontend: `app/(app)/admin-agent/beszelgetes/page.tsx`,
    `components/admin-agent/LaraBeszelgetes.tsx`.
  - Fül és menü: „Kérdezz Larától”.
- **Tesztek.** `tests/test_lara_beszelgetes.py`: 15 teszt (hamis modell-
  beszélgetéssel). **KÉSZ + TESZTELT**, és **ÉLŐBEN MEGNÉZVE** modell
  nélküli módban. Képernyőképek a munkamenet scratchpadjában:
  `lara_1..8_*.png`.
- **NEM ELLENŐRZÖTT:** a válasz valódi Gemini-modellel (hangnem, eszközhívások
  minősége).

## A. A tanulási folyamat ellenőrizhetősége

- **Futásnapló.**
  - Mind a 11 ütemezett Lara-feladat (`workers/admin_agent_tasks.py`,
    `_feladat` burkoló) rögzíti a sikert, a hibát (rövid, titok nélkül) és a
    kihagyás okát.
  - Forrásonként EGY `aa_learning_runs` sor (`folyamat:<forrás>`), ezért
    korlátos marad, és nem kell törölni.
  - A percenkénti visszacsatolás kihagyását nem naplózza.
- **Állapotok.**
  - Forrásonként (`folyamat.allapot`, `GET /admin-agent/folyamat`), külön-
    külön: `nincs_adat`, `kikapcsolva`, `nincs_jogosultsag` (pl. hiányzó
    Gmail-hitelesítés vagy modell-kulcs), `feldolgozasi_hiba`,
    `jovahagyasra_var`, `rendben`.
  - Mellette: a várakozó munka, és a gyors visszacsatolás sorának állapota.
- **Nyomvonal.** Egy tudás-darab útja (`GET /admin-agent/memory/{id}/trace`):
  - beérkezés és forrásesemény;
  - napló-bejegyzések, jóváhagyó és ideje;
  - mikor vált használhatóvá, hányszor és mikor került Lara elé;
  - mely szabály hivatkozik rá.
- **Teljes utas teszt.** `test_teljes_ut_tanitastol_a_felhasznalasig`:
  tanítás → sor → feldolgozás → a beszélgetés visszakeresi → a felhasználás
  rögzül → a nyomvonal mindent mutat. **KÉSZ + TESZTELT.**
- **Felület.** Tanulás és minőség → „Tanulási folyamat és minőség”.
  **ÉLŐBEN MEGNÉZVE.**
- **Megjegyzés.** A futásnapló a bővítés óta gyűlik; a korábbi futások a
  meglévő kártyákon látszanak.

## B. Verziózott rendszerkézikönyv

- **Szakaszok.** `kezikonyv.py` az `aa_memory_chunks`-ban tárolja őket
  (`hatokor="kezikonyv"`; új tábla nincs).
- **Technikai leírás** (`kezikonyv_technikai`).
  - Gépi TERVEZET a SQLAlchemy-modellekből (docstring + a mezők `#:`
    megjegyzései) és a `docs/kezikonyv/*.md` fejezeteiből.
  - Jóváhagyásig nem használható.
- **Üzleti eljárás** (`kezikonyv_uzleti`).
  - Csak ember írja, ugyanúgy jóváhagyásra vár.
  - Technikai leírásból sosem lesz magától üzleti szabály.
- **Verziók.**
  - Megváltozott forrásból új verzió lesz (tervezet), az előzőre mutatva.
  - A régi jóváhagyott addig érvényes. A jóváhagyáskor az érvényessége
    lezárul (`ervenyes_ig`), de nem törlődik.
- **Keresés.** Csak a releváns, jóváhagyott szakaszok (szótő-egyezés), soha
  a teljes kézikönyv.
  - Az oldalhoz kötött szakasz (pl. pénzügy → `/penzugyek`) csak annak
    megy, aki látja az oldalt.
  - Ez a listára és a beszélgetésre egyaránt vonatkozik.
- **Tudástár.** A Tudástár általános jóváhagyása (`/memory`, `/memory/bulk`)
  nem kezeli a kézikönyvet (409 / kihagyva), és a listában sem jelenik meg.
- **Felület.** Tudástár → „Rendszerkézikönyv”. **ÉLŐBEN MEGNÉZVE:** a
  generálás 246 tervezetet hozott.
- **Tesztek.** `tests/test_lara_kezikonyv.py`: 7 teszt. **KÉSZ + TESZTELT.**
- **Kézi ellenőrzés.**
  1. Tudástár → Rendszerkézikönyv → „Tervezetek frissítése a kódból”.
  2. Hagyj jóvá egy szakaszt.
  3. Kérdezz rá a „Kérdezz Larától” oldalon.
  4. A „Honnan tudom” alatt R-címkével jelenik meg.
- **Éles teendő.** A 246 technikai tervezet átnézése és jóváhagyása: amíg
  nincs jóváhagyva, Lara nem használja.

## C. „Tanítsd Larát”

- **Előnézet** (`tanitas.elonezet`). Semmit nem ment. Ezeket mutatja:
  - fajta: eseti magyarázat / kivétel / fogalom / általános szabály;
  - egymondatos állítás;
  - terület, partner, projektkód;
  - kivételek, érvényesség;
  - egy célzott tisztázó kérdés;
  - „mi lesz belőle”, és a már meglévő, kapcsolódó tudás.
  Modell nélkül kulcsszavakból tippel, és mindig rákérdez a fajtára.
- **Megerősítés** (`tanitas.megerosit`).
  - Tudás-darab lesz (forrás = a tanító ember, napló-bejegyzéssel).
  - Tudás-aktiválási joggal (`delete` a Lara oldalon) azonnal használható;
    anélkül jelölt a Tudástárban.
  - **Általános szabályból legfeljebb szabály-PISZKOZAT** (`draft`). A tudás
    jóváhagyása NEM a szabály élesítése.
  - Idempotens: ugyanaz a tanítás másodszor nem lesz új tudás.
- **A tanító szöveg adat.** Nem változtat beállítást, jogosultságot,
  bizalmi szintet (erre teszt van).
- **Tesztek.** A `test_lara_beszelgetes.py` tanítás-tesztjei.
  **KÉSZ + TESZTELT**, **ÉLŐBEN MEGNÉZVE**.
- **NEM ELLENŐRZÖTT:** a modell-alapú előnézet valódi Geminivel.

## D. Összekapcsolt esetek (üzleti ügy) és elkülönített vizsgakészlet

- **Ügykulcs** (`ugyek.py`).
  - Projektkóddal: projektkód(ok) + partner.
  - Projektkód nélkül a dokumentum maga (pl. havi közüzemi számla — minden
    hónap külön döntés).
- **Ügyeket számol** (nem rekordokat):
  - a megerősítés: auto-jóváhagyás, szabályjavaslat;
  - az önellenőrzés tudása (`Tudas.cel`);
  - a tapasztalás: tények és igazolt állítások.
- **Viselkedésváltozás.** Egy partner ugyanarra a projektkódra küldött több
  számlája mostantól EGY esetnek számít. Így a „TAPASZT-1 kódra rögzítjük”
  jellegű állítás egyetlen ügyből nem igazolódik.
  - Ezt a meglévő tapasztalás-tesztekben is átírtam, indoklással.
  - A papír-önellenőrzés (`onellenorzes_papir.PapirTudas`) rekordonként
    számol. Ott egy papír jellemzően maga az ügy — nem változott.
- **Oka és hipotézis.**
  - A Gemini partner-profil és önreflexiós tanulság `bizonyitek_szint =
    "hipotezis"` jelölést kap, és „[HIPOTÉZIS…]” előtaggal megy a modell elé.
  - A tapasztalás adaton igazolt állítása `forras`.
- **Vizsgakészlet** (`limitek.vizsgakeszlet`, **alap: KI**; arány:
  `limitek.vizsga_arany`, alap 0,2).
  - Bekapcsolva a vizsgaügyek kimaradnak ezekből: a megerősítés, az
    önellenőrzés tudása, a tapasztalás, a partner-profil.
  - Kikapcsolva a Tudáspróba eredménye „szennyezett” jelölést kap.
- **Tesztek.** `tests/test_lara_ugyek.py`: 4 teszt, és a frissített
  `test_admin_agent_tapasztalas.py`. **KÉSZ + TESZTELT.**
- **Visszaállítás.** A kód-commit visszavonása. Adatot nem ír át, csak a
  saját táblájában tölti az `ugy_kulcs` mezőt.

## E. Gyors visszacsatolás és automatikus számla-elemzés

- **Gyors visszacsatolás** (`visszacsatolas.py`, `limitek.gyors_visszacsatolas`,
  **alap: KI**).
  - Ezek ugyanabban a tranzakcióban kerülnek az `aa_outbox` sorba, mint maga
    a változás:
    - a mentett javítás;
    - a feladathoz adott magyarázat;
    - a Tudástár-jóváhagyás;
    - a tanítás;
    - a kérdésre adott válasz.
  - A Celery percenként dolgozza fel, idempotensen:
    - háttér-tanuló;
    - beágyazás, ha be van kapcsolva;
    - megerősítés.
  - Hibánál visszalépő újrapróba (1, 2, 4… perc), 5 próba után karantén.
  - A sor sorai maradnak naplónak.
  - A meglévő ütemezett folyamatok változatlanul futnak (helyreállítási út).
- **Automatikus számla-elemzés** (`limitek.auto_szamla_elemzes`,
  **alap: KI**).
  - Csak a bekapcsolás UTÁN érkezett, kiolvasott számlák; percenként
    legfeljebb 5.
  - `arnyek_elemzes(csak_javaslat=True)`: a policy döntésétől függetlenül
    CSAK javaslat.
    - nincs jóváhagyás;
    - nincs végrehajtási sor;
    - nincs értesítés;
    - nincs üzleti rekord;
    - nincs bizalmi szint-emelés.
  - Erre teszt van: a hamisított „jóváhagyást kérne” policy mellett sem jön
    létre jóváhagyás.
- **Tesztek.** A `test_lara_beszelgetes.py` visszacsatolás-, csak-javaslat
  és teljes utas tesztjei. **KÉSZ + TESZTELT.**
- **NEM ELLENŐRZÖTT:** élő Celery-worker percenkénti futása (a feladat
  regisztrálva van, és kézzel importálható).
- **Bekapcsolás.** Beállítások → „Gyors visszacsatolás és vizsgakészlet”.

## F. Kategorizált visszakeresés, valós minőség, szakmai tesztek

- **Visszakeresés.**
  - `memory.tudas_csomag` / `kapcsolodo_tudas` rovatai: szabályok,
    kivételek, rendszerismeret, hasonló esetek.
  - Az aktuális üzleti adatot a beszélgetés az eszközökkel a hiteles
    rekordokból olvassa, nem a tudásból.
  - Minden visszakeresés a használható (jóváhagyott, érvényes, nyitott
    ablakú) tudásra szűr. A kézikönyvnél a kérdező oldal-jogosultságára is.
- **Minőség** (`minoseg.py`, `GET /admin-agent/minoseg`). Öt KÜLÖN szám,
  mintaszámmal; n = 0 esetén „nincs adat”, nem 0%:
  1. megtalálja-e a releváns tudást;
  2. helyesség új eseteken (Tudáspróba + önellenőrzés);
  3. emberi javítás igénye;
  4. indokolt kérdezés;
  5. tanulási késés (medián perc, forrásonként).
  A Tudásháló-% felirata „bizonyíték-erősség” lett.
- **Szakmai tesztek** (`szakmai_eval.py`).
  - Szabály-VERZIÓHOZ kötött esetek: pozitív / ellenpélda / hiányos adat.
  - Egy kattintással kiinduló esetek generálhatók.
  - **Élesítési kapu:** ha a szabály aktuális verziójához van eset, az
    élesítéshez mindnek át kell mennie. Ha nincs eset, a korábbi feltételek
    maradnak, és a felület jelzi a hiányt.
  - A biztonsági eval a szakmai eseteket nem futtatja.
- **Tesztek.** A `test_lara_beszelgetes.py` minőség- és szakmai tesztjei.
  **KÉSZ + TESZTELT.**

---

## Migráció

`backend/alembic/versions/q0k7h18e5f29_lara_beszelgetes_tudas_bovites.py`
(előző: `p9j6g07d4e18`).

- **CSAK ADDITÍV.**
  - Új oszlopok az `aa_memory_chunks` és az `aa_eval_cases` táblán.
  - Új táblák: `aa_beszelgetesek`, `aa_beszelgetes_uzenetek`.
- Meglévő adatot nem ír át.
- Fejlesztői adatbázison upgrade → downgrade → upgrade lefutott.
- **Élesben még nem futott**: a deploy futtatja.
- **Visszaállítás:** `alembic downgrade p9j6g07d4e18`. Ez az új oszlopokkal
  és a beszélgetésekkel együtt törli az azokban lévő adatot is.

## Kapcsolók összefoglalója (`aa_settings.limitek`)

| Kulcs | Alap | Hatás |
|---|---|---|
| `gyors_visszacsatolas` | KI | tartós sor + percenkénti feldolgozás |
| `auto_szamla_elemzes` | KI | automatikus, csak-javaslatos számla-elemzés (bekapcsoláskor `auto_szamla_elemzes_tol` rögzül) |
| `vizsgakeszlet` | KI | a vizsgaügyek kimaradnak a tanító összesítésből |
| `vizsga_arany` | 0,2 | a vizsgaügyek aránya |
| `szemelyiseg_verzio` | `v1` | aktív személyiség-verzió |
| `megszolitasok` | — | felhasználónkénti SAJÁT megszólítás (csak a felhasználó állíthatja) |

A modul-, mellékhatás- és vészleállítás-kapcsolók, a bizalmi szintek, az
R0–R3 besorolás, a végrehajtási őrök, a jóváhagyás és a felelős-korlátozás
**nem változott**. Utalás továbbra sincs.

## Lefuttatott ellenőrzések (2026-09-24)

- Backend: `pytest` teljes csomag — **268 átment, 1 kihagyva**. Az új
  tesztfájlok:
  - `test_lara_szemelyiseg`;
  - `test_lara_kezikonyv`;
  - `test_lara_ugyek`;
  - `test_lara_beszelgetes`;
  - `test_lara_kommunikacio`.
- `ruff` az új / módosított fájlokon: tiszta. A `pipeline_szamla.py`
  `CEL_TIPUSOK` és a routes `EvalCase` importja korábbi, nem az enyém.
- Frontend: `tsc --noEmit` tiszta; `eslint` a módosított fájlokon tiszta;
  `next build` sikeres.
- Élő bejárás (Playwright, demóadattal, modell nélkül) hiba nélkül:
  1. tanítás;
  2. kérdés;
  3. „Honnan tudom”;
  4. értékelés;
  5. tudáspróba;
  6. folyamat;
  7. kézikönyv.
- Takarítás: a bejárás után minden demósort töröltem, és az összes
  időbélyeg-oszlopot végigellenőriztem.
  - Csak a beállítás-sor `updated_at` értéke frissült: ezt a meglévő
    vészleállítás-teszt teszi, az értékeket visszaállítja.
  - A levelezés-teszt mostantól a futásnapló sorait is eltakarítja.

## Nem ellenőrzött / külső beállítás kell

- **Valódi Gemini.** Nincs kulcs a fejlesztői környezetben. Nem próbáltam
  élőben:
  - a beszélgetés modell-válaszát;
  - a tanítás modell-előnézetét;
  - a 20 kommunikációs forgatókönyvet.
  Mindegyiknek van hamis modellel futó automata tesztje.
- **Élő Celery-worker** a percenkénti visszacsatolás-feladattal.
- **Éles Gmail:** nem érinti ez a bővítés.
- **Éles adatbázison a migráció:** a deploy futtatja.
