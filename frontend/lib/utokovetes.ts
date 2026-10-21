import type { AlairasVaro, UtokovetesOverview } from "@/lib/api";

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

/** Mi hiányzik pontosan - a kártyán, az ÖSSZES egyidejű hiánnyal.
 *
 * Korábban csak a legkorábbi fázis hiányát írtuk ki, pedig egy projekten
 * egyszerre több minden is állhat (a felhasználó kérése, hogy mind
 * látszódjon). Minden szám SZÁMLÁZÓ FELET számol, nem embert/dokumentumot. */
export function hianyzik(sor: UtokovetesOverview): string {
  const reszek: string[] = [];
  if (sor.szerzodes_fuggo > 0) reszek.push(`${sor.szerzodes_fuggo} félnél szerződés`);
  if (sor.tig_fuggo > 0) reszek.push(`${sor.tig_fuggo} félnél TIG`);
  if (sor.kifizetes_fuggo > 0) reszek.push(`${sor.kifizetes_fuggo} félnél kifizetés`);
  if (sor.alairas_varo > 0) reszek.push(`${sor.alairas_varo} aláírt példány`);
  if (reszek.length > 0) return `Hiányzik: ${reszek.join(" · ")}`;
  // Kész oszlop: a "tényleg minden el van intézve" és a "nincs is papírozandó
  // fél" nem ugyanaz - a kettőt külön mondjuk ki.
  return sor.van_papirozando === false || sor.kifizetes_osszes + sor.szerzodes_osszes + sor.tig_osszes === 0
    ? "Nincs papírozandó fél ezen a projekten"
    : "Minden papír és kifizetés rendben";
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

/** ISO időbélyeg -> "09.28." (helyi idő szerint) - a kártyán elég a hónap és
 * a nap. */
function rovidDatum(iso: string | null): string {
  if (!iso) return "–";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "–";
  return `${String(d.getMonth() + 1).padStart(2, "0")}.${String(d.getDate()).padStart(2, "0")}.`;
}

/** Egy aláírásra váró szerződés egy sorban a kártyán (a felhasználó
 * kérése): mikor ment ki, és mikor esedékes a "küldd vissza aláírva"
 * emlékeztető. Pl. "Kiss Péter · ki: 09.28. (9 napja) · emlékeztető: most". */
export function alairasVaroSor(a: AlairasVaro): { szoveg: string; esedekes: boolean } {
  const ki = a.kikuldve_at
    ? `ki: ${rovidDatum(a.kikuldve_at)}${typeof a.kikuldve_napja === "number" ? ` (${a.kikuldve_napja === 0 ? "ma" : `${a.kikuldve_napja} napja`})` : ""}`
    : "kiküldés ideje nem ismert";
  let emlekezteto: string;
  if (a.emlekezteto_esedekes) emlekezteto = "emlékeztető: most küldhető";
  else if (typeof a.emlekezteto_hatra_nap === "number" && a.emlekezteto_hatra_nap > 0)
    emlekezteto = `emlékeztető: ${a.emlekezteto_hatra_nap} nap múlva (${rovidDatum(a.emlekezteto_felajanlhato_at)})`;
  else if (!a.kikuldve_at) emlekezteto = "emlékeztető nem küldhető (nem e-mailben ment)";
  else emlekezteto = "emlékeztető nem küldhető (nincs e-mail cím)";
  const ment = a.emlekezteto_kuldve_at
    ? ` · utolsó emlékeztető: ${rovidDatum(a.emlekezteto_kuldve_at)}${a.emlekezteto_db > 1 ? ` (${a.emlekezteto_db}×)` : ""}`
    : "";
  return { szoveg: `${a.nev} · ${ki} · ${emlekezteto}${ment}`, esedekes: a.emlekezteto_esedekes };
}
