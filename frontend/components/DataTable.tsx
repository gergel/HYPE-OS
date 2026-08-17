import { Fragment, isValidElement, type ReactNode } from "react";
import { InteractiveTableClient } from "@/components/InteractiveTableClient";
import type { ColumnKind } from "@/lib/tableFilters";

/** A már leredenderelt cella szöveges tartalma - ebből lesz a mezőnkénti
 * szűrés alapja (lásd TableFilterBuilder), hogy pontosan arra lehessen
 * szűrni, ami a cellában LÁTSZIK, és ne kelljen minden listaoldalon külön
 * szűrő-mezőket deklarálni.
 *
 * Három helyről szedjük ki a szöveget, ebben a sorrendben:
 *
 * 1. `children` - a szokásos eset;
 * 2. `label` - a StatusBadge-szerű komponensek így kapják a szövegüket;
 * 3. `value` (és üres értéknél a `placeholder`) - a HELYBEN SZERKESZTHETŐ
 *    cellák (EditableTableCell, EditableStatusBadge) így kapják.
 *
 * A harmadik nélkül a szűrő ott hallgatott, ahol a legtöbb oszlop szerkeszthető
 * cella: a Kiadások listáján a megnevezés, a nettó, a fizetési mód és az
 * állapot MIND ilyen, tehát az oszlop-szűrő egyáltalán nem talált semmit, és
 * legördülő értékkészletet sem tudott kínálni. Kívülről ez úgy néz ki, hogy
 * "a szűrő nem működik". */
function nodeToText(node: ReactNode): string {
  if (node === null || node === undefined || typeof node === "boolean") return "";
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(nodeToText).join(" ");
  if (isValidElement(node)) {
    const props = node.props as {
      children?: ReactNode;
      label?: ReactNode;
      value?: ReactNode;
      placeholder?: ReactNode;
    };
    const fromChildren = nodeToText(props.children);
    if (fromChildren.trim()) return fromChildren;
    const fromLabel = nodeToText(props.label);
    if (fromLabel.trim()) return fromLabel;
    const fromValue = nodeToText(props.value);
    if (fromValue.trim()) return fromValue;
    // Üres értéknél a cellában a helykitöltő látszik ("Nincs megadva"), tehát
    // a szűrőben is arra kell tudni szűrni.
    return nodeToText(props.placeholder);
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

/** Legfeljebb ennyi különböző értéknél kínálunk legördülő listát a szűrőben.
 * Efölött (pl. egy név-oszlopnál) a lista használhatatlan lenne, ott marad a
 * szabad szöveges beírás. */
const MAX_SZURO_OPCIO = 40;

/** Egy oszlop választható értékei a szűrőhöz: az oszlopban ténylegesen
 * előforduló, különböző értékek. Így az állapot-jellegű mezőknél nem kell
 * kitalálni, pontosan mit kell beírni - ki lehet választani a listából. */
function filterOptions(values: string[]): string[] | undefined {
  const kulonbozo = new Set<string>();
  for (const raw of values) {
    const value = raw.trim();
    if (!value || value === "–" || value === "-") continue;
    // A hosszú, szabad szövegek (leírás, megjegyzés) nem select-jellegűek.
    if (value.length > 60 || value.includes("\n")) return undefined;
    kulonbozo.add(value);
    if (kulonbozo.size > MAX_SZURO_OPCIO) return undefined;
  }
  if (kulonbozo.size === 0) return undefined;
  return [...kulonbozo].sort((a, b) => a.localeCompare(b, "hu"));
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
  // A cellák TÖMBBEN utaznak a kliens-komponensig, ezért kulcsot kapnak: egy
  // tömbben álló React-elem kulcs nélkül "Each child in a list should have a
  // unique key" figyelmeztetést ad a konzolon. Sima szövegnél ez nem látszik,
  // ezért csak akkor bukkant elő, amikor egy oszlop komponenst renderelt
  // (állapot-badge, jelzők) - a Fragment mindegyiket lefedi.
  const renderedCells = rows.map((row) =>
    columns.map((col, colIndex) => <Fragment key={colIndex}>{col.render(row)}</Fragment>),
  );
  // A szűrés ARRA fut, AMI A CELLÁBAN LÁTSZIK - ez a szűrő egész működésének
  // alapelve (lásd lib/tableFilters fejléc-kommentje).
  //
  // Korábban a sortAccessor értéke élvezett elsőbbséget, "mert az a nyers
  // érték". Ez viszont pont az állapot-oszlopokat rontotta el: ott a
  // sortAccessor csak RENDEZÉSI kulcs (pl. `kesz ? 1 : 0`), aminek semmi köze
  // a kiírt szöveghez - a felhasználó "Kifizetve"-t látott, de az "1"-re
  // kellett volna szűrnie, amit sehonnan nem tudhatott. Ezért a látható szöveg
  // az elsődleges, és a sortAccessor csak akkor jön, ha a cella szövege üres
  // (pl. tisztán ikonnal jelölt érték).
  const filterValuesByRow = rows.map((row, rowIndex) =>
    columns.map((col, colIndex) => {
      const text = nodeToText(renderedCells[rowIndex][colIndex]).trim();
      if (text) return text;
      const sortValue = col.sortAccessor?.(row);
      return sortValue === null || sortValue === undefined ? "" : String(sortValue);
    }),
  );
  const headerMeta = columns.map((col, colIndex) => {
    const ertekek = filterValuesByRow.map((values) => values[colIndex]);
    return {
      header: col.header,
      align: col.align,
      sortable: !!col.sortAccessor,
      kind: columnKind(ertekek),
      options: filterOptions(ertekek),
    };
  });
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
