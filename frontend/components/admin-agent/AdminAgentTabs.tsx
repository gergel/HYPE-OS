"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { authFetch } from "@/lib/authFetch";

const FULEK = [
  { href: "/admin-agent", label: "Áttekintés" },
  { href: "/admin-agent/munkasor", label: "Munkasor" },
  { href: "/admin-agent/jovahagyasok", label: "Jóváhagyások" },
  { href: "/admin-agent/tudastar", label: "Tudástár" },
  { href: "/admin-agent/tudashalo", label: "Tudásháló" },
  { href: "/admin-agent/kerdesek", label: "Kérdések" },
  { href: "/admin-agent/tanulas", label: "Tanulás és minőség" },
  { href: "/admin-agent/naplo", label: "Napló" },
  { href: "/admin-agent/beallitasok", label: "Beállítások" },
];

/** Lara aloldalak közti navigáció (a meglévő sötét design tokenekkel).
 *
 * Leállított Laránál (vészleállítás) minden aloldalon piros csík jelzi, hogy
 * minden szál áll - a szerver ilyenkor minden futtató kérést elutasít. */
export function AdminAgentTabs() {
  const path = usePathname();
  const [leallitva, setLeallitva] = useState<{ indok: string | null } | null>(null);

  useEffect(() => {
    let el = false;
    authFetch("/api/v1/admin-agent/settings")
      .then((r) => (r.ok ? r.json() : null))
      .then((d: { kill_switch?: boolean; kill_switch_indok?: string | null } | null) => {
        if (!el) setLeallitva(d?.kill_switch ? { indok: d.kill_switch_indok ?? null } : null);
      })
      .catch(() => undefined);
    return () => {
      el = true;
    };
  }, [path]);

  return (
    <>
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
    {leallitva && (
      <div role="alert" className="mb-4 rounded-[var(--radius)] bg-bg-danger px-4 py-3 text-[13px] text-text-danger">
        <p className="font-medium">Lara le van állítva (vészleállítás)</p>
        <p className="mt-0.5 text-text-danger/80">
          Minden szál áll: se megfigyelés, se tanulás, se levelezés-olvasás, se elemzés vagy végrehajtás. A tudása
          megmaradt.{leallitva.indok ? ` Indok: ${leallitva.indok}.` : ""}{" "}
          <Link href="/admin-agent/beallitasok" className="underline">
            Visszakapcsolás a Beállításokban
          </Link>
        </p>
      </div>
    )}
    </>
  );
}
