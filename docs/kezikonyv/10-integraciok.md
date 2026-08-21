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

#### A naptáras fiók ne jelentkezzen ki

A hozzáférés magától megújul, és ezt **nem a lejáratkor**, hanem 10 perccel
előtte tesszük (`FRISSITESI_TARTALEK`): a szinkron percekig futhat, egy futás
közben lejáró token pedig fél munkával, 401-gyel állna meg.

Egy **sikertelen** megújítás nem dobja el a tárolt hozzáférést. A kettőt
megkülönböztetjük (`_vegleges_hiba`):

- `invalid_grant` / `invalid_client` → a refresh token maga halott, tényleg
  újra be kell jelentkezni;
- hálózati hiba, időtúllépés → magától elmúlik, a következő szinkron újra
  próbálja. Erre "csatlakoztasd újra a fiókot" üzenetet adni fölösleges
  riasztás, ami után valaki tényleg lecsatlakoztatja a működő kapcsolatot.

Minden megújítás nyomot hagy (`last_refresh_at`, `last_error`,
`last_error_at`), és ez a Beállítások oldalon is látszik. Enélkül a felület
"Összekötve" állapotot mutatott olyankor is, amikor a szinkron napok óta állt:
a tárolt token megléte nem bizonyítja, hogy él a kapcsolat.

> **AMIT A KÓDBÓL NEM LEHET MEGOLDANI.** Ha a Google Cloud projekt **„Testing"**
> állapotban van, a Google a refresh tokent **7 naponta** érvényteleníti -
> bármit csinálunk. Ez a leggyakoribb oka annak, hogy a naptáras fiók
> "kijelentkezik". A megoldás egyszeri beállítás: *Google Cloud Console → APIs
> & Services → OAuth consent screen → **Publish app*** ("In production"). A
> hibaüzenetünk ki is mondja, hogy ezt kell megnézni.
>
> A refresh token ezen kívül akkor szűnik meg, ha valaki visszavonja a
> hozzáférést (myaccount.google.com/permissions), vagy ha a fiók 6 hónapig nem
> használja - az utóbbi nálunk nem fordulhat elő, mert a szinkron percenként
> fut.

A levelek feladó CÍME alapból `GMAIL_SENDER`. Kivétel a megrendelői
**keretszerződés** és a hozzá tartozó **szerződésmódosítás**: ezek az admin
fiókból mennek (`MODOSITAS_SENDER`), és a levél aláírását is abból a fiókból
olvassuk ki (`users.settings.sendAs`), hogy a Gmailben beállított aláírás
legyen a hiteles forrás. A közös burok: `services/admin_level.py` - lásd
[06-papirozas.md](06-papirozas.md).

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

### Az import nem írja felül a helyi munkát

Újrafuttatáskor az import **csak az újakat és a valódi változásokat** hozza át.
Amit a HYPE OS-ben módosítottak az előző import óta, azt érintetlenül hagyja -
enélkül egy ismételt import visszaírná a Notion elavult adatát arra, amit itt
már befejeztek (pl. egy megírt és kiküldött TIG-re vagy egy lezárt utókövetésre).

Hogyan dönti el (`notion_import/engine.py`): a `notion_import_map` rekordonként
eltárolja, **mit írt bele legutóbb az import** (`imported_fields`). Ha a mostani
adatbázis-érték ezzel egyezik, azóta senki nem nyúlt hozzá → a Notion frissítése
felülírhatja. Ha eltér → helyben dolgoztak rajta → kimarad. A döntés
**mezőnkénti**, nem rekord-szintű: egy helyben átírt összeg nem akadályozza meg,
hogy a mellette lévő, érintetlen mező frissüljön.

Két részlet, ami miatt ez a gyakorlatban is működik:

- Az összehasonlítás **normalizált** (`_ertek_kulcs`): `Decimal("1000.00")` és
  `1000` ugyanaz. Enélkül a típuskülönbség minden mezőt tévesen "módosítottnak"
  mutatna, és az import soha többé nem frissítene semmit.
