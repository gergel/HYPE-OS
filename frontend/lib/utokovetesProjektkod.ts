import type { UtokovetesOverviewProjectCode } from "@/lib/api";

/** A projektkód (forgatás nélküli alvállalkozói kiadás) papírozásának fázisai
 * - lásd lib/utokovetes.ts FAZISOK (a forgatás-alapú megfelelője, ugyanaz a
 * gondolat). Ennek az ágnak nincs "aláírásra vár" és "utalásra vár" fázisa:
 * itt nincs tétel-rendszer, és a kifizetés állapotát nem egy külön
 * papír-allépés, hanem maga az Expense hordozza (lásd backend
 * utokovetes_admin.py "projektkód-szintű ág" fejléce) - ezért csak három
 * fázis van, nem öt. FÜGGŐSÉG NÉLKÜLI modul, ugyanazért, amiért lib/utokovetes
 * is az: kliens-komponensből importolva ne húzza be a "next/headers"-t. */
export type FazisProjektkod = "szerzodes" | "tig" | "kesz";

export const FAZISOK_PROJEKTKOD: { kulcs: FazisProjektkod; cim: string; leiras: string }[] = [
  { kulcs: "szerzodes", cim: "Szerződés hiányzik", leiras: "Van, akinek még nincs meg az eseti szerződése." },
  { kulcs: "tig", cim: "Már csak TIG kell", leiras: "A szerződések megvannak, a teljesítési igazolás hiányzik." },
  { kulcs: "kesz", cim: "Kész", leiras: "Szerződés és TIG is megvan mindenkinek." },
];

/** A projektkód a LEGKORÁBBI hiányzó fázisban áll - lásd lib/utokovetes.fazisa. */
export function fazisaProjektkod(sor: UtokovetesOverviewProjectCode): FazisProjektkod {
  if (sor.szerzodes_fuggo > 0) return "szerzodes";
  if (sor.tig_fuggo > 0) return "tig";
  return "kesz";
}

/** Mi hiányzik pontosan - a kártyán egy sorban. */
export function hianyzikProjektkod(sor: UtokovetesOverviewProjectCode): string {
  switch (fazisaProjektkod(sor)) {
    case "szerzodes":
      return `${sor.szerzodes_fuggo} / ${sor.szerzodes_osszes} szerződés hiányzik`;
    case "tig":
      return `${sor.tig_fuggo} / ${sor.tig_osszes} TIG hiányzik`;
    default:
      return "Szerződés és TIG is megvan";
  }
}
