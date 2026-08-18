"use client";

import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { RowLink } from "@/components/RowLink";
import { DeleteButton } from "@/components/DeleteButton";
import { RecordDetailModal } from "@/components/RecordDetailModal";
import { TableFilterBuilder } from "@/components/TableFilterBuilder";
import { matchesAllRules, type ColumnKind, type FilterRule } from "@/lib/tableFilters";

export type HeaderMeta = {
  header: string;
  align?: "left" | "right";
  sortable: boolean;
  kind: ColumnKind;
  /** Az oszlopban előforduló értékek - ezekből lehet a szűrőben legördülő
   * listából választani (lásd DataTable filterOptions). */
  options?: string[];
};
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

/** Ennyi sort teszünk ki egyszerre a képernyőre, és ennyivel bővítünk, amikor
 * a lista aljára ér a görgetés.
 *
 * Miért? Mert egy 800 soros táblázat 800 × 9 = 7200 cellát jelent, és a
 * cellák nagy része önálló, kattintható komponens (helyben szerkeszthető mező,
 * állapot-badge). Ezeket egyszerre a képernyőre tenni másodperceket vesz el a
 * megnyitáskor, pedig az első képernyőn 15-20 sor látszik. A rendezés és a
 * szűrés viszont TELJES listán fut - csak a megjelenítés lépeget. */
const ABLAK_MERET = 80;

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

  // A képernyőre ténylegesen kitett sorok száma (lásd ABLAK_MERET). Szűrésre/
  // rendezésre visszaáll az elejére: az új sorrend eleje az, ami érdekes.
  // (Renderelés közbeni állapot-igazítás, nem effect: így nincs egy fölösleges
  // kör, amiben még a régi ablakmérettel rajzolnánk ki a listát.)
  const [latszik, setLatszik] = useState(ABLAK_MERET);
  const nezetKulcs = `${query}|${sortIndex}|${sortDir}|${JSON.stringify(rules)}`;
  const [elozoKulcs, setElozoKulcs] = useState(nezetKulcs);
  if (nezetKulcs !== elozoKulcs) {
    setElozoKulcs(nezetKulcs);
    setLatszik(ABLAK_MERET);
  }

  const megjelenitett = sorted.length > latszik ? sorted.slice(0, latszik) : sorted;
  const vanMeg = sorted.length > megjelenitett.length;

  // A lista aljára görgetve magától bővül - "Továbbiak" gombot nem kell nyomni.
  const orszem = useRef<HTMLTableRowElement | null>(null);
  useEffect(() => {
    const elem = orszem.current;
    if (!elem || !vanMeg) return;
    const figyelo = new IntersectionObserver(
      (bejegyzesek) => {
        if (bejegyzesek.some((b) => b.isIntersecting)) setLatszik((n) => n + ABLAK_MERET);
      },
      { rootMargin: "300px" },
    );
    figyelo.observe(elem);
    return () => figyelo.disconnect();
  }, [vanMeg, megjelenitett.length]);

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
        <div className="mb-4 flex flex-wrap items-center gap-2">
          {filterable && (
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Keresés..."
              className="field w-full max-w-[260px]"
            />
          )}
          {columnFilters && (
            <TableFilterBuilder
              columns={headerMeta.map((col) => ({ header: col.header, kind: col.kind, options: col.options }))}
              rules={rules}
              onChange={setRules}
            />
          )}
        </div>
      )}
      {sorted.length === 0 ? (
        <p className="py-8 text-center text-[13px] text-text-muted">
          {query || rules.length > 0 ? "Nincs találat a szűrésre." : emptyText}
        </p>
      ) : (
        /* A táblázat saját, korlátozott magasságú görgető-kerete: így a
           fejléc megtapadhat, és hosszú listánál is látszik, melyik oszlopot
           nézzük - enélkül a fejléc kigörgött a képernyő tetején. */
        <div className="-mx-1 max-h-[70vh] overflow-auto px-1">
          <table className="os-table w-full border-collapse text-[13px]">
            <thead>
              <tr>
                {headerMeta.map((col, index) => (
                  <th
                    key={col.header}
                    onClick={() => toggleSort(index)}
                    className={`whitespace-nowrap ${col.align === "right" ? "text-right" : "text-left"} ${
                      col.sortable ? "cursor-pointer select-none hover:text-text-secondary" : ""
                    } ${sortIndex === index ? "text-text-secondary" : ""}`}
                  >
                    {col.header}
                    {col.sortable && sortIndex === index ? (sortDir === "asc" ? " ↑" : " ↓") : ""}
                  </th>
                ))}
                {hasDelete && <th className="w-8" />}
              </tr>
            </thead>
            <tbody>
              {megjelenitett.map((row) => {
                const cells = row.cells.map((cell, i) => (
                  <td key={i} className={headerMeta[i]?.align === "right" ? "text-right" : "text-left"}>
                    {cell}
                  </td>
                ));
                if (hasDelete) {
                  cells.push(
                    <td key="__delete" className="pr-0 text-right" onClick={(e) => e.stopPropagation()}>
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
                  <tr key={row.id}>
                    {cells}
                  </tr>
                );
              })}
              {vanMeg && (
                <tr ref={orszem}>
                  <td colSpan={headerMeta.length + (hasDelete ? 1 : 0)} className="py-3 text-center text-[12px] text-text-muted">
                    További {sorted.length - megjelenitett.length} sor betöltése…
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
      {/* Csak akkor írunk ki bármit, ha az információt hordoz: szűrés van, vagy
          nem fér ki minden sor. Egy 5 soros táblázat alá nem kell odaírni,
          hogy 5 sor. */}
      {(vanMeg || sorted.length !== rows.length) && sorted.length > 0 && (
        <p className="mt-2 text-[12px] text-text-muted">
          {sorted.length !== rows.length
            ? `${sorted.length} találat (összesen ${rows.length})`
            : `${rows.length} sor`}
          {vanMeg ? ` · ${megjelenitett.length} látszik, a többi görgetve töltődik` : ""}
        </p>
      )}
      <RecordDetailModal href={modalHref} onClose={() => setModalHref(null)} />
    </div>
  );
}
