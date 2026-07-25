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
  onRowClick,
  openInModal = false,
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
  /** Ha meg van adva, sorra kattintáskor ez fut le a sor id-jével a getHref
   * szerinti navigáció HELYETT (pl. felugró ablakban való megnyitáshoz). */
  onRowClick?: (id: number) => void;
  /** A getHref szerinti cél felugró ablakban nyíljon meg, ne teljes oldalként
   * (lásd RecordDetailModal) - a kapcsolódó rekordok tábláinál ez az
   * alapértelmezés, lásd RelatedTable. */
  openInModal?: boolean;
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

  return (
    <InteractiveTableClient
      headerMeta={headerMeta}
      rows={renderedRows}
      emptyText={emptyText}
      filterable={filterable}
      onRowClick={onRowClick}
      openInModal={openInModal}
    />
  );
}
