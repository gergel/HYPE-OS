/** Az árajánlat-készítő (backend: /api/v1/quotes, app/quotes/) típusai,
 * API-segédei és a szerverrel AZONOS összegzés - így a felület gépelés
 * közben is azonnal frissül, a szerver válasza pedig megerősíti. */

import { authFetch, authFetchVisszavonasNelkul } from "@/lib/authFetch";

export const API = "/api/v1/quotes";

export type Egyseg = "fo_nap" | "db_nap" | "nap" | "ora" | "alkalom" | "db" | "project" | "km" | "fo" | "honap";

export const EGYSEGEK: { ertek: Egyseg; cimke: string }[] = [
  { ertek: "fo_nap", cimke: "fő/nap" },
  { ertek: "db_nap", cimke: "db/nap" },
  { ertek: "nap", cimke: "nap" },
  { ertek: "ora", cimke: "óra" },
  { ertek: "alkalom", cimke: "alkalom" },
  { ertek: "db", cimke: "db" },
  { ertek: "project", cimke: "projekt" },
  { ertek: "km", cimke: "km" },
  { ertek: "fo", cimke: "fő" },
  { ertek: "honap", cimke: "hónap" },
];

export function egysegCimke(e: string | null | undefined): string {
  return EGYSEGEK.find((x) => x.ertek === e)?.cimke ?? e ?? "";
}

export const STATUSZOK: { ertek: string; cimke: string; tone: "neutral" | "blue" | "success" | "danger" | "warning" }[] = [
  { ertek: "draft", cimke: "Piszkozat", tone: "neutral" },
  { ertek: "sent", cimke: "Elküldve", tone: "blue" },
  { ertek: "accepted", cimke: "Elfogadva", tone: "success" },
  { ertek: "rejected", cimke: "Elutasítva", tone: "danger" },
  { ertek: "archived", cimke: "Archivált", tone: "warning" },
];

export function statusz(ertek: string) {
  return STATUSZOK.find((s) => s.ertek === ertek) ?? STATUSZOK[0];
}

export const MARKAK: { ertek: "HYPE" | "CB"; cimke: string; logo: string }[] = [
  { ertek: "HYPE", cimke: "HYPE", logo: "/arajanlat-hype-logo.png" },
  { ertek: "CB", cimke: "ContentBee", logo: "/arajanlat-contentbee-logo.png" },
];

export type KatalogusTetel = {
  id: number;
  category_id: number;
  category: string | null;
  name: string;
  default_description: string | null;
  unit: Egyseg;
  base_price: number;
  price_min: number | null;
  price_max: number | null;
  price_median: number | null;
  is_active: boolean;
  sort_order: number;
  tags: string[];
  updated_at: string | null;
};

export type Kategoria = { id: number; name: string; sort_order: number };

export type AjanlatSor = {
  id: number;
  catalog_item_id: number | null;
  section: string | null;
  name: string;
  description: string | null;
  occasions: number;
  quantity: number;
  unit: string | null;
  unit_price: number;
  line_discount_percent: number;
  is_optional: boolean;
  sort_order: number;
  line_total: number;
  catalog_price: number | null;
  variant_tags: string[];
};

export type Osszesito = {
  reszosszeg: number;
  kedvezmeny: number;
  netto: number;
  afa: number;
  brutto: number;
  opcionalis: number;
  havidij: number | null;
};

export type Ajanlat = {
  id: number;
  number: string;
  version: number;
  brand: "HYPE" | "CB";
  client_id: number | null;
  client: { id: number; nev: string } | null;
  project_name: string;
  event_date_from: string | null;
  event_date_to: string | null;
  location: string | null;
  status: string;
  pricing_mode: "one_off" | "monthly";
  months: number;
  discount_percent: number;
  discount_amount: number;
  vat_percent: number;
  summary_label: string | null;
  occasions_label: string | null;
  note_text: string | null;
  internal_note: string | null;
  parent_quote_id: number | null;
  parent: { id: number; number: string; version: number } | null;
  template_id: number | null;
  template_name: string | null;
  net_total: number;
  created_at: string | null;
  updated_at: string | null;
  sent_at: string | null;
  items: AjanlatSor[];
  totals: Osszesito;
  versions: { id: number; version: number; status: string; net_total: number; created_at: string | null }[];
};

export type AjanlatListaElem = {
  id: number;
  number: string;
  version: number;
  brand: "HYPE" | "CB";
  client_id: number | null;
  client_name: string | null;
  project_name: string;
  event_date_from: string | null;
  event_date_to: string | null;
  location: string | null;
  status: string;
  pricing_mode: string;
  net_total: number;
  created_at: string | null;
  updated_at: string | null;
};

export type SablonSor = {
  id: number;
  catalog_item_id: number | null;
  section: string | null;
  name_override: string | null;
  description_override: string | null;
  unit_override: string | null;
  default_occasions: number;
  default_quantity: number;
  price_override: number | null;
  is_optional: boolean;
  sort_order: number;
  catalog_item: KatalogusTetel | null;
  effective: { name: string; description: string | null; unit: string | null; unit_price: number };
};

