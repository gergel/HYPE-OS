"use client";

import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import type { UtokovetesOverviewProjectCode } from "@/lib/api";
import { KeresosSelect } from "@/components/KeresosSelect";
import {
  FAZISOK_PROJEKTKOD,
  type FazisProjektkod,
  fazisaProjektkod,
  hianyzikProjektkod,
} from "@/lib/utokovetesProjektkod";

type Rendezes = "nev" | "hianyzo";

const RENDEZESEK: { kulcs: Rendezes; cimke: string }[] = [
  { kulcs: "nev", cimke: "Projekt neve szerint" },
  { kulcs: "hianyzo", cimke: "Legtöbb hiányzó elöl" },
];

/** Ennyi projektkód látszik oszloponként - lásd UtokovetesTabla ELSO_ADAG. */
const ELSO_ADAG = 12;

function hianyzikDarabProjektkod(sor: UtokovetesOverviewProjectCode): number {
  return sor.szerzodes_fuggo + sor.tig_fuggo + sor.kifizetes_fuggo + sor.alairas_varo;
}

/** Ugyanaz a fázisonkénti oszlopos elrendezés, mint az ÁTTEKINTÉS nézeten
 * (lásd UtokovetesTabla, a forgatás-alapú megfelelője) - korábban ez egy
 * sima, keresés nélküli táblázat volt egy kártya alján, ahol könnyű volt
 * elveszni mellette. Ugyanaz az öt fázis, ugyanaz a rácsköz. */
export function UtokovetesProjektkodTabla({ rows }: { rows: UtokovetesOverviewProjectCode[] }) {
  const [kereses, setKereses] = useState("");
  const [rendezes, setRendezes] = useState<Rendezes>("nev");
  const [csakTeendo, setCsakTeendo] = useState(false);
  const [nyitott, setNyitott] = useState<FazisProjektkod[]>([]);

  const szurt = useMemo(() => {
    const keresett = kereses.trim().toLocaleLowerCase("hu-HU");
    const talalatok = rows.filter((r) => {
      if (!keresett) return true;
      return [r.project_nev, r.projektkod].some((mezo) => (mezo ?? "").toLocaleLowerCase("hu-HU").includes(keresett));
    });
    return [...talalatok].sort((a, b) =>
      rendezes === "hianyzo"
        ? hianyzikDarabProjektkod(b) - hianyzikDarabProjektkod(a)
        : (a.project_nev ?? "").localeCompare(b.project_nev ?? "", "hu-HU"),
    );
  }, [rows, kereses, rendezes]);

  const oszlopok = FAZISOK_PROJEKTKOD.filter((f) => !(csakTeendo && f.kulcs === "kesz")).map((fazis) => ({
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
        <KeresosSelect
          value={rendezes}
          options={RENDEZESEK.map((r) => ({ value: r.kulcs, label: r.cimke }))}
          onChange={(ertek) => setRendezes(ertek as Rendezes)}
          className="w-[220px]"
        />
        <label className="flex cursor-pointer items-center gap-1.5 text-[13px] text-text-secondary">
          <input
            type="checkbox"
            checked={csakTeendo}
            onChange={(e) => setCsakTeendo(e.target.checked)}
            className="cursor-pointer"
          />
          Csak a teendők
        </label>
        {kereses && (
          <span className="text-[12.5px] text-text-muted">
            {szurt.length} / {rows.length} projektkód
          </span>
        )}
      </div>

      <div className={`grid grid-cols-1 gap-4 md:grid-cols-2 ${csakTeendo ? "xl:grid-cols-3" : "xl:grid-cols-4"}`}>
        {oszlopok.map((oszlop) => {
          const mind = nyitott.includes(oszlop.kulcs);
          const lathato = mind ? oszlop.projektkodok : oszlop.projektkodok.slice(0, ELSO_ADAG);
          const rejtett = oszlop.projektkodok.length - lathato.length;
          return (
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
                  lathato.map((sor) => (
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
                {rejtett > 0 && (
                  <button
                    type="button"
                    onClick={() => setNyitott((elozo) => [...elozo, oszlop.kulcs])}
                    className="w-fit text-[12.5px] text-text-accent hover:underline"
                  >
                    További {rejtett} projektkód
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
