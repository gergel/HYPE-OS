# Lara – haladás (élő folytatási pont)

Ez a fájl a kontextusváltás-biztos folytatási pont: mi készült el (és
tesztelt-e), mi van hátra, mik a blokkolók. NEM az implementáció
helyettesítője. A fázisok a master prompt 17. pontjának sorrendjét követik.

## Állapot-jelölés
- ✅ kész és ellenőrzött (migráció lefutott / tsc+build zöld / teszt zöld)
- 🟡 részben kész / bekötve, de nem teljes
- ⛔ hátravan
- 🔧 külső beállítás szükséges (kulcs/jogosultság)

## Fázisok

### A. Felmérés + architektúra ✅
- Repófelmérés kész (stack, worker=Celery+beat, RBAC, nincs multitenancy,
  pgvector NINCS telepítve → opcionális + fallback).
- `docs/admin-agent/architecture.md` kész.
- Megőrzendő invariánsok rögzítve (projektkód↔projekt, pénzügyi szolgáltatáson
  át, kesz-alapú kimutatás).

### B. Additív migrációk + magmodellek + policy engine + jogosultságok ✅
- Táblák (migráció `g0a7x18u5v49_admin_agent_core`, lefutott): `aa_source_events`,
  `aa_tasks`, `aa_agent_runs`, `aa_action_traces`, `aa_corrections`,
  `aa_action_proposals`, `aa_approvals`, `aa_action_executions`,
  `aa_playbook_rules`, `aa_trust_policies`, `aa_settings` (singleton
  kill-switch/flag). Seed: settings f|f|f + 6 trust_policy L0-n.
- Enumok (állapotgép, R0–R3 kockázat, L0–L4 trust): `app/admin_agent/enums.py`.
- Policy engine (szerveroldali kockázat-besorolás + végrehajtási döntés +
  kill-switch): `app/admin_agent/policy.py` + `settings_service.py`. 8 egységteszt
  zöld (`tests/test_admin_agent_policy.py`).
- L0-biztos API (nincs üzleti/külső mellékhatás): `routes/admin_agent.py` —
  overview, tasks (GET/POST), task részlet + PATCH (optimista zárolás 409,
  csak mellékhatás-mentes állapotátmenetek), approvals, settings GET/PATCH,
  pause/resume (kill-switch). Éles smoke-teszttel ellenőrizve (create→200,
  PATCH→row_version++, stale→409, nem-kézi állapot→400, pause/resume OK).
- Jogosultság: `/admin-agent` oldal, minden szerepkör-kapu nyitva
  (`_MINDEN_SZEREPKOR`), a valódi szűrést a page_permissions adja; a magas
  kockázatú kapcsolók (modul/mellékhatás/kill) a `delete` művelethez kötöttek.
  A finomabb pénzügyi/jogi/trust permissionök a G fázisban jönnek.
- **Hátra (következő migráció):** `memory_chunk`, `eval_case`, `eval_run`,
  `learning_run`, `agent_release`, outbox — a memória/eval fázissal (F).

