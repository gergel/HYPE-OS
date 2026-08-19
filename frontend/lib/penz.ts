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

/** Miért NEM számít bele ez a bevétel-sor az ÉVES bevételbe? `null`, ha
 * beleszámít.
 *
 * Ugyanaz a szabály, mint a backend `services/elszamolas.bevetel_beleszamit`
 * függvényében - két helyen kell, mert a szerver szűri az összesítőket, a
 * lista pedig kiírja soronként, hogy melyik marad ki. Ha az egyik változik,
 * a másikat is állítani kell. */
export function bevetelKihagyasOka(sor: {
  bevetel_formaja: string | null;
  beleszamit_a_bevetelekbe: boolean | null;
}): string | null {
  if ((sor.bevetel_formaja ?? "").toLowerCase().includes("nem volt tranzakc")) {
    return "Nem volt tranzakció";
  }
  if (sor.beleszamit_a_bevetelekbe === false) return "Nem kerül a bevételek közé";
  return null;
}
