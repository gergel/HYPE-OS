/** A PROJEKTKÓD felépítése: `HYPE26-0001` - évszámos előtag + négyjegyű sorszám.
 *
 * Az új kód felvételekor a KÖVETKEZŐ szabad sorszámot ajánljuk fel. Enélkül a
 * felvevőnek végig kellett görgetnie a listát, hogy megnézze, hol tartunk - és
 * két ember egyszerre dolgozva könnyen ugyanazt a számot írta be.
 *
 * Az ajánlás JAVASLAT, nem kényszer: a mező szabadon átírható (régebbi évre
 * szóló vagy más rendszerű kód is felvehető), és az adatbázisban úgyis egyedi
 * a kód, tehát az ütközést a mentés akkor is elkapja, ha közben más is felvett
 * egyet.
 */

/** Az adott év előtagja - a mai évből, tehát 2027-től magától `HYPE27-`. */
export function projektkodElotag(ev: number = new Date().getFullYear()): string {
  return `HYPE${String(ev).slice(2)}-`;
}

/** Ennyi számjegyre töltjük fel a sorszámot, ha nincs mihez igazodni. */
const ALAP_SZAMJEGYEK = 4;

/** A következő szabad projektkód az adott évre.
 *
 * Csak a TISZTÁN SZÁMOS sorszámokat nézzük: a `HYPE26-KERET1`-féle, kézzel
 * kitalált kódok nem a sorozat részei, és ha beleszámítanának, a következő
 * szám tőlük ugrana el.
 *
 * A számjegyek számát a meglévő kódokból vesszük (a leghosszabbhoz igazodva),
 * hogy a `0007` után ne `8` következzen - ránézésre az másik sorozatnak
 * látszana, és a listák a sorszámot amúgy is számként rendezik. */
export function kovetkezoProjektkod(kodok: string[], ev: number = new Date().getFullYear()): string {
  const elotag = projektkodElotag(ev);
  const sorszamok = kodok
    .map((kod) => (kod ?? "").trim())
    .filter((kod) => kod.startsWith(elotag))
    .map((kod) => kod.slice(elotag.length))
    .filter((veg) => /^\d+$/.test(veg));

  const legnagyobb = sorszamok.reduce((max, veg) => Math.max(max, Number(veg)), 0);
  const szamjegyek = sorszamok.reduce((max, veg) => Math.max(max, veg.length), ALAP_SZAMJEGYEK);
  return `${elotag}${String(legnagyobb + 1).padStart(szamjegyek, "0")}`;
}
