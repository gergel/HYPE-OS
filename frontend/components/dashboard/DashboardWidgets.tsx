import Link from "next/link";
import { DashboardAlerts, MyTasksSummary, RevenueMonth, UpcomingEvent, formatHuf } from "@/lib/api";

const MONTH_SHORT = ["jan", "feb", "márc", "ápr", "máj", "jún", "júl", "aug", "szept", "okt", "nov", "dec"];

function formatShortDate(iso: string): string {
  const d = new Date(iso);
  return `${MONTH_SHORT[d.getMonth()]} ${d.getDate()}.`;
}

export function AlertsCard({ alerts }: { alerts: DashboardAlerts }) {
  const items = [
    { label: "lejárt utómunka határidő", count: alerts.lejart_utomunka, href: "/utomunka" },
    { label: "lejárt feladat határidő", count: alerts.lejart_feladat, href: "/feladatok" },
  ].filter((i) => i.count > 0);

  if (items.length === 0) {
    return <p className="text-[13px] text-text-muted">Nincs aktív figyelmeztetés.</p>;
  }

  return (
    <div className="space-y-2.5">
      {items.map((i) => (
        <Link
          key={i.label}
          href={i.href}
          className="flex items-center gap-2 rounded-[var(--radius)] bg-bg-warning px-3 py-2.5 text-[13px] text-text-warning transition-colors hover:opacity-90"
        >
          <span className="font-medium">{i.count}</span> {i.label}
        </Link>
      ))}
    </div>
  );
}

export function MyTasksCard({ myTasks }: { myTasks: MyTasksSummary }) {
  const { deliverables, tasks } = myTasks;
  if (deliverables.length === 0 && tasks.length === 0) {
    return <p className="text-[13px] text-text-muted">Nincs nyitott teendőd.</p>;
  }
  return (
    <div className="space-y-3">
      {deliverables.length > 0 && (
        <div>
          <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-text-muted">Rád kiosztott utómunka</p>
          <ul className="space-y-1">
            {deliverables.map((d) => (
              <li key={`deliverable-${d.id}`}>
                <Link
                  href={d.link}
                  className="flex items-center justify-between gap-3 rounded-[var(--radius)] px-2 py-1.5 text-[13px] transition-colors hover:bg-surface-3"
                >
                  <span className="truncate text-text-primary">{d.title}</span>
                  {d.hatarido && <span className="shrink-0 text-text-secondary">{formatShortDate(d.hatarido)}</span>}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
      {tasks.length > 0 && (
        <div>
          <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-text-muted">Rád osztott feladat</p>
          <ul className="space-y-1">
            {tasks.map((t) => (
              <li key={`task-${t.id}`}>
                <Link
                  href={t.link}
                  className="flex items-center justify-between gap-3 rounded-[var(--radius)] px-2 py-1.5 text-[13px] transition-colors hover:bg-surface-3"
                >
                  <span className="truncate text-text-primary">{t.title}</span>
                  {t.hatarido && <span className="shrink-0 text-text-secondary">{formatShortDate(t.hatarido)}</span>}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export function AiSuggestionCard() {
  return (
    <div className="flex h-full flex-col justify-between gap-4">
      <p className="text-[13px] text-text-secondary">
        Kérdezd az AI Assistantot a mai forgatásokról, az ütemezésről vagy bármelyik projekt állapotáról.
      </p>
      <Link
        href="/ai-assistant"
        className="inline-flex w-fit items-center gap-1.5 rounded-[var(--radius)] bg-bg-accent px-3 py-1.5 text-[13px] font-medium text-text-accent hover:opacity-90"
      >
        Kérdezek valamit →
      </Link>
    </div>
  );
}

export function UpcomingEventsCard({ events }: { events: UpcomingEvent[] }) {
  if (events.length === 0) {
    return <p className="text-[13px] text-text-muted">Nincs közelgő forgatás.</p>;
  }
  return (
    <ul className="space-y-1.5">
      {events.map((e) => (
        <li key={e.id}>
          <Link
            href={`/projektek/${e.id}`}
            className="flex items-center justify-between gap-3 rounded-[var(--radius)] px-2 py-2 text-[13px] transition-colors hover:bg-surface-3"
          >
            <div className="min-w-0">
              <p className="truncate text-text-primary">{e.nev}</p>
              {e.helyszin && <p className="truncate text-[12px] text-text-muted">{e.helyszin}</p>}
            </div>
            <span className="shrink-0 text-text-secondary">{e.forgatas_datuma ? formatShortDate(e.forgatas_datuma) : "–"}</span>
          </Link>
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
    <div className="flex flex-wrap items-center gap-5">
      <div className="relative h-28 w-28 shrink-0 rounded-full" style={{ background: gradient }}>
        <div className="absolute inset-2 flex flex-col items-center justify-center rounded-full bg-surface-2">
          <p className="text-xl font-semibold text-text-primary">{total}</p>
          <p className="text-[11px] text-text-muted">összes projekt</p>
        </div>
      </div>
      <ul className="space-y-2">
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
      <div className="flex h-28 items-end gap-3">
        {trend.map((t) => {
          const heightPct = t.total > 0 ? Math.max(4, (t.total / max) * 100) : 2;
          const month = Number(t.month.split("-")[1]) - 1;
          return (
            <div key={t.month} className="flex flex-1 flex-col items-center gap-2">
              <div className="flex h-24 w-full items-end justify-center">
                <div className="w-full max-w-6 rounded-t-[4px] bg-text-accent" style={{ height: `${heightPct}%` }} />
              </div>
              <p className="text-[10px] text-text-muted">{MONTH_SHORT[month]}</p>
            </div>
          );
        })}
      </div>
      <p className="mt-3 text-[12px] text-text-muted">
        Utolsó hónap: <span className="text-text-secondary">{formatHuf(trend[trend.length - 1]?.total ?? 0)}</span>
      </p>
    </div>
  );
}
