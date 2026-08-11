"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Clock, LayoutDashboard, TrendingDown, TrendingUp } from "lucide-react";

/** A Krumpello négy oldala. Szándékosan ennyi és nem több: ez a rész
 * kizárólag pénzügy - bevétel, kiadás, munkabér, és az, ami ezekből kijön. */
const OLDALAK = [
  { href: "/krumpello", label: "Áttekintés", Ikon: LayoutDashboard },
  { href: "/krumpello/bevetel", label: "Bevétel", Ikon: TrendingUp },
  { href: "/krumpello/kiadas", label: "Kiadás", Ikon: TrendingDown },
  { href: "/krumpello/munkaber", label: "Munkabér", Ikon: Clock },
];

export function KrumpelloNav() {
  const pathname = usePathname();
  // A leghosszabb egyező útvonal az aktív - így a "/krumpello/bevetel" nem
  // teszi aktívvá az "/krumpello" áttekintést is.
  const aktiv = OLDALAK.map((o) => o.href)
    .filter((h) => pathname === h || pathname.startsWith(h + "/"))
    .sort((a, b) => b.length - a.length)[0];

  return (
    <nav className="flex flex-col gap-1">
      {OLDALAK.map(({ href, label, Ikon }) => (
        <Link
          key={href}
          href={href}
          className={`flex items-center gap-2.5 rounded-[var(--radius)] px-3 py-2 text-[13px] transition-colors ${
            aktiv === href
              ? "bg-bg-accent font-medium text-text-accent"
              : "text-text-secondary hover:bg-surface-3 hover:text-text-primary"
          }`}
        >
          <Ikon size={15} />
          {label}
        </Link>
      ))}
    </nav>
  );
}
