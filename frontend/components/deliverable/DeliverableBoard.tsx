"use client";

import { useState } from "react";
import { selectColor } from "@/lib/selectColor";

export type BoardCard = {
  id: number;
  href: string;
  title: string;
  subtitle?: string | null;
  badges: string[];
};

export type BoardColumn = { key: string; label: string; cards: BoardCard[] };

const PAGE_SIZE = 10;

function BoardCardView({ card }: { card: BoardCard }) {
  return (
    <a
      href={card.href}
      className="block rounded-[var(--radius)] border border-border bg-surface-3 p-2.5 text-[13px] hover:bg-surface-2"
    >
      <p className="font-medium text-text-primary">{card.title}</p>
      {card.subtitle && <p className="mt-0.5 text-[12px] text-text-muted">{card.subtitle}</p>}
      {card.badges.length > 0 && (
        <div className="mt-1.5 flex flex-wrap gap-1">
          {card.badges.map((b) => (
            <span
              key={b}
              className="rounded px-1.5 py-0.5 text-[11px]"
              style={{ background: selectColor(b).bg, color: selectColor(b).text }}
            >
              {b}
            </span>
          ))}
        </div>
      )}
    </a>
  );
}

/** Egyetlen oszlop - alapból legfeljebb 10 kártyát mutat, hogy egy nagy
 * csoportnál (pl. sok "Aktuális" állapotú anyag) ne kelljen egyszerre száz
 * sort görgetni - "további megjelenítése" nyitja ki a többit. */
function BoardColumnView({ column }: { column: BoardColumn }) {
  const [expanded, setExpanded] = useState(false);
  const visible = expanded ? column.cards : column.cards.slice(0, PAGE_SIZE);
  const remaining = column.cards.length - visible.length;

  return (
    <div className="flex w-72 shrink-0 flex-col rounded-[var(--radius-lg)] border border-border bg-surface-3 p-3">
      <p className="mb-2 text-[13px] font-medium text-text-primary">
        {column.label} <span className="text-text-muted">({column.cards.length})</span>
      </p>
      <div className="flex flex-col gap-2">
        {visible.length === 0 && <p className="text-[12px] text-text-muted italic">Üres.</p>}
        {visible.map((card) => (
          <BoardCardView key={card.id} card={card} />
        ))}
      </div>
      {remaining > 0 && (
        <button
          type="button"
          onClick={() => setExpanded(true)}
          className="mt-2 text-left text-[12px] text-text-accent hover:underline"
        >
          {remaining} további megjelenítése
        </button>
      )}
    </div>
  );
}

/** Kanban-szerű táblanézet (állapot vagy vinyó szerint csoportosított
 * oszlopok) - a vágóknak, hogy ne a nyers adattáblát/lista-nézetet kelljen
 * böngészniük, hanem egyben lássák, mi hol tart. Ugyanez a komponens adja az
 * "Állapot szerint" és a "Vinyók szerint" nézetet is (lásd Utómunka oldal),
 * csak az oszlopok csoportosítási kulcsa más. */
export function DeliverableBoard({ columns }: { columns: BoardColumn[] }) {
  if (columns.length === 0) {
    return <p className="text-[13px] text-text-muted">Nincs megjeleníthető anyag.</p>;
  }
  return (
    <div className="flex gap-3 overflow-x-auto pb-2">
      {columns.map((col) => (
        <BoardColumnView key={col.key} column={col} />
      ))}
    </div>
  );
}
