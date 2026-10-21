import { DataTable } from "@/components/DataTable";
import { formatDate, type JsonRecord } from "@/lib/api";
import { recordHref, type RecordEntityKey } from "@/lib/recordEntities";

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
 * entitásonként kézzel felsorolva.
 *
 * A sorok FELUGRÓ ABLAKBAN nyílnak meg (lásd RecordDetailModal), nem teljes
 * oldalként: egy kapcsolódó rekordba belenézni (pl. egy Külsősnél a hozzá
 * tartozó szerződésbe) ne járjon azzal, hogy elveszítjük az éppen nézett
 * rekordot és vissza kell navigálni. */
export function RelatedTable({
  rows,
  emptyText,
  getHref,
  entityKey,
  deleteBasePath,
}: {
  rows: JsonRecord[];
  emptyText: string;
  getHref?: (row: JsonRecord) => string;
  /** Azoknak az entitásoknak, amiknek nincs saját részletnézet-oldaluk (díj,
   * munkaidő-elszámolás, visszajelzés, eszközfoglalás, kapcsolattartó) - így
   * a soruk a generikus /rekord/... adatlapon nyílik meg, és minden mezőjük
   * szerkeszthető. Enélkül ezek a sorok kattinthatatlanok voltak, tehát a
   * bennük lévő adatot sehol nem lehetett javítani. */
  entityKey?: RecordEntityKey;
  /** Ha meg van adva, minden sor mellett törlés-gomb jelenik meg, ami a rekordot
   * magát törli (pl. deleteBasePath="/api/v1/deliverables") - FK-tulajdonolt
   * (egy-a-többhöz) kapcsolatokhoz, NEM many-to-many linkeléshez. */
  deleteBasePath?: string;
}) {
  const href = getHref ?? (entityKey ? (row: JsonRecord) => recordHref(entityKey, String(row.id)) : undefined);
  return (
    <DataTable<JsonRecord>
      rows={rows}
      emptyText={emptyText}
      getHref={href}
      openInModal
      filterable={rows.length > 8}
      // Kapcsolódó rekordok táblái általában rövidek - néhány sornál a
      // szűrő-építő csak zaj lenne, ezért ugyanannál a küszöbnél jelenik meg,
      // mint a keresőmező.
      columnFilters={rows.length > 8}
      deleteHref={deleteBasePath ? (r) => `${deleteBasePath}/${r.id}` : undefined}
      columns={[
        { header: "Megnevezés", render: (r) => pickField(r, LABEL_KEYS) ?? `#${r.id}`, sortAccessor: (r) => pickField(r, LABEL_KEYS) },
        { header: "Állapot", render: (r) => pickField(r, STATUS_KEYS) ?? "–", sortAccessor: (r) => pickField(r, STATUS_KEYS) },
        {
          header: "Dátum",
          align: "right",
          render: (r) => formatDate(pickField(r, DATE_KEYS)),
          sortAccessor: (r) => pickField(r, DATE_KEYS),
        },
      ]}
    />
  );
}
