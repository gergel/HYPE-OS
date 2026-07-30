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
        className={`flex w-full items-center gap-1.5 text-left text-sm font-medium text-text-primary ${open ? "mb-3" : ""}`}
      >
        {open ? <ChevronDown size={14} className="text-text-muted" /> : <ChevronRight size={14} className="text-text-muted" />}
        {Icon && <Icon size={15} strokeWidth={2} className="text-text-accent" aria-hidden />}
        {title}
      </button>
      {open && children}
    </div>
  );
}
