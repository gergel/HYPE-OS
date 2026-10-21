/** A vágói visszajelzés állapotai.
 *
 * Külön modul, mert kliens komponensek is használják - a `lib/api.ts` a
 * `next/headers`-t húzza be, azt böngészőbe nem lehet importálni. */

export const VISSZAJELZES_ALLAPOTOK = [
  { ertek: "uj", cimke: "Új visszajelzés" },
  { ertek: "kikuldve", cimke: "Kiküldve" },
  { ertek: "nem_kuldjuk", cimke: "Nem küldjük ki" },
] as const;

export type VisszajelzesAllapot = (typeof VISSZAJELZES_ALLAPOTOK)[number]["ertek"];

/** A tárolt érték ("uj") emberi neve ("Új visszajelzés") - a felület mindenhol
 * a címkét mutatja, a szerver a rövid értéket tárolja. */
export function allapotCimke(ertek: string): string {
  return VISSZAJELZES_ALLAPOTOK.find((a) => a.ertek === ertek)?.cimke ?? VISSZAJELZES_ALLAPOTOK[0].cimke;
}

/** A címkéből vissza az értékre. Üres választás (a legördülő "törlés" gombja)
 * az alapállapotot jelenti: ami nincs eldöntve, az új visszajelzés. */
export function allapotErtek(cimke: string | null): string {
  return VISSZAJELZES_ALLAPOTOK.find((a) => a.cimke === cimke)?.ertek ?? "uj";
}

/** Az állapot jelzője. Az "új" a figyelemfelhívó (ezzel van dolgunk), a
 * kiküldött lezárt, a "nem küldjük ki" pedig szándékos döntés - ezért
 * semleges, nem hibajelzés. */
export function allapotJelzo(allapot: string): {
  label: string;
  tone: "success" | "warning" | "neutral";
} {
  if (allapot === "kikuldve") return { label: "Kiküldve", tone: "success" };
  if (allapot === "nem_kuldjuk") return { label: "Nem küldjük ki", tone: "neutral" };
  return { label: "Új visszajelzés", tone: "warning" };
}
