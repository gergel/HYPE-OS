import { AccountCard } from "@/components/AccountCard";
import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { FieldVisibilityManager } from "@/components/FieldVisibilityManager";
import { StatusBadge } from "@/components/StatusBadge";
import { TopBar } from "@/components/TopBar";
import { Employee, ENTITY_PATHS, getEmployees, getFieldVisibility, getSampleRecord } from "@/lib/api";
import { toEditableDetailFields } from "@/lib/detail";

const ROLE_LABEL: Record<string, string> = {
  admin: "Admin",
  operator: "Operatőr",
  editor: "Vágó",
  client: "Ügyfél",
};

/** A részletnézeteken szereplő entitások, ugyanazokkal a hide-listákkal, mint
 * a saját oldaluk (lásd app/*.tsx), hogy a mező-láthatóság beállítás
 * pontosan azokat a mezőket sorolja fel, amik ténylegesen megjeleníthetők. */
const VISIBILITY_ENTITIES: { entityType: string; label: string; basePath: string; hide: string[] }[] = [
  { entityType: "project", label: "Projektek", basePath: ENTITY_PATHS.project, hide: ["project_code_id", "campaign_id", "crew_employee_ids", "szerzodes_keszites_employee_id", "alvallakozo_keretszerzodes_contract_id"] },
  { entityType: "client", label: "Ügyfelek", basePath: ENTITY_PATHS.client, hide: [] },
  { entityType: "projectCode", label: "Project Code-ok", basePath: ENTITY_PATHS.projectCode, hide: ["client_id", "contract_id"] },
  { entityType: "employee", label: "Crew", basePath: ENTITY_PATHS.employee, hide: ["hashed_password"] },
  { entityType: "equipment", label: "Felszerelés", basePath: ENTITY_PATHS.equipment, hide: ["project_ids"] },
  { entityType: "campaign", label: "Kampányok", basePath: ENTITY_PATHS.campaign, hide: ["felelos_employee_id", "client_id"] },
  { entityType: "task", label: "Feladatok", basePath: ENTITY_PATHS.task, hide: [] },
  { entityType: "expense", label: "Kiadások", basePath: ENTITY_PATHS.expense, hide: ["project_code_id", "employee_id"] },
  { entityType: "revenue", label: "Bevételek", basePath: ENTITY_PATHS.revenue, hide: ["project_code_id"] },
  { entityType: "deliverable", label: "Utómunka", basePath: ENTITY_PATHS.deliverable, hide: ["project_code_id", "project_id", "vago_employee_id", "campaign_id"] },
];

export default async function BeallitasokPage() {
  const [employees, visibilityConfigs, samples] = await Promise.all([
    getEmployees(),
    getFieldVisibility(),
    Promise.all(VISIBILITY_ENTITIES.map((e) => getSampleRecord(e.basePath))),
  ]);
  const visibleFieldsByEntity = new Map(visibilityConfigs.map((c) => [c.entity_type, c.visible_fields]));

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-6 p-6">
        <AccountCard />

        <Card title={`Csapattagok és szerepkörök (${employees.length})`}>
          <DataTable<Employee>
            rows={employees}
            emptyText="Még nincs felvett crew tag."
            getHref={(e) => `/csapat/${e.id}`}
            columns={[
              { header: "Név", render: (e) => e.full_name },
              { header: "Email", render: (e) => e.email ?? "–" },
              { header: "Szerepkör", render: (e) => <StatusBadge label={ROLE_LABEL[e.role] ?? e.role} tone="neutral" /> },
              {
                header: "Aktív",
                align: "right",
                render: (e) => <StatusBadge label={e.is_active ? "Aktív" : "Inaktív"} tone={e.is_active ? "success" : "neutral"} />,
              },
            ]}
          />
        </Card>

        <Card title="Mező-láthatóság">
          <p className="mb-3 text-[13px] text-text-secondary">
            Melyik mezők jelenjenek meg az egyes részletnézeteken - mindenkire egyformán vonatkozik, csak admin szerkesztheti.
          </p>
          <div className="space-y-2">
            {VISIBILITY_ENTITIES.map((entity, i) => {
              const sample = samples[i];
              if (!sample) return null;
              const availableFields = toEditableDetailFields(sample, entity.hide, null).map((f) => ({ key: f.key, label: f.label }));
              return (
                <FieldVisibilityManager
                  key={entity.entityType}
                  entityType={entity.entityType}
                  entityLabel={entity.label}
                  availableFields={availableFields}
                  initialVisible={visibleFieldsByEntity.get(entity.entityType) ?? null}
                />
              );
            })}
          </div>
        </Card>

        <Card title="Rendszer">
          <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
            <div>
              <dt className="text-[12px] text-text-muted">API cím</dt>
              <dd className="mt-0.5 text-[13px] text-text-primary">{process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}</dd>
            </div>
            <div>
              <dt className="text-[12px] text-text-muted">Adatforrás</dt>
              <dd className="mt-0.5 text-[13px] text-text-primary">Notion import (idempotens, egyenkénti mezőleképezéssel)</dd>
            </div>
          </dl>
        </Card>
      </div>
    </div>
  );
}
