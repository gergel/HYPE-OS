import { StatusBadge } from "@/components/StatusBadge";
import { formatFt } from "@/lib/ido";
import type { ElkeszultSzerzodes } from "@/lib/api";

/** Egy projekt már elkészült eseti szerződései.
 *
 * A fölötte lévő "Szerződés készítés" blokk csak a TEENDŐKET sorolja fel:
 * amint egy szerződés kiküldésre kerül (vagy kihagyják), az onnan eltűnik.
 * Ez a lista mutatja meg, kinek van kész papírja - a generált dokumentum
 * linkjével és a szerződés adatlapjával, ahová az aláírt PDF feltölthető. */
export function ElkeszultSzerzodesek({ szerzodesek }: { szerzodesek: ElkeszultSzerzodes[] }) {
  const kesz = szerzodesek.filter((s) => s.szerzodes_allapota === "Kiküldve" || s.szerzodes_allapota === "Kihagyva");
  if (kesz.length === 0) return null;

  return (
    <div className="mt-4 border-t border-border pt-4">
      <p className="mb-2 text-[13px] font-medium text-text-primary">Elkészült szerződések</p>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[13px]">
          <thead>
            <tr className="border-b border-border">
              <th className="py-1.5 pr-6 text-left font-medium text-text-secondary">Megbízott</th>
              <th className="py-1.5 pr-6 text-left font-medium text-text-secondary">Állapot</th>
              <th className="py-1.5 pr-6 text-right font-medium text-text-secondary">Nettó</th>
              <th className="py-1.5 text-left font-medium text-text-secondary">Szerződés</th>
            </tr>
          </thead>
          <tbody>
            {kesz.map((s) => (
              <tr key={s.contract_id} className="border-b border-border last:border-0">
                <td className="py-2.5 pr-6">{s.full_name}</td>
                <td className="py-2.5 pr-6">
                  {s.szerzodes_allapota === "Kihagyva" ? (
                    <StatusBadge label="Kihagyva" tone="neutral" />
                  ) : (
                    <StatusBadge label="Kiküldve" tone="success" />
                  )}
                </td>
                <td className="whitespace-nowrap py-2.5 pr-6 text-right tabular-nums">
                  {s.netto_osszeg === null ? "–" : formatFt(s.netto_osszeg)}
                </td>
                <td className="py-2.5">
                  <span className="flex flex-wrap gap-x-3 gap-y-1">
                    {s.szerzodes_file_url && (
                      <a
                        href={s.szerzodes_file_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-text-accent hover:underline"
                      >
                        Elkészült szerződés
                      </a>
                    )}
                    {/* A szerződés saját adatlapja: ide tölthető fel az aláírva
                        visszakapott PDF. */}
                    <a href={`/szerzodesek/${s.contract_id}`} className="text-text-accent hover:underline">
                      Adatlap és fájlok
                    </a>
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
