"use client";

import {
  BadgeCheck,
  CheckSquare,
  Clapperboard,
  ClipboardList,
  FileCheck2,
  FileSignature,
  FolderKanban,
  Globe,
  Hash,
  History,
  LayoutDashboard,
  LucideIcon,
  Megaphone,
  Package,
  Scissors,
  Send,
  Settings,
  Sparkles,
  UserCheck,
  UserRound,
  Users,
  Wallet,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { navGroups } from "@/lib/nav";

const ICONS: Record<string, LucideIcon> = {
  LayoutDashboard,
  Hash,
  FolderKanban,
  Users,
  UserRound,
  Scissors,
  UserCheck,
  Package,
  ClipboardList,
  Send,
  Clapperboard,
  Globe,
  Wallet,
  FileSignature,
  FileCheck2,
  BadgeCheck,
  History,
  Megaphone,
  CheckSquare,
  Sparkles,
  Settings,
};

/** allowedPages: az egyénenként beállított oldal-hozzáférés (lásd Beállítások) -
 * null = minden oldal látszik, egyébként csak azok, amiknek a href-jének első
 * útvonal-szegmense (pl. "/projektek") szerepel a listában. A tényleges
 * belépés-blokkolást a middleware végzi, ez csak a navigáció elrejtése. */
export function Sidebar({ allowedPages }: { allowedPages: string[] | null }) {
  const pathname = usePathname();

  function isAllowed(href: string): boolean {
    if (!allowedPages) return true;
    const topSegment = "/" + href.split("/").filter(Boolean)[0];
    return topSegment === "/dashboard" || allowedPages.includes(topSegment);
  }

  const visibleGroups = navGroups
    .map((group) => ({ ...group, items: group.items.filter((item) => isAllowed(item.href)) }))
    .filter((group) => group.items.length > 0);

  // Csak a LEGSPECIFIKUSABB (leghosszabb) egyező href legyen aktív - enélkül
  // pl. "/penzugyek/keretszerzodesek"-en a "Pénzügyek" (href "/penzugyek")
  // ÉS a "Keretszerződések" is aktívnak látszana egyszerre, mert mindkettő
  // előtagja az útvonalnak.
  const allHrefs = navGroups.flatMap((group) => group.items.map((item) => item.href));
  const activeHref = allHrefs
    .filter((href) => pathname === href || pathname.startsWith(href + "/"))
    .sort((a, b) => b.length - a.length)[0];

  return (
    <aside className="hidden w-64 shrink-0 flex-col border-r border-border bg-surface-1 p-4 md:flex">
      <div className="mb-6 flex items-center gap-2.5 px-2">
        <div
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[var(--radius)] text-white"
          style={{ background: "var(--accent-gradient)" }}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
            <path
              d="M12 2 3 7v10l9 5 9-5V7l-9-5Z"
              stroke="white"
              strokeWidth="1.6"
              strokeLinejoin="round"
              fill="rgba(255,255,255,0.14)"
            />
            <path d="M3 7l9 5 9-5M12 12v10" stroke="white" strokeWidth="1.6" strokeLinejoin="round" />
          </svg>
        </div>
        <div>
          <p className="text-sm font-semibold tracking-tight text-text-primary">HYPE OS</p>
          <p className="text-[11px] text-text-muted">HYPE Brain</p>
        </div>
      </div>

      <nav className="flex flex-1 flex-col gap-5 overflow-y-auto">
        {visibleGroups.map((group, idx) => (
          <div key={idx}>
            {group.label && (
              <p className="mb-1.5 px-2.5 text-[11px] font-medium uppercase tracking-wide text-text-muted">
                {group.label}
              </p>
            )}
            <div className="flex flex-col gap-0.5">
              {group.items.map((item) => {
                const active = item.href === activeHref;
                const Icon = item.icon ? ICONS[item.icon] : undefined;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`flex items-center gap-2.5 rounded-[var(--radius)] px-2.5 py-1.5 text-[13px] transition-colors ${
                      active
                        ? "text-white shadow-[0_4px_14px_-4px_rgba(124,92,255,0.55)]"
                        : "text-text-secondary hover:bg-surface-2 hover:text-text-primary"
                    }`}
                    style={active ? { background: "var(--accent-gradient)" } : undefined}
                  >
                    {Icon && (
                      <Icon
                        size={15}
                        strokeWidth={2}
                        className={active ? "text-white" : "text-text-muted"}
                        aria-hidden
                      />
                    )}
                    <span className="truncate">{item.label}</span>
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>
    </aside>
  );
}