### C. Munkasor + taskrészlet + jóváhagyási felület + meglévő oldalak 🟡
- Felület (Next.js, sötét design tokenek), 4 valós, bekötött aloldal a
  `/admin-agent` alatt: **Áttekintés** (biztonsági alapállás-csík, statisztikák,
  állapot-bontás, „Még nincs elég adat" a mért mutatókra), **Munkasor**
  (szűrés, feladat-létrehozás, felelős-kiosztás, mellékhatás-mentes
  állapotváltás — mind a valós API-n át), **Jóváhagyások** (üres állapot a
  végrehajtó réteg megérkezéséig), **Beállítások** (modul/mellékhatás
  kapcsolók + vészleállítás, a `delete` joghoz kötve). Navigáció bekötve
  (`lib/nav.ts`, `NavList.tsx`). tsc+eslint+`next build` zöld.
- **Taskrészlet / idővonal KÉSZ:** `/admin-agent/munkasor/[id]` — a feladat
  adatai, a művelet-javaslatok (payload + ellenőrzések + payload-ujjlenyomat,
  „Árnyék (L0): nem hajtódott végre" jelzéssel) és az idővonal (ki mit tett,
  milyen policy-döntéssel). Backend: `GET /admin-agent/tasks/{id}/timeline`
  (csak olvasás). A munkasor sorai ide linkelnek.
- **Hátra:** a jóváhagyás jóváhagyás/elvetés gombjai (a végrehajtó réteggel,
  D/E), és a meglévő oldalakba (Pénzügyek beérkező számlák) való „Lara
  árnyék-elemzés" gomb. Tudástár/Tanulás/Napló aloldalak: F/G fázis.
### D. Számlafolyamat végig L0/L1-ben, valós szolgáltatásokra kötve 🟡
- **L0 árnyék-elemzés kész** (`app/admin_agent/pipeline_szamla.py`): egy beérkező
  számlából (BejovoSzamla) forrásesemény → feladat → Lara-futás → nyomvonal →
  művelet-javaslat, a policy engine döntésével. A javaslat payloadja pontosan a
  meglévő `services/szamla_erkeztetes.jovahagy` `dontes`-alakját írja le (az
  Lara a MEGLÉVŐ pénzügyi szolgáltatáson át dolgozna), de L0-ban VÉGRE NEM
  HAJTJUK. Determinista, szerver-oldali ellenőrzések (hiányzó cél/összeg/díjbekérő)
  → hiányos javaslat NEEDS_INFO. Kockázat szerver-oldalon R2 (belső pénzügyi
  rekord írása). Idempotens (forrásesemény: forras+azonosító+állapot; feladat:
  egy bejovó = egy feladat a forras_referenciak alapján).
- API: `POST /admin-agent/tasks/from-bejovo/{id}` (create jog, L0-biztos).
- Tesztek: `tests/test_admin_agent_szamla_pipeline.py` (Postgres-integráció,
  self-skip DB nélkül) — bizonyítja: 0 Expense-változás, idempotencia,
  BLOCKED (árnyék), hiányos→NEEDS_INFO. Éles smoke + API-teszt OK.
- **L1 végrehajtó réteg KÉSZ** (`app/admin_agent/executor.py`): a teljes
  guard-lánc (master prompt 8.) — jóváhagyás-hash kötés, javaslat-frissesség,
  regisztrált eszköz (`TOOL_REGISTRY`, szűk hatókör: nincs általános SQL/shell/
  URL), a policy engine ÚJRA a végrehajtás pillanatában, idempotens lefoglalás
  (javaslatonként egy `aa_action_executions` az egyedi kulccsal), fencing token,
  majd a valós eszközhívás. A számla eszköz a MEGLÉVŐ `szamla_erkeztetes.jovahagy`-ot
  hívja. Éles smoke: L1 + mellékhatás BE → jóváhagyás → 1 valós Expense; ismételt
  végrehajtás → ugyanaz a rekord, továbbra is 1 Expense (idempotens, 7. forgatókönyv
  valós mellékhatással); utána a biztonságos alapállás visszaállítva.
- **Jóváhagyás + feladat-műveletek API:** `POST /approvals/{id}/approve`
  (payload-hash kötés, 409 eltérésnél; a végrehajtást guardolt úton kísérli meg),
  `/approvals/{id}/reject`, `/tasks/{id}/analyze` (újraelemzés), `/corrections`
  (emberi javítás → `aa_corrections`, `uj` állapot, NEM aktivál szabályt),
  `/assign`, `/cancel`, `GET /executions/{id}`.
- Tesztek: `tests/test_admin_agent_executor.py` (5 elfogadási teszt: alapállás
  blokkol + 0 Expense, vészleállítás, eltérő hash, consumed jóváhagyás,
  idempotencia). 15 Lara teszt zöld; HTTP-smoke minden új végponton OK.
- **Jóváhagyások felület bekötve:** a Jóváhagyások aloldal a valós listát
  mutatja (javaslat payload + kockázat), „Jóváhagyás és végrehajtás" / „Elutasítás"
  gombokkal; a jóváhagyás a payload-hash-hez kötött (409 eltérésnél), a
  visszajelzés jelzi, ha a végrehajtás blokkolt (alapállás). HTTP-teszt:
  lista→hash, rossz hash→409, helyes→végrehajtva (valós Expense), újra→409.
- **Hátra:** háttér-ingesztálás (Celery beat, az érkeztető inboxából),
  `execution_unknown` egyeztetés (reconcile) a külső időtúllépésre, LLM-alapú
  elemzés (jelenleg determinista leképezés a meglévő javaslatból), a finance-oldali
  „árnyék-elemzés" gomb, és a detail-nézet művelet-gombjai (analyze/cancel/correction).
### E. E-mail, TIG, szerződés, utalás-előkészítés (korlátokkal) 🟡
- **E-mail-válasz KÉSZ (L0/L1):** `email.valasz_kuldes` eszköz (R2, mellékhatás)
  a MEGLÉVŐ `google_email.send_message`-re kötve. Determinista, szerver-oldali
  validálás: automata/nem-válaszolható címzett (no-reply, mailer-daemon, bounce,
  postmaster…) TILTOTT → nincs körkörös levelezési hurok (10./21.); hiányzó
  címzett/tárgy/szöveg → nem küldhető. Gmail nélkül a küldés beszédes „Beállítás
  szükséges" hibát ad (NEM hamis siker).
- **Általános javaslatkészítő** (`proposals.keszit_javaslat`) + `POST
  /tasks/{id}/propose {eszkoz, payload}`: bármely regisztrált eszközre javaslat,
  a policy engine-en át, jóváhagyással; a végrehajtás az `executor` guard-láncán.
- **Eszköztár** (`GET /tools`): deklarált kockázat/feladattípus/mellékhatás.
  BANKI utalást INDÍTÓ/aláíró/végrehajtó eszköz SZÁNDÉKOSAN NINCS regisztrálva
  (R3, tiltott). Az utalás-ELŐKÉSZÍTÉS export-tervezet a javaslat payloadjában,
  külső hatás nélkül.
- **Integráció-állapot** (`integrations.py`): valós config-ellenőrzés (Gmail,
  modell, dokumentumtár) — az Áttekintésen és a Beállításokban „Kész / Beállítás
  szükséges" (a titkok értéke sosem kerül a böngészőbe).
- Tesztek: `tests/test_admin_agent_email.py` (validáció/automata-hurok, nincs
  banki eszköz, „Beállítás szükséges" DRAFT+NEEDS_INFO). 21 Lara teszt zöld.
- **Hátra:** TIG/szerződés-előkészítés a meglévő papír-generátorra (a draft a
  javaslat, ember véglegesít a meglévő felületen — L1); „Admin-feladat
  létrehozása" gomb a meglévő e-mail-nézetből (nincs általános e-mail-inbox UI a
  repóban → dokumentálva); LLM-alapú fogalmazás.

### F. Memória, szabálykezelés, háttér-tanuló, eval, verziózott kiadások ✅
- 2. migráció (`h1b8y29v6w50`, additív, reverzibilis): memory_chunks, eval_cases,
  eval_runs, learning_runs, agent_releases, outbox.
- `learning.distill` (küszöb + idempotens + jelölt-only), `memory.retrieve`
  (aktív/érvényes/jóváhagyott; pgvector opcionális → fallback), `evals`
  (kód-invariáns safety-eval, 7 beépített eset). API: rules/learning-runs/
  evaluations/releases/audit. Celery beat: éjszakai distill + heti eval.
- Tesztek: `test_admin_agent_learning.py`. Lásd `learning-and-evals.md`.

### G. Trust-szintek, L2 (szűk), dashboard, értesítések, üzemeltetés ✅
- Bizalmi szint kezelés (GET/PATCH `/trust-policies`, trust_change=delete).
  L2 auto-képesség a policy engine-ben (R1 L2+, R2 L3+ allowlisttel).
- A hét aloldal teljes: Tudástár, Tanulás és minőség, Napló + a Beállításokban
  bizalmi szint szerkesztő és forráskapcsolat-állapot. Áttekintésen
  forráskapcsolati állapot.
- Megjegyzés: a külön értesítés-becsatlakozás (jóváhagyás/elakadás/határidő a
  meglévő notifications rendszerbe) még hátra — a napló + overview jelzi az
  állapotot.

### H. Teljes tesztelés, migrációpróba, build, biztonsági ellenőrzés, docs 🟡
- 25 Lara teszt zöld (`pytest tests/test_admin_agent_*.py`); tsc + eslint
  + `next build` zöld; migráció le/fel próbálva.
- Dokumentáció kész: `architecture.md`, `operations.md`, `permissions-and-risk.md`,
  `learning-and-evals.md`, `acceptance-checklist.md`, `user-guide.md`, `progress.md`,
  `.env.example` Lara szekció.
- Hátra: valós modell (Gemini) elemzés explicit konfiggal + elkülönített teszt,
  worker crash-recovery + külső-timeout reconcile end-to-end, frontend E2E
  (Playwright), teljes backend regressziós suite futtatása.

### I. Teljes kattinthatóság + projektkód/utókövetés megfigyelés ✅
- **Kattintható belépési pontok:** Beérkező számlák sorain „Lara" gomb
  (árnyék-elemzés → feladat); a feladat oldalán „Javítás rögzítése" űrlap +
  „Újraelemzés" / „Megszakítás"; a Tanulás oldalon Megfigyelés / Kezdeti
  visszatekintés / Háttér-tanuló / Értékelés gombok; a Tudástárban példák
  jóváhagyása/elvetése és szabályok élesítése/visszavonása.
- **Projektkód + Utókövetés bekötés:** „Lara teendők" blokk a
  projektkód-adatlapon és az utókövetés projektkód-oldalán (feladatlista +
  új szerződés/TIG/számla/utalás feladat a projektkódhoz kötve; jog nélkül rejtve).
- **Megfigyelő** (`app/admin_agent/observer.py`): a szerződések, TIG-ek, belsős
  TIG-ek és kiadások változásait olvassa (`updated_at`), NEM akaszkodik a mentési
  útvonalra. Idempotens forrásesemény + emberi nyomvonal; a lezárt emberi
  munkából példa-JELÖLT (ervenyes=False). Engedélyhez kötött (`engedett_forrasok.
  megfigyeles`, Beállítások kapcsoló); ütemezve félóránként; a kézi indítás
  jogosult döntés. Első futás korlátozott visszatekintéssel.
- API: `POST /observations`, `GET /memory`, `PATCH /memory/{id}` (jóváhagyás =
  delete jog; elvetett nem hagyható jóvá); overview `tanulas` blokk.
- Az éjszakai tanuló mostantól akkor is fut, ha a tanulási forrás be van
  kapcsolva (L0-ban is tanul, mellékhatás nélkül).
- Tesztek: `test_admin_agent_observer.py` (4). Backend: 92 zöld. Élő E2E: a teljes
  kör (kapcsoló → megfigyelés → példa jóváhagyás → projektkód-feladat → 2 javítás →
  szabály-jelölt → eval 7/7 → élesítés) valós adaton lefutott, utána visszaállítva.

### J. Modell-alapú elemzés és tervezetek (Gemini) + Tudástár-javítás ✅ (valós Gemini-hívás: ⚠️ nem ellenőrzött)
- **Tudástár-javítás:** a megfigyelt példák tévesen „projektkód nélkül" címkét
  kaptak — a TIG/szerződés a projekten át (`project_id → projects.project_code_id`)
  kötődik a projektkódhoz. Új szöveg pl.: „HYPE26-0001 · Projekt — TIG: Név,
  állapot: Kiküldve, nettó 135 000 Ft." A meglévő jelöltek szövege a „Kezdeti
  visszatekintés (90 nap)" újrafuttatásakor frissül (jóváhagyott példa új
  rekord-verziónál újra jelölt lesz).
- **Modelladapter** (`app/admin_agent/llm.py`): Gemini (`google-genai`),
  strukturált JSON-séma, egy javító újrapróba, utána fail-closed; 429/timeout →
  kontrollált hiba; kulcs nélkül „beállítás szükséges" (a determinista út fut).
  A bemenet (e-mail, PDF, példák) ADAT, nem utasítás — a rendszerprompt rögzíti.
- **Számla-átnézés a megtanult tudással** (`pipeline_szamla._modell_atnezes`):
  a modell üres célt/projektkódot CSAK létező értékkel tölthet; ha eltér az
  érkeztetőtől → konfliktus, emberhez (needs_info, bizonytalanság 1.0); összeget
  NEM írhat át; kitalált projektkód elutasítva. Új elemzés leváltja a korábbi
  javaslatot (a függő jóváhagyás lejár).
