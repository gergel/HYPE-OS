/** Pénz-formázás.
 *
 * SZÁNDÉKOSAN önálló, függőség nélküli modul: kliens-komponensek is használják
 * (lásd HaviKoltsegek, BelsosTigManager), a lib/api.ts viszont a
 * `next/headers`-t is behúzza (szerver-oldali cookie-olvasáshoz) - onnan
 * importálva a kliens-bundle összeomlana. Ugyanaz a minta, mint a
 * lib/mezoNev.ts és a lib/ido.ts esetében. */
export function formatHuf(value: number | null): string {
  if (value === null) return "–";
  if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1).replace(".0", "")}M Ft`;
  if (Math.abs(value) >= 1_000) return `${Math.round(value / 1_000)}k Ft`;
  return `${value} Ft`;
}
