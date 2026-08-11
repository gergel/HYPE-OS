# 06 - Papírozás: szerződések és teljesítési igazolások

Ez a rendszer legsűrűbb doménje. Ha egyetlen dolgot jegyzel meg róla, ez legyen:

> **A papír nem emberhez tartozik, hanem SZÁMLÁZÓ FÉLHEZ.**
> Ha egy projekten több stábtag munkáját ugyanaz a fél számlázza (egy másik
> ember vagy egy cég), akkor **egy** szerződés és **egy** TIG kell mindannyiukra.
> A csoportosítás egy helyen dől el: `services/szamlazo.py` (`SzamlazoFel`,
> `SzamlazoCsoport`).

## Áttekintés

| Papír | API prefix | Kinek |
|---|---|---|
| Alvállalkozói **keretszerződés** (álló) | `/api/v1/contracts` | Külsős, tartós együttműködés |
| **Eseti** alvállalkozói szerződés | `/api/v1/alvallalkozoi-szerzodesek`, lista: `/api/v1/eseti-szerzodesek` | Külsős, projekthez kötve |
| **Megrendelői** szerződés | `/api/v1/megrendeloi-szerzodesek` | Ügyfél felé, Project Code-onként |
| **Külsős TIG** | `/api/v1/teljesitesi-igazolasok` | Nem belsős stábtag, projektenként |
| **Belsős TIG** | `/api/v1/belsos-tig` | Belsős munkatárs, havonta |
| Céges keretszerződés | `/api/v1/vallalkozasok` | Számlázó cégek |

Összefoglaló nézet mindegyikről: **Utókövetés** (`/utokovetes`).

## Az alvállalkozói folyamat sorrendje

1. **Diszpó kimegy** → megvan, ki vett részt a projekten.
2. **Eseti szerződés**: azokra kell, akik *sem nem belsősök*, *sem nincs érvényes
   keretszerződésük*. Aki keretszerződéses, az itt mentesül.
3. **Külsős TIG**: minden nem belsős stábtagnak - **a keretszerződéseseknek is**.
   A TIG a konkrét munka elvégzését igazolja, nem azt, hogy van-e álló szerződés.

**A TIG felenként nyílik meg, nem projektenként.** Amint egy számlázó félnek
megvan a szerződése (kiküldve vagy kihagyva) - vagy keretszerződés mentesíti -,
róla **azonnal** készíthető TIG, akkor is, ha a projekt többi szereplője még
szerződésre vár. Korábban az egész projekt szerződés-fázisának le kellett
zárulnia, így egyetlen késlekedő stábtag megállította mindenki papírozását.
A szabály egy helyen áll: `subcontractor_contracts.csoport_szerzodes_kesz()`,
a TIG-oldali szűrő pedig `performance_certificates.tig_keszitheto_csoportok()`.

### A kétlépéses életciklus

Szerződésnél és TIG-nél azonos, a régi Notion-os "Adatok átemelése" →
"Szerződés készítése és küldése" gombpáros mintájára:

- **Mentés** - az adatok egy "Készítés alatt" állapotú sorba kerülnek. Nincs
  PDF, nincs email; bármikor be lehet zárni és később folytatni.
- **Generálás és küldés** - ugyanez elmentve, majd azonnal PDF + kiküldés
  (`services/gdoc_template.py` + `services/google_email.py`).
- **Kihagyás** - lezárja az adott felet erre a projektre nézve, papír nélkül.
- **Saját, kész papír feltöltése** - ha a dokumentum máshol készült, fel lehet
  tölteni generálás helyett (`components/SajatPapirFeltoltes.tsx`).

### Tételek: több ember, több projekt egy papíron

Az eseti szerződés (`ContractTetel`) és a TIG (`PerformanceCertificateTetel`) is
**tételeken** keresztül mondja meg, kinek a munkáját melyik projekten fedi.
Segéd: `services/papir_tetelek.py`, frontend `components/PapirTetelValaszto.tsx`.

Egy visszafelé kompatibilis eset van, és ezt fontos tudni: a **tétel nélküli** sor
(Notion-importból, régi adatból, kézi adatbázis-javításból) pontosan azt fedi,
amiről a saját mezői szólnak - a saját projektjén a saját emberét. Ezt a szabályt
egy helyen tartja a `services/papir_fedettseg.py`, hogy a szerződés-oldal és a
TIG-oldal ugyanúgy lássa. Enélkül egy import után készült papír "nem létezőnek"
látszana, és a rendszer újra kérné.

