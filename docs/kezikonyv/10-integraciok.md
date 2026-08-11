# 10 - Külső integrációk

Közös alapelv az egészre: **hiányzó hitelesítés nem hiba.** Ha egy szolgáltatás
kulcsa nincs beállítva, az app elindul, és csak az adott képesség jelez vissza
egyértelműen (vagy csendben kihagyja a futást, ahol az a helyes). Fejlesztéshez
egyetlen külső kulcs sem kötelező.

## Google

Három, egymástól **független** Google-hitelesítés van a rendszerben. Ez nem
véletlen: a naptár más fióknál van, mint a levelezés.

| Mire | Env előtag | Fájl |
|---|---|---|
| Gmail (küldés) | `GMAIL_*` | `services/google_email.py` |
| Docs/Drive (sablon, PDF) | `GOOGLE_DOCS_OAUTH_TOKEN_JSON`, `GDOC_*`, `DRIVE_*` | `services/gdoc_template.py` |
| Calendar (szinkron) | `GOOGLE_CALENDAR_*` | `services/google_calendar.py` |

Mindegyik kétféle módon hitelesíthető: **OAuth token JSON** vagy **service
account JSON + opcionális impersonation**. A naptárnál van egy harmadik, ajánlott
út is: a "csak jelentkezz be egyszer" folyamat (`services/google_oauth.py`), ami a
refresh tokent **adatbázisban** tárolja, így adminnak nem kell JSON-t másolgatnia
env változóba. Ha nincs külön naptár-OAuth-kliens megadva, a Gmail OAuth kliensre
esik vissza (ugyanabban a Google Cloud projektben lévő kliens több scope-ra is
használható).

### Dokumentum-generálás

`services/gdoc_template.py`: Docs sablon másolása → placeholder csere → PDF export.
Ugyanez a motor hajtja a diszpót, a szerződéseket és a TIG-eket, csak más sablon-ID
és mezőkészlet.

Egy fontos üzemeltetési részlet: a backend Railway-en fut, ahol a **fájlrendszer
efemer**, ezért a PDF nem lemezre kerül, hanem memóriában (bytes) adódik vissza, és
onnan megy egyenesen a Gmail csatolmányba.

Sablonokra és célmappákra külön env változók vannak (külsős TIG, belsős TIG,
alvállalkozói szerződés, keretszerződés, diszpó), több szintű visszaeséssel:
saját mappa → generikus kimeneti mappa → Drive gyökér. Lásd
[11-uzemeltetes.md](11-uzemeltetes.md).

A rendszer elfogadja a különálló belsős-TIG program env-neveit is
(`GOOGLE_DRIVE_TEMPLATE_ID`, `NOTION_FILE_FOLDER_ID`, `TIGTOKEN_JSON`) - hogy a
HYPE OS ugyanazzal a Railway-beállítással működjön, amivel az a program eddig
futott, és ne kelljen ugyanazt a sablont új néven még egyszer felvenni.

## Notion (egyszeri import, nem élő szinkron)

**Nincs élő Notion API-hívás a működésben.** A Notion csak egyszeri, idempotens
adatáthozatalra szolgál a cutover előtt: `app/notion_import/`, katalógus +
`run_all.py`.

Indítás a böngészőből: `/api/v1/admin/notion-import` (admin). Ez azért kellett,
mert a `railway ssh` kapcsolat rendszeresen megszakad, mielőtt a - Notion
rate-limitje miatt akár órákig tartó - import lefutna, és a megszakadt SSH-val
együtt a Python-processz is meghal. A végpont ehelyett a **futó backend
processzében**, háttérszálon indítja az importot, ami a HTTP-válasz után is tovább
fut. Redeploy/újraindítás viszont elviszi (memóriabeli állapot).

Külön ügy a portál Notion-szinkronja (`PORTAL_NOTION_*`,
`services/portal_notion.py`) - az **másik** adatbázis, lásd
[09-media-portal.md](09-media-portal.md).

## Cloudflare R2 (S3-kompatibilis)

`R2_*` env változók. Két használat:

- általános dokumentum-tárolás (`services/document_storage.py`) - csatolmányok,
  feltöltött papírok, számlaképek;
- a Média Portál médiája (`services/portal_storage.py`), `media-portal/` kulcs-
  előtag alatt, hogy elkülönüljön.

Hiányzó R2-nél `R2NotConfiguredError` jön, amit a route-ok érthető hibává
fordítanak.

## Barion és Számlázz.hu

Csak a Média Portál fizetéséhez - részletek: [09-media-portal.md](09-media-portal.md).
`services/portal_barion.py`, `services/portal_szamlazz.py`.
Env: `BARION_POS_KEY`, `BARION_ENV` (`test`|`prod`), `BARION_PAYEE`,
`SZAMLAZZ_AGENT_KEY`, frontend oldalon `NEXT_PUBLIC_BARION_PIXEL_ID`.

## AI Assistant (Google Gemini)

`/api/v1/ai-assistant/ask`, oldal: `/ai-assistant`.
`services/ai_assistant.py`, frontend `components/AiAssistantChat.tsx`.

Gemini **function calling** a végleges Postgres felett. A lényeges rész: az
adathozzáférés a **bejelentkezett felhasználó saját jogosultsága szerint szűrve**
történik (`page_permissions` + `field_visibility`) - az asszisztens nem lát többet,
mint az, aki kérdezi.

Env: `GEMINI_API_KEY`, `GEMINI_MODEL` (alapból `gemini-2.5-flash`; belső, kis
léptékű eszközről van szó, ahol a gyors válasz többet ér a nagyobb modellnél -
`gemini-2.5-pro`-ra átállítható).

## Háttérfeladatok (Celery + Redis)

`app/workers/`:

| Fájl | Mit csinál |
|---|---|
| `calendar_tasks.py` | Percenkénti naptár-szinkron (Celery Beat) |
| `dispo_tasks.py` | Forgatás után 12 órával utókövető email |
| `portal_tasks.py` | Videó-transzkódolás a portálhoz |

A `docker-compose.yml` a `media-worker` szolgáltatásban indít Celery workert a
portál-feladatokhoz. **Nem minden ismétlődő művelet ütemezett**: a visszatérő
kötelezettségek "utolérése" például igény szerint, a lista lekérésekor fut le,
idempotensen (lásd [07-penzugyek.md](07-penzugyek.md)).
