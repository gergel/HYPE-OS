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
