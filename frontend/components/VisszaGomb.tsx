"use client";

import { useRouter } from "next/navigation";

/** A böngésző-előzményeket használja (nem egy fix célt), hogy pontosan oda
 * vigyen vissza, ahonnan a felhasználó idekattintott - lásd
 * app/(app)/nincs-jogosultsag/page.tsx. Külön kliens-komponens, hogy maga az
 * oldal szerver-komponens maradhasson (a TopBar is az - lásd annak
 * megjegyzését). */
export function VisszaGomb() {
  const router = useRouter();
  return (
    <button
      type="button"
      onClick={() => router.back()}
      className="rounded-[var(--radius)] border border-border-strong bg-surface-4 px-4 py-2 text-[13px] font-medium text-text-primary hover:bg-surface-3"
    >
      ← Vissza
    </button>
  );
}