- **Baseline nélküli** sornál (a védelem bevezetése előtt importált rekord) a
  kitöltött mezőt védettnek tekintjük, az üreset kitöltjük - a legóvatosabb
  viselkedés, mert üres mezőből nem veszhet el munka.

A napló mezőnként számol be róla: *"12 mező védve 5 rekordon (helyben
módosították)"*. Vészkijáratként `NOTION_IMPORT_OVERWRITE=1` mellett az import a
régi módon fut, és mindent felülír - ez nem alapértelmezés, csak akkor kell, ha
egy elrontott helyi szerkesztést szándékosan a Notion állapotára állítanánk vissza.

Indítás a böngészőből: `/api/v1/admin/notion-import` (admin). Ez azért kellett,
mert a `railway ssh` kapcsolat rendszeresen megszakad, mielőtt a - Notion
rate-limitje miatt akár órákig tartó - import lefutna, és a megszakadt SSH-val
együtt a Python-processz is meghal. A végpont ehelyett a **futó backend
processzében**, háttérszálon indítja az importot, ami a HTTP-válasz után is tovább
fut. Redeploy/újraindítás viszont elviszi (memóriabeli állapot).

### A mezőnevek táblánként eltérnek

Ugyanaz az adat a HYPE Notion tábláiban más-más oszlopnéven szerepel. A
megrendelői **Keretszerződés** tábla például `Képviselő` és
`Nyilvántartásiszám` néven vezeti azt, amit az alvállalkozói oldal
`Vállalkozás képviselője` / `Vállalkozás nyilvántartási szám` néven - az import
pedig sokáig csak az utóbbit kereste, tehát **egyik sem jött át** (23, illetve
21 cégnél volt kitöltve). Épp ez a kettő kell a keretszerződés generálásához
(`{{kepvis}}`, `{{nyilvszam}}`).

Ezért használ az import `_mezo()` / `_szoveg_mezo()` segédfüggvényt, ami TÖBB
lehetséges nevet próbál sorban, és az első nem üreset veszi. Új tábla
bekötésekor érdemes előbb kiíratni a tényleges mezőneveket
(`extract_properties` egy sorra), és nem feltételezni, hogy egyeznek egy másik
tábláéval - a hiányzó mező ugyanis némán üres marad, nem hibázik.

### Kétirányú relation: a hiányzó kapcsolat némán marad üres

A Notionban a keretszerződés és a projektkód **két irányból** is össze van
kötve: a projektkód `Keretszerződés` mezőjéből és a keretszerződés
`HYPE ADMIN projektkódok` mezőjéből. Az import sokáig csak az elsőt használta -
csakhogy a projektkódok importja akkor fut, amikor a keretszerződések még nem
feltétlenül vannak bent, egy feloldatlan hivatkozás pedig **nem hiba**:
`resolve_relation_id` csendben `None`-t ad (ez másutt helyes viselkedés, mert
az 5 éves adatban rengeteg a törölt vagy soha nem importált célpont). Így a
projektkódok `contract_id`-ja tömegesen üresen maradt, és utólag semmi nem
hozta helyre - a keretszerződések importja nem nyúlt a projektkódokhoz, a
projektkódoké meg nem futott újra. A felületen ez úgy látszott, hogy a 28
keretszerződés bejött, de **egyikhez sem tartozott projekt**.

Ezért kötünk a **keret felől is** (`kosd_a_keret_projektkodjait`), a
keretszerződések importja után - ekkorra már mindkét oldal bent van.
Két szabály tartja biztonságosan ismételhetőnek:

- csak az **üres** `contract_id`-t tölti ki - amit a projektkód saját importja
  vagy egy ember már beállított, ahhoz nem nyúl;
- a bekötések száma a napló saját mezőjébe megy (`bekotott_kapcsolatok`), nem a
  hibák közé. Egy ismételt futásnál épp az a jó jel, ha itt már **nulla** áll.

