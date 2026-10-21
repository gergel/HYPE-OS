import { formatHuf } from "@/lib/api";

/** A Pénzügyek jogosultsági kulcsa - a kiadás- és bevétel-lista minden
 * helyen (Pénzügyek oldal, külön Kiadások / Bevételek oldal) ezt nézi. */
export const PENZUGYEK_PAGE = "/penzugyek";

/** A dátum-szűrő alatti összegzés: hány tétel, mennyi nettó. */
export function szurtOsszegzes(sorok: { netto: number | null }[]): string {
  const netto = sorok.reduce((ossz, s) => ossz + (Number(s.netto) || 0), 0);
  return `${sorok.length} tétel ebben az időszakban · nettó ${formatHuf(netto)}`;
}

/** Csak a ÉÉÉÉ-HH-NN alakú URL-paramétert fogadjuk el dátumnak. */
export function datumParam(v: string | string[] | undefined): string {
  const s = Array.isArray(v) ? v[0] : v;
  return s && /^\d{4}-\d{2}-\d{2}$/.test(s) ? s : "";
}
