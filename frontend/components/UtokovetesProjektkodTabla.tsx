"use client";

import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import type { UtokovetesOverviewProjectCode } from "@/lib/api";
import { FAZISOK_PROJEKTKOD, type FazisProjektkod, fazisaProjektkod, hianyzikProjektkod } from "@/lib/utokovetesProjektkod";

/** Ugyanaz a fázisonkénti oszlopos elrendezés, mint az ÁTTEKINTÉS nézeten
 * (lásd UtokovetesTabla, a forgatás-alapú megfelelője) - korábban ez egy
 * sima, keresés nélküli táblázat volt egy kártya alján, ahol könnyű volt
 * elveszni mellette. Itt csak három fázis van (lásd
 * lib/utokovetesProjektkod.ts fejléce), ezért az oszlopok száma is három - a
 * rácsköz ugyanúgy törik, mint az alap nézet "Csak a teendők" állapotában
 * (ott is három oszlop marad, ha a "Kész" kikerül). */
export function UtokovetesProjektkodTabla({ rows }: { rows: UtokovetesOverviewProjectCode[] }) {
  const [kereses, setKereses] = useState("");

  const szurt = useMemo(() => {
    const keresett = kereses.trim().toLocaleLowerCase("hu-HU");
    if (!keresett) return rows;
    return rows.filter((r) =>
      [r.project_nev, r.projektkod].some((mezo) => (mezo ?? "").toLocaleLowerCase("hu-HU").includes(keresett)),
    );
  }, [rows, kereses]);

  const oszlopok: { kulcs: FazisProjektkod; cim: string; leiras: string; projektkodok: UtokovetesOverviewProjectCode[] }[] =
    FAZISOK_PROJEKTKOD.map((fazis) => ({
      ...fazis,
      projektkodok: szurt.filter((r) => fazisaProjektkod(r) === fazis.kulcs),
    }));

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <label className="relative">
          <Search size={13} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-text-muted" />
          <input
            type="search"
            value={kereses}
            onChange={(e) => setKereses(e.target.value)}
            placeholder="Keresés (projekt, projektkód)"
            aria-label="Keresés a projektkódok közt"
            className="w-72 rounded-[var(--radius)] border border-border bg-surface-2 py-1.5 pl-7 pr-2 text-[13px] text-text-primary focus:outline-none"
          />
        </label>
        {kereses && (
          <span className="text-[12.5px] text-text-muted">
            {szurt.length} / {rows.length} projektkód
          </span>
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {oszlopok.map((oszlop) => (
          <div
            key={oszlop.kulcs}
            data-fazis={oszlop.kulcs}
            className="flex min-w-0 flex-col rounded-[var(--radius)] border border-border bg-surface-2"
          >
            <div className="border-b border-border px-3 py-2.5">
              <p className="flex items-baseline justify-between gap-2 text-[13px] font-medium text-text-primary">
                {oszlop.cim}
                <span className="tabular-nums text-text-muted">{oszlop.projektkodok.length}</span>
              </p>
              <p className="mt-0.5 text-[11.5px] text-text-muted">{oszlop.leiras}</p>
            </div>
            <div className="flex flex-col gap-2 p-3">
              {oszlop.projektkodok.length === 0 ? (
                <p className="py-2 text-[12.5px] text-text-muted">
                  {kereses ? "Nincs találat ebben az állapotban." : "Nincs ilyen projektkód."}
                </p>
              ) : (
                oszlop.projektkodok.map((sor) => (
                  <a
                    key={sor.project_code_id}
                    href={`/utokovetes/projektkodok/${sor.project_code_id}`}
                    className="block w-full rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2 text-left transition-colors hover:border-text-accent/40"
                  >
                    <p className="truncate text-[13px] text-text-primary">
                      {sor.project_nev ?? `#${sor.project_code_id}`}
                    </p>
                    {sor.projektkod && <p className="mt-0.5 text-[11.5px] text-text-muted">{sor.projektkod}</p>}
                    <p
                      className={`mt-1 text-[12px] ${
                        oszlop.kulcs === "kesz" ? "text-text-success" : "text-text-secondary"
                      }`}
                    >
                      {hianyzikProjektkod(sor)}
                    </p>
                  </a>
                ))
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
