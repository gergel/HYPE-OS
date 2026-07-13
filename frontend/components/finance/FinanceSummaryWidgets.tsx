import { StatusBadge } from "@/components/StatusBadge";
import { formatDate, formatHuf, FinanceSummary } from "@/lib/api";

const MONTH_SHORT = ["jan", "feb", "márc", "ápr", "máj", "jún", "júl", "aug", "szept", "okt", "nov", "dec"];

const EXPENSE_COLOR = "#fb923c";

/** Havi bevétel/kiadás trend - két sorozat UGYANAZON a (forint) tengelyen,
 * nem két külön skálán, ezért csoportosított oszlopdiagram, nem kettős
 * tengelyes vonaldiagram. Legenda mindig látszik (2 sorozat), a sávok
 * hover-re a pontos összeget mutatják (natív title attribútum). */
export function FinanceMonthlyChart({ trend }: { trend: FinanceSummary["havi_trend"] }) {
  const max = Math.max(1, ...trend.flatMap((t) => [t.bevetel, t.kiadas]));
  return (
    <div>
      <div className="mb-4 flex items-center gap-4 text-[12px] text-text-secondary">
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: "var(--accent-solid)" }} />
          Bevétel
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: EXPENSE_COLOR }} />
          Kiadás
        </span>
      </div>
      <div className="flex h-40 items-end gap-3">
        {trend.map((t) => {
          const month = Number(t.month.split("-")[1]) - 1;
          const bevPct = t.bevetel > 0 ? Math.max(3, (t.bevetel / max) * 100) : 1;
          const kiadPct = t.kiadas > 0 ? Math.max(3, (t.kiadas / max) * 100) : 1;
          return (
            <div key={t.month} className="flex flex-1 flex-col items-center gap-2">
              <div className="flex h-32 w-full items-end justify-center gap-[3px]">
                <div
                  title={`Bevétel (${MONTH_SHORT[month]}): ${formatHuf(t.bevetel)}`}
                  className="w-full max-w-3.5 rounded-t-[4px]"
                  style={{ height: `${bevPct}%`, background: "var(--accent-gradient)" }}
                />
                <div
                  title={`Kiadás (${MONTH_SHORT[month]}): ${formatHuf(t.kiadas)}`}
                  className="w-full max-w-3.5 rounded-t-[4px]"
                  style={{ height: `${kiadPct}%`, background: EXPENSE_COLOR }}
                />
              </div>
              <p className="text-[10px] text-text-muted">{MONTH_SHORT[month]}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** Kintlévőségek: kifizetetlen bevétel-sorok project code-onként összesítve
 * (lásd backend finance.py finance_summary) - a legnagyobb összeggel elöl,
 * lejárt határidejű piros jelzéssel. */
export function OutstandingProjectsTable({ projects }: { projects: FinanceSummary["kintlevo_projektek"] }) {
  if (projects.length === 0) {
    return <p className="text-[13px] text-text-secondary">Nincs nyitott kintlévőség - minden bevétel kifizetve.</p>;
  }
  return (
    <table className="w-full border-collapse text-[13px]">
      <thead>
        <tr className="border-b border-border">
          <th className="py-1.5 text-left font-medium text-text-secondary">Projekt</th>
          <th className="py-1.5 text-left font-medium text-text-secondary">Ügyfél</th>
          <th className="py-1.5 text-right font-medium text-text-secondary">Kintlévő</th>
          <th className="py-1.5 text-right font-medium text-text-secondary">Határidő</th>
        </tr>
      </thead>
      <tbody>
        {projects.map((p) => (
          <tr key={p.project_code_id} className="border-b border-border last:border-0">
            <td className="py-2 pr-4">
              <a href={`/projektek/project-kodok/${p.project_code_id}`} className="text-text-accent hover:underline">
                {p.projektkod}
              </a>
            </td>
            <td className="py-2 pr-4 text-text-secondary">{p.ugyfel_nev ?? "–"}</td>
            <td className="py-2 text-right font-medium text-text-primary">{formatHuf(p.kintlevo_osszeg)}</td>
            <td className="py-2 text-right">
              {p.legkorabbi_hatarido ? (
                <StatusBadge label={formatDate(p.legkorabbi_hatarido)} tone={p.lejart ? "danger" : "warning"} />
              ) : (
                "–"
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
