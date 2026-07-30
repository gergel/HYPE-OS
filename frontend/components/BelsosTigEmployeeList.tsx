import { StatusBadge } from "@/components/StatusBadge";
import { huEvHonap } from "@/lib/huDate";
import type { InternalPerformanceCertificate } from "@/lib/api";

function formatFt(value: number | null): string {
  return value != null ? `${value.toLocaleString("hu-HU")} Ft` : "–";
}

function statusBadge(allapot: string | null) {
  // A "Kész" a korábbi, email-küldés nélküli életciklusból maradt állapot -
  // a régi bejegyzések így vannak eltárolva (lásd backend TERMINAL_STATUSES).
  if (allapot === "Kiküldve" || allapot === "Kész") return <StatusBadge label={allapot} tone="success" />;
  if (allapot === "Kihagyva") return <StatusBadge label="Kihagyva" tone="neutral" />;
  if (allapot === "Készítés alatt") return <StatusBadge label="Készítés alatt" tone="warning" />;
  return <StatusBadge label="Nincs elkezdve" tone="neutral" />;
}

/** A munkatárs havi belsős TIG-jei egy helyen, a legfrissebb hónappal elöl:
 * mennyi volt az összeg, kiment-e, és hol a kiküldött teljesítési igazolás
 * (Drive link) meg a hozzá tartozó számlák. A hónap mindig BETŰVEL. */
export function BelsosTigEmployeeList({ records }: { records: InternalPerformanceCertificate[] }) {
  if (records.length === 0) {
    return <p className="text-[13px] text-text-muted">Nincs még belsős TIG ehhez a munkatárshoz.</p>;
  }

  const osszesen = records.reduce((sum, r) => sum + (r.brutto_osszeg ?? 0), 0);

  return (
    <table className="w-full border-collapse text-[13px]">
      <thead>
        <tr className="border-b border-border">
          <th className="py-1.5 pr-6 text-left font-medium text-text-secondary">Hónap</th>
          <th className="py-1.5 pr-6 text-left font-medium text-text-secondary">Állapot</th>
          <th className="py-1.5 pr-6 text-right font-medium text-text-secondary">Nettó</th>
          <th className="py-1.5 pr-6 text-right font-medium text-text-secondary">Bruttó</th>
          <th className="py-1.5 pr-6 text-left font-medium text-text-secondary">Teljesítési igazolás</th>
          <th className="py-1.5 text-left font-medium text-text-secondary">Számlák</th>
        </tr>
      </thead>
      <tbody>
        {records.map((r) => (
          <tr key={r.id} className="border-b border-border align-top last:border-0">
            <td className="py-2.5 pr-6 whitespace-nowrap">{huEvHonap(r.ev, r.honap)}</td>
            <td className="py-2.5 pr-6">
              <div className="flex flex-wrap items-center gap-1.5">
                {statusBadge(r.allapot)}
                {r.szamla_kifizetve && <StatusBadge label="Kifizetve" tone="success" />}
              </div>
            </td>
            <td className="py-2.5 pr-6 text-right whitespace-nowrap">{formatFt(r.netto_osszeg)}</td>
            <td className="py-2.5 pr-6 text-right whitespace-nowrap">{formatFt(r.brutto_osszeg)}</td>
            <td className="py-2.5 pr-6">
              {r.file_url ? (
                <a href={r.file_url} target="_blank" rel="noopener noreferrer" className="text-text-accent hover:underline">
                  Megnyitás
                </a>
              ) : (
                <span className="text-text-muted">–</span>
              )}
            </td>
            <td className="py-2.5">
              {r.invoices.length === 0 ? (
                <span className="text-text-muted">–</span>
              ) : (
                <div className="flex flex-col gap-1">
                  {r.invoices.map((inv) => (
                    <a
                      key={inv.id}
                      href={inv.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      title={inv.filename}
                      className="max-w-[220px] truncate text-text-accent hover:underline"
                    >
                      {inv.filename}
                    </a>
                  ))}
                </div>
              )}
            </td>
          </tr>
        ))}
        <tr>
          <td className="py-2.5 pr-6 text-text-secondary" colSpan={3}>
            Összesen
          </td>
          <td className="py-2.5 pr-6 text-right font-medium whitespace-nowrap text-text-primary">{formatFt(osszesen)}</td>
          <td colSpan={2} />
        </tr>
      </tbody>
    </table>
  );
}
