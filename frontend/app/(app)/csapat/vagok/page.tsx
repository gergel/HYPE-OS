import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { EditableTableCell } from "@/components/EditableTableCell";
import { QuickCreateForm } from "@/components/QuickCreateForm";
import { StopClickPropagation } from "@/components/StopClickPropagation";
import { TopBar } from "@/components/TopBar";
import { EmployeeActiveToggle, EmployeeStartDateEditor, EmployeeTipusSelect, RateHourlyEditor } from "@/components/VagoInlineFields";
import { Employee, ENTITY_PATHS, formatDate, getCurrentUser, getEmployees, getMyPagePermissions, getRates, Rate } from "@/lib/api";
import { canDoAction } from "@/lib/permissions";

type VagoRow = Employee & { rate: Rate | null };

const PAGE = "/csapat";

/** Ki számít vágónak: a SZEREPKÖR (role) dönti el, nem az üzleti típus. A
 * tipus mező csak azt mondja meg, hogy az illető külsős vagy belsős - a kettő
 * két külön kérdés, egy vágó ugyanúgy lehet külsős, mint belsős. (Korábban a
 * tipus="vago" jelölte ki ezt a listát, ami épp a külsős/belsős információt
 * írta felül.) */
const VAGO_ROLE = "vago";

/** Vágók (editorok) listája: ki dolgozik nálunk vágóként, mikor kezdett,
 * dolgozik-e még, és mennyi az óradíja - ez utóbbi adja a projektenkénti
 * vágási költség alapját (lásd a Projekt oldal Utómunka szekciójának
 * összesítő sorát, ami a Timesheet.koltseg mezőket szummázza, amit a Start/
 * Stop időmérés az itt megadott óradíj alapján számol ki). */
export default async function VagokPage() {
  const [employees, rates, currentUser, pagePermissions] = await Promise.all([
    getEmployees(),
    getRates(),
    getCurrentUser(),
    getMyPagePermissions(),
  ]);
  const ratesByEmployee = new Map(rates.map((r) => [r.employee_id, r]));
  const rows: VagoRow[] = employees
    .filter((e) => e.role === VAGO_ROLE)
    .map((e) => ({ ...e, rate: ratesByEmployee.get(e.id) ?? null }));
  const canCreate = canDoAction(currentUser, pagePermissions, PAGE, "create");
  const canDelete = canDoAction(currentUser, pagePermissions, PAGE, "delete");
  const canEdit = canDoAction(currentUser, pagePermissions, PAGE, "edit");

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-8">
        <Card title={`Vágók (${rows.length})`}>
          {canCreate && (
            <QuickCreateForm
              postPath={ENTITY_PATHS.employee}
              addLabel="+ Új vágó hozzáadása"
              presetFields={{ role: VAGO_ROLE }}
              fields={[
                { name: "full_name", label: "Név", required: true },
                { name: "email", label: "Email" },
                {
                  name: "tipus",
                  label: "Külsős / Belsős",
                  type: "select",
                  required: true,
                  options: [
                    { value: "kulsos", label: "Külsős" },
                    { value: "belsos", label: "Belsős" },
                  ],
                },
              ]}
            />
          )}
          <DataTable<VagoRow>
            filterable
            rows={rows}
            emptyText="Még nincs vágóként felvett munkatárs - add hozzá fent."
            getHref={(e) => `/csapat/${e.id}?from=vagok`}
            deleteHref={canDelete ? (e) => `${ENTITY_PATHS.employee}/${e.id}` : undefined}
            columns={[
              {
                header: "Név",
                render: (e) =>
                  canEdit ? (
                    <EditableTableCell patchPath={`${ENTITY_PATHS.employee}/${e.id}`} field="full_name" value={e.full_name} />
                  ) : (
                    e.full_name
                  ),
                sortAccessor: (e) => e.full_name,
              },
              {
                header: "Email",
                render: (e) =>
                  canEdit ? (
                    <EditableTableCell patchPath={`${ENTITY_PATHS.employee}/${e.id}`} field="email" value={e.email} />
                  ) : (
                    e.email ?? "–"
                  ),
                sortAccessor: (e) => e.email,
              },
              {
                header: "Külsős / Belsős",
                render: (e) => (
                  <StopClickPropagation>
                    <EmployeeTipusSelect employeeId={e.id} initialValue={e.tipus} />
                  </StopClickPropagation>
                ),
                sortAccessor: (e) => e.tipus,
              },
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
