import type { ProjectCode } from "@/lib/api";

/** A projektkód papír- és pénz-fázisai - FÜGGŐSÉG NÉLKÜLI modul.
 *
 * Szándékosan nem a lib/api.ts-ben él: azt kliens-komponensből behúzva a
 * `next/headers` is a böngésző-csomagba kerülne, és eltörne a build (a típus
 * import viszont fordításkor eltűnik, az rendben van). Ugyanaz a minta, mint
 * a lib/utokovetes.ts-nél - és a fázisok is ugyanazt a logikát követik, mert
 * a folyamat ugyanaz, csak a másik oldalon: ott mi fizetünk, itt minket
 * fizetnek. */
export type ProjektkodFazis = "szerzodes" | "tig" | "fizetes" | "kesz";

export const PROJEKTKOD_FAZISOK: { kulcs: ProjektkodFazis; cim: string; leiras: string }[] = [
  {
    kulcs: "szerzodes",
    cim: "Nincs még szerződés",
    leiras: "Papírt igényel, de eseti szerződés még nincs lezárva rá.",
  },
  { kulcs: "tig", cim: "Már csak a TIG kell", leiras: "A szerződés megvan, a teljesítési igazolás még nem." },
  {
    kulcs: "fizetes",
    cim: "Nincs kifizetve",
    leiras: "A papírozás rendben (vagy nem is kell), de a pénz még nem érkezett meg.",
  },
  { kulcs: "kesz", cim: "Kész", leiras: "Szerződés, TIG és a bevétel is megvan." },
];

/** A projektkód a LEGKORÁBBI hiányzó fázisban áll - így a táblán balról jobbra
 * haladva az látszik, mi a KÖVETKEZŐ teendő rajta. Egy hiányzó szerződést nem
 * lehet TIG-gel pótolni, ezért a sorrend maga is információ.
 *
 * Ahol nincs mit papírozni (nem szerződéses munka, vagy papír nélkül
 * elszámolt), ott a papír-lépések kimaradnak: a hiányzó papír nem elmaradás,
 * a pénz viszont ott is megérkezhet. */
export function projektkodFazisa(pc: ProjectCode): ProjektkodFazis {
  if (pc.papir_kell && !pc.szerzodes_kesz) return "szerzodes";
  if (pc.papir_kell && !pc.tig_kesz) return "tig";
  if (!pc.bevetel_kifizetve) return "fizetes";
  return "kesz";
}

/** Mi hiányzik pontosan - a kártyán egy sorban. */
export function projektkodHianyzik(pc: ProjectCode): string {
  switch (projektkodFazisa(pc)) {
    case "szerzodes":
      return "Eseti szerződés hiányzik";
    case "tig":
      return "Teljesítési igazolás hiányzik";
    case "fizetes":
      return pc.bevetel === 0 ? "Nincs bevétel felvezetve" : "A bevétel még nem érkezett meg";
    default:
      return pc.papir_kell ? "Papír és pénz is megvan" : "Papír nem kell, a pénz megérkezett";
  }
}