- **TIG/szerződés tervezet** (`app/admin_agent/tervezo.py`): a projektkód
  projektjein a MEGLÉVŐ `get_pending_for_project` adja a teendőket; előtöltés
  forrással (mentett piszkozat / eseti szerződés / partnertörzs / projekt dátumai /
  tételek összege); a modell csak a hiányzó mezőt egészíti ki; összeg csak IGAZOLT
  forrásból (±0,5 Ft), különben elutasítva + figyelmeztetés. Új R1 eszközök:
  `tig.piszkozat_mentes`, `szerzodes.piszkozat_mentes` — a meglévő piszkozat-
  mentésen át, egy SAVEPOINT-ban, „Készítés alatt" állapotba; PDF és kiküldés
  NINCS (emberi lépés marad).
- **E-mail tervezet:** címzett CSAK igazolt címből (megrendelő kontaktjai, függő
  felek); ismeretlen cím elutasítva; címzett nélkül a javaslat hiányos.
- **Szerkesztés = tanulás:** `POST /tasks/{id}/proposals/{pid}/edit` — a
  különbség mezőszintű javításként rögzül, új javaslat készül (a régi leváltva).
- **Tudástár tömeges kijelölés:** típusszűrő + pipálás + „Kijelöltek
  jóváhagyása/elvetése" (`POST /memory/bulk`, max 500; nincs „mindent jóváhagy").
- **Felület:** a feladat oldalán „Tervezet készítése (Lara)", „Lara
  értékelése" doboz (összefoglaló, bizonytalanság, konfliktus, hiányok,
  figyelmeztetések, felhasznált tudás), tételtábla forrásokkal, „Javaslat
  szerkesztése".
- **Tesztek:** `test_admin_agent_llm.py` (9), `test_admin_agent_tervezo.py` (12,
  köztük valós piszkozat-mentés dev-adaton, rollback — ez egy valós hibát fogott:
  a szerződés állapotmezője `szerzodes_allapota`). Teljes backend: 114 zöld,
  1 kihagyott; tsc + eslint + `next build` zöld. Élő API-kör (rollback-ben):
  tervezet → szerkesztés → L1 jóváhagyás → 5 szerződés-piszkozat „Készítés
  alatt"; alapállásban (modul KI / L0) blokkolt, jóváhagyás sem keletkezik.
- **Nem ellenőrzött:** a valós Gemini-hívás (a sandboxban nincs `GEMINI_API_KEY`) —
  hamis adapterrel tesztelve; élesben a kulcs beállítása után ellenőrizendő.

### K. Tanulási korszak: csak 2026. szeptember 1. óta ✅
- Ok: a cég szept. 1. óta a HYPE OS felületén dolgozik, előtte Notionben — a
  régi rekordok (pl. a Notion „Kiadások" tábla projektkód nélküli sorai) félre-
  vezető mintát adnának.
- Migráció `i2c9z30w7x51`: `aa_memory_chunks.forras_keletkezes`, `regi_korszak`.
- Megfigyelő: példa-jelölt CSAK a tanulás kezdete óta keletkezett, nem Notionből
  importált (`notion_import_map`) rekordból; a visszatekintés sem megy a
  kezdőnap elé. `korszak_rendezes`: a régi korszak el nem bírált jelöltjei
  `minosites="felreteve"` (nem törlődnek, egyenként jóváhagyhatók; ha a
  kezdőnap korábbra kerül, visszajönnek); a jóváhagyott régi példa megmarad.
- Visszakeresés: az új korszak példái előbb, a régi utána, „[RÉGI…] kisebb
  súllyal" jelöléssel a modell felé; számlánál ha a projektkódot csak régi eset
  támasztja alá, bizonytalanság ≥ 0,4.
- Beállítás: `PATCH /settings {tanulas_kezdete}` (jövőbeli dátum → 400; mentéskor
  újrabesorolás), Beállítások → „Tanulás kezdete"; `POST /observations?kezdettol=true`;
  `GET /memory` alapból a félretetteket kihagyja (`felretett=true`-val kérhetők).
- Felület: Tudástár „Félretett régi jelöltek" szekció, „régi (kisebb súllyal)"
  címke; Tanulás: „Visszatekintés a tanulás kezdetéig"; Áttekintés: kezdőnap +
  félretett darabszám.
- Tesztek: +5 (`test_admin_agent_observer.py`): régi rekordból nincs jelölt,
  Notion-import régi, félretétel + visszahozás, régi példa hátrébb és jelölve,
  jövőbeli kezdőnap elutasítva. Teljes backend: 119 zöld, 1 kihagyott; tsc +
  eslint + `next build` zöld; migráció le/fel próbálva.

### L. Visszajátszás + találati arány + kézi szabály ✅
- `app/admin_agent/visszajatszas.py`: a tanulás kezdete óta rögzített számláknál
  az érkeztető eredeti javaslata (`BejovoSzamla.javaslat`) vs a végső emberi döntés
  (cél, célrekord, projektkód; bontásnál a sorok kódjai) → egyezik / eltér / nem
  javasolt. Számlánként konkrét példa-JELÖLT („a HELYES besorolás …, az érkeztető
  tévesen …"); partnerenként ≥2 egybehangzó (≥80%) döntésből szabály-JELÖLT
  (`feltetelek.partner/cel_tipus/projektkod_idk`, pending). Idempotens
  (forrásesemény `visszajatszas`), üzleti rekord nem változik.
- Találati arány (`GET /replays/summary`): érkeztető és — ha a döntés előtt
  elemezte — Lara egyezése, összesen és hetente. `POST /replays` futtat.
- Az érkeztető mostantól pillanatképet tesz a javaslatba a javasolt célról
  (`javaslat.javasolt_cel`, additív kulcs) — a pontos utólagos összevetéshez.
- Partner-egyezés normalizált névvel (`memory.partner_kulcs`: ékezet, kisbetű,
  cégforma nélkül); a partnerhez kötött szabály csak annál a partnernél jön elő.
- ÉLESÍTETT partner-szabály a számla-elemzésben MODELL NÉLKÜL is alkalmazódik:
  csak üres célt/kódot tölt (érkeztetőt nem ír felül, eltérésnél figyelmeztet),
  bizonytalanság 0,3.
- Kézi szabály (`POST /rules` bővítve: partner, cel_tipus, projektkod, validálás;
  vázlat → értékelés → élesítés). Felület: Tudástár „+ Új szabály kézzel",
  Tanulás „Visszajátszás és találati arány" kártya, eval-magyarázat.
- Tesztek: `test_admin_agent_visszajatszas.py` (5). Teljes backend: 124 zöld,
  1 kihagyott; tsc + eslint + `next build` zöld. Dev-adaton nincs szept. 1. utáni
  rögzített számla — a valós számok élesben látszanak.

### M. Tudásháló (a tudás kapcsolati „glóriája") ✅
- Backend `app/admin_agent/tudashalo.py` + `GET /knowledge-graph`: pontok
  (mag, 5 témakör, partner, projektkód, számla-cél, szabály) és kapcsolatok
  KIZÁRÓLAG valós tudásból (megfigyelt munka, visszajátszás, szabályok,
  javítások). Bizonyosság = 1 − e^(−súly/2); súlyok: jóváhagyott példa 1,
  jelölt 0,25, élesített szabály 3, szabály-jelölt 0,5, javítás 0,6, régi korszak
  ×0,4; elvetett/félretett nem számít. Minden kapcsolatnak első megjelenése van.
  Méretkorlát: 220 partner, 140 projektkód (a legerősebbek).
- Felület `/admin-agent/tudashalo` (Tudásháló fül + oldalmenü): canvas-alapú,
  J.A.R.V.I.S.-szerű HUD — forgó gyűrűk, skála, fényimpulzusok. Szín = témakör
  (validált sötét paletta, all-pairs CVD ΔE 9,6, normál ΔE 17,0), forma = fajta,
  pontméret = kapcsolatsúly, vonalvastagság/fény = bizonyosság, szaggatott =
  csak jelölt. Témaszektorok a tartalom arányában. „Növekedés lejátszása" +
  idősáv (a HUD-számok az adott napig), hover-tooltip, kattintásra részletpanel
  (kapcsolatok bizonyosság szerint, jóváhagyott tudás), témaszűrők, táblázat-
  nézet, mobil elrendezés, prefers-reduced-motion.
- Tesztek: `test_admin_agent_tudashalo.py` (2). Teljes backend: 126 zöld,
  1 kihagyott; tsc + eslint + `next build` zöld. Vizuális ellenőrzés Playwright-
  képernyőképekkel (ideiglenes, jelölt demóadaton — utána törölve).

### N. Átnevezés Larára + önellenőrző, folyamatos tanulás (kérdésekkel) ✅
- Név: **Lara** (korábban Admin-Ágens / HYRON) minden felhasználói szövegben,
  a docsban és a modell rendszerpromptjában; szabály: `CLAUDE.md`. Technikai
  azonosítók (útvonal, API, csomag, táblák) változatlanok.
- `app/admin_agent/onellenorzes.py`: Lara a tanulás kezdete óta rögzített
  számlákra „vakon" (az adott számla saját tanulsága nélkül) megmondja, mit
  javasolt volna a JELENLEGI tudásával (`Tudas`: élesített partner-szabály →
  ≥2 egybehangzó jóváhagyott eset / megválaszolt kérdés → különben az érkeztető
  javaslata), és összeveti a valósággal. Eltérésnél / tudáshiánynál KÉRDEZ
  (új tábla `aa_questions`, migráció `j3d0a41x8y52`; partnerenként és végső
  céltípusonként egy kérdés, max. 25 nyitott, ismételt futásnál bővül, nem duplikál).
- Válaszok → tudás: „mindig így" = partner-szabály (élesítési joggal + sikeres
  eval mellett azonnal aktív, különben jelölt); „magyarázat" = jóváhagyott tudás
  a magyarázattal (a `Tudas` esetként is számolja); „egyszeri kivétel" =
  feljegyzés általánosítás nélkül; „hibás rögzítés" = nem tanít; „nem releváns".
- Az éles számla-elemzés ugyanazt a `Tudas`-t használja (szabály 0,3,
  esetekből 0,45 bizonytalanság; csak üres mezőt tölt, érkeztetőt nem ír felül).
- Futásonként találati arány (`aa_learning_runs`, trigger `onellenorzes:*`):
  ebből látszik a tanulás. Ütemezés: Celery beat kétóránként (:15), bekapcsolt
  „Tanulás és megfigyelés" mellett, előtte visszajátszással.
- API: `POST /self-check`, `GET /self-check/runs`, `GET /questions`,
  `POST /questions/{id}/answer`; overview `nyitott_kerdesek`; a háttér-tanuló
  listája az önellenőrző futásokat nem mutatja.
- Felület: „Kérdések" fül + „Lara kérdései" menü (kérdéskártya: Lara javaslata
  vs. a rögzítés, válaszlehetőségek), Tanulás oldalon „Lara önellenőrzése"
  kártya (találati arány, futások), Áttekintésen nyitott kérdések száma.
- Tesztek: `test_admin_agent_onellenorzes.py` (6) — a teljes kör: nem érti →
  kérdez → „mindig így" → a következő futáson eltalálja; magyarázat → éles
  elemzés is használja; hibás rögzítés nem tanít; vak jóslat nem „puskáz".
  Teljes backend: 132 zöld, 1 kihagyott; tsc + eslint + `next build` zöld.
  Élő próba (jelölt demóadaton, utána törölve): 7 számla, 3 kérdés; egy
  „mindig így" válasz után a találati arány 29% → 57%.
- Korlát: az önellenőrzés most a számlák besorolására fut (ez a fő tanulható
  döntés); a TIG/szerződés-mezőkre kiterjeszthető. → Kiterjesztve: lásd O.

### O. Önellenőrzés a papírozáson: eseti szerződések, TIG-ek (Utókövetés) ✅
- `app/admin_agent/onellenorzes_papir.py` (új): Lara a tanulás kezdete óta
  LEZÁRT eseti (alvállalkozói, nem keret-) szerződések (`Kiküldve` /
  `Kihagyva` / `Van már szerződés`) és TIG-ek (`Kiküldve` / `Kihagyva`)
  döntéseire is „vakon" jósol (a rekord saját tanulsága nélkül; Notion-import
  és régi korszak kizárva). Vizsgált döntések partnerenként: **kell-e a papír**
  (kihagyás + indok), **nettó összeg** (eltér-e a lefedett tételek összegétől),
  **+ÁFA**, **megbízás tárgya** (normalizált szöveg-hasonlóság), TIG-nél
  **kell-e számla**.
