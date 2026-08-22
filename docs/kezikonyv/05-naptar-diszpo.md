# 05 - Naptár, diszpó, utókövető kérdőív

Oldal: `/naptar`. Fő fájlok: `services/google_calendar.py`, `services/dispo.py`,
`services/google_oauth.py`, `routes/admin_calendar_sync.py`, `routes/callsheets.py`,
`routes/public_utokovetes.py`, `workers/calendar_tasks.py`, `workers/dispo_tasks.py`,
frontend `components/NaptarDiszpoContent.tsx`, `CalendarSyncPanel.tsx`,
`ForgatasIdopontEditor.tsx`, `DispoResponsiblesManager.tsx`.

## Naptár-szinkron

A HYPE CALENDAR Google-naptára **percenként** szinkronizálódik projektekre
(Celery Beat feladat, `workers/calendar_tasks.py`).

Amit tudni kell:

- A naptár **külön Google-fiókban** van, mint a Gmail/Docs - ezért saját
  hitelesítése van (`GOOGLE_CALENDAR_*` env változók). Ha egyik hitelesítés sincs
  beállítva, a szinkron csendben kihagyja a futást; nem hiba.
- A hitelesítés ajánlott módja a **"csak jelentkezz be egyszer" OAuth folyamat**
  (`services/google_oauth.py`): az admin a felületen összeköti a fiókot, a refresh
  token az **adatbázisba** kerül. Így nem kell token- vagy service account JSON-t
  env változóba másolgatni.
- Naptár-azonosítás: ha a `GOOGLE_CALENDAR_ID` üres, név szerint keresi
  (`GOOGLE_CALENDAR_NAME`, alapból "HYPE CALENDAR"). Azonos nevű naptáraknál add
  meg az ID-t.
- **Szín = jelentés**: a `NAPTAR_MEETING_SZINEK` (alapból `3`, a Google "Szőlő"
  lila árnyalata) azt jelöli, hogy az esemény meeting vagy helyszínbejárás, tehát
  **nem diszponálandó**.
- Kézi indítás és állapot: `/api/v1/admin/calendar-sync` (admin). Azért van, hogy
  ne kelljen megvárni a következő automatikus futást, és akkor is legyen
  visszajelzés, ha a Celery worker/beat még nincs rendesen deployolva.

## Diszpó kiküldés

### A lista a TEENDŐ napja szerint tagolódik, nem a forgatáséi szerint

A diszpó egy nappal a forgatás előtt készül: **ma a holnapi napot írjuk**. A
Naptár/Diszpó oldal ezért nem a "mai forgatást" emeli ki, hanem azt, ami ma a
feladat (`components/NaptarDiszpoContent.tsx`):

| Csoport | Melyik nap forgatása | Miért |
|---|---|---|
| **Ma írandó** (kiemelt) | holnapi | ez a mai munka |
| **Holnap írandó** | holnaputáni | ez jön ezután |
| **Mai / Tegnapi forgatás** | mai, tegnapi | a diszpójuk már elment - csak akkor kiabálnak (narancs), ha tényleg maradt rajtuk hátra |
| hétköznap neve | távolabbi | még nem sürgős |

A fejléc első sora ugyanezt mondja számokban: hány diszpó írandó ma, és mennyi a
lemaradás. A csoportok sorrendje marad időrendi (tegnap → ma → holnap → …),
csak a kiemelés és a felirat mondja meg, mikor mi a teendő.

`services/dispo.py`. A korábbi Notion-oldali megoldás checkbox + 60 másodperces
pollozás volt; itt **explicit gombok** vannak: az "Előzetes diszpó" és a "Diszpó
küldése" gomb megnyomása maga a trigger, nincs állapotgép és nincs pollozás.

### A diszpó felől megnyitott projekt SZŰKÍTETT

A Naptár/Diszpó listán egy sorra kattintva a projekt teljes adatlapja nyílik meg
felugró ablakban (`ProjectDetailModal` → `/embed/projektek/[id]`). Ugyanezt a
felugró ablakot használja a **Projektek** lista is - és a kettő nem ugyanazt
mutatja:

