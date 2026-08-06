import { AlertCircle, TrendingDown, TrendingUp, Wallet } from "lucide-react";
import {
  ENTITY_PATHS,
  Expense,
  formatHuf,
  getCurrentUser,
  getExpenses,
  getFieldTypes,
  getFinanceSummary,
  getMyPagePermissions,
  getProjectCodes,
  getRevenues,
  getUtalasraVaro,
  Revenue,
} from "@/lib/api";
import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { EditableBooleanCell } from "@/components/EditableBooleanCell";
import { EditableStatusBadge } from "@/components/EditableStatusBadge";
import { EditableTableCell } from "@/components/EditableTableCell";
import { FinanceMonthlyChart, OutstandingProjectsTable } from "@/components/finance/FinanceSummaryWidgets";
import { SzamlaCsomagLetoltes } from "@/components/finance/SzamlaCsomagLetoltes";
import { UtalasraVaroSzamlak } from "@/components/finance/UtalasraVaroSzamlak";
import { KimenoSzamlaCella } from "@/components/finance/KimenoSzamlaCella";
import { QuickCreateForm } from "@/components/QuickCreateForm";
import { RevenueInvoiceStatus } from "@/components/RevenueInvoiceStatus";
import { StatCard } from "@/components/StatCard";
import { StatusBadge } from "@/components/StatusBadge";
import { TopBar } from "@/components/TopBar";
import { canDoAction } from "@/lib/permissions";

const PAGE = "/penzugyek";