- Tudás (`PapirTudas`): élesített papír-szabály (`hatokor` = szerzodes/tig,
  `feltetelek.mezo`/`ertek`/`partner`) → ≥2 egybehangzó (≥80%) jóváhagyott
  megfigyelt eset / magyarázat → alapértelmezés (papír kell, összeg = tételek
  összege, számla kell; ÁFA-ra és tárgyra tudás nélkül NEM jósol).
- Kérdések: `aa_questions.tipus = "papir"`, kulcs
  `papir:{terulet}:{dimenzio}:{partner}` — partnerenként és döntésenként egy
  kérdés, új esetek hozzáfűzve. Válasz: „mindig így" → partnerre szabott
  papír-szabály (élesítési jog + sikeres eval nélkül jelölt); magyarázat /
  kivétel → tudás-darab; hibás → nem tanít. Számla-kérdések változatlanok.
- Futás-összegzés: `teruletek` bontás (szamla / szerzodes / tig) találati
  aránnyal; a „szabalyok" a papír-szabályokat is számolja.
- Tervező (`tervezo._papir_tudas_alkalmazasa`): TIG/szerződés-tervezetnél a
  HIÁNYZÓ megbízási tárgyat és ÁFA-jelzőt Lara tudásából tölti („Lara tudása
  (…)" forrással); a szokásos kihagyást, eltérő összeget, számla nélküli TIG-et
  figyelmeztetésként jelzi. Összeget NEM ír, meglévő mezőt nem ír felül.
- Felület: Kérdések — terület-szűrő (Mind / Számlák / Szerződések / TIG-ek),
  papír-kérdésnél terület + döntés címke, esettábla (projektkód · projekt,
  nettó, lezárva, Lara ezt várta, ahogy döntöttetek). Tanulás — területenkénti
  találati arány kártyák.
- Tesztek: `test_admin_agent_onellenorzes_papir.py` (4) — kihagyott TIG →
  kérdés → „mindig így" → a következő futáson eltalálja; összeg-eltérés →
  kérdés → jelölt szabály; hibás válasz nem tanít; vak jóslat + tervező
  előtöltés. Teljes backend: 136 zöld, 1 kihagyott; tsc + eslint + `next build`
  zöld. Élő próba (jelölt demóadaton, utána minden táblából törölve): 4 TIG,
  3 papír-kérdés; egy „mindig így" válasz után a TIG-találati arány 56% → 78%.
- Nem ellenőrzött: valós (nem demó) szerződés-adaton, mert a fejlesztői DB-ben
  nincs szeptember 1. utáni lezárt eseti szerződés.

### P. Utalás nélkül + teljes vészleállítás + tanulás a szamla@ levelezésből ✅ (valós Gmail-olvasás: ⚠️ nem ellenőrzött)
- **Utalás kivéve** (a felhasználó döntése: Lara utalni sosem fog, a kifizethetők
  a Pénzügyek dolga): `TaskType.UTALAS` törölve, a Tudásháló „Utalások" témája,
  a „+ Feladat" opció és a felületi szövegek kikerültek. Migráció
  `k4e1b52y9z63`: az `utalas` bizalmi-szint sor törlődik, a nyitott
  utalás-feladatok indokkal visszavontak (nem törlődnek). Utalás-feladat
  létrehozása 400.
- **Vészleállítás = teljes leállás** (`settings_service.leallitva`): minden
  Celery-feladat induláskor kilép (megfigyelés, distill, eval, önellenőrzés,
  levelezés); a levelezés-olvasó futás közben is figyeli (friss munkamenetből);
  az API minden nem-olvasó kérése 423 (router-szintű függőség), kivéve
  `/pause` és `/resume`. A tudás és a kapcsolók nem változnak; a
  visszakapcsolás oda tér vissza. Leállítás/visszakapcsolás a Naplóba kerül
  (`eroforras = lara`). Felület: minden Lara-oldalon piros csík, a
  Beállításokban „Lara leállítása" / „Lara visszakapcsolása".
- **Levelezés-olvasás** (`app/admin_agent/levelezes.py`): a szamla@ postafiók
  szálai a tanulás kezdete óta (bejövő és küldött), szálanként egy
  `email` hatókörű tudás-JELÖLT: partner, tárgy, levelek időrendben (idézett
  részek levágva), a mi válaszaink, csatolmány-kivonat (PDF `pypdf`, XML,
  Excel/CSV, szöveg), és ha a szálból számla érkeztetődött, ahogy rögzítettétek.
  Idempotens (`historyId` verzió); új levélnél a jelölt frissül (a jóváhagyott
  újra jelölt). Gépi (no-reply) szál kimarad. Csak olvas. Jóváhagyás után:
  e-mail-tervezetnél (`kapcsolodo_tudas(hatokor="email")`) és számla-elemzésnél
  (a modell adatként kapja) használja; Tudásháló „E-mailek" téma.
  Félóránkénti Celery (`admin_agent.levelezes`), kézi futtatás a Tanulás
  oldalon, forrás-kapcsoló a Beállításokban (`l5f2c63z0a74` bekapcsolja).
- Tesztek: `test_admin_agent_levelezes.py` (6, hamis Gmail-szolgáltatással):
  jelölt idézet nélkül + csatolmány-kivonat; változatlan szál nem töltődik le
  újra, új levélnél frissít; gépi szál kimarad; jóváhagyás után partner szerint
  előkerül; vészleállítás futás közben, API 423, ütemezett feladatok; utalás
  nem feladattípus. Élő próba (demószál, utána törölve): Tanulás-kártya,
  Tudástár „Levelezés" jelölt, leállítás → piros csík → visszakapcsolás.
- **Külső beállítás kell:** a szamla@ levelek a hitelesített Gmail-fiókban
  legyenek (alias/továbbítás); a válaszaink csak akkor látszanak, ha ugyanebből
  a fiókból, a szamla@ címről mentek. A sandboxban nincs Gmail-hozzáférés, ezért
  valós postafiókon nem futott.

### P2. Levelezés-olvasás: éles „Váratlan szerverhiba" javítva ✅
- Két reprodukált 500-as ok: (1) NUL (0x00) bájt a levélben / PDF-kivonatban —
  a PostgreSQL szövegmezője nem tárolhatja → most minden szöveg és metaadat
  vezérlőkarakter-szűrőn megy át; (2) a Gmail-lista hibája (pl. hiányzó
  olvasási jog, lejárt hozzáférés) nem volt elkapva → most érthető
  `gmail_hiba` üzenet. Emellett: szálanként saját mentési pont (egy hibás szál
  nem rontja el a többit, az oka a futás `hibak` listájában), a kézi futás
  ~40 mp-es időkerettel (nincs időtúllépés; a maradékot a következő futás
  viszi), és a végpont bármi más hibánál konkrét okot ad vissza.
- Nem ellenőrzött: az éles postafiókon (a sandboxban nincs Gmail) — az éles
  napló nélkül nem biztos, melyik ok volt; mindkettő javítva, tesztelve.

### Q. Magyarázat a feladat ellenőrzésénél (mezők nélkül) ✅
- `POST /tasks/{id}/corrections`: a `javitott` elhagyható; ha csak összefoglaló
  magyarázat jön (mit hova kellett volna tenni és miért), `Correction`
  `tipus=magyarazat` (feldolgozva) + AZONNAL jóváhagyott tudás-darab a feladat
  típusához (partnernév + Lara javaslatának kivonata + a magyarázat) — ugyanúgy,
  mint a Kérdésekre adott magyarázat. Partner szerint előkerül
  (`kapcsolodo_tudas`), így a számla-elemzés / tervezet modellje megkapja. Üres
  küldés 400. A mezőszintű javítás útja változatlan.
- Felület: „Javítás / magyarázat Larának" — elöl a szabad szöveges magyarázat,
  a mezőszintű javítás lenyitható, opcionális rész.
- Tesztek: `test_admin_agent_magyarazat.py` (2). Élő próba demó-feladaton
  (utána törölve).

### R. Tanulás az AI asszisztens munkájából ✅
- `app/admin_agent/asszisztens.py`: Lara az AI asszisztens beszélgetéseit
  KÉRÉS-KÖRÖNKÉNT figyeli (felhasználói kérdés + válasz + a közben indított
  írási műveletek az `ai_muveletek` naplóból). Minden LEZÁRT kör (nem fut, nincs
  jóváhagyásra váró művelete) tudás-JELÖLT: ki, mikor, melyik oldalról
  kérdezett, a kérdés, a válasz, és a műveletek állapottal (végrehajtva /
  a felhasználó ELUTASÍTOTTA / hiba) + a kérés kulcsadataival (partnernév,
  összeg…). A téma a művelet útvonalából (számla / TIG / szerződés / e-mail /
  általános), ez a jelölt hatóköre — jóváhagyás után partner szerint előkerül
  a számla-elemzésnél és a tervezeteknél. Idempotens (körönként forrásesemény,
  a kör ujjlenyomata a verzió); csak a tanulás kezdete óta; vészleállításnál
  nem fut; csak olvas.
- Az asszisztens felhasználói üzenete mostantól az oldal-kontextust is tárolja
  (`ai_uzenetek.adat.kontextus`) — Lara ebből látja, melyik oldalról kérdeztek.
- Forrás-kapcsoló `engedett_forrasok.asszisztens` (migráció `m6g3d74a1b85`
  bekapcsolja), félóránkénti Celery (`admin_agent.asszisztens`), kézi futtatás
  és statisztika a Tanulás oldalon (kérések, végrehajtott / elutasított
  műveletek, témák), Tudásháló „AI asszisztens" téma, Tudástár „AI asszisztens"
  címke.
- Tesztek: `test_admin_agent_asszisztens.py` (3). Élő próba demó-beszélgetésen
  (utána törölve).

### S. Gyorsított tanulás ✅ (valós Gemini-beágyazás: ⚠️ nem ellenőrzött — kulcs nélkül „Beállítás szükséges")
- **Új megfigyelt források** (`observer.FIGYELT`, ugyanazon a biztonságos,
  csak olvasó, idempotens úton): megrendelői szerződés és TIG (`szerzodes`/`tig`),
  projektkód-komment (`projektkod`, csak ≥25 karakter), bevétel — a megrendelő
  mikor fizetett a határidőhöz képest (`kintlevoseg`), utalások felvezetése — a
  már elutalt számla hová lett rögzítve, milyen elszámolással (`szamla`; Lara
  nem utal), kiadott árajánlat + ügyfélnév és időpont alapján VALÓSZÍNŰ
  projektkód-lánc (`arajanlat`; a sablon nem), végleges törlés (2 óra után,
  vissza nem állítva — negatív jel, a tábla szerinti tudás-körben). Tudásháló:
  új „Projektek, ajánlatok" téma (6. szín `#5d10f8`, validátor: minden PASS,
  kontraszt-WARN → feliratok + jelmagyarázat), váz-él teszt 6-ra frissítve.