| Honnan nyílt | Mi látszik |
|---|---|
| **Diszpó** (`?nezet=diszpo`) | forgatás, gyártás, stáb, technika, gyártás komment, a levél mellékletei, a két küldés |
| **Projektek** (paraméter nélkül) | ugyanez **plusz** az utómunka, az alvállalkozói szerződések, a külsős TIG-ek és a költségek |

A megkülönböztetés az **eredeté**, nem a jogosultságé: ugyanaz az ember a
diszpóból szűkítve, a Projektek listából teljesen látja ugyanazt a projektet. A
diszpós munkája a forgatás körül van; a papírozás hetekkel később, más kézben
történik, és ott csak zajt vinne.

A jogosultság ettől függetlenül is szűkít: akinek **csak** diszpó hozzáférése
van, annak mindenhonnan a szűkített nézet nyílik - a papírozás neki úgyis 403
lenne, és egy működésképtelen kártya rosszabb, mint a hiánya (lásd
[02-auth-jogosultsag.md](02-auth-jogosultsag.md), `OLDAL_ALIASZOK`).

A papírozás **műveletei** (generálás, kiküldés, aláírt példány, számla) a teljes
nézetben sincsenek ott: azok az Utókövetésen maradnak, ahol egyszerre több
projektre rálátva történnek. A projekt adatlapján az **állásuk** és a
**költségek** látszanak, onnan egy link vezet tovább.

### Újraküldés: nagy, piros figyelmeztetés

A kiküldés megismételhető (javított diszpót muszáj újraküldeni), de nem
véletlenül: ha az adott projekten már van kiküldés-állapot
(`elozetes_diszpo_kuldes`, illetve `diszpo`), akkor a gomb felirata
"Újraküldés"-re vált, és kattintásra egy **nagy, piros** "MÁR KI VAN KÜLDVE"
figyelmeztetés ugrik fel; a megerősítő gomb felirata "Igen, újraküldöm". Enélkül
a szürke, mindig ugyanúgy kinéző kérdést az ember átfutja - itt viszont a stáb
MÉG EGYSZER megkapja ugyanazt a levelet.

A figyelmeztetés a megerősítő párbeszéd egy opciója
(`ConfirmProvider` → `ConfirmOpciok.figyelmeztetes` / `megerositoCimke`), az
`ActionButton` csak továbbadja - így bármelyik másik "fáj, ha kétszer megy el"
művelet is megkaphatja. Mindkét hívóhely ugyanúgy viselkedik: a projekt
részletnézet "Diszpó küldése" füle és a Naptár/Diszpó lista.

**Projektkód nélkül nem megy ki diszpó** (`_require_projektkod`). Ez az a pont,
ahol a forgatás "élessé" válik: innentől stáb, technika és papír kapcsolódik rá,
és mindegyik a kódra hivatkozik vissza. A naptárból a projekt kód nélkül érkezik,
ezért a kiküldés az a hely, ahol számon kérjük.

