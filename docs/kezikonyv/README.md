# HYPE OS kézikönyv

Ez a mappa a HYPE OS **működési leírása**, témánként külön fájlban. Szándékosan
nincs "egy nagy dokumentum": a rendszer mérete miatt (kb. 45 API-modul, 40+
adatmodell, 80+ frontend komponens) egyetlen fájl pár hét alatt kezelhetetlen,
több száz oldalas lesz, amiben már senki nem talál meg semmit, és amit nem lehet
értelmesen se verziózni, se átadni.

Helyette a szabály:

1. **Egy téma = egy fájl**, és egy fájl ne nőjön ~200 sor fölé. Ha nő, ketté kell
   vágni, és ide, az indexbe felvenni.
2. **A részletes indoklás a kód mellett él**, nem itt. A backend szolgáltatásai és
   a route-ok tetején hosszú, magyar nyelvű docstringek magyarázzák, miért úgy
   működik valami, ahogy - azok a hiteles forrás. Ez a kézikönyv **térkép**: mi hol
   van, mi mihez tartozik, mire kell figyelni.
3. **Ez a mappa a repóban él**, tehát a kód mellett verziózódik, és mindig a
   `git pull` a "mentés". Nem kell semmit chatből kimásolni és külön fájlba
   gyűjteni: ami itt van, az megvan.

## Tartalom

| Fájl | Miről szól |
|---|---|
| [01-architektura.md](01-architektura.md) | Rétegek, mappaszerkezet, a CRUD-generátor, a rekord-részletnézet motorja |
| [02-auth-jogosultsag.md](02-auth-jogosultsag.md) | Bejelentkezés, szerepkörök, per-oldal jogosultság, mező-láthatóság |
| [03-projektek-ugyfelek.md](03-projektek-ugyfelek.md) | Project Code, projekt, ügyfél, kontakt, kampány |
| [04-csapat-felszereles.md](04-csapat-felszereles.md) | Crew, díjak, eszközök, leltározás, autók |
| [05-naptar-diszpo.md](05-naptar-diszpo.md) | Google Calendar szinkron, diszpó kiküldés, utókövető kérdőív |
| [06-papirozas.md](06-papirozas.md) | Keret- és eseti szerződés, alvállalkozói szerződés, külsős/belsős TIG, utókövetés |
| [07-penzugyek.md](07-penzugyek.md) | Költség, bevétel, KP-forgalom, számlázó cégek, visszatérő kötelezettségek |
| [08-utomunka-utokovetes.md](08-utomunka-utokovetes.md) | Deliverable-ök, timesheet, vágói visszajelzés |
| [09-media-portal.md](09-media-portal.md) | Az ügyfélnek szóló publikus portál, fizetés, számlázás, adatvédelem |
| [10-integraciok.md](10-integraciok.md) | Google (Gmail/Docs/Drive/Calendar), Notion import, R2, Barion, Számlázz.hu, Gemini |
| [11-uzemeltetes.md](11-uzemeltetes.md) | Env változók, indítás, migrációk, deploy, mit tegyél, ha valami nem megy |
| [12-migracio.md](12-migracio.md) | Átállás a régi rendszerről: kód, adat és média külön útja, cutover |
| [13-domain-es-atallas.md](13-domain-es-atallas.md) | A portál saját domainje (hypeclient.com), és az átállás lépésről lépésre |

A tervezési előzményeket (termékspecifikáció, AS-IS rendszertérkép, migration
map, roadmap, ER-diagram) a szülő `docs/` mappa őrzi - azok a rendszer
**megépítése előtti** állapotot írják le, ez a kézikönyv a **jelenlegit**.

## Hogyan tartsd karban

- Új modul készül → kap egy szakaszt a témájához tartozó fájlban, vagy saját
  fájlt, ha nem fér bele egyikbe sem. Az index sorát is vedd fel hozzá.
- Egy szabály megváltozik → a kódban lévő docstring a fontosabb; ide csak akkor
  kerüljön, ha több modult érint (mert akkor a kódban nincs egy "otthona").
- Ha egy fájl hosszabb lett, mint amit egy ülésben el lehet olvasni, vágd ketté.
  Ez nem esztétikai kérdés: az egybefolyó doksit senki nem olvassa el.