- **Automatikus megerősítés** (`admin_agent/megerosites.py`): ha ugyanannál a
  partnernél ≥ `auto_jovahagyas_min` (alap 3) eset egybehangzó (≥80%) és egyiket
  sem vetették el, a PÉLDÁK maguktól jóváhagyottak (`minosites=auto_jovahagyott`,
  nyomvonal `aa_action_traces.muvelet=auto_jovahagyas`). Szabad szöveg
  (komment, árajánlat) és törlés sosem; a bevétel tény → magától. Ember által
  visszavett auto-példa `kezi_jelolt` lesz, többé nem hagyja jóvá magától.
- **Szabályjavaslat a csoportokból**: ≥5 jóváhagyott, ≥90%-ban egybehangzó
  eset → `pending` szabály (`feltetelek.forras=megerosites`, `minta_kulcs`
  deduplikál); számlánál az önellenőrzés formátumában (`cel_tipus`), papírnál
  `mezo/ertek`; bevételből fizetési szokás (átlagos késés). SOHA nem élesedik
  magától. Fut: kétóránként az önellenőrzés után, éjszaka a distill után, kézzel.
- **Jelentés szerinti keresés** (`admin_agent/embedding.py`): a tudás-darabok
  Gemini-beágyazása (`GEMINI_EMBEDDING_MODEL`, alap `gemini-embedding-001`,
  768 dim) a meglévő `aa_memory_chunks.embedding` JSONB oszlopba — pgvector nem
  kell; koszinusz Pythonban, küszöb 0,62, csak jóváhagyott darab. A
  `kapcsolodo_tudas` új `hasonlo_jelentes` mezője a számla-elemzés, a
  TIG/szerződés- és az e-mail-tervezet modell-bemenetébe is bekerül (rokon
  tudás-körökkel). Fail-closed (kulcs/hiba → a régi, név szerinti út). A szöveg
  változása törli a vektort (ORM-esemény). Félóránkénti Celery
  (`admin_agent.beagyazas`) + kézi gomb.