export default async function PenzugyekPage() {
  const [expenses, revenues, summary, projectCodes, expenseFieldTypes, currentUser, pagePermissions, utalasraVaro] =
    await Promise.all([
      getExpenses(),
      getRevenues(),
      getFinanceSummary(),
      getProjectCodes(),
      getFieldTypes("expense"),
      getCurrentUser(),
      getMyPagePermissions(),
      getUtalasraVaro(),
    ]);
  const canCreate = canDoAction(currentUser?.role, pagePermissions, PAGE, "create");
  const canDelete = canDoAction(currentUser?.role, pagePermissions, PAGE, "delete");
  const canEdit = canDoAction(currentUser?.role, pagePermissions, PAGE, "edit");
  const fizetesiModOptions = expenseFieldTypes.kifizetes_modja?.options ?? ["Készpénz", "Átutalás", "Bankkártya"];

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-8 p-8">
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

            {summary.ytd_kiadas_fizetesi_mod_szerint.length > 0 && (
              <Card title="Kiadás fizetési mód szerint (idén)">
                <ul className="divide-y divide-border">
                  {summary.ytd_kiadas_fizetesi_mod_szerint.map((row) => (
                    <li key={row.kifizetes_modja ?? "ismeretlen"} className="flex items-center justify-between py-2 text-[13px]">
                      <span className="text-text-secondary">{row.kifizetes_modja ?? "Nincs megadva"}</span>
                      <span className="font-medium text-text-primary">{formatHuf(row.osszeg)}</span>
                    </li>
                  ))}
                </ul>
              </Card>
            )}
          </>
        )}

        {/* Ami már megérkezett számlaként, de még nem utaltuk el - egy
            listában a három forrásból (kiadás, külsős és belsős TIG), a
            kijelöltek számlái egyben letölthetők. */}
        <Card title={`Utalásra váró számlák (${utalasraVaro.length})`}>
          <UtalasraVaroSzamlak kezdeti={utalasraVaro} />
        </Card>

        {/* Havi számla-csomag a könyvelésnek - egy hónap összes bejövő és
            kimenő számlája egyetlen ZIP-ben. */}
        <Card title="Havi számlák letöltése">
          <SzamlaCsomagLetoltes />
        </Card>

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
              {
                header: "Megnevezés",
                render: (e) =>
                  canEdit ? (
                    <EditableTableCell patchPath={`${ENTITY_PATHS.expense}/${e.id}`} field="megnevezes" value={e.megnevezes} />
                  ) : (
                    e.megnevezes
                  ),
                sortAccessor: (e) => e.megnevezes,
              },
              { header: "Típus", render: (e) => e.tipus ?? "–", sortAccessor: (e) => e.tipus },
              {
                header: "Nettó",
                align: "right",
                render: (e) =>
                  canEdit ? (
                    <EditableTableCell patchPath={`${ENTITY_PATHS.expense}/${e.id}`} field="netto" value={e.netto} type="number" />
                  ) : (
                    formatHuf(e.netto)
                  ),
                sortAccessor: (e) => e.netto,
              },
              { header: "Bruttó", align: "right", render: (e) => formatHuf(e.brutto), sortAccessor: (e) => e.brutto },
              {
                header: "Fizetési mód",
                render: (e) => (
                  <EditableStatusBadge
                    patchPath={`${ENTITY_PATHS.expense}/${e.id}`}
                    field="kifizetes_modja"
                    value={e.kifizetes_modja}
                    options={fizetesiModOptions}
                    placeholder="Nincs megadva"
                  />
                ),
                sortAccessor: (e) => e.kifizetes_modja,
              },
              {
                // A cella tartalma egy ÁLLAPOT ("Kifizetve"/"Nyitott"), ezért a
                // fejléc is "Állapot" - a korábbi "Kész" cím alapján a szűrőben
                // nem lehetett kitalálni, mire kell szűrni.
                header: "Állapot",
                align: "right",
                render: (e) => <StatusBadge label={e.kesz ? "Kifizetve" : "Nyitott"} tone={e.kesz ? "success" : "warning"} />,
                sortAccessor: (e) => (e.kesz ? 1 : 0),
              },
              {
                header: "Beleszámít",
                align: "right",
                render: (e) =>
                  canEdit ? (
                    <EditableBooleanCell
                      patchPath={`${ENTITY_PATHS.expense}/${e.id}`}
                      field="hozzaadas_a_kiadasokhoz"
                      value={e.hozzaadas_a_kiadasokhoz}
                    />
                  ) : (
                    <StatusBadge
                      label={e.hozzaadas_a_kiadasokhoz === false ? "Nem" : "Igen"}
                      tone={e.hozzaadas_a_kiadasokhoz === false ? "neutral" : "success"}
                    />
                  ),
                sortAccessor: (e) => (e.hozzaadas_a_kiadasokhoz === false ? 0 : 1),
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
              {
                header: "Forma",
                render: (r) =>
                  canEdit ? (
                    <EditableTableCell patchPath={`${ENTITY_PATHS.revenue}/${r.id}`} field="bevetel_formaja" value={r.bevetel_formaja} />
                  ) : (
                    r.bevetel_formaja ?? "–"
                  ),
                sortAccessor: (r) => r.bevetel_formaja,
              },
              {
                header: "Nettó",
                align: "right",
                render: (r) =>
                  canEdit ? (
                    <EditableTableCell patchPath={`${ENTITY_PATHS.revenue}/${r.id}`} field="netto" value={r.netto} type="number" />
                  ) : (
                    formatHuf(r.netto)
                  ),
                sortAccessor: (r) => r.netto,
              },
              { header: "Bruttó", align: "right", render: (r) => formatHuf(r.brutto), sortAccessor: (r) => r.brutto },
              { header: "Pénznem", align: "right", render: (r) => r.penznem, sortAccessor: (r) => r.penznem },
              {
                header: "Számla",
                align: "right",
                render: (r) => (
                  <RevenueInvoiceStatus
                    patchPath={`${ENTITY_PATHS.revenue}/${r.id}`}
                    szamlaKiallitva={r.szamla_kiallitva_datuma}
                    fizetve={r.fizetes_datuma}
                  />
                ),
                sortAccessor: (r) => (r.fizetes_datuma ? 2 : r.szamla_kiallitva_datuma ? 1 : 0),
              },
              {
                // A kimenő számla PDF-je: maga a számla külső rendszerben
                // készül, ide azért kerül fel, hogy a havi csomagban is benne
                // legyen (lásd SzamlaCsomagLetoltes).
                header: "Számla fájl",
                align: "right",
                render: (r) => (
                  <KimenoSzamlaCella
                    revenueId={r.id}
                    filename={typeof r.szamla_filename === "string" ? r.szamla_filename : null}
                    url={typeof r.szamla_file_url === "string" ? r.szamla_file_url : null}
                    canEdit={canEdit}
                    canDelete={canDelete}
                  />
                ),
                sortAccessor: (r) => (r.szamla_filename ? 1 : 0),
              },
            ]}
          />
        </Card>
      </div>
    </div>
  );
}
