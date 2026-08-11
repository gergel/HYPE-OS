import Link from "next/link";

/** A Krumpello oldalak közös fejléce: cím + időszak-szűrő + kilépés.
 *
 * Az időszak SZÁNDÉKOSAN URL-ben (`?tol=&ig=`) él, nem komponens-állapotban:
 * így egy "2026 július" nézet linkelhető és megosztható, a frissítés nem
 * dobja vissza az alapértelmezésre, és a szerveroldali lekérés is látja -
 * nem kell a böngészőben újraszűrni azt, amit az adatbázis egyszer már
 * kiszámolt. */
export function KrumpelloFejlec({
  cim,
  leiras,
  tol,
  ig,
  utvonal,
  jobbOldal,
}: {
  cim: string;
  leiras?: string;
  tol?: string;
  ig?: string;
  /** Melyik oldal szűrőjét állítjuk (pl. "/krumpello/kiadas"). */
  utvonal: string;
  jobbOldal?: React.ReactNode;
}) {
  return (
    <div
      data-app-chrome
      className="sticky top-0 z-20 border-b border-border bg-surface-1/90 px-8 py-5 backdrop-blur-xl"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-[22px] font-semibold tracking-[-0.02em] text-text-primary">{cim}</h1>
          {leiras && <p className="mt-1 text-[12.5px] text-text-muted">{leiras}</p>}
        </div>
        <div className="flex items-center gap-2">{jobbOldal}</div>
      </div>
      <IdoszakSzuro tol={tol} ig={ig} utvonal={utvonal} />
    </div>
  );
}

/** Sima `<form method="get">`: JavaScript nélkül is működik, és nem kell hozzá
 * kliens-komponens csak azért, hogy két dátumot az URL-be tegyen. */
function IdoszakSzuro({ tol, ig, utvonal }: { tol?: string; ig?: string; utvonal: string }) {
  const mezo =
    "rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1 text-[12.5px] text-text-primary focus:outline-none";
  return (
    <form action={utvonal} method="get" className="mt-3 flex flex-wrap items-center gap-2">
      <label className="text-[11px] uppercase tracking-wide text-text-muted">Időszak</label>
      <input type="date" name="tol" defaultValue={tol ?? ""} className={mezo} aria-label="Ettől" />
      <span className="text-[12px] text-text-muted">–</span>
      <input type="date" name="ig" defaultValue={ig ?? ""} className={mezo} aria-label="Eddig" />
      <button type="submit" className="btn btn-primary !py-1 !text-[12.5px]">
        Szűrés
      </button>
      {(tol || ig) && (
        <Link href={utvonal} className="text-[12.5px] text-text-secondary hover:text-text-primary hover:underline">
          Teljes időszak
        </Link>
      )}
    </form>
  );
}
