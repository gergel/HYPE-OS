/** Szöveg-normalizálás kereséshez.
 *
 * SZÁNDÉKOSAN önálló, függőség nélküli modul: szerver- és kliens-komponensek
 * is használják (a DataTable a sorok kereső-szövegét építi vele, a kliens
 * oldali keresők a beírt szót normalizálják). Ugyanaz a minta, mint a
 * lib/penz.ts és a lib/ido.ts esetében.
 */

/** Kisbetűsít és ELDOBJA AZ ÉKEZETEKET.
 *
 * Magyar adaton ez nem finomság: a "feny" nem találta meg a "Fény Bt."-t, és a
 * felhasználó oldaláról ez nem "pontatlan keresés", hanem "nem működik a
 * keresés". Aki gyorsan gépel egy listában, nem vált billentyűzetkiosztást.
 *
 * A NFD felbontja az ékezetes betűt alapbetűre + kombináló jelre, a
 * \u0300-\u036f tartomány pedig pont ezeket a kombináló jeleket dobja el. */
export function normalizal(szoveg: string): string {
  return szoveg
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

/** Illeszkedik-e a keresés a megadott mezőkre?
 *
 * Szavanként ÉS-kapcsolattal: a "media kft budapest" arra is illeszkedik, ahol
 * a három szó három külön mezőben áll - így nem kell tudni, melyik mezőben mi
 * van. Üres keresésre minden illeszkedik. */
export function illeszkedik(kereses: string, mezok: (string | null | undefined)[]): boolean {
  const szavak = normalizal(kereses).split(/\s+/).filter(Boolean);
  if (szavak.length === 0) return true;
  const szoveg = normalizal(mezok.filter(Boolean).join(" "));
  return szavak.every((szo) => szoveg.includes(szo));
}
