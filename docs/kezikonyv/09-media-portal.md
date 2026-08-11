# 09 - Média Portál (publikus ügyfélfelület)

Ez az **egyetlen** része a rendszernek, amit külső ügyfél lát, bejelentkezés
nélkül. Ezért itt más szabályok érvényesek, mint a HYPE OS többi oldalán.

| Réteg | Hol |
|---|---|
| Publikus oldal | `frontend/app/p/[slug]/` (`portal-client.tsx`) |
| Publikus API | `/api/v1/public/portal`, `/api/v1/public/...` (`routes/portal_public.py`) |
| Admin felület | `/media-portal` (`frontend/app/(app)/media-portal/`) |
| Admin API | `/api/v1/portal-admin` (`routes/portal_admin.py`) |
| Régi portál/fizetés váz | `/api/v1/portal`, `/api/v1/payments` (`routes/portal.py`) |
| Kliens API | `frontend/lib/portalApi.ts` (publikus), `portalAdminApi.ts` (belső) |

A modul a különálló client-portál projekt (Hype-repo-main) portolt logikája, két
lényegi eltéréssel: **nincs külön admin-tábla és admin-JWT** (a HYPE OS
Employee-autentikációt használja, `/media-portal` oldaljogosultsággal), és **egy
Portal mindig egy meglévő Projecthez van kötve** (1:1) - a cím, ügyfélnév, dátum
a Project mezőire esik vissza, hacsak az admin felül nem írja
(`services/portal_resolve.py`).

## Fontos: a publikus kliens sosem küld Authorization headert

A `lib/portalApi.ts` szándékosan **külön fájl** a `lib/api.ts`-től. Az utóbbi
cookie-ból/localStorage-ból olvasott Bearer tokennel hitelesít (HYPE OS
alkalmazottaknak); a portál kliense soha nem küld tokent, mert a valódi ügyfelek
nem HYPE OS felhasználók. Ezt a szétválasztást ne olvaszd össze.

## Hozzáférés a portálhoz

Három út vezet be:

1. **Nyílt link** - `/p/{slug}`.
2. **Jelszó** - ha a portál védett, jelszókapu jön (`PasswordGate`), az
   `unlock` végpont rövid életű tokent ad, amit a kliens `sessionStorage`-ban
   tárol (`hype_unlock_{slug}`).
3. **Megosztó link** - `?share={token}`, saját végponton (`/share/{token}`).

## Lejárat és fizetés

A portálnak lejárati ideje van (`expires_at`). Lejárat után a tartalom nem
érhető el, és a `payment_mode` dönti el, mi történik:

- `contact` → az ügyfél a megadott kapcsolati e-mailt látja (alapértelmezés,
  ha a fizetési ablak bezárult).
- `paid` → az ügyfél maga hosszabbíthat.

Csomagok (`routes/portal_public.py`):

| Kód | Időtartam | Bruttó |
|---|---|---|
| `1month` | 30 nap | 6 000 Ft |
| `180days` | 180 nap | 30 000 Ft |
| `1year` | 365 nap | 50 000 Ft |

### A fizetés útja

1. Az ügyfél megadja a **számlázási adatait** az űrlapon (magánszemély vagy cég;
   cégnél adószám is) - ezek a `Payment` sorba kerülnek.
2. `POST /{slug}/pay` → `services/portal_barion.py` elindít egy azonnali
   (Immediate), HUF-os Barion fizetést, és visszaadja a `gateway_url`-t.
3. A Barion **callback**-je (`barion_callback`) zárja le a fizetést: meghosszabbítja
   a portált, és `services/portal_szamlazz.py` kiállítja a számlát a Számlázz.hu
   Számla Agenttel.
4. Az ügyfél visszairányítása `?paid=1&pkg=&amt=&pid=` paraméterekkel érkezik -
   ebből megy el a Barion Pixel `purchase` eseménye, majd a kliens **kitörli a
   paramétereket az URL-ből**, hogy egy oldalfrissítés ne küldje el újra.

Ami hiányzó beállítás mellett történik - és ez szándékos:

- **Barion kulcs nélkül** a portál átadó funkciója (videó/kép) teljes értékűen
  megy, csak fizetni nem lehet.
- **Számlázz.hu Agent kulcs nélkül** a fizetés érvényes marad, csak számla nem
  készül automatikusan - a pénz megjött, a számlát kézzel kell kiállítani. Ez
  nem hiba, hanem visszajelzett állapot.
- **Barion Pixel ID nélkül** nem töltődik be semmilyen követő szkript.

`BARION_ENV=test|prod` váltja a Barion API-t teszt és éles között.

## Követés és adatvédelem

Ez a rész jogi következményekkel jár, ezért külön figyelmet érdemel:

- A **Barion Pixel** (`components/media-portal/BarionPixel.tsx`) kizárólag a
  publikus portálon fut, **nem** a gyökér layoutban. A belső HYPE OS oldalak a
  saját munkatársainké - ott nincs mit követni, és nem is töltünk be külső
  szkriptet minden admin oldalra.
- A marketing célú adatküldés csak **süti-hozzájárulás után** indul
  (`components/media-portal/CookieConsent.tsx`, események:
  `frontend/lib/barionPixel.ts`).
- Az **adatkezelési tájékoztató** (`frontend/app/adatvedelem/page.tsx`) szintén a
  bejelentkezésen kívül él, mert a fizetési űrlapról és a süti-sávról is ide
  hivatkozunk. Adatkezelő: Hype Productions Kft.; adatfeldolgozók: Barion Payment
  Zrt., KBOSS.hu (Számlázz.hu).

## Média feltöltés és feldolgozás

- **Tárolás**: Cloudflare R2, S3-kompatibilis módon (`services/portal_storage.py`).
  A portál fájljai `media-portal/` kulcs-előtag alatt vannak, hogy elkülönüljenek a
  bucket egyéb tartalmától (pl. diszpó PDF-ek).
- **Videó-feldolgozás**: FFmpeg/ffprobe (`services/portal_transcode.py`) - MP4 és
  HLS változat, méret/hossz/felbontás kiolvasása, thumbnail. Háttérben fut:
  `workers/portal_tasks.py` (`process_video_task`).
- **Mappák, sorrend, borítókép**: `routes/portal_admin.py` - a képek átméretezése
  Pillow-val, a slug generálása `slugify`-jal.
- **Letöltés**: a publikus letöltő végpontok aláírt URL-t adnak vissza
  (`/public/portal-videos/{id}/download`, `/public/portal-images/{id}/download`).
- Opcionális **Notion-szinkron** a portál-projektekhez:
  `services/portal_notion.py`, külön Notion adatbázissal (`PORTAL_NOTION_*`) -
  ez **nem** ugyanaz, mint a fő HYPE OS Notion-importja.

## Frontend komponensek

`frontend/components/media-portal/` (publikus: `portal-view`, `password-gate`,
`BarionPixel`, `CookieConsent`) és `media-portal-admin/` (belső kezelőfelület).
Téma: `frontend/app/portal-theme.css` + a `hype-portal` osztály - a portál sötét,
szemcsés megjelenése szándékosan eltér a belső felülettől.
