"use client";

import {
  BadgeCheck,
  Car,
  CheckSquare,
  Clapperboard,
  ClipboardList,
  Contact,
  FileCheck2,
  Building2,
  FileSignature,
  FileText,
  FolderKanban,
  Globe,
  Hash,
  History,
  LayoutDashboard,
  LucideIcon,
  Megaphone,
  MessageSquare,
  Package,
  Repeat,
  Scissors,
  Send,
  Settings,
  ShieldCheck,
  Sparkles,
  Trophy,
  UserCheck,
  UserRound,
  Users,
  Wallet,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { NavItem, navGroups } from "@/lib/nav";

const ICONS: Record<string, LucideIcon> = {
  LayoutDashboard,
  Building2,
  Hash,
  FolderKanban,
  Users,
  UserRound,
  Scissors,
  UserCheck,
  Package,
  ClipboardList,
  Contact,
  Send,
  Clapperboard,
  Globe,
  Wallet,
  FileSignature,
  FileText,
  FileCheck2,
  BadgeCheck,
  History,
  Megaphone,
  MessageSquare,
  CheckSquare,
  Sparkles,
  Settings,
  Repeat,
  ShieldCheck,
  Car,
  Trophy,
};

/** allowedPages: az egyénenként beállított oldal-hozzáférés (lásd Beállítások) -
 * null = minden oldal látszik, egyébként csak azok, amiknek a permissionPage-e
 * (vagy ha az nincs megadva, a href-je) szerepel a listában - lásd
 * NavItem.permissionPage kommentje arról, miért nem elég a puszta URL első
 * szegmense. A tényleges belépés-blokkolást a middleware végzi, ez csak a
 * navigáció elrejtése.
 *
 * anyagKorlat: ha nem null, a felhasználó CSAK a rábízott utómunka-anyagokat
 * láthatja (külsős vágó fiókja) - neki a menüben egyáltalán nincs mire
 * navigálni: a Dashboard maga a teendő-listája, az anyag pedig felugró
 * ablakban nyílik (lásd KorlatozottDashboard). */
export function Sidebar({
  allowedPages,
  anyagKorlat = null,
}: {
  allowedPages: string[] | null;
  anyagKorlat?: number[] | null;
}) {
  const pathname = usePathname();

  function isAllowed(item: NavItem): boolean {
    const page = item.permissionPage ?? item.href;
    if (anyagKorlat !== null) return page === "/dashboard";
    if (!allowedPages) return true;
    return page === "/dashboard" || allowedPages.includes(page);
  }

  const visibleGroups = navGroups
    .map((group) => ({ ...group, items: group.items.filter((item) => isAllowed(item)) }))
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
    <aside className="hidden w-[248px] shrink-0 flex-col border-r border-border bg-surface-1 px-3 py-6 md:flex">
      <div className="mb-8 flex items-center gap-3 px-3">
        {/* A logó-jel egy matt titánlapka: nem világít, nem színez - csak
            jelöli, hol a rendszer eleje. */}
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[var(--radius)] border border-border-strong bg-surface-4 text-text-secondary">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
            <path
              d="M12 2 3 7v10l9 5 9-5V7l-9-5Z"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinejoin="round"
              // currentColor, nem fix fehér: világos nézetben a fehér kitöltés
              // eltűnne a világos lapkán (lásd globals.css data-theme="light").
              fill="currentColor"
              fillOpacity={0.08}
            />
            <path d="M3 7l9 5 9-5M12 12v10" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
          </svg>
        </div>
        <div className="min-w-0">
          <p className="text-[13px] font-semibold tracking-[-0.01em] text-text-primary">HYPE OS</p>
          <p className="mt-0.5 text-[11px] text-text-muted">HYPE Brain</p>
        </div>
      </div>

      <nav className="flex flex-1 flex-col gap-6 overflow-y-auto pb-4">
        {visibleGroups.map((group, idx) => (
          <div key={idx}>
            {group.label && (
              <p className="t-nav-group mb-2 px-3">{group.label}</p>
            )}
            <div className="flex flex-col gap-px">
              {group.items.map((item) => {
                const active = item.href === activeHref;
                const Icon = item.icon ? ICONS[item.icon] : undefined;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`relative flex items-center gap-2.5 rounded-[var(--radius)] px-3 py-[7px] text-[13px] transition-colors duration-200 ${
                      active
                        ? "bg-surface-3 font-medium text-text-primary"
                        : "text-text-secondary hover:bg-surface-2 hover:text-text-primary"
                    }`}
                  >
                    {/* Az aktív elem jelölése egy rövid függőleges vonal a bal
                        szélen - halkabb, mint egy kitöltött gomb, de görgetés
                        közben azonnal megtalálható. */}
                    {active && (
                      <span
                        aria-hidden
                        className="absolute left-0 top-1/2 h-4 w-[2px] -translate-y-1/2 rounded-full bg-text-accent"
                      />
                    )}
                    {Icon && (
                      <Icon
                        size={15}
                        strokeWidth={1.75}
                        className={active ? "text-text-secondary" : "text-text-muted"}
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
