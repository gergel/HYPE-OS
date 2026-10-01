"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";

/** Időszak-szűrő a Pénzügyek kiadás- és bevétel-listája fölé (a felhasználó
 * kérése: a tételek DÁTUMÁRA lehessen szűrni). Gyorsgombok a leggyakoribb
 * időszakokra + szabad tól-ig. Az állapot az URL-ben él (pl.
 * `?kiadas_tol=2026-09-01&kiadas_ig=2026-09-30`), így a szűrt nézet
 * könyvjelzőzhető, és a lista a szerveren szűrődik - a két lista szűrője
 * egymástól független (külön paraméter-pár). */

function iso(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function gyorsIdoszakok(): { label: string; tol: string; ig: string }[] {
  const ma = new Date();
  const ev = ma.getFullYear();
  const ho = ma.getMonth();
  return [
    { label: "Ez a hónap", tol: iso(new Date(ev, ho, 1)), ig: iso(new Date(ev, ho + 1, 0)) },
    { label: "Előző hónap", tol: iso(new Date(ev, ho - 1, 1)), ig: iso(new Date(ev, ho, 0)) },
    { label: "Idén", tol: `${ev}-01-01`, ig: `${ev}-12-31` },
    { label: "Tavaly", tol: `${ev - 1}-01-01`, ig: `${ev - 1}-12-31` },
  ];
}

export function DatumSzuro({
  elotag,
  tol,
  ig,
  mire,
  osszegzes,
}: {
  /** Az URL-paraméterek előtagja (`kiadas` -> `kiadas_tol`, `kiadas_ig`). */
  elotag: string;
  tol: string;
  ig: string;
  /** Melyik dátumra szűr (a felhasználónak kiírva), pl. „fizetés dátuma”. */
  mire: string;
  /** Szűréskor a találatok összesítése (darab, összeg). */
  osszegzes?: string | null;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  function beallit(ujTol: string, ujIg: string) {
    const params = new URLSearchParams(searchParams.toString());
    if (ujTol) params.set(`${elotag}_tol`, ujTol);
    else params.delete(`${elotag}_tol`);
    if (ujIg) params.set(`${elotag}_ig`, ujIg);
    else params.delete(`${elotag}_ig`);
    const q = params.toString();
    router.replace(q ? `${pathname}?${q}` : pathname, { scroll: false });
  }

  const aktiv = Boolean(tol || ig);
  const gomb = (bekapcsolva: boolean) =>
    `rounded-[var(--radius)] border px-2.5 py-1 text-[12.5px] transition-colors ${
      bekapcsolva
        ? "border-text-accent/50 bg-bg-accent text-text-accent"
        : "border-border text-text-secondary hover:border-border-strong hover:text-text-primary"
    }`;

  return (
    <div className="mb-4 space-y-2 rounded-[var(--radius)] border border-border bg-surface-2 px-3 py-2.5">
      <div className="flex flex-wrap items-center gap-2">
        <span className="t-label mr-1">Időszak ({mire})</span>
        <button type="button" className={gomb(!aktiv)} onClick={() => beallit("", "")}>
          Összes
        </button>
        {gyorsIdoszakok().map((g) => (
          <button
            key={g.label}
            type="button"
            className={gomb(tol === g.tol && ig === g.ig)}
            onClick={() => beallit(g.tol, g.ig)}
          >
            {g.label}
          </button>
        ))}
        <span className="flex items-center gap-1.5 text-[12.5px] text-text-muted">
          <input
            type="date"
            aria-label="Ettől"
            value={tol}
            onChange={(e) => beallit(e.target.value, ig)}
            className="field h-8 w-[150px] py-0 text-[12.5px]"
          />
          –
          <input
            type="date"
            aria-label="Eddig"
            value={ig}
            onChange={(e) => beallit(tol, e.target.value)}
            className="field h-8 w-[150px] py-0 text-[12.5px]"
          />
        </span>
      </div>
      {aktiv && osszegzes && <p className="text-[12.5px] text-text-secondary">{osszegzes}</p>}
    </div>
  );
}
