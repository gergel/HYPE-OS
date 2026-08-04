"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, type LucideIcon } from "lucide-react";
import { CARD_CLASS } from "@/components/Card";

/** Ugyanaz a kártya, mint a Card, csak a címére kattintva összecsukható - a
 * hosszú, listás szekciókhoz (pl. a vágó havi bontású utómunka-ideje), hogy ne
 * tolják le a fontosabb adatokat az oldal aljára. */
export function CollapsibleCard({
  title,
  icon: Icon,
  defaultOpen = false,
  children,
  className = "",
}: {
  title: string;
  icon?: LucideIcon;
  defaultOpen?: boolean;
  children: React.ReactNode;
  className?: string;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className={`${CARD_CLASS} ${className}`}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className={`t-card flex w-full items-center gap-2 text-left transition-colors duration-200 ${open ? "mb-4" : ""}`}
      >
        {open ? <ChevronDown size={14} className="text-text-muted" /> : <ChevronRight size={14} className="text-text-muted" />}
        {Icon && <Icon size={14} strokeWidth={1.75} className="shrink-0 text-text-muted" aria-hidden />}
        {title}
      </button>
      {open && children}
    </div>
  );
}
