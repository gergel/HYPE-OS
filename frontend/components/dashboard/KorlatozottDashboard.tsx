"use client";

import { useState } from "react";
import { Clapperboard } from "lucide-react";
import { RecordDetailModal } from "@/components/RecordDetailModal";
import { StatusBadge } from "@/components/StatusBadge";
import type { Deliverable } from "@/lib/api";

/** A KORLÁTOZOTT fiók teljes felülete: csak a rábízott anyag(ok), teendőként.
 *
 * Így dolgozik egy külsős vágó nálunk: kap egy fiókot, belép, és egyetlen
 * dolgot lát - amin dolgoznia kell. Az anyag felugró ablakban nyílik (a rendes
 * részletnézet keret nélküli változata, lásd RecordDetailModal), tehát az
 * időmérő, a feladat leírása és a hozzászólások mind ott vannak, de sehova nem
 * tud "kinavigálni" a rendszerbe. A korlátozást a backend tartja be (lásd
 * core/security.lathato_anyagok), ez a nézet csak azt teszi hozzá, hogy ne is
 * kelljen keresgélnie.
 *
 * Ha egyszerre több anyagot bíztunk rá, mind itt sorakozik. */
export function KorlatozottDashboard({ anyagok }: { anyagok: Deliverable[] }) {
  const [nyitott, setNyitott] = useState<string | null>(null);

  if (anyagok.length === 0) {
    return (
      <p className="text-[13px] text-text-muted">
        Jelenleg nincs rád bízott anyag. Ha ez tévedés, szólj a gyártásvezetőnek.
      </p>
    );
  }

  return (
    <>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
        {anyagok.map((anyag) => (
          <button
            key={anyag.id}
            type="button"
            onClick={() => setNyitott(`/utomunka/${anyag.id}`)}
            className="flex flex-col gap-2 rounded-[var(--radius)] border border-border bg-surface-2 p-4 text-left transition-colors hover:border-text-accent/40"
          >
            <span className="flex items-start gap-2">
              <Clapperboard size={15} className="mt-0.5 shrink-0 text-text-muted" aria-hidden />
              <span className="text-[14px] text-text-primary">{anyag.projekt_neve}</span>
            </span>
            <span className="flex flex-wrap items-center gap-2 text-[12.5px] text-text-secondary">
              <StatusBadge label={anyag.allapot ?? "Nincs állapot"} tone={anyag.allapot ? "accent" : "neutral"} />
              {anyag.hatarido && <span>Határidő: {anyag.hatarido.slice(0, 10)}</span>}
            </span>
            <span className="text-[12.5px] text-text-accent">Megnyitás →</span>
          </button>
        ))}
      </div>
      <RecordDetailModal href={nyitott} onClose={() => setNyitott(null)} />
    </>
  );
}
