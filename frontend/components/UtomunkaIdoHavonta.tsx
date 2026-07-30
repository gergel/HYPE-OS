"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { formatFt, formatPercek } from "@/lib/ido";
import type { UtomunkaHonapIdo } from "@/lib/api";

/** Mennyit vágott ez a munkatárs HÓNAPOKRA bontva - a személy adatlapján, az
 * alapadatok alatt. Minden hónap egy összecsukható sor: a fejlécében ott az
 * adott havi összes óra és költség, kinyitva pedig projektenként látszik a
 * megoszlás.
 *
 * A forintos rész csak akkor jelenik meg, ha a backend küldött összeget -
 * Pénzügy-hozzáférés nélkül nem küld (lásd crew.py get_utomunka_ido). */
export function UtomunkaIdoHavonta({ honapok }: { honapok: UtomunkaHonapIdo[] }) {
  // Alapból a legfrissebb hónap van nyitva, a többi csukva - így az oldal nem
  // hízik meg évekre visszamenőleg.
  const [nyitott, setNyitott] = useState<string[]>(honapok.length > 0 ? [kulcs(honapok[0])] : []);

  if (honapok.length === 0) {
    return <p className="text-[13px] text-text-muted">Nincs rögzített utómunka-idő ehhez a munkatárshoz.</p>;
  }

  const showCost = honapok.some((h) => h.total_cost != null);
  const osszPerc = honapok.reduce((sum, h) => sum + h.total_minutes, 0);
  const osszKoltseg = honapok.reduce((sum, h) => sum + (h.total_cost ?? 0), 0);

  function toggle(h: UtomunkaHonapIdo) {
    const k = kulcs(h);
    setNyitott((elozo) => (elozo.includes(k) ? elozo.filter((x) => x !== k) : [...elozo, k]));
  }

  return (
    <div>
      <div className="mb-3 flex items-center justify-between border-b border-border pb-2 text-[13px]">
        <span className="text-text-secondary">Mindösszesen</span>
        <span className="font-medium text-text-primary">
          {formatPercek(osszPerc)}
          {showCost && <span className="text-text-secondary"> · {formatFt(osszKoltseg)}</span>}
        </span>
      </div>

      <div className="space-y-1">
        {honapok.map((h) => {
          const nyitva = nyitott.includes(kulcs(h));
          return (
            <div key={kulcs(h)} className="rounded-[var(--radius)] border border-border">
              <button
                type="button"
                onClick={() => toggle(h)}
                className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-[13px] hover:bg-surface-3"
              >
                <span className="flex items-center gap-1.5 text-text-primary">
                  {nyitva ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                  {h.honap_szoveg}
                </span>
                <span className="whitespace-nowrap text-text-secondary">
                  {formatPercek(h.total_minutes)}
                  {h.total_cost != null && <span className="text-text-muted"> · {formatFt(h.total_cost)}</span>}
                </span>
              </button>

              {nyitva && (
                <table className="w-full border-collapse border-t border-border text-[13px]">
                  <thead>
                    <tr className="border-b border-border">
                      <th className="py-1.5 pl-3 pr-4 text-left font-medium text-text-secondary">Projekt</th>
                      <th className="py-1.5 pr-4 text-right font-medium text-text-secondary">Anyagok</th>
                      <th className="py-1.5 pr-4 text-right font-medium text-text-secondary">Idő</th>
                      {showCost && <th className="py-1.5 pr-3 text-right font-medium text-text-secondary">Költség</th>}
                    </tr>
                  </thead>
                  <tbody>
                    {h.projektek.map((p) => (
                      <tr key={p.project_id ?? "nincs"} className="border-b border-border last:border-0">
                        <td className="py-2 pl-3 pr-4">
                          {p.project_id ? (
                            <a href={`/projektek/${p.project_id}`} className="text-text-accent hover:underline">
                              {p.project_nev ?? `Projekt #${p.project_id}`}
                            </a>
                          ) : (
                            <span className="text-text-muted">Projekt nélküli anyagok</span>
                          )}
                          {p.projektkod && <span className="ml-2 text-[11px] text-text-muted">{p.projektkod}</span>}
                        </td>
                        <td className="py-2 pr-4 text-right text-text-secondary">{p.anyagok_szama}</td>
                        <td className="py-2 pr-4 text-right whitespace-nowrap">{formatPercek(p.total_minutes)}</td>
                        {showCost && (
                          <td className="py-2 pr-3 text-right whitespace-nowrap text-text-secondary">
                            {p.total_cost != null ? formatFt(p.total_cost) : "–"}
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function kulcs(h: UtomunkaHonapIdo): string {
  return `${h.ev}-${h.honap}`;
}
