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

#### "Belsős" mindig A FORGATÁS NAPJÁRA értendő

Egy projekten sosem a mai típus dönt, hanem az, hogy az illető **azon a napon**
belsős volt-e (`belsos_idoszak.belsos_a_napon()`). A projektek ugyanis
visszamenőlegesek: aki ma belsős, tavaly még külsősként forgathatott - és arra a
munkájára ugyanúgy jár neki szerződés és TIG, mint bármely külsősnek.

Ez a szabály egy helyen él, és minden érintett pont ezt használja:

| Hol | Mit dönt el |
|---|---|
| Stábtag hozzáadása | a választóban a **Belsős** csoportba csak az kerül, aki akkor belsős volt; a többi Külsősként jön (és úgy is kezeljük: kérdezzük a megbeszélt díját) |
| Eseti szerződés és TIG populációja | kitől kérünk papírt (`szerzodest_igenylo_emberek`, `tig_igenylo_emberek`) |
| "Ki számláz kiért" tábla + megbeszélt díj | kinél kérdés egyáltalán a számlázás (`routes/project_szamlazok.py`) |
| Belsős napidíj | kinek a napidíja terheli a projektet (`services/belsos_koltseg.py`) |

Az utolsó sor a legfontosabb: ha a napidíj a mai típus alapján számítana, a
tavalyi projektre RÁÍRNÁNK a napidíját, miközben a munkája a TIG-jén is ott van
- ugyanaz a költség kétszer.

**Adat híján a mai típus dönt.** Ha nincs se felvitt időszaka, se első/utolsó
munkanapja, nem kezdünk találgatni (lásd `bizonyithatoan_nem_belsos`) - ilyenkor
a belsős időszakot érdemes pótolni.

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

Az összesítés HÁROM dolgot mond meg, nem kettőt: mi nem "Jó" állapotú, miből
hiányzik, és **miből van több az elvártnál**. A többlet ugyanúgy eltérés, mint a
hiány - vagy a nyilvántartás volt rossz, vagy egy másik tétel alá könyvelt
darabok kerültek elő -, és ha nem írjuk ki, a készlet csendben elcsúszik.

**A lezárás magyarázatot követel** a "Szerelendő" és a "Szervíz" állapotú
eszközökhöz (`MAGYARAZATOT_IGENYLO_STATUSZOK`). Egy hónappal később a puszta
státuszból már senki nem tudja, mi a baja a gépnek, hol van, és ki vitte el - a
leltározás viszont épp az a pillanat, amikor ezt valaki még fejből tudja. Amíg
hiányzik, a `complete` végpont `400`-zal elutasít, és a szerkesztő oldal előre
kiírja, kinél áll. A Selejt/Elhagyva szándékosan nem kér magyarázatot: ott maga
a szó megmondja, mi történt.

**Törölni csak admin tud** egy leltározást (`DELETE /sessions/{id}`) - a leltár
egy elvégzett munka nyoma, aki végigment 300 eszközön, annak az eredményét ne
tüntesse el egy félrekattintás. A törlés a tételeket viszi, az eszközök leltár
közben beállított állapotát/darabszámát NEM állítja vissza: azok a valós
állapotot tükrözik.

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
