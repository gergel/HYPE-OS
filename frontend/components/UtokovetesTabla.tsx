"use client";

import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import { UtokovetesDetailModal } from "@/components/UtokovetesDetailModal";
import type { UtokovetesOverview } from "@/lib/api";
import { FAZISOK, type Fazis, datum, fazisa, hianyzik, hianyzikDarab } from "@/lib/utokovetes";
import { KeresosSelect } from "@/components/KeresosSelect";

type Rendezes = "ujabb" | "regebbi" | "nev" | "hianyzo";

const RENDEZESEK: { kulcs: Rendezes; cimke: string }[] = [
  { kulcs: "ujabb", cimke: "Legújabb forgatás elöl" },
  { kulcs: "regebbi", cimke: "Legrégebbi forgatás elöl" },
  { kulcs: "nev", cimke: "Projekt neve szerint" },
  { kulcs: "hianyzo", cimke: "Legtöbb hiányzó elöl" },
];

/** Ennyi projekt látszik oszloponként - a többi egy kattintással nyitható. */
const ELSO_ADAG = 12;

/** Az ALAP nézet: a projektek fázisonként, egymás melletti oszlopokban -
 * egy pillantásra látszik, mi az, ami kész, mi az, ahol már csak utalni kell,
 * hol hiányzik a TIG, és hol még a szerződés sincs meg.
 *
 * Keresni, szűrni és rendezni is lehet: a keresés és a rendezés MINDEN
 * oszlopra egyszerre vonatkozik (az oszlop maga az állapot szerinti bontás),
 * a "Csak a teendők" pedig elrejti a kész projekteket. */
export function UtokovetesTabla({ rows }: { rows: UtokovetesOverview[] }) {
  const [kereses, setKereses] = useState("");
  const [rendezes, setRendezes] = useState<Rendezes>("ujabb");
  const [csakTeendo, setCsakTeendo] = useState(false);
  const [nyitott, setNyitott] = useState<Fazis[]>([]);
  const [nyitottProjekt, setNyitottProjekt] = useState<number | null>(null);

  const szurt = useMemo(() => {
    const keresett = kereses.trim().toLocaleLowerCase("hu-HU");
    const talalatok = rows.filter((r) => {
      if (!keresett) return true;
      return [r.project_nev, r.projektkod, r.forgatas_datuma].some((mezo) =>
        (mezo ?? "").toLocaleLowerCase("hu-HU").includes(keresett),
      );
    });
    return [...talalatok].sort((a, b) => {
      if (rendezes === "nev") return (a.project_nev ?? "").localeCompare(b.project_nev ?? "", "hu-HU");
      if (rendezes === "hianyzo") return hianyzikDarab(b) - hianyzikDarab(a);
      // Dátum szerint: a dátum nélküli projekt mindig a lista végén.
      const aDatum = a.forgatas_datuma ?? "";
      const bDatum = b.forgatas_datuma ?? "";
      if (!aDatum !== !bDatum) return aDatum ? -1 : 1;
      return rendezes === "ujabb" ? bDatum.localeCompare(aDatum) : aDatum.localeCompare(bDatum);
    });
  }, [rows, kereses, rendezes]);

  const oszlopok = FAZISOK.filter((f) => !(csakTeendo && f.kulcs === "kesz")).map((fazis) => ({
    ...fazis,
    projektek: szurt.filter((r) => fazisa(r) === fazis.kulcs),
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
            placeholder="Keresés (projekt, projektkód, dátum)"
            aria-label="Keresés a projektek közt"
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
            {szurt.length} / {rows.length} projekt
          </span>
        )}
      </div>

      <div
        className={`grid grid-cols-1 gap-4 md:grid-cols-2 ${csakTeendo ? "xl:grid-cols-3" : "xl:grid-cols-4"}`}
      >
        {oszlopok.map((oszlop) => {
          const mind = nyitott.includes(oszlop.kulcs);
          const lathato = mind ? oszlop.projektek : oszlop.projektek.slice(0, ELSO_ADAG);
          const rejtett = oszlop.projektek.length - lathato.length;
          return (
            <div
              key={oszlop.kulcs}
              data-fazis={oszlop.kulcs}
              className="flex min-w-0 flex-col rounded-[var(--radius)] border border-border bg-surface-2"
            >
              <div className="border-b border-border px-3 py-2.5">
                <p className="flex items-baseline justify-between gap-2 text-[13px] font-medium text-text-primary">
                  {oszlop.cim}
                  <span className="tabular-nums text-text-muted">{oszlop.projektek.length}</span>
                </p>
                <p className="mt-0.5 text-[11.5px] text-text-muted">{oszlop.leiras}</p>
              </div>
              <div className="flex flex-col gap-2 p-3">
                {oszlop.projektek.length === 0 ? (
                  <p className="py-2 text-[12.5px] text-text-muted">
                    {kereses ? "Nincs találat ebben az állapotban." : "Nincs ilyen projekt."}
                  </p>
                ) : (
                  lathato.map((sor) => (
                    // Felugró ablak, nem új oldal: a kártyáról a projekt
                    // papírozása azonnal elvégezhető anélkül, hogy a szűrés és
                    // a görgetési hely elveszne (lásd UtokovetesDetailModal).
                    <button
                      key={sor.project_id}
                      type="button"
                      onClick={() => setNyitottProjekt(sor.project_id)}
                      className="block w-full rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2 text-left transition-colors hover:border-text-accent/40"
                    >
                      <p className="truncate text-[13px] text-text-primary">{sor.project_nev ?? `#${sor.project_id}`}</p>
                      <p className="mt-0.5 flex flex-wrap items-baseline gap-x-2 text-[11.5px] text-text-muted">
                        {sor.projektkod && <span>{sor.projektkod}</span>}
                        {/* Negatív azonosító = projektkód-szintű sor: nincs
                            forgatása, a "–" helyett mondjuk is ki. */}
                        <span>{sor.project_id < 0 ? "forgatás nélkül" : datum(sor.forgatas_datuma)}</span>
                      </p>
                      <p
                        className={`mt-1 text-[12px] ${
                          oszlop.kulcs === "kesz" ? "text-text-success" : "text-text-secondary"
                        }`}
                      >
                        {hianyzik(sor)}
                      </p>
                    </button>
                  ))
                )}
                {rejtett > 0 && (
                  <button
                    type="button"
                    onClick={() => setNyitott((elozo) => [...elozo, oszlop.kulcs])}
                    className="w-fit text-[12.5px] text-text-accent hover:underline"
                  >
                    További {rejtett} projekt
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
      <UtokovetesDetailModal projectId={nyitottProjekt} onClose={() => setNyitottProjekt(null)} />
    </div>
  );
}
