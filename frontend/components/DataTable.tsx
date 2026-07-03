import type { ReactNode } from "react";
import { InteractiveTableClient } from "@/components/InteractiveTableClient";

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
  deleteHref,
}: {
  columns: Column<T>[];
  rows: T[];
  emptyText: string;
  getHref?: (row: T) => string;
  /** Szabadszavas keresőmező a táblázat felett. */
  filterable?: boolean;
  /** Ha meg van adva, minden sor végén egy törlés-gomb jelenik meg - a DELETE
   * végpont teljes útvonalát adja vissza (pl. `/api/v1/deliverables/42`). */
  deleteHref?: (row: T) => string;
}) {
  const headerMeta = columns.map((col) => ({ header: col.header, align: col.align, sortable: !!col.sortAccessor }));
  const renderedRows = rows.map((row) => ({
    id: row.id,
    href: getHref?.(row),
    deletePath: deleteHref?.(row),
    cells: columns.map((col) => col.render(row)),
    sortKeys: columns.map((col) => col.sortAccessor?.(row) ?? null),
    searchText: JSON.stringify(row).toLowerCase(),
  }));

  return <InteractiveTableClient headerMeta={headerMeta} rows={renderedRows} emptyText={emptyText} filterable={filterable} />;
}
