import { AlertCircle, TrendingDown, TrendingUp, Wallet } from "lucide-react";
import {
  ENTITY_PATHS,
  Expense,
  formatHuf,
  getCurrentUser,
  getExpenses,
  getFinanceSummary,
  getMyPagePermissions,
  getProjectCodes,
  getRevenues,
  Revenue,
} from "@/lib/api";
import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { FinanceMonthlyChart, OutstandingProjectsTable } from "@/components/finance/FinanceSummaryWidgets";
import { QuickCreateForm } from "@/components/QuickCreateForm";
import { StatCard } from "@/components/StatCard";
import { StatusBadge } from "@/components/StatusBadge";
import { TopBar } from "@/components/TopBar";
import { canDoAction } from "@/lib/permissions";

const PAGE = "/penzugyek";

export default async function PenzugyekPage() {
  const [expenses, revenues, summary, projectCodes, currentUser, pagePermissions] = await Promise.all([
    getExpenses(),
    getRevenues(),
    getFinanceSummary(),
    getProjectCodes(),
    getCurrentUser(),
    getMyPagePermissions(),
  ]);
  const canCreate = canDoAction(currentUser?.role, pagePermissions, PAGE, "create");
  const canDelete = canDoAction(currentUser?.role, pagePermissions, PAGE, "delete");

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-6 p-6">
        {summary && (
          <>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <StatCard label="Bevétel (idén)" value={formatHuf(summary.ytd_bevetel)} icon={TrendingUp} tone="teal" />
              <StatCard label="Kiadás (idén)" value={formatHuf(summary.ytd_kiadas)} icon={TrendingDown} tone="orange" />
              <StatCard
                label="Profit (idén)"
                value={formatHuf(summary.ytd_profit)}
                icon={Wallet}
                tone={summary.ytd_profit >= 0 ? "accent" : "danger"}
              />
              <StatCard
                label={`Kintlévőség (${summary.kintlevo_projektek_szama} projekt)`}
                value={formatHuf(summary.osszes_kintlevoseg)}
                icon={AlertCircle}
                tone={summary.osszes_kintlevoseg > 0 ? "pink" : "blue"}
              />
            </div>

            <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
              <Card title="Bevétel / kiadás - utolsó 12 hónap">
                <FinanceMonthlyChart trend={summary.havi_trend} />
              </Card>
              <Card title="Kintlévőségek projektenként">
                <OutstandingProjectsTable projects={summary.kintlevo_projektek} />
              </Card>
            </div>
          </>
        )}

        <Card title={`Kiadások (${expenses.length})`}>
          {canCreate && (
            <QuickCreateForm
              postPath={ENTITY_PATHS.expense}
              addLabel="+ Új kiadás hozzáadása"
              fields={[
                { name: "megnevezes", label: "Megnevezés", required: true },
                { name: "netto", label: "Nettó", type: "number" },
              ]}
            />
          )}
          <DataTable<Expense>
            rows={expenses}
            emptyText="Még nincs felvett kiadás - importáld a Notionból, vagy adj hozzá egyet a fenti gombbal."
            getHref={(e) => `/penzugyek/kiadas/${e.id}`}
            deleteHref={canDelete ? (e) => `${ENTITY_PATHS.expense}/${e.id}` : undefined}
            filterable
            columns={[
              { header: "Megnevezés", render: (e) => e.megnevezes, sortAccessor: (e) => e.megnevezes },
              { header: "Típus", render: (e) => e.tipus ?? "–", sortAccessor: (e) => e.tipus },
              { header: "Nettó", align: "right", render: (e) => formatHuf(e.netto), sortAccessor: (e) => e.netto },
              { header: "Bruttó", align: "right", render: (e) => formatHuf(e.brutto), sortAccessor: (e) => e.brutto },
              {
                header: "Kész",
                align: "right",
                render: (e) => <StatusBadge label={e.kesz ? "Kifizetve" : "Nyitott"} tone={e.kesz ? "success" : "warning"} />,
                sortAccessor: (e) => (e.kesz ? 1 : 0),
              },
            ]}
          />
        </Card>

        <Card title={`Bevételek (${revenues.length})`}>
          {canCreate && (
            <QuickCreateForm
              postPath={ENTITY_PATHS.revenue}
              addLabel="+ Új bevétel hozzáadása"
              fields={[
                {
                  name: "project_code_id",
                  label: "Project Code",
                  type: "select",
                  required: true,
                  options: projectCodes.map((pc) => ({ value: pc.id, label: pc.projektkod })),
                },
                { name: "netto", label: "Nettó", type: "number" },
              ]}
            />
          )}
          <DataTable<Revenue>
            rows={revenues}
            emptyText="Még nincs felvett bevétel - importáld a Notionból, vagy adj hozzá egyet a fenti gombbal."
            getHref={(r) => `/penzugyek/bevetel/${r.id}`}
            deleteHref={canDelete ? (r) => `${ENTITY_PATHS.revenue}/${r.id}` : undefined}
            filterable
            columns={[
              { header: "Forma", render: (r) => r.bevetel_formaja ?? "–", sortAccessor: (r) => r.bevetel_formaja },
              { header: "Nettó", align: "right", render: (r) => formatHuf(r.netto), sortAccessor: (r) => r.netto },
              { header: "Bruttó", align: "right", render: (r) => formatHuf(r.brutto), sortAccessor: (r) => r.brutto },
              { header: "Pénznem", align: "right", render: (r) => r.penznem, sortAccessor: (r) => r.penznem },
            ]}
          />
        </Card>
      </div>
    </div>
  );
}
