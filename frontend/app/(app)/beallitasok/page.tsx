import { AccountCard } from "@/components/AccountCard";
import { Card } from "@/components/Card";
import { EmployeeAccessManager } from "@/components/EmployeeAccessManager";
import { RevokeAllOthersButton } from "@/components/RevokeAllOthersButton";
import { TopBar } from "@/components/TopBar";
import {
  ENTITY_PATHS,
  getAllFieldVisibility,
  getAllPageAccess,
  getEmployees,
  getSampleRecord,
} from "@/lib/api";
import { toEditableDetailFields } from "@/lib/detail";
import { pagePermissionGroups } from "@/lib/nav";

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
  {
    entityType: "deliverable",
    label: "Utómunka",
    basePath: ENTITY_PATHS.deliverable,
    hide: [
      "project_code_id",
      "project_id",
      "vago_employee_id",
      "campaign_id",
      "aki_felvezette_employee_id",
      "assigned_to_employee_id",
      "vinyok",
      "megrendeloi_kontaktok_notion_ids",
      "megrendeloi_email_cimek",
      "aki_felvezette_az_utomunkat_notion_ids",
      "aki_ellenorzesbe_tette_notion_ids",
      "assigned_to_notion",
      "visszajelzessek_notion_ids",
      "timesheet_public_notion_ids",
      "timesheet_private_notion_ids",
      "total_time",
      "stop_timer",
    ],
  },
];

export default async function BeallitasokPage() {
  const [employees, pageAccessConfigs, fieldVisibilityConfigs, samples] = await Promise.all([
    getEmployees(),
    getAllPageAccess(),
    getAllFieldVisibility(),
    Promise.all(VISIBILITY_ENTITIES.map((e) => getSampleRecord(e.basePath))),
  ]);
  const pages = pagePermissionGroups();

  const visibilityEntities = VISIBILITY_ENTITIES.map((entity, i) => {
    const sample = samples[i];
    if (!sample) return null;
    return {
      entityType: entity.entityType,
      label: entity.label,
      availableFields: toEditableDetailFields(sample, entity.hide, null).map((f) => ({ key: f.key, label: f.label })),
    };
  }).filter((e): e is { entityType: string; label: string; availableFields: { key: string; label: string }[] } => e !== null);

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-6 p-6">
        <AccountCard />

        <Card title="Felhasználó-kezelés">
          <p className="mb-3 text-[13px] text-text-secondary">
            Válaszd ki (kereséssel) a munkatársat, akinek be szeretnéd állítani a felhasználónevét (email), jelszavát, illetve hogy
            pontosan mely oldalakat és azokon belül mely mezőket lássa - csak admin szerkesztheti, az érintett munkatárs saját maga
            nem módosíthatja.
          </p>
          <EmployeeAccessManager
            employees={employees}
            pages={pages}
            visibilityEntities={visibilityEntities}
            pageAccessConfigs={pageAccessConfigs}
            fieldVisibilityConfigs={fieldVisibilityConfigs}
          />
        </Card>

        <Card title="Veszélyzóna">
          <p className="mb-3 text-[13px] text-text-secondary">
            Egy kattintással törölheted mindenki más hozzáférését (a sajátod kivételével) - a munkatárs-rekordok megmaradnak, csak
            a jelszavuk törlődik és a hozzáférésük áll vissza alapértelmezettre. Utána egyénenként újra beállíthatod, akinek kell.
          </p>
          <RevokeAllOthersButton />
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
