"use client";

import { useMemo, useState, type ReactNode } from "react";
import { RowLink } from "@/components/RowLink";
import { DeleteButton } from "@/components/DeleteButton";

export type HeaderMeta = { header: string; align?: "left" | "right"; sortable: boolean };
export type RenderedRow = {
  id: number;
  href?: string;
  deletePath?: string;
  cells: ReactNode[];
  sortKeys: (string | number | null | undefined)[];
  searchText: string;
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
}: {
  headerMeta: HeaderMeta[];
  rows: RenderedRow[];
  emptyText: string;
  filterable: boolean;
}) {
  const [query, setQuery] = useState("");
  const [sortIndex, setSortIndex] = useState<number | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const filtered = useMemo(() => {
    if (!query.trim()) return rows;
    const needle = query.trim().toLowerCase();
    return rows.filter((row) => row.searchText.includes(needle));
  }, [rows, query]);

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
      {filterable && (
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Szűrés..."
          className="mb-2 w-full max-w-xs rounded-[var(--radius)] border border-border bg-surface-3 px-2.5 py-1.5 text-[13px] text-text-primary placeholder:text-text-muted focus:outline-none"
        />
      )}
      {sorted.length === 0 ? (
        <p className="text-[13px] text-text-muted">{query ? "Nincs találat a szűrésre." : emptyText}</p>
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
                if (row.href) {
                  return (
                    <RowLink key={row.id} href={row.href}>
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
    </div>
  );
}
