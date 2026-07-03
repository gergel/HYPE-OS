import { notFound } from "next/navigation";
import { BackLink } from "@/components/BackLink";
import { Card } from "@/components/Card";
import { DetailGrid } from "@/components/DetailGrid";
import { RelatedTable } from "@/components/RelatedTable";
import { TopBar } from "@/components/TopBar";
import { ENTITY_PATHS, getRecord, getRelated } from "@/lib/api";
import { toDetailFields } from "@/lib/detail";

export default async function EmployeeDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const employeeId = Number(id);
  const employee = await getRecord(ENTITY_PATHS.employee, employeeId);
  if (!employee) notFound();

  const [rates, timesheets, expenses, contracts, deliverables, campaigns] = await Promise.all([
    getRelated(ENTITY_PATHS.rate, { employee_id: employeeId }),
    getRelated(ENTITY_PATHS.timesheet, { employee_id: employeeId }),
    getRelated(ENTITY_PATHS.expense, { employee_id: employeeId }),
    getRelated(ENTITY_PATHS.contract, { employee_id: employeeId }),
    getRelated(ENTITY_PATHS.deliverable, { vago_employee_id: employeeId }),
    getRelated(ENTITY_PATHS.campaign, { felelos_employee_id: employeeId }),
  ]);

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-6 p-6">
        <BackLink href="/csapat" label="Csapat" />

        <Card title={String(employee.full_name ?? `Crew tag #${employee.id}`)}>
          <DetailGrid fields={toDetailFields(employee, ["hashed_password"])} />
        </Card>

        <Card title={`Díjak (${rates.length})`}>
          <RelatedTable rows={rates} emptyText="Nincs felvett díj ehhez a crew taghoz." />
        </Card>

        <Card title={`Munkaidő-elszámolások (${timesheets.length})`}>
          <RelatedTable rows={timesheets} emptyText="Nincs munkaidő-elszámolás ehhez a crew taghoz." />
        </Card>

        <Card title={`Kiadások (${expenses.length})`}>
          <RelatedTable rows={expenses} emptyText="Nincs kiadás ehhez a crew taghoz." getHref={(e) => `/penzugyek/kiadas/${e.id}`} />
        </Card>

        <Card title={`Szerződések (${contracts.length})`}>
          <RelatedTable rows={contracts} emptyText="Nincs szerződés ehhez a crew taghoz." />
        </Card>

        <Card title={`Vágott anyagok (${deliverables.length})`}>
          <RelatedTable rows={deliverables} emptyText="Nincs vágandó anyag ehhez a crew taghoz." getHref={(d) => `/utomunka/${d.id}`} />
        </Card>

        <Card title={`Felelős kampányok (${campaigns.length})`}>
          <RelatedTable rows={campaigns} emptyText="Nincs kampány ehhez a crew taghoz." getHref={(c) => `/kampanyok/${c.id}`} />
        </Card>
      </div>
    </div>
  );
}
