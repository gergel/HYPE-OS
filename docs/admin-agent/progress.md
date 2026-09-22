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

### F. Memória, szabálykezelés, háttér-tanuló, eval, verziózott kiadások ⛔
### G. Trust-szintek, L2 (szűk), dashboard, értesítések, üzemeltetés ⛔
### H. Teljes tesztelés, migrációpróba, build, biztonsági ellenőrzés, docs ⛔

## Biztonsági alapállás (induláskor)
- Modul: KIKAPCSOLVA (`ADMIN_AGENT_ENABLED=false`).
- Mellékhatás: TILTVA (`ADMIN_AGENT_SIDE_EFFECTS_ENABLED=false`).
- Minden feladattípus: L0 (árnyék).
- Éles autonómia nincs; a mellékhatásos eszközök nincsenek regisztrálva/aktívak.

## Módosított/új fájlok
- Backend: `app/admin_agent/{enums,policy,settings_service}.py`,
  `app/models/admin_agent.py`, `alembic/versions/g0a7x18u5v49_admin_agent_core.py`,
  `app/api/routes/admin_agent.py`, `tests/test_admin_agent_policy.py`.
- Frontend: `app/(app)/admin-agent/{page,munkasor,jovahagyasok,beallitasok}.tsx`,
  `components/admin-agent/{AdminAgentTabs,AdminAgentSafetyBanner,AdminMunkasor,
  AdminBeallitasok,allapotok}.tsx`, `lib/{nav,api}.ts`, `components/NavList.tsx`.

## Következő lépés
- Taskrészlet-nézet (agent_run/action_trace/proposal idővonal) az `/admin-agent`
  alatt, majd a D fázis: számlafolyamat végig L0/L1-ben a valós pénzügyi
  szolgáltatásra kötve (érkeztető/utalás-előkészítés meglévő service-ei), a
  policy engine-en át generált javaslatokkal és a jóváhagyási felülettel
  összekötve. Csak ezután E (e-mail/TIG/szerződés) és F (memória/tanulás).
