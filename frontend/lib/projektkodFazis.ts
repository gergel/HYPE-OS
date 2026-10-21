import type { ProjectCode } from "@/lib/api";

/** A projektkód papír- és pénz-fázisai - FÜGGŐSÉG NÉLKÜLI modul.
 *
 * Szándékosan nem a lib/api.ts-ben él: azt kliens-komponensből behúzva a
 * `next/headers` is a böngésző-csomagba kerülne, és eltörne a build (a típus
 * import viszont fordításkor eltűnik, az rendben van). Ugyanaz a minta, mint
 * a lib/utokovetes.ts-nél - és a fázisok is ugyanazt a logikát követik, mert
 * a folyamat ugyanaz, csak a másik oldalon: ott mi fizetünk, itt minket
 * fizetnek. */
export type ProjektkodFazis = "szerzodes" | "tig" | "fizetes_van_szamla" | "fizetes_nincs_szamla" | "kesz";

export const PROJEKTKOD_FAZISOK: { kulcs: ProjektkodFazis; cim: string; leiras: string }[] = [
  {
    kulcs: "szerzodes",
    cim: "Nincs még szerződés",
    leiras: "Papírt igényel, de eseti szerződés még nincs lezárva rá.",
  },
  { kulcs: "tig", cim: "Már csak a TIG kell", leiras: "A szerződés megvan, a teljesítési igazolás még nem." },
  // A "Nincs kifizetve" KÉT külön teendő: az egyiknél már csak várni kell (a
  // számla kiment, fut a fizetési határidő), a másiknál még a számlázás sincs
  // elindítva - ez utóbbi a sürgetőbb, mert amíg nincs számla, a fizetési
  // határidő sem tud elindulni.
  {
    kulcs: "fizetes_van_szamla",
    cim: "Számla kint, várjuk a kifizetést",
    leiras: "Van feltöltött számla és fizetési határidő, de a pénz még nem érkezett meg.",
  },
  {
    kulcs: "fizetes_nincs_szamla",
    cim: "Még nincs számla",
    leiras: "A papírozás rendben (vagy nem is kell), de még nincs feltöltött számla vagy fizetési határidő.",
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
  // ELMARADT az esemény: nincs rajta teendő. Se papír, se pénz - ami meg sem
  // történt, arról nincs mit igazolni, és nem is fizet érte senki. Enélkül a
  // "Nincs kifizetve" fázisba esne, és örökre ott állna a teendők között
  // (lásd backend models/project_code.esemeny_elmaradt).
  if (pc.elmaradt) return "kesz";
  // Élő keretszerződés alatt eseti szerződés nem kell (`szerzodes_kell`
  // hamis), a TIG viszont ugyanúgy jár - ugyanez a szabály az alvállalkozói
  // oldalon is.
  if (pc.szerzodes_kell && !pc.szerzodes_kesz) return "szerzodes";
  if (pc.papir_kell && !pc.tig_kesz) return "tig";
  // VAN-e feltöltött számla, aminek fizetési határideje is van - enélkül
  // hiába várnánk a kifizetésre, még a számlázás sincs elindítva (lásd
  // szamla_hataridok - backend models/project_code.szamla_hataridok).
  if (!pc.bevetel_kifizetve) return pc.szamla_hataridok.length > 0 ? "fizetes_van_szamla" : "fizetes_nincs_szamla";
  return "kesz";
}

/** Mi hiányzik pontosan - a kártyán egy sorban. */
export function projektkodHianyzik(pc: ProjectCode): string {
  switch (projektkodFazisa(pc)) {
    case "szerzodes":
      return "Eseti szerződés hiányzik";
    case "tig":
      return pc.keret_fedi
        ? "Teljesítési igazolás hiányzik (keretszerződés alatt)"
        : "Teljesítési igazolás hiányzik";
    case "fizetes_van_szamla":
      return "A bevétel még nem érkezett meg";
    case "fizetes_nincs_szamla":
      return pc.bevetel === 0 ? "Nincs bevétel felvezetve" : "Még nincs feltöltött számla vagy fizetési határidő";
    default:
      if (pc.elmaradt) return "Az esemény elmaradt - nincs rajta teendő";
      return pc.papir_kell ? "Papír és pénz is megvan" : "Papír nem kell, a pénz megérkezett";
  }
}
