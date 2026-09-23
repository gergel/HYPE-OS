# HYRON – architektúra és bekötési térkép

Ez a dokumentum a HYPE OS-be integrált **HYRON** modul tényleges
bekötési pontjait, adatfolyamát és a megőrzendő üzleti szabályokat rögzíti.
A modul célja az adminisztrációs munka (számla-felvezetés, e-mail-válasz,
TIG-előkészítés, szerződés-előkészítés, utalás-előkészítés) fokozatos,
mért, emberi felügyelet mellett történő automatizálása. **Banki utalás
végrehajtása NEM része a modulnak.**

## 1. A tényleges stack (repófelmérés eredménye)

| Terület | Ami a repóban VAN | A HYRON ezt használja |
|---|---|---|
| Backend | FastAPI, SQLAlchemy 2 (`mapped_column`), Alembic (kézi revíziók) | Additív migrációk, új `app/admin_agent/` csomag + `app/api/routes/admin_agent.py` |
| Adatbázis | PostgreSQL (psycopg) | Új táblák a meglévő konvenciókkal (`TimestampMixin`, JSONB) |
| Worker | **Celery + Redis** (`app/workers/portal_tasks.py` a közös `celery_app`), **Celery beat** (`beat_schedule` a calendar/portal_export taskokban) | Az ingest / éjszakai tanulás / heti eval / határidő-eszkaláció Celery taskok + beat |
| DB-alapú háttérfeladat | `services/hatter_feladat.py` + `hatter_feladatok` tábla (több-worker-biztos, DB-zár + napló) | Minta a tartós, több-worker-biztos futáskövetéshez |
| Auth / jogosultság | Szerepkör (`Role`) + oldal×művelet (`require_page_action(page, action, *roles)`, `check_page_action`, `page_permissions`) | Új oldal: `/admin-agent`, saját permissionökkel |
| Modell (AI) | `google-genai` (Gemini) SDK jelen van; AI-asszisztens tool-réteg (`services/ai_eszkozok.py`, `services/ai_assistant.py`) | Gemini-adapter a kiolvasáshoz; a tervező/embedding cserélhető |
| Számla-kiolvasás | `services/kiadas_kiolvasas.py` (prompt + strukturált kimenet), `services/szamla_erkeztetes.py` (kód-először párosítás) | Ezekre wrapelt, auditált eszközök |
| Utalás-felvezetés | `services/utalas_felvezetes.py`, `api/routes/utalas_felvezetes.py` | Utalás-**előkészítés** eszköz (nem banki végrehajtás) |
| TIG / szerződés | `performance_certificates.py`, `internal_performance_certificates.py`, dokumentumkezelés (`services/attachments.py`, `megrendeloi_szamla.py`) | TIG/szerződés **előkészítés** eszköz, meglévő sablon/dokumentumkezeléssel |
| Gmail | `services/google_email.py` (OAuth, küldés/lehúzás) | Ingest connector + e-mail-**javaslat** (küldés jóváhagyással) |
| Tárolás | Cloudflare R2 (`services/portal_storage.py`, boto3) | Nagy fájlok/dokumentumok referenciával + integritási hash |
| Frontend | Next.js App Router, `app/(app)/` route-csoport, `lib/nav.ts` sidebar, sötét prémium design tokenek | Új `/admin-agent` aloldalak a meglévő design tokenekkel |

## 2. Fontos tech-megfeleltetések (logikai név → tényleges)

- **Multi-tenancy / `org_id`:** a HYPE OS **egyszervezetes** — nincs `org_id`
  a modellekben, nincs több-tenant elkülönítés. Ezért a HYRON sem vezet
  be `org_id`-t; a hozzáférést a **meglévő RBAC** (szerepkör + oldal-jog +
  rekordszintű szűkítés, pl. `lathato_anyagok`) érvényesíti minden úton
  (API, worker, tool, keresés, dokumentumletöltés). A prompt „szervezeti
  elkülönítés" követelménye itt = a meglévő rekordszintű hozzáférés + az az
  invariáns, hogy a modul soha nem lép ki a HYPE OS adatkörén.
- **pgvector:** a jelenlegi Postgresben **NINCS telepítve** a `vector`
  extension. Ezért a memória/retrieval réteg **pgvector-opcionális**: ha az
  extension elérhető és engedélyezett (config), vektoros keresés megy;
  egyébként dokumentált, jogosultság-szűrt **pontos + szöveges (trigram/ILIKE)
  fallback** működik, szűkebb autonómiával. Ez „Beállítás szükséges" állapot,
  nem néma csend.
- **Tartós worker:** Celery + Redis + beat (megvan). A DB-alapú
  job-nyilvántartás mintája a `hatter_feladatok`.