## Belsős TIG - havi, nem projektenkénti

`/api/v1/belsos-tig`, oldal: `/belsos-tig`. Minden belsős embernek **pontosan egy**
TIG-je kell havonta, függetlenül attól, hány projekten dolgozott. Ezért a végpontok
nem projektre, hanem `(employee_id, év, hónap)` hármasra épülnek.

Amit tudni kell:

- **Visszafelé készül**: mindig az *előző* hónapé az aktuális feladat - júliusban a
  júniusi. Az admin oldal ezért alapból az előző hónapot mutatja, és felsorolja az
  **összes** belsős munkatársat: akinek még nincs TIG-je arra a hónapra, azt vagy
  létre kell hozni, vagy kihagyni (ha épp nem dolgozott).
- **A hónapot a teljesítés dátuma dönti el**, mégpedig az azt megelőző hónapot
  (2026.07.20-i teljesítés = a 2026. **júniusi** TIG). Ha az admin átírja a
  teljesítési dátumot másik hónapra, a bejegyzés átkerül oda
  (`_apply_teljesites_honap`).
- A teljesítés és a fizetési határidő alapértéke a **következő hónap 20-a**
  (`services/hu_datum.tig_hatarido`).
- Kinek kell egyáltalán: `services/belsos_idoszak.kell_havi_tig()` - az
  `alkalmazott` jogviszonyúaknak nem (nekik bérszámfejtés van), és csak arra a
  hónapra, amikor tényleg belsős volt (lásd [04-csapat-felszereles.md](04-csapat-felszereles.md)).
- Havi tételek (fizetés, bónusz, levonás): `models/employee_monthly_item.py`,
  előjeles összegzéssel. Frontend: `components/BelsosTigManager.tsx`,
  `BelsosTigHaviAttekintes.tsx`, `BelsosTigEmployeeList.tsx`, `TigInvoiceManager.tsx`.

## Megrendelői szerződés

Minden Project Code-hoz kell tartoznia egy szerződésnek
(`ProjectCode.contract_id`): ha a megrendelőnek van álló keretszerződése, azt újra
lehet használni; ha nincs, új, erre a Project Code-ra szóló szerződés kell.

Itt **nincs** Google Docs generálás és automata email (nincs sablon a megrendelői
szerződéshez) - a dokumentumot admin tölti fel kézzel. A modul csak az állapotot
és a Project Code ↔ Contract összerendelést kezeli.
Frontend: `components/ClientContractManager.tsx`.

## Utókövetés - az összefoglaló nézet

`/api/v1/utokovetes`, oldal: `/utokovetes`. Egy helyen mutatja egy diszpózott
projekt teljes adminisztrációs "utóéletét":

- az eseti szerződések állapota,
- a teljesítési igazolások állapota,
- a forgatás utáni kérdőívre beérkezett válaszok (lásd [05-naptar-diszpo.md](05-naptar-diszpo.md)).

A tényleges mentés/generálás/küldés/kihagyás továbbra is a saját végpontjain fut -
ez a nézet csak összegyűjt, hogy ne kelljen projektenként két oldalt végignézni.
**A sorok számlázó felenként állnak**, nem emberenként.

Emiatt szűnt meg az "Alvállalkozók szerződése" és a "Teljesítési igazolások"
külön menüpont: a műveletek megmaradtak, csak a jogosultságuk az Utókövetés
oldaláé lett. Frontend: `components/UtokovetesLista.tsx`, `UtokovetesNezetek.tsx`,
`UtokovetesTabla.tsx`.

## Dokumentum-generálás

Közös motor: `services/gdoc_template.py` - Google Docs sablon kitöltése,
PDF-export, tárolás. Sablononként külön env változó tartozik hozzá (külsős TIG,
belsős TIG, alvállalkozói szerződés, keretszerződés, diszpó) - lásd
[11-uzemeltetes.md](11-uzemeltetes.md).

A nettó összeg szöveges kiírását (a szerződések kötelező eleme) a
`services/hu_number_words.py` adja.
