import { DataTable } from "@/components/DataTable";
import { formatDate, type JsonRecord } from "@/lib/api";

const LABEL_KEYS = [
  "projektkod",
  "nev",
  "full_name",
  "feladat",
  "megnevezes",
  "projekt_neve",
  "bevetel_formaja",
  "ceg_neve",
  "tipus",
];

const STATUS_KEYS = ["allapot", "esemeny_allapota", "kampany_statusza", "szerzodes_allapota", "tig_statusza"];
const DATE_KEYS = ["datum", "hatarido", "forgatas_datuma", "kivitel_datuma", "keltezes"];

function pickField(row: JsonRecord, keys: string[]): string | null {
  for (const key of keys) {
    const value = row[key];
    if (typeof value === "string" && value) return value;
  }
  return null;
}

/** Kapcsolódó rekordok (pl. egy Project Code összes Projektje) generikus,
 * entitástípustól független listázása - a részletnézetek sok különböző
 * kapcsolt táblát mutatnak be, ehelyett ismételnénk ugyanazt a 3 oszlopot
 * entitásonként kézzel felsorolva. */
export function RelatedTable({
  rows,
  emptyText,
  getHref,
}: {
  rows: JsonRecord[];
  emptyText: string;
  getHref?: (row: JsonRecord) => string;
}) {
  return (
    <DataTable<JsonRecord>
      rows={rows}
      emptyText={emptyText}
      getHref={getHref}
      columns={[
        { header: "Megnevezés", render: (r) => pickField(r, LABEL_KEYS) ?? `#${r.id}` },
        { header: "Állapot", render: (r) => pickField(r, STATUS_KEYS) ?? "–" },
        { header: "Dátum", align: "right", render: (r) => formatDate(pickField(r, DATE_KEYS)) },
      ]}
    />
  );
}
