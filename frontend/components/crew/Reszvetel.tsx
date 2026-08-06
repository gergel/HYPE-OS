import Link from "next/link";
import { formatPercek } from "@/lib/ido";
import type { ReszvetelSor } from "@/lib/api";

/** Miken vett részt ez a munkatárs - forgatáson, vágáson vagy mindkettőn.
 *
 * Minden munkatársnál megjelenik (belsősnél és külsősnél is), mert ez az a
 * kérdés, amit egy adatlapon először keres az ember: min dolgozott. A két
 * részvételi mód szándékosan EGY listában van, soronként jelölve - van, aki
 * csak forgat, van, aki csak vág, és van, aki ugyanazon a projekten mindkettő.
 *
 * A vágás nem a kijelölt vágóból (Deliverable.vago_employee_id) jön, hanem a
 * tényleges munkaidő-sorokból: egy anyagon többen is dolgozhattak. */
export function Reszvetel({ sorok }: { sorok: ReszvetelSor[] }) {
  if (sorok.length === 0) {
    return <p className="text-[13px] text-text-muted">Ez a munkatárs még egyetlen projekten sem vett részt.</p>;
  }

  const forgatas = sorok.filter((s) => s.stabtag).length;
  const vagas = sorok.filter((s) => s.vagott).length;

  return (
    <div className="space-y-3">
      <p className="text-[12.5px] text-text-secondary">
        {forgatas} forgatás
        {vagas > 0 && ` · ${vagas} projekten vágott is`}
      </p>
      <div className="overflow-x-auto">
        <table className="os-table w-full border-collapse text-[13px]">
          <thead>
            <tr>
              <th className="text-left">Projekt</th>
              <th className="text-left">Forgatás</th>
              <th className="text-left">Mit csinált</th>
              <th className="text-right">Vágással töltött idő</th>
            </tr>
          </thead>
          <tbody>
            {sorok.map((sor) => (
              <tr key={sor.project_id}>
                <td>
                  <Link href={`/projektek/${sor.project_id}`} className="text-text-accent hover:underline">
                    {sor.project_nev ?? `#${sor.project_id}`}
                  </Link>
                  {sor.projektkod && <span className="ml-2 text-[12px] text-text-muted">{sor.projektkod}</span>}
                </td>
                <td className="whitespace-nowrap text-text-secondary">{sor.forgatas_datuma ?? "–"}</td>
                <td className="text-text-secondary">
                  <span className="flex flex-wrap gap-x-2">
                    {sor.stabtag && <span>Stábtag</span>}
                    {sor.vagott && (
                      <span className="text-text-accent">
                        Vágás{sor.anyagok_szama > 1 ? ` (${sor.anyagok_szama} anyag)` : ""}
                      </span>
                    )}
                  </span>
                </td>
                <td className="whitespace-nowrap text-right tabular-nums text-text-secondary">
                  {sor.vagott ? formatPercek(sor.vagas_percek) : "–"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
