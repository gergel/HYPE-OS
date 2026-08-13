# 08 - Utómunka

Oldal: `/utomunka`. Route: `routes/postproduction.py`,
`routes/vagoi_visszajelzesek.py`. Logika: `services/deliverable_actions.py`.

## Három entitás

| Entitás | Mi | API prefix |
|---|---|---|
| **Deliverable** | A vágandó/leszállítandó anyag | `/api/v1/deliverables` |
| **Timesheet** | Ledolgozott idő | `/api/v1/timesheets` |
| **Feedback** | Visszajelzés az anyagról | `/api/v1/feedback` |

Modellek: `models/deliverable.py`, `models/timesheet.py`, `models/feedback.py`,
`models/deliverable_comment.py`, `models/deliverable_status.py`.

## Deliverable-ök

A tábla/board állapotai és elrendezése konfigurálható
(`DeliverableStatusConfig`, `DeliverableBoardConfig`) - nem kódba égetett
státuszlista.

Amit érdemes tudni:

- **Projektkód nélkül nem jön létre vágás.** Az utómunka a legkönnyebben
  elszakadó láncszem: ha nincs kódja, sehol nem látszik, melyik munkához
  tartozik, és a projektkód adatlapján sem jelenik meg a költsége. Az űrlapon
  ezért kötelező mező. **Projekthez felvezetve nem kell beírni**: a vágás a
  projekt kódját örökli (`routes/postproduction._vagas_projektkodja`), és a
  szöveg alapján rögtön a Project Code-hoz is kötődik. A kódot utólag sem lehet
  kiüríteni, csak másikra cserélni. A szabály:
  `services/projektkod_kotes.py`, lásd
  [03-projektek-ugyfelek.md](03-projektek-ugyfelek.md#a-projektkód-kötése-mi-tartozik-egy-kód-alá).
- **Kiosztás értesítést vált ki**: ha egy PATCH beállítja az "Assigned To"-t,
  a rendszer értesítést küld az érintettnek (`services/notifications.py`).
- **Anyag-szintű hozzáférés**: egy vágó korlátozható arra, hogy csak bizonyos
  deliverable-öket lásson (`lathato_anyagok()`,
  `ellenorizd_anyag_hozzaferest()`, `PageAccessConfig.lathato_deliverable_idk`).
  Ez a jogosultsági rendszer legfinomabb szintje - lásd
  [02-auth-jogosultsag.md](02-auth-jogosultsag.md).
- **Időmérő**: a deliverable-höz tartozik indítható/leállítható timer
  (`TimerState`), ami timesheet-sorokat termel.
- Kommentek, kiosztható emberek, kontaktok, vinyó-opciók: mind a
  `deliverable_actions` végpontcsoport alatt.

Frontend: `components/deliverable/`, `UtomunkaIdoHavonta.tsx`,
`VagoInlineFields.tsx`, `lib/visszajelzesAllapot.ts`.

## Vágói visszajelzések

Oldal: `/utomunka/visszajelzesek` (jogosultsága az `/utomunka` oldalé).
API: `/api/v1/vagoi-visszajelzesek`.

Ez a gyűjtőhely: minden visszajelzés egy sorban, azzal együtt, amitől
használható lesz - ki írta és mikor, melyik anyagról, hol a kész anyag (a link a
visszajelzés pillanatában), melyik forgatáshoz tartozik, és kik voltak ott azon a
forgatáson.

Az utolsó pont adja az értelmét: **a vágó észrevétele annak szól, aki forgatta.**
Ezért lehet innen egy gombbal kiküldeni a forgatás **diszpó-levelére válaszként** -
abba a szálba, amit a stáb már ismer (`services/dispo.py`,
`services/google_email.py`).

A kiküldött levél tartalma szándékosan szűk: **csak a szöveges megjegyzés és a
kész anyag linkje**. A pontszámok belső mérőszámok, nem a stábnak szólnak - egy
"technikai helyesség: 6/10" a levélben számonkérésnek olvasódna, a szöveges rész
viszont pont az, amiből tanulni lehet. Ha ezen változtatnál, ez tudatos döntés
volt, nem hiányosság.

## Kapcsolódás máshova

- A forgatás utáni **kérdőív** válaszai nem itt, hanem az utókövetésben látszanak:
  [05-naptar-diszpo.md](05-naptar-diszpo.md), [06-papirozas.md](06-papirozas.md).
- A kész anyag ügyfélnek való átadása a **Média Portálon** megy:
  [09-media-portal.md](09-media-portal.md).