export type Sablon = {
  id: number;
  name: string;
  description: string | null;
  brand: "HYPE" | "CB";
  pricing_mode: "one_off" | "monthly";
  summary_label: string | null;
  occasions_label: string | null;
  typical_total: number | null;
  default_note_id: number | null;
  sort_order: number;
  is_active: boolean;
  item_count: number;
  base_total: number;
  items?: SablonSor[];
};

export type Megjegyzes = { id: number; name: string; text: string; sort_order: number };
export type Ugyfel = { id: number; nev: string; adoszam: string | null; szekhely: string | null };

// ── Hívások ──────────────────────────────────────────────────────────────────

export class ApiHiba extends Error {
  status: number;
  constructor(status: number, uzenet: string) {
    super(uzenet);
    this.status = status;
  }
}

async function hibaUzenet(res: Response): Promise<string> {
  const d = (await res.json().catch(() => null)) as { detail?: unknown } | null;
  if (typeof d?.detail === "string") return d.detail;
  if (Array.isArray(d?.detail)) return "Érvénytelen érték.";
  if (res.status === 403) return "Ehhez nincs jogosultságod.";
  return `Sikertelen művelet (HTTP ${res.status}).`;
}

/** JSON-hívás; hibánál ApiHiba (magyar üzenettel). A sűrű mentések a
 * visszavonás-gyűjtés nélküli úton mennek (lásd lib/authFetch). */
export async function hivas<T>(path: string, init: RequestInit = {}, { visszavonhato = false } = {}): Promise<T> {
  const f = visszavonhato ? authFetch : authFetchVisszavonasNelkul;
  const res = await f(`${API}${path}`, init);
  if (!res.ok) throw new ApiHiba(res.status, await hibaUzenet(res));
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const kuld = <T>(path: string, method: string, body?: unknown) =>
  hivas<T>(path, { method, body: body === undefined ? undefined : JSON.stringify(body) });

/** Export letöltése (bejelentkezést igényel, ezért nem sima <a href>). */
export async function letoltes(path: string, tartalek: string): Promise<void> {
  const res = await authFetchVisszavonasNelkul(`${API}${path}`);
  if (!res.ok) throw new ApiHiba(res.status, await hibaUzenet(res));
  const cd = res.headers.get("content-disposition") ?? "";
  const m = /filename\*=UTF-8''([^;]+)/i.exec(cd);
  const nev = m ? decodeURIComponent(m[1]) : tartalek;
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nev;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

// ── Összegzés (a backend app/quotes/szamitas.py párja) ──────────────────────

/** Forintra kerekítés, fél felfelé (a szerver ROUND_HALF_UP-ja). */
function kerekit(x: number): number {
  return Math.sign(x) * Math.round(Math.abs(x) + 1e-9);
}

export function sorOsszeg(s: Pick<AjanlatSor, "occasions" | "quantity" | "unit_price" | "line_discount_percent">): number {
  return kerekit((s.occasions || 0) * (s.quantity || 0) * (s.unit_price || 0) * (1 - (s.line_discount_percent || 0) / 100));
}

export function osszesit(a: Pick<Ajanlat, "items" | "discount_percent" | "discount_amount" | "vat_percent" | "pricing_mode" | "months">): Osszesito {
  let resz = 0;
  let opcio = 0;
  for (const s of a.items) {
    const o = sorOsszeg(s);
    if (s.is_optional) opcio += o;
    else resz += o;
  }
  let kedv = kerekit((resz * (a.discount_percent || 0)) / 100) + (a.discount_amount || 0);
  kedv = Math.max(0, Math.min(kedv, resz));
  const netto = resz - kedv;
  const afa = kerekit((netto * (a.vat_percent || 0)) / 100);
  const havidij = a.pricing_mode === "monthly" && a.months > 0 ? kerekit(netto / a.months) : null;
  return { reszosszeg: resz, kedvezmeny: kedv, netto, afa, brutto: netto + afa, opcionalis: opcio, havidij };
}

// ── Formázás ─────────────────────────────────────────────────────────────────

export function ft(n: number | null | undefined): string {
  if (n === null || n === undefined || !Number.isFinite(n)) return "–";
  return `${Math.round(n).toLocaleString("hu-HU")} Ft`;
}

export function szamSzoveg(n: number): string {
  return Number.isInteger(n) ? String(n) : String(n).replace(".", ",");
}

/** "40 000" / "1,5" / "1.5" → szám; üres vagy értelmezhetetlen → null. */
export function szamBe(szoveg: string): number | null {
  const t = szoveg.replace(/\s| |Ft/g, "").replace(",", ".");
  if (t === "") return null;
  const n = Number(t);
  return Number.isFinite(n) ? n : null;
}

export function datumSzoveg(tol: string | null, ig: string | null): string {
  if (!tol) return "–";
  const f = (d: string) => d.replaceAll("-", ".") + ".";
  return ig && ig !== tol ? `${f(tol)} – ${f(ig).slice(5)}` : f(tol);
}

export function ajanlatSzam(a: { number: string; version: number }): string {
  return a.version > 1 ? `${a.number} v${a.version}` : a.number;
}
