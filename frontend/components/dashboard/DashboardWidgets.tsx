import { DashboardAlerts, RevenueMonth, UpcomingEvent, formatHuf } from "@/lib/api";

const MONTH_SHORT = ["jan", "feb", "márc", "ápr", "máj", "jún", "júl", "aug", "szept", "okt", "nov", "dec"];

function formatShortDate(iso: string): string {
  const d = new Date(iso);
  return `${MONTH_SHORT[d.getMonth()]} ${d.getDate()}.`;
}

export function AlertsCard({ alerts }: { alerts: DashboardAlerts }) {
  const items = [
    { label: "lejárt utómunka határidő", count: alerts.lejart_utomunka },
    { label: "lejárt feladat határidő", count: alerts.lejart_feladat },
  ].filter((i) => i.count > 0);

  if (items.length === 0) {
    return <p className="text-[13px] text-text-muted">Nincs aktív figyelmeztetés.</p>;
  }

  return (
    <div className="space-y-2">
      {items.map((i) => (
        <div
          key={i.label}
          className="flex items-center gap-2 rounded-[var(--radius)] bg-bg-warning px-3 py-2 text-[13px] text-text-warning"
        >
          <span className="font-medium">{i.count}</span> {i.label}
        </div>
      ))}
    </div>
  );
}

export function AiSuggestionCard() {
  return (
    <div className="flex h-full flex-col justify-between gap-3">
      <p className="text-[13px] text-text-secondary">
        Kérdezd az AI Assistantot a mai forgatásokról, az ütemezésről vagy bármelyik projekt állapotáról.
      </p>
      <a
        href="/ai-assistant"
        className="inline-flex w-fit items-center gap-1.5 rounded-[var(--radius)] bg-bg-accent px-3 py-1.5 text-[13px] font-medium text-text-accent hover:opacity-90"
      >
        Kérdezek valamit →
      </a>
    </div>
  );
}

export function UpcomingEventsCard({ events }: { events: UpcomingEvent[] }) {
  if (events.length === 0) {
    return <p className="text-[13px] text-text-muted">Nincs közelgő forgatás.</p>;
  }
  return (
    <ul className="space-y-2.5">
      {events.map((e) => (
        <li key={e.id} className="flex items-center justify-between gap-3 text-[13px]">
          <div className="min-w-0">
            <p className="truncate text-text-primary">{e.nev}</p>
            {e.helyszin && <p className="truncate text-[12px] text-text-muted">{e.helyszin}</p>}
          </div>
          <span className="shrink-0 text-text-secondary">{e.forgatas_datuma ? formatShortDate(e.forgatas_datuma) : "–"}</span>
        </li>
      ))}
    </ul>
  );
}

const DONUT_COLORS = ["#93c5fd", "#86efac", "#fbbf24", "#fca5a5", "#a1a1aa"];

export function ProjectStatusDonut({ statusCounts }: { statusCounts: { label: string; value: number }[] }) {
  const total = statusCounts.reduce((sum, s) => sum + s.value, 0);
  let cumulative = 0;
  const stops = statusCounts.map((s, i) => {
    const start = total > 0 ? (cumulative / total) * 360 : 0;
    cumulative += s.value;
    const end = total > 0 ? (cumulative / total) * 360 : 0;
    return `${DONUT_COLORS[i % DONUT_COLORS.length]} ${start}deg ${end}deg`;
  });
  const gradient = total > 0 ? `conic-gradient(${stops.join(", ")})` : "conic-gradient(var(--surface-3) 0deg 360deg)";

  return (
    <div className="flex items-center gap-4">
      <div className="relative h-28 w-28 shrink-0 rounded-full" style={{ background: gradient }}>
        <div className="absolute inset-2 flex flex-col items-center justify-center rounded-full bg-surface-2">
          <p className="text-xl font-semibold text-text-primary">{total}</p>
          <p className="text-[11px] text-text-muted">összes projekt</p>
        </div>
      </div>
      <ul className="space-y-1.5">
        {statusCounts.map((s, i) => (
          <li key={s.label} className="flex items-center gap-2 text-[12px] text-text-secondary">
            <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: DONUT_COLORS[i % DONUT_COLORS.length] }} />
            <span className="truncate">{s.label}</span> <span className="text-text-muted">({s.value})</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function RevenueTrendChart({ trend }: { trend: RevenueMonth[] }) {
  const max = Math.max(1, ...trend.map((t) => t.total));
  return (
    <div>
      <div className="flex h-28 items-end gap-2">
        {trend.map((t) => {
          const heightPct = t.total > 0 ? Math.max(4, (t.total / max) * 100) : 2;
          const month = Number(t.month.split("-")[1]) - 1;
          return (
            <div key={t.month} className="flex flex-1 flex-col items-center gap-1.5">
              <div className="flex h-24 w-full items-end justify-center">
                <div className="w-full max-w-6 rounded-t-[4px] bg-text-accent" style={{ height: `${heightPct}%` }} />
              </div>
              <p className="text-[10px] text-text-muted">{MONTH_SHORT[month]}</p>
            </div>
          );
        })}
      </div>
      <p className="mt-2 text-[12px] text-text-muted">
        Utolsó hónap: <span className="text-text-secondary">{formatHuf(trend[trend.length - 1]?.total ?? 0)}</span>
      </p>
    </div>
  );
}
