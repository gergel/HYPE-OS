"use client";

import type { ReactNode } from "react";

/** Egy kattintható soron/kártyán belüli interaktív elemet (gomb, link, input)
 * csomagol be, hogy a rákattintás ne indítsa el a sor kattintás-navigációját
 * (lásd RowLink) vagy a kártya megnyitását - a szülő onClick a böngészőben
 * felbugyog, ezt itt állítjuk meg.
 *
 * A `className` azért van, hogy ne kelljen fölé még egy elrendezés-doboz: a
 * művelet-sáv gyakran maga a flex konténer. */
export function StopClickPropagation({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <span className={className} onClick={(e) => e.stopPropagation()}>
      {children}
    </span>
  );
}
