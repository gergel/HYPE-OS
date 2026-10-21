"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const FULEK = [
  { href: "/arajanlatok", label: "Ajánlatok" },
  { href: "/arajanlatok/katalogus", label: "Katalógus" },
  { href: "/arajanlatok/sablonok", label: "Sablonok" },
  { href: "/arajanlatok/regi", label: "Régi ajánlatok" },
];

/** Az Árajánlatok aloldalai közti navigáció. Az ajánlat-szerkesztő
 * (/arajanlatok/[id]) az „Ajánlatok” fül alá tartozik. */
export function ArajanlatFulek() {
  const path = usePathname();
  const tobbi = FULEK.slice(1).map((f) => f.href);
  return (
    <nav className="-mx-1 mb-4 flex gap-1 overflow-x-auto px-1 print:hidden">
      {FULEK.map((f) => {
        const aktiv =
          f.href === "/arajanlatok"
            ? !tobbi.some((t) => path === t || path.startsWith(t + "/"))
            : path === f.href || path.startsWith(f.href + "/");
        return (
          <Link
            key={f.href}
            href={f.href}
            className={`whitespace-nowrap rounded-[var(--radius)] border px-3 py-1.5 text-[13px] transition-colors ${
              aktiv ? "border-border bg-surface-3 text-text-primary" : "border-transparent text-text-secondary hover:bg-surface-2"
            }`}
          >
            {f.label}
          </Link>
        );
      })}
    </nav>
  );
}
