/** Notion-stílusú, mezőnkénti szűrés a listaoldalak tábláihoz.
 *
 * A szabályok ÉS kapcsolatban állnak (minden szabálynak teljesülnie kell),
 * és a táblázat fölötti szabadszavas kereséssel is együtt élnek - a kettő
 * egymást szűkíti, nem váltja ki egymást (a felhasználó kifejezett kérése).
 *
 * A szűrés a DataTable által soronként/oszloponként előre kiszámolt
 * szövegértéken fut (lásd DataTable filterValues), nem a nyers rekordon:
 * így pontosan arra lehet szűrni, ami a cellában LÁTSZIK, és nem kell minden
 * listaoldalt külön felkészíteni rá. */

export type FilterOperator =
  | "is"
  | "isNot"
  | "contains"
  | "notContains"
  | "startsWith"
  | "endsWith"
  | "gt"
  | "lt"
  | "isEmpty"
  | "isNotEmpty";

export type ColumnKind = "text" | "number";

export type FilterRule = {
  /** Egyedi azonosító, hogy a React kulcsok stabilak legyenek átrendezéskor. */
  id: number;
  columnIndex: number;
  operator: FilterOperator;
  value: string;
};

export const OPERATOR_LABELS: Record<FilterOperator, string> = {
  is: "Egyenlő",
  isNot: "Nem egyenlő",
  contains: "Tartalmazza",
  notContains: "Nem tartalmazza",
  startsWith: "Ezzel kezdődik",
  endsWith: "Ezzel végződik",
  gt: "Nagyobb mint",
  lt: "Kisebb mint",
  isEmpty: "Üres",
  isNotEmpty: "Nem üres",
};

const TEXT_OPERATORS: FilterOperator[] = [
  "is",
  "isNot",
  "contains",
  "notContains",
  "startsWith",
  "endsWith",
  "isEmpty",
  "isNotEmpty",
];

/** Számoszlopnál a "tartalmazza" jellegű műveletek félrevezetők (a 100 nem
 * "tartalmazza" a 10-et üzletileg), viszont a nagyobb/kisebb hasznos. */
const NUMBER_OPERATORS: FilterOperator[] = ["is", "isNot", "gt", "lt", "isEmpty", "isNotEmpty"];

export function operatorsFor(kind: ColumnKind): FilterOperator[] {
  return kind === "number" ? NUMBER_OPERATORS : TEXT_OPERATORS;
}

export function needsValue(operator: FilterOperator): boolean {
  return operator !== "isEmpty" && operator !== "isNotEmpty";
}

function toNumber(text: string): number | null {
  // A cellákban formázott számok is lehetnek ("127 000 Ft", "1 234,50") -
  // ezekből a puszta számot próbáljuk kiolvasni, hogy a nagyobb/kisebb
  // összehasonlítás azon is működjön, ami a képernyőn látszik.
  const cleaned = text.replace(/\s| /g, "").replace(/[^0-9,.-]/g, "");
  if (!cleaned) return null;
  const normalized = cleaned.includes(",") && !cleaned.includes(".") ? cleaned.replace(",", ".") : cleaned;
  const n = Number(normalized);
  return Number.isFinite(n) ? n : null;
}

function matchesRule(cellValue: string, rule: FilterRule): boolean {
  const cell = cellValue.trim().toLowerCase();
  const needle = rule.value.trim().toLowerCase();

  switch (rule.operator) {
    case "isEmpty":
      return cell === "" || cell === "–" || cell === "-";
    case "isNotEmpty":
      return !(cell === "" || cell === "–" || cell === "-");
    default:
      break;
  }
  if (!needle) return true; // félkész szabály nem szűr ki semmit

  switch (rule.operator) {
    case "is":
      return cell === needle;
    case "isNot":
      return cell !== needle;
    case "contains":
      return cell.includes(needle);
    case "notContains":
      return !cell.includes(needle);
    case "startsWith":
      return cell.startsWith(needle);
    case "endsWith":
      return cell.endsWith(needle);
    case "gt":
    case "lt": {
      const a = toNumber(cell);
      const b = toNumber(needle);
      if (a === null || b === null) return false;
      return rule.operator === "gt" ? a > b : a < b;
    }
    default:
      return true;
  }
}

export function matchesAllRules(filterValues: string[], rules: FilterRule[]): boolean {
  return rules.every((rule) => matchesRule(filterValues[rule.columnIndex] ?? "", rule));
}

/** Egy szabály "aktív"-e, azaz ténylegesen szűr-e - a félkész (érték nélküli)
 * szabályokat nem számoljuk bele a "N szűrő" jelzésbe. */
export function isActiveRule(rule: FilterRule): boolean {
  return !needsValue(rule.operator) || rule.value.trim() !== "";
}
