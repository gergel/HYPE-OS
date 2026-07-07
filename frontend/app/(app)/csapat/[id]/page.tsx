import { notFound } from "next/navigation";
import { BackLink } from "@/components/BackLink";
import { Card } from "@/components/Card";
import { EditableDetailGrid } from "@/components/EditableDetailGrid";
import { MunkaszerzodesUpload } from "@/components/MunkaszerzodesUpload";
import { RelatedTable } from "@/components/RelatedTable";
import { TopBar } from "@/components/TopBar";
import { ENTITY_PATHS, getEmployeeDocuments, getFieldTypes, getRecord, getRelated, getVisibleFields } from "@/lib/api";
import { toEditableDetailFields } from "@/lib/detail";

/** Ezek az adatok másolódnak át előtöltésként az alvállalkozói eseti
 * szerződés generálásakor (lásd backend/app/api/routes/subcontractor_contracts.py
 * _get_or_create_draft) - ezért egy külön, jól látható szekcióban gyűjtjük
 * össze őket a crew tag oldalán, hogy egyszer kelljen csak kitölteni. */
const VALLALKOZAS_FIELD_KEYS = [
  "vallakozas_neve",
  "vallalkozas_kepviselo",
  "vallakozas_szekhely",
  "vallalkozas_adoszama",
  "nyilvantartasi_szam",
  "megbizas_targya",
  "plusz_afa",
  "email",
];

export default async function EmployeeDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const employeeId = Number(id);
  const employee = await getRecord(ENTITY_PATHS.employee, employeeId);
  if (!employee) notFound();

  const [rates, timesheets, expenses, contracts, deliverables, campaigns, documents, visibleFields, fieldTypes] =
    await Promise.all([
      getRelated(ENTITY_PATHS.rate, { employee_id: employeeId }),
      getRelated(ENTITY_PATHS.timesheet, { employee_id: employeeId }),
      getRelated(ENTITY_PATHS.expense, { employee_id: employeeId }),
      getRelated(ENTITY_PATHS.contract, { employee_id: employeeId }),
      getRelated(ENTITY_PATHS.deliverable, { vago_employee_id: employeeId }),
      getRelated(ENTITY_PATHS.campaign, { felelos_employee_id: employeeId }),
      getEmployeeDocuments(employeeId),
      getVisibleFields("employee"),
      getFieldTypes("employee"),
    ]);

  const vallalkozasFieldKeys = visibleFields
    ? VALLALKOZAS_FIELD_KEYS.filter((k) => visibleFields.includes(k))
    : VALLALKOZAS_FIELD_KEYS;

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-6 p-6">
        <BackLink href="/csapat" label="Csapat" />

        <Card title={String(employee.full_name ?? `Crew tag #${employee.id}`)}>
          <EditableDetailGrid
            patchPath={`${ENTITY_PATHS.employee}/${employee.id}`}
            fields={toEditableDetailFields(
              employee,
              ["hashed_password", ...VALLALKOZAS_FIELD_KEYS],
              visibleFields,
              fieldTypes,
            )}
          />
        </Card>

        {vallalkozasFieldKeys.length > 0 && (
          <Card title="Vállalkozás adatok">
            <EditableDetailGrid
              patchPath={`${ENTITY_PATHS.employee}/${employee.id}`}
              fields={toEditableDetailFields(employee, [], vallalkozasFieldKeys, fieldTypes)}
            />
            <div className={vallalkozasFieldKeys.length > 0 ? "mt-4 border-t border-border pt-4" : ""}>
              <p className="mb-2 text-[11px] text-text-muted">Munkaszerződés</p>
              <MunkaszerzodesUpload employeeId={employee.id} documents={documents} />
            </div>
          </Card>
        )}

        <Card title={`Díjak (${rates.length})`}>
          <RelatedTable rows={rates} emptyText="Nincs felvett díj ehhez a crew taghoz." deleteBasePath={ENTITY_PATHS.rate} />
        </Card>

        <Card title={`Munkaidő-elszámolások (${timesheets.length})`}>
          <RelatedTable
            rows={timesheets}
            emptyText="Nincs munkaidő-elszámolás ehhez a crew taghoz."
            deleteBasePath={ENTITY_PATHS.timesheet}
          />
        </Card>

        <Card title={`Kiadások (${expenses.length})`}>
          <RelatedTable
            rows={expenses}
            emptyText="Nincs kiadás ehhez a crew taghoz."
            getHref={(e) => `/penzugyek/kiadas/${e.id}`}
            deleteBasePath={ENTITY_PATHS.expense}
          />
        </Card>

        <Card title={`Szerződések (${contracts.length})`}>
          <RelatedTable rows={contracts} emptyText="Nincs szerződés ehhez a crew taghoz." deleteBasePath={ENTITY_PATHS.contract} />
        </Card>

        <Card title={`Vágott anyagok (${deliverables.length})`}>
          <RelatedTable
            rows={deliverables}
            emptyText="Nincs vágandó anyag ehhez a crew taghoz."
            getHref={(d) => `/utomunka/${d.id}`}
            deleteBasePath={ENTITY_PATHS.deliverable}
          />
        </Card>

        <Card title={`Felelős kampányok (${campaigns.length})`}>
          <RelatedTable
            rows={campaigns}
            emptyText="Nincs kampány ehhez a crew taghoz."
            getHref={(c) => `/kampanyok/${c.id}`}
            deleteBasePath={ENTITY_PATHS.campaign}
          />
        </Card>
      </div>
    </div>
  );
}
