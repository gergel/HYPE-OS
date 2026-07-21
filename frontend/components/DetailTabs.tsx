"use client";

import { useState, type ReactNode } from "react";

export type DetailTab = { key: string; label: string; badge?: number; content: ReactNode };

/** Fület-navigáció egy részletnézeten belül - a mezőket/kapcsolódó
 * kártyákat témák szerint csoportosítja (Áttekintés/Diszpó/Technika/stb.),
 * hogy egy sok mezős entitás (pl. Projekt, ~140 oszlop) ne egy végtelen
 * hosszú, egyben görgetendő listaként jelenjen meg. A nem aktív fülek
 * tartalma a DOM-ban marad (csak elrejtve), hogy fül-váltáskor ne vesszen el
 * egy éppen folyamatban lévő szerkesztés állapota. */
export function DetailTabs({ tabs, defaultTab }: { tabs: DetailTab[]; defaultTab?: string }) {
  const [active, setActive] = useState(defaultTab ?? tabs[0]?.key);

  return (
    <div>
      <div className="mb-5 flex gap-1 overflow-x-auto border-b border-border">
        {tabs.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setActive(t.key)}
            className={`flex shrink-0 items-center gap-1.5 border-b-2 px-3 py-2 text-[13px] transition-colors ${
              active === t.key
                ? "border-text-accent text-text-primary"
                : "border-transparent text-text-secondary hover:text-text-primary"
            }`}
          >
            {t.label}
            {typeof t.badge === "number" && t.badge > 0 && (
              <span className="rounded-full bg-surface-3 px-1.5 py-0.5 text-[11px] text-text-muted">{t.badge}</span>
            )}
          </button>
        ))}
      </div>
      {tabs.map((t) => (
        <div key={t.key} className={active === t.key ? "space-y-6" : "hidden"}>
          {t.content}
        </div>
      ))}
    </div>
  );
}
