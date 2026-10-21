"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { clearToken } from "@/lib/authFetch";

/** Avatar + lenyíló menü a TopBar jobb szélén - mindenki (bármelyik oldalon)
 * innen tud kijelentkezni, nem csak a Beállítások oldal AccountCard-járól,
 * amit egy oldal-hozzáférés korlátozás miatt nem biztos, hogy mindenki elér.
 * Innen nyílik a PROFIL oldal is (a felhasználó kérése): profilkép + saját
 * szín beállítása - és ha van profilkép, az avatár azt mutatja a monogram
 * helyett. */
export function UserMenu({
  name,
  email,
  initials,
  profilkep = null,
}: {
  name: string;
  email: string | null;
  initials: string;
  /** Profilkép data-URL-ként (lásd app/profil) - null-nál marad a monogram. */
  profilkep?: string | null;
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
        className="flex h-8 w-8 items-center justify-center overflow-hidden rounded-full bg-bg-accent text-[13px] font-medium text-text-accent"
      >
        {profilkep ? (
          // data-URL-t mutat - a next/image itt nem optimalizálna semmit.
          // eslint-disable-next-line @next/next/no-img-element
          <img src={profilkep} alt={name} className="h-full w-full object-cover" />
        ) : (
          initials
        )}
      </button>
      {open && (
        <div className="absolute right-0 top-full z-10 mt-2 w-52 rounded-[var(--radius)] border border-border bg-surface-2 p-2 shadow-lg">
          <div className="border-b border-border px-2 pb-2">
            <p className="truncate text-[13px] text-text-primary">{name}</p>
            {email && <p className="truncate text-[12px] text-text-muted">{email}</p>}
          </div>
          <a
            href="/profil"
            onClick={() => setOpen(false)}
            className="mt-2 block w-full rounded-[var(--radius)] px-2 py-1.5 text-left text-[13px] text-text-primary hover:bg-surface-3"
          >
            Profilom
          </a>
          <button
            type="button"
            onClick={handleLogout}
            className="w-full rounded-[var(--radius)] px-2 py-1.5 text-left text-[13px] text-text-danger hover:bg-surface-3"
          >
            Kijelentkezés
          </button>
        </div>
      )}
    </div>
  );
}
