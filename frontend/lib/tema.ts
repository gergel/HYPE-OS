/** Világos/sötét nézet - a szerver és a böngésző közös nyelve.
 *
 * A választás az EMBERHEZ tartozik, és a munkatárs rekordján él (lásd backend
 * models/employee.py `tema`, illetve `PUT /api/v1/auth/me/tema`). A süti
 * ennek csak a GYORSÍTÓTÁRA: a legelső renderelés (még bármilyen API-hívás
 * előtt) ebből tudja, mit írjon a `<html data-theme>`-be - enélkül minden
 * oldalbetöltés sötéten villanna fel, mielőtt világosra vált.
 *
 * Ebből következik, hogy ütközéskor a SZERVER nyer: a fejlécben ülő kapcsoló
 * a bejelentkezett ember mentett témájával indul, és ha a süti mást mondott
 * (más gép, más böngésző, más ember lépett be ugyanott), csendben javítja.
 *
 * Ez a modul szándékosan mentes minden React- és next/headers-importtól, hogy
 * szerver- és kliensoldalról egyaránt behúzható legyen.
 */

export type Tema = "sotet" | "vilagos";

/** A süti neve. Nem httpOnly: a kapcsoló a böngészőből írja. Nincs benne
 * semmi bizalmas - egyetlen szó arról, milyen színű legyen a felület. */
export const TEMA_COOKIE = "hype-tema";

/** Aki még nem választott, a sötét alapot kapja.
 *
 * SZÁNDÉKOSAN nem a `prefers-color-scheme`: a HYPE OS sötét alapra tervezett
 * felület, és akinek az operációs rendszere világos, attól még nem biztos,
 * hogy ezt is világosan akarja használni. Aki igen, egy kattintással megkapja
 * - és onnantól emlékszünk rá. */
export const ALAP_TEMA: Tema = "sotet";

export function temaVagyAlap(ertek: string | null | undefined): Tema {
  return ertek === "vilagos" || ertek === "sotet" ? ertek : ALAP_TEMA;
}

/** Amit a `<html data-theme>` attribútumba írunk.
 *
 * Sötétnél ÜRES (attribútum nélkül): a globals.css alaptokenjei eleve a sötét
 * nézetet adják, tehát az attribútum ott nem hordozna információt - így
 * viszont az is a helyes felületet kapja, akihez a süti valamiért nem jut el. */
export function temaAttributum(tema: Tema): string | undefined {
  return tema === "vilagos" ? "light" : undefined;
}

/** A süti beírása egy évre. A `Lax` elég: nem hitelesítésre való, és
 * kizárólag saját oldalon olvassuk. */
export function temaSutiMentese(tema: Tema): void {
  document.cookie = `${TEMA_COOKIE}=${tema}; path=/; max-age=31536000; samesite=lax`;
}

/** A süti kiolvasása a böngészőben - a kapcsoló ebből látja, kell-e javítania. */
export function temaSutibol(): Tema | null {
  const talalat = document.cookie.match(new RegExp(`(?:^|; )${TEMA_COOKIE}=([^;]*)`));
  if (!talalat) return null;
  const ertek = decodeURIComponent(talalat[1]);
  return ertek === "vilagos" || ertek === "sotet" ? ertek : null;
}

/** A gyökér-elrendezés `<head>`-jébe kerülő, BLOKKOLÓ script (lásd
 * app/layout.tsx): a body kirajzolása előtt ráteszi a `data-theme`-et a
 * `<html>`-re, hogy világos nézetben ne villanjon fel a sötét felület.
 *
 * Szándékosan pici és önálló - nem hív semmit ebből a modulból, mert a
 * böngészőbe nyers szövegként kerül be, a csomagoló nélkül. Ha itt hiba
 * lenne, az a legelső festést állítaná meg, ezért a `try` is: egy elrontott
 * süti se tudja megfogni az oldalt (rosszabb esetben marad a sötét alap). */
export const TEMA_INIT_SCRIPT = `try{var m=document.cookie.match(/(?:^|; )${TEMA_COOKIE}=([^;]*)/);if(m&&decodeURIComponent(m[1])==="vilagos")document.documentElement.setAttribute("data-theme","light")}catch(e){}`;
