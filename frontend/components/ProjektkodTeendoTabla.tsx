"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Search } from "lucide-react";
import type { ProjectCode } from "@/lib/api";
import { formatHuf } from "@/lib/penz";
import {
  PROJEKTKOD_FAZISOK,
  projektkodFazisa,
  projektkodHianyzik,
  type ProjektkodFazis,
} from "@/lib/projektkodFazis";

type Rendezes = "kod" | "profit" | "bevetel";

const RENDEZESEK: { kulcs: Rendezes; cimke: string }[] = [
  { kulcs: "kod", cimke: "Projektkód szerint" },
  { kulcs: "profit", cimke: "Legnagyobb profit elöl" },
  { kulcs: "bevetel", cimke: "Legnagyobb bevétel elöl" },
];

/** Ennyi projektkód látszik oszloponként - a többi egy kattintással nyitható. */
const ELSO_ADAG = 12;

/** A projektkódok FÁZISONKÉNT, egymás melletti oszlopokban - ugyanaz a nézet,
 * mint az Utókövetésen (lásd UtokovetesTabla), csak a másik oldalról: ott a mi
 * fizetéseink útját követi, itt a megrendelő felé menő papírokét és a beérkező
 * pénzét.
 *
 * Egy projektkód PONTOSAN EGY oszlopban áll, a legkorábbi hiányzó lépésnél -
 * így balról jobbra haladva az látszik, mi a következő teendő rajta, és nem
 * kell ugyanazt a sort több helyen is átfutni.
 *
 * A kártya a projektkód adatlapjára visz: a papírozás ott végezhető el. */
export function ProjektkodTeendoTabla({ rows }: { rows: ProjectCode[] }) {
  const [kereses, setKereses] = useState("");
  const [rendezes, setRendezes] = useState<Rendezes>("kod");
  const [csakTeendo, setCsakTeendo] = useState(true);
  const [nyitott, setNyitott] = useState<ProjektkodFazis[]>([]);

  const szurt = useMemo(() => {
    const keresett = kereses.trim().toLocaleLowerCase("hu-HU");
    const talalatok = rows.filter((pc) => {
      if (!keresett) return true;
      return [pc.projektkod, pc.project_nev, pc.helyszin, pc.datum_megjegyzes].some((mezo) =>
        (mezo ?? "").toLocaleLowerCase("hu-HU").includes(keresett),
      );
    });
    return [...talalatok].sort((a, b) => {
      if (rendezes === "profit") return b.becsult_profit - a.becsult_profit;
      if (rendezes === "bevetel") return b.bevetel - a.bevetel;
      return a.projektkod.localeCompare(b.projektkod, "hu-HU");
    });
  }, [rows, kereses, rendezes]);

  const oszlopok = PROJEKTKOD_FAZISOK.filter((f) => !(csakTeendo && f.kulcs === "kesz")).map((fazis) => ({
    ...fazis,
    kodok: szurt.filter((pc) => projektkodFazisa(pc) === fazis.kulcs),
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
            placeholder="Keresés (kód, projekt, helyszín)"
            aria-label="Keresés a projektkódok közt"
            className="w-72 rounded-[var(--radius)] border border-border bg-surface-2 py-1.5 pl-7 pr-2 text-[13px] text-text-primary focus:outline-none"
          />
        </label>
        <select
          value={rendezes}
          onChange={(e) => setRendezes(e.target.value as Rendezes)}
          aria-label="Rendezés"
          className="rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1.5 text-[13px] text-text-primary focus:outline-none"
        >
          {RENDEZESEK.map((r) => (
            <option key={r.kulcs} value={r.kulcs}>
              {r.cimke}
            </option>
          ))}
        </select>
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
          const lathato = mind ? oszlop.kodok : oszlop.kodok.slice(0, ELSO_ADAG);
          const rejtett = oszlop.kodok.length - lathato.length;
          return (
            <div
              key={oszlop.kulcs}
              data-fazis={oszlop.kulcs}
              className="flex min-w-0 flex-col rounded-[var(--radius)] border border-border bg-surface-2"
            >
              <div className="border-b border-border px-3 py-2.5">
                <p className="flex items-baseline justify-between gap-2 text-[13px] font-medium text-text-primary">
                  {oszlop.cim}
                  <span className="tabular-nums text-text-muted">{oszlop.kodok.length}</span>
                </p>
                <p className="mt-0.5 text-[11.5px] text-text-muted">{oszlop.leiras}</p>
              </div>
              <div className="flex flex-col gap-2 p-3">
                {oszlop.kodok.length === 0 ? (
                  <p className="py-2 text-[12.5px] text-text-muted">
                    {kereses ? "Nincs találat ebben az állapotban." : "Nincs ilyen projektkód."}
                  </p>
                ) : (
                  lathato.map((pc) => (
                    <Link
                      key={pc.id}
                      href={`/projektek/project-kodok/${pc.id}`}
                      className="block w-full rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2 transition-colors hover:border-text-accent/40"
                    >
                      <p className="truncate text-[13px] text-text-primary">{pc.projektkod}</p>
                      <p className="mt-0.5 flex flex-wrap items-baseline gap-x-2 text-[11.5px] text-text-muted">
                        {pc.project_nev && <span className="truncate">{pc.project_nev}</span>}
                        {pc.datum_megjegyzes && <span>{pc.datum_megjegyzes}</span>}
                      </p>
                      <p
                        className={`mt-1 text-[12px] ${
                          oszlop.kulcs === "kesz" ? "text-text-success" : "text-text-secondary"
                        }`}
                      >
                        {projektkodHianyzik(pc)}
                      </p>
                      {/* A pénz azért van a kártyán, mert a teendő súlyát ez
                          adja: egy 3 milliós kintlévőség máshogy sürgős, mint
                          egy 30 ezres. */}
                      <p className="mt-1 flex flex-wrap gap-x-2 text-[11.5px] text-text-muted">
                        <span>Bevétel {formatHuf(pc.bevetel)}</span>
                        <span>Profit {formatHuf(pc.becsult_profit)}</span>
                      </p>
                    </Link>
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