Általános tanulság új tábla bekötéséhez: ha egy relation mindkét oldalon meg
van adva, azt az oldalt használd, amelyik a **később importált** entitásnál
van - vagy kösd be mindkét irányból, ahogy itt.

### Törölt rekord: a leképezést is vinni kell

A `notion_import_map` generikus tábla (Notion oldal → entitástípus + id),
**idegen kulcs nélkül** - tehát a rekord törlésekor nincs semmi, ami magától
elvinné a hozzá tartozó sort. Az árván maradt leképezés viszont **véglegesen
kizárta** azt a Notion-oldalt az importból: a motor a leképezésből azt hitte,
hogy a rekord megvan, és frissíteni próbálta - de nem volt mit, amitől minden
további futás ugyanazzal a rejtélyes `AttributeError`-ral hagyta ki a sort.

Két oldalról van megoldva:

- **törléskor takarítunk** (`services/notion_mapping.py`) - a generikus CRUD
  törlés és a megrendelői keretszerződés törlése is elviszi a leképezést;
- **importkor öngyógyítunk** - ha a leképezés mégis árva (régi törlésekből),
  a motor újrahasznosítja: eldobja és a rekordot újra létrehozza
  (`notion_import/engine.upsert`).

Ez a gyakorlatban azt jelenti, hogy egy egyszer törölt sor **újraimportálható**
- korábban nem volt az.

### Egy katalógus-elem, ami nem hív Notiont

A *"Megrendelői papírok"* lépés (`importers_megrendeloi.py`) kivétel: a MÁR
importált projektkódokból és csatolmányokból dolgozik, nem a Notion API-ból.
Ezért kell a `ProjectCode` **után** futnia - és ezért futtatható újra
önmagában, anélkül hogy az egész projektkód-táblát újra le kellene kérni.
Ugyanaz a kód fut benne, mint a `c9e4a71b2f08` adatmigrációban, tehát a kettő
nem csúszhat el (lásd [06-papirozas.md](06-papirozas.md)).

### Egy lépés egyetlen mezőért: a projektkódok neve

A *"Projektkódok: csak a projekt neve"* (`importers_projektnevek.py`) a Notion
*HYPE ADMIN projektkódok* táblájából egyetlen mezőt hoz át: a **PROJECT NÉV**-et
a projektkód *Projekt neve* mezőjébe. Fájlokat nem másol, más mezőhöz nem nyúl,
ezért másodpercek alatt lefut - a teljes projektkód-import ezzel szemben 780
lapot és a csatolmányaikat is végigjárja.

A kódokat kis/nagybetűtől és szóköztől függetlenül párosítja (ugyanaz a szabály,
mint a projektkód-kötésnél), a már kitöltött nevet pedig nem írja felül: amit itt
gépeltek be, az erősebb. A napló kiírja, hányat töltött ki, hányat hagyott
érintetlenül, és melyik kód nincs meg egyáltalán a rendszerben (azt előbb a
*Projektkódok* lépés hozza be).

### Ami már megvan: a meglévő rekord örökbefogadása

Az import a **Notion-lap azonosítója** alapján tudja, melyik rekordot frissítse
(`NotionImportMap`). Csakhogy egy rekord nem csak importból születhet: felvehetik
kézzel, vagy létrehozhatja egy másik import mellékesen (pl. egy hivatkozott
projektkód). Ilyenkor nincs leképezés, az import tehát LÉTREHOZNI próbálja - és
egyedi mezőn (a projektkód az) ez UNIQUE ütközéssel elszáll. A savepoint miatt
csak az az egy sor esik ki, de **minden futásnál újra**: kívülről ez úgy néz ki,
hogy a Notionban kitöltött mező (pl. a *PROJECT NÉV*) "sosem jön át", hiába
frissít az ember újra meg újra.

Ezért az importer megadhat egy **természetes kulcsot** (`termeszetes_kulcs`,
`upsert`/`safe_upsert`): ha nincs leképezés, de a kulcs alapján megvan a rekord,
felvesszük hozzá a leképezést, és onnantól frissítésként fut rá. A baseline
szándékosan üres marad, tehát a már kitöltött mezőket védettnek tekintjük (azokon
lehet helyi munka), az üreseket viszont kitölti a Notion - pontosan azt hozza át,
ami eddig hiányzott.

