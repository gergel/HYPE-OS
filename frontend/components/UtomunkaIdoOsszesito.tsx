import type { UtomunkaProjektIdo } from "@/lib/api";

function formatPerc(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = Math.round(minutes % 60);
  return h > 0 ? `${h} ó ${m} p` : `${m} p`;
}

/** Melyik projekten mennyit dolgozott ez a vágó utómunkával, összesítve - a
 * személy adatlapján, közvetlenül a neve alatt. Az egyes munkaidő-sorok az
 * anyagok oldalán javíthatók (lásd TimesheetMinutesTable); ez csak az
 * összkép.
 *
 * A forintos oszlop csak akkor jelenik meg, ha a backend küldött összeget -
 * Pénzügy-hozzáférés nélkül nem küld (lásd crew.py get_utomunka_ido). */
export function UtomunkaIdoOsszesito({ rows }: { rows: UtomunkaProjektIdo[] }) {
  if (rows.length === 0) {
    return <p className="text-[13px] text-text-muted">Nincs rögzített utómunka-idő ehhez a munkatárshoz.</p>;
  }

  const showCost = rows.some((r) => r.total_cost != null);
  const osszesPerc = rows.reduce((sum, r) => sum + r.total_minutes, 0);
  const osszesKoltseg = rows.reduce((sum, r) => sum + (r.total_cost ?? 0), 0);

  return (
    <table className="w-full border-collapse text-[13px]">
      <thead>
        <tr className="border-b border-border">
          <th className="py-1.5 pr-4 text-left font-medium text-text-secondary">Projekt</th>
          <th className="py-1.5 pr-4 text-right font-medium text-text-secondary">Anyagok</th>
          <th className="py-1.5 pr-4 text-right font-medium text-text-secondary">Idő</th>
          {showCost && <th className="py-1.5 text-right font-medium text-text-secondary">Költség</th>}
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.project_id ?? "nincs"} className="border-b border-border last:border-0">
            <td className="py-2 pr-4">
              {r.project_id ? (
                <a href={`/projektek/${r.project_id}`} className="text-text-accent hover:underline">
                  {r.project_nev ?? `Projekt #${r.project_id}`}
                </a>
              ) : (
                <span className="text-text-muted">Projekt nélküli anyagok</span>
              )}
              {r.projektkod && <span className="ml-2 text-[11px] text-text-muted">{r.projektkod}</span>}
            </td>
            <td className="py-2 pr-4 text-right text-text-secondary">{r.anyagok_szama}</td>
            <td className="py-2 pr-4 text-right whitespace-nowrap">{formatPerc(r.total_minutes)}</td>
            {showCost && (
              <td className="py-2 text-right whitespace-nowrap text-text-secondary">
                {r.total_cost != null ? `${Math.round(r.total_cost).toLocaleString("hu-HU")} Ft` : "–"}
              </td>
            )}
          </tr>
        ))}
        <tr>
          <td className="py-2 pr-4 text-text-secondary" colSpan={2}>
            Összesen
          </td>
          <td className="py-2 pr-4 text-right font-medium whitespace-nowrap text-text-primary">
            {formatPerc(osszesPerc)}
          </td>
          {showCost && (
            <td className="py-2 text-right font-medium whitespace-nowrap text-text-primary">
              {`${Math.round(osszesKoltseg).toLocaleString("hu-HU")} Ft`}
            </td>
          )}
        </tr>
      </tbody>
    </table>
  );
}
