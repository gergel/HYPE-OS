"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { formatPercek } from "@/lib/ido";
import type { VagottAnyag } from "@/lib/api";

const ELSO_ADAG = 10;

function idopont(value: string | null): string {
  if (!value) return "–";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "–";
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}. ${p(d.getMonth() + 1)}. ${p(d.getDate())}.`;
}

/** Minden anyag, amin ez a vágó VALAHA dolgozott (futott rajta az időmérője),
 * a legutóbb érintettel elöl.
 *
 * Alapból csak a legutóbbi tíz látszik: egy régóta itt dolgozó vágónál ez a
 * lista több százas is lehet, és az adatlap többi része lecsúszna alá. A
 * többi egy kattintásra előjön, és bármelyik kereshető - beleértve a
 * lenyitás nélkül nem látszó sorokat is (a keresés mindig a TELJES listán
 * fut, nem csak a megjelenítetten). */
export function VagottAnyagokLista({ anyagok }: { anyagok: VagottAnyag[] }) {
  const [kereses, setKereses] = useState("");
  const [mindet, setMindet] = useState(false);

  const talalatok = useMemo(() => {
    const needle = kereses.trim().toLowerCase();
    if (!needle) return anyagok;
    return anyagok.filter((a) =>
      `${a.projekt_neve} ${a.projektkod ?? ""} ${a.allapot ?? ""}`.toLowerCase().includes(needle),
    );
  }, [anyagok, kereses]);

  // Keresés közben mindig a teljes találati listát mutatjuk: ott épp az a
  // kérdés, hogy megvan-e valami, nem az, hogy mi a legutóbbi.
  const keres = kereses.trim().length > 0;
  const lathato = keres || mindet ? talalatok : talalatok.slice(0, ELSO_ADAG);
  const rejtett = talalatok.length - lathato.length;

  if (anyagok.length === 0) {
    return <p className="text-[13px] text-text-muted">Ez a munkatárs még egyetlen anyagon sem dolgozott.</p>;
  }

  return (
    <div className="space-y-4">
      <input
        type="text"
        value={kereses}
        onChange={(e) => setKereses(e.target.value)}
        placeholder="Keresés anyag, projektkód vagy állapot szerint…"
        className="field w-full max-w-[320px]"
      />

      {lathato.length === 0 ? (
        <p className="text-[13px] text-text-muted">Nincs találat a keresésre.</p>
      ) : (
        <ul className="divide-y divide-border">
          {lathato.map((a) => (
            <li key={a.id}>
              <Link
                href={`/utomunka/${a.id}`}
                className="flex flex-wrap items-center justify-between gap-x-6 gap-y-1 py-3 transition-colors duration-200 hover:bg-surface-3"
              >
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[13.5px] text-text-primary">{a.projekt_neve}</span>
                  <span className="mt-0.5 block text-[12px] text-text-muted">
                    {a.projektkod ?? "Nincs projektkód"}
                    {a.allapot ? ` · ${a.allapot}` : ""}
                  </span>
                </span>
                <span className="shrink-0 text-right text-[12.5px] text-text-secondary tabular-nums">
                  {formatPercek(a.osszes_perc)}
                  <span className="mt-0.5 block text-[12px] text-text-muted">{idopont(a.utoljara)}</span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}

      {!keres && rejtett > 0 && (
        <button type="button" onClick={() => setMindet(true)} className="btn btn-ghost">
          További {rejtett} anyag mutatása
        </button>
      )}
      {!keres && mindet && talalatok.length > ELSO_ADAG && (
        <button type="button" onClick={() => setMindet(false)} className="btn btn-ghost">
          Csak a legutóbbi {ELSO_ADAG} mutatása
        </button>
      )}
    </div>
  );
}
