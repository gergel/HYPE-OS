# Lara — felhasználói útmutató

Ez az útmutató a napi adminmunkához szól. Lara az adminisztrációt
segíti: elemzi a beérkező dolgokat, javaslatot készít, és emberi jóváhagyással
elvégzi a rutinlépéseket. **Alapból óvatos módban indul**: csak elemez, semmit
nem hajt végre magától.

## Hol találom?

A bal oldali menüben az **Lara** csoport. Kilenc aloldal:

- **Áttekintés** — mennyi a nyitott / lejárt munka, mi vár jóváhagyásra, milyen
  állapotban vannak a forráskapcsolatok (Gmail, modell, tároló).
- **Munkasor** — a feladatok listája. Itt hozhatsz létre feladatot, oszthatsz ki
  felelőst, és nyithatod meg egy feladat részleteit.
- **Jóváhagyások** — amit Lara előkészített, és emberi döntést vár.
- **Tudástár** — a szabályok és jóváhagyott minták. A gépi javaslat mindig külön
  van jelölve az élesben használt szabálytól.
- **Kérdések** — Lara kérdései: ahol az önellenőrzés során nem érti, miért úgy
  rögzítettetek valamit, ahogy. A válaszod azonnal a tudásába kerül.
- **Tudásháló** — Lara tudása egy színes kapcsolati „glóriaként": minden
  pont egy partner, projektkód, cél vagy szabály, a vonal vastagsága azt mutatja,
  mennyire biztos a kapcsolat. A „Növekedés lejátszása" megmutatja, hogyan épült fel.
- **Tanulás és minőség** — mit dolgozott fel a háttér-tanuló, és hogy áll a
  minőség-értékelés.
- **Napló** — mi történt: minden elemzés, döntés és végrehajtás nyoma.
- **Beállítások** — kapcsolók, bizalmi szintek, vészleállítás.

## Biztonságos alapállás — mit jelent?

- **A modul KI van kapcsolva**, a **mellékhatások TILTVA** vannak, minden
  feladattípus **L0 (árnyék)** módban van.
- L0-ban Lara **csak elemez és javaslatot ír** — nem rögzít kiadást, nem küld
  e-mailt, nem nyúl külső rendszerhez.
- A javaslatnál egyértelmű jelzés áll: „Árnyék (L0): nem hajtódott végre".

## A napi folyamat

1. **Nézd meg a javaslatokat.** A Munkasorban egy feladatra kattintva látod, mit
   elemzett Lara: a kiolvasott mezőket, az ellenőrzéseket és azt, milyen
   műveletet javasolna.
2. **Javíts, ha kell.** Ha valamit rosszul talált el, a javítás rögzül, és a
   háttér-tanuló tanul belőle (de egyetlen javításból nem lesz automatikus szabály).
3. **Jóváhagyás.** Ha bekapcsoltátok a mellékhatásokat és a feladattípus legalább
   L1, a Jóváhagyások oldalon a „Jóváhagyás és végrehajtás" gombbal engeded a
   műveletet. A gomb pontosan azt csinálja, amit ír.
4. **Elutasítás.** Ha nem jó, elutasítod — ez is tanulási jel.

## Tervezetet kérsz Larától (TIG, szerződés, e-mail)

1. Projektkód-adatlap vagy Utókövetés → **„Lara teendők"** → **„+ Feladat"**
   (TIG vagy szerződés) — vagy nyiss meg egy meglévő feladatot.
