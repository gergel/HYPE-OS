"use client";

import { useMemo, useState } from "react";
import { FolderSearch } from "lucide-react";
import { UtokovetesDetailModal } from "@/components/UtokovetesDetailModal";

export type KeresoProjekt = {
  id: number;
  nev: string | null;
  projektkod: string | null;
  datum: string | null;
};

/** BÁRMELYIK projekt utókövetése megnyitható innen névre/projektkódra keresve
 * - akkor is, ha a lenti áttekintő hatóköréből kimarad (a hatókör szűr, lásd
 * backend services/papirozas_hatokor.py). A felhasználó jelzése szerint
 * enélkül az ilyen projektet csak a projekt adatlapja felől, kerülővel
 * lehetett elérni - itt a keresés ugyanazt a felugró részletnézetet nyitja,
 * mint az áttekintő kártyái. */
export function UtokovetesProjektKereso({
  projektek,
  listazott,
}: {
  projektek: KeresoProjekt[];
  listazott: number[];
}) {
  const [kereses, setKereses] = useState("");
  const [nyitottProjekt, setNyitottProjekt] = useState<number | null>(null);

  const listazottak = useMemo(() => new Set(listazott), [listazott]);

  const talalatok = useMemo(() => {
    const keresett = kereses.trim().toLocaleLowerCase("hu-HU");
    // Egy betűre még ne dőljön ki több ezer sor - két karaktertől keresünk.
    if (keresett.length < 2) return [];
    return projektek
      .filter((p) =>
        [p.nev, p.projektkod, p.datum].some((mezo) =>
          (mezo ?? "").toLocaleLowerCase("hu-HU").includes(keresett),
        ),
      )
      .sort((a, b) => (b.datum ?? "").localeCompare(a.datum ?? ""))
      .slice(0, 30);
  }, [projektek, kereses]);

  return (
    <div className="relative w-fit">
      <label className="relative block">
        <FolderSearch
          size={13}
          className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-text-muted"
        />
        <input
          type="search"
          value={kereses}
          onChange={(e) => setKereses(e.target.value)}
          placeholder="Bármelyik projekt megnyitása…"
          aria-label="Bármelyik projekt utókövetésének megnyitása"
          className="w-72 rounded-[var(--radius)] border border-border bg-surface-2 py-1.5 pl-7 pr-2 text-[13px] text-text-primary focus:outline-none"
        />
      </label>
      {kereses.trim().length >= 2 && (
        <div className="absolute left-0 top-full z-30 mt-1 max-h-80 w-[26rem] max-w-[80vw] overflow-y-auto rounded-[var(--radius)] border border-border bg-surface-2 shadow-lg">
          {talalatok.length === 0 ? (
            <p className="px-3 py-2 text-[12.5px] text-text-muted">Nincs ilyen projekt.</p>
          ) : (
            talalatok.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => {
                  setNyitottProjekt(p.id);
                  setKereses("");
                }}
                className="block w-full border-b border-border px-3 py-2 text-left last:border-b-0 hover:bg-surface-3"
              >
                <p className="truncate text-[13px] text-text-primary">{p.nev ?? `#${p.id}`}</p>
                <p className="mt-0.5 flex flex-wrap items-baseline gap-x-2 text-[11.5px] text-text-muted">
                  {p.projektkod && <span>{p.projektkod}</span>}
                  {p.datum && <span>{p.datum}</span>}
                  {/* Jelezzük, ha a projekt a lenti áttekintőben nem szerepel -
                      így látszik, hogy a keresés többet lát, mint a lista. */}
                  {!listazottak.has(p.id) && (
                    <span className="text-text-warning">nincs az áttekintőben</span>
                  )}
                </p>
              </button>
            ))
          )}
        </div>
      )}
      <UtokovetesDetailModal projectId={nyitottProjekt} onClose={() => setNyitottProjekt(null)} />
    </div>
  );
}
