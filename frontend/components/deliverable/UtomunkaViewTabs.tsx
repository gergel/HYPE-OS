"use client";

import { useState, type ReactNode } from "react";

/** Két nézet közti váltó az Utómunka oldalon - "Vágó nézet" (tábla + naptár,
 * alapértelmezett) és "Admin lista" (a régi, nyers adattáblás nézet). A nem
 * aktív nézetet csak elrejtjük (nem szedjük ki a DOM-ból), hogy a tábla
 * oszlopainak "további megjelenítése" állapota megmaradjon váltás közben. */
export function UtomunkaViewTabs({ board, list }: { board: ReactNode; list: ReactNode }) {
  const [tab, setTab] = useState<"board" | "list">("board");

  return (
    <div>
      <div className="mb-4 flex gap-2">
        <button
          type="button"
          onClick={() => setTab("board")}
          className={`rounded-[var(--radius)] px-3 py-1.5 text-[13px] ${
            tab === "board" ? "bg-surface-3 text-text-primary" : "text-text-secondary hover:bg-surface-3"
          }`}
        >
          Vágó nézet
        </button>
        <button
          type="button"
          onClick={() => setTab("list")}
          className={`rounded-[var(--radius)] px-3 py-1.5 text-[13px] ${
            tab === "list" ? "bg-surface-3 text-text-primary" : "text-text-secondary hover:bg-surface-3"
          }`}
        >
          Admin lista
        </button>
      </div>
      <div className={tab === "board" ? "" : "hidden"}>{board}</div>
      <div className={tab === "list" ? "" : "hidden"}>{list}</div>
    </div>
  );
}
