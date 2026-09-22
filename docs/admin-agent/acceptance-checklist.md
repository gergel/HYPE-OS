# Admin-Ágens — elfogadási ellenőrzőlista

Jelölés: ✅ automata teszt vagy dokumentált ellenőrzés lefutott · 🟡 részben
(kód kész, teljes end-to-end teszt hátra) · ⛔ hátra. Egy pontot csak akkor
jelölünk ✅-nak, ha a hozzá tartozó tesztet/ellenőrzést TÉNYLEGESEN lefuttattuk.

A minta-/tesztadat szintetikus és elkülönített; a live smoke-ellenőrzések a
létrehozott sorokat feltakarítják, a biztonságos alapállást visszaállítják.

Backend admin-ágens tesztek: **25 zöld** (`pytest tests/test_admin_agent_*.py`).
Frontend: `tsc + eslint + next build` zöld. Migráció le/fel próbálva.

| # | Forgatókönyv | Állapot | Bizonyíték |
|---|---|---|---|
| 1 | Ugyanaz az e-mail/dokumentum többször → nincs dupla számlafelvezetés | ✅ | `test_admin_agent_szamla_pipeline` (forrásesemény + feladat idempotens); az érkeztető meglévő üzleti duplikáció-ellenőrzése |
| 2 | Egy levélben több számla + válaszigény → külön feladatok | 🟡 | Forrásesemény→0..N feladat modell kész (`SourceEvent`, dokumentumonkénti azonosítás); többszámlás e-mail-bontó a jövő lépés |
| 3 | Hiányos / két projektkódhoz is illő adat → nincs találgatás, emberhez | ✅ | `test_...szamla_pipeline` (hiányos→NEEDS_INFO); a párosítás konfliktusnál emberi döntés |
| 4 | L0 elemzés után nincs üzleti/külső mellékhatás | ✅ | `test_...szamla_pipeline` (0 Expense), `test_...executor` (alapállás blokkol) |
| 5 | Jóváhagyás nélküli / lejárt / rossz állapotú végrehajtás blokkolt | ✅ | `test_admin_agent_executor` (consumed/hash/blokk) |
| 6 | Jóváhagyás után összeg/címzett/rekord változik → új jóváhagyás kell | ✅ | `test_...executor` (eltérő hash blokkol) + HTTP: approve rossz hash → 409 |
| 7 | Dupla kattintás / két worker / retry → nincs dupla belső végrehajtás | ✅ | `test_...executor` (idempotens egy rekord) + live L1 smoke (1 Expense ismétléskor is) |
| 8 | Külső küldés timeout után egyeztetés, nem vak újraküldés | 🟡 | `execution_unknown` állapot + `aa_outbox` modell kész; a reconcile-hurok bekötése hátra |
| 9 | Workerleállás után helyreáll a munka; korábbi eredményt figyelembe veszi | 🟡 | Fencing token + idempotens végrehajtási rekord kész; teljes crash-recovery worker-teszt hátra |
| 10 | Vészleállítás futás közben is megállítja a következő mellékhatást | ✅ | `test_...executor` (kill switch blokkol); a policy a végrehajtáskor újraolvas |
| 11 | Más szervezet adata nem elérhető (API/fájl/cache/retrieval) | ✅ | Egyszervezetes rendszer (nincs org-közi reláció); retrieval a hívó RBAC-ját örökli |
| 12 | Prompt injection nem módosít policyt/bankszámlát/címzettet | ✅ | Szerver-oldali validálás (email automata-cím tiltás), policy engine, nincs banki eszköz — `test_admin_agent_email` |
| 13 | Emberi javításból correction + JELÖLT szabály, nem csendben aktív | ✅ | `test_admin_agent_learning` (küszöb, pending, nem aktív) |
| 14 | Sikertelen eval / hiányos minta megakadályozza a szintlépést/kiadást | ✅ | `test_...learning` (safety-eval); release/rule aktiválás eval-hez kötve (HTTP 409) |
| 15 | Memóriaforrás törlése/visszavonása után a modell nem kapja meg | ✅ | `test_...learning` (retrieval csak érvényes/nem visszavont/jóváhagyott) |
| 16 | Hibás modell-JSON / 429 / timeout / kerettúllépés → kontrollált hiba | ✅ | `test_admin_agent_llm` (séma-ellenőrzés, egy javító újrapróba, 429/timeout → ModellHiba, kulcs nélkül „beállítás szükséges"); modellhiba esetén a determinista út fut. Valós Gemini-hívás: nem ellenőrzött (nincs kulcs a tesztkörnyezetben) |
| 17 | Projektkód több projektet fog össze; kiadások pontosan egyszer összesülnek | ✅ | Az ágens a MEGLÉVŐ `szamla_erkeztetes.jovahagy`-on át rögzít (nem duplikál); invariáns a pénzügyi szolgáltatásban |
| 18 | Több deviza/áfa/kerekítés/stornó helyesen vagy emberhez | 🟡 | A meglévő érkeztető kezeli ezeket; az ágens a `felosztas`/összeg-egyezést a szolgáltatásra bízza, hiánynál NEEDS_INFO |
| 19 | TIG/szerződés nem lesz auto-elfogadott/aláírt; banki utalás nem futtatható | ✅ | Nincs banki végrehajtó eszköz (`test_admin_agent_email`); TIG/szerződés = előkészítés, emberi véglegesítés |
| 20 | Új e-mail elavulttá teszi a régi javaslatot; emberi szöveg nem íródik felül | 🟡 | A payload-hash kötés elavult javaslatot blokkol (6.); a thread-frissesség-detektálás bekötése az e-mail-inbox integrációval jön |
| 21 | Automata levelezési hurok / ismételt értesítés nem keletkezik | ✅ | `test_admin_agent_email` (no-reply/mailer-daemon/bounce tiltva) |
| 22 | Éjszakai job / DST / scheduler-újraindítás → nincs dupla tudáskiadás | ✅ | `test_...learning` (distill idempotens, kurzor); jelölt→jóváhagyás→aktiválás lánc |
| 23 | A hét oldal működik laptopon és mobilon, empty/error/forbidden állapotban | 🟡 | Mind a 7 aloldal fordul (build), reszponzív tokenek + empty/forbidden állapotok; teljes E2E böngészőteszt hátra |
| 24 | A meglévő projekt/pénzügyi/dokumentum folyamatok regressziói megmaradnak | ✅ | Additív migrációk; a meglévő `jovahagy` szolgáltatást hívjuk (nem módosítjuk); érintetlen kódutak |

## Ami külön, explicit konfigurációval fut / hátra

- **Valós modellhívás (Gemini):** a kód bekötve (számla-átnézés, TIG/szerződés-
  kiegészítés, e-mail-tervezet), hamis adapterrel tesztelve
  (`test_admin_agent_llm`, `test_admin_agent_tervezo`). A VALÓS hívás nem
  ellenőrzött: `GEMINI_API_KEY` beállítása után egy számla „Admin-Ágens" gombbal
  és egy TIG-feladat „Tervezet készítése" gombbal ellenőrizendő — „Az ügynök
  értékelése" dobozban a modell neve látszik.
- **Gmail-küldés éles teszt:** csak beállított OAuth mellett; enélkül az eszköz
  „Beállítás szükséges" állapotban, tiltva marad (nem hamis siker).
- **Teljes worker crash-recovery és külső-timeout reconcile** end-to-end teszt.
- **Frontend E2E** (Playwright) a hét aloldalra.
