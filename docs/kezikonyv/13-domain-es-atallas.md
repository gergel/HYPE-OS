# 13 - Két domain és az átállás lépései

Ez a fejezet két dolgot ír le: hogyan fut a portál saját domainen, és pontosan
mit kell tenni ahhoz, hogy a régi rendszer tartalma átjöjjön.

## Rész 1 - A két domain

| Domain | Mit szolgál ki |
|---|---|
| **hypeclient.com** | Csak a publikus portál: `/p/{slug}` és `/adatvedelem` |
| a HYPE OS eddigi domainje | Az admin felület, a bejelentkezés, minden belső oldal |

Egyetlen Next.js telepítés szolgálja ki mindkettőt - nem kell második deploy.
A szétválasztást három dolog tartja be:

1. **`NEXT_PUBLIC_PORTAL_HOST`** (`frontend/middleware.ts`): erről a hosztról
   érkező kéréseknél csak a portál útvonalai élnek, minden más **404**. Nem
   átirányítás, mert az elárulná az admin felület címét.
2. **`NEXT_PUBLIC_PORTAL_BASE_URL`** (`frontend/lib/portalUrl.ts`): az admin
   felületen készülő linkek (Megosztó link, "Kész anyag URL") ide mutatnak - nem
   a böngésző aktuális origin-jébe, ami az admin domainje volna.
3. **`PORTAL_BASE_URL`** (backend, `settings.portal_front_base`): a szerver által
   generált linkek - a megosztó link és a Barion fizetés utáni visszairányítás.

Mindhárom üresen hagyva a rendszer pontosan úgy működik, mint eddig: egy domain,
minden útvonal. Fejlesztéshez ez a helyes.

Ami **marad** az admin domainen (szándékosan): az utókövető kérdőív
(`/kerdoiv/...`), mert az a stábnak megy, nem az ügyfélnek; és a Google OAuth
visszatérése. Ezeket a `FRONTEND_BASE_URL` vezérli.

## Rész 2 - Miért nem jött át eddig semmi

Mert még senki nem futtatta le az átemelést. A repóban a **kód** van meg hozzá; a
tényleges migrációhoz olyan hozzáférések kellenek, amik nincsenek és nem is
lehetnek a repóban: a régi adatbázis jelszava és a régi tárhely kulcsai. Ezeket
csak te tudod megadni.

Az alábbi lista pontosan az, amit el kell végezni, sorrendben.

---

## 1. lépés - Szedd össze a hozzáféréseket

Ezek nélkül egyik lépés sem indítható. Írd össze őket egy jelszókezelőbe (**ne**
e-mailbe, **ne** a repóba):

- [ ] **Régi adatbázis kapcsolati URL-je.** Railway → a régi portál szolgáltatás
      → *Variables* → `DATABASE_URL`. Ilyen alakú:
      `postgresql://user:jelszo@host:5432/adatbazis`
- [ ] **Régi tárhely (bucket) adatai**: account ID, access key ID, secret access
      key, bucket neve. Cloudflare R2 esetén: Cloudflare → R2 → *Manage API
      tokens*.
- [ ] **Új (HYPE OS) tárhely ugyanezen adatai** - ezek már a HYPE OS env
      változóiban vannak (`R2_*`).
- [ ] **A hypeclient.com DNS-kezelése** (ahol a domaint vetted).
- [ ] **Barion belépés** (a domain regisztrálásához a fizetéshez).

## 2. lépés - Nézzük meg, mi van a régi adatbázisban

Ez **csak olvas**, semmit nem módosít. A HYPE OS backend konténerében futtatható:

```bash
LEGACY_DATABASE_URL='postgresql://user:jelszo@host:5432/adatbazis' \
    python scripts/legacy_portal_inspect.py
```

Kiírja a táblákat, oszlopokat, sorszámokat és a fájlra mutató oszlopok
mintaértékeit.

**A kimenetet el kell menteni** - ebből derül ki, milyen néven és milyen
kulcs-formátumban vannak a videók és képek, és e nélkül a tényleges átemelő
szkript csak találgatás lenne. Ha a sorszámok nullák, akkor rossz adatbázisra
néztünk - ez már önmagában fontos információ.

## 3. lépés - Másold át a médiát (a leghosszabb lépés)

**Szerveren futtasd, ne a laptopodról.** Sok videónál ez órákig tart, és egy
lecsukott laptop megszakítja.

Telepítés és beállítás:

```bash
curl https://rclone.org/install.sh | sudo bash
rclone config
```

Két remote-ot hozz létre (`regi` és `uj`), mindkettőnél:
`type = s3`, `provider = Cloudflare`, `region = auto`,
`endpoint = https://<account-id>.r2.cloudflarestorage.com`.

Majd - először **próbaképp**, hogy lásd, jó helyre mutat-e:

