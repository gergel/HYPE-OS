"use client";

import { useEffect, useState } from "react";
import { elteltPercek, formatFt, formatPercek, futoKoltseg } from "@/lib/ido";

export type FutoMeres = {
  /** ISO időpont, amikor a mérés elindult. */
  since: string;
  /** A méréshez rögzített órabér - enélkül csak az idő számolható. */
  orabere: number | null;
};

/** A projekt összes utómunka-ideje és -költsége egy sorban, a MÉG FUTÓ
 * mérésekkel együtt, másodpercenként frissülve. A lezárt sorok összegét a
 * szerver adja (Timesheet.koltseg, mindig a sor saját, befagyasztott
 * órabérével számolva), a futókat itt számoljuk hozzá - így nem kell
 * megvárni a Stopot ahhoz, hogy lássuk, hol tart a projekt. */
export function VagasiKoltsegOsszesen({
  lezartPercek,
  lezartKoltseg,
  futok,
  showCost,
}: {
  lezartPercek: number;
  lezartKoltseg: number;
  futok: FutoMeres[];
  /** Forintot csak az lát, akinek a Pénzügy oldalhoz van hozzáférése. */
  showCost: boolean;
}) {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    if (futok.length === 0) return;
    const interval = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(interval);
  }, [futok.length]);

  const percek = lezartPercek + futok.reduce((sum, f) => sum + elteltPercek(f.since, now), 0);
  const koltseg = lezartKoltseg + futok.reduce((sum, f) => sum + futoKoltseg(f.since, f.orabere, now), 0);

  // A suppressHydrationWarning nem öröklődik: a futó mérés miatt változó
  // szövegeket tartalmazó gyerek-elemeken külön is ott kell lennie.
  return (
    <p className="mb-3 text-[13px] text-text-secondary" suppressHydrationWarning>
      Utómunkával töltött idő:{" "}
      <span suppressHydrationWarning className="font-medium text-text-primary">
        {formatPercek(percek)}
      </span>
      {showCost && (
        <>
          {" · "}Vágási költség összesen:{" "}
          <span suppressHydrationWarning className="font-medium text-text-primary">
            {formatFt(koltseg)}
          </span>
        </>
      )}
      {futok.length > 0 && <span className="text-text-warning"> · {futok.length} mérés épp fut</span>}
    </p>
  );
}
