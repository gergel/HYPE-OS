# Admin-Ágens – haladás (élő folytatási pont)

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
  D/E), és a meglévő oldalakba (Pénzügyek beérkező számlák) való „Admin-Ágens
  árnyék-elemzés" gomb. Tudástár/Tanulás/Napló aloldalak: F/G fázis.
### D. Számlafolyamat végig L0/L1-ben, valós szolgáltatásokra kötve 🟡
- **L0 árnyék-elemzés kész** (`app/admin_agent/pipeline_szamla.py`): egy beérkező
  számlából (BejovoSzamla) forrásesemény → feladat → ügynökfutás → nyomvonal →
  művelet-javaslat, a policy engine döntésével. A javaslat payloadja pontosan a
  meglévő `services/szamla_erkeztetes.jovahagy` `dontes`-alakját írja le (az
  ágens a MEGLÉVŐ pénzügyi szolgáltatáson át dolgozna), de L0-ban VÉGRE NEM
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
  idempotencia). 15 admin-ágens teszt zöld; HTTP-smoke minden új végponton OK.
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
  banki eszköz, „Beállítás szükséges" DRAFT+NEEDS_INFO). 21 admin-ágens teszt zöld.
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
- 25 admin-ágens teszt zöld (`pytest tests/test_admin_agent_*.py`); tsc + eslint
  + `next build` zöld; migráció le/fel próbálva.
- Dokumentáció kész: `architecture.md`, `operations.md`, `permissions-and-risk.md`,
  `learning-and-evals.md`, `acceptance-checklist.md`, `user-guide.md`, `progress.md`,
  `.env.example` admin-ágens szekció.
- Hátra: valós modell (Gemini) elemzés explicit konfiggal + elkülönített teszt,
  worker crash-recovery + külső-timeout reconcile end-to-end, frontend E2E
  (Playwright), teljes backend regressziós suite futtatása.

### I. Teljes kattinthatóság + projektkód/utókövetés megfigyelés ✅
- **Kattintható belépési pontok:** Beérkező számlák sorain „Admin-Ágens" gomb
  (árnyék-elemzés → feladat); a feladat oldalán „Javítás rögzítése" űrlap +
  „Újraelemzés" / „Megszakítás"; a Tanulás oldalon Megfigyelés / Kezdeti
  visszatekintés / Háttér-tanuló / Értékelés gombok; a Tudástárban példák
  jóváhagyása/elvetése és szabályok élesítése/visszavonása.
- **Projektkód + Utókövetés bekötés:** „Admin-Ágens teendők" blokk a
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
- **Felület:** a feladat oldalán „Tervezet készítése (ügynök)", „Az ügynök
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
