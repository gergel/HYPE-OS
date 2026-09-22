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
- **Hátra:** taskrészlet-nézet (agent_run/trace/proposal idővonal), a
  jóváhagyás jóváhagyás/elvetés gombjai (a javaslat/végrehajtó réteggel, D/E),
  és a meglévő oldalakba (Pénzügyek, Projektek) való „Admin-Ágens javaslat"
  becsatlakozás. Tudástár/Tanulás/Napló aloldalak: F/G fázis.
### D. Számlafolyamat végig L0/L1-ben, valós szolgáltatásokra kötve ⛔
### E. E-mail, TIG, szerződés, utalás-előkészítés (korlátokkal) ⛔
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
