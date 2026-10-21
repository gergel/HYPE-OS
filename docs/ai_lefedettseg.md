# AI Assistant - műveleti lefedettségi tábla

*Generálva a futó alkalmazás végpont-katalógusából (567 végpont). Frissítés:
`python -c "from app.services import ai_eszkozok; ..."` - a tábla forrása a
`services/ai_eszkozok._api_katalogus_epites()`.*

## Hogyan éri el az asszisztens a műveleteket?

- Az asszisztens a rendszer SAJÁT REST-végpontjait hívja belső eszközként
  (`api_lekeres` olvasásra, `api_muvelet` írásra), a bejelentkezett felhasználó
  tokenjével - tehát pontosan ugyanaz a szerveroldali üzleti művelet, jogosultság-
  ellenőrzés (page_permissions, fül-jogok, sor-szűrők), értesítés és visszavonás-
  pillanatkép fut, mint a normál felületről.
- A végpontok listáját az `api_katalogus` eszköz adja a modellnek - minden modul
  minden művelete elérhető, kézi felsorolás nélkül; egy új végpont automatikusan
  bekerül.
- Kivételek (nem hívhatók): `/api/v1/auth`, `/api/v1/ai-assistant` (önhívás),
  `/api/v1/realtime`.
- MEGERŐSÍTENDŐ műveletek (jóváhagyás-kártya a chatben, a végrehajtás a tárolt
  kéréssel): minden DELETE, továbbá a pénzügyi felvezetés/kifizetés/rögzítés,
  reset, tömeges törlés és hozzáférés-módosítás útvonalai (lásd
  `ai_eszkozok.MEGEROSITENDO_RESZLETEK`).
- Minden írás naplózott (`ai_muveletek`: kezdeményező, kérés, válasz, állapot)
  és idempotencia-kulcsos - az ismételt hívás nem fut le kétszer.
- Fájl-műveletek: `szamla_feltoltes` (közös számla-érkeztető folyamat, Excel-
  részletező párosítással), `dokumentum_csatolas` (normál csatolmány-folyamat).
- Csak-olvasó gyorseszközök: `globalis_kereses` (minden fő modul),
  `query_entity`/`aggregate_entity` (szűrt lekérdezés/összesítés).

## Modulonkénti végpont-lefedettség

