"use client";

import { Menu, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { usePathname } from "next/navigation";
import { KrumpelloNav } from "@/components/krumpello/KrumpelloNav";

/** A Krumpello telefonos navigációja - ugyanaz a hamburger+fiók minta, mint a
 * fő HYPE OS-ben (lásd components/MobileNav.tsx), mert a Krumpello oldalsávja
 * (lásd (krumpello)/layout.tsx) is `hidden md:flex`, tehát telefonon
 * enélkül szintén navigálhatatlan lenne. */
export function KrumpelloMobileNav() {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();

  // A fiókot a `<body>` VÉGÉRE portálozzuk - lásd MobileNav.tsx ugyanerről a
  // jelenségről (a KrumpelloFejlec `backdrop-blur-xl`-je új "containing
  // block"-ot nyit a `position: fixed` gyerekeinek).
  const [mount, setMount] = useState(false);
  useEffect(() => setMount(true), []);

  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!open) return;
    const eredeti = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = eredeti;
    };
  }, [open]);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Menü megnyitása"
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[var(--radius)] border border-border text-text-secondary hover:bg-surface-3 md:hidden"
      >
        <Menu size={18} strokeWidth={1.75} aria-hidden />
      </button>

      {open &&
        mount &&
        createPortal(
          <div className="fixed inset-0 z-50 md:hidden">
            <div
              aria-hidden
              onClick={() => setOpen(false)}
              className="fade-in absolute inset-0 bg-black/60 backdrop-blur-[1px]"
            />
            <div className="absolute inset-y-0 left-0 flex w-[240px] max-w-[85vw] flex-col border-r border-border bg-surface-1 px-3 py-6 shadow-xl">
              <div className="mb-8 flex items-center justify-between px-3">
                <div>
                  <p className="text-[19px] font-extrabold tracking-[-0.02em] text-text-accent">krumpello</p>
                  <p className="mt-0.5 text-[11px] text-text-muted">Pénzügy</p>
                </div>
                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  aria-label="Menü bezárása"
                  className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[var(--radius)] text-text-muted hover:bg-surface-3"
                >
                  <X size={18} strokeWidth={1.75} aria-hidden />
                </button>
              </div>
              <KrumpelloNav />
              <div className="mt-auto border-t border-border pt-4">
                <Link
                  href="/dashboard"
                  className="flex items-center gap-2 rounded-[var(--radius)] px-3 py-2 text-[12.5px] text-text-secondary transition-colors hover:bg-surface-3 hover:text-text-primary"
                >
                  ← Vissza a HYPE OS-be
                </Link>
              </div>
            </div>
          </div>,
          document.body,
        )}
    </>
  );
}
