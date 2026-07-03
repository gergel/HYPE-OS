import type { ReactNode } from "react";
import { formatDate, formatHuf } from "@/lib/api";

const HIDDEN_KEYS = new Set(["id", "created_at", "updated_at"]);

const MONEY_KEY_PATTERN = /(netto|brutto|osszeg|koltseg|profit|bevetel|arfolyam|dij|ber)/i;
const DATE_VALUE_PATTERN = /^\d{4}-\d{2}-\d{2}/;
const URL_PATTERN = /^https?:\/\/\S+$/i;
const LONG_TEXT_LENGTH = 120;

export type DetailField = { label: string; value: ReactNode; wide?: boolean };

function humanizeKey(key: string): string {
  return key
    .replace(/_id$/, "")
    .replace(/_/g, " ")
    .replace(/^./, (c) => c.toUpperCase());
}

function isLongText(value: string): boolean {
  return value.includes("\n") || value.length > LONG_TEXT_LENGTH;
}

function isUrl(value: string): boolean {
  return URL_PATTERN.test(value.trim());
}

function LinkValue({ href }: { href: string }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className="text-text-accent break-all hover:underline">
      {href}
    </a>
  );
}

function formatValue(key: string, value: unknown): { node: ReactNode; wide: boolean } {
  if (value === null || value === undefined || value === "") return { node: "–", wide: false };
  if (typeof value === "boolean") return { node: value ? "Igen" : "Nem", wide: false };
  if (Array.isArray(value)) {
    if (value.length === 0) return { node: "–", wide: false };
    if (value.every((v) => typeof v === "string" && isUrl(v))) {
      return {
        node: (
          <div className="flex flex-col gap-0.5">
            {value.map((v) => (
              <LinkValue key={v} href={v} />
            ))}
          </div>
        ),
        wide: value.length > 1,
      };
    }
    const joined = value.map((v) => (typeof v === "object" && v !== null ? JSON.stringify(v) : String(v))).join(", ");
    return { node: joined, wide: isLongText(joined) };
  }
  if (typeof value === "object") return { node: JSON.stringify(value), wide: false };
  if (typeof value === "number") {
    return { node: MONEY_KEY_PATTERN.test(key) ? formatHuf(value) : String(value), wide: false };
  }
  if (typeof value === "string" && DATE_VALUE_PATTERN.test(value)) return { node: formatDate(value), wide: false };
  if (typeof value === "string" && isUrl(value)) return { node: <LinkValue href={value} />, wide: false };
  if (typeof value === "string" && isLongText(value)) {
    // a Notion rich_text mezők (pl. diszpó szövege, brief, technika lista) sortöréseit
    // meg kell tartani, különben az egész szöveg egy sorba tördelődik a böngészőben
    return { node: <span className="whitespace-pre-line">{value}</span>, wide: true };
  }
  return { node: String(value), wide: false };
}

/** Egy nyers rekord (bármelyik entitás, tetszőleges Notionből átjött mezőkkel)
 * DetailGrid-kompatibilis label/value listává alakítása - nem kell entitásonként
 * kézzel felsorolni a mezőket, mert a cél az, hogy minden mezőt lássunk. Hosszú
 * vagy többsoros szövegek (diszpó szövege, brief, technika lista, stb.) teljes
 * szélességben, a sortörések megtartásával jelennek meg. */
export function toDetailFields(record: Record<string, unknown>, hide: string[] = []): DetailField[] {
  const hideSet = new Set([...HIDDEN_KEYS, ...hide]);
  return Object.entries(record)
    .filter(([key]) => !hideSet.has(key))
    .map(([key, value]) => {
      const { node, wide } = formatValue(key, value);
      return { label: humanizeKey(key), value: node, wide };
    });
}
