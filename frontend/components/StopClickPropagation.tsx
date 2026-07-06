"use client";

import type { ReactNode } from "react";

/** Egy táblázatsoron belüli interaktív elemet (input, checkbox) csomagol be,
 * hogy a rákattintás ne indítsa el a sor kattintás-navigációját (lásd
 * RowLink) - a sor onClick a böngészőben bugyog fel, ezt itt állítjuk meg. */
export function StopClickPropagation({ children }: { children: ReactNode }) {
  return <span onClick={(e) => e.stopPropagation()}>{children}</span>;
}
