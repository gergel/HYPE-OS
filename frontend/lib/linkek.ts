/** Linkek felismerése FOLYÓ SZÖVEGBEN - függőség nélküli, tisztán számoló
 * modul, hogy a szerver- és a kliens-oldal is használhassa (a megjelenítést
 * lásd components/LinkeltSzoveg.tsx).
 *
 * A hosszú, szabad szöveges mezőkbe (vágás leírása, gyártás komment) a
 * kollégák egy mondat közepén szúrják be a linket - "a nyersanyag itt van:
 * https://drive.google.com/... , a briefet lásd a diszpóban". Ilyenkor a mező
 * értéke NEM egy URL, csak tartalmaz egyet, ezért az "egész érték egy link"
 * vizsgálat (lásd lib/detail.tsx) nem talál rá semmit, és a felhasználónak
 * kézzel kellett kimásolnia a címet. */

const URL_MINTA = /(https?:\/\/[^\s<>"']+|www\.[^\s<>"']+)/gi;

/** Záró írásjelek, amik jellemzően a MONDATHOZ tartoznak, nem a linkhez:
 * "lásd https://pelda.hu/anyag." végén a pont már nem része a címnek. */
const ZARO_KARAKTEREK = ".,;:!?»\"'";

const ZAROJEL_PARJA: Record<string, string> = { ")": "(", "]": "[", "}": "{" };

/** A találat végéről levágja azt, ami már a mondathoz tartozik. A zárójelet
 * megtartja, ha a linken belül párban áll - így a "…/Wikipedia_(film)" alakú
 * címek sem csonkulnak. */
function levagottVeg(url: string): { cim: string; maradek: string } {
  let vege = url.length;
  while (vege > 0) {
    const utolso = url[vege - 1];
    if (ZARO_KARAKTEREK.includes(utolso)) {
      vege -= 1;
      continue;
    }
    const nyito = ZAROJEL_PARJA[utolso];
    if (nyito) {
      // A vizsgált zárójel ELŐTTI részben számoljuk a párokat: ha ott több a
      // nyitó, akkor ez a záró hozzá tartozik, tehát a linkhez.
      const resz = url.slice(0, vege - 1);
      const nyitokSzama = resz.split(nyito).length - 1;
      const zarokSzama = resz.split(utolso).length - 1;
      if (nyitokSzama > zarokSzama) break; // van hozzá nyitó pár: a linkhez tartozik
      vege -= 1;
      continue;
    }
    break;
  }
  return { cim: url.slice(0, vege), maradek: url.slice(vege) };
}

export type SzovegDarab = { szoveg: string; href?: string };

/** Tartalmaz-e a szöveg legalább egy megnyitható linket? */
export function tartalmazLinket(szoveg: string): boolean {
  URL_MINTA.lastIndex = 0;
  return URL_MINTA.test(szoveg);
}

/** A szöveg felbontása sima szöveg- és link-darabokra, sorrendben. Ha nincs
 * benne link, egyetlen szöveg-darabot ad vissza. */
export function linkDarabok(szoveg: string): SzovegDarab[] {
  const darabok: SzovegDarab[] = [];
  let utolsoVeg = 0;
  URL_MINTA.lastIndex = 0;
  let talalat: RegExpExecArray | null;

  while ((talalat = URL_MINTA.exec(szoveg)) !== null) {
    const { cim, maradek } = levagottVeg(talalat[0]);
    if (!cim) continue;
    if (talalat.index > utolsoVeg) darabok.push({ szoveg: szoveg.slice(utolsoVeg, talalat.index) });
    darabok.push({ szoveg: cim, href: cim.startsWith("www.") ? `https://${cim}` : cim });
    if (maradek) darabok.push({ szoveg: maradek });
    utolsoVeg = talalat.index + talalat[0].length;
  }

  if (darabok.length === 0) return [{ szoveg }];
  if (utolsoVeg < szoveg.length) darabok.push({ szoveg: szoveg.slice(utolsoVeg) });
  return darabok;
}
