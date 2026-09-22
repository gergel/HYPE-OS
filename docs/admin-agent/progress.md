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

### B. Additív migrációk + magmodellek + policy engine + jogosultságok 🟡
- Tervezett táblák (első migráció): `admin_task`, `agent_run`, `action_trace`,
  `correction`, `action_proposal`, `approval`, `action_execution`,
  `playbook_rule`, `trust_policy`, `admin_agent_setting` (singleton
  kill-switch/flag), `source_event`.
- Enumok (állapotgép, R0–R3 kockázat, L0–L4 trust): `app/admin_agent/enums.py`.
- Policy engine (szerveroldali kockázat-besorolás + végrehajtási döntés +
  kill-switch): `app/admin_agent/policy.py`.
- Jogosultság: `/admin-agent` oldal + finomabb permissionök (view/edit/approve/
  financial_approve/legal_approve/rule_activate/trust_change/audit_export).
- **Hátra (következő migráció):** `memory_chunk`, `eval_case`, `eval_run`,
  `learning_run`, `agent_release`, outbox — a memória/eval fázissal (F).

### C. Munkasor + taskrészlet + jóváhagyási felület + meglévő oldalak ⛔
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
- (ez a szakasz commitonként frissül)

## Következő lépés
- B fázis: migráció + modellek + enums + policy + settings + L0-API + minimal UI,
  majd C fázis (munkasor/jóváhagyás felület).
