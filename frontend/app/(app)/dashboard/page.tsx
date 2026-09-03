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
import {
  getDashboardSummary,
  getDeliverables,
  getEszkozKivitelHianyok,
  getMyAnyagKorlat,
  getMyDashboardConfig,
  getMyPageAccess,
  getMyTasksSummary,
  getProjectCodeOptions,
} from "@/lib/api";
import { EszkozHianyKartya } from "@/components/dashboard/EszkozHianyKartya";
import { KorlatozottDashboard } from "@/components/dashboard/KorlatozottDashboard";
import { MyTasksCard } from "@/components/dashboard/DashboardWidgets";
import {
  VagoiGyoztesKartya,
  VagoiNyeremenyBekero,
  VagoiUjNyeremenyKartya,
} from "@/components/dashboard/VagoiJatekKartyak";

const WIDGETS: WidgetOption[] = [
  { key: "teendoim", label: "Teendőim" },
  { key: "mai_feladatok", label: "Mai feladatok" },
  { key: "figyelmeztetesek", label: "Figyelmeztetések" },
  { key: "ai_javaslat", label: "AI javaslat", requiredPages: ["/ai-assistant"] },
  { key: "kozelgo_esemenyek", label: "Közelgő események", requiredPages: ["/projektek"] },
  { key: "projektek_statusza", label: "Projektek státusza", requiredPages: ["/projektek/project-kodok"] },
  { key: "bevetel", label: "Bevétel (havi, nettó)", requiredPages: ["/penzugyek"] },
];