2. A feladat oldalán **„Tervezet készítése (Lara)"**. Lara végigmegy a
   projektkód projektjein, és minden félhez, akinek még kell TIG/szerződés,
   előtölti, amit a rendszer tud. Minden mező mellett látod a **forrást**
   (mentett piszkozat, partnertörzs, projekt dátumai, tételek összege, vagy
   „Lara (korábbi esetek alapján)"). A hiányzó mező kiemelve látszik.
3. Ha kell, **„Javaslat szerkesztése"** → javítsd → **„Mentés új javaslatként"**.
   Amit módosítasz, javításként rögzül — **ebből tanul** a legtöbbet.
4. Jóváhagyás után (L1-től) a piszkozatok **„Készítés alatt"** állapotban
   megjelennek a meglévő TIG/szerződés felületen. **A PDF-generálás és a kiküldés
   továbbra is a te lépésed** a megszokott helyen.
5. E-mailnél a címzett csak ismert címből lehet (a megrendelő kontaktjai, a
   függő felek). Más címet Lara nem írhat be.

**Összeget Lara nem talál ki:** csak akkor tölti ki, ha az igazolt forrásban
(piszkozat, szerződés, tételek, jóváhagyott korábbi eset) pontosan szerepel.
Ha nincs ilyen, üresen hagyja és jelzi.

**Modell-kulcs:** a kiegészítéshez és az e-mail megírásához a szerveren be kell
állítani a `GEMINI_API_KEY` értéket. Enélkül a tervezet a rendszer ismert
adataiból készül („A modell nincs beállítva" üzenet), e-mail-tervezet pedig
nem készül.

## Így indítod el a tanulást — és így látod, hogy tanul

Minden lépés kattintással megy:

1. **Kapcsold be a tanulást:** Lara → **Beállítások** → „**Tanulás és
   megfigyelés (L0)**" kapcsoló. Ettől Lara félóránként megnézi a
   projektkódokon és az utókövetésben történt szerződés-, TIG- és
   számla/kiadás-lépéseket, és éjszaka tanul. Csak olvas — üzleti adatot nem módosít.
2. **Első betanítás:** Lara → **Tanulás és minőség** → „**Visszatekintés
   a tanulás kezdetéig**". Ez feldolgozza a tanulás kezdete óta végzett munkát.
   **A tanulás kezdete alapból 2026. szeptember 1.** — azóta dolgozunk a HYPE OS
   felületén (előtte Notionben). Az ennél régebbi, illetve a Notionből hozott
   rekordokból nem készül példa-jelölt; a régi korszak korábbi jelöltjei a
   Tudástárban „Félretett régi jelöltek" alá kerülnek (nem törlődnek, egyenként
   jóváhagyhatók), a már jóváhagyott régi példákat pedig Lara csak az újabbak
   után, kisebb súllyal használja. A dátum a **Beállítások → Tanulás kezdete**
   mezőben módosítható.
3. **Nézd meg, mit tanult:** Lara → **Tudástár** → „Jóváhagyásra váró
   példák". Minden lezárt emberi munkából (pl. kiküldött TIG, kifizetett számla)
   egy példa-jelölt lesz, a projektkóddal és a projekttel együtt. Ami jó:
   **Jóváhagyás**; ami nem: **Elvetés**. Sok példánál szűrj típusra, pipáld ki
   az átnézetteket, és **„Kijelöltek jóváhagyása"**.
4. **Adj neki munkát:**
   - Beérkező számlák (Pénzügyek) → sor végén **„Lara"** gomb → Lara
     elemzi, és megnyílik a feladat.
   - Projektkód-adatlap vagy Utókövetés → projektkód → **„Lara teendők"**
     blokk → **„+ Feladat"** (szerződés / TIG / számla / utalás).
5. **Tanítsd a meglévő munkából (kevés új adatnál is):** Tanulás és minőség →
   „**Visszajátszás a rögzített számlákon**". A szeptember 1. óta rögzített
   számláknál összeveti, mit javasolt az érkeztető és mit döntöttetek; minden
   számlából példa-jelölt, a partnerenként egybehangzó döntésekből szabály-jelölt
   lesz (Tudástár). Ugyanitt a **Találati arány** mutatja hétről hétre, javul-e.
   A fejetekben lévő szokásokat a Tudástárban **„+ Új szabály kézzel"** írhatod be
   (partnerhez és — számlánál — célhoz kötve). Élesítés után Lara ennél a
   partnernél modell nélkül is ezt javasolja, ha az érkeztető nem döntött.
6. **Válaszolj Lara kérdéseire:** Lara kétóránként magától végignézi a rögzített
   számlákat és az Utókövetésben lezárt eseti szerződéseket és TIG-eket:
   megmondja, mit javasolt volna a mostani tudásával, és összeveti azzal, amit
   döntöttetek (számlánál a célt; szerződésnél/TIG-nél, hogy kellett-e, a nettó
   összeget a tételekhez képest, az ÁFÁ-t, a megbízás tárgyát, TIG-nél a
   számlát). Ahol nem érti az eltérést, **kérdez** (Lara → **Kérdések**, fent
   területre szűrhető). Válaszlehetőségek: **„Mindig így kell"** (szabályt tanul),
   **„Megmagyarázom"** (a magyarázat a tudásába kerül), **„Egyszeri kivétel"**,
   **„Rosszul rögzítettük"** (ebből nem tanul — a rögzítést javítsd). A Tanulás
   oldalon a **„Lara önellenőrzése"** kártya mutatja, hogyan nő a találati aránya
   — külön a számlákon, a szerződéseken és a TIG-eken. Amit a szerződésekről /
   TIG-ekről megtanult, azt a következő tervezetnél használja: a hiányzó
   megbízási tárgyat és ÁFA-jelzőt „Lara tudása" forrással előtölti, és szól,
   ha egy félnél a papír vagy a számla szokás szerint kihagyható.
7. **Javítsd, ha téved:** a feladat oldalán **„Javítás rögzítése"** → írd be a
   helyes értéket. Ez a legerősebb tanulási jel.
8. **Futtasd a tanulót:** Tanulás és minőség → **„2. Háttér-tanuló"** (vagy
   megvárod az éjszakai futást). Két hasonló javításból **szabály-jelölt** lesz.
