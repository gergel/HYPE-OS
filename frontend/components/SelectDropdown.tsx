"use client";

import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
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
}: {
  value: string | null;
  options: string[];
  onChange: (next: string | null) => void;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
        setQuery("");
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  const filtered = query.trim() ? options.filter((o) => o.toLowerCase().includes(query.trim().toLowerCase())) : options;
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
        <div className="absolute left-0 top-full z-50 mt-1 w-64 rounded-[var(--radius-lg)] border border-border bg-surface-2 p-2 shadow-xl">
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
                if (e.key === "Escape") {
                  setOpen(false);
                  setQuery("");
                }
                if (e.key === "Enter" && filtered.length === 1) select(filtered[0]);
              }}
              placeholder={value ?? placeholder}
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
          <div className="max-h-64 space-y-1 overflow-y-auto">
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
            {filtered.length === 0 && <p className="p-2 text-[12px] text-text-muted">Nincs találat.</p>}
          </div>
        </div>
      )}
    </div>
  );
}
