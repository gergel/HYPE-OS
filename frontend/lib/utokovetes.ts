import type { UtokovetesOverview } from "@/lib/api";

/** Az utókövetés fázisai - FÜGGŐSÉG NÉLKÜLI modul.
 *
 * Szándékosan nem a lib/api.ts-ben él: azt kliens-komponensből behúzva a
 * `next/headers` is a böngésző-csomagba kerülne, és eltörne a build (a típus
 * import viszont fordításkor eltűnik, az rendben van). */

/** Melyik fázisban áll egy projekt utóélete.
 *
 * A sorrend a folyamat sorrendje: előbb mindenkinek szerződés kell, utána jön
 * a TIG, végül az utalás. Egy projekt mindig a LEGKORÁBBI hiányzó fázisban
 * van - így a táblán balról jobbra haladva látszik, mi a következő teendő. */
export type Fazis = "szerzodes" | "tig" | "utalas" | "alairas" | "kesz";

export const FAZISOK: { kulcs: Fazis; cim: string; leiras: string }[] = [
  { kulcs: "szerzodes", cim: "Szerződés hiányzik", leiras: "Van, akinek még nincs meg az eseti szerződése." },
  { kulcs: "tig", cim: "Már csak TIG kell", leiras: "A szerződések megvannak, a teljesítési igazolás hiányzik." },
  { kulcs: "utalas", cim: "Utalásra vár", leiras: "A papírok megvannak, a kifizetés még hátravan." },
  {
    kulcs: "alairas",
    cim: "Aláírt szerződésre vár",
    leiras: "Minden más megvan, csak a kiküldött szerződés nem jött vissza aláírva.",
  },
  { kulcs: "kesz", cim: "Kész", leiras: "Szerződés, aláírás, TIG és kifizetés is megvan." },
];

/** A projekt a LEGKORÁBBI hiányzó fázisban áll.
 *
 * Az aláírás-várás szándékosan a SOR VÉGÉN van, nem a szerződés után: a
 * kiküldött szerződés elég ahhoz, hogy a TIG és a kifizetés elinduljon (lásd
 * backend csoport_szerzodes_kesz), ezért egy visszavárt aláírás nem
 * takarhatja el a sürgősebb teendőket. Viszont ide kell, hogy egy projekt ne
 * csússzon át "Kész"-be úgy, hogy közben a papír sosem érkezett vissza. */
export function fazisa(sor: UtokovetesOverview): Fazis {
  if (sor.szerzodes_fuggo > 0) return "szerzodes";
  if (sor.tig_fuggo > 0) return "tig";
  if (sor.kifizetes_fuggo > 0) return "utalas";
  if (sor.alairas_varo > 0) return "alairas";
  return "kesz";
}

/** Mi hiányzik pontosan - a kártyán egy sorban. */
export function hianyzik(sor: UtokovetesOverview): string {
  switch (fazisa(sor)) {
    case "szerzodes":
      return `${sor.szerzodes_fuggo} / ${sor.szerzodes_osszes} szerződés hiányzik`;
    case "tig":
      return `${sor.tig_fuggo} / ${sor.tig_osszes} TIG hiányzik`;
    case "utalas":
      return `${sor.kifizetes_fuggo} / ${sor.kifizetes_osszes} kifizetés hátravan`;
    case "alairas":
      return `${sor.alairas_varo} aláírt szerződés hiányzik`;
    default:
      return sor.kifizetes_osszes === 0 ? "Nincs kifizetendő alvállalkozó" : "Mindenki ki van fizetve";
  }
}

/** Hány tétel hiányzik összesen - erre is lehet rendezni ("hol van a legtöbb
 * dolgom"). */
export function hianyzikDarab(sor: UtokovetesOverview): number {
  return sor.szerzodes_fuggo + sor.tig_fuggo + sor.kifizetes_fuggo + sor.alairas_varo;
}

/** Dátum kiírása (ugyanaz, amit a lib/api formatDate ad) - itt azért van
 * külön, hogy a kliens-komponensnek ne kelljen a lib/api-t behúznia. */
export function datum(value: string | null): string {
  return value ? value.slice(0, 10) : "–";
}
