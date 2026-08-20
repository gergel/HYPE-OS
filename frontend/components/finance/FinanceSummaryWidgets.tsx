import { StatusBadge } from "@/components/StatusBadge";
import { formatDate, formatHuf, FinanceSummary } from "@/lib/api";

const MONTH_SHORT = ["jan", "feb", "márc", "ápr", "máj", "jún", "júl", "aug", "szept", "okt", "nov", "dec"];

const EXPENSE_COLOR = "var(--text-orange)";

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
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: "var(--text-blue)" }} />
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
                  style={{ height: `${bevPct}%`, background: "var(--text-blue)" }}
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
          <th className="py-1.5 text-left font-medium text-text-secondary">Projektkód</th>
          {/* A munka NEVE, nem az ügyfélé: a régi, Notionból importált
              kódoknál az ügyfél többnyire "Ismeretlen ügyfél (Notion
              import)" volt, tehát ez az oszlop nem mondott semmit arról,
              MI ez a tétel. */}
          <th className="py-1.5 text-left font-medium text-text-secondary">Projekt</th>
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
            <td className="py-2 pr-4 text-text-secondary">{p.projekt_nev ?? "–"}</td>
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

/** MENNYI KÉSZPÉNZ VAN A KASSZÁBAN - és hogyan alakult.
 *
 * A kassza egy fizikai doboz: az egyenlege a készpénzes bevételek és kiadások
 * különbsége, BRUTTÓBAN (egy doboz pénz nem tud nettó lenni - lásd backend
 * services/fizetesi_mod.py).
 *
 * A diagram két dolgot mond egyszerre: a havi be/ki mozgást (oszlopok,
 * ugyanazon a forint-tengelyen) és a hónap végi EGYENLEGET (a szám az oszlopok
 * alatt). Nem kettős tengely: az egyenleg számként áll ott, nem vonalként egy
 * másik skálán - két különböző skálájú görbe egy képen többet hazudik, mint
 * amennyit mutat. */
export function KasszaWidget({ kassza }: { kassza: FinanceSummary["kassza"] }) {
  const max = Math.max(1, ...kassza.havi.flatMap((h) => [h.be, h.ki]));
  const jeloletlen = kassza.jeloletlen_kiadas + kassza.jeloletlen_bevetel;
  return (
    <div>
      <div className="mb-4 flex flex-wrap items-baseline gap-x-6 gap-y-1">
        <p className="text-[26px] font-semibold tracking-[-0.02em] text-text-primary">
          {formatHuf(kassza.egyenleg)}
        </p>
        <p className="text-[12.5px] text-text-secondary">
          idén <span className="text-text-teal">+{formatHuf(kassza.idei_be)}</span> be ·{" "}
          <span style={{ color: EXPENSE_COLOR }}>−{formatHuf(kassza.idei_ki)}</span> ki
        </p>
      </div>

      {/* Amíg van megjelöletlen tétel, az egyenleg csak közelítés - ezt ki kell
          mondani, különben egy hiányos szám tűnik pontosnak. */}
      {jeloletlen > 0 && (
        <p className="mb-3 text-[12px] text-text-warning">
          {jeloletlen} kifizetett tételen nincs megjelölve a fizetési mód ({kassza.jeloletlen_kiadas} kiadás,{" "}
          {kassza.jeloletlen_bevetel} bevétel) – amíg ez így van, az egyenleg csak közelítés.
        </p>
      )}

      <div className="mb-3 flex items-center gap-4 text-[12px] text-text-secondary">
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: "var(--text-teal)" }} />
          Készpénz be
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: EXPENSE_COLOR }} />
          Készpénz ki
        </span>
      </div>

      <div className="flex h-40 items-end gap-3">
        {kassza.havi.map((h) => {
          const month = Number(h.month.split("-")[1]) - 1;
          const bePct = h.be > 0 ? Math.max(3, (h.be / max) * 100) : 1;
          const kiPct = h.ki > 0 ? Math.max(3, (h.ki / max) * 100) : 1;
          return (
            <div key={h.month} className="flex flex-1 flex-col items-center gap-2">
              <div className="flex h-32 w-full items-end justify-center gap-[3px]">
                <div
                  title={`Készpénz be (${MONTH_SHORT[month]}): ${formatHuf(h.be)}`}
                  className="w-full max-w-3.5 rounded-t-[4px]"
                  style={{ height: `${bePct}%`, background: "var(--text-teal)" }}
                />
                <div
                  title={`Készpénz ki (${MONTH_SHORT[month]}): ${formatHuf(h.ki)}`}
                  className="w-full max-w-3.5 rounded-t-[4px]"
                  style={{ height: `${kiPct}%`, background: EXPENSE_COLOR }}
                />
              </div>
              <p className="text-[10px] text-text-muted">{MONTH_SHORT[month]}</p>
              <p
                className={`text-[10px] ${h.egyenleg < 0 ? "text-text-danger" : "text-text-secondary"}`}
                title={`A hónap végén a kasszában: ${formatHuf(h.egyenleg)}`}
              >
                {formatHuf(h.egyenleg)}
              </p>
            </div>
          );
        })}
      </div>
      <p className="mt-3 text-[12px] text-text-muted">
        A készpénzesnek jelölt bevételek és kiadások különbsége, bruttóban. A hónap alatti szám a hónap VÉGI
        egyenleg.
      </p>
    </div>
  );
}
