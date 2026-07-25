import { isValidElement, type ReactNode } from "react";
import { InteractiveTableClient } from "@/components/InteractiveTableClient";
import type { ColumnKind } from "@/lib/tableFilters";

/** A már leredenderelt cella szöveges tartalma - ebből lesz a mezőnkénti
 * szűrés alapja (lásd TableFilterBuilder), hogy pontosan arra lehessen
 * szűrni, ami a cellában LÁTSZIK, és ne kelljen minden listaoldalon külön
 * szűrő-mezőket deklarálni.
 *
 * A StatusBadge-szerű komponensek a szövegüket nem gyerekként, hanem `label`
 * propban kapják, ezért azt is megnézzük - enélkül pl. egy státusz-oszlopra
 * egyáltalán nem lehetne szűrni. */
function nodeToText(node: ReactNode): string {
  if (node === null || node === undefined || typeof node === "boolean") return "";
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(nodeToText).join(" ");
  if (isValidElement(node)) {
    const props = node.props as { children?: ReactNode; label?: ReactNode };
    const fromChildren = nodeToText(props.children);
    if (fromChildren.trim()) return fromChildren;
    return nodeToText(props.label);
  }
  return "";
}

/** A rekord ÉRTÉKEINEK összefűzött szövege a szabadszavas kereséshez.
 *
 * Szándékosan nem `JSON.stringify(row)`: az a MEZŐNEVEKET is beleveszi, így pl.
 * a "zoom" keresés minden eszközre illeszkedett, mert az Equipment táblának van
 * egy `zoom_atfogas` oszlopa - a felhasználó szemszögéből ez néma hibás
 * találat-áradat. Így csak az látszik keresésnek, ami tényleges adat. */
function valuesText(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (Array.isArray(value)) return value.map(valuesText).join(" ");
  if (typeof value === "object") return Object.values(value).map(valuesText).join(" ");
  return String(value);
}

const NUMBER_LIKE = /^-?[\d\s  .,]+(?:\s*(?:ft|huf|eur|usd|db|%))?$/i;

/** Egy oszlop "szám" jellegű-e - ettől függ, milyen műveleteket kínálunk rá a
 * szűrőben (nagyobb/kisebb vs. tartalmazza). Az oszlop tényleges értékeiből
 * döntjük el, mert a Column típus nem hordoz mezőtípust. */
function columnKind(values: string[]): ColumnKind {
  const filled = values.map((v) => v.trim()).filter((v) => v && v !== "–" && v !== "-");
  if (filled.length === 0) return "text";
  return filled.every((v) => NUMBER_LIKE.test(v)) ? "number" : "text";
}

export type Column<T> = {
  header: string;
  align?: "left" | "right";
  render: (row: T) => ReactNode;
  /** Ha meg van adva, az oszlop fejléce kattintható lesz és rendezhető erre az
   * értékre - stringet/számot ad vissza (nem JSX-et, mert azt nem lehet rendezni). */
  sortAccessor?: (row: T) => string | number | null | undefined;
};

/** Szerver-oldali komponens: minden sort/cellát itt renderelünk le (col.render,
 * col.sortAccessor, getHref, deleteHref függvényeit itt hívjuk meg), mert
 * függvényeket nem lehet átküldeni a szerver/kliens határon. A már kész,
 * szerializálható eredményt (ReactNode cellák, string/szám sortKey-ek, string
 * href-ek) adjuk át az InteractiveTableClient-nek, ami a rendezést/szűrést/
 * törlést kezeli kliens oldalon. */
export function DataTable<T extends { id: number }>({
  columns,
  rows,
  emptyText,
  getHref,
  filterable = false,
  columnFilters = true,
  deleteHref,
  onRowClick,
  openInModal = false,
}: {
  columns: Column<T>[];
  rows: T[];
  emptyText: string;
  getHref?: (row: T) => string;
  /** Szabadszavas keresőmező a táblázat felett. */
  filterable?: boolean;
  /** Mezőnkénti szűrő-építő ("+ Szűrő") a táblázat felett - alapból mindenhol
   * bekapcsolva. Külön kapcsolható a szabadszavas keresőtől, mert van olyan
   * oldal (Projektek), ahol a keresés szülő szinten fut, hogy a naptár
   * nézetre is érvényes legyen - ott csak ez a szűrő kell a táblához. */
  columnFilters?: boolean;
  /** Ha meg van adva, minden sor végén egy törlés-gomb jelenik meg - a DELETE
   * végpont teljes útvonalát adja vissza (pl. `/api/v1/deliverables/42`). */
  deleteHref?: (row: T) => string;
  /** Ha meg van adva, sorra kattintáskor ez fut le a sor id-jével a getHref
   * szerinti navigáció HELYETT (pl. felugró ablakban való megnyitáshoz). */
  onRowClick?: (id: number) => void;
  /** A getHref szerinti cél felugró ablakban nyíljon meg, ne teljes oldalként
   * (lásd RecordDetailModal) - a kapcsolódó rekordok tábláinál ez az
   * alapértelmezés, lásd RelatedTable. */
  openInModal?: boolean;
}) {
  const renderedCells = rows.map((row) => columns.map((col) => col.render(row)));
  // A szűrés alapértéke a cella látható szövege; ahol van sortAccessor, az
  // pontosabb (nyers érték, formázás nélkül), ezért az élvez elsőbbséget.
  const filterValuesByRow = rows.map((row, rowIndex) =>
    columns.map((col, colIndex) => {
      const sortValue = col.sortAccessor?.(row);
      if (sortValue !== null && sortValue !== undefined && sortValue !== "") return String(sortValue);
      return nodeToText(renderedCells[rowIndex][colIndex]);
    }),
  );
  const headerMeta = columns.map((col, colIndex) => ({
    header: col.header,
    align: col.align,
    sortable: !!col.sortAccessor,
    kind: columnKind(filterValuesByRow.map((values) => values[colIndex])),
  }));
  const renderedRows = rows.map((row, rowIndex) => ({
    id: row.id,
    href: getHref?.(row),
    deletePath: deleteHref?.(row),
    cells: renderedCells[rowIndex],
    sortKeys: columns.map((col) => col.sortAccessor?.(row) ?? null),
    searchText: valuesText(row).toLowerCase(),
    filterValues: filterValuesByRow[rowIndex],
  }));

  return (
    <InteractiveTableClient
      headerMeta={headerMeta}
      rows={renderedRows}
      emptyText={emptyText}
      filterable={filterable}
      columnFilters={columnFilters}
      onRowClick={onRowClick}
      openInModal={openInModal}
    />
  );
}