- **Értékrangsor + napi összesítő** (`admin_agent/osszesito.py`): a várakozó
  jelöltek pontszáma (forrás, esetszám a partnernél, „egy esetre a
  megerősítéstől", elutasított asszisztens-művelet, frissesség); Tudástár
  „Legértékesebb elöl" (`/memory?rendezes=ertek`, okokkal); munkanap reggel
  értesítés + push a jóváhagyásra jogosultaknak (`lara_osszesito`).
- **Kérdés-értesítés**: új Lara-kérdésnél értesítés + push (`lara_kerdes`) a
  számla jóváhagyójának, egyébként a Lara-felelősöknek; több kérdés → egy
  összefoglaló címzettenként. A push-beállításokban mindkét típus kapcsolható.
- Kapcsolók (`aa_settings.limitek`, hiányzó kulcs = be): `auto_jovahagyas`,
  `auto_jovahagyas_min`, `szemantikus_kereses`, `napi_osszesito`,
  `kerdes_ertesites` — Beállítások → „Gyorsított tanulás". Új végpontok:
  `GET /learning-boost`, `POST /learning-boost/confirm`, `POST /learning-boost/embed`.
  Tanulás oldal: „Gyorsított tanulás" kártya.
- Tesztek: `test_admin_agent_gyorsitas.py` (8): új források, auto-jóváhagyás
  (küszöb, elvetett blokkol, visszavétel tartós, kikapcsolás), szabályjavaslat
  pending + dedup + bevétel-szabály, jelentés szerinti találat más partnernévnél
  + kikapcsolva/hibánál üres, vektor-érvénytelenítés, rangsor + összesítő,
  kérdés-értesítés összevonása, API. Teljes backend: 163 passed, 1 skipped.
  Élő próba demó-adaton (11 auto-jóváhagyás, 2 szabályjavaslat; utána törölve).

### T. A Tudásháló mérete a tudással nő ✅
- `components/admin-agent/Tudashalo.tsx`: a háló ÁTMÉRŐJE és Lara magjának
  mérete a látható tudás mennyiségével (pont + kapcsolat + 2× jóváhagyott
  kapcsolat) logaritmikusan nő: üres tudásnál 34%, kb. 2500 tudás-egységnél
  tölti ki a vásznat. Finoman animálva „kinő" (betöltéskor, új tudásnál és a
  Növekedés lejátszása közben is); a HUD „Háló átmérő" százalékot mutat. A
  pontok mérete nem zsugorodik, a kattintás-találat a pillanatnyi mérethez
  igazodik. Élő próba demó-tudással: 34% → 85% (utána törölve).

### U. Egyetlen felelős: Vidor Gergely — másnak Lara nem küld ✅
- `settings_service.lara_felelos`: a Beállításokban kiválasztott
  (`limitek.felelos_employee_id`), vagy név szerint a „Vidor Gergely" nevű
  aktív munkatárs; `csak_felelosnek` (alap: be) mód.
- Migráció `n7h4e85b2c96`: bekapcsolja a módot, név szerint beállítja a
  felelőst (ha megtalálja), és a nyitott Lara-feladatokat hozzá rendeli.
- Minden Lara-értesítés (kérdés, napi összesítő, ÚJ: `lara_feladat` —
  ellenőrzésre / jóváhagyásra vár, adatot kér; állapotváltáskor egyszer)
  KIZÁRÓLAG a felelősnek; ha nincs felelős, senkinek.
- Új Lara-feladat felelőse mindig ő (kézi létrehozásnál is); a felelős
  átállításakor a nyitott feladatok átkerülnek.
- Jóváhagyás/elutasítás csak a felelősnek (API 403, végrehajtó-őr is);
  kimenő levél csak a felelős saját címére (végrehajtó-őr).
- Beállítások → „Lara felelőse": választó, „Minden csak a felelőshöz" és
  „Értesítés Lara javaslatairól" kapcsoló; figyelmeztetés, ha nincs felelős.
- Tesztek: `test_admin_agent_felelos.py` (6). Teljes backend: 175 passed.

### V. A teljes rendszer figyelése (csak tanulás) + hatáskör: csak adminisztráció ✅
- `app/admin_agent/rendszer.py`: Lara óránként (`admin_agent.rendszer`, :40)
  átnézi az EGÉSZ HYPE OS-t (az adatbázisban létező, nem kizárt táblák — most
  97 terület), és két fajta TÉNY-tudást ír (`hatokor="rendszer"`,
  `minosites="rendszer_teny"`, azonnal használható, a Tudástárban elvethető,
  elvetett tényt nem ír vissza):
  1. **Rendszerismeret modulonként** (`rendszer:modul:<tábla>`): a modell
     leírása, tételszám, 30 napos mozgás, állapot-eloszlás, kötődések;
  2. **Projektkód-életút** (`rendszer:projektkod:<id>`): a projektkódhoz a
     rendszer minden részében kötődő tételek darabszámmal és állapottal.
- Csak olvas; csak `aa_memory_chunks` / `aa_learning_runs` írás (teszt
  ellenőrzi). Kizárva: Lara és az AI asszisztens táblái, hitelesítés /
  értesítés / push, felület-beállítások, munkatársi adatlap és dokumentumok;
  minden jelszó-, token-, kulcs-, bankszámla-, adóazonosító-, e-mail-,
  telefon-, lakcím-jellegű mező. Szabad szöveget nem másol, csak számlál.
  Egy hibás / még nem migrált tábla nem állítja meg (savepoint táblánként).
- A projektkód-életút bekerül a számla-elemzés, a TIG/szerződés- és az e-mail-
  tervezet modell-bemenetébe (`a_projektkod_eletutja_a_rendszerben`); a
  jelentés szerinti keresés rokon köreibe a „rendszer" is. Tudásháló: a
  „Projektek, rendszer" témában megrendelő ↔ projektkód élek.
- Forrás-kapcsoló `engedett_forrasok.rendszer` (migráció `o8i5f96c3d07`
  bekapcsolja), API `GET /system-learning`, `POST /system-learning/run`,
  Tanulás oldal kártya, Beállítások kapcsoló, Tudástár címke.
- **Hatáskör**: `enums.ADMIN_FELADATTIPUSOK` (számla, e-mail, TIG,
  szerződés, egyéb papírmunka). A végrehajtó minden eszköznél ellenőrzi
  (nem adminisztratív feladat/eszköz → blokk), az eszköz-regiszter betöltéskor
  is (nem adminisztratív eszköz fel sem vehető), a heti értékelés 3 új
  kritikus hatáskör-esetet futtat (diszpó / utómunka / portál módosítása
  tiltott), és a modell rendszerpromptja is kimondja.
- Tesztek: `test_admin_agent_rendszer.py` (6). Teljes backend: 181 passed.
- **Éles hiba javítva** („Váratlan szerverhiba" a „Rendszer átnézése most"
  gombra): az `ajanlatkeresek` tábla `updated_at` oszlopa időzóna NÉLKÜLI, a
  többi időzónás — ha egy projektkódnál munkafelajánlás és más mozgás is volt,
  a legutóbbi mozgás összehasonlítása `TypeError`-t dobott (a fejlesztői
  adatban ilyen nem volt). Most minden időpont időzónássá normalizálva, a
  projektkód-életút lekérdezései is táblánként védettek (egy hibás tábla nem
  állítja meg), és a kézi futtatás hibánál érthető üzenetet ad. Regressziós
  teszt: `test_idozona_nelkuli_tabla_nem_dont_el`.

### W. Folyamatos önteszt a teljes adminon és a rendszeren — kérdésekkel ✅ (éles adaton: ⚠️ nem ellenőrzött)
Kérés: Lara, ahogy átnézi az egészet és az adminisztrációt, folyamatosan
tesztelje magát, és kérdezzen, ha nem érti, miért van valami úgy — a teljes
projektkód-, TIG-, szerződés- és számla-részen és a teljes Utókövetésen.
- Új modul: `app/admin_agent/onellenorzes_bovitett.py`, az önellenőrzés
  (`onellenorzes.py`, kétóránként + kézzel) része, saját savepointban (egy
  hibája nem állítja meg a régi részeket). Csak olvas; csak `aa_` táblába ír.
