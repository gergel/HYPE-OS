# Admin-Ágens — felhasználói útmutató

Ez az útmutató a napi adminmunkához szól. Az Admin-Ágens az adminisztrációt
segíti: elemzi a beérkező dolgokat, javaslatot készít, és emberi jóváhagyással
elvégzi a rutinlépéseket. **Alapból óvatos módban indul**: csak elemez, semmit
nem hajt végre magától.

## Hol találom?

A bal oldali menüben az **Admin-Ágens** csoport. Hét aloldal:

- **Áttekintés** — mennyi a nyitott / lejárt munka, mi vár jóváhagyásra, milyen
  állapotban vannak a forráskapcsolatok (Gmail, modell, tároló).
- **Munkasor** — a feladatok listája. Itt hozhatsz létre feladatot, oszthatsz ki
  felelőst, és nyithatod meg egy feladat részleteit.
- **Jóváhagyások** — amit az ágens előkészített, és emberi döntést vár.
- **Tudástár** — a szabályok és jóváhagyott minták. A gépi javaslat mindig külön
  van jelölve az élesben használt szabálytól.
- **Tanulás és minőség** — mit dolgozott fel a háttér-tanuló, és hogy áll a
  minőség-értékelés.
- **Napló** — mi történt: minden elemzés, döntés és végrehajtás nyoma.
- **Beállítások** — kapcsolók, bizalmi szintek, vészleállítás.

## Biztonságos alapállás — mit jelent?

- **A modul KI van kapcsolva**, a **mellékhatások TILTVA** vannak, minden
  feladattípus **L0 (árnyék)** módban van.
- L0-ban az ágens **csak elemez és javaslatot ír** — nem rögzít kiadást, nem küld
  e-mailt, nem nyúl külső rendszerhez.
- A javaslatnál egyértelmű jelzés áll: „Árnyék (L0): nem hajtódott végre".

## A napi folyamat

1. **Nézd meg a javaslatokat.** A Munkasorban egy feladatra kattintva látod, mit
   elemzett az ágens: a kiolvasott mezőket, az ellenőrzéseket és azt, milyen
   műveletet javasolna.
2. **Javíts, ha kell.** Ha valamit rosszul talált el, a javítás rögzül, és a
   háttér-tanuló tanul belőle (de egyetlen javításból nem lesz automatikus szabály).
3. **Jóváhagyás.** Ha bekapcsoltátok a mellékhatásokat és a feladattípus legalább
   L1, a Jóváhagyások oldalon a „Jóváhagyás és végrehajtás" gombbal engeded a
   műveletet. A gomb pontosan azt csinálja, amit ír.
4. **Elutasítás.** Ha nem jó, elutasítod — ez is tanulási jel.

## Tervezetet kérsz az ügynöktől (TIG, szerződés, e-mail)

1. Projektkód-adatlap vagy Utókövetés → **„Admin-Ágens teendők"** → **„+ Feladat"**
   (TIG vagy szerződés) — vagy nyiss meg egy meglévő feladatot.
