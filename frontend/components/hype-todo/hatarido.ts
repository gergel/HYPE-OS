import { napKulonbseg } from "@/lib/idoszak";

export const KESZ_ALLAPOT = "Done";

/** Az állapotok magyar címkéje (az adatbázisban a Notion eredeti, vegyes
 * angol-magyar értékei maradnak - lásd backend models/hype_todo.py). */
export const ALLAPOT_CIMKE: Record<string, string> = {
  "In progress": "Folyamatban",
  "Not started": "Nincs elkezdve",
  "Ellenőrzés": "Ellenőrzésre vár",
  Done: "Kész",
};

export type HataridoJelzes = { szoveg: string; tone: "danger" | "warning" | "neutral" | "success" };

/** A határidő emberi alakban, a mai naphoz mérve: „3 napja lejárt”, „ma”,
 * „holnap”, „5 nap múlva”, „okt. 12.”. Kész feladatnál nincs riasztó szín. */
export function hataridoJelzes(hatarido: string | null, ma: string, kesz = false): HataridoJelzes | null {
  if (!hatarido) return null;
  const n = napKulonbseg(ma, hatarido);
  const datum = new Date(`${hatarido.slice(0, 10)}T00:00:00Z`).toLocaleDateString("hu-HU", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
  if (kesz) return { szoveg: datum, tone: "neutral" };
  if (n < 0) return { szoveg: `${-n} napja lejárt`, tone: "danger" };
  if (n === 0) return { szoveg: "ma", tone: "warning" };
  if (n === 1) return { szoveg: "holnap", tone: "warning" };
  if (n <= 7) return { szoveg: `${n} nap múlva`, tone: "warning" };
  return { szoveg: datum, tone: "neutral" };
}
