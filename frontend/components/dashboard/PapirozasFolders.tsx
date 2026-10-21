"use client";

import { useState } from "react";
import Link from "next/link";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { MyTaskItem } from "@/lib/api";

const MONTH_SHORT = ["jan", "feb", "márc", "ápr", "máj", "jún", "júl", "aug", "szept", "okt", "nov", "dec"];

function formatShortDate(iso: string): string {
  const d = new Date(iso);
  return `${MONTH_SHORT[d.getMonth()]} ${d.getDate()}.`;
}

/** Egy mappán belül ennyi tétel látszik; a többit a "+N további" sor mögé
 * rejtjük, hogy egy sok tételes csoport se nyomja le az egész dashboardot. */
const LATHATO_TETEL = 8;

/** A papírozás teendői MAPPÁKBA rendezve (Belsős TIG, Külsős TIG,
 * Alvállalkozói szerződés, Megrendelői szerződés/TIG) - a csoportot a backend
 * adja meg (MyTaskItem.csoport).
 *
 * Miért: több száz nyitott papír esetén egyetlen lista használhatatlan - a
 * dashboardon végtelen hosszú lenne, és nem derülne ki belőle, MIBŐL van sok.
 * Így alapból csak a mappák látszanak a darabszámmal, és az nyílik ki, amivel
 * épp foglalkozni akarsz. */
export function PapirozasFolders({ items }: { items: MyTaskItem[] }) {
  const csoportok = new Map<string, MyTaskItem[]>();
  for (const item of items) {
    const kulcs = item.csoport ?? "Egyéb";
    csoportok.set(kulcs, [...(csoportok.get(kulcs) ?? []), item]);
  }
  const [nyitott, setNyitott] = useState<string[]>([]);
  const [teljes, setTeljes] = useState<string[]>([]);

  function toggle(kulcs: string) {
    setNyitott((elozo) => (elozo.includes(kulcs) ? elozo.filter((k) => k !== kulcs) : [...elozo, kulcs]));
  }

  return (
    <div className="space-y-1">
      {[...csoportok.entries()].map(([csoport, csoportItems]) => {
        const nyitva = nyitott.includes(csoport);
        const mindet = teljes.includes(csoport);
        const lathato = mindet ? csoportItems : csoportItems.slice(0, LATHATO_TETEL);
        return (
          <div key={csoport} className="rounded-[var(--radius)] border border-border">
            <button
              type="button"
              onClick={() => toggle(csoport)}
              aria-expanded={nyitva}
              className="flex w-full items-center gap-2 px-2 py-1.5 text-left text-[13px] hover:bg-surface-3"
            >
              {nyitva ? (
                <ChevronDown size={13} className="shrink-0 text-text-muted" />
              ) : (
                <ChevronRight size={13} className="shrink-0 text-text-muted" />
              )}
              <span className="text-text-primary">{csoport}</span>
              <span className="ml-auto rounded-full bg-surface-3 px-1.5 py-0.5 text-[11px] text-text-secondary">
                {csoportItems.length}
              </span>
            </button>

            {nyitva && (
              <ul className="space-y-0.5 border-t border-border px-1 py-1">
                {lathato.map((item, i) => (
                  <li key={`${csoport}-${item.id}-${i}`}>
                    <Link
                      href={item.link}
                      className="flex items-center justify-between gap-3 rounded-[var(--radius)] px-2 py-1 text-[13px] transition-colors hover:bg-surface-3"
                    >
                      <span className="truncate text-text-primary">{item.title}</span>
                      {item.hatarido && (
                        <span className="shrink-0 text-text-secondary">{formatShortDate(item.hatarido)}</span>
                      )}
                    </Link>
                  </li>
                ))}
                {!mindet && csoportItems.length > LATHATO_TETEL && (
                  <li>
                    <button
                      type="button"
                      onClick={() => setTeljes((elozo) => [...elozo, csoport])}
                      className="w-full px-2 py-1 text-left text-[12px] text-text-accent hover:underline"
                    >
                      +{csoportItems.length - LATHATO_TETEL} további
                    </button>
                  </li>
                )}
              </ul>
            )}
          </div>
        );
      })}
    </div>
  );
}
