/** A külsős TIG állapotának felirata. A "Kiküldve" állapot a TIG KÉSZ
 * állapota (mehet a számla-fázis) - de ha csak legenerálták, és e-mailben nem
 * ment ki (a felhasználó kérése: lehessen csak generálni), azt is mutassuk,
 * hogy senki ne higgye, hogy a megbízott már megkapta. */
export function tigAllapotCimke(allapot: string | null | undefined, csakGeneralva?: boolean): string {
  if (allapot === "Kiküldve" && csakGeneralva) return "Generálva (nem ment ki)";
  return allapot ?? "Készítés alatt";
}