A projektkódoknál ez a `projektkod` mező. Ott is helyes, mert a Notionban a kód
egyedi - ha egyszer mégis két lap kapná ugyanazt, azok ugyanarra a rekordra
írnának, ami legalább látszik (a régi viselkedés az volt, hogy mindkettő némán
kiesett).

### A külsős TIG-ek összevetése a Notionnal

A Notion *"Külsős"* táblájában soronként egy (ember, forgatás) pár áll, rajta az
eseti szerződés és a TIG állapota. Az import (`importers_kulsos.py`) csak azokat
veszi át, ahol a papír a Notion szerint elkészült - de a rendszer csak akkor
tudja "megvan"-nak látni, ha a sort ide is tudja kötni. Két dolog rontotta el
ezt, és mindkettő ugyanúgy nézett ki a felületen: "hiányzik a TIG", pedig a
Notionban ott van, feltöltve.

1. **Nem volt meg a forgatás.** Ha a "Forgatás" relation üres (vagy a
   hivatkozott sor nem jött át), a papír kimaradt. Mostantól a PROJEKTKÓD is
   elvezet hozzá: a relation vagy a szöveges kód alapján megkeressük a
   projektkódot, és ha alatta egyetlen forgatás van, az a papíré; ha több, a
   "Forgatás dátuma" dönt. Ha az sem választja szét őket, inkább nem tippelünk
   - a rossz projektre könyvelt papír rosszabb, mint a hiányzó.
2. **Nem volt TÉTELE az importált TIG-nek.** A "hiányzik-e még TIG" kérdésre a
   tételek válaszolnak, ha az illetőt MÁS számlázza (lásd
   `_csoport_fedve`) - tétel nélkül a rendszer újra kérte a papírt. Az import
   mostantól minden futásnál pótolja a hiányzó tételt, nem csak az újonnan
   létrehozott TIG-eknél.

Az import naplója külön kiírja, hány KÉSZ TIG-et látott a Notionban és ebből
mennyit nem sikerült ide kötni (`ImportResult.notion_kesz_tig` /
`hianyzo_kesz_tig`) - a kettő különbsége pontosan az, ami miatt a felület még
mindig hiányt mutathat, a hozzá tartozó sorok pedig a hibalistában
azonosíthatók.

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

### A projektkód TIG- és SZÁMLA-részének átvétele

A Notion "HYPE ADMIN projektkódok" táblájában a szerződés alatt ott a TIG-rész
(állapot, aláírt papír), az alatt pedig a számla-rész (mikor kellett volna
fizetni, mikor fizették ki, és maga a számla). Ezt lapos mezőkbe már az import
áthozta; valódi rekorddá a `services/megrendeloi_papir_atvetel.py` alakítja -
az import után és migrációból is futtatható, IDEMPOTENSEN.

**TIG:** ha az aláírt példány fel van töltve, a papír kész ("Van már papír", az
aláírt fájllal). Ha a Notion szerint kiment, de aláírt példány nincs, akkor
"Kiküldve" - a felületen ez az **aláírásra vár** állapot, mert ott valódi teendő
van: vissza kell kérni az aláírt papírt. Ugyanez a különbségtétel a
szerződésnél is.

**Számla:** a fizetési határidő, az utalás dátuma, a bevétel formája és a
feltöltött számla a **bevétel-sorra** kerül. Óvatosan gyártunk sort: a bevételek
a Notion "Bevételek" táblájából jönnek, ezért ha már van bevétel-sor, csak a
HIÁNYZÓ mezőit töltjük ki - egy második sor megduplázná a bevételt. Új sort csak
akkor nyitunk, ha egyáltalán nincs bevétel, és a projektkódon van összeg. A már
kitöltött értékeket sosem írjuk felül.
