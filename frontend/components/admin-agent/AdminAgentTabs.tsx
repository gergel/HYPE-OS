"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const FULEK = [
  { href: "/admin-agent", label: "Áttekintés" },
  { href: "/admin-agent/munkasor", label: "Munkasor" },
  { href: "/admin-agent/jovahagyasok", label: "Jóváhagyások" },
  { href: "/admin-agent/tudastar", label: "Tudástár" },
  { href: "/admin-agent/tudashalo", label: "Tudásháló" },
  { href: "/admin-agent/tanulas", label: "Tanulás és minőség" },
  { href: "/admin-agent/naplo", label: "Napló" },
  { href: "/admin-agent/beallitasok", label: "Beállítások" },
];

/** A HYRON aloldalak közti navigáció (a meglévő sötét design tokenekkel). */
export function AdminAgentTabs() {
  const path = usePathname();
  return (
    <nav className="-mx-1 mb-4 flex gap-1 overflow-x-auto px-1">
      {FULEK.map((f) => {
        const aktiv = f.href === "/admin-agent" ? path === f.href : path === f.href || path.startsWith(f.href + "/");
        return (
          <Link
            key={f.href}
            href={f.href}
            className={`whitespace-nowrap rounded-[var(--radius)] border px-3 py-1.5 text-[13px] transition-colors ${
              aktiv
                ? "border-border bg-surface-3 text-text-primary"
                : "border-transparent text-text-secondary hover:bg-surface-2"
            }`}
          >
            {f.label}
          </Link>
        );
      })}
    </nav>
  );
}
