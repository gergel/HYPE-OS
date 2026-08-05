"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Plus, X } from "lucide-react";
import { AnchoredPanel } from "@/components/AnchoredPanel";
import { selectColor } from "@/lib/selectColor";

/** Notion-stílusú select mező: kattintásra AZONNAL megnyílik egy lebegő
 * panel (nem egy natív böngésző-<select>, aminek a megnyitása böngészőnként/
 * OS-enként eltérően viselkedik, és nem stílusozható) - a panel tetején egy
 * szövegmező mutatja/szűri az opciókat, alatta színes "pill" alakban minden
 * lehetőség egyenként kattintható. Ugyanaz a komponens adja az összes select-
 * jellegű mező interakcióját az appban (lásd EditableStatusBadge lista-
 * nézetekben, EditableDetailGrid select mezői a részletnézeteken). */
export function SelectDropdown({
  value,
  options,
  onChange,
  placeholder = "Üres",
  disabled = false,
  className = "",
  allowNew = false,
}: {
  value: string | null;
  options: string[];
  onChange: (next: string | null) => void;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  /** Ha igaz, a listán kívüli érték is megadható: a kereső mezőbe beírt új
   * szöveg egy "hozzáadása" gombbal (vagy Enterrel) rögtön beállítható. Olyan
   * mezőkhöz, amiknek van kialakult értékkészlete, de az nem zárt - pl.
   * "megbízás tárgya" (lásd backend entity_registry.NYITOTT_SELECT_MEZOK). */
  allowNew?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // A panelen kívülre kattintás kezelését az AnchoredPanel végzi (a panel a
  // portál miatt már nincs a containerRef-en belül).
  const close = useCallback(() => {
    setOpen(false);
    setQuery("");
  }, []);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  const filtered = query.trim() ? options.filter((o) => o.toLowerCase().includes(query.trim().toLowerCase())) : options;
  const ujErtek = query.trim();
  // Új értéket csak akkor kínálunk, ha tényleg új: a már meglévő opciót
  // (kis/nagybetűtől függetlenül) a listából kell választani, hogy ne
  // keletkezzen két, csak írásmódban eltérő változat ugyanabból.
  const felvehetoUj =
    allowNew && ujErtek.length > 0 && !options.some((o) => o.toLowerCase() === ujErtek.toLowerCase());
  const color = value ? selectColor(value) : { bg: "var(--surface-3)", text: "var(--text-muted)" };

  function select(next: string | null) {
    onChange(next);
    setOpen(false);
    setQuery("");
  }

  return (
    <div ref={containerRef} className={`relative inline-block ${className}`} onClick={(e) => e.stopPropagation()}>
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((o) => !o)}
        className="inline-flex w-full items-center gap-1.5 rounded-full py-1 pl-2.5 pr-2 text-left text-[13px] font-medium disabled:opacity-50"
        style={{ background: color.bg, color: color.text }}
      >
        <span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: color.text }} />
        <span className="truncate">{value ?? placeholder}</span>
      </button>

      {open && (
        <AnchoredPanel anchorRef={containerRef} onClose={close} width={256}>
          <div
            className="mb-2 flex items-center gap-1.5 rounded-full py-1 pl-2.5 pr-2 text-[13px]"
            style={{ background: color.bg, color: color.text }}
          >
            <span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: color.text }} />
            <input
              ref={inputRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Escape") close();
                if (e.key === "Enter") {
                  if (filtered.length === 1) select(filtered[0]);
                  else if (felvehetoUj) select(ujErtek);
                }
              }}
              placeholder={value ?? (allowNew ? "Válassz vagy írj újat" : placeholder)}
              className="min-w-0 flex-1 bg-transparent text-[13px] outline-none placeholder:opacity-70"
              style={{ color: color.text }}
            />
            {value && (
              <button
                type="button"
                onClick={() => select(null)}
                className="shrink-0 opacity-70 hover:opacity-100"
                aria-label="Törlés"
              >
                <X size={12} />
              </button>
            )}
          </div>
          <div className="space-y-1">
            {filtered.map((opt) => {
              const c = selectColor(opt);
              return (
                <button
                  key={opt}
                  type="button"
                  onClick={() => select(opt)}
                  className="flex w-full items-center gap-1.5 rounded-full px-2.5 py-1 text-left text-[13px] hover:opacity-80"
                  style={{ background: c.bg, color: c.text }}
                >
                  <span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: c.text }} />
                  {opt}
                </button>
              );
            })}
            {felvehetoUj && (
              <button
                type="button"
                onClick={() => select(ujErtek)}
                className="flex w-full items-center gap-1.5 rounded-full border border-dashed border-border-strong px-2.5 py-1 text-left text-[13px] text-text-secondary hover:bg-surface-3"
              >
                <Plus size={12} className="shrink-0" />
                <span className="truncate">„{ujErtek}" hozzáadása</span>
              </button>
            )}
            {filtered.length === 0 && !felvehetoUj && (
              <p className="p-2 text-[12px] text-text-muted">
                {allowNew ? "Írj be egy új értéket." : "Nincs találat."}
              </p>
            )}
          </div>
        </AnchoredPanel>
      )}
    </div>
  );
}
