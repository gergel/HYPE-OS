import type { ReactNode } from "react";

export type DetailSection = { key: string; label: string; badge?: number; content: ReactNode };

/** A részletnézet TELJES tartalma egyetlen, görgethető oldalon, szekció-
 * kártyákra bontva - NINCS fül-navigáció (a felhasználó kifejezett kérése:
 * a korábbi fül-váltós elrendezés "kaotikusnak" hatott, a referenciakép
 * szerint minden szekció egyszerre látszik, csak vizuálisan van csoportosítva
 * kártyákba). Az admin által a Beállítások oldalon konfigurált fül-elrendezés
 * (lásd lib/detailTabs.tsx buildFieldTabs) így is érvényben marad - csak azt
 * szabja meg, hogy mely mezők kerüljenek egy-egy kártyába, nem azt, hogy
 * kattintással kelljen köztük váltani.
 *
 * CSS multi-column elrendezést használ (nem CSS grid) - ez ad "masonry"-szerű,
 * eltérő magasságú kártyákat oszlopokba rendező viselkedést natív CSS-sel,
 * JS-es masonry könyvtár nélkül (lásd referenciakép: a kártyák nem egyenlő
 * magasságú sorokban, hanem a legrövidebb oszlopba folyva rendeződnek). */
export function DetailSections({ sections }: { sections: DetailSection[] }) {
  // 2 oszlopnál nem megyünk tovább: 3+ oszlopnál a CSS multi-column
  // kiegyenlítő algoritmusa (Chrome) nagyon egyenlőtlenül tölti fel az
  // oszlopokat, ha a kártyák magassága nagyon eltérő (pl. egy 16 mezős
  // szekció egy 4 mezős mellett) - ez nagy, üres területeket hagy néhány
  // oszlopban. 2 oszlopnál ez a torzulás sokkal kevésbé feltűnő.
  return (
    <div className="columns-1 gap-5 lg:columns-2 [&>*]:mb-5 [&>*]:break-inside-avoid">
      {sections.map((s) => (
        <div key={s.key}>{s.content}</div>
      ))}
    </div>
  );
}