- **Tábla-/útvonalnevek:** a master prompt logikai neveit a repó
  konvencióihoz illesztjük (magyar oszlopnevek ott, ahol a kód is magyar;
  `TimestampMixin`; JSONB). A megfeleltetést a `progress.md` és a modellfájl
  kommentjei rögzítik.

## 3. Megőrzendő üzleti invariánsok

1. **Egy projektkódhoz több projekt tartozhat.** A **bevétel projektkódhoz**
   tartozik; a **kiadás projekten** van és **projektkód-szinten összesül**.
   Nincs projektszintű bevételi logika. Ugyanazt a kiadást ne számold el
   külön a projekten és még egyszer a projektkódon.
2. HYRON **mindig a meglévő pénzügyi szolgáltatáson keresztül** dolgozzon
   (pl. `Expense` létrehozás a `_expense_before_create` hookkal, nem nyers
   INSERT), így az áfa/deviza/összesítés-szabályok érvényesülnek.
3. **Kiadás akkor számít „elköltöttnek"** a kimutatásba, ha ki van fizetve
   (`kesz`) – lásd a `fizetes_datuma`/`kiadas_datuma` összevonást. HYRON
   ezt nem kerülheti meg.
4. HYRON **nem** végez könyvelési feladást, kifizetettre állítást
   automatikusan (a számlafolyamat csak belső kiadás-rögzítésig mehet L2-ben),
   nem módosít partnertörzset/bankszámlát, és **nem indít banki utalást**.

## 4. Adatfolyam (magas szint)

```
Forrás (Gmail / feltöltött PDF / appon belüli esemény)
  → SourceEvent (forrás-azonosítóval, duplikáció-védelemmel)
  → 0..N AdminTask (típus + szándék; egy levélből több számla + válaszigény)
  → AgentRun (kontextus → aktív szabályok + engedélyezett példák → strukturált javaslat)
  → determinisztikus (kód-először) validálás  → ActionProposal (immutable payload + hash)
  → Policy engine (risk × trust × altípus × kill-switch)
       ├─ L0: csak belső javaslat, semmi mellékhatás
       ├─ jóváhagyás-köteles: Approval (a pontos payload-hash-hez kötve)
       └─ engedélyezett auto: ActionExecution (idempotenciakulcs)
  → auditált eszköz-hívás a MEGLÉVŐ szolgáltatáson át → eredmény-ellenőrzés
  → ActionTrace (audit) ; emberi javítás → Correction → (éjszakai) tanulás
```

## 5. Biztonságos alapállás

- **Modul kapcsoló** (`ADMIN_AGENT_ENABLED`, alap: ki) és **mellékhatás-tiltás**
  (`ADMIN_AGENT_SIDE_EFFECTS_ENABLED`, alap: ki).
- **Feladattípusonként alap L0** (árnyék): csak olvasás/elemzés/belső
  javaslat/napló; nem módosul üzleti rekord, nincs Gmail-piszkozat, nincs
  külső hívás.
- **Vészleállítás** (globális kill-switch) minden mellékhatásos lépés ELŐTT
  ellenőrizve, nem csak a futás elején.
- Első induláskor **nem** dolgozza fel a teljes régi postaládát; csak az
  admin által kijelölt bemeneti kört.

## 6. Kockázati és bizalmi modell

- **Kockázat (szerveroldali, a modell nem írhatja át):** R0 olvasás/belső
  javaslat · R1 ellenőrzötten visszafordítható belső írás · R2 külső
  kommunikáció vagy pénzügyi/jogi jelentőségű változás · R3 tiltott (pl. banki
  végrehajtás).
- **Bizalom (feladattípus×altípus):** L0 árnyék · L1 előkészítés + emberi
  véglegesítés · L2 szűk, alacsony kockázatú auto · L3 munkasor-önállóság
  kivételkezeléssel · L4 csak külön engedélyezett szűk körben.
- A magasabb L-szint **nem** írhatja felül az R3-tiltást. A végrehajtási
  engedélyt a `policy engine` adja (risk × trust × altípus × kill-switch),
  minden hívási úton (worker, közvetlen API, újrapróbálás).

## 7. Az implementáció helye a repóban

- `backend/app/admin_agent/` – enumok, policy engine, settings-szolgáltatás,
  (később) HYRON-mag, ingest, tanulás.
- `backend/app/models/admin_agent.py` – a modul táblái.
- `backend/app/api/routes/admin_agent.py` – az `/admin-agent` API.
- `backend/app/workers/admin_agent_tasks.py` – (később) Celery taskok + beat.
- `frontend/app/(app)/admin-agent/` – a felület aloldalai.

A tényleges készültséget és a következő lépést a `progress.md` követi.
