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

/** A mai nap Budapesten, "YYYY-MM-DD" alakban (szerveren számolva, hogy a
 * kliens és a szerver ugyanazt a napot lássa). */
export function budapestiMa(): string {
  return new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Budapest" }).format(new Date());
}

/** Két "YYYY-MM-DD" dátum különbsége napokban (b - a). */
export function napKulonbseg(a: string, b: string): number {
  return Math.round((Date.parse(`${b.slice(0, 10)}T00:00:00Z`) - Date.parse(`${a.slice(0, 10)}T00:00:00Z`)) / 86400000);
}
