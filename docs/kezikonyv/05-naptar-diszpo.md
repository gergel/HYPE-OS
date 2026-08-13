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

`services/dispo.py`. A korábbi Notion-oldali megoldás checkbox + 60 másodperces
pollozás volt; itt **explicit gombok** vannak: az "Előzetes diszpó" és a "Diszpó
küldése" gomb megnyomása maga a trigger, nincs állapotgép és nincs pollozás.

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
