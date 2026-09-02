"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AnchoredPanel } from "@/components/AnchoredPanel";
import { selectColor } from "@/lib/selectColor";

export type IdOption = { id: number; label: string; sublabel?: string | null; group?: string | null };

const UNGROUPED = "__ungrouped__";

/** Csoport szerint rendezett, de az egyes csoportokon belül az eredeti
 * sorrendet megtartó lista - a csoport-fejlécek (pl. eszköz-kategóriák)
 * ugyanabban a sorrendben jelennek meg, ahogy a csoport első tagja
 * szerepelt az `options` listában. Csoport nélküli elemek (group=null/
 * undefined) egyetlen, fejléc nélküli "egyéb" blokkba kerülnek a végén. */
function groupOptions(options: IdOption[]): { group: string | null; items: IdOption[] }[] {
  const order: string[] = [];
  const byGroup = new Map<string, IdOption[]>();
  for (const opt of options) {
    const key = opt.group?.trim() || UNGROUPED;
    if (!byGroup.has(key)) {
      byGroup.set(key, []);
      order.push(key);
    }
    byGroup.get(key)!.push(opt);
  }
  const result: { group: string | null; items: IdOption[] }[] = order
    .filter((key) => key !== UNGROUPED)
    .map((key) => ({ group: key, items: byGroup.get(key)! }));
  if (byGroup.has(UNGROUPED)) result.push({ group: null, items: byGroup.get(UNGROUPED)! });
  return result;
}

/** Ugyanaz a kattintásra-azonnal-nyíló, kereshető felugró UI, mint a
 * SelectDropdown-nál (lásd components/SelectDropdown.tsx), csak nem egy
 * rögzített string-készletből választunk (pl. állapot), hanem ID-vel
 * azonosított rekordokból (pl. eszköz) - ezért külön komponens, nem a
 * SelectDropdown bővítése, hogy az (list- és részletnézeteken már bevált)
 * string-alapú komponens API-ját ne kelljen módosítani. */
export function SearchableIdPicker({
  value,
  options,
  onChange,
  placeholder = "Válassz…",
  disabled = false,
  className = "",
  colorByGroup = false,
  keepOpenOnSelect = false,
}: {
  value: number | null;
  options: IdOption[];
  onChange: (next: number | null) => void;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  /** A sorok színét a CSOPORT (pl. eszköz-kategória: hang, kamera…) adja, ne
   * az elem saját neve - így az azonos kategóriájú elemek azonos színűek. */
  colorByGroup?: boolean;
  /** Választás után a lista NYITVA marad (és a keresőszó is megmarad) - ahol
   * a kattintás azonnali műveletet indít (pl. eszköz hozzáadása a
   * projekthez), ott így egymás után több elem is kattintható. */
  keepOpenOnSelect?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const close = useCallback(() => {
    setOpen(false);
    setQuery("");
  }, []);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  const current = options.find((o) => o.id === value) ?? null;
  const filtered = query.trim()
    ? options.filter((o) => o.label.toLowerCase().includes(query.trim().toLowerCase()))
    : options;
  const groupedFiltered = groupOptions(filtered);

  const szine = (opt: IdOption) => selectColor((colorByGroup && opt.group?.trim()) || opt.label);
  const color = current ? szine(current) : { bg: "var(--surface-3)", text: "var(--text-muted)" };

  function select(next: number | null) {
    onChange(next);
    if (keepOpenOnSelect) return;
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
        <span className="truncate">{current?.label ?? placeholder}</span>
      </button>
      {open && (
        <AnchoredPanel anchorRef={containerRef} onClose={close} width={288}>
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
                if (e.key === "Enter" && filtered.length === 1) select(filtered[0].id);
              }}
              placeholder={current?.label ?? placeholder}
              className="min-w-0 flex-1 bg-transparent text-[13px] outline-none placeholder:opacity-70"
              style={{ color: color.text }}
            />
          </div>
          <div className="space-y-2">
            {groupedFiltered.map(({ group, items }) => (
              <div key={group ?? UNGROUPED}>
                {group && (
                  <p className="mb-1 px-1 text-[10px] font-semibold uppercase tracking-wide text-text-muted">{group}</p>
                )}
                <div className="space-y-1">
                  {items.map((opt) => {
                    const c = szine(opt);
                    return (
                      <button
                        key={opt.id}
                        type="button"
                        onClick={() => select(opt.id)}
                        className="flex w-full items-center gap-1.5 rounded-full px-2.5 py-1 text-left text-[13px] hover:opacity-80"
                        style={{ background: c.bg, color: c.text }}
                      >
                        <span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: c.text }} />
                        <span className="truncate">{opt.label}</span>
                        {opt.sublabel && <span className="ml-auto shrink-0 text-[11px] opacity-70">{opt.sublabel}</span>}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
            {filtered.length === 0 && <p className="p-2 text-[12px] text-text-muted">Nincs találat.</p>}
          </div>
        </AnchoredPanel>
      )}
    </div>
  );
}
