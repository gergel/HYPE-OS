/** Krumpello segédek - FÜGGŐSÉG NÉLKÜLI modul.
 *
 * Szándékosan nem a lib/api.ts-ben él: azt kliens-komponensből behúzva a
 * `next/headers` is a böngésző-csomagba kerülne, és eltörne a build (a típus
 * import viszont fordításkor eltűnik, az rendben van). Ugyanaz a minta, mint
 * a lib/utokovetes.ts-nél.
 */

/** Hogyan volt valaki bejelentve egy adott napon. Ugyanaz a zárt lista, mint
 * a backendben (lásd models/krumpello.py BEJELENTESEK) - ez dönti el, mennyi
 * megy utalással és mennyi készpénzben. */
export const KRUMPELLO_BEJELENTESEK = [
  { ertek: "efo", cimke: "EFO" },
  { ertek: "hatarozott", cimke: "Határozott idejű" },
  { ertek: "nincs", cimke: "Nincs bejelentve" },
] as const;

export function krumpelloBejelentesCimke(ertek: string | null): string {
  return KRUMPELLO_BEJELENTESEK.find((b) => b.ertek === ertek)?.cimke ?? "Nincs bejelentve";
}
