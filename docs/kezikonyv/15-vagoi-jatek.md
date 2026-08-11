# 15 - Vágói játék

Havi pontverseny a vágók között. Oldal: `/vagoi-jatek`, jogosultság:
`/vagoi-jatek`, backend: `routes/vagoi_jatek.py`, logika:
`services/vagoi_jatek.py`, modell: `models/vagoi_jatek.py`.

## Pontozás

| Miért | Mennyi |
|---|---|
| Ellenőrzésbe tett anyag | **50 pont** |
| Vágás | **3 perc = 1 pont** (lefelé kerekítve) |

A számok egy helyen élnek (`models/vagoi_jatek.py` `ELLENORZES_PONT`,
`PERC_PER_PONT`), és a felület a `/szabalyok` végpontról kéri le őket - így a
magyarázó szöveg nem csúszhat el a valóságtól.

**A pontozás a meglévő munkából jön, nem külön adminisztrációból**: az
ellenőrzésbe tett anyag és a lemért vágási idő úgyis keletkezik. Egy játék,
amiért külön adatot kell vezetni, két hét után elhal.

## Miért van saját esemény-tábla az ellenőrzéshez

Az 50 pont a **megtörtént eseményhez** tartozik, nem az anyag mai állapotához.
Ha a pontot abból számolnánk, hogy most éppen mi az `allapot`:

- egy későbbi állapotváltás **visszamenőleg elvenné** a pontot (az anyag
  továbbmegy "Kész"-be, és eltűnik a havi eredményből),
- egy oda-vissza kattintgatás pedig **újra és újra adná**.

Egy versenynél mindkettő végzetes: az egyik igazságtalan, a másik játszható.
Ezért a `vago_ellenorzes_esemenyek` tábla `deliverable_id`-je **egyedi** -
ugyanaz az anyag akkor sem hoz még egyszer pontot, ha kiveszik és visszateszik.
Az `idopont` dönti el, melyik hónapba számít.

Az esemény a `postproduction.py` `_after_deliverable_update` hookjában
keletkezik, tehát minden állapotváltás átmegy rajta. Az "ellenőrzés" felismerése
**névre megy** (`ellenorzes_allapot`): az állapotok szabad szövegek, amiket
admin szerkeszt, ezért nem fix listához hasonlítunk, hanem a nevében keressük
az "ellenőrzés" szót, ékezet- és kisbetű-érzéketlenül. Így egy átnevezés
("Ellenőrzésre vár") nem töri el némán a pontozást.

A **vágási pont** ezzel szemben a timesheetekből **számítva** jön, nem
másolva: egy javított időmérés így magától javítja a pontot is, nem kell
szinkronban tartani két igazságot. A mérés a **kezdés** dátuma szerint tartozik
egy hónapba, hogy az éjfélen átnyúló munka ne hasadjon ketté.

## Az arányosítás - ettől igazságos

Aki 12 napot dolgozik (szabadság, betegség), az nyers pontban esélytelen
azzal szemben, aki 22-t - pedig lehet, hogy naponta többet teljesített. Ezért
mindenkit úgy arányosítunk, mintha **20 napja** lett volna:

> **pont = nyers pont × (20 / munkanap)**

A munkanapot emberenként és hónaponként lehet megadni (`vago_jatek_napok`), és
**menet közben is átírható**: ha valaki megbetegszik vagy plusz napot vállal, a
szám javítható, és az állás azonnal újraszámolódik. A pontokhoz nem kell
hozzányúlni - azok a nyers teljesítményt őrzik, az arányosítás mindig a friss
munkanapszámmal fut le.

Akinek nincs beállítva, az 20 nappal számol, tehát a nyers pontja marad - a
beállítás elmaradása senkit nem hoz hátrányba. A 0 munkanap sem száll el
(nullával osztás): ott marad a nyers pont.

## Felület

| Rész | Mi |
|---|---|
| Nyeremény-kártya | A hónap nyereménye **fotóval**, legfelül. Ha nincs kihirdetve, figyelmeztet - a verseny akkor működik, ha a hónap elején tudják, miért mennek. |
| Versenypálya | Sávos futam: a sáv hossza a pont az **éllovashoz** mérve (nem fix maximumhoz), így a hónap elején is van mit nézni. Kupa az elsőnek. |
| Pontok bontása | Miből jött ki a szám, + a munkanap helyben szerkeszthető. |
| Korábbi hónapok | Ki nyert (kupával), ki hányadik lett, hány ponttal, mi volt a nyeremény (bélyegképpel). |

### A nyeremény fotója

Egy kép többet mond, mint a "20 000 Ft utalvány". Feltöltés a nyeremény
szerkesztő ablakában, a gépről vagy telefonról - JPG, PNG, WEBP, GIF, HEIC,
AVIF, max. 10 MB. A kép **azonnal felmegy**, nem a "Mentés" gombra vár: két
külön művelet két külön végponton (a szöveg JSON-nal, a fájl multipart-tal), és
így a feltöltés eredménye rögtön látszik.

Egy hónapnak **egy képe** van - az újabb feltöltés lecseréli az előzőt, és a
régi objektumot eldobjuk a tárhelyről. A tárolási kulcs **egyedi** (uuid), nem
a hónapból képzett: azonos kulcson a csere ugyanarra az URL-re írna, és a
böngésző (meg a CDN) a gyorsítótárból továbbra is a régi képet mutatná.

A típus-ellenőrzés szűk, zárt listával megy: a kép publikus URL-ről jelenik
meg, tehát nem lehet bármilyen fájlt "képként" feltölteni és a tárhelyen
keresztül kiszolgálni.

**Holtversenynél azonos hely**, és a következő hely ugyanannyival ugrik
(1., 1., 3.) - egy versenyben a holtversenyt nem lehet önkényesen, mondjuk
névsor szerint eldönteni. Aki 0 ponton áll, nem kap helyezést: a "17. helyezett
0 ponttal" nem eredmény, csak zaj.

Az állás **mindenkinek látszik**, akit beengedünk (a verseny lényege, hogy
lássák egymást); a nyeremény kihirdetése és a munkanapok állítása
**szerkesztési jog**.