| Modul (útvonal-előtag) | Olvasó (GET) | Író | Ebből megerősítendő | Példa író műveletek |
|---|---|---|---|---|
| admin | 4 | 4 | 0 | POST /api/v1/admin/calendar-sync; POST /api/v1/admin/calendar-sync/oauth/disconnect |
| agi-todo | 2 | 3 | 1 | POST /api/v1/agi-todo; DELETE /api/v1/agi-todo/{item_id} |
| alvallalkozoi-szerzodesek | 7 | 17 | 4 | DELETE /api/v1/alvallalkozoi-szerzodesek/projektkodok/{project_code_id}/{szamlazo_kulcs}; DELETE /api/v1/alvallalkozoi-szerzodesek/projektkodok/{project_code_id}/{szamlazo_kulcs}/alairt-fajl |
| arajanlat-tetelek | 2 | 3 | 1 | POST /api/v1/arajanlat-tetelek; DELETE /api/v1/arajanlat-tetelek/{item_id} |
| arajanlatok | 2 | 3 | 1 | POST /api/v1/arajanlatok; DELETE /api/v1/arajanlatok/{item_id} |
| assignments | 1 | 3 | 1 | POST /api/v1/assignments; DELETE /api/v1/assignments/{assignment_id} |
| autok | 3 | 9 | 3 | POST /api/v1/autok; DELETE /api/v1/autok/kiadasok/{kiadas_id} |
| automation | 0 | 1 | 0 | POST /api/v1/automation/generate-document |
| bejovo-szamlak | 4 | 11 | 4 | POST /api/v1/bejovo-szamlak/email-lehuzas; POST /api/v1/bejovo-szamlak/feltoltes |
| belsos-idoszakok | 1 | 4 | 1 | DELETE /api/v1/belsos-idoszakok/idoszak/{idoszak_id}; PATCH /api/v1/belsos-idoszakok/idoszak/{idoszak_id} |
| belsos-tig | 7 | 13 | 4 | DELETE /api/v1/belsos-tig/tetelek/{tetel_id}; PATCH /api/v1/belsos-tig/tetelek/{tetel_id} |
| callsheets | 2 | 3 | 1 | POST /api/v1/callsheets; DELETE /api/v1/callsheets/{item_id} |
| campaigns | 2 | 3 | 1 | POST /api/v1/campaigns; DELETE /api/v1/campaigns/{item_id} |
| clients | 2 | 3 | 1 | POST /api/v1/clients; DELETE /api/v1/clients/{item_id} |
| contacts | 2 | 3 | 1 | POST /api/v1/contacts; DELETE /api/v1/contacts/{item_id} |
| contracts | 5 | 15 | 4 | POST /api/v1/contracts; DELETE /api/v1/contracts/idoszakok/{idoszak_id} |
| crew | 7 | 6 | 2 | POST /api/v1/crew; POST /api/v1/crew/{employee_id}/munkaszerzodesek |
| csatolmanyok | 1 | 5 | 4 | DELETE /api/v1/csatolmanyok/{attachment_id:int}; PUT /api/v1/csatolmanyok/{attachment_id:int}/fizetesi-allapot |
| dashboard | 5 | 1 | 0 | PUT /api/v1/dashboard/config/me |
| deliverables | 13 | 18 | 1 | POST /api/v1/deliverables; PUT /api/v1/deliverables/allapot-beallitasok |
| detail-tabs | 3 | 2 | 0 | PUT /api/v1/detail-tabs/{entity_type}; PUT /api/v1/detail-tabs/{entity_type}/section-order |
| dispo-responsibles | 2 | 2 | 0 | PUT /api/v1/dispo-responsibles; PUT /api/v1/dispo-responsibles/masolat |
| diszpo-tabla | 5 | 10 | 2 | POST /api/v1/diszpo-tabla/sheet-sync; PUT /api/v1/diszpo-tabla/{munkalap_id}/cella |
| entity-fields | 2 | 4 | 1 | POST /api/v1/entity-fields/{entity_type}/custom; DELETE /api/v1/entity-fields/{entity_type}/custom/{field_key} |
| equipment | 3 | 3 | 1 | POST /api/v1/equipment; DELETE /api/v1/equipment/{item_id} |
| eseti-szerzodesek | 1 | 1 | 1 | DELETE /api/v1/eseti-szerzodesek/{contract_id} |
| eszkozkivitelek | 2 | 4 | 1 | POST /api/v1/eszkozkivitelek/generalas; DELETE /api/v1/eszkozkivitelek/{kivitel_id} |
| expenses | 2 | 4 | 1 | POST /api/v1/expenses; POST /api/v1/expenses/kiolvasas |
| feedback | 2 | 3 | 1 | POST /api/v1/feedback; DELETE /api/v1/feedback/{item_id} |
| field-visibility | 4 | 1 | 0 | PUT /api/v1/field-visibility/{employee_id}/{entity_type} |
| finance | 6 | 6 | 4 | DELETE /api/v1/finance/kiadasok-bevetelek/mind; DELETE /api/v1/finance/kp-forgalom/mind |
| flora | 3 | 4 | 1 | POST /api/v1/flora; POST /api/v1/flora/{flora_id}/comments |
| folders | 2 | 3 | 1 | POST /api/v1/folders; DELETE /api/v1/folders/{item_id} |
| hype-todo | 3 | 4 | 1 | POST /api/v1/hype-todo; DELETE /api/v1/hype-todo/{item_id} |
| kotelezettsegek | 2 | 5 | 1 | POST /api/v1/kotelezettsegek; PUT /api/v1/kotelezettsegek/idoszakok/{idoszak_id} |
| kp-forgalom | 2 | 3 | 1 | POST /api/v1/kp-forgalom; DELETE /api/v1/kp-forgalom/{item_id} |
| krumpello | 9 | 16 | 5 | POST /api/v1/krumpello/dolgozok; PATCH /api/v1/krumpello/dolgozok/{dolgozo_id} |
| kulsos-tigek | 2 | 0 | 0 | - |
| media | 2 | 3 | 1 | POST /api/v1/media; DELETE /api/v1/media/{item_id} |
| megrendeloi-keretszerzodesek | 3 | 11 | 2 | POST /api/v1/megrendeloi-keretszerzodesek; DELETE /api/v1/megrendeloi-keretszerzodesek/{keret_id} |
| megrendeloi-kontaktok | 1 | 0 | 0 | - |
| megrendeloi-papirok | 4 | 11 | 2 | POST /api/v1/megrendeloi-papirok/keret-kotes/{project_code_id}; POST /api/v1/megrendeloi-papirok/szamla/{project_code_id}/kifizetve |
| notifications | 2 | 2 | 0 | POST /api/v1/notifications/read-all; POST /api/v1/notifications/{notification_id}/read |
| payments | 2 | 3 | 1 | POST /api/v1/payments; DELETE /api/v1/payments/{item_id} |
| portal | 2 | 3 | 1 | POST /api/v1/portal; DELETE /api/v1/portal/{item_id} |
| portal-admin | 5 | 31 | 8 | POST /api/v1/portal-admin; DELETE /api/v1/portal-admin/folders/{folder_id} |
| project-codes | 5 | 4 | 1 | POST /api/v1/project-codes; DELETE /api/v1/project-codes/{item_id} |
| projects | 3 | 10 | 1 | POST /api/v1/projects; DELETE /api/v1/projects/{item_id} |
| projekt-szamlazok | 2 | 3 | 0 | PUT /api/v1/projekt-szamlazok/{project_id}/{employee_id}; PUT /api/v1/projekt-szamlazok/{project_id}/{employee_id}/dij |
| public | 9 | 14 | 0 | POST /api/v1/public/eszkozkivitel/belepes; PUT /api/v1/public/eszkozkivitel/{kod}/kulso |
| rates | 2 | 3 | 1 | POST /api/v1/rates; DELETE /api/v1/rates/{item_id} |
| revenues | 2 | 3 | 1 | POST /api/v1/revenues; DELETE /api/v1/revenues/{item_id} |
| search | 1 | 0 | 0 | - |
| stocktake | 3 | 4 | 1 | POST /api/v1/stocktake/sessions; DELETE /api/v1/stocktake/sessions/{session_id} |
| tasks | 2 | 3 | 1 | POST /api/v1/tasks; DELETE /api/v1/tasks/{item_id} |
| teljesitesi-igazolasok | 8 | 22 | 6 | DELETE /api/v1/teljesitesi-igazolasok/projektkodok/{project_code_id}/{szamlazo_kulcs}; POST /api/v1/teljesitesi-igazolasok/projektkodok/{project_code_id}/{szamlazo_kulcs}/allapot |
| timeline | 1 | 1 | 0 | POST /api/v1/timeline |
| timesheets | 2 | 3 | 1 | POST /api/v1/timesheets; DELETE /api/v1/timesheets/{item_id} |
| user-access | 3 | 3 | 3 | DELETE /api/v1/user-access/others; DELETE /api/v1/user-access/{employee_id} |
| utalasok | 2 | 8 | 3 | POST /api/v1/utalasok; PATCH /api/v1/utalasok/tetel/{tetel_id} |
| utokovetes | 3 | 0 | 0 | - |
| vagoi-jatek | 3 | 4 | 1 | PUT /api/v1/vagoi-jatek/munkanap; PUT /api/v1/vagoi-jatek/nyeremeny |
| vagoi-visszajelzesek | 1 | 2 | 0 | PUT /api/v1/vagoi-visszajelzesek/{feedback_id}/allapot; POST /api/v1/vagoi-visszajelzesek/{feedback_id}/diszpo-valasz |
| vallalkozasok | 3 | 8 | 3 | POST /api/v1/vallalkozasok; POST /api/v1/vallalkozasok/ember/{employee_id} |
| visszavonas | 1 | 1 | 0 | POST /api/v1/visszavonas/torles/{pillanatkep_id} |

## Ismert hiányok / korlátok

- A megerősítés-kapu útvonal-minta alapú (MEGEROSITENDO_RESZLETEK) - új,
  kényes végpontnál a mintát bővíteni kell.
- A modell a body-mezőket részben a katalógusból, részben a rendszerüzenet
  receptjeiből ismeri; egzotikus végpontnál előfordulhat első körben 400-as
  válasz, amiből a modell javít (a hibák a naplóban látszanak).
- A multipart (fájlos) végpontok közül a számla-feltöltés és a csatolmány-
  feltöltés dedikált eszköz; egyéb fájlos végpontokhoz (pl. diszpó-melléklet
  kiküldése) a dokumentum_csatolas a kerülőút.
- Oldal-kontextus átadása jelenleg query-paramokkal működik
  (`/ai-assistant?entity=...&rekord=...&cim=...&honnan=...`) - az egyes
  oldalakra kitett "Kérdezd az asszisztenst" gomb még nincs bekötve.
