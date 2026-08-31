import Link from "next/link";
import { PapirozasFolders } from "@/components/dashboard/PapirozasFolders";
import { DashboardAlerts, MyTaskItem, MyTasksSummary, RevenueMonth, UpcomingEvent, formatHuf } from "@/lib/api";

const MONTH_SHORT = ["jan", "feb", "márc", "ápr", "máj", "jún", "júl", "aug", "szept", "okt", "nov", "dec"];

function formatShortDate(iso: string): string {
  const d = new Date(iso);
  return `${MONTH_SHORT[d.getMonth()]} ${d.getDate()}.`;
}

/** Hány nap van a határidőig (negatív = lejárt). A napok naptári napban
 * számolódnak, hogy a "ma"/"holnap" a nap folyamán stabil maradjon. */
function napokAHataridoig(iso: string): number {
  const ma = new Date();
  const maNap = new Date(ma.getFullYear(), ma.getMonth(), ma.getDate()).getTime();
  const h = new Date(iso);
  const hataridoNap = new Date(h.getFullYear(), h.getMonth(), h.getDate()).getTime();
  return Math.round((hataridoNap - maNap) / 86_400_000);
}

/** A határidő-címke: lejárt → piros "lejárt X napja", közeli (≤3 nap) →
 * sárga "ma"/"holnap"/"X nap múlva", távoli → tompított rövid dátum. */
function HataridoCimke({ hatarido }: { hatarido: string | null }) {
  if (!hatarido) return null;
  const napok = napokAHataridoig(hatarido);
  if (napok < 0) {
    const szoveg = napok === -1 ? "lejárt tegnap" : `lejárt ${-napok} napja`;
    return (
      <span className="shrink-0 rounded-full bg-bg-danger px-2 py-0.5 text-[11px] font-medium text-text-danger">
        {szoveg}
      </span>
    );
  }
  if (napok <= 3) {
    const szoveg = napok === 0 ? "ma" : napok === 1 ? "holnap" : `${napok} nap múlva`;
    return (
      <span className="shrink-0 rounded-full bg-bg-warning px-2 py-0.5 text-[11px] font-medium text-text-warning">
        {szoveg}
      </span>
    );
  }
  return <span className="shrink-0 text-text-secondary">{formatShortDate(hatarido)}</span>;
}

/** Határidő szerint növekvőbe rendez (lejárt legelöl), a határidő nélküliek
 * a lista végére kerülnek. */
function hataridoSorrend(items: MyTaskItem[]): MyTaskItem[] {
  return [...items].sort((a, b) => {
    if (!a.hatarido && !b.hatarido) return 0;
    if (!a.hatarido) return 1;
    if (!b.hatarido) return -1;
    return a.hatarido.localeCompare(b.hatarido);
  });
}

function TeendoLista({ cim, items, kulcs }: { cim: string; items: MyTaskItem[]; kulcs: string }) {
  if (items.length === 0) return null;
  return (
    <div>
      <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-text-muted">{cim}</p>
      <ul className="space-y-1">
        {hataridoSorrend(items).map((t, i) => (
          <li key={`${kulcs}-${t.id}-${i}`}>
            <Link
              href={t.link}
              className="flex items-center justify-between gap-3 rounded-[var(--radius)] px-2 py-1.5 text-[13px] transition-colors hover:bg-surface-3"
            >
              <span className="truncate text-text-primary">{t.title}</span>
              <HataridoCimke hatarido={t.hatarido} />
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function AlertsCard({ alerts, allowedPages }: { alerts: DashboardAlerts; allowedPages: string[] | null }) {
  const hasPage = (page: string) => allowedPages === null || allowedPages.includes(page);
  const items = [
    { label: "lejárt utómunka határidő", count: alerts.lejart_utomunka, href: "/utomunka" },
    { label: "lejárt feladat határidő", count: alerts.lejart_feladat, href: "/feladatok" },
  ].filter((i) => i.count > 0 && hasPage(i.href));

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
  const { deliverables, tasks, diszpok, papirozas = [], auto_teendok = [], hype_todok = [] } = myTasks;
  if (
    deliverables.length === 0 &&
    tasks.length === 0 &&
    diszpok.length === 0 &&
    papirozas.length === 0 &&
    auto_teendok.length === 0 &&
    hype_todok.length === 0
  ) {
    return <p className="text-[13px] text-text-muted">Nincs nyitott teendőd.</p>;
  }
  return (
    <div className="space-y-3">
      {/* Elöl a diszpók: ezek MÁSNAPI határidejűek, tehát a legsürgősebbek -
          lásd backend api/routes/dashboard.py _tomorrow_dispo_tasks. */}
      <TeendoLista cim="Holnapi diszpó" items={diszpok} kulcs="diszpo" />
      {/* Papírozás: csak az Adminisztráció szerepkörűeknek jön vissza a
          backendtől (belsős/külsős TIG, alvállalkozói és megrendelői
          szerződés) - lásd routes/dashboard.py _papirozas_tasks. */}
      {papirozas.length > 0 && (
        <div>
          <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-text-muted">
            Papírozás ({papirozas.length})
          </p>
          {/* Mappákba rendezve: több száz nyitott papírnál egyetlen lista
              használhatatlan lenne a dashboardon (lásd PapirozasFolders). */}
          <PapirozasFolders items={papirozas} />
        </div>
      )}
      <TeendoLista cim="Rád kiosztott utómunka" items={deliverables} kulcs="deliverable" />
      <TeendoLista cim="Rád osztott feladat" items={tasks} kulcs="task" />
      <TeendoLista cim="HYPE TO-DO" items={hype_todok} kulcs="hype-todo" />
      <TeendoLista cim="Autó teendő" items={auto_teendok} kulcs="auto-teendo" />
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

// Kategorikus szín-sorrend a design rendszerből (lila elsődleges, majd kék,
// türkiz, narancs, pink) - lásd app/globals.css szín tokenjei.
/* A fánkdiagram szegmensei a tompított kategória-tónusokból (lásd
   globals.css). Nyers hex azért, mert SVG stroke-ként megy tovább - a
   sorrend és az értékek szándékosan egyeznek a --text-* tokenekkel. */
const DONUT_COLORS = ["#7d8fa6", "#6d9490", "#b0906f", "#a88b95", "#b3a173"];

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
    <div className="flex flex-wrap items-center gap-6">
      <div
        className="relative h-32 w-32 shrink-0 rounded-full p-[3px]"
        style={{ background: gradient, boxShadow: total > 0 ? "0 0 24px -8px rgba(139,108,255,0.45)" : undefined }}
      >
        <div className="flex h-full w-full flex-col items-center justify-center rounded-full bg-surface-2">
          <p className="text-2xl font-bold text-text-primary">{total}</p>
          <p className="text-[11px] text-text-muted">összes projekt</p>
        </div>
      </div>
      <ul className="space-y-2">
        {statusCounts.map((s, i) => (
          <li key={s.label} className="flex items-center gap-2 text-[12px] text-text-secondary">
            <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: DONUT_COLORS[i % DONUT_COLORS.length] }} />
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
                <div
                  className="w-full max-w-6 rounded-t-[5px]"
                  style={{ height: `${heightPct}%`, background: "var(--accent-gradient)" }}
                />
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