2. A feladat oldalán **„Tervezet készítése (ügynök)"**. Az ügynök végigmegy a
   projektkód projektjein, és minden félhez, akinek még kell TIG/szerződés,
   előtölti, amit a rendszer tud. Minden mező mellett látod a **forrást**
   (mentett piszkozat, partnertörzs, projekt dátumai, tételek összege, vagy
   „ügynök (korábbi esetek alapján)"). A hiányzó mező kiemelve látszik.
3. Ha kell, **„Javaslat szerkesztése"** → javítsd → **„Mentés új javaslatként"**.
   Amit módosítasz, javításként rögzül — **ebből tanul** a legtöbbet.
4. Jóváhagyás után (L1-től) a piszkozatok **„Készítés alatt"** állapotban
   megjelennek a meglévő TIG/szerződés felületen. **A PDF-generálás és a kiküldés
   továbbra is a te lépésed** a megszokott helyen.
5. E-mailnél a címzett csak ismert címből lehet (a megrendelő kontaktjai, a
   függő felek). Más címet az ügynök nem írhat be.

**Összeget az ügynök nem talál ki:** csak akkor tölti ki, ha az igazolt forrásban
(piszkozat, szerződés, tételek, jóváhagyott korábbi eset) pontosan szerepel.
Ha nincs ilyen, üresen hagyja és jelzi.

**Modell-kulcs:** a kiegészítéshez és az e-mail megírásához a szerveren be kell
állítani a `GEMINI_API_KEY` értéket. Enélkül a tervezet a rendszer ismert
adataiból készül („A modell nincs beállítva" üzenet), e-mail-tervezet pedig
nem készül.

## Így indítod el a tanulást — és így látod, hogy tanul

Minden lépés kattintással megy:

1. **Kapcsold be a tanulást:** Admin-Ágens → **Beállítások** → „**Tanulás és
   megfigyelés (L0)**" kapcsoló. Ettől az ügynök félóránként megnézi a
   projektkódokon és az utókövetésben történt szerződés-, TIG- és
   számla/kiadás-lépéseket, és éjszaka tanul. Csak olvas — üzleti adatot nem módosít.
2. **Első betanítás:** Admin-Ágens → **Tanulás és minőség** → „**Kezdeti
   visszatekintés (90 nap)**". Ez feldolgozza a közelmúlt munkáját.
3. **Nézd meg, mit tanult:** Admin-Ágens → **Tudástár** → „Jóváhagyásra váró
   példák". Minden lezárt emberi munkából (pl. kiküldött TIG, kifizetett számla)
   egy példa-jelölt lesz, a projektkóddal és a projekttel együtt. Ami jó:
   **Jóváhagyás**; ami nem: **Elvetés**. Sok példánál szűrj típusra, pipáld ki
   az átnézetteket, és **„Kijelöltek jóváhagyása"**. (Ha régebbi jelöltek még
   „projektkód nélkül" szöveggel állnak, futtasd újra a „Kezdeti visszatekintés
   (90 nap)" gombot — a szövegük frissül.)
4. **Adj neki munkát:**
   - Beérkező számlák (Pénzügyek) → sor végén **„Admin-Ágens"** gomb → az ügynök
     elemzi, és megnyílik a feladat.
   - Projektkód-adatlap vagy Utókövetés → projektkód → **„Admin-Ágens teendők"**
     blokk → **„+ Feladat"** (szerződés / TIG / számla / utalás).
5. **Javítsd, ha téved:** a feladat oldalán **„Javítás rögzítése"** → írd be a
   helyes értéket. Ez a legerősebb tanulási jel.
6. **Futtasd a tanulót:** Tanulás és minőség → **„2. Háttér-tanuló"** (vagy
   megvárod az éjszakai futást). Két hasonló javításból **szabály-jelölt** lesz.
7. **Élesítsd a jót:** Tanulás és minőség → **„3. Értékelés"**, majd Tudástár →
   szabály-jelölt → **„Élesítés"**.
8. **Kövesd:** az **Áttekintés** „Tanulás állapota" kártyáján látod a számokat
   (megfigyelt lépés, javítás, példa-/szabály-jelölt, jóváhagyott példa, aktív
   szabály), a **Napló**ban pedig minden egyes megfigyelést.

## Bizalmi szintek (Beállítások)

Feladattípusonként állítható, mennyi önállóságot engedsz:

- **L0** — árnyék (csak elemzés). Ez az alapállás.
- **L1** — az ágens előkészít, te véglegesíted (jóváhagyással).
- **L2** — szűk, alacsony kockázatú automatika (csak mérés után érdemes).
- **L3/L4** — nagyobb önállóság, de a pénzügyi/jogi korlátok változatlanok.

A magasabb szint **soha** nem enged tiltott (banki végrehajtás) műveletet, és a
pénzt/jogi dokumentumot érintő lépés emberhez kötött marad.

## Vészleállítás

A Beállításokban a **Vészleállítás** gomb azonnal letiltja az ágens minden
mellékhatásos lépését. A már elindult, nem visszavonható külső műveleteket ez nem
vonja vissza — ezt a Napló mutatja. Feloldani a „Feloldás" gombbal lehet.

## Fontos korlátok

- **Banki utalást az ágens nem indít.** Az utalásnál csak előkészítést készít
  (kit, mennyit, mikorra), a tényleges utalás emberi feladat marad.
- **Új vagy megváltozott bankszámla** esetén az ágens megáll és emberi
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