9. **Élesítsd a jót:** Tanulás és minőség → **„3. Értékelés"**, majd Tudástár →
   szabály-jelölt → **„Élesítés"**.
10. **Kövesd:** az **Áttekintés** „Tanulás állapota" kártyáján látod a számokat
   (megfigyelt lépés, javítás, példa-/szabály-jelölt, jóváhagyott példa, aktív
   szabály), a **Napló**ban pedig minden egyes megfigyelést.

## Bizalmi szintek (Beállítások)

Feladattípusonként állítható, mennyi önállóságot engedsz:

- **L0** — árnyék (csak elemzés). Ez az alapállás.
- **L1** — Lara előkészít, te véglegesíted (jóváhagyással).
- **L2** — szűk, alacsony kockázatú automatika (csak mérés után érdemes).
- **L3/L4** — nagyobb önállóság, de a pénzügyi/jogi korlátok változatlanok.

A magasabb szint **soha** nem enged tiltott (banki végrehajtás) műveletet, és a
pénzt/jogi dokumentumot érintő lépés emberhez kötött marad.

## Vészleállítás

A Beállításokban a **Vészleállítás** gomb azonnal letiltja Lara minden
mellékhatásos lépését. A már elindult, nem visszavonható külső műveleteket ez nem
vonja vissza — ezt a Napló mutatja. Feloldani a „Feloldás" gombbal lehet.

## Fontos korlátok

- **Banki utalást Lara nem indít.** Az utalásnál csak előkészítést készít
  (kit, mennyit, mikorra), a tényleges utalás emberi feladat marad.
- **Új vagy megváltozott bankszámla** esetén Lara megáll és emberi
  ellenőrzést kér.
- **E-mail**: automatikus feladóra (pl. no-reply) nem válaszol; a te
  szerkesztésedet nem írja felül.
- A **jóváhagyás a konkrét javaslathoz kötött**: ha időközben változott (pl. az
  összeg), újra kell nézned és jóváhagynod.

## Ha valami nem működik

- „Beállítás szükséges" a forráskapcsolatnál → hiányzik egy integráció (pl.
  Gmail); az adott művelet addig tiltva marad, a többi működik. Szólj az
  üzemeltetőnek (lásd `operations.md`).
- „A javaslat megváltozott" (409) → töltsd újra az oldalt, és nézd meg az új
  javaslatot.