function hasPage(allowedPages: string[] | null, page: string): boolean {
  return allowedPages === null || allowedPages.includes(page);
}

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
  // A KORLÁTOZOTT fiók (külsős vágó) csak a rábízott anyagot látja - neki a
  // dashboard maga a teendő-lista, semmi más. Ezt előbb kérdezzük le, hogy a
  // többi (számára úgyis üres) összesítőt el se indítsuk.
  const anyagKorlat = await getMyAnyagKorlat();
  if (anyagKorlat !== null) {
    // A lista a szerver oldalán már eleve csak az engedélyezett anyagokat
    // adja vissza (lásd backend crud_router sor_szuro).
    const sajatAnyagok = await getDeliverables(50);
    return (
      <div className="flex flex-1 flex-col">
        <TopBar />
        <div className="flex-1 p-4 md:p-8">
          <Card title={`Rád bízott anyagok (${sajatAnyagok.length})`} icon={Clapperboard}>
            <KorlatozottDashboard anyagok={sajatAnyagok} />
          </Card>
        </div>
      </div>
    );
  }

  const [summary, projectCodes, visibleWidgets, myTasks, allowedPages] = await Promise.all([
    getDashboardSummary(),
    getProjectCodeOptions(),
    getMyDashboardConfig(),
    getMyTasksSummary(),
    getMyPageAccess(),
  ]);

  // A "Mai feladatok" és "Figyelmeztetések" widget több különböző oldalra
  // mutató al-kártyát/sort tartalmaz (Forgatás->/projektek, Aktív Project
  // Code->/projektek/project-kodok, Equipment ütközés->/felszereles, stb.) -
  // ezért nem egyetlen requiredPages listával, hanem "legalább egy elérhető
  // al-elem" logikával döntjük el, hogy egyáltalán felkínálható-e a widget.
  // ESZKÖZKIVITEL-HIÁNYOK: lejárt kódú, hiányos kivitelek - jól láthatóan a
  // dashboard tetején (a felhasználó kérése). Csak annak, aki az
  // Eszközkivitelek oldalt is látja; jog nélkül a végpont üresen tér vissza.
  const eszkozHianyok = hasPage(allowedPages, "/eszkozkivitelek") ? await getEszkozKivitelHianyok() : [];

  const canSeeProjektek = hasPage(allowedPages, "/projektek");
  const canSeeProjectCodes = hasPage(allowedPages, "/projektek/project-kodok");
  const canSeeFelszereles = hasPage(allowedPages, "/felszereles");
  const canSeeUtomunka = hasPage(allowedPages, "/utomunka");
  const canSeeFeladatok = hasPage(allowedPages, "/feladatok");

  const permittedWidgets = WIDGETS.filter((w) => {
    if (w.key === "mai_feladatok") return canSeeProjektek || canSeeProjectCodes || canSeeFelszereles;
    if (w.key === "figyelmeztetesek") return canSeeUtomunka || canSeeFeladatok;
    return !w.requiredPages || w.requiredPages.every((p) => hasPage(allowedPages, p));
  });
  const permittedKeys = new Set(permittedWidgets.map((w) => w.key));

  const isVisible = (key: string) => permittedKeys.has(key) && (!visibleWidgets || visibleWidgets.includes(key));
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
      <div className="flex-1 space-y-8 p-4 sm:p-6 lg:p-8">
        {apiUnavailable && (
          <div className="rounded-[var(--radius)] border border-border bg-surface-1 px-4 py-3 text-[13px] text-text-secondary">
            A backend API ({process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}) jelenleg nem elérhető -
            demó/placeholder adatok jelennek meg.
          </div>
        )}

        {/* Vágói játék: ünneplő kártya a győztesnek (a kihirdetéstől 5 napig,
            csak neki jön adat), és nyeremény-bekérő az adminnak, amíg a folyó
            hónap nyereménye hiányzik. Szándékosan nem testreszabható widgetek:
            időszakosak, és pont az a dolguk, hogy ne lehessen elrejteni őket. */}
        {/* Eszközkivitel-hiányok: kiemelt, nem elrejthető figyelmeztetés (a
            felhasználó kérése) - csak akkor látszik, ha van nyitott hiány. */}
        {eszkozHianyok.length > 0 && <EszkozHianyKartya kezdeti={eszkozHianyok} />}

        {summary?.vagoi_jatek_nyertes && <VagoiGyoztesKartya nyertes={summary.vagoi_jatek_nyertes} />}
        {summary?.vagoi_jatek_nyeremeny_bekeres && <VagoiNyeremenyBekero />}
        {summary?.vagoi_jatek_uj_nyeremeny && (
          <VagoiUjNyeremenyKartya nyeremeny={summary.vagoi_jatek_uj_nyeremeny} />
        )}

        <div className="flex justify-end">
          <DashboardCustomizePanel widgets={permittedWidgets} initialVisible={visibleWidgets} />
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
                {canSeeProjektek && (
                  <StatCard label="Forgatás" value={summary?.mai_forgatasok ?? "–"} href="/projektek" icon={Clapperboard} tone="blue" />
                )}
                {canSeeProjectCodes && (
                  <StatCard
                    label="Aktív Project Code"
                    value={summary?.aktiv_project_codeok ?? "–"}
                    href="/projektek/project-kodok"
                    icon={Hash}
                    tone="accent"
                  />
                )}
                {canSeeFelszereles && (
                  <StatCard
                    label="Equipment ütközés"
                    value={summary?.equipment_utkozesek ?? "–"}
                    tone={summary && summary.equipment_utkozesek > 0 ? "danger" : "teal"}
                    href="/felszereles"
                    icon={AlertTriangle}
                  />
                )}
              </div>
            </Card>
          )}
          {isVisible("figyelmeztetesek") && (
            <Card title="Figyelmeztetések">
              {summary ? <AlertsCard alerts={summary.alerts} allowedPages={allowedPages} /> : <p className="text-[13px] text-text-muted">–</p>}
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
              <Card title="Bevétel (havi, nettó)" className="h-full transition-colors hover:border-text-accent/40">
                {summary ? <RevenueTrendChart trend={summary.revenue_trend} /> : <p className="text-[13px] text-text-muted">–</p>}
              </Card>
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}
