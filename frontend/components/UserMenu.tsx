"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { clearToken } from "@/lib/authFetch";

/** Avatar + lenyíló menü a TopBar jobb szélén - mindenki (bármelyik oldalon)
 * innen tud kijelentkezni, nem csak a Beállítások oldal AccountCard-járól,
 * amit egy oldal-hozzáférés korlátozás miatt nem biztos, hogy mindenki elér. */
export function UserMenu({
  name,
  email,
  initials,
}: {
  name: string;
  email: string | null;
  initials: string;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  function handleLogout() {
    clearToken();
    router.push("/login");
    router.refresh();
  }

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex h-8 w-8 items-center justify-center rounded-full bg-bg-accent text-[13px] font-medium text-text-accent"
      >
        {initials}
      </button>
      {open && (
        <div className="absolute right-0 top-full z-10 mt-2 w-52 rounded-[var(--radius)] border border-border bg-surface-2 p-2 shadow-lg">
          <div className="border-b border-border px-2 pb-2">
            <p className="truncate text-[13px] text-text-primary">{name}</p>
            {email && <p className="truncate text-[12px] text-text-muted">{email}</p>}
          </div>
          <button
            type="button"
            onClick={handleLogout}
            className="mt-2 w-full rounded-[var(--radius)] px-2 py-1.5 text-left text-[13px] text-text-danger hover:bg-surface-3"
          >
            Kijelentkezés
          </button>
        </div>
      )}
    </div>
  );
}
