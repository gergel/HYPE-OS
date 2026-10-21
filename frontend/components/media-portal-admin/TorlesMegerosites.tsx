"use client";

import { AlertTriangle } from "lucide-react";
import { vedettOverlayZaras } from "@/lib/vedettOverlayZaras";
import type { ReactNode } from "react";

/** NAGY, PIROS törlés-megerősítő a Média Portál adminhoz (a felhasználó
 * kérése): kép, videó, mappa vagy egy teljes portál törlése előtt ne egy
 * halvány kis ablak kérdezzen, hanem egy félreérthetetlen, piros
 * figyelmeztetés - a törlés itt tényleg végleges (a fájlok a tárhelyről is
 * mennek), nincs visszaút.
 *
 * A megerősítő gomb szándékosan NEM az alapértelmezett helyen/színen van:
 * a beidegződött "jobb alsó gombra kattintok" mozdulat a Mégsét találja el,
 * a törléshez a piros gombig kell menni. */
export function TorlesMegerosites({
  uzenet,
  cim = "Biztosan törlöd?",
  gombCimke = "Igen, törlöm",
  busy = false,
  onMegse,
  onTorles,
}: {
  uzenet: ReactNode;
  /** A piros főcím - visszavonás-jellegű műveletnél más szöveg kell, mint
   * törlésnél (pl. "Biztosan visszavonod?"). */
  cim?: string;
  gombCimke?: string;
  /** Folyamatban lévő törlésnél a gombok tiltva (pl. R2-ürítés). */
  busy?: boolean;
  onMegse: () => void;
  onTorles: () => void;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-6"
      {...vedettOverlayZaras(() => !busy && onMegse())}
    >
      <div
        role="alertdialog"
        aria-modal="true"
        className="w-full max-w-md rounded-[var(--radius-lg)] border-2 border-red-600/70 bg-surface-2 p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3 flex items-center gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-red-600/15">
            <AlertTriangle className="h-5 w-5 text-red-500" />
          </span>
          <h3 className="text-[19px] font-semibold text-red-500">{cim}</h3>
        </div>
        <p className="text-[14.5px] leading-relaxed text-text-primary">{uzenet}</p>
        <div className="mt-6 flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={onMegse}
            disabled={busy}
            className="rounded-[var(--radius)] border border-border px-4 py-2.5 text-[13.5px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
          >
            Mégse
          </button>
          <button
            type="button"
            onClick={onTorles}
            disabled={busy}
            className="rounded-[var(--radius)] bg-red-600 px-5 py-2.5 text-[13.5px] font-semibold text-white transition-colors hover:bg-red-500 disabled:opacity-60"
          >
            {busy ? "Törlés…" : gombCimke}
          </button>
        </div>
      </div>
    </div>
  );
}
