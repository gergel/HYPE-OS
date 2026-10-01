/** A Pénzügyek időszak-szűrőjének (components/finance/DatumSzuro) szerver-
 * oldali párja - külön modulban, mert a "use client" fájlból importált
 * függvény a szerveren nem hívható. */

/** Benne van-e egy "YYYY-MM-DD" dátum a tól-ig
 * időszakban. Dátum nélküli tétel szűréskor kiesik (nem tudni, hova tartozik). */
export function idoszakban(datum: string | null | undefined, tol: string, ig: string): boolean {
  if (!tol && !ig) return true;
  if (!datum) return false;
  const d = datum.slice(0, 10);
  return (!tol || d >= tol) && (!ig || d <= ig);
}
