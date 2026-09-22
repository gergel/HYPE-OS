# Admin-Ágens — tanulás és értékelés

## Tanulás (retrieval + verziózott playbook)

A tanulás első változata **retrieval + verziózott szabálykönyv**, NEM automatikus
fine-tuning és NEM a forráskód/prompt/jogosultság csendes átírása. Az elfogadott
tudás a saját adatbázisban marad, visszakereshető forrással.

### Capture (rögzítés)
- Az emberi és ágensműveletek szerver-oldali nyoma: `aa_action_traces`, a
  javaslat (`aa_action_proposals`) és a végleges eredmény (`aa_action_executions`)
  külön tárolva.
- Emberi javítás → `aa_corrections` (mezőszintű diff, típus, magyarázat). A
  javaslat elutasítása is jel. A későbbi emberi változtatás nem feltétlenül
  korrekció: a típus (`besorolando`/`egyszeri_kivetel`/`stilus`/`tenyszeru_hiba`/
  `uj_uzleti_adat`) különbözteti meg; kétes esetben `besorolando`.

### Distill (háttér-feldolgozás) — `app/admin_agent/learning.py`
- Éjszakai (02:00) vagy kézi futás. Csak az `uj` korrekciókat dolgozza fel, majd
  `feldolgozva`-ra állítja → **idempotens**, újraindításkor nincs dupla feldolgozás.
- A hasonló javításokat (feladattípus × érintett mezők) csoportosítja. Legalább
  **2 hasonló** javításból lesz **szabály-JELÖLT** (`aa_playbook_rules`, `pending`);
  **egyetlen javításból nem lesz általános szabály**.
- A jelölt **nem aktív** és **nem aktiválhatja magát**. A példa-jelöltek
  (`aa_memory_chunks`) `ervenyes=false` — nem használhatók éles döntésben
  jóváhagyásig. A besorolandó esetek SOP-kérésként számolódnak.

### Jóváhagyás és kiadás
- Szabály-jelölt → emberi tartalmi jóváhagyás (a szabály `active`-ra állítása) →
  **sikeres eval szükséges** (a `PATCH /rules/{id}` aktiválás 409-et ad, ha az
  utolsó eval nem ment át) → verziózott, külön aktiválható kiadás
  (`aa_agent_releases`, `POST /releases/{id}/activate`, szintén eval-hez kötve).
- Konfliktusnál nincs csendes felülírás; az aktiválás jogosult emberhez kötött.

### Retrieve — `app/admin_agent/memory.py`
- Feladatonként legfeljebb 5–10 releváns elem: **csak AKTÍV szabály** és
  **érvényes, nem visszavont, jóváhagyott példa**. A holdout SOHA nem kerül a
  visszakeresésbe (`tanulasi_halmaz="holdout"` kizárva).
- **pgvector OPCIONÁLIS**: elérhetőségét futásidőben nézzük (`pg_extension`).
  Mivel az embedding itt JSONB (nem natív vektor), a keresés determinista
  pontos/szöveges fallbackre épül. A visszakeresés a hívó RBAC-ját örökli.
- Forrás törlése/visszavonása vagy jogosultságvesztés után az érintett memória
  `ervenyes=false`/`visszavont=true` — nem kerül vissza a modellnek.

## Értékelés (eval) — `app/admin_agent/evals.py`

- A **biztonsági/pénzügyi invariánsokat KÓDDAL** ellenőrizzük, nem a modellel.
- Beépített safety-esetek (magvetés idempotens, név szerint): R3 mindig tiltott,
  L0 árnyék tiltott, vészleállítás tiltott, modul-ki tiltott, mellékhatás-tiltás
  tiltott, R2 alapból jóváhagyás-köteles, R0 auto. Ezek a policy engine
  **regressziós őrei**.
- Egy eset a döntés pillanatában ismert bemenetből (`bemenet`) játssza vissza a
  policy-döntést, és összeveti az elvárttal. **Kritikus hiba**: ha az elvárt
  döntés BLOCKED, de a kapott nem az (biztonsági invariáns sérülése).
- `atment` = nincs kritikus hiba ÉS a megfelelési arány ≥ 95%. **Sikertelen eval
  nem aktiválhat** szabályt vagy kiadást.
- Holdout és tanulási adat nem keveredik: a holdout `aa_eval_cases`, amit a
  distill/retrieval nem használ.

## Mutatók

A definíciók a kódban és itt élnek. A mért minőségi mutatók (ember nélkül lezárt
arány, elfogadási arány, kritikus hibák, modellköltség) az Áttekintésen csak
akkor jelennek meg, ha van elég rögzített adat — addig **„Még nincs elég adat"**
(nem hamis nulla). Mért adatok hiányában nincs szintlépés; a jóváhagyás is emberi
beavatkozásnak számít az autonómia-arányban.