- **Vak jóslat** (`tipus="admin_dontes"`): megrendelői szerződés és TIG
  (kihagyva-e, +ÁFA), projektkód-döntések (papír nélkül, számla kihagyva,
  bevételbe ne), bevétel (késés a partner mediánjához képest, 15 nap tűrés),
  belsős TIG (havi összeg az előző hónaphoz, +ÁFA). Partnerenként a többi
  eset (≥2, ≥80% egyetértés) vagy alapértelmezés alapján.
- **Elvárás-ellenőrzés** (`tipus="rendszer_elteres"`): fizetett, de nincs
  papír; TIG 30+ napja lezárva, de nincs bevétel; alvállalkozó kifizetve
  szerződés/TIG nélkül.
- **Fogalom-kérdések** (`tipus="rendszer_fogalom"`): a figyelt táblák
  állapot-mezőinek ≥3 tételes értékei; futásonként ≤3 új, egyszerre ≤8 nyitott;
  a válaszhoz szöveg kötelező. A találati arányba nem számít bele.
- Válasz: „mindig / magyarázat" → tudás (`MemoryChunk`, `forras=kerdes:<id>`),
  és csak a megválaszolt esetnél ÚJABB esetekre vonatkozik (a múltat nem
  teszi hibássá); „kivétel" → csak az eset; „hiba" → `AdminTask` (egyéb,
  „Javítandó (Lara kérdéséből)…") Lara felelősének.
- Felület: Kérdések oldal új szűrők (Projektkódok, Bevételek, Eltérések,
  Rendszer), típusonkénti válaszlehetőségek és esettábla; Tanulás oldal
  önellenőrzés-kártyáján az új területek.
- Tesztek: `test_admin_agent_onellenorzes_bovitett.py` (7). Teljes backend:
  188 passed, 1 skipped. tsc, eslint, `next build` rendben. Dev szerveren
  kipróbálva demóadattal (kérdések megjelenése, „Hiba" → feladat), utána a
  demósorok törölve (időbélyeg-ellenőrzéssel).

### X. Utánanézés az AI asszisztens tudásával ✅ (valós Gemini-hívás: ⚠️ nem ellenőrzött — kulcs nélkül „Beállítás szükséges")
Kérés: Lara néha olyat kérdez, amire az AI asszisztens magától is jól
válaszolna — vonjuk bele az asszisztens tudását egy az egyben, hogy Lara is
átlásson mindent.
- Új modul: `app/admin_agent/nyomozas.py`. Mielőtt Lara embert kérdezne, maga
  is utánanéz, az AI asszisztens CSAK OLVASÓ eszközeivel (globális kereső,
  teljes végpont-katalógus, GET a saját API-n, entitás-lekérdezés/-összesítés),
  az asszisztens tudásával (a rendszerüzenet receptjei + az entitás-séma) és a
  saját tudásával (szabályok, hasonló esetek, projektkód-életút).
- Csak olvas: író eszköz (api_muvelet, számla-feltöltés, csatolás) nincs a
  modell kezében, és ha kérné, az eszköz-réteg elutasítja. Minden hívás a
  futtató jogosultságával megy (háttérben Lara felelőse, kézzel a kérő), és az
  eredményt a felület CSAK neki mutatja.
- Kimenet a kérdés kontextusában (`lara_nyomozas`): válasz, javaslat
  (mindig / magyarázat / kivétel / hibás / nem tudom), biztosság,
  bizonyítékok (csak belső link), a lépések listája. A kérdést továbbra is
  ember zárja le — egy kattintással elfogadhatja Lara válaszát.
- Ütemezés: a kétóránkénti önellenőrzés után legfeljebb 3 friss kérdésnél
  (`limitek.nyomozas`, `limitek.nyomozas_max`); kézzel: „Nézz utána most"
  (`POST /questions/{id}/investigate`, a felelős-őr mögött). Fail-closed:
  modellhiba → „nem tudom", a kérdés marad.
- Felület: Kérdések oldalon „Lara utánanézett" panel (válasz, bizonyítékok,
  „Hol nézett utána", „Elfogadom Lara válaszát", „Nézz utána újra"),
  statisztika (hánynál nézett utána, hánynál talált választ, hányat fogadtatok
  el); Beállításokban kapcsoló.
- Javítva: a modell rendszerpromptjában „ügynöke" helyett „munkatársa"
  (CLAUDE.md elnevezési szabály).
- Tesztek: `test_admin_agent_nyomozas.py` (5, hamis modellel). Teljes backend:
  193 passed, 1 skipped. tsc, eslint, `next build` rendben. Dev szerveren
  demóadattal kipróbálva (panel, elfogadás → tudás + statisztika; felelős
  nélkül a kézi utánanézés 403), utána a demósorok törölve.

### Y. Megoldási javaslat a feladatokhoz + gyorsított tanulás a Geminivel ✅ (valós Gemini-hívás: ⚠️ nem ellenőrzött — kulcs nélkül „Beállítás szükséges")
Kérés: (1) ha a kérdéseknél valami hiba miatt nem készül el, és Lara abból
feladatot csinál, ahhoz is javasoljon megoldási ötletet — ne csak a kívülről
kapott feladatnál; (2) a rendszerben bekötött Geminit (az AI asszisztensé)
kössük be Larába is, hogy gyorsabban tanuljon, nagyobb tudásra tegyen szert és
gyorsan fejlessze önmagát.
- `app/admin_agent/megoldas.py`: MINDEN „hibás" válasz (számla, papír,
  bővített kérdések) javítási feladatot készít (`egyeb` / `javitas`) Lara
  felelősének, azonnali, linkes lépésekkel a kérdés adataiból. Erre épül Lara
  saját javaslata: a közös csak-olvasó eszköz-hurok (`nyomozas.eszkozhurok`)
  utánanéz a rekordoknak, és konkrét lépéseket ad (rekord, mező, érték, link;
  csak belső link; nem-adminisztratív teendő csak figyelmeztetésként). Bármely
  feladathoz kérhető (`POST /tasks/{id}/solution`, felelős-őr mögött); a
  háttérben a javítási feladatok elöl, kétóránként legfeljebb 3; a „hibás"
  válasz után a felület azonnal el is indítja. A modell-rész csak a
  futtatónak látszik; semmit nem módosít.
- `app/admin_agent/gemini_tanulas.py`: Lara UGYANAZT a Gemini-kapcsolatot
  használja, mint az AI asszisztens (`GEMINI_API_KEY`, `GEMINI_MODEL`). Új:
  éjszakánként **partner-profil** (≥3 jóváhagyott eset → tömör profil-jelölt
  + függő szabályjavaslat, csak adminisztratív hatókörre; ujjlenyomattal nem
  kérdez újra), és **önreflexió** (a kérdésekre adott válaszokból, a
  javításokból és az önellenőrzés arányaiból tanulság-jelöltek + gyenge
  pontok). Minden eredmény jelölt / függő — ember hagyja jóvá; kódot,
  promptot, jogosultságot, küszöböt Lara nem ír át.
- API: `GET /gemini` (állapot, funkciók, eredmények — titok nélkül),
  `POST /gemini/test` (apró valódi hívás), `POST /gemini/learn`.
- Felület: feladat oldalán „Lara megoldási javaslata" kártya; Tanulás oldalon
  „Gemini — gyorsított tanulás és önfejlesztés" kártya; Beállításokban két új
  kapcsoló; Tudástárban „Partner-profil (Gemini)" / „Tanulság (önreflexió)".
- Tesztek: `test_admin_agent_megoldas_gemini.py` (6), a papír-teszt a
  javítási feladattal bővült. Teljes backend: 199 passed, 1 skipped. tsc,
  eslint, `next build` rendben. Dev szerveren demóadattal kipróbálva, utána a
  demósorok törölve.

### Z. Önellenőrzés: a válaszok beszámítanak + vizsga véletlen / teljes adaton ✅ (éles adaton: ⚠️ nem ellenőrzött)
Visszajelzés: telik az idő, válaszolt is Lara kérdéseire, de a találati arány
nem javult (94%, 15 eltérés — mind a 15 megválaszolva), és az önellenőrzés
mindig ugyanazokon az adatokon fut.
- Ok: a megválaszolt eltérés továbbra is „eltért”-ként számított, és a vak
  jóslat (helyesen) nem használhatja az adott eset saját tanulságát — ezért a
  válasz ugyanazt az esetet sosem javíthatta a mérőszámban.
- Új `app/admin_agent/idoszak.py`: a válasz-kategóriák — „hibás rögzítés” →
  Lara javára (`lara_helyes`), „mindig így” / „magyarázat” → megtanulta
  (`tanult`), „kivétel” / „nem releváns” → kimarad. Új mérőszám: **pontosság a
  válaszaid után**; mellette a **vak találati arány** változatlan (szigorú), és
  a **nyitott eltérés** (amire még nincs válasz). Minden területre is.
- Adatkör (`Idoszak`): a fő kör a tanulás kezdete óta mindent néz (mint eddig);
  minden futásnál **vizsga** is: a tanulás kezdete ELŐTTI rekordokból egy
  VÉLETLEN adag (alap 30%, a mag futásonként más; `limitek.onellenorzes_minta`),
  a teljes múlt társ-adatával. Kézzel „Vizsga az összes elérhető adaton”
  (`POST /self-check?vizsga=teljes`). A régi adatból futásonként legfeljebb 3
  új kérdés, „Régi adatból” jelöléssel. Kapcsoló: `limitek.onellenorzes_vizsga`.
- A bővített rekordok az adatkörnél a LÉTREHOZÁS idejét nézik (a módosítás
  ideje friss lehet).
- Felület: Tanulás oldal — Pontosság / Vak arány / Nyitott eltérés, vizsga-
  sáv, két indítógomb, a futás-táblában pontosság + vizsga oszlop; Beállítások
  kapcsoló.
- Tesztek: `test_admin_agent_onellenorzes_adatkor.py` (4). Teljes backend:
  203 passed, 1 skipped. tsc, eslint, `next build` rendben. Dev szerveren a
  teljes vizsga lefutott (a dev adatban nincs régi rekord → 0), a futás sorai
  törölve.

### AA. Lara előbb utánanéz, és csak akkor kérdez, ha tényleg nem tudja ✅ (valós Gemini-hívás: ⚠️ nem ellenőrzött)
Visszajelzés: sok olyan kérdés jön, amire a „Nézz utána” gombbal Lara magának
is meg tudja adni a választ.
- Az önellenőrzés új kérdéseiről NEM megy azonnal értesítés (ha az utánanézés
  elérhető): a kétóránkénti futás előbb utánanéz (futásonként legfeljebb 10,
  eddig 3). Ha Lara legalább 75%-ban biztos (`limitek.onallo_min`), nem
  kérdez: a kérdés `lara_valaszolt` állapotba kerül („Lara magától
  megválaszolta — ellenőrizd”), értesítés nélkül. Értesítés csak arról megy,
  ami utánanézés után is nyitott maradt.
- Tudás a magától adott válaszból csak a felelős elfogadása után lesz (a
  bővített önellenőrzés sem tanul belőle addig). Kérdések oldal: új szakasz
  „Rendben” / „Nem így — kérdezz” / „Mind rendben” gombokkal
  (`POST /questions/{id}/answer` a felelős-őrrel, `POST /questions/{id}/reopen`).
  Kapcsoló: `limitek.onallo_valasz`.
- Tesztek: `test_admin_agent_nyomozas.py` +2.

### AB. Tapasztalás: önálló tanulás a teljes adattörténetből, a Geminivel, adaton ellenőrizve ✅ (éles adaton és valós Gemini-hívással: ⚠️ nem ellenőrzött)
- Kérés: Lara a Gemini segítségével a háttérben önállóan tanuljon, hogy az
  adat és a kapcsolatok száma drasztikusan nőjön, és vele a bizonyosság is
  (a Tudásháló átlagos bizonyossága 21% volt).
- A bizonyosságot nem hangoltuk fel, és a modell sem mondhatja meg, mennyire
  biztos valami: csak valódi, ellenőrzött bizonyíték növeli.
- `app/admin_agent/tapasztalas.py`:
  1. **Tények a teljes történetből**, modell nélkül. Minden lezárt emberi munka
     (szerződés, TIG, belsős TIG, kiadás, megrendelői papír, bevétel,
     utalás-felvezetés), a megfigyelő kinyerőivel. Partnerenként: milyen
     formában, melyik projektkódon, melyik megrendelőnek, milyen típussal
     dolgozunk vele. Tapasztalat az, ami legalább kétszer megtörtént. A régi
     korszak ×0,4 súllyal számít.
     - Tárolás: `aa_source_events` (`forras=tapasztalas`, partnerenként egy
       sor, lenyomattal) és egy tudás-darab `minosites=tapasztalat`
       címkével.
  2. **Hipotézis → ellenőrzés.** A Gemini zárt típusú, ellenőrizhető
     állításokat javasol: forrás, projektkód, megrendelő, típus, összegsáv,
     „papír a kiadás mellett”, fizetési késés.
     - Lara mindet a partner összes rekordján ellenőrzi. Megmarad, ha legalább
       3 eset és 80% igazolja (`minosites=adat_igazolta`); egyébként cáfolt,
       és a Gemini találati arányába számít.
     - Új adatnál újraellenőriz, és visszavonja, ami már nem áll
       (`adat_cafolta`).
     - Szabályt nem javasol és nem élesít. Az ember által elvetett állítást
       nem hozza vissza.
- **Tudásháló:** új „tapasztalat” kapcsolatfajta.
  - Súly: rekordonként 0,35, igazolt állítás esetén igazoló esetenként 0,5.
  - A tapasztalt kapcsolat folytonos vonal; a HUD mutatja a számukat.
  - `MAX_PARTNER` 320-ra, `MAX_KOD` 220-ra nőtt.
- **Dátum:**
  - Valódi hiba: a Tudásháló HUD a hálót egy nappal a legutolsó tudás után
    mutatta, ezért mindig a holnapi dátumot írta ki. A kiírt dátum mostantól
    legfeljebb a legutolsó tudás ideje.
  - Minden Lara-modellhívás megkapja a budapesti mai dátumot
    (`llm.mai_datum()`). Eddig a `strukturalt_hivas` promptjaiban nem volt
    benne, az utánanézés pedig UTC-dátumot kapott. Az AI asszisztens is ezt
    használja.
- **Ütemezés és vezérlés:**
  - Celery `admin_agent.tapasztalas` óránként (:10). Csak bekapcsolt
    „Tanulás és megfigyelés” forrással fut, vészleállításnál nem.
  - Kapcsolók: `limitek.tapasztalas` és `limitek.tapasztalas_gemini_max`
    (alap: 6 partner/kör).
  - Kézi indítás: `POST /api/v1/admin-agent/experience` (felelős-őr).
  - Állapot: a `GET /gemini` válaszában (`tapasztalas`), a felületen a
    Tanulás és minőség → Gemini kártyán.
- **Tesztek:** `test_admin_agent_tapasztalas.py` (5).
- **Nem ellenőrzött:** a dev adatbázisban szinte nincs adat (3 partner,
  partnerenként 1 rekord), ezért a bizonyosság tényleges emelkedése csak éles
  adaton mérhető. Valós Gemini-kulcs nélkül a hipotézis-kör kimarad, a
  tény-gyűjtés akkor is fut.

## Biztonsági alapállás (induláskor)
- Modul: KIKAPCSOLVA (`aa_settings.module_enabled=false`, auditált DB-config).
- Mellékhatás: TILTVA (`aa_settings.side_effects_enabled=false`).
- Minden feladattípus: L0 (árnyék); a trust szintek a Beállításokból állíthatók.
- Banki utalást végrehajtó eszköz nincs regisztrálva. Éles autonómia nincs.

## Módosított/új fájlok (kivonat)
- Backend: `app/admin_agent/{enums,policy,settings_service,pipeline_szamla,
  executor,proposals,integrations,learning,memory,evals,observer,llm,tervezo}.py`,
  `app/models/admin_agent.py`, két migráció (`g0a7x18u5v49`, `h1b8y29v6w50`),
  `app/api/routes/admin_agent.py`, `app/workers/admin_agent_tasks.py`,
  `tests/test_admin_agent_{policy,szamla_pipeline,executor,email,learning}.py`.
- Frontend: `app/(app)/admin-agent/{page,munkasor,munkasor/[id],jovahagyasok,
  tudastar,tanulas,naplo,beallitasok}`, `components/admin-agent/*`,
  `lib/{nav,api}.ts`, `components/NavList.tsx`.
- Dokumentáció: `docs/admin-agent/*`, `backend/.env.example`.

## Következő lépés
- Valós Gemini-hívás ellenőrzése éles kulccsal (a kód kész, hamis adapterrel
  tesztelt); worker crash-recovery / reconcile end-to-end; frontend E2E. Az éles autonómia továbbra is emberi engedélyhez + méréshez
  kötött.
