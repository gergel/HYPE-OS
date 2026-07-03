import type { ReactNode } from "react";
import { formatDate, formatHuf } from "@/lib/api";

const HIDDEN_KEYS = new Set(["id", "created_at", "updated_at"]);

const MONEY_KEY_PATTERN = /(netto|brutto|osszeg|koltseg|profit|bevetel|arfolyam|dij|ber)/i;
const DATE_VALUE_PATTERN = /^\d{4}-\d{2}-\d{2}/;

function humanizeKey(key: string): string {
  return key
    .replace(/_id$/, "")
    .replace(/_/g, " ")
    .replace(/^./, (c) => c.toUpperCase());
}

function formatValue(key: string, value: unknown): ReactNode {
  if (value === null || value === undefined || value === "") return "–";
  if (typeof value === "boolean") return value ? "Igen" : "Nem";
  if (Array.isArray(value)) {
    if (value.length === 0) return "–";
    return value.map((v) => (typeof v === "object" && v !== null ? JSON.stringify(v) : String(v))).join(", ");
  }
  if (typeof value === "object") return JSON.stringify(value);
  if (typeof value === "number") return MONEY_KEY_PATTERN.test(key) ? formatHuf(value) : String(value);
  if (typeof value === "string" && DATE_VALUE_PATTERN.test(value)) return formatDate(value);
  return String(value);
}

/** Egy nyers rekord (bármelyik entitás, tetszőleges Notionből átjött mezőkkel)
 * DetailGrid-kompatibilis label/value listává alakítása - nem kell entitásonként
 * kézzel felsorolni a mezőket, mert a cél az, hogy minden mezőt lássunk. */
export function toDetailFields(record: Record<string, unknown>, hide: string[] = []): { label: string; value: ReactNode }[] {
  const hideSet = new Set([...HIDDEN_KEYS, ...hide]);
  return Object.entries(record)
    .filter(([key]) => !hideSet.has(key))
    .map(([key, value]) => ({ label: humanizeKey(key), value: formatValue(key, value) }));
}