A formátum viszont **szabad**: bármi elfogadható, ami nem üres és nem a régi
import-gyűjtő (`NAPTAR-IMPORT`, `ISMERETLEN-NOTION-IMPORT`) - más ügyfél
kódrendszere vagy egy régi sorozat is jó. A szabály egy helyen él:
`services/projektkod_kotes.py`, lásd
[03-projektek-ugyfelek.md](03-projektek-ugyfelek.md#a-projektkód-kötése-mi-tartozik-egy-kód-alá).

Egyetlen állapotfüggő viselkedés maradt: ha a projektnek már van
`gmail_thread_id`-je, a további levelek **ugyanabba a Gmail-szálba válaszolnak**.

Fontos részlet, ami elsőre nem magától értetődő: a Gmail API `threadId`-je csak a
**küldő saját fiókjában** garantálja a szálba fűzést. A címzettek postaládájában a
valódi RFC822 `In-Reply-To`/`References` fejléc dönt, aminek igazi Message-ID-t
kell tartalmaznia - ezért tároljuk a `gmail_thread_id` **mellett** a
`gmail_last_message_id`-t is (Project modell), és azt adjuk át `in_reply_to`-ként.

Egyéb:

- A diszpó-levelek feladóneve külön állítható (`DISPO_SENDER_NAME`, alapból
  "HYPE GYÁRTÁS"), mert a szerződés/TIG levelek nem a gyártástól mennek. A küldő
  **cím** mindig a `GMAIL_SENDER`.
- A kész diszpó PDF a Drive-ra kerül: `DRIVE_DISZPO_FOLDER_ID`, ha üres, a
  generikus kimeneti mappa, ha az sincs, a Drive gyökere.
- Ki a felelős egy diszpóért: `/api/v1/dispo-responsibles`.

## HYPE 2026 tábla (a Google Sheet diszpótáblája)

`/diszpo-tabla` - a korábban Google Sheetben vezetett munkafüzet, minden
munkalapjával, fülekként. `models/diszpo_tabla.py`,
`routes/diszpo_tabla.py`, `components/DiszpoTablaRacs.tsx`.

### A CELLA SZÍNE ADAT, nem formázás

Ez a tábla nem csak beosztás volt: a szín hordozta a legfontosabb információt,
azt, hogy ki melyik nap dolgozott. Ezért nálunk sem "kitöltőszín", hanem
nevesített érték:

| Szín | Jelentés | Munkanap? |
|---|---|---|
| **zöld** | aznap dolgozott (a vágóknál: terepen) | **igen** |
| **kék** | a vágók munkanapja (irodában) | **igen** |
| **fehér** | munkanap volt, de nem tudtunk neki munkát adni | **igen** |
| piros | nem munkanap (szabadnap) | nem |
| szürke | nem releváns (akkor még nem dolgozott nálunk) | nem |

A **fehér** a lényeges eset: a napja le volt kötve, csak nem jött rá munka -
a szerződött napokból ugyanúgy fogy (lásd
[04-csapat-felszereles.md](04-csapat-felszereles.md)).

**Egy nap egy munkanap**, akkor is, ha aznap két diszpó volt: a táblázatban
olyankor két sor tartozik ugyanahhoz a naphoz (a második sor dátum-mezője
üres, az import viszont továbbviszi a dátumot). A szerződés napokról szól, nem
diszpókról.

### Miért generikus rács

A munkafüzet hat munkalapja mind más alakú: a belsős tábla 25 oszlop
emberekkel, a külsős 146 oszlop kategóriákkal, az AUTÓK egy lista, a PROJECT
KÓDOK egy másik. Egy "mindent tudó" séma vagy csak az egyiket szolgálná ki,
vagy annyi kivétellel lenne tele, hogy senki nem érti. A rács mindet elbírja.

A JELENTÉS ott van, ahol kell: az **oszlop** tudja, melyik munkatársé
(`employee_id`), a **sor** tudja, melyik naphoz tartozik (`datum`) - ez a két
kapcsolat teszi a rácsot számolhatóvá. **Kötés nélkül egy oszlop színei nem
számítanak bele semmibe**: a "GERI" felirat nekünk nem azonosít senkit. Az
import csak EGYÉRTELMŰ névegyezésre köt (két azonos keresztnév között egy
szkript nem dönthet), a többit a felületen kell megadni - az oszlop egy
cellájára kattintva.

### Úgy működik, mint egy táblázat

A felület szándékosan a Google Sheets viselkedését követi, mert a munka is
ugyanaz:

| Amit csinálsz | Ami történik |
|---|---|
| kattintás | kijelölés (a jobb felső sarok kiírja: `G14 · GERI · 2026-08-13`) |
| gépelés | azonnal szerkesztés, a leütött karakterrel |
| Enter / dupla kattintás | szerkesztés; Enter kilép és lelép egy sort |
| nyilak, Tab | mozgás cellák között (a nézet utána görget) |
| Shift+nyíl, húzás | TARTOMÁNY kijelölése |
| színgomb | a teljes kijelölt tartomány színezése - egy kör-úttal |
| Delete | a kijelölt tartomány tartalmának törlése |
| jobb gomb | sor/oszlop beszúrása vagy törlése |

Van **sorszám és oszlopbetű** (`A`, `B`, … `1`, `2`, …), a fejlécsorok fent
ragadnak, és az első oszlopok (dátum, nap, diszpószám) balra fagyasztva
maradnak - 146 oszlopnál e nélkül nem lehetne tudni, melyik sorban vagyunk.

**Az egész év egyben látszik**, hónapválasztó nélkül. A külsős munkalap 381
sor x 146 oszlop = 55 ezer cella, amitől a böngésző megállna, ezért a rács
**virtualizált**: csak a látható ablakot rajzoljuk ki, a görgetősáv viszont a
teljes méretet mutatja - a görgetés így ugyanaz, mintha minden ott volna.

### Sor és oszlop beszúrása

A beszúrás/törlés az INDEXEKET tolja el, és ezt nem lehet naivan egy
`idx = idx + 1` utasítással megtenni: az egyediségi megkötés menet közben
sérülne, mert a mozgó sor beleütközne a még nem mozdult szomszédjába. Ezért
**két lépésben** toljuk (`_tolas`): előbb egy nagy eltolással félretesszük az
érintett tartományt, majd onnan hozzuk vissza a helyére. Mindkét lépés egy
utasítás - a soronkénti mozgatás egy 146 oszlopos munkalapon több tízezer
UPDATE lenne.

Az új sornak **nincs dátuma**, tehát addig egyetlen naphoz sem tartozik (a
munkanap-számlálásba sem számít). Az új oszlop a bal szomszédja szekcióját
örökli, és amíg nincs munkatárshoz kötve, a színei nem számítanak bele
semmibe.

A **törlés külön jogosultság** (`delete`): a tartalmat is viszi.

### Az átvétel

```bash
python scripts/diszpo_tabla_import.py              # próba: mit hozna át
python scripts/diszpo_tabla_import.py --vegrehajt  # élesben
```

A megosztott linkről tölti le a munkafüzetet (`export?format=xlsx`) - nem kell
hozzá Google-fiók, és a CSV-vel ellentétben ez viszi a SZÍNEKET is. Az
xlsx-olvasáshoz **openpyxl** kell (`requirements.txt`); ha egy régebbi
image-ben még nincs benne, a szkript ezt meg is mondja, és addig egy
`pip install openpyxl` átsegít rajta.

Ha a konténerből nem érhető el a Google, a munkafüzet letölthető kézzel és
átadható: `--fajl hype2026.xlsx`. A szkript
**újrafuttatható**: munkalaponként cseréli a tartalmat, tehát a második
átvételnél (amikor teljesen átálltok a rendszerre) ugyanígy futtatható. Ami
viszont nálunk készült és a Sheetben nincs benne, azt a csere eldobja - ezért
a próba-futás előbb kiírja, mi történne.

## Callsheet

`/api/v1/callsheets` - a `/naptar` oldal jogosultságával, CRUD-generátorral.

## Utókövető kérdőív (publikus)

A forgatás vége után **12 órával** automatikus email megy ki
(`workers/dispo_tasks.py`), benne link a kérdőívre. A végpont bejelentkezés
nélküli: `/api/v1/public/utokovetes`, frontend: `frontend/app/kerdoiv`.

A link nem a nyers `project_id`-vel azonosít, hanem egy `utokoveto_token`-nel
(`Project.utokoveto_token`), hogy a publikus végpont ne legyen kitalálható vagy
végigpróbálható. A projekt neve/kódja/dátuma az űrlapon csak megjelenítés - a
link már projekt-specifikus, így nincs elgépelhető projektkód-mező.

A beérkező válaszok: `models/post_shoot_feedback.py`, feldolgozásuk az
[utókövetésben](06-papirozas.md) és az utómunka-modulban látszik.