```bash
rclone ls regi:regi-bucket | head -20
rclone size regi:regi-bucket
```

Ha stimmel, indulhat a másolás:

```bash
rclone copy regi:regi-bucket uj:hype-os-storage/media-portal/legacy/ \
  --progress --transfers 16 --checkers 32 --retries 5
```

Megszakadhat, nyugodtan indítsd újra ugyanezzel a paranccsal: a már átment,
azonos méretű fájlokat kihagyja.

Végül ellenőrizd:

```bash
rclone check regi:regi-bucket uj:hype-os-storage/media-portal/legacy/ --size-only
rclone size uj:hype-os-storage/media-portal/legacy/
```

A darabszámnak és az összméretnek egyeznie kell a régivel.

## 4. lépés - A DB-sorok átemelése

Ehhez a 2. lépés kimenete kell. Ennek alapján készül a migrációs szkript, ami:

- létrehozza a `portals` / `portal_folders` / `portal_videos` / `portal_images`
  sorokat a régi adatból,
- a fájlokat a staging (`legacy/`) helyükről a végleges kulcsra másolja
  **bucketen belül** (nem tölti át újra az adatot),
- `--dry-run`-nal előre megmutatja, mit csinálna,
- `--only-portal <slug>`-gal egyetlen portálon kipróbálható,
- újrafuttatható: a már átemelt sorokat felismeri, nem duplikál.

Egy döntés, ami rád tartozik: a HYPE OS-ben **minden portál egy meglévő
Projekthez tartozik**, a régiben viszont szabadon kitöltött cím/ügyfélnév volt.
Ahol nincs párja egy régi portálnak, ott az adat a felülíró mezőkbe kerül
(`title_override`, `client_name_override`) - ez működik, csak tudni kell róla.

## 5. lépés - Állítsd be a domaint

- [ ] **DNS**: a hypeclient.com (és a `www`) mutasson a Next.js telepítésre.
      Railway-en: *Settings → Domains → Custom Domain*, majd a kapott `CNAME`-et
      vedd fel a domain szolgáltatójánál. A HTTPS-tanúsítvány automatikus,
      de a DNS terjedése akár órákig tarthat.
- [ ] **Frontend env** (a Next.js szolgáltatásnál):
      `NEXT_PUBLIC_PORTAL_HOST=hypeclient.com`
      `NEXT_PUBLIC_PORTAL_BASE_URL=https://hypeclient.com`
- [ ] **Backend env**: `PORTAL_BASE_URL=https://hypeclient.com`
      (a `FRONTEND_BASE_URL` **marad** az admin domain!)
- [ ] **Barion**: a webshop/bolt adatainál a domaint állítsd át
      `hypeclient.com`-ra, különben a fizetés utáni visszatérés elutasításba fut.
      A Pixel is erre a domainre lesz bejegyezve.
- [ ] Újraindítás után nézd meg: `hypeclient.com/p/<egy-slug>` betölt, viszont
      `hypeclient.com/projektek` és `hypeclient.com/login` **404**.

## 6. lépés - Ellenőrzés, mielőtt bárkinek kiküldenél linket

- [ ] Nyiss meg 10-15 véletlen portált. Játszd le a videót, nyisd meg a képet,
      próbáld a **letöltést** is - az más úton megy, mint a lejátszás.
- [ ] Jelszavas portál: a régi jelszó működik-e. Ha a hash formátuma más volt, a
      jelszót újra kell adni - ez nem hiba, de az ügyfeleket értesíteni kell.
- [ ] Lejárt portál: a lejárati képernyőt adja-e, a helyes kapcsolati e-maillel.
- [ ] Fizetés **teszt módban** (`BARION_ENV=test`) végig: fizetési űrlap →
      Barion → visszatérés → a portál meghosszabbodott → számla kiállt.
- [ ] Darabszámok: portál / videó / kép a régi és az új adatbázisban egyezik-e.

## 7. lépés - Váltás és utána

- [ ] A régi rendszert tedd **írásra tilttá** (ne keletkezzen új adat, amit már
      senki nem hoz át), de még **ne kapcsold ki**.
- [ ] A régi bucketet és egy friss DB-dumpot tarts meg **legalább 1-2 hónapig**.
      Ez a visszaút, ha valami hiányzik.
- [ ] Ha a régi portál linkjeit már kiküldted ügyfeleknek, gondoskodj
      átirányításról a régi domainről az újra - különben a korábban kiküldött
      linkek meghalnak.

---

## Mit csinálj, ha elakadsz

A 2. lépés kimenete a kulcs mindenhez: abból derül ki, mi van a régi
rendszerben. Ha az megvan, a 4. lépés szkriptje megírható; addig a 3. lépés (a
média átmásolása) tőle függetlenül futhat, mert az csak a bájtokat mozgatja.
