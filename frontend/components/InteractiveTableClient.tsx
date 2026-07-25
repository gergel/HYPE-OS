"use client";

import { useMemo, useState, type ReactNode } from "react";
import { RowLink } from "@/components/RowLink";
import { DeleteButton } from "@/components/DeleteButton";
import { RecordDetailModal } from "@/components/RecordDetailModal";
import { TableFilterBuilder } from "@/components/TableFilterBuilder";
import { matchesAllRules, type ColumnKind, type FilterRule } from "@/lib/tableFilters";

export type HeaderMeta = { header: string; align?: "left" | "right"; sortable: boolean; kind: ColumnKind };
export type RenderedRow = {
  id: number;
  href?: string;
  deletePath?: string;
  cells: ReactNode[];
  sortKeys: (string | number | null | undefined)[];
  searchText: string;
  /** Oszloponkénti szöveges érték a mezőnkénti szűréshez (lásd DataTable). */
  filterValues: string[];
};

type SortDir = "asc" | "desc";

/** A DataTable szerver-oldalon előre renderelt celláit fogadja (nem függvényeket -
 * azok nem küldhetők át a szerver/kliens határon), és csak a rendezést/szűrést/
 * törlést kezeli kliens oldalon. */
export function InteractiveTableClient({
  headerMeta,
  rows,
  emptyText,
  filterable,
  columnFilters = true,
  onRowClick,
  openInModal = false,
}: {
  headerMeta: HeaderMeta[];
  rows: RenderedRow[];
  emptyText: string;
  filterable: boolean;
  /** Mezőnkénti szűrő-építő (lásd TableFilterBuilder). */
  columnFilters?: boolean;
  /** Ha meg van adva, sorra kattintáskor ez fut le (a sor id-jével) a
   * href-alapú navigáció HELYETT - lásd RowLink.tsx. */
  onRowClick?: (id: number) => void;
  /** A sor href-je felugró ablakban nyíljon meg, ne teljes oldalként (lásd
   * RecordDetailModal) - a kapcsolódó rekordok tábláinál ez az alapértelmezés,
   * hogy ne kelljen elnavigálni a nézett rekordról. */
  openInModal?: boolean;
}) {
  const [query, setQuery] = useState("");
  const [rules, setRules] = useState<FilterRule[]>([]);
  const [modalHref, setModalHref] = useState<string | null>(null);
  const [sortIndex, setSortIndex] = useState<number | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  // A szabadszavas kereső és a mezőnkénti szabályok EGYÜTT szűkítenek (a
  // felhasználó kérése: a szűrő-rendszer mellett a keresés is maradjon meg).
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle && rules.length === 0) return rows;
    return rows.filter(
      (row) => (!needle || row.searchText.includes(needle)) && matchesAllRules(row.filterValues, rules),
    );
  }, [rows, query, rules]);

  const sorted = useMemo(() => {
    if (sortIndex === null) return filtered;
    const copy = [...filtered];
    copy.sort((a, b) => {
      const ak = a.sortKeys[sortIndex];
      const bk = b.sortKeys[sortIndex];
      if (ak === null || ak === undefined) return 1;
      if (bk === null || bk === undefined) return -1;
      if (ak < bk) return sortDir === "asc" ? -1 : 1;
      if (ak > bk) return sortDir === "asc" ? 1 : -1;
      return 0;
    });
    return copy;
  }, [filtered, sortIndex, sortDir]);

  function toggleSort(index: number) {
    if (!headerMeta[index].sortable) return;
    if (sortIndex === index) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortIndex(index);
      setSortDir("asc");
    }
  }

  const hasDelete = rows.some((r) => r.deletePath);

  return (
    <div>
      {(filterable || columnFilters) && (
        <div className="mb-2 flex flex-wrap items-center gap-2">
          {filterable && (
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Keresés..."
              className="w-full max-w-xs rounded-[var(--radius)] border border-border bg-surface-3 px-2.5 py-1.5 text-[13px] text-text-primary placeholder:text-text-muted focus:outline-none"
            />
          )}
          {columnFilters && (
            <TableFilterBuilder
              columns={headerMeta.map((col) => ({ header: col.header, kind: col.kind }))}
              rules={rules}
              onChange={setRules}
            />
          )}
        </div>
      )}
      {sorted.length === 0 ? (
        <p className="text-[13px] text-text-muted">
          {query || rules.length > 0 ? "Nincs találat a szűrésre." : emptyText}
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-[13px]">
            <thead>
              <tr className="border-b border-border">
                {headerMeta.map((col, index) => (
                  <th
                    key={col.header}
                    onClick={() => toggleSort(index)}
                    className={`whitespace-nowrap py-1.5 font-medium text-text-secondary ${
                      col.align === "right" ? "text-right" : "text-left"
                    } ${col.sortable ? "cursor-pointer select-none hover:text-text-primary" : ""}`}
                  >
                    {col.header}
                    {col.sortable && sortIndex === index ? (sortDir === "asc" ? " ▲" : " ▼") : ""}
                  </th>
                ))}
                {hasDelete && <th className="w-8" />}
              </tr>
            </thead>
            <tbody>
              {sorted.map((row) => {
                const cells = row.cells.map((cell, i) => (
                  <td key={i} className={`py-2 pr-4 ${headerMeta[i]?.align === "right" ? "text-right" : "text-left"}`}>
                    {cell}
                  </td>
                ));
                if (hasDelete) {
                  cells.push(
                    <td key="__delete" className="py-2 text-right" onClick={(e) => e.stopPropagation()}>
                      {row.deletePath && <DeleteButton path={row.deletePath} />}
                    </td>,
                  );
                }
                if (row.href || onRowClick) {
                  const onClick = onRowClick
                    ? () => onRowClick(row.id)
                    : openInModal && row.href
                      ? () => setModalHref(row.href!)
                      : undefined;
                  return (
                    <RowLink key={row.id} href={row.href} onClick={onClick}>
                      {cells}
                    </RowLink>
                  );
                }
                return (
                  <tr key={row.id} className="border-b border-border last:border-0">
                    {cells}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <RecordDetailModal href={modalHref} onClose={() => setModalHref(null)} />
    </div>
  );
}
