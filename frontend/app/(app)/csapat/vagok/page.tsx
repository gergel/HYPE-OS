import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { QuickCreateForm } from "@/components/QuickCreateForm";
import { StopClickPropagation } from "@/components/StopClickPropagation";
import { TopBar } from "@/components/TopBar";
import { EmployeeActiveToggle, EmployeeStartDateEditor, RateHourlyEditor } from "@/components/VagoInlineFields";
import { Employee, ENTITY_PATHS, formatDate, getEmployees, getRates, Rate } from "@/lib/api";

type VagoRow = Employee & { rate: Rate | null };

/** Vágók (editorok) listája: ki dolgozik nálunk vágóként, mikor kezdett,
 * dolgozik-e még, és mennyi az óradíja - ez utóbbi adja a projektenkénti
 * vágási költség alapját (lásd a Projekt oldal Utómunka szekciójának
 * összesítő sorát, ami a Timesheet.koltseg mezőket szummázza, amit a Start/
 * Stop időmérés az itt megadott óradíj alapján számol ki). */
export default async function VagokPage() {
  const [employees, rates] = await Promise.all([getEmployees(), getRates()]);
  const ratesByEmployee = new Map(rates.map((r) => [r.employee_id, r]));
  const rows: VagoRow[] = employees
    .filter((e) => e.tipus === "vago")
    .map((e) => ({ ...e, rate: ratesByEmployee.get(e.id) ?? null }));

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-6">
        <Card title={`Vágók (${rows.length})`}>
          <QuickCreateForm
            postPath={ENTITY_PATHS.employee}
            addLabel="+ Új vágó hozzáadása"
            presetFields={{ tipus: "vago" }}
            fields={[
              { name: "full_name", label: "Név", required: true },
              { name: "email", label: "Email" },
            ]}
          />
          <DataTable<VagoRow>
            rows={rows}
            emptyText="Még nincs vágóként felvett munkatárs - add hozzá fent."
            getHref={(e) => `/csapat/${e.id}`}
            columns={[
              { header: "Név", render: (e) => e.full_name, sortAccessor: (e) => e.full_name },
              { header: "Email", render: (e) => e.email ?? "–", sortAccessor: (e) => e.email },
              {
                header: "Első munkanap",
                render: (e) => (
                  <StopClickPropagation>
                    <EmployeeStartDateEditor employeeId={e.id} initialValue={e.elso_munkanap} />
                  </StopClickPropagation>
                ),
                sortAccessor: (e) => e.elso_munkanap,
              },
              {
                header: "Aktív",
                render: (e) => (
                  <StopClickPropagation>
                    <EmployeeActiveToggle employeeId={e.id} initialActive={e.is_active} />
                  </StopClickPropagation>
                ),
                sortAccessor: (e) => (e.is_active ? 1 : 0),
              },
              {
                header: "Óradíj",
                render: (e) => (
                  <StopClickPropagation>
                    <RateHourlyEditor employeeId={e.id} rateId={e.rate?.id ?? null} initialValue={e.rate?.orabler ?? null} />
                  </StopClickPropagation>
                ),
                sortAccessor: (e) => e.rate?.orabler ?? null,
              },
              {
                header: "Utolsó munkanap",
                render: (e) => formatDate(e.utolso_munkanap),
                sortAccessor: (e) => e.utolso_munkanap,
              },
            ]}
          />
        </Card>
      </div>
    </div>
  );
}
