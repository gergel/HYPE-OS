import { AlertTriangle, Clapperboard, Hash } from "lucide-react";
import Link from "next/link";
import { Card } from "@/components/Card";
import { DashboardCustomizePanel, WidgetOption } from "@/components/DashboardCustomizePanel";
import {
  AiSuggestionCard,
  AlertsCard,
  ProjectStatusDonut,
  RevenueTrendChart,
  UpcomingEventsCard,
} from "@/components/dashboard/DashboardWidgets";
import { StatCard } from "@/components/StatCard";
import { TopBar } from "@/components/TopBar";
import { getDashboardSummary, getMyDashboardConfig, getMyTasksSummary, getProjectCodes } from "@/lib/api";
import { MyTasksCard } from "@/components/dashboard/DashboardWidgets";

const WIDGETS: WidgetOption[] = [
  { key: "teendoim", label: "Teendőim" },
  { key: "mai_feladatok", label: "Mai feladatok" },
  { key: "figyelmeztetesek", label: "Figyelmeztetések" },
  { key: "ai_javaslat", label: "AI javaslat" },
  { key: "kozelgo_esemenyek", label: "Közelgő események" },
  { key: "projektek_statusza", label: "Projektek státusza" },
  { key: "bevetel", label: "Bevétel (havi)" },
];

const STATUS_LABEL: Record<string, string> = {
  folyamatban: "Folyamatban",
  tervezes: "Tervezés",
  kesz: "Kész",
  lezarva: "Lezárva",
};

function normalizedStatusLabel(allapot: string | null): string {
  if (!allapot) return "Nincs státusz";
  return STATUS_LABEL[allapot.toLowerCase()] ?? allapot;
}

export default async function DashboardPage() {
  const [summary, projectCodes, visibleWidgets, myTasks] = await Promise.all([
    getDashboardSummary(),
    getProjectCodes(),
    getMyDashboardConfig(),
    getMyTasksSummary(),
  ]);

  const isVisible = (key: string) => !visibleWidgets || visibleWidgets.includes(key);
  const apiUnavailable = summary === null;

  const statusCounts = Array.from(
    projectCodes.reduce((map, pc) => {
      const label = normalizedStatusLabel(pc.esemeny_allapota);
      map.set(label, (map.get(label) ?? 0) + 1);
      return map;
    }, new Map<string, number>()),
  ).map(([label, value]) => ({ label, value }));

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-8 p-6 lg:p-8">
        {apiUnavailable && (
          <div className="rounded-[var(--radius)] border border-border bg-surface-1 px-4 py-3 text-[13px] text-text-secondary">
            A backend API ({process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}) jelenleg nem elérhető -
            demó/placeholder adatok jelennek meg.
          </div>
        )}

        <div className="flex justify-end">
          <DashboardCustomizePanel widgets={WIDGETS} initialVisible={visibleWidgets} />
        </div>

        <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3">
          {isVisible("teendoim") && (
            <Card title="Teendőim">
              {myTasks ? <MyTasksCard myTasks={myTasks} /> : <p className="text-[13px] text-text-muted">–</p>}
            </Card>
          )}
          {isVisible("mai_feladatok") && (
            <Card title="Mai feladatok">
              <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-3">
                <StatCard label="Forgatás" value={summary?.mai_forgatasok ?? "–"} href="/projektek" icon={Clapperboard} tone="blue" />
                <StatCard
                  label="Aktív Project Code"
                  value={summary?.aktiv_project_codeok ?? "–"}
                  href="/projektek/project-kodok"
                  icon={Hash}
                  tone="accent"
                />
                <StatCard
                  label="Equipment ütközés"
                  value={summary?.equipment_utkozesek ?? "–"}
                  tone={summary && summary.equipment_utkozesek > 0 ? "danger" : "teal"}
                  href="/felszereles"
                  icon={AlertTriangle}
                />
              </div>
            </Card>
          )}
          {isVisible("figyelmeztetesek") && (
            <Card title="Figyelmeztetések">
              {summary ? <AlertsCard alerts={summary.alerts} /> : <p className="text-[13px] text-text-muted">–</p>}
            </Card>
          )}
          {isVisible("ai_javaslat") && (
            <Card title="AI javaslat">
              <AiSuggestionCard />
            </Card>
          )}
        </div>

        <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3">
          {isVisible("kozelgo_esemenyek") && (
            <Card title="Közelgő események">
              {summary ? <UpcomingEventsCard events={summary.upcoming_events} /> : <p className="text-[13px] text-text-muted">–</p>}
            </Card>
          )}
          {isVisible("projektek_statusza") && (
            <Link href="/projektek/project-kodok" className="block">
              <Card title="Projektek státusza" className="h-full transition-colors hover:border-text-accent/40">
                <ProjectStatusDonut statusCounts={statusCounts} />
              </Card>
            </Link>
          )}
          {isVisible("bevetel") && (
            <Link href="/penzugyek" className="block">
              <Card title="Bevétel (havi)" className="h-full transition-colors hover:border-text-accent/40">
                {summary ? <RevenueTrendChart trend={summary.revenue_trend} /> : <p className="text-[13px] text-text-muted">–</p>}
              </Card>
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}
