"use client";

/** Rendszerszintű visszavonás (Ctrl+Z / Cmd+Z) - a verem.
 *
 * A bejegyzéseket az authFetch gyűjti (lásd lib/authFetch.ts): minden sikeres
 * mező-mentés (PATCH) előtt elteszi a mező RÉGI értékét, minden generikus
 * törlés (DELETE) után a backend törlés-pillanatképének azonosítóját. A
 * Ctrl+Z-t a VisszavonasFigyelo komponens (a gyökér-layoutban) fogja el, és
 * a verem tetején lévő bejegyzést futtatja.
 *
 * A verem szándékosan csak a memóriában él (lapfrissítésig): a visszavonás
 * a "hoppá, most rontottam el" mozdulat ellenszere, nem verziókezelés. */

export type VisszavonasBejegyzes = {
  /** Mit ír ki a felület a visszavonás után (pl. "Törlés visszavonva"). */
  cimke: string;
  /** A tényleges visszavonás - true, ha sikerült. */
  futtat: () => Promise<boolean>;
};

const MAX_MERET = 50;
const verem: VisszavonasBejegyzes[] = [];

export function rogzitsVisszavonast(bejegyzes: VisszavonasBejegyzes) {
  verem.push(bejegyzes);
  if (verem.length > MAX_MERET) verem.shift();
}

/** A legutóbbi bejegyzés kivétele a veremből (nincs "mégis visszateszem"). */
export function kovetkezoVisszavonas(): VisszavonasBejegyzes | undefined {
  return verem.pop();
}

export function vanVisszavonhato(): boolean {
  return verem.length > 0;
}
