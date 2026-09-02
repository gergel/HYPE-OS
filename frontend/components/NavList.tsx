"use client";

import {
  BadgeCheck,
  Calculator,
  Car,
  CheckSquare,
  Clapperboard,
  ClipboardList,
  PackageOpen,
  Table,
  Coins,
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
  ListChecks,
  LucideIcon,
  Megaphone,
  MessageSquare,
  Package,
  Palette,
  Repeat,
  Scissors,
  Send,
  Settings,
  ShieldCheck,
  Sparkle,
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
import { oldalMuveletei } from "@/lib/permissions";

const ICONS: Record<string, LucideIcon> = {
  Calculator,
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
  PackageOpen,
  Table,
  Contact,
  Send,
  Clapperboard,
  Globe,
  Wallet,
  Coins,
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
  ListChecks,
  Palette,
  Sparkle,
};

/** A nav-elemek listája - a Sidebar (asztali oldalsáv) ÉS a MobileNav
 * (telefonos hamburger-fiók) is ezt használja, hogy a két felület sose
 * csússzon szét egymástól (lásd Sidebar.tsx és MobileNav.tsx). */
export function NavList({
  allowedPages,
  pagePermissions = null,
  anyagKorlat = null,
  onNavigate,
}: {
  allowedPages: string[] | null;
  pagePermissions?: Record<string, string[]> | null;
  anyagKorlat?: number[] | null;
  /** Mobil-fiókban a linkre kattintás után be kell csukni a fiókot - lásd
   * MobileNav.tsx. Az asztali oldalsávnál nincs mit tenni. */
  onNavigate?: () => void;
}) {
  const pathname = usePathname();

  function isAllowed(item: NavItem): boolean {
    const page = item.permissionPage ?? item.href;
    if (anyagKorlat !== null) return page === "/dashboard";
    if (!allowedPages) return true;
    if (page === "/dashboard") return true;
    if (!allowedPages.includes(page)) return false;
    if (item.permissionAction && pagePermissions !== null) {
      return oldalMuveletei(pagePermissions, page)?.has(item.permissionAction) === true;
    }
    return true;
  }

  const visibleGroups = navGroups
    .map((group) => ({ ...group, items: group.items.filter((item) => isAllowed(item)) }))
    .filter((group) => group.items.length > 0);

  const allHrefs = navGroups.flatMap((group) => group.items.map((item) => item.href));
  const activeHref = allHrefs
    .filter((href) => pathname === href || pathname.startsWith(href + "/"))
    .sort((a, b) => b.length - a.length)[0];

  return (
    <nav className="flex flex-1 flex-col gap-6 overflow-y-auto pb-4">
      {visibleGroups.map((group, idx) => (
        <div key={idx}>
          {group.label && <p className="t-nav-group mb-2 px-3">{group.label}</p>}
          <div className="flex flex-col gap-px">
            {group.items.map((item) => {
              const active = item.href === activeHref;
              const Icon = item.icon ? ICONS[item.icon] : undefined;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={onNavigate}
                  className={`relative flex items-center gap-2.5 rounded-[var(--radius)] px-3 py-2.5 text-[13px] transition-colors duration-200 md:py-[7px] ${
                    active
                      ? "bg-surface-3 font-medium text-text-primary"
                      : "text-text-secondary hover:bg-surface-2 hover:text-text-primary"
                  }`}
                >
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
  );
}
