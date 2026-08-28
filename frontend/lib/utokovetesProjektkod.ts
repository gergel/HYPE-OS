import type { UtokovetesOverviewProjectCode } from "@/lib/api";

/** A projektkód (forgatás nélküli alvállalkozói kiadás) papírozásának fázisai
 * - lásd lib/utokovetes.ts (a forgatás-alapú megfelelője). UGYANAZ az öt
 * fázis: a projektkód-ág is ismeri az aláírásra várást és a kifizetést (lásd
 * backend utokovetes_admin.py "projektkód-szintű ág" fejléce) - a
 * `UtokovetesOverviewProjectCode` mezői szándékosan ugyanazt nevet viselik,
 * mint a forgatás-alapú `UtokovetesOverview`-én. FÜGGŐSÉG NÉLKÜLI modul,
 * ugyanazért, amiért lib/utokovetes is az. */
export type FazisProjektkod = "szerzodes" | "tig" | "utalas" | "alairas" | "kesz";

export const FAZISOK_PROJEKTKOD: { kulcs: FazisProjektkod; cim: string; leiras: string }[] = [
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

/** A projektkód a LEGKORÁBBI hiányzó fázisban áll - lásd lib/utokovetes.fazisa. */
export function fazisaProjektkod(sor: UtokovetesOverviewProjectCode): FazisProjektkod {
  if (sor.szerzodes_fuggo > 0) return "szerzodes";
  if (sor.tig_fuggo > 0) return "tig";
  if (sor.kifizetes_fuggo > 0) return "utalas";
  if (sor.alairas_varo > 0) return "alairas";
  return "kesz";
}

/** Mi hiányzik pontosan - a kártyán egy sorban. */
export function hianyzikProjektkod(sor: UtokovetesOverviewProjectCode): string {
  switch (fazisaProjektkod(sor)) {
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
