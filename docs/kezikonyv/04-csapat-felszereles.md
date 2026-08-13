# 04 - Csapat és felszerelés

## Csapat

Egy tábla, öt üzleti típus: a korábbi külön Vágók / Külsős / Belsős / Kreatív
team / Hype Stáb táblák egyetlen `Employee` entitásban egyesültek
(`models/employee.py`), a `tipus` mező (`EmployeeType`) különbözteti meg őket.
A frontend menü ezért mutat három bejáratot ugyanarra az adatra:

| Menüpont | Szűrés |
|---|---|
| Külsős (`/csapat`) | `kulsos` |
| Vágók (`/csapat/vagok`) | `vago` |
| Belsősök (`/csapat/belsosok`) | `belsos` |

Mindhárom ugyanazt a backend jogosultságot használja (`/csapat`).

API: `/api/v1/crew` (munkatársak), `/api/v1/rates` (díjak).
Route: `routes/crew.py`. Jogosultsági szerepkörökről lásd
[02-auth-jogosultsag.md](02-auth-jogosultsag.md).

### Belsős jogviszony és belsős időszakok

Belsősnél a `BelsosJogviszony` dönti el, kell-e havi TIG:

- `megbizas` → havonta számláz → kell TIG, számla, kifizetés-követés
- `alkalmazott` → bérszámfejtés → nincs TIG, csak a fizetés kerül be a hónapra

A logika egy helyen: `services/belsos_idoszak.py` → `kell_havi_tig()`.

Mivel valaki nem örökre belsős, külön tartjuk nyilván, **mettől meddig** volt az:
`/api/v1/belsos-idoszakok` (`models/belsos_idoszak.py`,
`routes/belsos_idoszakok.py`, frontend `components/BelsosIdoszakok.tsx`). A havi
belsős TIG-lista ez alapján tudja, kit kell egyáltalán kérdezni egy adott hónapban.

### Belsős napidíj: mennyibe kerül egy munkanapja

`Employee.napi_dij` - a belsősök listáján helyben szerkeszthető. Ebből számoljuk,
mennyi SAJÁT munka van egy projektben: minden forgatás költségébe beleszámít,
amin az illető stábtag ott volt (`services/belsos_koltseg.py`, több napos
forgatásnál napok × napidíj). Enélkül a projekt profitja szebb a valóságnál,
mert a saját emberünk munkája ingyennek látszik.

**A vágóknál nincs jelentése**: ők órabérben dolgoznak, a munkájuk ára a mért
időből jön (`Deliverable.koltseg`, lásd
[08-utomunka-utokovetes.md](08-utomunka-utokovetes.md)).

**Kiadás sor SOSEM lesz belőle.** A belsős alapbér a hónap végén, egy tételben
kerül a kiadások közé (Belsős TIG) - ha a napidíj is bekerülne, ugyanaz a pénz
kétszer szerepelne a Pénzügyekben. A napidíj tehát csak a projekt
önköltségét/profitját színezi, a kiadás-listát nem érinti.

### Munkatárs-dokumentumok

`models/employee_document.py`, `components/MunkaszerzodesUpload.tsx`,
`DokumentumFeltoltes.tsx` - munkaszerződés és egyéb papírok az adatlapon.
A tárolás közös motoron megy: `services/document_storage.py`.

## Felszerelés

**Eszközök** - `/api/v1/equipment` (CRUD-generátorral), `models/equipment.py`,
oldal: `/felszereles`.

**Kiadás/foglalás (Assignment)** - `/api/v1/assignments`. Itt van a rendszer egyik
kevés "kemény" szabálya: **ütközés-detektálás**. Ha egy eszközt olyan időszakra
akarnak lefoglalni, amikor már máshol van, a végpont `409`-cel visszautasítja.
A követési mód eszközönként állítható (`TrackMode`) - nem minden eszköznél
életszerű darabszintű nyomon követés.

Frontend: `components/EquipmentBookingManager.tsx`, `TechnikaCheckButton.tsx`,
backend segéd: `services/technika.py`.

**Leltározás** - `/api/v1/stocktake` (`services/stocktake.py`,
`models/stocktake.py`, `components/stocktake/`). Leltár-munkamenetek: megnyitod,
végigmész a tételeken, a végén összesítést kapsz. Jogosultsága a `/felszereles`
oldalé.

## Céges autók

`/api/v1/autok`, oldal: `/autok`, modell: `models/auto.py`, route: `routes/autok.py`.

A jármű maga sovány rekord, mert a tartalma két meglévő rendszerből jön - ez
szándékos, így nincs másolt adat, amit szinkronban kéne tartani:

- **Határidők** (forgalmi, biztosítás) → kötelezettségként futnak, ugyanazzal a
  lejárat-figyeléssel, értesítéssel és feladat-generálással, mint bármelyik
  előfizetés (`services/kotelezettseg.py`).
- **Költségek** (tankolás, szerviz) → sima kiadások az `expenses.auto_id`-n
  keresztül, tehát azonnal megjelennek a Pénzügy összesítőben.

Részletek: [07-penzugyek.md](07-penzugyek.md).
