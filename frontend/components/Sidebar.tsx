"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { navGroups } from "@/lib/nav";

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden w-60 shrink-0 flex-col border-r border-border bg-surface-1 p-4 md:flex">
      <div className="mb-6 px-2">
        <p className="text-sm font-semibold tracking-tight text-text-primary">HYPE OS</p>
        <p className="text-[11px] text-text-muted">HYPE Brain</p>
      </div>

      <nav className="flex flex-1 flex-col gap-5 overflow-y-auto">
        {navGroups.map((group, idx) => (
          <div key={idx}>
            {group.label && (
              <p className="mb-1.5 px-2 text-[11px] font-medium uppercase tracking-wide text-text-muted">
                {group.label}
              </p>
            )}
            <div className="flex flex-col gap-0.5">
              {group.items.map((item) => {
                const active = pathname === item.href || pathname.startsWith(item.href + "/");
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`rounded-[var(--radius)] px-2.5 py-1.5 text-[13px] transition-colors ${
                      active
                        ? "bg-bg-accent text-text-accent"
                        : "text-text-secondary hover:bg-surface-2 hover:text-text-primary"
                    }`}
                  >
                    {item.label}
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
